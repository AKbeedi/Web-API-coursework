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
    

    
class ProblemDetails(BaseModel):
    type: str
    title: str
    status: int
    detail: str
    instance: str | None = None

from typing import Literal

AnomalyMethod = Literal["zscore", "rolling_zscore", "iqr"]

class AnomalyPoint(BaseModel):
    date: DateType
    value: float
    score: float  # z-score for zscore methods, deviation score for iqr (see below)
    direction: Literal["high", "low"]

class AnomalyOut(BaseModel):
    city_id: int
    metric: str
    start: DateType
    end: DateType

    method: AnomalyMethod
    window: int | None = None   # only for rolling_zscore
    threshold: float | None = None  # used by zscore + rolling_zscore
    k: float | None = None      # used by iqr (1.5 default)

    # method-specific stats (optional)
    mean: float | None = None
    std: float | None = None
    q1: float | None = None
    q3: float | None = None
    iqr: float | None = None

    anomalies: list[AnomalyPoint]


# ---- Risk score ----
class RiskScoreOut(BaseModel):
    city_id: int
    start: DateType
    end: DateType
    risk_score: float  # 0-100
    label: Literal["Low", "Moderate", "High"]
    components: dict[str, float]  # transparency: variance, anomaly_rate, trend_slope etc.


# ---- Regimes ----
class RegimePoint(BaseModel):
    date: DateType
    value: float | None
    rolling_std: float | None
    regime: Literal["Stable", "Volatile", "Extreme"]

class RegimesOut(BaseModel):
    city_id: int
    metric: str
    start: DateType
    end: DateType
    window: int
    points: list[RegimePoint]
    
    
class CityCompareStats(BaseModel):
    city_id: int
    city_name: str
    country: str
    start: DateType
    end: DateType
    count_days: int
    avg_temp_c: float | None
    avg_pm25: float | None
    max_temp_c: float | None
    max_pm25: float | None


class CityCompareOut(BaseModel):
    city_1: CityCompareStats
    city_2: CityCompareStats
    hotter_city: str | None
    more_polluted_city: str | None
    temp_diff_avg: float | None
    pm25_diff_avg: float | None

class CityInsightsOut(BaseModel):
    city_id: int
    city_name: str
    start: DateType
    end: DateType
    insight: str

class CityRankingItem(BaseModel):
    city_id: int
    city_name: str
    country: str
    value: float


class CityRankingOut(BaseModel):
    metric: str
    start: DateType
    end: DateType
    limit: int
    rankings: list[CityRankingItem]