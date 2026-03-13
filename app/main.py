from __future__ import annotations

from datetime import date
from math import sqrt
from statistics import quantiles
from typing import Literal

from fastapi import FastAPI, Depends, Query, status, Request
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from sqlalchemy import func

from .database import Base, engine, get_db
from . import models, schemas

from pydantic import BaseModel

class ObservationCreateIn(BaseModel):
    city_id: int
    date: date
    temp_c: float | None = None
    pm25: float | None = None

def _mean_std(values: list[float]) -> tuple[float, float]:
    n = len(values)
    mean = sum(values) / n
    var = sum((v - mean) ** 2 for v in values) / n
    std = sqrt(var)
    return mean, std


def _rolling_mean_std(values: list[float], window: int, idx: int) -> tuple[float | None, float | None]:
    start_i = max(0, idx - window)
    base = values[start_i:idx]
    base = [v for v in base if v is not None]
    if len(base) < 2:
        return None, None
    mean, std = _mean_std([float(v) for v in base])
    if std == 0:
        return mean, 0.0
    return mean, std


def _rolling_std(values: list[float | None], window: int, idx: int) -> float | None:
    start_i = max(0, idx - window + 1)
    w = [v for v in values[start_i:idx + 1] if v is not None]
    if len(w) < 2:
        return None
    _, std = _mean_std([float(v) for v in w])
    return std


class ProblemException(Exception):
    def __init__(self, *, status: int, title: str, detail: str, type_: str = "about:blank"):
        self.status = status
        self.title = title
        self.detail = detail
        self.type_ = type_


app = FastAPI(
    title="COMP3011 Climate & Urban Environment Statistics API",
    version="1.0.0",
    description="Stores historical city observations (temperature + PM2.5) and provides analytics endpoints.",
)


@app.exception_handler(ProblemException)
def problem_exception_handler(request: Request, exc: ProblemException):
    return JSONResponse(
        status_code=exc.status,
        content={
            "type": exc.type_,
            "title": exc.title,
            "status": exc.status,
            "detail": exc.detail,
            "instance": str(request.url.path),
        },
    )


@app.on_event("startup")
def on_startup():
    Base.metadata.create_all(bind=engine)


app.mount("/static", StaticFiles(directory="app/static"), name="static")


@app.get("/dashboard", include_in_schema=False)
def dashboard():
    return FileResponse("app/static/dashboard.html")


def get_city_or_404(db: Session, city_id: int) -> models.City:
    city = db.get(models.City, city_id)
    if not city:
        raise ProblemException(
            status=404,
            title="City not found",
            detail=f"City with id={city_id} does not exist.",
            type_="https://example.com/problems/city-not-found",
        )
    return city


@app.get(
    "/",
    tags=["Meta"],
    summary="API status",
    description="Returns a simple message confirming that the API is running."
)
def root():
    return {"message": "API is running. Visit /docs for Swagger UI."}


# -------------------- City CRUD --------------------
@app.post(
    "/cities",
    response_model=schemas.CityOut,
    status_code=status.HTTP_201_CREATED,
    tags=["Cities"],
    summary="Create a city",
    description="Creates a new city record with name, country, latitude, and longitude."
)
def create_city(payload: schemas.CityCreate, db: Session = Depends(get_db)):
    city = models.City(
        name=payload.name.strip(),
        country=payload.country.strip(),
        lat=payload.lat,
        lon=payload.lon,
    )
    db.add(city)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ProblemException(
            status=409,
            title="Duplicate city",
            detail="City already exists (same name + country).",
            type_="https://example.com/problems/duplicate-city",
        )
    db.refresh(city)
    return city


@app.get(
    "/cities",
    response_model=list[schemas.CityOut],
    tags=["Cities"],
    summary="List all cities",
    description="Returns all cities stored in the database, ordered by country and city name."
)
def list_cities(db: Session = Depends(get_db)):
    return db.query(models.City).order_by(models.City.country.asc(), models.City.name.asc()).all()


