"""
Post-scan subscription alert service.

Flow:
  1. Called after each scan completes.
  2. If any scan is still running → skip (last scan to finish will handle it).
  3. Find NEW/REAPPEARED listings not yet alerted to each subscriber.
  4. For each subscriber, filter listings to those matching ALL subscribed tags.
  5. Send photos + details. Mark as alerted.
"""
import asyncio
import logging
import threading
import httpx

# Ensures only one alert run executes at a time within this process.
# Prevents duplicate Telegram sends when multiple scans finish simultaneously.
_alert_lock = threading.Lock()
from telegram import Bot, InputMediaPhoto
from telegram.constants import ParseMode
from telegram.error import TelegramError, TimedOut
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.exc import IntegrityError
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from ..config import settings
from ..database import SessionLocal
from ..models import Listing, ScanRun, SearchProfile, TelegramSubscription, TelegramAlertedListing, CommuteResult

logger = logging.getLogger(__name__)

ACTIVE_ALERT_STATUSES = {"NEW", "REAPPEARED"}
DELISTED_STATUSES = {"MISSING_ON_SEARCH", "UNAVAILABLE", "ARCHIVED"}


# ── Formatting ──────────────────────────────────────────────────────────────

def _esc(text: str) -> str:
    """Escape HTML special chars for ParseMode.HTML."""
    return text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

def _all_tags(listing: Listing, profile_names: dict | None = None) -> list[str]:
    """All tags are stored in listing.tags by the tagger (including badge: and profile:)."""
    return list(listing.tags or [])


def _maps_url(listing: Listing) -> str | None:
    """Google Maps search URL for this listing's location."""
    query = listing.address or listing.district
    if not query:
        return None
    import urllib.parse
    return "https://maps.google.com/?q=" + urllib.parse.quote(query + " 台灣")


def _format_listing(listing: Listing, profile_names: dict | None = None) -> str:
    if profile_names is None:
        profile_names = {}
    parts = []

    # Title
    if listing.title:
        parts.append(f"<b>{_esc(listing.title)}</b>")

    # Key stats line
    price_str = f"NT${listing.price:,}/mo" if listing.price else "Price N/A"
    size_str = f"{listing.size_ping}坪" if listing.size_ping else "?"
    floor_str = f" · {_esc(listing.floor)}" if listing.floor else ""
    parts.append(f"💰 {price_str}  |  📐 {size_str}{floor_str}")

    # Location — always shown, hyperlinked to Google Maps
    location_label = listing.district or listing.address or "Unknown location"
    maps_url = _maps_url(listing)
    if maps_url:
        parts.append(f'📍 <a href="{maps_url}">{_esc(location_label)}</a>')
    else:
        parts.append(f"📍 {_esc(location_label)}")

    # Score
    if listing.score is not None:
        parts.append(f"⭐ Score: {listing.score:.0f}/100")

    # Commute
    if listing.commute_results:
        commute_lines = []
        for cr in listing.commute_results:
            anchor_name = "Anchor"
            try:
                if cr.anchor:
                    anchor_name = cr.anchor.name
            except Exception:
                pass
            transit = f"{cr.transit_minutes}min" if cr.transit_minutes else "N/A"
            scooter = f"{cr.scooter_minutes}min 🛵" if cr.scooter_minutes else ""
            line = f"🚇 {_esc(anchor_name)}: {transit} transit"
            if scooter:
                line += f" · {scooter}"
            commute_lines.append(line)
        parts.extend(commute_lines)

    # Tags — all tags: listing + profile + badge
    all_tags = _all_tags(listing, profile_names)
    if all_tags:
        parts.append(f"🏷 {' · '.join(_esc(t) for t in all_tags)}")

    # Link
    parts.append(f'🔗 <a href="{listing.url}">View on 591</a>')

    return "\n".join(parts)


