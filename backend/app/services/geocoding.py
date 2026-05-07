import logging
import httpx
from ..config import settings

logger = logging.getLogger(__name__)

GEOCODING_URL = "https://maps.googleapis.com/maps/api/geocode/json"


def geocode_address(address: str) -> tuple[float, float] | None:
    """Returns (lat, lng) or None if geocoding fails."""
    if not settings.google_maps_api_key:
        logger.warning("GOOGLE_MAPS_API_KEY not set, skipping geocoding")
        return None
    try:
        response = httpx.get(
            GEOCODING_URL,
            params={"address": address, "key": settings.google_maps_api_key, "language": "zh-TW"},
            timeout=10.0,
        )
        response.raise_for_status()
        data = response.json()
        if data["status"] == "OK" and data["results"]:
            loc = data["results"][0]["geometry"]["location"]
            return loc["lat"], loc["lng"]
        logger.warning("Geocoding no results for '%s' — status: %s", address, data.get("status"))
        return None
    except Exception as exc:
        logger.error("Geocoding failed for '%s': %s", address, exc)
        return None
