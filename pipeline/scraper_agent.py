"""
Scraper Agent — collects raw job postings from LinkedIn or SerpAPI.
Uses Playwright for browser automation with stealth and anti-bot measures.
"""

from __future__ import annotations

import asyncio
import os
from typing import Any, Dict, List

from agents import Agent, function_tool
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn

from models.job_schema import RawJobPage, ScraperResult

console = Console()

# Marker prefix so the parser knows this page contains raw SerpAPI JSON
SERPAPI_MARKER = "SERPAPI_JSON::"


# ─────────────────────────────────────────────
# TOOLS
# ─────────────────────────────────────────────

@function_tool
def scrape_linkedin_pages(
    queries_json: str,
    config_json: str,
) -> str:
    """
    Scrape LinkedIn job search result pages using Playwright.

    Args:
        queries_json: JSON list of {"keywords": str, "location": str} dicts
        config_json:  JSON scraper config

    Returns:
        JSON string with ScraperResult data
    """
    import json

    queries = json.loads(queries_json)
    config = json.loads(config_json)

    try:
        loop = asyncio.new_event_loop()
        result = loop.run_until_complete(_run_playwright_scraper(queries, config))
        loop.close()
        return result.model_dump_json()
    except Exception as e:
        console.print(f"[red]Playwright scraper failed: {e}[/red]")
        return ScraperResult(
            source="playwright",
            failed_queries=[q.get("keywords", "") for q in queries],
        ).model_dump_json()


@function_tool
def scrape_via_serpapi(
    queries_json: str,
    serpapi_key: str,
) -> str:
    """
    Scraper using SerpAPI Google Jobs engine.

    Args:
        queries_json: JSON list of {"keywords": str, "location": str} dicts
        serpapi_key:  SerpAPI API key

    Returns:
        JSON string with ScraperResult data
    """
    import json

    queries = json.loads(queries_json)

    try:
        result = _run_serpapi_scraper(queries, serpapi_key)
        return result.model_dump_json()
    except Exception as e:
        console.print(f"[red]SerpAPI scraper failed: {e}[/red]")
        return ScraperResult(source="serpapi").model_dump_json()


# ─────────────────────────────────────────────
# PLAYWRIGHT IMPLEMENTATION
# ─────────────────────────────────────────────

async def _run_playwright_scraper(
    queries: List[Dict[str, str]],
    config: Dict[str, Any],
) -> ScraperResult:
    from tools.browser_tool import BrowserSession, build_linkedin_url

    pages: List[RawJobPage] = []
    failed_queries: List[str] = []
    captcha_encountered = False

    headless    = config.get("headless", True)
    browser_type = config.get("browser", "chromium")
    min_delay   = config.get("min_delay", 2.0)
    max_delay   = config.get("max_delay", 5.0)
    max_pages   = config.get("max_pages", 5)
    max_retries = config.get("max_retries", 3)
    backoff     = config.get("backoff_factor", 2.0)
    time_range  = config.get("time_range_seconds", 63072000)
    jobs_per_page = 25

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("[cyan]Scraping LinkedIn...", total=len(queries) * max_pages)

        async with BrowserSession(
            headless=headless,
            browser_type=browser_type,
            min_delay=min_delay,
            max_delay=max_delay,
        ) as session:
            for query in queries:
                keywords    = query["keywords"]
                location    = query["location"]
                query_failed = False
                captcha_count = 0

                for page_num in range(max_pages):
                    start = page_num * jobs_per_page
                    url   = build_linkedin_url(keywords, location, time_range, start)

                    result = None
                    for attempt in range(max_retries):
                        result = await session.fetch_page(url)

                        if result.captcha:
                            captcha_encountered = True
                            captcha_count += 1
                            console.print(
                                f"[yellow]  CAPTCHA (attempt {attempt+1}) for '{keywords}' / '{location}'[/yellow]"
                            )
                            if captcha_count >= 2:
                                console.print(f"[red]  Skipping due to repeated CAPTCHAs[/red]")
                                query_failed = True
                                break
                            await asyncio.sleep(backoff ** attempt * 15)
                            continue

                        if result.success:
                            break

                        wait = backoff ** attempt * 3
                        console.print(f"[dim]  Retry {attempt+1}/{max_retries}, waiting {wait:.1f}s...[/dim]")
                        await asyncio.sleep(wait)

                    if query_failed:
                        failed_queries.append(f"{keywords}|{location}")
                        break

                    if result and result.success and result.html:
                        pages.append(RawJobPage(
                            url=url, html=result.html,
                            query=keywords, location=location,
                            page_number=page_num + 1, success=True,
                        ))
                        progress.update(task, advance=1)
                        console.print(f"  [green]✓[/green] {keywords} / {location} — page {page_num+1}")
                    else:
                        pages.append(RawJobPage(
                            url=url, html="",
                            query=keywords, location=location,
                            page_number=page_num + 1, success=False,
                            error_message=result.error if result else "Unknown error",
                        ))
                        progress.update(task, advance=1)
                        break

                    await session.random_delay()

    return ScraperResult(
        pages=pages,
        total_pages_scraped=sum(1 for p in pages if p.success),
        total_queries_run=len(queries),
        failed_queries=failed_queries,
        captcha_encountered=captcha_encountered,
        source="playwright",
    )