def _format_delisted(listing: Listing) -> str:
    price_str = f"NT${listing.price:,}/mo" if listing.price else "N/A"
    location_label = listing.district or listing.address or "Unknown location"
    maps_url = _maps_url(listing)
    location_str = f'<a href="{maps_url}">{_esc(location_label)}</a>' if maps_url else _esc(location_label)
    return (
        f"⚠️ <b>Saved listing delisted</b>\n"
        f"💰 {price_str}  |  📍 {location_str}\n"
        f"⭐ Score: {listing.score or 0:.0f}/100\n"
        f'🔗 <a href="{listing.url}">View on 591</a>'
    )


# ── Sending ──────────────────────────────────────────────────────────────────

def _listing_action_keyboard(listing_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Read", callback_data=f"mark_read:{listing_id}"),
        InlineKeyboardButton("💾 Save", callback_data=f"mark_save:{listing_id}"),
        InlineKeyboardButton("❌ Reject", callback_data=f"mark_reject:{listing_id}"),
    ]])


_591_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Referer": "https://rent.591.com.tw/",
}


async def _download_image(url: str) -> bytes | None:
    """Download an image via our server (avoids 591 CDN blocking Telegram's IPs)."""
    try:
        async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
            r = await client.get(url, headers=_591_HEADERS)
            if r.status_code == 200 and r.content:
                return r.content
    except Exception as exc:
        logger.warning("Failed to download image %s: %s", url, exc)
    return None


async def _send_listing_async(bot: Bot, chat_id: str, listing: Listing, profile_names: dict | None = None) -> bool:
    """Returns True if send succeeded with photos, False will retry next scan."""
    caption = _format_listing(listing, profile_names or {})
    single_caption = caption if len(caption) <= 1024 else caption[:1021] + "…"

    image_urls = [u for u in (listing.image_urls or []) if u.startswith("http")]
    reply_markup = _listing_action_keyboard(listing.listing_id)

    if image_urls:
        # Download images through our server — 591 CDN blocks Telegram's IPs
        photo_bytes = await _download_image(image_urls[0])
        extra_bytes = []
        if photo_bytes and len(image_urls) > 1:
            for url in image_urls[1:8]:
                b = await _download_image(url)
                if b:
                    extra_bytes.append(b)

        if photo_bytes:
            if not extra_bytes:
                # Single photo — caption is included, safe to retry whole thing
                for attempt in range(6):
                    try:
                        await bot.send_photo(
                            chat_id=chat_id,
                            photo=photo_bytes,
                            caption=single_caption,
                            parse_mode=ParseMode.HTML,
                            reply_markup=reply_markup,
                            read_timeout=40,
                            write_timeout=40,
                            connect_timeout=15,
                        )
                        return True
                    except TelegramError as exc:
                        logger.warning("Photo send attempt %d/6 failed for %s: %s", attempt + 1, listing.listing_id, exc)
                        if attempt < 5:
                            await asyncio.sleep(10)
            else:
                # Multi-photo: send_media_group and send_message are separate calls.
                # Track each independently so a successful media_group is never re-sent
                # on retry (which caused duplicate spam when only the text message failed).
                media_sent = False
                for attempt in range(6):
                    try:
                        if not media_sent:
                            media = [InputMediaPhoto(media=photo_bytes)] + [InputMediaPhoto(media=b) for b in extra_bytes]
                            await bot.send_media_group(
                                chat_id=chat_id,
                                media=media,
                                read_timeout=60,
                                write_timeout=60,
                                connect_timeout=15,
                            )
                            media_sent = True
                        await bot.send_message(
                            chat_id=chat_id,
                            text=caption,
                            parse_mode=ParseMode.HTML,
                            reply_markup=reply_markup,
                            disable_web_page_preview=True,
                            read_timeout=30,
                            write_timeout=30,
                            connect_timeout=15,
                        )
                        return True
                    except TimedOut as exc:
                        # On timeout we cannot know if Telegram delivered the message.
                        # Retrying risks a duplicate — stop here and treat as success.
                        if media_sent:
                            logger.warning(
                                "send_message timed out for %s (media already sent) — "
                                "treating as delivered to avoid duplicate text", listing.listing_id
                            )
                            return True
                        # Timed out before media was sent — safe to retry whole thing
                        logger.warning("send_media_group timed out for %s attempt %d/6 — retrying",
                                       listing.listing_id, attempt + 1)
                        if attempt < 5:
                            await asyncio.sleep(10)
                    except TelegramError as exc:
                        logger.warning("Send attempt %d/6 failed for %s (media_sent=%s): %s",
                                       attempt + 1, listing.listing_id, media_sent, exc)
                        if attempt < 5:
                            await asyncio.sleep(10)
                # If photos sent but text never made it, still count as success —
                # photos were delivered, don't re-send on next scan
                if media_sent:
                    logger.warning("Photos sent but text failed for %s — marking as sent anyway", listing.listing_id)
                    return True

        # Download failed or all send attempts exhausted — retry next scan
        logger.warning("Photo send failed for %s — will retry next scan", listing.listing_id)
        return False

    # No images — send text only
    for attempt in range(6):
        try:
            await bot.send_message(
                chat_id=chat_id,
                text=caption,
                parse_mode=ParseMode.HTML,
                reply_markup=reply_markup,
                disable_web_page_preview=True,
                read_timeout=30,
                write_timeout=30,
                connect_timeout=15,
            )
            return True
        except TimedOut:
            # Timeout — message likely delivered, stop retrying to avoid duplicate
            logger.warning("send_message timed out for %s (text-only) — treating as delivered", listing.listing_id)
            return True
        except TelegramError as exc:
            logger.warning("Text send attempt %d/6 failed for %s: %s", attempt + 1, listing.listing_id, exc)
            if attempt < 5:
                await asyncio.sleep(10)
    return False


