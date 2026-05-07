import asyncio
import logging
import signal
from ..config import settings
from .scheduler import setup_scheduler
from .bot import setup_bot

logging.basicConfig(
    level=settings.log_level,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)


async def run_worker() -> None:
    logger.info("Starting worker...")

    scheduler = setup_scheduler()
    scheduler.start()
    logger.info("Scheduler started with %d jobs", len(scheduler.get_jobs()))

    app = None
    if settings.telegram_bot_token:
        from telegram.ext import Application
        app = Application.builder().token(settings.telegram_bot_token).build()
        setup_bot(app)
        await app.initialize()
        await app.start()
        await app.updater.start_polling(drop_pending_updates=True)
        logger.info("Telegram bot started")
    else:
        logger.warning("TELEGRAM_BOT_TOKEN not set — bot disabled")

    stop_event = asyncio.Event()

    def _handle_signal(*_: object) -> None:
        logger.info("Shutdown signal received")
        stop_event.set()

    loop = asyncio.get_event_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _handle_signal)
        except NotImplementedError:
            # Windows doesn't support add_signal_handler for all signals
            pass

    await stop_event.wait()

    scheduler.shutdown(wait=False)
    from ..scraper.browser import shutdown_browser
    shutdown_browser()

    if app:
        await app.updater.stop()
        await app.stop()
        await app.shutdown()

    logger.info("Worker stopped")


if __name__ == "__main__":
    asyncio.run(run_worker())
