import logging
import threading
from pathlib import Path
from contextlib import contextmanager
from playwright.sync_api import sync_playwright, BrowserContext
from ..config import settings

logger = logging.getLogger(__name__)

# Thread-local storage: each thread gets its own BrowserManager instance.
# Playwright's sync API uses greenlets that cannot cross thread boundaries,
# so a shared singleton breaks when background tasks run in different threads.
_local = threading.local()


class BrowserManager:
    def __init__(self):
        self._playwright = None
        self._context: BrowserContext | None = None

    def start(self):
        profile_path = Path(settings.playwright_profile_path)
        profile_path.mkdir(parents=True, exist_ok=True)
        self._playwright = sync_playwright().start()
        self._context = self._playwright.chromium.launch_persistent_context(
            user_data_dir=str(profile_path),
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
            ],
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            locale="zh-TW",
            timezone_id="Asia/Taipei",
        )
        logger.info("Browser started (thread %s) with profile: %s", threading.get_ident(), profile_path)

    def stop(self):
        if self._context:
            self._context.close()
        if self._playwright:
            self._playwright.stop()
        self._context = None
        self._playwright = None
        logger.info("Browser stopped (thread %s)", threading.get_ident())

    @contextmanager
    def new_page(self):
        if not self._context:
            raise RuntimeError("BrowserManager not started.")
        page = self._context.new_page()
        try:
            yield page
        finally:
            page.close()


def get_browser_manager() -> BrowserManager:
    """Return this thread's BrowserManager, creating and starting one if needed."""
    mgr = getattr(_local, "manager", None)
    if mgr is None:
        mgr = BrowserManager()
        mgr.start()
        _local.manager = mgr
    return mgr


def shutdown_browser():
    """Stop and discard this thread's BrowserManager."""
    mgr = getattr(_local, "manager", None)
    if mgr:
        mgr.stop()
        _local.manager = None
