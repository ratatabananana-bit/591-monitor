import logging
import time
import re
from playwright.sync_api import Page, TimeoutError as PlaywrightTimeout
from .browser import get_browser_manager

logger = logging.getLogger(__name__)

BASE_URL = "https://rent.591.com.tw"

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
        # Find the link with listing ID
        link = card.query_selector("a[href*='/home/']")
        if not link:
            return None
        href = link.get_attribute("href") or ""
        match = re.search(r"/home/(\d+)", href)
        if not match:
            return None
        listing_id = match.group(1)

        result = {
            "listing_id": listing_id,
            "url": f"{BASE_URL}/home/{listing_id}",
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

    # Wait for content
    try:
        page.wait_for_selector("section, article, [class*='list'], [class*='item']", timeout=10000)
    except PlaywrightTimeout:
        pass

    # Try multiple card selectors — 591 uses different layouts
    selectors = [
        "section.vue-list-rent-item",
        "[class*='list-item']",
        "[class*='rent-item']",
        "article",
    ]

    cards = []
    for sel in selectors:
        cards = page.query_selector_all(sel)
        if cards:
            logger.debug("Found %d cards with selector '%s'", len(cards), sel)
            break

    if not cards:
        # Fallback: extract all /home/ links directly from page
        links = page.query_selector_all("a[href*='/home/']")
        seen = set()
        for link in links:
            href = link.get_attribute("href") or ""
            m = re.search(r"/home/(\d+)", href)
            if m and m.group(1) not in seen:
                lid = m.group(1)
                seen.add(lid)
                listings.append({"listing_id": lid, "url": f"{BASE_URL}/home/{lid}"})
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


def scrape_profile(profile: dict) -> list[dict]:
    """
    Scrape all listings for a search profile.
    Returns list of raw listing dicts.
    """
    mgr = get_browser_manager()
    url = _build_search_url(profile)
    all_listings: list[dict] = []
    seen_ids: set[str] = set()
    page_num = 1

    with mgr.new_page() as page:
        logger.info("Scraping URL: %s", url)
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            time.sleep(3)

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

                # Try to navigate to next page
                next_btn = page.query_selector(".pageNext:not(.disabled), [class*='next']:not([class*='disabled'])")
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
    url = f"{BASE_URL}/home/{listing_id}"
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