# ─────────────────────────────────────────────
# SERPAPI IMPLEMENTATION  (fixed)
# ─────────────────────────────────────────────

# Placeholder values that mean "no real key was set"
_PLACEHOLDER_KEYS = {
    "", "PASTE_YOUR_SERPAPI_KEY_HERE", "your_key_here",
    "YOUR_API_KEY", "serpapi_key", "xxxx",
}


def _run_serpapi_scraper(
    queries: List[Dict[str, str]],
    api_key: str,
    max_pages_per_query: int = 1,
) -> ScraperResult:
    """
    Fetch jobs via SerpAPI Google Jobs engine with full pagination.

    Each SerpAPI call returns ~10 jobs.
    max_pages_per_query=5 → up to 50 jobs per query.
    26 queries × 5 pages = 130 API credits → ~1,000 unique jobs.

    Pagination uses SerpAPI's next_page_token (most reliable method).
    Falls back to `start` offset if token is absent.
    """
    import json
    import time

    # ── Validate API key ──────────────────────────────────────────────
    key = (api_key or "").strip()
    if key in _PLACEHOLDER_KEYS:
        console.print(
            "[red bold]✗ SerpAPI key not set![/red bold]\n"
            "  Open [cyan]config.yaml[/cyan] and replace "
            "[yellow]PASTE_YOUR_SERPAPI_KEY_HERE[/yellow] with your real key.\n"
            "  Get one free at [link=https://serpapi.com]serpapi.com[/link]"
        )
        return ScraperResult(source="serpapi")

    try:
        from serpapi import GoogleSearch
    except ImportError:
        console.print("[red]google-search-results not installed. Run: uv sync[/red]")
        return ScraperResult(source="serpapi")

    pages: List[RawJobPage] = []
    failed: List[str] = []
    total_credits_used = 0

    console.print(
        f"  [dim]Plan: {len(queries)} queries × {max_pages_per_query} pages "
        f"= up to {len(queries) * max_pages_per_query} API credits[/dim]"
    )

    for query in queries:
        keywords = query["keywords"]
        location = query["location"]
        query_jobs: List[dict] = []

        # ── Base params (same for every page of this query) ──────────
        base_params = {
            "engine":        "google_jobs",
            "q":             keywords,
            "location":      location,
            "api_key":       key,
            "hl":            "en",
            "chips":         "date_posted:month",
        }

        next_page_token: str = ""
        page_num = 0

        while page_num < max_pages_per_query:
            try:
                params = dict(base_params)

                # ── Pagination ────────────────────────────────────────
                if page_num == 0:
                    pass                                      # first page: no extra param
                elif next_page_token:
                    params["next_page_token"] = next_page_token   # preferred
                else:
                    params["start"] = page_num * 10               # fallback offset

                results = GoogleSearch(params).get_dict()
                total_credits_used += 1

                # ── Handle API-level errors ───────────────────────────
                if "error" in results:
                    err = str(results["error"])
                    if page_num == 0:
                        # Only mark as failed if even page 1 errored
                        console.print(f"  [red]✗[/red] {keywords}/{location} — {err}")
                        if "Invalid API key" in err:
                            console.print("    [yellow]→ Check key: https://serpapi.com/manage-api-key[/yellow]")
                        failed.append(f"{keywords}|{location}")
                    break   # stop paginating this query

                batch = results.get("jobs_results", []) or []
                query_jobs.extend(batch)

                # ── Check for next page ───────────────────────────────
                pagination     = results.get("serpapi_pagination", {}) or {}
                next_page_token = pagination.get("next_page_token", "")

                if not batch:
                    break                    # no results on this page → stop
                if len(batch) < 10 and not next_page_token:
                    break                    # partial page + no token → last page

                page_num += 1
                time.sleep(0.4)             # be polite between pages

            except Exception as e:
                console.print(f"  [red]✗[/red] Page {page_num+1} exception: {e}")
                break

        if query_jobs:
            raw_payload = SERPAPI_MARKER + json.dumps(query_jobs)
            pages.append(RawJobPage(
                url=f"serpapi://google_jobs/{keywords}@{location}",
                html=raw_payload,
                query=keywords,
                location=location,
                page_number=page_num + 1,
                success=True,
            ))
            console.print(
                f"  [green]✓[/green] [bold]{keywords}[/bold] / [bold]{location}[/bold]"
                f" — {len(query_jobs)} jobs ({page_num+1} page{'s' if page_num else ''})"
            )
        elif f"{keywords}|{location}" not in failed:
            console.print(
                f"  [yellow]⚠[/yellow]  0 results: [dim]{keywords} / {location}[/dim]"
            )

        time.sleep(0.3)   # brief pause between queries

    console.print(f"\n  [dim]Total SerpAPI credits used: {total_credits_used}[/dim]")

    return ScraperResult(
        pages=pages,
        total_pages_scraped=len(pages),
        total_queries_run=len(queries),
        failed_queries=failed,
        source="serpapi",
    )


