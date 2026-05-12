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
    params = [f"region={city_code}"]

    room_types = profile.get("room_types", [])
    if room_types:
        codes = [str(ROOM_TYPE_CODES[rt]) for rt in room_types if rt in ROOM_TYPE_CODES]
        params.append(f"kind={','.join(codes) if codes else '0'}")
    else:
        params.append("kind=0")

    price_min = profile.get("price_min")
    price_max = profile.get("price_max")
    if price_min or price_max:
        params.append(f"price={price_min or 0}_{price_max or 0}")

    districts = profile.get("districts", [])
    if districts:
        params.append(f"section={','.join(str(d) for d in districts)}")

    return f"{BASE_URL}/list?{'&'.join(params)}"


def _parse_relative_date(text: str) -> datetime | None:
    """Convert '7天前更新', '昨日更新', '今日更新', '新上架' to UTC datetime."""
    now = datetime.now(timezone.utc)
    m = re.search(r"(\d+)天前", text)
    if m:
        return now - timedelta(days=int(m.group(1)))
    if "昨日" in text:
        return now - timedelta(days=1)
    if "今日" in text or "剛剛" in text or "小時前" in text or "分鐘前" in text or "新上架" in text or "上架" in text:
        return now
    return None


def _parse_listing_card(card) -> dict | None:
    """Extract listing data from a div.item[data-id] card (591 /list page)."""
    try:
        # Listing ID from data-id attribute
        listing_id = card.get_attribute("data-id")
        if not listing_id:
            return None

        result: dict = {
            "listing_id": listing_id,
            "url": f"{BASE_URL}/{listing_id}",
        }

        # Title + canonical URL
        title_el = card.query_selector(".item-info-title .link")
        if title_el:
            result["title"] = title_el.inner_text().strip()
            href = title_el.get_attribute("href") or ""
            if href.startswith("http"):
                result["url"] = href

        # Price from .text-26px inside .item-info-price
        price_el = card.query_selector(".item-info-price .text-26px")
        if not price_el:
            price_el = card.query_selector(".item-info-price")
        if price_el:
            digits = re.sub(r"[^\d]", "", price_el.inner_text())
            if digits:
                result["price"] = int(digits)

        # Room type / size / floor — first .item-info-txt (has .house-home icon)
        for txt_el in card.query_selector_all(".item-info-txt"):
            cls = txt_el.get_attribute("class") or ""

            if txt_el.query_selector(".house-home"):
                # Room type: first span text
                spans = txt_el.query_selector_all("span")
                if spans:
                    rt_text = spans[0].inner_text().strip()
                    for rt in ["整層住家", "獨立套房", "分租套房", "雅房"]:
                        if rt in rt_text:
                            result["room_type"] = rt
                            break
                # Size and floor from .line elements
                for line in txt_el.query_selector_all(".line"):
                    line_txt = line.inner_text().strip()
                    if "size_ping" not in result:
                        m = re.search(r"([\d.]+)坪", line_txt)
                        if m:
                            result["size_ping"] = float(m.group(1))
                    if "floor" not in result:
                        m = re.search(r"(\d+F/\d+F|\d+F)", line_txt)
                        if m:
                            result["floor"] = m.group(1)

            elif txt_el.query_selector(".house-place"):
                # District from .inline-flex-row inside place row
                addr_el = txt_el.query_selector(".inline-flex-row")
                if addr_el:
                    result["district"] = addr_el.inner_text().strip()

            elif "role-name" in cls:
                # Update time from .line containing 更新/上架
                for line in txt_el.query_selector_all(".line"):
                    line_txt = line.inner_text().strip()
                    if "更新" in line_txt or "上架" in line_txt:
                        dt = _parse_relative_date(line_txt)
                        if dt:
                            result["listing_updated_at"] = dt.isoformat()
                        break

        # Thumbnail — try data-src first (lazy-loaded), then non-placeholder src
        img = card.query_selector("img[data-src]")
        if img:
            result["thumbnail_url"] = img.get_attribute("data-src")
        else:
            img = card.query_selector("img[src]")
            if img:
                src = img.get_attribute("src") or ""
                if src and not src.startswith("data:"):
                    result["thumbnail_url"] = src

        return result

    except Exception as exc:
        logger.debug("Card parse error: %s", exc)
        return None


