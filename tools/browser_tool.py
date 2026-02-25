"""
Playwright browser wrapper as an agent tool.
Handles LinkedIn scraping with stealth mode, randomized delays,
user-agent rotation, pagination, and exponential backoff.
"""

from __future__ import annotations

import asyncio
import random
import time
from typing import List, Optional
from urllib.parse import quote_plus

from fake_useragent import UserAgent
from rich.console import Console
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

console = Console()
ua = UserAgent()


# ─────────────────────────────────────────────
# USER AGENT POOL
# ─────────────────────────────────────────────

DESKTOP_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4_1) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4.1 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36 Edg/123.0.0.0",
]


def get_random_user_agent() -> str:
    try:
        return ua.random
    except Exception:
        return random.choice(DESKTOP_USER_AGENTS)


# ─────────────────────────────────────────────
# STEALTH SCRIPT
# ─────────────────────────────────────────────

STEALTH_JS = """
// Override webdriver property
Object.defineProperty(navigator, 'webdriver', {
    get: () => undefined,
});

// Override plugins length
Object.defineProperty(navigator, 'plugins', {
    get: () => [1, 2, 3, 4, 5],
});

// Override languages
Object.defineProperty(navigator, 'languages', {
    get: () => ['en-US', 'en'],
});

// Mock permissions
const originalQuery = window.navigator.permissions.query;
window.navigator.permissions.query = (parameters) => (
    parameters.name === 'notifications' ?
    Promise.resolve({ state: Notification.permission }) :
    originalQuery(parameters)
);

// Remove headless chrome signal
window.chrome = {
    runtime: {},
    loadTimes: function() {},
    csi: function() {},
    app: {},
};
"""


# ─────────────────────────────────────────────
# SCRAPE RESULT
# ─────────────────────────────────────────────

class ScrapePageResult:
    def __init__(
        self,
        url: str,
        html: str,
        success: bool,
        error: Optional[str] = None,
        captcha: bool = False,
    ):
        self.url = url
        self.html = html
        self.success = success
        self.error = error
        self.captcha = captcha


# ─────────────────────────────────────────────
# LINKEDIN URL BUILDER
# ─────────────────────────────────────────────

def build_linkedin_url(
    keywords: str,
    location: str,
    time_range_seconds: int = 63072000,
    start: int = 0,
) -> str:
    """Build a LinkedIn jobs search URL."""
    base = "https://www.linkedin.com/jobs/search/"
    params = (
        f"?keywords={quote_plus(keywords)}"
        f"&location={quote_plus(location)}"
        f"&f_TPR=r{time_range_seconds}"
        f"&start={start}"
        f"&sortBy=DD"  # Sort by date descending
    )
    return base + params


# ─────────────────────────────────────────────
# BROWSER SESSION
# ─────────────────────────────────────────────

class BrowserSession:
    """Manages a single Playwright browser session with stealth."""

    def __init__(
        self,
        headless: bool = True,
        browser_type: str = "chromium",
        min_delay: float = 2.0,
        max_delay: float = 5.0,
    ):
        self.headless = headless
        self.browser_type = browser_type
        self.min_delay = min_delay
        self.max_delay = max_delay
        self._playwright = None
        self._browser = None
        self._context = None

    async def start(self) -> None:
        from playwright.async_api import async_playwright

        self._playwright = await async_playwright().start()

        launcher = getattr(self._playwright, self.browser_type)
        self._browser = await launcher.launch(
            headless=self.headless,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-infobars",
                "--window-size=1920,1080",
            ],
        )

        user_agent = get_random_user_agent()
        self._context = await self._browser.new_context(
            user_agent=user_agent,
            viewport={"width": 1920, "height": 1080},
            locale="en-US",
            timezone_id="America/New_York",
            extra_http_headers={
                "Accept-Language": "en-US,en;q=0.9",
                "Accept-Encoding": "gzip, deflate, br",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "none",
            },
        )

        # Apply stealth scripts
        await self._context.add_init_script(STEALTH_JS)

        # Try playwright-stealth if available
        try:
            from playwright_stealth import stealth_async
            page = await self._context.new_page()
            await stealth_async(page)
            await page.close()
        except ImportError:
            pass

        console.print("[dim]Browser session started[/dim]")

    async def stop(self) -> None:
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()
        console.print("[dim]Browser session closed[/dim]")

    async def random_delay(self) -> None:
        delay = random.uniform(self.min_delay, self.max_delay)
        await asyncio.sleep(delay)

    async def fetch_page(self, url: str, wait_for: str = ".jobs-search__results-list") -> ScrapePageResult:
        """Fetch a single page with retries and CAPTCHA detection."""
        page = await self._context.new_page()

        try:
            # Randomize user agent per page
            await page.set_extra_http_headers({
                "User-Agent": get_random_user_agent()
            })

            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            await self.random_delay()

            # Scroll to load dynamic content
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight / 3)")
            await asyncio.sleep(1.0)
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight * 2 / 3)")
            await asyncio.sleep(1.0)
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await asyncio.sleep(1.5)

            # Check for CAPTCHA
            html = await page.content()
            if _is_captcha(html):
                console.print(f"[yellow]CAPTCHA detected at {url}[/yellow]")
                return ScrapePageResult(url=url, html="", success=False, captcha=True)

            # Check for rate limiting
            if _is_rate_limited(html):
                console.print(f"[yellow]Rate limited at {url}[/yellow]")
                return ScrapePageResult(
                    url=url, html="", success=False, error="rate_limited"
                )

            return ScrapePageResult(url=url, html=html, success=True)

        except Exception as e:
            console.print(f"[red]Error fetching {url}: {e}[/red]")
            return ScrapePageResult(url=url, html="", success=False, error=str(e))
        finally:
            await page.close()

    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, *args):
        await self.stop()


