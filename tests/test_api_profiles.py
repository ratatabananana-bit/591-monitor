def test_create_profile(client):
    response = client.post("/api/search-profiles", json={
        "name": "Taipei Cheap",
        "city": "taipei",
        "price_max": 20000,
        "scan_interval_minutes": 30,
    })
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Taipei Cheap"
    assert data["enabled"] is True


def test_list_profiles(client):
    client.post("/api/search-profiles", json={"name": "Test"})
    response = client.get("/api/search-profiles")
    assert response.status_code == 200
    assert isinstance(response.json(), list)
    assert len(response.json()) >= 1


def test_update_profile(client):
    r = client.post("/api/search-profiles", json={"name": "Old Name"})
    pid = r.json()["id"]
    response = client.put(f"/api/search-profiles/{pid}", json={"name": "New Name", "enabled": False})
    assert response.status_code == 200
    assert response.json()["name"] == "New Name"


def test_delete_profile(client):
    r = client.post("/api/search-profiles", json={"name": "To Delete"})
    pid = r.json()["id"]
    client.delete(f"/api/search-profiles/{pid}")
    get_r = client.get(f"/api/search-profiles/{pid}")
    assert get_r.status_code == 404
