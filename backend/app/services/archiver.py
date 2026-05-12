MISSING_THRESHOLD = 3
FROZEN_STATUSES = {"REJECTED"}
STICKY_STATUSES = {"SAVED", "CHECKING"}


def determine_new_status(
    current_status: str,
    found_in_search: bool,
    detail_exists: bool,
    missing_count: int,
) -> str:
    # REJECTED: completely frozen, scanner never touches it
    if current_status in FROZEN_STATUSES:
        return current_status

    # Detail page gone = archived (applies to SAVED/CHECKING too)
    if not detail_exists:
        return "ARCHIVED"

    # SAVED/CHECKING: keep status while listing still exists, ignore search misses
    if current_status in STICKY_STATUSES:
        return current_status

    if found_in_search:
        if current_status in ("MISSING_ON_SEARCH", "UNAVAILABLE", "REAPPEARED"):
            return "REAPPEARED"
        return "ACTIVE"

    if missing_count >= MISSING_THRESHOLD:
        return "UNAVAILABLE"
    return "MISSING_ON_SEARCH"