@app.get(
    "/cities/compare",
    response_model=schemas.CityCompareOut,
    tags=["Analytics"],
    summary="Compare two cities",
    description="Compares two cities over a selected date range using average temperature and PM2.5 statistics."
)
def compare_cities(
    city1: int = Query(..., ge=1),
    city2: int = Query(..., ge=1),
    start: date = Query(...),
    end: date = Query(...),
    db: Session = Depends(get_db),
):
    if city1 == city2:
        raise ProblemException(
            status=422,
            title="Invalid city comparison",
            detail="city1 and city2 must be different",
            type_="https://example.com/problems/invalid-city-comparison",
        )
    if end < start:
        raise ProblemException(
            status=422,
            title="Invalid date range",
            detail="end must be >= start",
            type_="https://example.com/problems/invalid-date-range",
        )

    c1 = get_city_or_404(db, city1)
    c2 = get_city_or_404(db, city2)

    def build_stats(city: models.City) -> schemas.CityCompareStats:
        rows = (
            db.query(models.Observation)
            .filter(models.Observation.city_id == city.id)
            .filter(models.Observation.obs_date >= start)
            .filter(models.Observation.obs_date <= end)
            .all()
        )

        if not rows:
            raise ProblemException(
                status=404,
                title="No observations found",
                detail=f"No observations for {city.name} in that date range.",
                type_="https://example.com/problems/no-observations",
            )

        temps = [float(r.temp_c) for r in rows if r.temp_c is not None]
        pm25s = [float(r.pm25) for r in rows if r.pm25 is not None]

        return schemas.CityCompareStats(
            city_id=city.id,
            city_name=city.name,
            country=city.country,
            start=start,
            end=end,
            count_days=len(rows),
            avg_temp_c=(sum(temps) / len(temps)) if temps else None,
            avg_pm25=(sum(pm25s) / len(pm25s)) if pm25s else None,
            max_temp_c=max(temps) if temps else None,
            max_pm25=max(pm25s) if pm25s else None,
        )

    s1 = build_stats(c1)
    s2 = build_stats(c2)

    hotter_city = None
    if s1.avg_temp_c is not None and s2.avg_temp_c is not None:
        if s1.avg_temp_c > s2.avg_temp_c:
            hotter_city = s1.city_name
        elif s2.avg_temp_c > s1.avg_temp_c:
            hotter_city = s2.city_name

    more_polluted_city = None
    if s1.avg_pm25 is not None and s2.avg_pm25 is not None:
        if s1.avg_pm25 > s2.avg_pm25:
            more_polluted_city = s1.city_name
        elif s2.avg_pm25 > s1.avg_pm25:
            more_polluted_city = s2.city_name

    temp_diff_avg = None
    if s1.avg_temp_c is not None and s2.avg_temp_c is not None:
        temp_diff_avg = round(s1.avg_temp_c - s2.avg_temp_c, 2)

    pm25_diff_avg = None
    if s1.avg_pm25 is not None and s2.avg_pm25 is not None:
        pm25_diff_avg = round(s1.avg_pm25 - s2.avg_pm25, 2)

    return schemas.CityCompareOut(
        city_1=s1,
        city_2=s2,
        hotter_city=hotter_city,
        more_polluted_city=more_polluted_city,
        temp_diff_avg=temp_diff_avg,
        pm25_diff_avg=pm25_diff_avg,
    )


