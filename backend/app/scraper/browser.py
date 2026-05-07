import logging
from pathlib import Path
from contextlib import contextmanager
from playwright.sync_api import sync_playwright, BrowserContext, Page
from ..config import settings

logger = logging.getLogger(__name__)


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
        logger.info("Browser started with profile: %s", profile_path)

    def stop(self):
        if self._context:
            self._context.close()
        if self._playwright:
            self._playwright.stop()
        self._context = None
        self._playwright = None

    @contextmanager
    def new_page(self):
        if not self._context:
            raise RuntimeError("BrowserManager not started. Call start() first.")
        page = self._context.new_page()
        try:
            yield page
        finally:
            page.close()


_browser_manager: BrowserManager | None = None


def get_browser_manager() -> BrowserManager:
    global _browser_manager
    if _browser_manager is None:
        _browser_manager = BrowserManager()
        _browser_manager.start()
    return _browser_manager


def shutdown_browser():
    global _browser_manager
    if _browser_manager:
        _browser_manager.stop()
        _browser_manager = None
