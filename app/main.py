from __future__ import annotations
from math import sqrt

from fastapi import Request
from fastapi.responses import JSONResponse


from datetime import date
from fastapi import FastAPI, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from sqlalchemy import func

from .database import Base, engine, get_db
from . import models, schemas  # <-- relative import (forces local models)

from math import sqrt
from statistics import quantiles
from typing import Literal  

from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

def _mean_std(values: list[float]) -> tuple[float, float]:
    n = len(values)
    mean = sum(values) / n
    var = sum((v - mean) ** 2 for v in values) / n
    std = sqrt(var)
    return mean, std


def _rolling_mean_std(values: list[float], window: int, idx: int) -> tuple[float | None, float | None]:
    # baseline excludes current point; uses previous window values
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

app = FastAPI(
    title="COMP3011 Climate & Urban Environment Statistics API",
    version="1.0.0",
    description="Stores historical city observations (temperature + PM2.5) and provides analytics endpoints.",
)

@app.on_event("startup")
def on_startup():
    # models must be imported before this so City is registered
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


@app.get("/")
def root():
    return {"message": "API is running. Visit /docs for Swagger UI."}


# -------------------- City CRUD --------------------
@app.post("/cities", response_model=schemas.CityOut, status_code=status.HTTP_201_CREATED)
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
        raise HTTPException(status_code=409, detail="City already exists (same name + country).")
    db.refresh(city)
    return city


@app.get("/cities", response_model=list[schemas.CityOut])
def list_cities(db: Session = Depends(get_db)):
    return db.query(models.City).order_by(models.City.country.asc(), models.City.name.asc()).all()


@app.get("/cities/{city_id}", response_model=schemas.CityOut)
def get_city(city_id: int, db: Session = Depends(get_db)):
    return get_city_or_404(db, city_id)


@app.put("/cities/{city_id}", response_model=schemas.CityOut)
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
        raise HTTPException(status_code=409, detail="Update would duplicate an existing city (name + country).")
    db.refresh(city)
    return city


@app.delete("/cities/{city_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_city(city_id: int, db: Session = Depends(get_db)):
    city = get_city_or_404(db, city_id)
    db.delete(city)
    db.commit()
    return None


# -------------------- Observations (read/query) --------------------
@app.get("/observations", response_model=list[schemas.ObservationOut])
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

# -------------------- Analytics --------------------
@app.get("/cities/{city_id}/summary", response_model=schemas.CitySummaryOut)
def city_summary(
    city_id: int,
    start: date = Query(...),
    end: date = Query(...),
    db: Session = Depends(get_db),
):
    if end < start:
        raise HTTPException(status_code=422, detail="end must be >= start")

    get_city_or_404(db, city_id)

    base = (
        db.query(models.Observation)
        .filter(models.Observation.city_id == city_id)
        .filter(models.Observation.obs_date >= start)
        .filter(models.Observation.obs_date <= end)
    )

    count_days = base.count()
    if count_days == 0:
        raise HTTPException(status_code=404, detail="No observations for that city and date range.")

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


@app.get("/cities/{city_id}/trend", response_model=schemas.TrendOut)
def city_trend(
    city_id: int,
    metric: str = Query("temp_c", pattern="^(temp_c|pm25)$"),
    start: date = Query(...),
    end: date = Query(...),
    window: int = Query(7, ge=1, le=60),
    db: Session = Depends(get_db),
):
    if end < start:
        raise HTTPException(status_code=422, detail="end must be >= start")

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
        raise HTTPException(status_code=404, detail="No observations for that city and date range.")

    dates = [d for d, _ in rows]
    values = [float(v) if v is not None else None for _, v in rows]

    points = []
    for i in range(len(values)):
        start_i = max(0, i - window + 1)
        window_vals = [v for v in values[start_i : i + 1] if v is not None]
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
@app.get("/cities/{city_id}/anomalies", response_model=schemas.AnomalyOut)
def city_anomalies(
    city_id: int,
    metric: str = Query("temp_c", pattern="^(temp_c|pm25)$"),
    start: date = Query(...),
    end: date = Query(...),
    method: str = Query("zscore", pattern="^(zscore|rolling_zscore|iqr)$"),
    threshold: float = Query(2.0, ge=0.5, le=10.0),   # for zscore methods
    window: int = Query(14, ge=3, le=120),            # for rolling_zscore
    k: float = Query(1.5, ge=0.5, le=10.0),           # for iqr
    db: Session = Depends(get_db),
):
    if end < start:
        raise HTTPException(status_code=422, detail="end must be >= start")

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
        raise HTTPException(status_code=404, detail="No observations for that city and date range.")

    dates = [d for d, _ in rows]
    values = [float(v) for _, v in rows]

    anomalies: list[schemas.AnomalyPoint] = []

    if method == "zscore":
        mean, std = _mean_std(values)
        if std == 0:
            return schemas.AnomalyOut(
                city_id=city_id, metric=metric, start=start, end=end,
                method="zscore", threshold=threshold, mean=float(mean), std=0.0,
                anomalies=[]
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
            city_id=city_id, metric=metric, start=start, end=end,
            method="zscore", threshold=float(threshold),
            mean=float(mean), std=float(std),
            anomalies=anomalies
        )

    if method == "rolling_zscore":
        # score each point relative to previous window baseline
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

        # For transparency, return global mean/std too (optional)
        mean_g, std_g = _mean_std(values)
        return schemas.AnomalyOut(
            city_id=city_id, metric=metric, start=start, end=end,
            method="rolling_zscore", window=window, threshold=float(threshold),
            mean=float(mean_g), std=float(std_g),
            anomalies=anomalies
        )

    # method == "iqr"
    # quartiles
    qs = quantiles(values, n=4, method="inclusive")
    q1, q3 = float(qs[0]), float(qs[2])
    iqr = q3 - q1
    low_cut = q1 - k * iqr
    high_cut = q3 + k * iqr

    for d, v in zip(dates, values):
        if v < low_cut or v > high_cut:
            # score: how far beyond the cutoff (in IQR units)
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
        city_id=city_id, metric=metric, start=start, end=end,
        method="iqr", k=float(k),
        q1=q1, q3=q3, iqr=float(iqr),
        anomalies=anomalies
    )
