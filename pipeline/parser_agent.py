"""
Parser Agent — extracts structured data from raw HTML pages.
Converts RawJobPage objects into JobPosting Pydantic models.
"""

from __future__ import annotations

from typing import Any, Dict, List

from agents import Agent, function_tool
from rich.console import Console

from models.job_schema import ParsedJobBatch, RawJobPage, ScraperResult

console = Console()


# ─────────────────────────────────────────────
# TOOLS
# ─────────────────────────────────────────────

@function_tool
def parse_job_pages(scraper_result_json: str) -> str:
    """
    Parse raw HTML pages from the ScraperResult into structured JobPosting objects.

    Args:
        scraper_result_json: JSON string of a ScraperResult object

    Returns:
        JSON string of a ParsedJobBatch object
    """
    from tools.parser_tool import deduplicate_jobs, extract_skills, parse_linkedin_job_cards

    scraper_result = ScraperResult.model_validate_json(scraper_result_json)
    all_jobs = []
    total_failed = 0

    console.print(
        f"\n[bold cyan]Parser Agent[/bold cyan] — processing {len(scraper_result.pages)} pages"
    )

    for page in scraper_result.pages:
        if not page.success or not page.html:
            total_failed += 1
            continue

        try:
            jobs = parse_linkedin_job_cards(page.html, page.query, page.location)

            # Enrich with skills from description if available
            for job in jobs:
                if job.job_description and not job.required_skills:
                    job.required_skills = extract_skills(job.job_description)
                elif not job.required_skills:
                    # Extract skills from title as fallback
                    job.required_skills = extract_skills(job.title)

            all_jobs.extend(jobs)
            console.print(
                f"  [green]✓[/green] {page.query} / {page.location} "
                f"page {page.page_number} → {len(jobs)} jobs"
            )
        except Exception as e:
            console.print(f"  [red]✗[/red] Parse error: {e}")
            total_failed += 1

    # Deduplicate
    unique_jobs, dupe_count = deduplicate_jobs(all_jobs)

    console.print(
        f"\n  Total parsed: [bold]{len(unique_jobs)}[/bold] unique jobs "
        f"([dim]{dupe_count} duplicates removed[/dim])"
    )

    batch = ParsedJobBatch(
        jobs=unique_jobs,
        total_parsed=len(unique_jobs),
        total_failed=total_failed,
        duplicate_count=dupe_count,
        source_pages=len(scraper_result.pages),
    )
    return batch.model_dump_json()


@function_tool
def enrich_jobs_with_skills(parsed_batch_json: str) -> str:
    """
    Re-scan all job descriptions to extract missing skills.

    Args:
        parsed_batch_json: JSON string of ParsedJobBatch

    Returns:
        Updated JSON string of ParsedJobBatch with enriched skills
    """
    from tools.parser_tool import extract_skills

    batch = ParsedJobBatch.model_validate_json(parsed_batch_json)
    enriched = 0

    for job in batch.jobs:
        if not job.required_skills:
            text = " ".join(filter(None, [job.title, job.job_description or ""]))
            skills = extract_skills(text)
            if skills:
                job.required_skills = skills
                enriched += 1

    console.print(f"  Enriched [bold]{enriched}[/bold] jobs with extracted skills")
    return batch.model_dump_json()


# ─────────────────────────────────────────────
# AGENT DEFINITION
# ─────────────────────────────────────────────

def create_parser_agent(config: Dict[str, Any]) -> Agent:
    """Create and return the Parser Agent."""
    return Agent(
        name="ParserAgent",
        model=config.get("openai", {}).get("model", "gpt-4o-mini"),
        instructions="""
You are the LinkedIn Jobs Parser Agent.

Your job is to extract structured job data from raw HTML pages collected by the Scraper Agent.

Process:
1. Call parse_job_pages with the ScraperResult JSON to extract all jobs
2. Call enrich_jobs_with_skills to fill in any missing skills
3. Return the ParsedJobBatch JSON

Each job should have:
- title (raw job title)
- normalized_category (classified role type)
- company_name
- location details (city, country, region)
- work_type (Remote/Hybrid/Onsite)
- experience_level
- employment_type
- required_skills (list of tech skills)
- date_posted

Be thorough and extract as many valid jobs as possible.
""",
        tools=[parse_job_pages, enrich_jobs_with_skills],
        output_type=ParsedJobBatch,
    )


# ─────────────────────────────────────────────
# STANDALONE RUNNER
# ─────────────────────────────────────────────

def run_parser(scraper_result: ScraperResult) -> ParsedJobBatch:
    """
    Run the parser pipeline synchronously.
    Automatically routes each page to the correct parser:
      - Pages starting with SERPAPI_JSON:: → parse_serpapi_json()
      - All other pages                    → parse_linkedin_job_cards()
    """
    from pipeline.scraper_agent import SERPAPI_MARKER
    from tools.parser_tool import (
        deduplicate_jobs,
        extract_skills,
        parse_linkedin_job_cards,
        parse_serpapi_json,
    )

    all_jobs = []
    total_failed = 0

    console.print(
        f"\n[bold cyan]Parser Agent[/bold cyan] — processing {len(scraper_result.pages)} pages "
        f"(source: {scraper_result.source})"
    )

    for page in scraper_result.pages:
        if not page.success or not page.html:
            total_failed += 1
            continue

        try:
            # ── Route to the correct parser ──────────────────────────
            if page.html.startswith(SERPAPI_MARKER):
                raw_json = page.html[len(SERPAPI_MARKER):]
                jobs = parse_serpapi_json(raw_json, page.query, page.location)
            else:
                jobs = parse_linkedin_job_cards(page.html, page.query, page.location)

            # Enrich skills
            for job in jobs:
                text = " ".join(filter(None, [job.title, job.job_description or ""]))
                if not job.required_skills:
                    job.required_skills = extract_skills(text)

            all_jobs.extend(jobs)
            console.print(
                f"  [green]✓[/green] {page.query} / {page.location} "
                f"pg {page.page_number} → {len(jobs)} jobs parsed"
            )
        except Exception as e:
            console.print(f"  [red]✗[/red] Parse error on page: {e}")
            total_failed += 1

    unique_jobs, dupe_count = deduplicate_jobs(all_jobs)

    console.print(
        f"\n  Total: [bold]{len(unique_jobs)}[/bold] unique | "
        f"{dupe_count} dupes removed | {total_failed} pages failed"
    )

    return ParsedJobBatch(
        jobs=unique_jobs,
        total_parsed=len(unique_jobs),
        total_failed=total_failed,
        duplicate_count=dupe_count,
        source_pages=len(scraper_result.pages),
    )