async def _send_text_async(bot: Bot, chat_id: str, text: str) -> None:
    try:
        await bot.send_message(
            chat_id=chat_id,
            text=text,
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True,
        )
    except TelegramError as exc:
        logger.warning("Failed to send message to %s: %s", chat_id, exc)


# ── Core alert logic ─────────────────────────────────────────────────────────


def _listing_matches_subscription(
    listing: Listing, subscribed_tags: list[str], profile_names: dict | None = None
) -> bool:
    """ALL subscribed tags must match (AND logic). Tags are read from listing.tags (stored by tagger)."""
    if not subscribed_tags:
        return False
    stored = set(listing.tags or [])
    return all(tag in stored for tag in subscribed_tags)


async def _run_alerts_async(db: Session, run: ScanRun | None = None) -> int:
    """Returns total number of listings successfully sent."""
    from datetime import datetime, timezone, timedelta
    def _utcnow():
        return datetime.now(timezone.utc)

    logger.info("_run_alerts_async: starting")
    if not settings.telegram_bot_token:
        logger.warning("_run_alerts_async: no telegram_bot_token, skipping")
        return 0

    # Auto-heal stale "running" scan records older than 2 hours (crash/kill leftovers).
    stale_cutoff = _utcnow() - timedelta(hours=2)
    stale = db.query(ScanRun).filter(
        ScanRun.status == "running",
        ScanRun.job_type != "telegram_alerts",
        ScanRun.started_at < stale_cutoff,
    ).all()
    for s in stale:
        logger.warning("Marking stale scan run %s as failed (started %s)", s.id, s.started_at)
        s.status = "failed"
        s.finished_at = _utcnow()
        s.errors = {"error": "auto-healed: process died without updating status"}
    if stale:
        db.commit()

    # Check if any scan still running — if so, last one to finish handles alerts
    running = db.query(ScanRun).filter(
        ScanRun.status == "running",
        ScanRun.job_type != "telegram_alerts",
    ).count()
    if running > 0:
        logger.info("Skipping alerts — %d scan(s) still running", running)
        if run:
            run.status = "cancelled"
            run.errors = {"reason": f"skipped — {running} scan(s) still running"}
            run.finished_at = _utcnow()
            db.commit()
        return 0

    subscriptions = db.query(TelegramSubscription).filter(
        TelegramSubscription.enabled == True
    ).all()
    logger.info("_run_alerts_async: %d active subscription(s)", len(subscriptions))
    if not subscriptions:
        if run:
            run.status = "success"
            run.finished_at = _utcnow()
            db.commit()
        return 0

    # Build profile_id → name map for profile tag matching
    profiles = db.query(SearchProfile).all()
    profile_names = {str(p.id): p.name for p in profiles}

    # Listings eligible for "new" alerts — eager-load relationships to avoid detached-instance errors
    new_listings = (
        db.query(Listing)
        .options(joinedload(Listing.commute_results).joinedload(CommuteResult.anchor))
        .filter(Listing.status.in_(ACTIVE_ALERT_STATUSES))
        .all()
    )
    logger.info("_run_alerts_async: %d NEW/REAPPEARED listings", len(new_listings))
    if run:
        run.listings_found = len(new_listings)
        db.commit()

    bot = Bot(token=settings.telegram_bot_token)
    total_sent = 0

    for sub in subscriptions:
        if not sub.subscribed_tags:
            logger.info("Sub %s (%s): no subscribed_tags, skipping", sub.chat_id, sub.chat_name)
            continue

        logger.info("Sub %s (%s): subscribed_tags=%s", sub.chat_id, sub.chat_name, sub.subscribed_tags)

        # Find already-alerted listing IDs for this subscription
        alerted_ids = {
            row.listing_id
            for row in db.query(TelegramAlertedListing.listing_id).filter(
                TelegramAlertedListing.subscription_id == sub.id
            ).all()
        }
        logger.info("Sub %s: %d already-alerted IDs", sub.chat_id, len(alerted_ids))

        # Filter to matching, not-yet-alerted listings
        to_send = []
        for l in new_listings:
            if l.id in alerted_ids:
                continue
            matches = _listing_matches_subscription(l, sub.subscribed_tags, profile_names)
            if not matches:
                logger.debug("Listing %s tags=%s — no match for sub tags=%s",
                             l.listing_id, l.tags, sub.subscribed_tags)
            else:
                to_send.append(l)

        if not to_send:
            logger.info("Sub %s: 0 listings to send (all filtered or already alerted)", sub.chat_id)
            continue

        logger.info(
            "Attempting to reserve %d listings for subscription %s (%s)",
            len(to_send), sub.chat_id, sub.chat_name or "?"
        )

        # Phase 1: Reserve all listings atomically before sending anything.
        # Both containers may reach here simultaneously with the same to_send list.
        # Committing each reservation first means only one container wins each
        # listing via the DB unique constraint — the loser gets IntegrityError
        # and is excluded. The header is then only sent if we own ≥1 listing,
        # preventing duplicate "🔔 N new listings" messages.
        reserved_listings: list[tuple] = []  # (listing, reserved_record)
        for listing in to_send:
            alert_type = "new" if listing.status == "NEW" else "reappeared"
            try:
                reserved = TelegramAlertedListing(
                    subscription_id=sub.id,
                    listing_id=listing.id,
                    alert_type=alert_type,
                )
                db.add(reserved)
                db.commit()
                reserved_listings.append((listing, reserved))
            except IntegrityError:
                db.rollback()
                logger.info(
                    "Listing %s sub %s already reserved by another process — skipping",
                    listing.listing_id, sub.id,
                )

        if not reserved_listings:
            logger.info("Sub %s: no listings reserved (all claimed by another process)", sub.chat_id)
            continue

        logger.info("Sub %s: reserved %d/%d listings — sending now", sub.chat_id, len(reserved_listings), len(to_send))

        # Phase 2: Send header, then each reserved listing.
        # Header count reflects only what this process actually owns.
        tag_str = " ".join(sub.subscribed_tags)
        n = len(reserved_listings)
        await _send_text_async(
            bot, sub.chat_id,
            f"🔔 <b>{n} new listing{'s' if n > 1 else ''}</b> matching {_esc(tag_str)}"
        )

        for listing, reserved in reserved_listings:
            ok = False
            try:
                ok = await _send_listing_async(bot, sub.chat_id, listing, profile_names)
            except Exception as exc:
                logger.error("Error sending listing %s: %s", listing.listing_id, exc)

            if not ok:
                # Send failed — remove reservation so next cycle retries
                try:
                    db.delete(reserved)
                    db.commit()
                except Exception as del_exc:
                    logger.warning("Failed to delete reservation for %s: %s", listing.listing_id, del_exc)
                    db.rollback()
                await asyncio.sleep(2)
                continue

            total_sent += 1
            if run:
                run.new_listings = total_sent
                db.commit()
            await asyncio.sleep(1)  # pace between successful sends

    return total_sent


