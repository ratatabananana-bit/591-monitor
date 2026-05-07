from app.services.scoring import score_listing, ScoreInput, CommuteData


def make_input(**kwargs):
    defaults = {
        "price": 15000,
        "price_min": 8000,
        "price_max": 25000,
        "days_since_first_seen": 1,
        "commute_data": [],
        "room_type": "整層住家",
        "required_keywords": [],
        "rejected_keywords": [],
        "title": "Nice apartment",
    }
    defaults.update(kwargs)
    return ScoreInput(**defaults)


def test_score_in_range():
    result = score_listing(make_input())
    assert 0 <= result <= 100


def test_cheap_listing_high_price_score():
    cheap = score_listing(make_input(price=8000))
    expensive = score_listing(make_input(price=24000))
    assert cheap > expensive


def test_fresh_listing_high_freshness():
    fresh = score_listing(make_input(days_since_first_seen=0))
    old = score_listing(make_input(days_since_first_seen=30))
    assert fresh > old


def test_short_commute_high_score():
    short = score_listing(make_input(commute_data=[CommuteData(anchor_weight=1.0, transit_minutes=10)]))
    long_ = score_listing(make_input(commute_data=[CommuteData(anchor_weight=1.0, transit_minutes=60)]))
    assert short > long_


def test_no_commute_data_midpoint():
    result = score_listing(make_input(commute_data=[]))
    assert 0 <= result <= 100


def test_rejected_keyword_zero():
    result = score_listing(make_input(title="has電梯 apartment", rejected_keywords=["電梯"]))
    assert result == 0.0


def test_required_keyword_boost():
    with_kw = score_listing(make_input(title="近捷運 apartment", required_keywords=["近捷運"]))
    without_kw = score_listing(make_input(title="apartment", required_keywords=["近捷運"]))
    assert with_kw > without_kw
