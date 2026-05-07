MISSING_THRESHOLD = 3
USER_STATUSES = {"SAVED", "WATCHED", "REJECTED", "CONTACTED", "VISITED"}


def determine_new_status(
    current_status: str,
    found_in_search: bool,
    detail_exists: bool,
    missing_count: int,
) -> str:
    if not detail_exists:
        return "ARCHIVED"

    if current_status in USER_STATUSES:
        return current_status

    if found_in_search:
        if current_status in ("MISSING_ON_SEARCH", "UNAVAILABLE", "REAPPEARED"):
            return "REAPPEARED"
        return "ACTIVE"

    if missing_count >= MISSING_THRESHOLD:
        return "UNAVAILABLE"
    return "MISSING_ON_SEARCH"