@app.get(
    "/cities/rankings",
    response_model=schemas.CityRankingOut,
    tags=["Analytics"],
    summary="Rank cities by metric",
    description="Ranks cities by average temperature, average PM2.5, or computed environmental risk over a selected date range."
)
def city_rankings(
    metric: str = Query(..., pattern="^(temp_c|pm25|risk)$"),
    start: date = Query(...),
    end: date = Query(...),
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
):
    if end < start:
        raise ProblemException(
            status=422,
            title="Invalid date range",
            detail="end must be >= start",
            type_="https://example.com/problems/invalid-date-range",
        )

    cities = db.query(models.City).all()
    rankings: list[schemas.CityRankingItem] = []

    for city in cities:
        rows = (
            db.query(models.Observation)
            .filter(models.Observation.city_id == city.id)
            .filter(models.Observation.obs_date >= start)
            .filter(models.Observation.obs_date <= end)
            .all()
        )

        if not rows:
            continue

        temps = [float(r.temp_c) for r in rows if r.temp_c is not None]
        pm25s = [float(r.pm25) for r in rows if r.pm25 is not None]

        value = None

        if metric == "temp_c":
            if temps:
                value = sum(temps) / len(temps)

        elif metric == "pm25":
            if pm25s:
                value = sum(pm25s) / len(pm25s)

        elif metric == "risk":
            temp_std = _mean_std(temps)[1] if len(temps) >= 2 else 0.0
            pm25_std = _mean_std(pm25s)[1] if len(pm25s) >= 2 else 0.0

            def anomaly_rate(values: list[float], threshold: float = 2.0) -> float:
                if len(values) < 3:
                    return 0.0
                mean, std = _mean_std(values)
                if std == 0:
                    return 0.0
                count = sum(1 for v in values if abs((v - mean) / std) >= threshold)
                return count / len(values)

            def slope(values: list[float]) -> float:
                if len(values) < 2:
                    return 0.0
                return values[-1] - values[0]

            temp_anom = anomaly_rate(temps, 2.0)
            pm25_anom = anomaly_rate(pm25s, 2.0)
            temp_slope = slope(temps)
            pm25_slope = slope(pm25s)

            value = (
                min(temp_std * 5.0, 35.0)
                + min(pm25_std * 1.0, 35.0)
                + min((temp_anom + pm25_anom) * 50.0, 20.0)
                + min((abs(temp_slope) + abs(pm25_slope)) * 2.0, 10.0)
            )
            value = float(max(0.0, min(100.0, value)))

        if value is not None:
            rankings.append(
                schemas.CityRankingItem(
                    city_id=city.id,
                    city_name=city.name,
                    country=city.country,
                    value=round(float(value), 2),
                )
            )

    rankings.sort(key=lambda x: x.value, reverse=True)

    return schemas.CityRankingOut(
        metric=metric,
        start=start,
        end=end,
        limit=limit,
        rankings=rankings[:limit],
    )


@app.get(
    "/cities/{city_id}",
    response_model=schemas.CityOut,
    tags=["Cities"],
    summary="Get a city",
    description="Returns details for a single city by ID."
)
def get_city(city_id: int, db: Session = Depends(get_db)):
    return get_city_or_404(db, city_id)


@app.put(
    "/cities/{city_id}",
    response_model=schemas.CityOut,
    tags=["Cities"],
    summary="Update a city",
    description="Updates an existing city record."
)
def update_city(city_id: int, payload: schemas.CityUpdate, db: Session = Depends(get_db)):
    city = get_city_or_404(db, city_id)

    if payload.name is not None:
        city.name = payload.name.strip()
    if payload.country is not None:
        city.country = payload.country.strip()
    if payload.lat is not None:
        city.lat = payload.lat
    if payload.lon is not None:
        city.lon = payload.lon

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ProblemException(
            status=409,
            title="Duplicate city",
            detail="Update would duplicate an existing city (name + country).",
            type_="https://example.com/problems/duplicate-city",
        )
    db.refresh(city)
    return city


@app.delete(
    "/cities/{city_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["Cities"],
    summary="Delete a city",
    description="Deletes a city and its associated observations."
)
def delete_city(city_id: int, db: Session = Depends(get_db)):
    city = get_city_or_404(db, city_id)
    db.delete(city)
    db.commit()
    return None


# -------------------- Observations (read/query) --------------------
@app.get(
    "/observations",
    response_model=list[schemas.ObservationOut],
    tags=["Observations"],
    summary="Query observations",
    description="Returns environmental observations for a city with optional date filtering, sorting, and pagination."
)
def query_observations(
    city_id: int = Query(..., ge=1),
    start: date | None = None,
    end: date | None = None,
    limit: int = Query(200, ge=1, le=2000),
    offset: int = Query(0, ge=0),
    sort: str = Query("obs_date", pattern="^(obs_date|temp_c|pm25)$"),
    order: str = Query("asc", pattern="^(asc|desc)$"),
    db: Session = Depends(get_db),
):
    get_city_or_404(db, city_id)

    q = db.query(models.Observation).filter(models.Observation.city_id == city_id)

    if start is not None:
        q = q.filter(models.Observation.obs_date >= start)
    if end is not None:
        q = q.filter(models.Observation.obs_date <= end)

    sort_col = {
        "obs_date": models.Observation.obs_date,
        "temp_c": models.Observation.temp_c,
        "pm25": models.Observation.pm25,
    }[sort]

    q = q.order_by(sort_col.asc() if order == "asc" else sort_col.desc())
    return q.offset(offset).limit(limit).all()
