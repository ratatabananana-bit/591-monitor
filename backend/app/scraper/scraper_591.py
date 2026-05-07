import logging
import re
import time
from datetime import datetime, timedelta, timezone
from playwright.sync_api import Page, TimeoutError as PlaywrightTimeout
from .browser import get_browser_manager

logger = logging.getLogger(__name__)

BASE_URL = "https://rent.591.com.tw"

# 591 listing URLs: https://rent.591.com.tw/{id}
_LISTING_ID_RE = re.compile(r"rent\.591\.com\.tw/(\d{5,})$")

CITY_CODES = {
    "taipei": 1,
    "new_taipei": 3,
    "taoyuan": 6,
    "taichung": 8,
    "tainan": 20,
    "kaohsiung": 22,
}

ROOM_TYPE_CODES = {
    "整層住家": 1,
    "獨立套房": 2,
    "分租套房": 3,
    "雅房": 4,
}


def _build_search_url(profile: dict) -> str:
    city_code = CITY_CODES.get(profile.get("city", "taipei"), 1)
    params = [f"region={city_code}", "kind=0"]

    price_min = profile.get("price_min")
    price_max = profile.get("price_max")
    if price_min or price_max:
        params.append(f"price={price_min or 0}_{price_max or 0}")

    room_types = profile.get("room_types", [])
    if room_types:
        codes = [str(ROOM_TYPE_CODES[rt]) for rt in room_types if rt in ROOM_TYPE_CODES]
        if codes:
            params.append(f"kind={','.join(codes)}")

    districts = profile.get("districts", [])
    if districts:
        params.append(f"section={','.join(str(d) for d in districts)}")

    return f"{BASE_URL}/?{'&'.join(params)}"


def _parse_relative_date(text: str) -> datetime | None:
    """Convert '7天前更新', '昨日更新', '今日更新' to UTC datetime."""
    now = datetime.now(timezone.utc)
    m = re.search(r"(\d+)天前", text)
    if m:
        return now - timedelta(days=int(m.group(1)))
    if "昨日" in text:
        return now - timedelta(days=1)
    if "今日" in text or "剛剛" in text or "小時前" in text or "分鐘前" in text:
        return now
    return None


def _parse_listing_card(card) -> dict | None:
    """Extract listing data from a .list-wrapper .item card."""
    try:
        # URL + listing ID
        listing_id = None
        for link in card.query_selector_all("a[href]"):
            href = link.get_attribute("href") or ""
            m = _LISTING_ID_RE.search(href)
            if m:
                listing_id = m.group(1)
                break
        if not listing_id:
            return None

        result: dict = {
            "listing_id": listing_id,
            "url": f"{BASE_URL}/{listing_id}",
        }

        # Thumbnail — lazy-loaded with data-src
        img = card.query_selector("img[data-src]")
        if img:
            result["thumbnail_url"] = img.get_attribute("data-src")

        # Title — .link.v-middle is the clean title without badges
        title_el = card.query_selector(".link.v-middle") or card.query_selector(".item-info-title")
        if title_el:
            result["title"] = title_el.inner_text().strip()

        # Price — .item-info-price
        price_el = card.query_selector(".item-info-price")
        if price_el:
            digits = re.sub(r"[^\d]", "", price_el.inner_text())
            if digits:
                result["price"] = int(digits)

        # Parse .item-info-txt elements for size, floor, room_type, district
        txt_els = card.query_selector_all(".item-info-txt")
        for el in txt_els:
            text = el.inner_text().strip()
            # Size
            if "size_ping" not in result:
                m = re.search(r"([\d.]+)坪", text)
                if m:
                    result["size_ping"] = float(m.group(1))
            # Floor
            if "floor" not in result:
                m = re.search(r"(\d+F/\d+F|\d+F)", text)
                if m:
                    result["floor"] = m.group(1)
            # Room type
            if "room_type" not in result:
                for rt in ["整層住家", "獨立套房", "分租套房", "雅房"]:
                    if rt in text:
                        result["room_type"] = rt
                        break
            # District/address — contains 區 or 市
            if "district" not in result and ("區" in text or "市" in text):
                # Try inner .inline-flex-row for cleaner text
                addr_el = el.query_selector(".inline-flex-row")
                district_text = (addr_el.inner_text().strip() if addr_el else text)
                # Strip non-address prefix tags (先搶先贏, etc.)
                district_text = re.sub(r"^[^一-鿿]*", "", district_text).strip()
                if district_text:
                    result["district"] = district_text

        # Update date from "N天前更新" in .line elements
        for line in card.query_selector_all(".line"):
            text = line.inner_text().strip()
            if "更新" in text:
                dt = _parse_relative_date(text)
                if dt:
                    result["listing_updated_at"] = dt.isoformat()
                break

        return result

    except Exception as exc:
        logger.debug("Card parse error: %s", exc)
        return None


