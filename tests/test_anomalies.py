# tests/test_anomalies.py
from datetime import date
from app import models


def test_city_anomalies_zscore_success(client, db_session):
    city = models.City(name="Leeds", country="UK", lat=53.8008, lon=-1.5491)
    db_session.add(city)
    db_session.commit()
    db_session.refresh(city)

    temps = [5.0, 5.1, 5.2, 5.0, 5.1, 20.0]

    for i, t in enumerate(temps, start=1):
        db_session.add(models.Observation(
            city_id=city.id,
            obs_date=date(2025, 1, i),
            temp_c=t,
            pm25=12.0
        ))

    db_session.commit()

    r = client.get(
        f"/cities/{city.id}/anomalies",
        params={
            "metric": "temp_c",
            "start": "2025-01-01",
            "end": "2025-01-06",
            "method": "zscore",
            "threshold": 1.5
        }
    )

    assert r.status_code == 200
    data = r.json()

    assert data["metric"] == "temp_c"
    assert data["method"] == "zscore"
    assert isinstance(data["anomalies"], list)
    assert len(data["anomalies"]) >= 1

    anomaly_dates = [a["date"] for a in data["anomalies"]]
    assert "2025-01-06" in anomaly_dates


def test_city_anomalies_invalid_date_range(client, db_session):
    city = models.City(name="York", country="UK", lat=53.9590, lon=-1.0815)
    db_session.add(city)
    db_session.commit()
    db_session.refresh(city)

    r = client.get(
        f"/cities/{city.id}/anomalies",
        params={
            "metric": "temp_c",
            "start": "2025-01-05",
            "end": "2025-01-01"
        }
    )

    assert r.status_code == 422


def test_city_anomalies_no_observations(client, db_session):
    city = models.City(name="Bradford", country="UK", lat=53.7950, lon=-1.7590)
    db_session.add(city)
    db_session.commit()
    db_session.refresh(city)

    r = client.get(
        f"/cities/{city.id}/anomalies",
        params={
            "metric": "temp_c",
            "start": "2025-02-01",
            "end": "2025-02-05"
        }
    )

    assert r.status_code == 404