# -------------------- Observations (create) --------------------
@app.post(
    "/observations",
    status_code=status.HTTP_201_CREATED,
    tags=["Observations"],
    summary="Create an observation",
    description="Creates a new environmental observation for a city on a specific date."
)
def create_observation(payload: ObservationCreateIn, db: Session = Depends(get_db)):
    # make sure city exists
    get_city_or_404(db, payload.city_id)

    obs = models.Observation(
        city_id=payload.city_id,
        obs_date=payload.date,
        temp_c=payload.temp_c,
        pm25=payload.pm25,
    )

    db.add(obs)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ProblemException(
            status=409,
            title="Duplicate observation",
            detail="An observation already exists for this city on that date.",
            type_="https://example.com/problems/duplicate-observation",
        )

    db.refresh(obs)

    return {
        "id": obs.id,
        "city_id": obs.city_id,
        "date": obs.obs_date,
        "temp_c": obs.temp_c,
        "pm25": obs.pm25,
    }
# -------------------- Analytics --------------------
@app.get(
    "/cities/{city_id}/summary",
    response_model=schemas.CitySummaryOut,
    tags=["Analytics"],
    summary="Compute summary statistics",
    description="Returns average, minimum, and maximum temperature and PM2.5 values for a city within a selected date range."
)
def city_summary(
    city_id: int,
    start: date = Query(...),
    end: date = Query(...),
    db: Session = Depends(get_db),
):
    if end < start:
        raise ProblemException(
            status=422,
            title="Invalid date range",
            detail="end must be >= start",
            type_="https://example.com/problems/invalid-date-range",
        )

    get_city_or_404(db, city_id)

    base = (
        db.query(models.Observation)
        .filter(models.Observation.city_id == city_id)
        .filter(models.Observation.obs_date >= start)
        .filter(models.Observation.obs_date <= end)
    )

    count_days = base.count()
    if count_days == 0:
        raise ProblemException(
            status=404,
            title="No observations found",
            detail="No observations for that city and date range.",
            type_="https://example.com/problems/no-observations",
        )

    temp_stats = db.query(
        func.avg(models.Observation.temp_c),
        func.min(models.Observation.temp_c),
        func.max(models.Observation.temp_c),
    ).filter(
        models.Observation.city_id == city_id,
        models.Observation.obs_date >= start,
        models.Observation.obs_date <= end,
        models.Observation.temp_c.isnot(None),
    ).one()

    pm25_stats = db.query(
        func.avg(models.Observation.pm25),
        func.min(models.Observation.pm25),
        func.max(models.Observation.pm25),
    ).filter(
        models.Observation.city_id == city_id,
        models.Observation.obs_date >= start,
        models.Observation.obs_date <= end,
        models.Observation.pm25.isnot(None),
    ).one()

    def f(x):
        return float(x) if x is not None else None

    return schemas.CitySummaryOut(
        city_id=city_id,
        start=start,
        end=end,
        count_days=count_days,
        avg_temp_c=f(temp_stats[0]),
        min_temp_c=f(temp_stats[1]),
        max_temp_c=f(temp_stats[2]),
        avg_pm25=f(pm25_stats[0]),
        min_pm25=f(pm25_stats[1]),
        max_pm25=f(pm25_stats[2]),
    )


@app.get(
    "/cities/{city_id}/trend",
    response_model=schemas.TrendOut,
    tags=["Analytics"],
    summary="Get trend data",
    description="Returns time-series values and moving averages for temperature or PM2.5 over a selected date range."
)
def city_trend(
    city_id: int,
    metric: str = Query("temp_c", pattern="^(temp_c|pm25)$"),
    start: date = Query(...),
    end: date = Query(...),
    window: int = Query(7, ge=1, le=60),
    db: Session = Depends(get_db),
):
    if end < start:
        raise ProblemException(
            status=422,
            title="Invalid date range",
            detail="end must be >= start",
            type_="https://example.com/problems/invalid-date-range",
        )

    get_city_or_404(db, city_id)
    field = models.Observation.temp_c if metric == "temp_c" else models.Observation.pm25

    rows = (
        db.query(models.Observation.obs_date, field)
        .filter(models.Observation.city_id == city_id)
        .filter(models.Observation.obs_date >= start)
        .filter(models.Observation.obs_date <= end)
        .order_by(models.Observation.obs_date.asc())
        .all()
    )
    if not rows:
        raise ProblemException(
            status=404,
            title="No observations found",
            detail="No observations for that city and date range.",
            type_="https://example.com/problems/no-observations",
        )

    dates = [d for d, _ in rows]
    values = [float(v) if v is not None else None for _, v in rows]

    points = []
    for i in range(len(values)):
        start_i = max(0, i - window + 1)
        window_vals = [v for v in values[start_i: i + 1] if v is not None]
        ma = (sum(window_vals) / len(window_vals)) if window_vals else None
        points.append(schemas.TrendPoint(date=dates[i], value=values[i], moving_avg=ma))

    return schemas.TrendOut(
        city_id=city_id,
        metric=metric,
        start=start,
        end=end,
        window=window,
        points=points,
    )


