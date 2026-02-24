# tests/test_city_crud.py

def test_city_crud(client):
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
    city_id = city["id"]

    # List
    r = client.get("/cities")
    assert r.status_code == 200
    cities = r.json()
    assert any(c["id"] == city_id for c in cities)

    # Delete
    r = client.delete(f"/cities/{city_id}")
    assert r.status_code == 204, r.text

    # Verify gone
    r = client.get(f"/cities/{city_id}")
    assert r.status_code == 404
