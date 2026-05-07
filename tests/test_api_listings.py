from datetime import datetime, timezone


def make_listing(db_session, listing_id="591-001", status="NEW", price=15000, score=75.0):
    from app.models import Listing
    listing = Listing(
        listing_id=listing_id,
        url=f"https://rent.591.com.tw/home/{listing_id}",
        title="Test Listing",
        price=price,
        district="大安區",
        status=status,
        score=score,
        first_seen_at=datetime.now(timezone.utc),
        last_seen_at=datetime.now(timezone.utc),
    )
    db_session.add(listing)
    db_session.commit()
    return listing


def test_list_listings_empty(client):
    response = client.get("/api/listings")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert data["items"] == []


def test_list_listings_with_data(client, db_session):
    make_listing(db_session, "591-002")
    response = client.get("/api/listings")
    assert response.status_code == 200
    assert len(response.json()["items"]) >= 1


def test_filter_by_status(client, db_session):
    make_listing(db_session, "591-003", status="SAVED")
    make_listing(db_session, "591-004", status="NEW")
    response = client.get("/api/listings?status=SAVED")
    assert response.status_code == 200
    items = response.json()["items"]
    assert all(i["status"] == "SAVED" for i in items)


def test_listing_action(client, db_session):
    listing = make_listing(db_session, "591-005")
    response = client.patch(f"/api/listings/{listing.id}/action", json={"action": "save"})
    assert response.status_code == 200
    assert response.json()["status"] == "SAVED"


def test_listing_action_invalid(client, db_session):
    listing = make_listing(db_session, "591-006")
    response = client.patch(f"/api/listings/{listing.id}/action", json={"action": "invalid"})
    assert response.status_code == 422
