# tests/test_anomalies.py
from datetime import date
from app import models


def test_city_anomalies(client, db_session):
    city = models.City(name="Leeds", country="UK", lat=53.8008, lon=-1.5491)
    db_session.add(city)
    db_session.commit()
    db_session.refresh(city)

    # Mostly normal temps + one big outlier
    temps = [5.0, 5.1, 5.2, 5.0, 5.1, 20.0]
    for i, t in enumerate(temps, start=1):
        db_session.add(models.Observation(
            city_id=city.id,
            obs_date=date(2025, 1, i),
            temp_c=t,
            pm25=12.0
        ))
    db_session.commit()

    r = client.get(f"/cities/{city.id}/anomalies", params={
        "metric": "temp_c",
        "start": "2025-01-01",
        "end": "2025-01-06",
        "threshold": 1.5,  # smaller threshold to reliably flag the outlier
    })
    assert r.status_code == 200, r.text
    data = r.json()

    assert "mean" in data and "std" in data
    assert isinstance(data["anomalies"], list)
    # Should flag at least the outlier day
    assert len(data["anomalies"]) >= 1
