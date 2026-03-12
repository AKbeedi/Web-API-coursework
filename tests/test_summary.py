# tests/test_summary.py
from datetime import date
from app import models


def test_city_summary_success(client, db_session):
    # Arrange: create city
    city = models.City(name="Leeds", country="UK", lat=53.8008, lon=-1.5491)
    db_session.add(city)
    db_session.commit()
    db_session.refresh(city)

    # Arrange: create observations
    obs = [
        models.Observation(city_id=city.id, obs_date=date(2025, 1, 1), temp_c=5.2, pm25=12.8),
        models.Observation(city_id=city.id, obs_date=date(2025, 1, 2), temp_c=4.9, pm25=14.1),
        models.Observation(city_id=city.id, obs_date=date(2025, 1, 3), temp_c=6.0, pm25=10.5),
    ]
    db_session.add_all(obs)
    db_session.commit()

    # Act
    r = client.get(
        f"/cities/{city.id}/summary",
        params={"start": "2025-01-01", "end": "2025-01-03"},
    )

    # Assert
    assert r.status_code == 200, r.text
    data = r.json()

    assert data["city_id"] == city.id
    assert data["start"] == "2025-01-01"
    assert data["end"] == "2025-01-03"
    assert data["count_days"] == 3

    assert data["avg_temp_c"] == (5.2 + 4.9 + 6.0) / 3
    assert data["min_temp_c"] == 4.9
    assert data["max_temp_c"] == 6.0

    assert data["avg_pm25"] == (12.8 + 14.1 + 10.5) / 3
    assert data["min_pm25"] == 10.5
    assert data["max_pm25"] == 14.1


def test_city_summary_invalid_date_range(client, db_session):
    city = models.City(name="Leeds", country="UK", lat=53.8008, lon=-1.5491)
    db_session.add(city)
    db_session.commit()
    db_session.refresh(city)

    r = client.get(
        f"/cities/{city.id}/summary",
        params={"start": "2025-01-03", "end": "2025-01-01"},
    )

    assert r.status_code == 422, r.text
    data = r.json()

    if "title" in data:
        assert data["title"] == "Invalid date range"
        assert data["status"] == 422
    else:
        assert data["detail"] == "end must be >= start"


def test_city_summary_no_observations(client, db_session):
    city = models.City(name="Leeds", country="UK", lat=53.8008, lon=-1.5491)
    db_session.add(city)
    db_session.commit()
    db_session.refresh(city)

    obs = [
        models.Observation(city_id=city.id, obs_date=date(2025, 1, 1), temp_c=5.2, pm25=12.8),
    ]
    db_session.add_all(obs)
    db_session.commit()

    r = client.get(
        f"/cities/{city.id}/summary",
        params={"start": "2025-02-01", "end": "2025-02-03"},
    )

    assert r.status_code == 404, r.text