@app.get(
    "/cities/{city_id}/anomalies",
    response_model=schemas.AnomalyOut,
    tags=["Analytics"],
    summary="Detect anomalies",
    description="Detects unusual temperature or PM2.5 values using z-score, rolling z-score, or IQR methods."
)
def city_anomalies(
    city_id: int,
    metric: str = Query("temp_c", pattern="^(temp_c|pm25)$"),
    start: date = Query(...),
    end: date = Query(...),
    method: str = Query("zscore", pattern="^(zscore|rolling_zscore|iqr)$"),
    threshold: float = Query(2.0, ge=0.5, le=10.0),
    window: int = Query(14, ge=3, le=120),
    k: float = Query(1.5, ge=0.5, le=10.0),
    db: Session = Depends(get_db),
):
    if end < start:
        raise ProblemException(
            status=422,
            title="Invalid date range",
            detail="end must be >= start",
            type_="https://example.com/problems/invalid-date-range",
        )

    get_city_or_404(db, city_id)

    field = models.Observation.temp_c if metric == "temp_c" else models.Observation.pm25

    rows = (
        db.query(models.Observation.obs_date, field)
        .filter(models.Observation.city_id == city_id)
        .filter(models.Observation.obs_date >= start)
        .filter(models.Observation.obs_date <= end)
        .filter(field.isnot(None))
        .order_by(models.Observation.obs_date.asc())
        .all()
    )

    if not rows:
        raise ProblemException(
            status=404,
            title="No observations found",
            detail="No observations for that city and date range.",
            type_="https://example.com/problems/no-observations",
        )

    dates = [d for d, _ in rows]
    values = [float(v) for _, v in rows]

    anomalies: list[schemas.AnomalyPoint] = []

    if method == "zscore":
        mean, std = _mean_std(values)
        if std == 0:
            return schemas.AnomalyOut(
                city_id=city_id,
                metric=metric,
                start=start,
                end=end,
                method="zscore",
                threshold=threshold,
                mean=float(mean),
                std=0.0,
                anomalies=[],
            )

        for d, v in zip(dates, values):
            z = (v - mean) / std
            if abs(z) >= threshold:
                anomalies.append(
                    schemas.AnomalyPoint(
                        date=d,
                        value=v,
                        score=float(z),
                        direction="high" if z > 0 else "low",
                    )
                )

        return schemas.AnomalyOut(
            city_id=city_id,
            metric=metric,
            start=start,
            end=end,
            method="zscore",
            threshold=float(threshold),
            mean=float(mean),
            std=float(std),
            anomalies=anomalies,
        )

    if method == "rolling_zscore":
        for i, (d, v) in enumerate(zip(dates, values)):
            mean_i, std_i = _rolling_mean_std(values, window, i)
            if mean_i is None or std_i is None or std_i == 0:
                continue
            z = (v - mean_i) / std_i
            if abs(z) >= threshold:
                anomalies.append(
                    schemas.AnomalyPoint(
                        date=d,
                        value=v,
                        score=float(z),
                        direction="high" if z > 0 else "low",
                    )
                )

        mean_g, std_g = _mean_std(values)
        return schemas.AnomalyOut(
            city_id=city_id,
            metric=metric,
            start=start,
            end=end,
            method="rolling_zscore",
            window=window,
            threshold=float(threshold),
            mean=float(mean_g),
            std=float(std_g),
            anomalies=anomalies,
        )

    qs = quantiles(values, n=4, method="inclusive")
    q1, q3 = float(qs[0]), float(qs[2])
    iqr = q3 - q1
    low_cut = q1 - k * iqr
    high_cut = q3 + k * iqr

    for d, v in zip(dates, values):
        if v < low_cut or v > high_cut:
            if v < low_cut:
                score = (low_cut - v) / iqr if iqr != 0 else 0.0
                direction = "low"
            else:
                score = (v - high_cut) / iqr if iqr != 0 else 0.0
                direction = "high"

            anomalies.append(
                schemas.AnomalyPoint(date=d, value=v, score=float(score), direction=direction)
            )

    return schemas.AnomalyOut(
        city_id=city_id,
        metric=metric,
        start=start,
        end=end,
        method="iqr",
        k=float(k),
        q1=q1,
        q3=q3,
        iqr=float(iqr),
        anomalies=anomalies,
    )