async def _run_delisted_alert_async(db: Session, listing: Listing) -> None:
    """Send delisted alert to any subscriber who was previously alerted about this listing."""
    if not settings.telegram_bot_token:
        return

    alerted_rows = db.query(TelegramAlertedListing).filter(
        TelegramAlertedListing.listing_id == listing.id,
        TelegramAlertedListing.alert_type != "delisted",
    ).all()

    if not alerted_rows:
        return

    bot = Bot(token=settings.telegram_bot_token)
    text = _format_delisted(listing)

    for row in alerted_rows:
        sub = db.query(TelegramSubscription).filter(
            TelegramSubscription.id == row.subscription_id
        ).first()
        if not sub or not sub.enabled:
            continue
        try:
            await _send_text_async(bot, sub.chat_id, text)
            row.alert_type = "delisted"
            db.commit()
        except Exception as exc:
            logger.error("Error sending delisted alert to %s: %s", sub.chat_id, exc)


# ── Sync wrappers ─────────────────────────────────────────────────────────────

def _run_in_thread(coro) -> None:
    def _run():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(coro)
        except Exception as exc:
            logger.error("Alert thread error: %s", exc, exc_info=True)
        finally:
            loop.close()
    t = threading.Thread(target=_run, daemon=True)
    t.start()


