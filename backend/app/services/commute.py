import re
import time
import logging
from urllib.parse import quote
from datetime import datetime, timezone, timedelta
from ..scraper.browser import get_browser_manager

logger = logging.getLogger(__name__)


def _today_11am_taipei() -> int:
    """Unix timestamp for today or tomorrow 11am Taipei time (UTC+8)."""
    taipei = timezone(timedelta(hours=8))
    now = datetime.now(taipei)
    t = now.replace(hour=11, minute=0, second=0, microsecond=0)
    if t <= now:
        t += timedelta(days=1)
    return int(t.timestamp())


def _parse_transit_minutes(text: str) -> int | None:
    """Parse transit route duration from Google Maps page text.
    Transit pages show 'N 分 下午HH:MM—下午HH:MM' for each route option.
    For nearby destinations Google shows walking: 'N 分 N 公尺/公里'.
    """
    text = text.replace('\xa0', ' ')
    # Hours + minutes: N 小時 N 分
    m = re.search(r'(\d+)\s*小時\s*(\d+)\s*分', text)
    if m:
        return int(m.group(1)) * 60 + int(m.group(2))
    m = re.search(r'(\d+)\s*小時', text)
    if m:
        return int(m.group(1)) * 60
    # "N 分 下午/上午HH:MM" — route duration before departure schedule
    m = re.search(r'(\d+)\s*分\s*(?:上午|下午)\d+:\d+', text)
    if m:
        val = int(m.group(1))
        if 1 <= val <= 300:
            return val
    # Nearby destination: Google shows walking "N 分 N 公尺/公里" (no schedule)
    m = re.search(r'(\d+)\s*分\s*[\d.]+\s*(?:公里|公尺)', text)
    if m:
        val = int(m.group(1))
        if 1 <= val <= 300:
            return val
    return None


def _parse_driving(text: str) -> tuple[int | None, int | None]:
    """Parse driving route duration and distance from Google Maps page text.
    Driving pages show 'N 分 X.X 公里' for each route option.
    Returns (minutes, meters).
    """
    text = text.replace('\xa0', ' ')
    # Hours + minutes + km
    m = re.search(r'(\d+)\s*小時\s*(\d+)\s*分\s*([\d.]+)\s*公里', text)
    if m:
        return int(m.group(1)) * 60 + int(m.group(2)), int(float(m.group(3)) * 1000)
    # Minutes + km
    m = re.search(r'(\d+)\s*分\s*([\d.]+)\s*公里', text)
    if m:
        return int(m.group(1)), int(float(m.group(2)) * 1000)
    # Minutes + meters
    m = re.search(r'(\d+)\s*分\s*(\d+)\s*公尺', text)
    if m:
        return int(m.group(1)), int(m.group(2))
    return None, None


def get_commute(
    origin_addr: str,
    dest_addr: str,
    cancel_ev=None,
) -> dict | None:
    result: dict = {}
    departure = _today_11am_taipei()
    modes = [
        ('transit', 'transit_minutes'),
        ('driving', 'scooter_minutes'),
    ]

    try:
        mgr = get_browser_manager()
        with mgr.new_page() as page:
            for mode, key in modes:
                if cancel_ev and cancel_ev.is_set():
                    break
                url = (
                    f"https://www.google.com/maps/dir/?api=1"
                    f"&origin={quote(origin_addr)}"
                    f"&destination={quote(dest_addr)}"
                    f"&travelmode={mode}"
                    f"&departure_time={departure}"
                    f"&hl=zh-TW"
                )
                try:
                    page.goto(url, wait_until='load', timeout=30000)
                    # Wait for SPA to build the full DOM (Google Maps needs 600+ nodes)
                    try:
                        page.wait_for_function(
                            "() => document.querySelectorAll('*').length > 600",
                            timeout=30000,
                        )
                    except Exception:
                        pass

                    text = page.inner_text('body')
                    logger.info("Maps [%s] %s→%s text[:300]: %s",
                                mode, origin_addr[:40], dest_addr[:40], text[:300])

                    if mode == 'transit':
                        minutes = _parse_transit_minutes(text)
                        if minutes is not None:
                            result['transit_minutes'] = minutes
                        else:
                            logger.warning("Maps [transit] no time found. text: %s", text[:300])
                    else:
                        mins, dist = _parse_driving(text)
                        if mins is not None:
                            result['scooter_minutes'] = mins
                            result['scooter_distance_meters'] = dist if dist else mins * 400
                        else:
                            logger.warning("Maps [driving] no time found. text: %s", text[:300])

                except Exception as exc:
                    logger.warning("Maps scrape [%s] failed: %s", mode, exc)

    except Exception as exc:
        logger.error("get_commute browser error: %s", exc, exc_info=True)

    return result if result else None
