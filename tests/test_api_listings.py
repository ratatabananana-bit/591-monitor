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


def test_filter_by_transit_max(client, db_session):
    from app.models import CommuteAnchor, CommuteResult
    import uuid
    from datetime import datetime, timezone

    # Create listing with commute data
    listing = make_listing(db_session, "591-007", status="ACTIVE")
    anchor = CommuteAnchor(name="Office", address="somewhere", weight=1.0, enabled=True)
    db_session.add(anchor)
    db_session.flush()
    cr = CommuteResult(
        listing_id=listing.id,
        anchor_id=anchor.id,
        transit_minutes=20,
        walk_minutes=10,
        distance_meters=5000,
    )
    db_session.add(cr)
    db_session.commit()

    # Should find listing with transit <= 30
    response = client.get("/api/listings?transit_max=30")
    assert response.status_code == 200
    ids = [i["id"] for i in response.json()["items"]]
    assert str(listing.id) in ids

    # Should NOT find listing with transit > 10
    response = client.get("/api/listings?transit_max=10")
    assert response.status_code == 200
    ids = [i["id"] for i in response.json()["items"]]
    assert str(listing.id) not in ids