# ─────────────────────────────────────────────
# AGENT DEFINITION
# ─────────────────────────────────────────────

def create_scraper_agent(config: Dict[str, Any]) -> Agent:
    """Create and return the Scraper Agent."""
    data_source = config.get("data_source", {})
    mode        = data_source.get("mode", "playwright")
    serpapi_key = (
        data_source.get("serpapi", {}).get("api_key")
        or os.getenv("SERPAPI_API_KEY", "")
    )

    tools = [scrape_linkedin_pages]
    if mode == "serpapi" or serpapi_key:
        tools.append(scrape_via_serpapi)

    return Agent(
        name="ScraperAgent",
        model=config.get("openai", {}).get("model", "gpt-4o-mini"),
        instructions=f"""
You are the LinkedIn Jobs Scraper Agent. Mode: {mode.upper()}.
Use the appropriate tool to collect job listings, then return the ScraperResult JSON.
Do NOT log in to LinkedIn. Only public pages.
""",
        tools=tools,
        output_type=ScraperResult,
    )


# ─────────────────────────────────────────────
# KEY RESOLVER  (env var beats placeholder in config)
# ─────────────────────────────────────────────

def _resolve_serpapi_key(config_key: str, env_key: str) -> str:
    """
    Return the best available SerpAPI key using this priority:
      1. SERPAPI_API_KEY environment variable  (if set and not placeholder)
      2. api_key field in config.yaml          (if set and not placeholder)
      3. Empty string → _run_serpapi_scraper will show a clear error
    """
    env  = (env_key    or "").strip()
    cfg  = (config_key or "").strip()

    if env and env not in _PLACEHOLDER_KEYS:
        return env      # ← env var wins
    if cfg and cfg not in _PLACEHOLDER_KEYS:
        return cfg      # ← config.yaml value
    return ""           # ← neither is set; let scraper show the error


# ─────────────────────────────────────────────
# STANDALONE RUNNER (called by main.py)
# ─────────────────────────────────────────────

async def run_scraper(config: Dict[str, Any]) -> ScraperResult:
    """Build queries from config and run the appropriate scraper."""
    search_cfg  = config.get("search", {})
    scraper_cfg = config.get("scraper", {})
    data_source = config.get("data_source", {})
    mode        = data_source.get("mode", "playwright")

    roles     = search_cfg.get("roles", [])
    locations = search_cfg.get("locations", [])

    queries = [
        {
            "keywords": role,
            "location": loc.get("name", loc) if isinstance(loc, dict) else loc,
        }
        for role in roles
        for loc in locations
    ]

    console.print(
        f"\n[bold cyan]Scraper Agent[/bold cyan] — "
        f"{len(queries)} queries, mode: [bold]{mode}[/bold]\n"
    )

    if mode == "serpapi":
        serpapi_key = _resolve_serpapi_key(
            config_key=data_source.get("serpapi", {}).get("api_key", ""),
            env_key=os.getenv("SERPAPI_API_KEY", ""),
        )
        max_pages_per_query = data_source.get("serpapi", {}).get(
            "pages_per_query",
            scraper_cfg.get("max_pages", 1),   # fallback to scraper.max_pages
        )
        return _run_serpapi_scraper(queries, serpapi_key, max_pages_per_query)

    # Default: Playwright
    return await _run_playwright_scraper(queries, scraper_cfg)
