"""
LinkedIn Jobs Research AI Agent — Entry Point

Orchestrates the full multi-agent pipeline:
  1. Scraper Agent  — collects raw HTML from LinkedIn
  2. Parser Agent   — extracts structured job data
  3. Analyst Agent  — computes statistics and insights
  4. Report Agent   — generates Markdown report + charts + exports

Usage:
    uv run python main.py
    uv run python main.py --config config.yaml
    uv run python main.py --mode serpapi
    uv run python main.py --demo   # Run with synthetic demo data (no scraping)
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

import yaml
from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table

console = Console()

# ─────────────────────────────────────────────
# BANNER
# ─────────────────────────────────────────────

BANNER = """
╔══════════════════════════════════════════════════════════════════╗
║          LinkedIn Jobs Research AI Agent                        ║
║          Multi-Agent Pipeline  |  OpenAI Agents SDK             ║
╚══════════════════════════════════════════════════════════════════╝
"""


# ─────────────────────────────────────────────
# CONFIG LOADER
# ─────────────────────────────────────────────

def load_config(config_path: str = "config.yaml") -> Dict[str, Any]:
    config_file = Path(config_path)
    if not config_file.exists():
        # Try relative to script location
        config_file = Path(__file__).parent / config_path

    if not config_file.exists():
        console.print(f"[yellow]Config file '{config_path}' not found, using defaults[/yellow]")
        return _default_config()

    with open(config_file, "r") as f:
        cfg = yaml.safe_load(f)

    console.print(f"[dim]Config loaded from: {config_file}[/dim]")
    return cfg


def _default_config() -> Dict[str, Any]:
    return {
        "data_source": {"mode": "playwright"},
        "scraper": {
            "min_delay": 2.0, "max_delay": 5.0,
            "max_pages": 3, "max_jobs_per_query": 50,
            "max_retries": 3, "backoff_factor": 2.0,
            "headless": True, "browser": "chromium",
            "time_range_seconds": 63072000,
        },
        "search": {
            "roles": ["Software Engineer", "Backend Engineer", "ML Engineer"],
            "locations": [
                {"name": "United States", "code": "us"},
                {"name": "India", "code": "in"},
            ],
        },
        "openai": {"model": "gpt-4o-mini", "analyst_model": "gpt-4o", "temperature": 0.2},
        "output": {
            "directory": "output",
            "report_filename": "linkedin_jobs_report.md",
            "json_filename": "jobs_data.json",
            "csv_filename": "jobs_data.csv",
            "charts_directory": "output/charts",
        },
        "logging": {"level": "INFO", "show_progress": True},
    }


# ─────────────────────────────────────────────
# PRE-FLIGHT CHECKS
# ─────────────────────────────────────────────

def check_environment() -> bool:
    """Verify required environment variables and dependencies."""
    ok = True
    issues = []

    if not os.getenv("OPENAI_API_KEY"):
        issues.append("[yellow]⚠ OPENAI_API_KEY not set — LLM features will be limited[/yellow]")

    try:
        import playwright
    except ImportError:
        issues.append("[red]✗ playwright not installed — run: uv run playwright install chromium[/red]")
        ok = False

    try:
        from agents import Agent
    except ImportError:
        issues.append("[red]✗ openai-agents not installed — run: uv sync[/red]")
        ok = False

    for msg in issues:
        console.print(msg)

    return ok


# ─────────────────────────────────────────────
# DEMO DATA GENERATOR
# ─────────────────────────────────────────────

def generate_demo_data() -> "ParsedJobBatch":
    """Generate synthetic job data for testing the pipeline without scraping."""
    import random
    from datetime import timedelta

    from models.job_schema import (
        EmploymentType,
        ExperienceLevel,
        JobPosting,
        ParsedJobBatch,
        Region,
        RoleCategory,
        WorkType,
    )

    console.print("[cyan]Generating demo data...[/cyan]")

    roles = [
        ("Software Engineer", RoleCategory.SOFTWARE_ENGINEER),
        ("Senior Backend Engineer", RoleCategory.BACKEND),
        ("Frontend Developer", RoleCategory.FRONTEND),
        ("Full Stack Engineer", RoleCategory.FULLSTACK),
        ("ML Engineer", RoleCategory.ML_AI),
        ("Data Engineer", RoleCategory.DATA_ENGINEER),
        ("Data Scientist", RoleCategory.DATA_SCIENTIST),
        ("DevOps Engineer", RoleCategory.DEVOPS),
        ("Engineering Manager", RoleCategory.ENGINEERING_MANAGER),
    ]

    companies_us = [
        "Google", "Meta", "Apple", "Microsoft", "Amazon", "Netflix", "Stripe",
        "Airbnb", "Uber", "Lyft", "Snowflake", "Databricks", "OpenAI", "Anthropic",
        "Cloudflare", "Figma", "Notion", "Vercel", "HashiCorp", "GitHub",
    ]
    companies_india = [
        "Flipkart", "Swiggy", "Zomato", "Paytm", "Infosys", "TCS", "Wipro",
        "HCL", "Razorpay", "Zepto", "Meesho", "Ola", "PhonePe", "CRED",
        "BrowserStack", "Freshworks", "Zoho", "Postman", "HasuraDB", "Chargebee",
    ]

    skills_pool = [
        ["Python", "AWS", "Docker", "Kubernetes", "PostgreSQL"],
        ["React", "TypeScript", "Node.js", "GraphQL", "CSS"],
        ["Go", "Microservices", "gRPC", "Redis", "Kafka"],
        ["PyTorch", "TensorFlow", "Python", "Machine Learning", "MLOps"],
        ["Spark", "Airflow", "dbt", "BigQuery", "SQL"],
        ["Kubernetes", "Terraform", "AWS", "CI/CD", "Linux"],
        ["Java", "Spring Boot", "PostgreSQL", "AWS", "Docker"],
        ["React", "TypeScript", "GraphQL", "AWS", "PostgreSQL"],
        ["Python", "Deep Learning", "NLP", "LLM", "Hugging Face"],
    ]

    work_types = [WorkType.REMOTE, WorkType.HYBRID, WorkType.ONSITE, WorkType.NOT_SPECIFIED]
    work_weights = [0.35, 0.40, 0.20, 0.05]
    exp_levels = [
        ExperienceLevel.ENTRY, ExperienceLevel.MID,
        ExperienceLevel.SENIOR, ExperienceLevel.STAFF,
    ]
    exp_weights = [0.15, 0.35, 0.40, 0.10]

    jobs = []
    now = datetime.utcnow()

    # US jobs (60% of total)
    for i in range(600):
        title, category = random.choice(roles)
        company = random.choice(companies_us)
        skills = random.choice(skills_pool) + random.sample(
            ["Git", "Agile", "REST API", "CI/CD", "Redis", "MongoDB"], 2
        )
        days_ago = random.randint(0, 730)
        work_type = random.choices(work_types, work_weights)[0]
        exp = random.choices(exp_levels, exp_weights)[0]

        jobs.append(JobPosting(
            job_id=f"us_{i:04d}",
            title=f"{'Senior ' if exp == ExperienceLevel.SENIOR else ''}{title}",
            normalized_category=category,
            company_name=company,
            location_raw=random.choice(["San Francisco, CA", "New York, NY", "Seattle, WA",
                                        "Austin, TX", "Remote, United States"]),
            location_city=random.choice(["San Francisco", "New York", "Seattle", "Austin"]),
            location_country="United States",
            region=Region.US,
            work_type=work_type,
            date_posted=now - timedelta(days=days_ago),
            required_skills=list(set(skills)),
            experience_level=exp,
            employment_type=EmploymentType.FULL_TIME,
            search_query=title,
            search_location="United States",
        ))

    # India jobs (40% of total)
    for i in range(400):
        title, category = random.choice(roles)
        company = random.choice(companies_india)
        skills = random.choice(skills_pool) + random.sample(
            ["Java", "Spring", "MySQL", "AWS", "Docker"], 2
        )
        days_ago = random.randint(0, 730)
        work_type = random.choices(work_types, [0.25, 0.45, 0.25, 0.05])[0]
        exp = random.choices(exp_levels, exp_weights)[0]

        jobs.append(JobPosting(
            job_id=f"in_{i:04d}",
            title=f"{'Senior ' if exp == ExperienceLevel.SENIOR else ''}{title}",
            normalized_category=category,
            company_name=company,
            location_raw=random.choice(["Bengaluru, Karnataka, India",
                                         "Hyderabad, Telangana, India",
                                         "Mumbai, Maharashtra, India",
                                         "Pune, Maharashtra, India",
                                         "Delhi NCR, India"]),
            location_city=random.choice(["Bengaluru", "Hyderabad", "Mumbai", "Pune", "Delhi"]),
            location_country="India",
            region=Region.INDIA,
            work_type=work_type,
            date_posted=now - timedelta(days=days_ago),
            required_skills=list(set(skills)),
            experience_level=exp,
            employment_type=EmploymentType.FULL_TIME,
            search_query=title,
            search_location="India",
        ))

    console.print(f"[green]✓[/green] Generated {len(jobs)} demo jobs")
    return ParsedJobBatch(
        jobs=jobs,
        total_parsed=len(jobs),
        total_failed=0,
        duplicate_count=0,
        source_pages=0,
    )


# ─────────────────────────────────────────────
# PIPELINE
# ─────────────────────────────────────────────

async def run_pipeline(config: Dict[str, Any], demo_mode: bool = False) -> None:
    """Execute the full multi-agent pipeline."""
    from pipeline.analyst_agent import run_analyst
    from pipeline.parser_agent import run_parser
    from pipeline.report_agent import run_report
    from pipeline.scraper_agent import run_scraper

    start_time = time.time()
    pipeline_start = datetime.utcnow()

    console.print(Panel(BANNER.strip(), style="bold blue"))
    console.print(f"[dim]Started at {pipeline_start.strftime('%Y-%m-%d %H:%M:%S UTC')}[/dim]\n")

    # ── Step 1: Scrape or Demo
    console.print(Rule("[bold cyan]Step 1: Data Collection[/bold cyan]"))

    if demo_mode:
        console.print("[yellow]Demo mode — skipping scraper, using synthetic data[/yellow]\n")
        parsed_batch = generate_demo_data()
        scraper_result = None
    else:
        try:
            scraper_result = await run_scraper(config)
            console.print(
                f"\n[green]✓ Scraper complete[/green] — "
                f"{scraper_result.total_pages_scraped} pages scraped"
            )
            if scraper_result.captcha_encountered:
                console.print("[yellow]⚠ CAPTCHA was encountered during scraping[/yellow]")
            if scraper_result.failed_queries:
                console.print(f"[yellow]⚠ {len(scraper_result.failed_queries)} queries failed[/yellow]")

            # ── Step 2: Parse
            console.print(Rule("[bold cyan]Step 2: Parsing[/bold cyan]"))
            parsed_batch = run_parser(scraper_result)

        except Exception as e:
            console.print(f"[red]Scraper/Parser failed: {e}[/red]")
            console.print("[yellow]Falling back to demo data...[/yellow]")
            parsed_batch = generate_demo_data()

    # Validate we have data
    if not parsed_batch.jobs:
        console.print("[red]No job data available. Check scraper settings or use --demo.[/red]")
        sys.exit(1)

    console.print(
        f"\n[bold green]Jobs ready:[/bold green] {parsed_batch.total_parsed:,} unique postings\n"
    )

    # ── Step 3: Analyze
    console.print(Rule("[bold cyan]Step 3: Analysis[/bold cyan]"))
    analysis = run_analyst(parsed_batch, config)

    # ── Step 4: Report
    console.print(Rule("[bold cyan]Step 4: Report Generation[/bold cyan]"))
    report = run_report(parsed_batch, analysis, config)

    # ── Summary
    elapsed = time.time() - start_time
    console.print(f"\n{Rule('[bold green]Pipeline Complete[/bold green]')}")

    summary_table = Table(title="Output Files", show_header=True, header_style="bold cyan")
    summary_table.add_column("File", style="dim")
    summary_table.add_column("Path", style="green")

    summary_table.add_row("Markdown Report", report.report_path)
    summary_table.add_row("JSON Data", report.json_path)
    summary_table.add_row("CSV Data", report.csv_path)
    for chart in report.charts_generated:
        summary_table.add_row("Chart", chart)

    console.print(summary_table)

    stats_table = Table(title="Run Statistics", show_header=True, header_style="bold cyan")
    stats_table.add_column("Metric", style="dim")
    stats_table.add_column("Value", style="bold")

    stats_table.add_row("Total Jobs Analyzed", f"{parsed_batch.total_parsed:,}")
    stats_table.add_row("US Jobs", f"{analysis.us_jobs:,}")
    stats_table.add_row("India Jobs", f"{analysis.india_jobs:,}")
    stats_table.add_row("Role Categories", str(len(analysis.role_stats)))
    stats_table.add_row("Top Skills Identified", str(len(analysis.top_skills)))
    stats_table.add_row("Charts Generated", str(len(report.charts_generated)))
    stats_table.add_row("Elapsed", f"{elapsed:.1f}s")

    console.print(stats_table)

    if report.success:
        console.print(f"\n[bold green]✓ Report saved to:[/bold green] {report.report_path}")
    else:
        console.print(f"\n[red]Report generation had errors: {report.error_message}[/red]")


# ─────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="LinkedIn Jobs Research AI Agent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  uv run python main.py
  uv run python main.py --demo
  uv run python main.py --config config.yaml --mode serpapi
  uv run python main.py --demo --output output/custom_report.md
        """,
    )
    parser.add_argument(
        "--config", default="config.yaml",
        help="Path to config.yaml (default: config.yaml)"
    )
    parser.add_argument(
        "--mode", choices=["playwright", "serpapi"],
        help="Override data source mode from config"
    )
    parser.add_argument(
        "--demo", action="store_true",
        help="Run with synthetic demo data (no scraping required)"
    )
    parser.add_argument(
        "--output", default=None,
        help="Override output directory"
    )
    parser.add_argument(
        "--headless", action="store_true", default=None,
        help="Run browser in headless mode (default from config)"
    )
    parser.add_argument(
        "--max-pages", type=int, default=None,
        help="Override max pages per query"
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    # Load config
    config = load_config(args.config)

    # Apply CLI overrides
    if args.mode:
        config.setdefault("data_source", {})["mode"] = args.mode

    if args.output:
        config.setdefault("output", {})["directory"] = args.output
        config["output"]["charts_directory"] = os.path.join(args.output, "charts")

    if args.headless is not None:
        config.setdefault("scraper", {})["headless"] = args.headless

    if args.max_pages is not None:
        config.setdefault("scraper", {})["max_pages"] = args.max_pages

    # Environment check
    if not args.demo:
        check_environment()

    # Run pipeline
    try:
        asyncio.run(run_pipeline(config, demo_mode=args.demo))
    except KeyboardInterrupt:
        console.print("\n[yellow]Pipeline interrupted by user[/yellow]")
        sys.exit(0)
    except Exception as e:
        console.print(f"\n[red]Pipeline failed: {e}[/red]")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
