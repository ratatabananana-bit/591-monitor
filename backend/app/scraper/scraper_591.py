import json
import logging
import time
import re
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


def _parse_listing_card(card) -> dict | None:
    """Extract listing data from a search result card."""
    try:
        # Find the link with listing ID — 591 uses rent.591.com.tw/{id}
        listing_id = None
        for link in card.query_selector_all("a[href]"):
            href = link.get_attribute("href") or ""
            m = _LISTING_ID_RE.search(href)
            if m:
                listing_id = m.group(1)
                break

        if not listing_id:
            return None

        result = {
            "listing_id": listing_id,
            "url": f"{BASE_URL}/{listing_id}",
        }

        # Title — try multiple selectors
        for sel in [".item-title", "[class*='title']", "h3", "[class*='name']"]:
            el = card.query_selector(sel)
            if el:
                text = el.inner_text().strip()
                if text:
                    result["title"] = text
                    break

        # Price
        for sel in [".price-num", "[class*='price']", ".item-price"]:
            el = card.query_selector(sel)
            if el:
                text = re.sub(r"[^\d]", "", el.inner_text())
                if text:
                    try:
                        result["price"] = int(text)
                    except ValueError:
                        pass
                    break

        # District/area
        for sel in [".item-area", "[class*='area']", "[class*='region']", "[class*='location']"]:
            el = card.query_selector(sel)
            if el:
                text = el.inner_text().strip()
                if text:
                    result["district"] = text
                    break

        # Size in ping
        for sel in ["[class*='size']", "[class*='ping']", ".item-size"]:
            el = card.query_selector(sel)
            if el:
                m = re.search(r"([\d.]+)\s*坪", el.inner_text())
                if m:
                    try:
                        result["size_ping"] = float(m.group(1))
                    except ValueError:
                        pass
                    break

        # Room type
        for sel in ["[class*='kind']", "[class*='type']", ".item-kind"]:
            el = card.query_selector(sel)
            if el:
                text = el.inner_text().strip()
                if text and len(text) < 20:
                    result["room_type"] = text
                    break

        return result if "listing_id" in result else None

    except Exception as exc:
        logger.debug("Card parse error: %s", exc)
        return None


def _extract_all_listings(page: Page) -> list[dict]:
    """Extract all listing cards visible on the page."""
    listings = []

    # Wait for listing cards — 591 Nuxt app may take a moment to render
    card_selectors = [
        "section.vue-list-rent-item",
        "[class*='list-item']",
        "[class*='rent-item']",
        "article",
    ]
    for sel in card_selectors:
        try:
            page.wait_for_selector(sel, timeout=8000)
            break
        except PlaywrightTimeout:
            continue

    # Try card selectors
    cards = []
    for sel in card_selectors:
        cards = page.query_selector_all(sel)
        if cards:
            logger.debug("Found %d cards with selector '%s'", len(cards), sel)
            break

    if not cards:
        # Fallback: grab all rent.591.com.tw/{id} links directly
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

    for card in cards:
        listing = _parse_listing_card(card)
        if listing:
            listings.append(listing)

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
        result.append(listing)
    return result


def _parse_api_response(data: dict) -> list[dict]:
    """Parse listings from 591 API JSON response."""
    listings = []
    # API returns data.data (list of house objects) or data.items
    items = None
    if isinstance(data, dict):
        inner = data.get("data") or data.get("result") or {}
        if isinstance(inner, dict):
            items = inner.get("data") or inner.get("items") or inner.get("list") or []
        elif isinstance(inner, list):
            items = inner

    if not items:
        return listings

    for item in items:
        try:
            house_id = str(item.get("house_id") or item.get("id") or "")
            if not house_id or len(house_id) < 5:
                continue
            listing: dict = {
                "listing_id": house_id,
                "url": f"{BASE_URL}/{house_id}",
            }
            # Title
            listing["title"] = item.get("title") or item.get("house_title") or None
            # Price — stored as int NT$/mo
            price_raw = item.get("price") or item.get("rent_price") or ""
            price_digits = re.sub(r"[^\d]", "", str(price_raw))
            if price_digits:
                listing["price"] = int(price_digits)
            # District / section
            listing["district"] = (
                item.get("section_name")
                or item.get("district_name")
                or item.get("address")
                or None
            )
            # Size in ping
            size_raw = str(item.get("area") or item.get("ping") or "")
            m = re.search(r"([\d.]+)", size_raw)
            if m:
                listing["size_ping"] = float(m.group(1))
            # Room type
            listing["room_type"] = item.get("kind_name") or item.get("room_type") or None

            listings.append(listing)
        except Exception as exc:
            logger.debug("API item parse error: %s", exc)

    return listings


def scrape_profile(profile: dict) -> list[dict]:
    """
    Scrape all listings for a search profile.
    Intercepts 591's internal API calls via Playwright for reliable data extraction.
    Falls back to link-only extraction if API not captured.
    """
    mgr = get_browser_manager()
    url = _build_search_url(profile)
    all_listings: list[dict] = []
    seen_ids: set[str] = set()

    # Collect API responses intercepted from the page
    api_responses: list[dict] = []

    def _on_response(response):
        try:
            if "api.591.com.tw" in response.url and response.status == 200:
                ct = response.headers.get("content-type", "")
                if "json" in ct:
                    body = response.json()
                    logger.debug("Captured API response: %s (%d bytes)", response.url, len(str(body)))
                    api_responses.append(body)
        except Exception:
            pass

    with mgr.new_page() as page:
        page.on("response", _on_response)
        logger.info("Scraping URL: %s", url)
        try:
            page.goto(url, wait_until="networkidle", timeout=30000)
            time.sleep(2)

            # Scroll to trigger lazy-load
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(2)

            # Process captured API responses first
            if api_responses:
                logger.info("Processing %d intercepted API responses", len(api_responses))
                for resp_data in api_responses:
                    parsed = _parse_api_response(resp_data)
                    for listing in parsed:
                        if listing["listing_id"] not in seen_ids:
                            seen_ids.add(listing["listing_id"])
                            all_listings.append(listing)
                logger.info("From API: %d listings", len(all_listings))

                # Try paginating if we got results
                page_num = 2
                while page_num <= 20 and all_listings:
                    prev_count = len(all_listings)
                    api_responses.clear()

                    next_btn = page.query_selector(
                        ".pageNext:not(.disabled), [class*='next']:not([class*='disabled']), "
                        "[class*='pagination'] [class*='next']"
                    )
                    if not next_btn:
                        break
                    next_btn.click()
                    time.sleep(3)

                    for resp_data in api_responses:
                        parsed = _parse_api_response(resp_data)
                        for listing in parsed:
                            if listing["listing_id"] not in seen_ids:
                                seen_ids.add(listing["listing_id"])
                                all_listings.append(listing)

                    if len(all_listings) == prev_count:
                        break
                    logger.info("Page %d: total %d listings", page_num, len(all_listings))
                    page_num += 1

            else:
                # Fallback: DOM link extraction (no metadata)
                logger.warning("No API responses captured — falling back to link extraction")
                listings = _extract_all_listings(page)
                for listing in listings:
                    if listing["listing_id"] not in seen_ids:
                        seen_ids.add(listing["listing_id"])
                        all_listings.append(listing)

        except PlaywrightTimeout as exc:
            logger.error("Timeout scraping %s: %s", url, exc)
        except Exception as exc:
            logger.error("Error scraping %s: %s", url, exc, exc_info=True)

    # Apply keyword filters
    all_listings = _filter_by_keywords(all_listings, profile)
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
