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
    days_since_first_seen: float
    commute_data: list[CommuteData]
    room_type: str | None
    required_keywords: list[str]
    rejected_keywords: list[str]
    title: str | None


def score_listing(inp: ScoreInput) -> float:
    title_lower = (inp.title or "").lower()

    for kw in inp.rejected_keywords:
        if kw.lower() in title_lower:
            return 0.0

    price_score = _price_score(inp.price, inp.price_min, inp.price_max)
    freshness_score = _freshness_score(inp.days_since_first_seen)
    commute_score = _commute_score(inp.commute_data)
    feature_score = _feature_score(inp.title, inp.required_keywords)

    total = (
        price_score * 0.30
        + freshness_score * 0.20
        + commute_score * 0.35
        + feature_score * 0.15
    )
    return round(min(max(total, 0.0), 100.0), 1)


def _price_score(price: int | None, price_min: int | None, price_max: int | None) -> float:
    if price is None:
        return 50.0
    lo = price_min or 0
    hi = price_max or price * 2
    if hi <= lo:
        return 50.0
    ratio = (price - lo) / (hi - lo)
    return (1.0 - ratio) * 100.0


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
    return max(0.0, (1.0 - minutes / 60.0) * 100.0)


def _feature_score(title: str | None, required_keywords: list[str]) -> float:
    if not required_keywords or not title:
        return 50.0
    title_lower = title.lower()
    matches = sum(1 for kw in required_keywords if kw.lower() in title_lower)
    return (matches / len(required_keywords)) * 100.0
