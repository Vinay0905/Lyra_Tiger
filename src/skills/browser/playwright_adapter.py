import asyncio
import os
import tempfile
import time
from typing import Optional

from src.config import settings
from src.skills.browser.engine import PageModel
from src.skills.browser.extractor import extract_page_model
from src.skills.browser.policy import assert_navigable, guarded_execute


class PlaywrightBrowserEngine:
    """
    Owned, lifecycle-managed web engine (L1).

    Two modes:
      - "cdp": attach to the user's real Chrome via the DevTools Protocol
        (seamless integration — Lyra drives the browser you already use).
      - "bundled": launch a Playwright-managed Chromium persistent context.

    The engine lazily initializes, recovers from crashes on next use, and tears
    itself down after an idle window. All navigation is policy-gated.
    """

    def __init__(self):
        self._pw = None
        self._browser = None
        self._context = None
        self._page = None
        self._lock = asyncio.Lock()
        self._last_used = 0.0

    # ── Lifecycle ───────────────────────────────────────────────────────────
    async def _ensure_started(self):
        async with self._lock:
            if self._page is not None and not self._page.is_closed():
                self._last_used = time.time()
                return

            from playwright.async_api import async_playwright

            if self._pw is None:
                self._pw = await async_playwright().start()

            if settings.browser_mode.lower() == "cdp":
                await self._start_cdp()
            else:
                await self._start_bundled()

            self._last_used = time.time()

    async def _start_cdp(self):
        """Attach to the user's Chrome (launched with --remote-debugging-port)."""
        try:
            self._browser = await self._pw.chromium.connect_over_cdp(settings.chrome_cdp_url)
            # Reuse the existing default context so we share the user's session.
            self._context = (
                self._browser.contexts[0]
                if self._browser.contexts
                else await self._browser.new_context()
            )
            pages = self._context.pages
            self._page = pages[0] if pages else await self._context.new_page()
        except Exception as e:
            print(f"[BrowserEngine] CDP attach to {settings.chrome_cdp_url} failed: {e}. "
                  f"Falling back to bundled Chromium.")
            await self._start_bundled()

    async def _start_bundled(self):
        """Launch a Playwright-managed Chromium with an ephemeral profile."""
        user_data_dir = settings.browser_user_data_dir or os.path.join(
            tempfile.gettempdir(), "lyra-chromium-profile"
        )
        self._context = await self._pw.chromium.launch_persistent_context(
            user_data_dir=user_data_dir,
            headless=settings.browser_headless,
            accept_downloads=False,
            args=["--no-first-run", "--no-default-browser-check"],
        )
        self._browser = None  # persistent context owns the browser
        pages = self._context.pages
        self._page = pages[0] if pages else await self._context.new_page()

    async def aclose(self) -> None:
        async with self._lock:
            try:
                if self._context is not None:
                    await self._context.close()
            except Exception:
                pass
            try:
                if self._browser is not None:
                    await self._browser.close()
            except Exception:
                pass
            try:
                if self._pw is not None:
                    await self._pw.stop()
            except Exception:
                pass
            self._pw = self._browser = self._context = self._page = None

    async def _page_or_start(self):
        await self._ensure_started()
        return self._page

    # ── Operations (all policy/budget guarded) ───────────────────────────────
    async def navigate(self, url: str) -> PageModel:
        if not url.startswith("http://") and not url.startswith("https://"):
            url = f"https://{url}"
        assert_navigable(url)

        async def _do():
            page = await self._page_or_start()
            await page.goto(url, timeout=settings.browser_nav_timeout_ms, wait_until="domcontentloaded")
            return await extract_page_model(page)

        return await guarded_execute(_do)

    async def snapshot(self) -> PageModel:
        async def _do():
            page = await self._page_or_start()
            return await extract_page_model(page)

        return await guarded_execute(_do)

    async def click(self, ref: str) -> PageModel:
        async def _do():
            page = await self._page_or_start()
            await page.click(f'[data-lyra-ref="{ref}"]', timeout=settings.browser_nav_timeout_ms)
            await page.wait_for_load_state("domcontentloaded")
            return await extract_page_model(page)

        return await guarded_execute(_do)

    async def fill(self, ref: str, text: str) -> PageModel:
        async def _do():
            page = await self._page_or_start()
            await page.fill(f'[data-lyra-ref="{ref}"]', text, timeout=settings.browser_nav_timeout_ms)
            return await extract_page_model(page)

        return await guarded_execute(_do)

    async def extract(self) -> PageModel:
        return await self.snapshot()

    async def screenshot(self) -> bytes:
        async def _do():
            page = await self._page_or_start()
            return await page.screenshot(type="png")

        return await guarded_execute(_do)


# ── Module singleton ──────────────────────────────────────────────────────────
_engine: Optional[PlaywrightBrowserEngine] = None


def get_browser_engine() -> PlaywrightBrowserEngine:
    global _engine
    if _engine is None:
        _engine = PlaywrightBrowserEngine()
    return _engine
