import asyncio
import logging
import signal
import threading
from ..config import settings
from .scheduler import setup_scheduler
from .bot import setup_bot

logging.basicConfig(
    level=settings.log_level,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)


def _start_log_queue_drainer() -> None:
    """Drain the subprocess log queue in the worker process.

    Scan subprocesses write logs to a multiprocessing.Queue via QueueHandler.
    In the API process the queue is drained by the /api/logs endpoint.
    In the worker process nobody reads it, so the pipe buffer fills up (~65 KB),
    the subprocess's feeder thread blocks, the subprocess hangs on exit, and
    p.join() in the watcher thread waits forever — silently stopping all alerts.

    This drainer thread continuously empties the queue so subprocesses can exit
    cleanly, and re-emits the log records to the worker's own logging handlers
    so scan logs appear in docker logs.
    """
    from ..api.logs import get_log_queue
    q = get_log_queue()

    def _drain():
        while True:
            try:
                record = q.get(timeout=1)
                logging.getLogger(record.name).handle(record)
            except Exception:
                pass  # queue.Empty on timeout — keep looping

    t = threading.Thread(target=_drain, daemon=True, name="log-queue-drainer")
    t.start()
    logger.info("Log queue drainer started")


async def run_worker() -> None:
    logger.info("Starting worker...")

    _start_log_queue_drainer()

    scheduler = setup_scheduler()
    scheduler.start()
    logger.info("Scheduler started with %d jobs", len(scheduler.get_jobs()))

    app = None
    if settings.telegram_bot_token and settings.telegram_polling:
        from telegram.ext import Application
        app = Application.builder().token(settings.telegram_bot_token).build()
        setup_bot(app)
        await app.initialize()
        await app.start()
        await app.updater.start_polling(drop_pending_updates=True)
        logger.info("Telegram bot started")
    elif settings.telegram_bot_token:
        logger.info("Telegram bot polling disabled (TELEGRAM_POLLING=false) — alerts only")
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

    if app and settings.telegram_polling:
        await app.updater.stop()
        await app.stop()
        await app.shutdown()

    logger.info("Worker stopped")


if __name__ == "__main__":
    asyncio.run(run_worker())
