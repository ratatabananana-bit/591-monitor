import logging
import threading
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, ContextTypes, filters
from ..config import settings
from ..database import SessionLocal
from ..models import Listing, SearchProfile, TelegramSubscription, TelegramAlertedListing

logger = logging.getLogger(__name__)

# Callback data prefixes
CB_TOGGLE = "tag_toggle:"
CB_SAVE = "tag_save"
CB_CLEAR = "tag_clear"
CB_MARK_READ = "mark_read:"
CB_MARK_SAVE = "mark_save:"
CB_MARK_REJECT = "mark_reject:"


def _get_all_tags(db) -> list[str]:
    """Get all subscribable tags: listing tags + profile tags + badge tags."""
    tags: set[str] = set()

    # Real tags from listings
    rows = db.query(Listing.tags).filter(Listing.tags != None).all()
    for (t,) in rows:
        if t:
            tags.update(t)

    # Profile tags
    profiles = db.query(SearchProfile).filter(SearchProfile.enabled == True).all()
    for p in profiles:
        tags.add(f"profile:{p.name}")

    # Badge tags
    tags.update(["badge:new", "badge:fresh", "badge:stale"])

    return sorted(tags)


def _get_or_create_sub(db, chat_id: str, chat_name: str | None) -> TelegramSubscription:
    sub = db.query(TelegramSubscription).filter(
        TelegramSubscription.chat_id == chat_id
    ).first()
    if not sub:
        sub = TelegramSubscription(chat_id=chat_id, chat_name=chat_name, subscribed_tags=[])
        db.add(sub)
        db.commit()
        db.refresh(sub)
    return sub


def _build_tag_keyboard(available_tags: list[str], selected: list[str]) -> InlineKeyboardMarkup:
    selected_set = set(selected)
    rows = []
    # Two tags per row
    for i in range(0, len(available_tags), 2):
        row = []
        for tag in available_tags[i:i + 2]:
            check = "✅ " if tag in selected_set else "⬜ "
            row.append(InlineKeyboardButton(
                text=f"{check}{tag}",
                callback_data=f"{CB_TOGGLE}{tag}",
            ))
        rows.append(row)
    # Action buttons
    rows.append([
        InlineKeyboardButton("💾 Save Subscription", callback_data=CB_SAVE),
        InlineKeyboardButton("🗑 Clear All", callback_data=CB_CLEAR),
    ])
    return InlineKeyboardMarkup(rows)


# ── Commands ─────────────────────────────────────────────────────────────────

MAIN_KEYBOARD = ReplyKeyboardMarkup(
    [
        [KeyboardButton("🏷 Subscribe"), KeyboardButton("📋 My Subscription")],
        [KeyboardButton("🆕 Recent Listings"), KeyboardButton("🔖 Saved Listings")],
        [KeyboardButton("🔍 Scan Now"), KeyboardButton("❌ Unsubscribe")],
    ],
    resize_keyboard=True,
)


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "🏠 *591 Rental Monitor*\n\nChoose an option below:",
        parse_mode="Markdown",
        reply_markup=MAIN_KEYBOARD,
    )


