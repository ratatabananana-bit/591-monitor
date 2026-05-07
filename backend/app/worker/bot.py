import logging
import threading
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from ..config import settings
from ..database import SessionLocal
from ..models import Listing, SearchProfile

logger = logging.getLogger(__name__)


async def cmd_scan_now(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    from ..services.pipeline import run_scan_for_profile
    db = SessionLocal()
    try:
        profiles = db.query(SearchProfile).filter(SearchProfile.enabled == True).all()
        if not profiles:
            await update.message.reply_text("No enabled search profiles configured.")
            return
        await update.message.reply_text(f"Triggering scan for {len(profiles)} profile(s)...")
        for profile in profiles:
            t = threading.Thread(target=run_scan_for_profile, args=(profile.id,), daemon=True)
            t.start()
    finally:
        db.close()


async def cmd_recent(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    db = SessionLocal()
    try:
        listings = (
            db.query(Listing)
            .filter(Listing.status.in_(["NEW", "ACTIVE", "REAPPEARED"]))
            .order_by(Listing.first_seen_at.desc())
            .limit(10)
            .all()
        )
        if not listings:
            await update.message.reply_text("No recent listings.")
            return
        lines = [
            f"💰 NT${l.price:,} | {l.district or '?'} | ⭐{l.score or 0:.0f} | [View]({l.url})"
            for l in listings
        ]
        await update.message.reply_text(
            "*Recent Listings:*\n" + "\n".join(lines),
            parse_mode="Markdown",
            disable_web_page_preview=True,
        )
    finally:
        db.close()


async def cmd_saved(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    db = SessionLocal()
    try:
        listings = db.query(Listing).filter(Listing.status == "SAVED").order_by(Listing.score.desc()).all()
        if not listings:
            await update.message.reply_text("No saved listings.")
            return
        lines = [
            f"💰 NT${l.price:,} | {l.district or '?'} | ⭐{l.score or 0:.0f} | [View]({l.url})"
            for l in listings
        ]
        await update.message.reply_text(
            "*Saved Listings:*\n" + "\n".join(lines),
            parse_mode="Markdown",
            disable_web_page_preview=True,
        )
    finally:
        db.close()


async def cmd_watched(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    db = SessionLocal()
    try:
        listings = db.query(Listing).filter(Listing.status == "WATCHED").order_by(Listing.score.desc()).all()
        if not listings:
            await update.message.reply_text("No watched listings.")
            return
        lines = [
            f"💰 NT${l.price:,} | {l.district or '?'} | ⭐{l.score or 0:.0f} | [View]({l.url})"
            for l in listings
        ]
        await update.message.reply_text(
            "*Watched Listings:*\n" + "\n".join(lines),
            parse_mode="Markdown",
            disable_web_page_preview=True,
        )
    finally:
        db.close()


def setup_bot(app: Application) -> None:
    app.add_handler(CommandHandler("scan_now", cmd_scan_now))
    app.add_handler(CommandHandler("recent", cmd_recent))
    app.add_handler(CommandHandler("saved", cmd_saved))
    app.add_handler(CommandHandler("watched", cmd_watched))
