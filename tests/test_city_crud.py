# tests/test_city_crud.py

def test_city_crud_flow(client):
    # Create
    r = client.post("/cities", json={
        "name": "Leeds",
        "country": "UK",
        "lat": 53.8008,
        "lon": -1.5491
    })
    assert r.status_code == 201, r.text
    city = r.json()
    assert city["name"] == "Leeds"
    assert city["country"] == "UK"
    assert city["lat"] == 53.8008
    assert city["lon"] == -1.5491
    city_id = city["id"]

    # Get by id
    r = client.get(f"/cities/{city_id}")
    assert r.status_code == 200, r.text
    fetched = r.json()
    assert fetched["id"] == city_id
    assert fetched["name"] == "Leeds"

    # List
    r = client.get("/cities")
    assert r.status_code == 200, r.text
    cities = r.json()
    assert any(c["id"] == city_id for c in cities)

    # Update
    r = client.put(f"/cities/{city_id}", json={
        "name": "Leeds Updated",
        "country": "UK",
        "lat": 53.81,
        "lon": -1.55
    })
    assert r.status_code == 200, r.text
    updated = r.json()
    assert updated["id"] == city_id
    assert updated["name"] == "Leeds Updated"
    assert updated["lat"] == 53.81
    assert updated["lon"] == -1.55

    # Delete
    r = client.delete(f"/cities/{city_id}")
    assert r.status_code == 204, r.text
    assert r.text == ""

    # Verify gone (Problem Details format)
    r = client.get(f"/cities/{city_id}")
    assert r.status_code == 404, r.text
    data = r.json()
    assert data["title"] == "City not found"
    assert data["status"] == 404
    assert "does not exist" in data["detail"]
    assert "type" in data
    assert "instance" in data


def test_create_duplicate_city_returns_conflict(client):
    payload = {
        "name": "Leeds",
        "country": "UK",
        "lat": 53.8008,
        "lon": -1.5491
    }

    r1 = client.post("/cities", json=payload)
    assert r1.status_code == 201, r1.text

    r2 = client.post("/cities", json=payload)
    assert r2.status_code == 409, r2.text

    data = r2.json()
    # If you changed create_city to ProblemException, this will match:
    if "title" in data:
        assert data["title"] == "Duplicate city"
        assert data["status"] == 409
    else:
        # fallback in case you're still using HTTPException there
        assert data["detail"] == "City already exists (same name + country)."


def test_update_city_to_duplicate_returns_conflict(client):
    r1 = client.post("/cities", json={
        "name": "Leeds",
        "country": "UK",
        "lat": 53.8008,
        "lon": -1.5491
    })
    assert r1.status_code == 201, r1.text
    city1 = r1.json()

    r2 = client.post("/cities", json={
        "name": "York",
        "country": "UK",
        "lat": 53.9590,
        "lon": -1.0815
    })
    assert r2.status_code == 201, r2.text
    city2 = r2.json()

    # Try to update York into duplicate of Leeds
    r = client.put(f"/cities/{city2['id']}", json={
        "name": "Leeds",
        "country": "UK",
        "lat": 53.9590,
        "lon": -1.0815
    })
    assert r.status_code == 409, r.text

    data = r.json()
    if "title" in data:
        assert data["title"] == "Duplicate city"
        assert data["status"] == 409
    else:
        assert "duplicate" in data["detail"].lower()