# ─────────────────────────────────────────────
# DETECTION HELPERS
# ─────────────────────────────────────────────

def _is_captcha(html: str) -> bool:
    captcha_signals = [
        "captcha",
        "CAPTCHA",
        "cf-captcha-container",
        "recaptcha",
        "challenge-form",
        "hCaptcha",
        "Please verify you are a human",
        "bot detection",
    ]
    return any(signal in html for signal in captcha_signals)


def _is_rate_limited(html: str) -> bool:
    rate_signals = [
        "429",
        "Too Many Requests",
        "rate limit",
        "slow down",
        "temporarily blocked",
    ]
    return any(signal.lower() in html.lower() for signal in rate_signals)


# ─────────────────────────────────────────────
# HIGH-LEVEL SCRAPE FUNCTION (with retry)
# ─────────────────────────────────────────────

async def scrape_linkedin_jobs(
    queries: List[dict],
    config: dict,
) -> List[dict]:
    """
    Scrape LinkedIn job listings for given queries.

    Args:
        queries: List of {"keywords": str, "location": str} dicts
        config: Scraper config from config.yaml

    Returns:
        List of {"url", "html", "query", "location", "page"} dicts
    """
    scraper_cfg = config.get("scraper", {})
    headless = scraper_cfg.get("headless", True)
    browser_type = scraper_cfg.get("browser", "chromium")
    min_delay = scraper_cfg.get("min_delay", 2.0)
    max_delay = scraper_cfg.get("max_delay", 5.0)
    max_pages = scraper_cfg.get("max_pages", 5)
    max_retries = scraper_cfg.get("max_retries", 3)
    backoff = scraper_cfg.get("backoff_factor", 2.0)
    time_range = scraper_cfg.get("time_range_seconds", 63072000)
    jobs_per_page = 25  # LinkedIn shows 25 per page

    results = []

    async with BrowserSession(
        headless=headless,
        browser_type=browser_type,
        min_delay=min_delay,
        max_delay=max_delay,
    ) as session:
        for query in queries:
            keywords = query["keywords"]
            location = query["location"]

            console.print(
                f"[cyan]Scraping:[/cyan] [bold]{keywords}[/bold] in [bold]{location}[/bold]"
            )

            captcha_count = 0
            for page_num in range(max_pages):
                start = page_num * jobs_per_page
                url = build_linkedin_url(keywords, location, time_range, start)

                # Retry with exponential backoff
                result = None
                for attempt in range(max_retries):
                    result = await session.fetch_page(url)

                    if result.captcha:
                        captcha_count += 1
                        if captcha_count >= 2:
                            console.print(
                                f"[red]Too many CAPTCHAs for '{keywords}' in '{location}', skipping[/red]"
                            )
                            break
                        wait = backoff ** attempt * 10
                        console.print(f"[yellow]Waiting {wait:.0f}s after CAPTCHA...[/yellow]")
                        await asyncio.sleep(wait)
                        continue

                    if result.success:
                        break

                    if result.error == "rate_limited":
                        wait = backoff ** (attempt + 1) * 5
                        console.print(f"[yellow]Rate limited, backing off {wait:.0f}s[/yellow]")
                        await asyncio.sleep(wait)
                    else:
                        wait = backoff ** attempt * 2
                        await asyncio.sleep(wait)

                if result and result.success and result.html:
                    results.append({
                        "url": url,
                        "html": result.html,
                        "query": keywords,
                        "location": location,
                        "page": page_num + 1,
                    })
                    console.print(
                        f"  [green]✓[/green] Page {page_num + 1} scraped ({len(result.html):,} chars)"
                    )

                    # Check if there are more pages
                    if not _has_next_page(result.html, page_num + 1):
                        console.print(f"  [dim]No more pages for this query[/dim]")
                        break
                else:
                    console.print(f"  [red]✗[/red] Failed page {page_num + 1}, skipping remaining pages")
                    break

                await session.random_delay()

    return results


def _has_next_page(html: str, current_page: int) -> bool:
    """Check if there's a next page of results."""
    if "No matching jobs found" in html:
        return False
    if "no-results" in html.lower():
        return False
    return True
