from datetime import date as DateType
from pydantic import BaseModel, Field


# ---------- City ----------
class CityCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    country: str = Field(min_length=1, max_length=100)
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)


class CityUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    country: str | None = Field(default=None, min_length=1, max_length=100)
    lat: float | None = Field(default=None, ge=-90, le=90)
    lon: float | None = Field(default=None, ge=-180, le=180)


class CityOut(BaseModel):
    id: int
    name: str
    country: str
    lat: float
    lon: float

    model_config = {"from_attributes": True}


# ---------- Observation (read/query) ----------
class ObservationOut(BaseModel):
    id: int
    city_id: int
    # DB column is obs_date, but API returns it as "date"
    date: DateType = Field(alias="obs_date")
    temp_c: float | None
    pm25: float | None

    model_config = {
        "from_attributes": True,
        "populate_by_name": True,  # allows using field names in output cleanly
    }


# ---------- Analytics ----------
class CitySummaryOut(BaseModel):
    city_id: int
    start: DateType
    end: DateType
    count_days: int

    avg_temp_c: float | None
    min_temp_c: float | None
    max_temp_c: float | None

    avg_pm25: float | None
    min_pm25: float | None
    max_pm25: float | None


class TrendPoint(BaseModel):
    date: DateType
    value: float | None
    moving_avg: float | None


class TrendOut(BaseModel):
    city_id: int
    metric: str
    start: DateType
    end: DateType
    window: int
    points: list[TrendPoint]