def _extract_all_listings(page: Page) -> list[dict]:
    """Extract all listing cards from the current page."""
    listings = []

    cards = page.query_selector_all(".item[data-id]")
    if cards:
        logger.info("Found %d listing cards", len(cards))
        for card in cards:
            listing = _parse_listing_card(card)
            if listing:
                listings.append(listing)
        return listings

    # Fallback: extract links only (no metadata)
    logger.warning("No .item[data-id] cards found — falling back to link extraction")
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
    """
    Fast pre-filter on list-page card data (title + district only).

    Rejected keywords: drop listing if keyword appears in title/district.
    Required keywords: NOT checked here — full article checked on detail page.
    Min ping: drop listing only when size is known and below threshold.
    """
    rejected = [kw.lower() for kw in profile.get("rejected_keywords", [])]
    min_ping = profile.get("min_ping")

    if not rejected and not min_ping:
        return listings

    result = []
    for listing in listings:
        # Size filter — only drop when size is known and below threshold
        if min_ping is not None:
            size = listing.get("size_ping")
            if size is not None and size < min_ping:
                continue

        text = (
            (listing.get("title") or "") + " " + (listing.get("district") or "")
        ).lower()
        if rejected and any(kw in text for kw in rejected):
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
            page.goto(url, wait_until="load", timeout=30000)
            # Wait for SPA to render listing cards
            try:
                page.wait_for_selector(".list-wrapper .item", timeout=15000)
            except Exception:
                pass
            # Scroll to trigger lazy-load images
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            try:
                page.wait_for_function(
                    "() => document.querySelectorAll('*').length > 600",
                    timeout=10000,
                )
            except Exception:
                pass

            while page_num <= 20:
                listings = _extract_all_listings(page)
                unseen = [l for l in listings if l["listing_id"] not in seen_ids]

                if not unseen:
                    logger.info("No new listing IDs on page %d, stopping", page_num)
                    break

                # Track all IDs seen (before keyword filter) to detect real end-of-pages
                for l in unseen:
                    seen_ids.add(l["listing_id"])

                filtered = _filter_by_keywords(unseen, profile)
                all_listings.extend(filtered)
                logger.info(
                    "Page %d: %d raw / %d after filter (total: %d)",
                    page_num, len(unseen), len(filtered), len(all_listings),
                )

                # Find next-page link: among all enabled navigators, pick one
                # whose target page number is strictly greater than current page.
                nav_links = page.query_selector_all(".paginator-container .navigator:not(.disabled) a")
                next_url = None
                for nav in nav_links:
                    href = nav.get_attribute("href") or ""
                    if not href:
                        continue
                    full = href if href.startswith("http") else f"{BASE_URL}{href}"
                    m = re.search(r'[?&]page=(\d+)', full)
                    target_page = int(m.group(1)) if m else 1
                    if target_page > page_num:
                        next_url = full
                        break

                if not next_url:
                    logger.info("No forward page link found after page %d, done", page_num)
                    break

                logger.info("Navigating to page %d: %s", page_num + 1, next_url)
                page.goto(next_url, wait_until="load", timeout=30000)
                try:
                    page.wait_for_selector(".item[data-id]", timeout=15000)
                except Exception:
                    pass
                page_num += 1

        except PlaywrightTimeout as exc:
            logger.error("Timeout scraping %s: %s", url, exc)
        except Exception as exc:
            logger.error("Error scraping %s: %s", url, exc, exc_info=True)

    logger.info("Scraped %d total listings for profile", len(all_listings))
    return all_listings