def _extract_all_listings(page: Page) -> list[dict]:
    """Extract all listing cards from the current page."""
    listings = []

    # Wait for search result cards
    try:
        page.wait_for_selector(".list-wrapper .item", timeout=10000)
    except PlaywrightTimeout:
        pass

    cards = page.query_selector_all(".list-wrapper .item")
    if cards:
        logger.info("Found %d listing cards", len(cards))
        for card in cards:
            listing = _parse_listing_card(card)
            if listing:
                listings.append(listing)
        return listings

    # Fallback: extract links only (no metadata)
    logger.warning("No .list-wrapper .item cards found — falling back to link extraction")
    links = page.query_selector_all("a[href]")
    seen: set[str] = set()
    for link in links:
        href = link.get_attribute("href") or ""
        m = _LISTING_ID_RE.search(href)
        if m and m.group(1) not in seen:
            lid = m.group(1)
            seen.add(lid)
            listings.append({"listing_id": lid, "url": f"{BASE_URL}/{lid}"})
    logger.info("Fallback link extraction: %d listings", len(listings))
    return listings


def _filter_by_keywords(listings: list[dict], profile: dict) -> list[dict]:
    required = [kw.lower() for kw in profile.get("required_keywords", [])]
    rejected = [kw.lower() for kw in profile.get("rejected_keywords", [])]
    if not required and not rejected:
        return listings

    result = []
    for listing in listings:
        text = (
            (listing.get("title") or "") + " " + (listing.get("district") or "")
        ).lower()
        if rejected and any(kw in text for kw in rejected):
            continue
        if required and not any(kw in text for kw in required):
            continue
        result.append(listing)
    return result


def scrape_profile(profile: dict) -> list[dict]:
    """
    Scrape all listings for a search profile via DOM scraping.
    Returns list of raw listing dicts with metadata.
    """
    mgr = get_browser_manager()
    url = _build_search_url(profile)
    all_listings: list[dict] = []
    seen_ids: set[str] = set()
    page_num = 1

    with mgr.new_page() as page:
        logger.info("Scraping URL: %s", url)
        try:
            page.goto(url, wait_until="networkidle", timeout=30000)
            time.sleep(2)

            # Scroll to trigger lazy-load
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(2)

            while page_num <= 20:
                listings = _extract_all_listings(page)
                new_listings = [l for l in listings if l["listing_id"] not in seen_ids]

                if not new_listings:
                    logger.info("No new listings on page %d, stopping", page_num)
                    break

                new_listings = _filter_by_keywords(new_listings, profile)
                for l in new_listings:
                    seen_ids.add(l["listing_id"])
                all_listings.extend(new_listings)
                logger.info("Page %d: %d listings (total: %d)", page_num, len(new_listings), len(all_listings))

                # Next page
                next_btn = page.query_selector(
                    ".pageNext:not(.disabled), [class*='next']:not([class*='disabled'])"
                )
                if not next_btn:
                    logger.info("No next page button, done")
                    break

                next_btn.click()
                time.sleep(2)
                page_num += 1

        except PlaywrightTimeout as exc:
            logger.error("Timeout scraping %s: %s", url, exc)
        except Exception as exc:
            logger.error("Error scraping %s: %s", url, exc, exc_info=True)

    logger.info("Scraped %d total listings for profile", len(all_listings))
    return all_listings


def check_listing_exists(listing_id: str) -> bool:
    """Check if a listing's detail page still exists (not archived/removed)."""
    mgr = get_browser_manager()
    url = f"{BASE_URL}/{listing_id}"
    with mgr.new_page() as page:
        try:
            response = page.goto(url, wait_until="domcontentloaded", timeout=15000)
            if response and response.status in (404, 410):
                return False
            content = page.content()
            gone_phrases = ["已下架", "不存在", "找不到此物件", "該物件已被刪除", "404"]
            if any(phrase in content for phrase in gone_phrases):
                return False
            return True
        except Exception as exc:
            logger.warning("Could not verify listing %s: %s — assuming exists", listing_id, exc)
            return True
