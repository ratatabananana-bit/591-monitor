import time
import logging
import httpx
from ..config import settings

logger = logging.getLogger(__name__)

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
GOOGLE_GEOCODING_URL = "https://maps.googleapis.com/maps/api/geocode/json"

_last_nominatim_call = 0.0


def _geocode_nominatim(address: str) -> tuple[float, float] | None:
    global _last_nominatim_call
    # Nominatim rate limit: 1 req/sec
    elapsed = time.time() - _last_nominatim_call
    if elapsed < 1.1:
        time.sleep(1.1 - elapsed)
    try:
        r = httpx.get(
            NOMINATIM_URL,
            params={"q": address, "format": "json", "limit": 1, "countrycodes": "tw"},
            headers={"User-Agent": "591-housing-monitor/1.0"},
            timeout=10.0,
        )
        _last_nominatim_call = time.time()
        r.raise_for_status()
        data = r.json()
        if data:
            return float(data[0]["lat"]), float(data[0]["lon"])
        logger.warning("Nominatim no results for '%s'", address)
        return None
    except Exception as exc:
        logger.error("Nominatim geocoding failed for '%s': %s", address, exc)
        return None


def _geocode_google(address: str) -> tuple[float, float] | None:
    try:
        r = httpx.get(
            GOOGLE_GEOCODING_URL,
            params={"address": address, "key": settings.google_maps_api_key, "language": "zh-TW"},
            timeout=10.0,
        )
        r.raise_for_status()
        data = r.json()
        if data["status"] == "OK" and data["results"]:
            loc = data["results"][0]["geometry"]["location"]
            return loc["lat"], loc["lng"]
        logger.warning("Google geocoding no results for '%s' — status: %s", address, data.get("status"))
        return None
    except Exception as exc:
        logger.error("Google geocoding failed for '%s': %s", address, exc)
        return None


def geocode_address(address: str) -> tuple[float, float] | None:
    """Try Google first (if key set), fall back to Nominatim."""
    if settings.google_maps_api_key:
        result = _geocode_google(address)
        if result:
            return result
    return _geocode_nominatim(address)
