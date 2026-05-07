import asyncio
import logging
from telegram import Bot
from telegram.constants import ParseMode
from ..config import settings

logger = logging.getLogger(__name__)


def _get_bot() -> Bot | None:
    if not settings.telegram_bot_token or not settings.telegram_chat_id:
        logger.warning("Telegram not configured, skipping alert")
        return None
    return Bot(token=settings.telegram_bot_token)


def _commute_lines(commute_results: list) -> str:
    if not commute_results:
        return "  No commute data"
    lines = []
    for cr in commute_results:
        transit = f"{cr.transit_minutes}min" if cr.transit_minutes else "N/A"
        walk = f"{cr.walk_minutes}min" if cr.walk_minutes else "N/A"
        dist = f"{cr.distance_meters / 1000:.1f}km" if cr.distance_meters else "N/A"
        anchor_name = cr.anchor.name if hasattr(cr, 'anchor') and cr.anchor else "Anchor"
        lines.append(f"  📍 {anchor_name}: transit {transit} / walk {walk} / {dist}")
    return "\n".join(lines)


def format_new_listing_alert(listing) -> str:
    commute = _commute_lines(listing.commute_results)
    return (
        f"🏠 *New Listing*\n"
        f"💰 NT${listing.price:,}/mo\n"
        f"📍 {listing.district or 'Unknown'} — {listing.size_ping or '?'}坪\n"
        f"⭐ Score: {listing.score or 0:.0f}/100\n"
        f"{commute}\n"
        f"🔗 [View Listing]({listing.url})"
    )


def format_price_change_alert(listing, old_price: int, new_price: int) -> str:
    direction = "📉" if new_price < old_price else "📈"
    diff = abs(new_price - old_price)
    return (
        f"{direction} *Price Change*\n"
        f"NT${old_price:,} → NT${new_price:,} ({'-' if new_price < old_price else '+'}{diff:,})\n"
        f"📍 {listing.district or 'Unknown'}\n"
        f"⭐ Score: {listing.score or 0:.0f}/100\n"
        f"🔗 [View Listing]({listing.url})"
    )


def format_reappeared_alert(listing) -> str:
    return (
        f"🔄 *Listing Reappeared*\n"
        f"💰 NT${listing.price:,}/mo\n"
        f"📍 {listing.district or 'Unknown'}\n"
        f"⭐ Score: {listing.score or 0:.0f}/100\n"
        f"🔗 [View Listing]({listing.url})"
    )


def format_scan_complete_alert(profile_name: str, new_count: int, total: int) -> str:
    return f"✅ Scan complete: *{profile_name}*\n{new_count} new / {total} total listings"


async def _send_async(text: str) -> None:
    bot = _get_bot()
    if not bot:
        return
    await bot.send_message(
        chat_id=settings.telegram_chat_id,
        text=text,
        parse_mode=ParseMode.MARKDOWN,
        disable_web_page_preview=True,
    )


def send_alert(text: str) -> None:
    """Sync wrapper — safe to call from any thread, including those with a running event loop."""
    import threading

    result_holder: list[Exception | None] = [None]

    def _run():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(_send_async(text))
        except Exception as exc:
            result_holder[0] = exc
        finally:
            loop.close()

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    t.join(timeout=15)
    if result_holder[0]:
        logger.error("Failed to send Telegram alert: %s", result_holder[0])
