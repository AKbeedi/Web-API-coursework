from __future__ import annotations

from datetime import date
from fastapi import FastAPI, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from sqlalchemy import func

from .database import Base, engine, get_db
from . import models, schemas  # <-- relative import (forces local models)

app = FastAPI(
    title="COMP3011 Climate & Urban Environment Statistics API",
    version="1.0.0",
    description="Stores historical city observations (temperature + PM2.5) and provides analytics endpoints.",
)

@app.on_event("startup")
def on_startup():
    # models must be imported before this so City is registered
    Base.metadata.create_all(bind=engine)




def get_city_or_404(db: Session, city_id: int) -> models.City:
    city = db.get(models.City, city_id)
    if not city:
        raise HTTPException(status_code=404, detail="City not found.")
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
    limit: int = Query(2000, ge=1, le=20000),
    db: Session = Depends(get_db),
):
    get_city_or_404(db, city_id)

    q = db.query(models.Observation).filter(models.Observation.city_id == city_id)
    if start is not None:
        q = q.filter(models.Observation.obs_date >= start)
    if end is not None:
        q = q.filter(models.Observation.obs_date <= end)

    return q.order_by(models.Observation.obs_date.asc()).limit(limit).all()


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