@app.get(
    "/cities/{city_id}/risk-score",
    response_model=schemas.RiskScoreOut,
    tags=["Analytics"],
    summary="Compute risk score",
    description="Computes a simple environmental risk score using variability, anomaly rate, and trend slope."
)
def city_risk_score(
    city_id: int,
    start: date = Query(...),
    end: date = Query(...),
    db: Session = Depends(get_db),
):
    if end < start:
        raise ProblemException(
            status=422,
            title="Invalid date range",
            detail="end must be >= start",
            type_="https://example.com/problems/invalid-date-range",
        )

    get_city_or_404(db, city_id)

    rows = (
        db.query(models.Observation.obs_date, models.Observation.temp_c, models.Observation.pm25)
        .filter(models.Observation.city_id == city_id)
        .filter(models.Observation.obs_date >= start)
        .filter(models.Observation.obs_date <= end)
        .order_by(models.Observation.obs_date.asc())
        .all()
    )
    if not rows:
        raise ProblemException(
            status=404,
            title="No observations found",
            detail="No observations for that city and date range.",
            type_="https://example.com/problems/no-observations",
        )

    temps = [float(t) for _, t, _ in rows if t is not None]
    pm25s = [float(p) for _, _, p in rows if p is not None]

    temp_std = _mean_std(temps)[1] if len(temps) >= 2 else 0.0
    pm25_std = _mean_std(pm25s)[1] if len(pm25s) >= 2 else 0.0

    def anomaly_rate(values: list[float], threshold: float = 2.0) -> float:
        if len(values) < 3:
            return 0.0
        mean, std = _mean_std(values)
        if std == 0:
            return 0.0
        count = sum(1 for v in values if abs((v - mean) / std) >= threshold)
        return count / len(values)

    temp_anom = anomaly_rate(temps, 2.0)
    pm25_anom = anomaly_rate(pm25s, 2.0)

    def slope(values: list[float]) -> float:
        if len(values) < 2:
            return 0.0
        return values[-1] - values[0]

    temp_slope = slope(temps)
    pm25_slope = slope(pm25s)

    score = (
        min(temp_std * 5.0, 35.0)
        + min(pm25_std * 1.0, 35.0)
        + min((temp_anom + pm25_anom) * 50.0, 20.0)
        + min((abs(temp_slope) + abs(pm25_slope)) * 2.0, 10.0)
    )

    score = float(max(0.0, min(100.0, score)))
    label = "Low" if score < 34 else ("Moderate" if score < 67 else "High")

    return schemas.RiskScoreOut(
        city_id=city_id,
        start=start,
        end=end,
        risk_score=score,
        label=label,
        components={
            "temp_std": float(temp_std),
            "pm25_std": float(pm25_std),
            "temp_anomaly_rate": float(temp_anom),
            "pm25_anomaly_rate": float(pm25_anom),
            "temp_slope": float(temp_slope),
            "pm25_slope": float(pm25_slope),
        },
    )


