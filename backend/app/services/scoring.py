from dataclasses import dataclass, field


@dataclass
class CommuteData:
    anchor_weight: float
    transit_minutes: int | None


@dataclass
class ScoreInput:
    price: int | None
    price_min: int | None
    price_max: int | None
    size_ping: float | None
    listing_age_days: float  # days since posted_at, falls back to first_seen_at
    commute_data: list[CommuteData]
    room_type: str | None
    required_keywords: list[str]
    rejected_keywords: list[str]
    title: str | None


def score_listing(inp: ScoreInput) -> tuple[float, dict]:
    """Returns (total_score, breakdown_dict)."""
    title_lower = (inp.title or "").lower()

    for kw in inp.rejected_keywords:
        if kw.lower() in title_lower:
            return 0.0, {"price": 0.0, "freshness": 0.0, "commute": 0.0, "size": 0.0}

    price_score = _price_score(inp.price, inp.price_min, inp.price_max)
    freshness_score = _freshness_score(inp.listing_age_days)
    commute_score = _commute_score(inp.commute_data)
    size_score = _size_score(inp.size_ping)

    total = (
        price_score * 0.35
        + freshness_score * 0.10
        + commute_score * 0.35
        + size_score * 0.20
    )
    breakdown = {
        "price": round(price_score, 1),
        "freshness": round(freshness_score, 1),
        "commute": round(commute_score, 1),
        "size": round(size_score, 1),
    }
    return round(min(max(total, 0.0), 100.0), 1), breakdown


def _price_score(
    price: int | None,
    price_min: int | None,
    price_max: int | None,
) -> float:
    """Score relative to profile's budget range. Cheapest end = 100, ceiling = 0."""
    if price is None:
        return 50.0
    lo = price_min or 0
    hi = price_max
    if not hi or hi <= lo:
        return 50.0
    ratio = (price - lo) / (hi - lo)
    return max(0.0, min(100.0, (1.0 - ratio) * 100.0))


def _freshness_score(days: float) -> float:
    if days <= 0:
        return 100.0
    if days >= 30:
        return 0.0
    return (1.0 - days / 30.0) * 100.0


def _commute_score(commute_data: list[CommuteData]) -> float:
    if not commute_data:
        return 50.0
    total_weight = sum(c.anchor_weight for c in commute_data if c.transit_minutes is not None)
    if total_weight == 0:
        return 50.0
    weighted_sum = sum(
        c.anchor_weight * _commute_minutes_to_score(c.transit_minutes)
        for c in commute_data
        if c.transit_minutes is not None
    )
    return weighted_sum / total_weight


def _commute_minutes_to_score(minutes: int) -> float:
    # ≤15 min → 100, 15–45 min → 100→60 (sweet spot), 45–90 min → 60→0, >90 → 0
    if minutes <= 15:
        return 100.0
    if minutes <= 45:
        return 100.0 - (minutes - 15) / 30.0 * 40.0
    if minutes <= 90:
        return 60.0 - (minutes - 45) / 45.0 * 60.0
    return 0.0


def _size_score(size_ping: float | None) -> float:
    """Fixed curve anchored to Taiwan rental market reality.
    <6 ping = unlivable, 8-10 = livable, 14+ = great, 18+ = excellent."""
    if size_ping is None:
        return 50.0
    # Piecewise linear: (ping, score) anchors
    anchors = [(0, 0), (6, 10), (8, 40), (10, 60), (14, 85), (18, 100)]
    if size_ping >= anchors[-1][0]:
        return 100.0
    for i in range(len(anchors) - 1):
        x0, y0 = anchors[i]
        x1, y1 = anchors[i + 1]
        if x0 <= size_ping <= x1:
            t = (size_ping - x0) / (x1 - x0)
            return y0 + t * (y1 - y0)
    return 0.0
