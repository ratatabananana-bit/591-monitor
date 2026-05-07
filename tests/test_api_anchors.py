def test_create_anchor(client):
    response = client.post("/api/commute-anchors", json={
        "name": "Office",
        "address": "台北市信義區信義路五段7號",
        "weight": 1.0,
    })
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Office"
    assert data["weight"] == 1.0


def test_list_anchors(client):
    response = client.get("/api/commute-anchors")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_update_anchor(client):
    r = client.post("/api/commute-anchors", json={"name": "Gym", "address": "somewhere", "weight": 0.5})
    aid = r.json()["id"]
    response = client.put(f"/api/commute-anchors/{aid}", json={"name": "Gym Updated", "address": "somewhere", "weight": 0.7})
    assert response.status_code == 200
    assert response.json()["weight"] == 0.7


def test_delete_anchor(client):
    r = client.post("/api/commute-anchors", json={"name": "To Delete", "address": "x", "weight": 1.0})
    aid = r.json()["id"]
    response = client.delete(f"/api/commute-anchors/{aid}")
    assert response.status_code == 200