def trigger_subscription_alerts() -> None:
    """Call after a scan completes. Skips if other scans still running."""
    def _run():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        db = SessionLocal()
        try:
            loop.run_until_complete(_run_alerts_async(db))
        except Exception as exc:
            logger.error("Alert thread error: %s", exc, exc_info=True)
        finally:
            db.close()
            loop.close()
    t = threading.Thread(target=_run, daemon=True)
    t.start()


def trigger_subscription_alerts_sync() -> None:
    """Blocking version for use in scan pipeline. Runs in a fresh thread to guarantee an isolated event loop."""
    import concurrent.futures
    from datetime import datetime, timezone

    logger.info("[alerts] trigger_subscription_alerts_sync: starting")

    if not _alert_lock.acquire(blocking=False):
        logger.info("[alerts] another alert run already in progress — skipping this cycle")
        return

    def _run():
        logger.info("[alerts] _run thread started")
        db = SessionLocal()
        run = ScanRun(
            started_at=datetime.now(timezone.utc),
            status="running",
            job_type="telegram_alerts",
            listings_found=0,
            new_listings=0,
            updated_listings=0,
            gone_listings=0,
        )
        db.add(run)
        db.commit()
        logger.info("[alerts] ScanRun created: %s", run.id)
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                total_sent = loop.run_until_complete(_run_alerts_async(db, run=run))
                if run.status not in ("cancelled",):
                    run.status = "success"
                run.finished_at = datetime.now(timezone.utc)
                db.commit()
                logger.info("[alerts] complete: %d sent", total_sent)
            finally:
                loop.close()
                asyncio.set_event_loop(None)
        except Exception as exc:
            logger.error("[alerts] error: %s", exc, exc_info=True)
            try:
                run.status = "failed"
                run.errors = {"error": str(exc)}
                run.finished_at = datetime.now(timezone.utc)
                db.commit()
            except Exception:
                pass
        finally:
            db.close()
            logger.info("[alerts] _run thread done")

    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(_run)
            try:
                future.result(timeout=300)  # 5-minute hard timeout
            except concurrent.futures.TimeoutError:
                logger.error("[alerts] timed out after 5 minutes — alert skipped this cycle")
            except Exception as exc:
                logger.error("[alerts] executor error: %s", exc, exc_info=True)
    finally:
        _alert_lock.release()
    logger.info("[alerts] trigger_subscription_alerts_sync: done")


def trigger_delisted_alert(listing: Listing, db: Session) -> None:
    """Call when a SAVED listing becomes delisted."""
    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(_run_delisted_alert_async(db, listing))
    finally:
        loop.close()