class ProblemException(Exception):
    def __init__(self, *, status: int, title: str, detail: str, type_: str = "about:blank"):
        self.status = status
        self.title = title
        self.detail = detail
        self.type_ = type_
        
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
@app.get("/cities/{city_id}/risk-score", response_model=schemas.RiskScoreOut)
def city_risk_score(
    city_id: int,
    start: date = Query(...),
    end: date = Query(...),
    db: Session = Depends(get_db),
):
    if end < start:
        raise HTTPException(status_code=422, detail="end must be >= start")

    get_city_or_404(db, city_id)

    # Pull data for both metrics
    rows = (
        db.query(models.Observation.obs_date, models.Observation.temp_c, models.Observation.pm25)
        .filter(models.Observation.city_id == city_id)
        .filter(models.Observation.obs_date >= start)
        .filter(models.Observation.obs_date <= end)
        .order_by(models.Observation.obs_date.asc())
        .all()
    )
    if not rows:
        raise HTTPException(status_code=404, detail="No observations for that city and date range.")

    temps = [float(t) for _, t, _ in rows if t is not None]
    pm25s = [float(p) for _, _, p in rows if p is not None]

    # variance proxies (std)
    temp_std = _mean_std(temps)[1] if len(temps) >= 2 else 0.0
    pm25_std = _mean_std(pm25s)[1] if len(pm25s) >= 2 else 0.0

    # anomaly rate (use your anomalies method quickly in-code: zscore, threshold 2)
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

    # simple trend slope (difference between first and last available)
    def slope(values: list[float]) -> float:
        if len(values) < 2:
            return 0.0
        return values[-1] - values[0]

    temp_slope = slope(temps)
    pm25_slope = slope(pm25s)

    # Combine into 0–100 score (simple, transparent scaling)
    # You can tune weights in the report and justify them.
    score = (
        min(temp_std * 5.0, 35.0) +
        min(pm25_std * 1.0, 35.0) +
        min((temp_anom + pm25_anom) * 50.0, 20.0) +
        min((abs(temp_slope) + abs(pm25_slope)) * 2.0, 10.0)
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
@app.get("/cities/{city_id}/regimes", response_model=schemas.RegimesOut)
def city_regimes(
    city_id: int,
    metric: str = Query("temp_c", pattern="^(temp_c|pm25)$"),
    start: date = Query(...),
    end: date = Query(...),
    window: int = Query(14, ge=3, le=120),
    db: Session = Depends(get_db),
):
    if end < start:
        raise HTTPException(status_code=422, detail="end must be >= start")

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
        raise HTTPException(status_code=404, detail="No observations for that city and date range.")

    dates = [d for d, _ in rows]
    values = [float(v) if v is not None else None for _, v in rows]

    # Use rolling std as volatility proxy.
    stds = []
    for i in range(len(values)):
        stds.append(_rolling_std(values, window, i))

    # Determine thresholds from observed rolling std distribution
    std_vals = [s for s in stds if s is not None]
    if len(std_vals) < 3:
        # Not enough data; mark everything Stable
        points = [
            schemas.RegimePoint(date=dates[i], value=values[i], rolling_std=stds[i], regime="Stable")
            for i in range(len(values))
        ]
        return schemas.RegimesOut(city_id=city_id, metric=metric, start=start, end=end, window=window, points=points)

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
        city_id=city_id, metric=metric, start=start, end=end, window=window, points=points
    )