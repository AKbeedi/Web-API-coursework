from datetime import date
from app import models


def seed_city_with_data(db_session, name="TestCity", country="TestLand"):
    city = models.City(
        name=name,
        country=country,
        lat=10.0,
        lon=20.0
    )
    db_session.add(city)
    db_session.commit()
    db_session.refresh(city)

    observations = [
        models.Observation(city_id=city.id, obs_date=date(2025, 1, 1), temp_c=10.0, pm25=20.0),
        models.Observation(city_id=city.id, obs_date=date(2025, 1, 2), temp_c=12.0, pm25=25.0),
        models.Observation(city_id=city.id, obs_date=date(2025, 1, 3), temp_c=14.0, pm25=30.0),
        models.Observation(city_id=city.id, obs_date=date(2025, 1, 4), temp_c=16.0, pm25=35.0),
        models.Observation(city_id=city.id, obs_date=date(2025, 1, 5), temp_c=18.0, pm25=40.0),
    ]

    db_session.add_all(observations)
    db_session.commit()

    return city


def test_trend_endpoint(client, db_session):
    city = seed_city_with_data(db_session, name="TrendCity")

    r = client.get(
        f"/cities/{city.id}/trend",
        params={
            "metric": "temp_c",
            "start": "2025-01-01",
            "end": "2025-01-05",
            "window": 3
        },
    )

    assert r.status_code == 200
    data = r.json()
    assert data["city_id"] == city.id
    assert len(data["points"]) == 5


def test_risk_score_endpoint(client, db_session):
    city = seed_city_with_data(db_session, name="RiskCity")

    r = client.get(
        f"/cities/{city.id}/risk-score",
        params={
            "start": "2025-01-01",
            "end": "2025-01-05"
        },
    )

    assert r.status_code == 200
    data = r.json()

    assert "risk_score" in data
    assert 0 <= data["risk_score"] <= 100
    assert data["label"] in ["Low", "Moderate", "High"]


def test_regimes_endpoint(client, db_session):
    city = seed_city_with_data(db_session, name="RegimeCity")

    r = client.get(
        f"/cities/{city.id}/regimes",
        params={
            "metric": "pm25",
            "start": "2025-01-01",
            "end": "2025-01-05",
            "window": 3
        },
    )

    assert r.status_code == 200
    data = r.json()

    assert data["city_id"] == city.id
    assert len(data["points"]) == 5


def test_insights_endpoint(client, db_session):
    city = seed_city_with_data(db_session, name="InsightCity")

    r = client.get(
        f"/cities/{city.id}/insights",
        params={
            "start": "2025-01-01",
            "end": "2025-01-05"
        },
    )

    assert r.status_code == 200
    data = r.json()

    assert data["city_id"] == city.id
    assert "insight" in data


def test_compare_endpoint(client, db_session):
    city1 = seed_city_with_data(db_session, name="CompareCityA")
    city2 = seed_city_with_data(db_session, name="CompareCityB")

    r = client.get(
        "/cities/compare",
        params={
            "city1": city1.id,
            "city2": city2.id,
            "start": "2025-01-01",
            "end": "2025-01-05"
        },
    )

    assert r.status_code == 200
    data = r.json()

    assert "city_1" in data
    assert "city_2" in data


def test_rankings_endpoint(client, db_session):
    seed_city_with_data(db_session, name="RankCityA")
    seed_city_with_data(db_session, name="RankCityB")

    r = client.get(
        "/cities/rankings",
        params={
            "metric": "pm25",
            "start": "2025-01-01",
            "end": "2025-01-05",
            "limit": 5
        },
    )

    assert r.status_code == 200
    data = r.json()

    assert data["metric"] == "pm25"
    assert isinstance(data["rankings"], list)