def _parse_posted_date(text: str) -> datetime | None:
    """Parse '此房屋在N天前發佈', '此房屋在N小時前發佈', '此房屋在N分鐘前發佈',
       '此房屋在4月29日發佈', '此房屋在今日發佈'."""
    now = datetime.now(timezone.utc)
    m = re.search(r"(\d+)分鐘前發佈", text)
    if m:
        return now - timedelta(minutes=int(m.group(1)))
    m = re.search(r"(\d+)小時前發佈", text)
    if m:
        return now - timedelta(hours=int(m.group(1)))
    m = re.search(r"(\d+)天前發佈", text)
    if m:
        return now - timedelta(days=int(m.group(1)))
    m = re.search(r"(\d+)月(\d+)日發佈", text)
    if m:
        month, day = int(m.group(1)), int(m.group(2))
        year = now.year
        dt = datetime(year, month, day, tzinfo=timezone.utc)
        if dt > now:  # date is in future → must be last year
            dt = datetime(year - 1, month, day, tzinfo=timezone.utc)
        return dt
    if "今日發佈" in text:
        return now
    if "昨日發佈" in text:
        return now - timedelta(days=1)
    return None


def scrape_listing_detail(listing_id: str) -> dict:
    """
    Open detail page once and extract:
      - posted_at (發佈 date) → datetime | None
      - image_urls            → list[str]
    Returns {} on complete failure.
    """
    mgr = get_browser_manager()
    url = f"{BASE_URL}/{listing_id}"
    result: dict = {}

    with mgr.new_page() as page:
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=15000)
            content = page.content()

            # --- Posted date ---
            m = re.search(r"此房屋在.{1,20}發佈", content)
            if m:
                dt = _parse_posted_date(m.group(0))
                if dt:
                    result["posted_at"] = dt
            else:
                logger.debug("No 發佈 date for listing %s", listing_id)

            # --- Images ---
            # Try known gallery selectors first
            image_urls: list[str] = []
            for selector in [
                ".house-img-list img",
                ".photo-list img",
                ".swiper-slide img",
                "[class*='img-list'] img",
                "[class*='photo'] img",
            ]:
                imgs = page.query_selector_all(selector)
                if imgs:
                    for img in imgs:
                        src = (
                            img.get_attribute("src")
                            or img.get_attribute("data-src")
                            or img.get_attribute("data-lazy-src")
                            or ""
                        )
                        src = src.strip()
                        if src and ("591" in src or "house" in src) and src not in image_urls:
                            image_urls.append(src)
                    if image_urls:
                        break

            # Fallback: regex all 591 image URLs from page source
            if not image_urls:
                found = re.findall(
                    r'https?://[^\s"\'<>]+\.(?:jpg|jpeg|png|webp)[^\s"\'<>]*',
                    content,
                )
                for url_str in found:
                    if ("591" in url_str or "house" in url_str) and url_str not in image_urls:
                        image_urls.append(url_str)

            result["image_urls"] = image_urls[:20]  # cap at 20
            logger.debug("listing %s: %d images found", listing_id, len(image_urls))

            # --- Facilities ---
            # Each facility is a <dl> inside .facility.service-facility
            # dl with class "del" = not available; skip those
            facilities: list[str] = []
            fac_dls = page.query_selector_all(".facility.service-facility dl")
            for dl in fac_dls:
                dl_class = dl.get_attribute("class") or ""
                if "del" in dl_class.split():
                    continue
                dd = dl.query_selector("dd.text")
                if dd:
                    name = dd.inner_text().strip()
                    if name:
                        facilities.append(name)
            result["facilities"] = facilities
            logger.debug("listing %s: %d facilities found", listing_id, len(facilities))

            # --- Address ---
            try:
                addr_el = page.query_selector('[class*=address]')
                if addr_el:
                    addr_text = addr_el.inner_text().strip()
                    addr_text = re.sub(r'^地址[：:]\s*', '', addr_text).strip()
                    if addr_text and len(addr_text) > 2:
                        result["address"] = addr_text
                        logger.debug("listing %s: address=%s", listing_id, addr_text)
            except Exception as exc:
                logger.debug("listing %s: address extraction failed: %s", listing_id, exc)

            # --- Full page text (for keyword checking by pipeline) ---
            try:
                result["page_text"] = page.inner_text("body")
            except Exception:
                result["page_text"] = content  # fall back to raw HTML

        except Exception as exc:
            logger.warning("scrape_listing_detail failed for %s: %s", listing_id, exc)

    return result


def scrape_posted_date(listing_id: str) -> datetime | None:
    """Kept for backwards compat. Prefer scrape_listing_detail."""
    detail = scrape_listing_detail(listing_id)
    return detail.get("posted_at")


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
