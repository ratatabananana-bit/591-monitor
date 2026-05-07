import logging
import httpx
from ..config import settings

logger = logging.getLogger(__name__)

DIRECTIONS_URL = "https://maps.googleapis.com/maps/api/directions/json"


def get_commute(
    origin_lat: float,
    origin_lng: float,
    dest_lat: float,
    dest_lng: float,
) -> dict | None:
    """
    Returns dict with walk_minutes, transit_minutes, distance_meters.
    Returns None on complete failure.
    """
    if not settings.google_maps_api_key:
        logger.warning("GOOGLE_MAPS_API_KEY not set, skipping commute calculation")
        return None

    origin = f"{origin_lat},{origin_lng}"
    destination = f"{dest_lat},{dest_lng}"
    key = settings.google_maps_api_key
    result: dict = {}

    try:
        r = httpx.get(
            DIRECTIONS_URL,
            params={"origin": origin, "destination": destination, "mode": "transit",
                    "key": key, "language": "zh-TW"},
            timeout=15.0,
        )
        r.raise_for_status()
        data = r.json()
        if data["status"] == "OK" and data["routes"]:
            leg = data["routes"][0]["legs"][0]
            result["transit_minutes"] = leg.get("duration", {}).get("value", 0) // 60
            result["distance_meters"] = leg.get("distance", {}).get("value", 0)
    except Exception as exc:
        logger.error("Transit commute failed: %s", exc)

    try:
        r = httpx.get(
            DIRECTIONS_URL,
            params={"origin": origin, "destination": destination, "mode": "walking",
                    "key": key, "language": "zh-TW"},
            timeout=15.0,
        )
        r.raise_for_status()
        data = r.json()
        if data["status"] == "OK" and data["routes"]:
            leg = data["routes"][0]["legs"][0]
            result["walk_minutes"] = leg.get("duration", {}).get("value", 0) // 60
            if "distance_meters" not in result:
                result["distance_meters"] = leg.get("distance", {}).get("value", 0)
    except Exception as exc:
        logger.error("Walking commute failed: %s", exc)

    return result if result else None