@app.get(
    "/cities/{city_id}/regimes",
    response_model=schemas.RegimesOut,
    tags=["Analytics"],
    summary="Classify environmental regimes",
    description="Classifies observations as Stable, Volatile, or Extreme using rolling standard deviation."
)
def city_regimes(
    city_id: int,
    metric: str = Query("temp_c", pattern="^(temp_c|pm25)$"),
    start: date = Query(...),
    end: date = Query(...),
    window: int = Query(14, ge=3, le=120),
    db: Session = Depends(get_db),
):
    if end < start:
        raise ProblemException(
            status=422,
            title="Invalid date range",
            detail="end must be >= start",
            type_="https://example.com/problems/invalid-date-range",
        )

    get_city_or_404(db, city_id)

    field = models.Observation.temp_c if metric == "temp_c" else models.Observation.pm25

    rows = (
        db.query(models.Observation.obs_date, field)
        .filter(models.Observation.city_id == city_id)
        .filter(models.Observation.obs_date >= start)
        .filter(models.Observation.obs_date <= end)
        .order_by(models.Observation.obs_date.asc())
        .all()
    )
    if not rows:
        raise ProblemException(
            status=404,
            title="No observations found",
            detail="No observations for that city and date range.",
            type_="https://example.com/problems/no-observations",
        )

    dates = [d for d, _ in rows]
    values = [float(v) if v is not None else None for _, v in rows]

    stds = []
    for i in range(len(values)):
        stds.append(_rolling_std(values, window, i))

    std_vals = [s for s in stds if s is not None]
    if len(std_vals) < 3:
        points = [
            schemas.RegimePoint(date=dates[i], value=values[i], rolling_std=stds[i], regime="Stable")
            for i in range(len(values))
        ]
        return schemas.RegimesOut(
            city_id=city_id,
            metric=metric,
            start=start,
            end=end,
            window=window,
            points=points,
        )

    qs = quantiles(std_vals, n=4, method="inclusive")
    q1, q3 = float(qs[0]), float(qs[2])

    def classify(s: float | None) -> Literal["Stable", "Volatile", "Extreme"]:
        if s is None:
            return "Stable"
        if s >= q3:
            return "Extreme"
        if s >= q1:
            return "Volatile"
        return "Stable"

    points = [
        schemas.RegimePoint(
            date=dates[i],
            value=values[i],
            rolling_std=stds[i],
            regime=classify(stds[i]),
        )
        for i in range(len(values))
    ]

    return schemas.RegimesOut(
        city_id=city_id,
        metric=metric,
        start=start,
        end=end,
        window=window,
        points=points,
    )


@app.get(
    "/cities/{city_id}/insights",
    response_model=schemas.CityInsightsOut,
    tags=["Analytics"],
    summary="Generate environmental insight",
    description="Returns a short natural-language summary of environmental conditions and overall risk level."
)
def city_insights(
    city_id: int,
    start: date = Query(...),
    end: date = Query(...),
    db: Session = Depends(get_db),
):
    if end < start:
        raise ProblemException(
            status=422,
            title="Invalid date range",
            detail="end must be >= start",
            type_="https://example.com/problems/invalid-date-range",
        )

    city = get_city_or_404(db, city_id)

    rows = (
        db.query(models.Observation)
        .filter(models.Observation.city_id == city_id)
        .filter(models.Observation.obs_date >= start)
        .filter(models.Observation.obs_date <= end)
        .all()
    )

    if not rows:
        raise ProblemException(
            status=404,
            title="No observations found",
            detail="No observations for that date range.",
            type_="https://example.com/problems/no-observations",
        )

    temps = [float(r.temp_c) for r in rows if r.temp_c is not None]
    pm25s = [float(r.pm25) for r in rows if r.pm25 is not None]

    avg_temp = sum(temps) / len(temps) if temps else None
    avg_pm25 = sum(pm25s) / len(pm25s) if pm25s else None

    insight_parts = []

    if avg_temp is not None:
        if avg_temp > 30:
            insight_parts.append("very high temperatures")
        elif avg_temp > 20:
            insight_parts.append("moderately warm temperatures")
        else:
            insight_parts.append("relatively mild temperatures")

    if avg_pm25 is not None:
        if avg_pm25 > 100:
            insight_parts.append("extreme PM2.5 pollution")
        elif avg_pm25 > 50:
            insight_parts.append("high PM2.5 pollution")
        elif avg_pm25 > 15:
            insight_parts.append("moderate air pollution")
        else:
            insight_parts.append("relatively clean air")

    risk_score = 0
    if avg_temp is not None:
        risk_score += avg_temp * 0.5
    if avg_pm25 is not None:
        risk_score += avg_pm25 * 0.3

    if risk_score < 30:
        risk_level = "Low"
    elif risk_score < 70:
        risk_level = "Moderate"
    else:
        risk_level = "High"

    insight = (
        f"{city.name} experienced "
        + " and ".join(insight_parts)
        + f" between {start} and {end}. "
        + f"Overall environmental risk was classified as {risk_level}."
    )

    return schemas.CityInsightsOut(
        city_id=city.id,
        city_name=city.name,
        start=start,
        end=end,
        insight=insight,
    )