async def cmd_subscribe(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = str(update.effective_chat.id)
    chat_name = update.effective_chat.title or update.effective_user.first_name if update.effective_user else None

    db = SessionLocal()
    try:
        available = _get_all_tags(db)
        if not available:
            await update.message.reply_text(
                "⚠️ No tags found yet. Run a scan and set up tag rules first."
            )
            return

        sub = _get_or_create_sub(db, chat_id, chat_name)
        selected = list(sub.subscribed_tags or [])

        # Store pending selection in user_data
        context.user_data["pending_tags"] = selected
        context.user_data["available_tags"] = available

        kb = _build_tag_keyboard(available, selected)
        await update.message.reply_text(
            "🏷 *Select tags for your subscription*\n"
            "Listings must match ALL selected tags to be sent to you.",
            parse_mode="Markdown",
            reply_markup=kb,
        )
    finally:
        db.close()


async def cb_tag_toggle(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    tag = query.data[len(CB_TOGGLE):]
    pending = context.user_data.get("pending_tags", [])
    available = context.user_data.get("available_tags", [])

    if tag in pending:
        pending.remove(tag)
    else:
        pending.append(tag)
    context.user_data["pending_tags"] = pending

    kb = _build_tag_keyboard(available, pending)
    selected_str = ", ".join(pending) if pending else "none"
    await query.edit_message_text(
        f"🏷 *Select tags for your subscription*\n"
        f"Listings must match ALL selected tags to be sent to you.\n\n"
        f"Currently selected: `{selected_str}`",
        parse_mode="Markdown",
        reply_markup=kb,
    )


async def cb_tag_save(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    chat_id = str(update.effective_chat.id)
    chat_name = update.effective_chat.title or (
        update.effective_user.first_name if update.effective_user else None
    )
    pending = context.user_data.get("pending_tags", [])

    db = SessionLocal()
    try:
        sub = _get_or_create_sub(db, chat_id, chat_name)
        sub.subscribed_tags = pending
        db.commit()

        if pending:
            tag_str = " ".join(pending)
            await query.edit_message_text(
                f"✅ *Subscription saved!*\n\nYou'll receive alerts for listings tagged: `{tag_str}`",
                parse_mode="Markdown",
            )
        else:
            await query.edit_message_text(
                "⚠️ No tags selected — subscription cleared. Use /subscribe to set up again."
            )
    finally:
        db.close()


async def cb_tag_clear(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    context.user_data["pending_tags"] = []
    available = context.user_data.get("available_tags", [])
    kb = _build_tag_keyboard(available, [])
    await query.edit_message_text(
        "🏷 *Select tags for your subscription*\n"
        "Listings must match ALL selected tags to be sent to you.\n\n"
        "Currently selected: `none`",
        parse_mode="Markdown",
        reply_markup=kb,
    )


async def cmd_mysubs(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = str(update.effective_chat.id)
    db = SessionLocal()
    try:
        sub = db.query(TelegramSubscription).filter(
            TelegramSubscription.chat_id == chat_id
        ).first()
        if not sub or not sub.subscribed_tags:
            await update.message.reply_text(
                "You have no active subscription. Use /subscribe to set one up."
            )
            return
        alerted_count = db.query(TelegramAlertedListing).filter(
            TelegramAlertedListing.subscription_id == sub.id
        ).count()
        tag_str = " ".join(sub.subscribed_tags)
        await update.message.reply_text(
            f"📋 *Your subscription*\n\n"
            f"Tags: `{tag_str}`\n"
            f"Listings sent: {alerted_count}\n"
            f"Status: {'✅ Active' if sub.enabled else '⏸ Paused'}\n\n"
            f"Use /subscribe to change tags or /unsubscribe to remove.",
            parse_mode="Markdown",
        )
    finally:
        db.close()


async def _handle_listing_action(update: Update, prefix: str, new_status: str, label: str) -> None:
    from ..services.tagger import apply_tags
    query = update.callback_query
    await query.answer()

    listing_id_str = query.data[len(prefix):]
    db = SessionLocal()
    try:
        listing = db.query(Listing).filter(Listing.listing_id == listing_id_str).first()
        if listing:
            listing.status = new_status
            apply_tags(db, listing)
            db.commit()
        try:
            await query.edit_message_reply_markup(reply_markup=None)
        except Exception:
            pass
    finally:
        db.close()


async def cb_mark_read(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _handle_listing_action(update, CB_MARK_READ, "ACTIVE", "Read")


async def cb_mark_save(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _handle_listing_action(update, CB_MARK_SAVE, "SAVED", "Saved")


async def cb_mark_reject(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _handle_listing_action(update, CB_MARK_REJECT, "REJECTED", "Rejected")


async def cmd_unsubscribe(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = str(update.effective_chat.id)
    db = SessionLocal()
    try:
        sub = db.query(TelegramSubscription).filter(
            TelegramSubscription.chat_id == chat_id
        ).first()
        if not sub:
            await update.message.reply_text("No subscription found.")
            return
        db.delete(sub)
        db.commit()
        await update.message.reply_text("✅ Subscription removed.")
    finally:
        db.close()


async def cmd_scan_now(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    from ..services.pipeline import run_scan_for_profile
    db = SessionLocal()
    try:
        profiles = db.query(SearchProfile).filter(SearchProfile.enabled == True).all()
        if not profiles:
            await update.message.reply_text("No enabled search profiles configured.")
            return
        await update.message.reply_text(f"Triggering scan for {len(profiles)} profile(s)…")
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
            .order_by(Listing.score.desc())
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
            "*Recent Listings (by score):*\n" + "\n".join(lines),
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


async def handle_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.message.text
    if text == "🏷 Subscribe":
        await cmd_subscribe(update, context)
    elif text == "📋 My Subscription":
        await cmd_mysubs(update, context)
    elif text == "🆕 Recent Listings":
        await cmd_recent(update, context)
    elif text == "🔖 Saved Listings":
        await cmd_saved(update, context)
    elif text == "🔍 Scan Now":
        await cmd_scan_now(update, context)
    elif text == "❌ Unsubscribe":
        await cmd_unsubscribe(update, context)


def setup_bot(app: Application) -> None:
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("subscribe", cmd_subscribe))
    app.add_handler(CommandHandler("mysubs", cmd_mysubs))
    app.add_handler(CommandHandler("unsubscribe", cmd_unsubscribe))
    app.add_handler(CommandHandler("scan_now", cmd_scan_now))
    app.add_handler(CommandHandler("recent", cmd_recent))
    app.add_handler(CommandHandler("saved", cmd_saved))
    # Reply keyboard button taps
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_buttons))
    # Inline keyboard callbacks
    app.add_handler(CallbackQueryHandler(cb_tag_toggle, pattern=f"^{CB_TOGGLE}"))
    app.add_handler(CallbackQueryHandler(cb_tag_save, pattern=f"^{CB_SAVE}$"))
    app.add_handler(CallbackQueryHandler(cb_tag_clear, pattern=f"^{CB_CLEAR}$"))
    app.add_handler(CallbackQueryHandler(cb_mark_read, pattern=f"^{CB_MARK_READ}"))
    app.add_handler(CallbackQueryHandler(cb_mark_save, pattern=f"^{CB_MARK_SAVE}"))
    app.add_handler(CallbackQueryHandler(cb_mark_reject, pattern=f"^{CB_MARK_REJECT}"))
