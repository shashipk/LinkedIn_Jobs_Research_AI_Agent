"""
HTML parsing utilities for extracting structured job data from LinkedIn pages.
Uses BeautifulSoup with lxml for fast, reliable parsing.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag
from dateutil.parser import parse as parse_date
from rich.console import Console

from models.job_schema import (
    EmploymentType,
    ExperienceLevel,
    JobPosting,
    Region,
    RoleCategory,
    WorkType,
)

console = Console()

# ─────────────────────────────────────────────
# SKILL TAXONOMY
# ─────────────────────────────────────────────

SKILL_KEYWORDS = {
    # Languages
    "Python", "JavaScript", "TypeScript", "Java", "Go", "Golang", "Rust", "C++", "C#",
    "Scala", "Kotlin", "Swift", "Ruby", "PHP", "R", "MATLAB", "Bash", "Shell",
    # Frontend
    "React", "React.js", "Next.js", "Vue", "Vue.js", "Angular", "Svelte",
    "HTML", "CSS", "Tailwind", "SASS", "Redux", "GraphQL", "REST API",
    "WebSockets", "Webpack", "Vite",
    # Backend
    "Node.js", "Django", "FastAPI", "Flask", "Spring Boot", "Express", "Rails",
    "NestJS", "gRPC", "Microservices", "REST", "API Design",
    # Databases
    "PostgreSQL", "MySQL", "MongoDB", "Redis", "Elasticsearch", "Cassandra",
    "DynamoDB", "SQLite", "Oracle", "SQL Server", "BigQuery", "Snowflake",
    "Redshift", "ClickHouse", "Kafka", "RabbitMQ",
    # Cloud & DevOps
    "AWS", "GCP", "Azure", "Docker", "Kubernetes", "Terraform", "Ansible",
    "CI/CD", "Jenkins", "GitHub Actions", "ArgoCD", "Helm", "Linux",
    "CloudFormation", "Pulumi", "Prometheus", "Grafana", "Datadog", "PagerDuty",
    # ML/AI
    "Machine Learning", "Deep Learning", "TensorFlow", "PyTorch", "Keras",
    "scikit-learn", "NLP", "Computer Vision", "LLM", "Transformers",
    "Hugging Face", "OpenAI", "BERT", "GPT", "RAG", "MLOps", "Feature Engineering",
    "Spark", "Hadoop", "Airflow", "dbt", "Pandas", "NumPy",
    # Architecture
    "Distributed Systems", "System Design", "Event-Driven Architecture",
    "Domain-Driven Design", "SOLID", "Design Patterns", "SOA", "Serverless",
    # Practices
    "Agile", "Scrum", "TDD", "BDD", "Code Review", "Open Source",
    # Tools
    "Git", "JIRA", "Confluence", "Figma",
}

SKILL_PATTERNS = {s.lower(): s for s in SKILL_KEYWORDS}

# ─────────────────────────────────────────────
# ROLE CATEGORY MAPPING
# ─────────────────────────────────────────────

ROLE_CATEGORY_KEYWORDS: Dict[RoleCategory, List[str]] = {
    RoleCategory.ML_AI: [
        "machine learning", "ml engineer", "ai engineer", "deep learning",
        "data science", "nlp engineer", "computer vision", "mlops",
        "research scientist", "applied scientist", "llm", "generative ai",
    ],
    RoleCategory.DATA_ENGINEER: [
        "data engineer", "etl", "data pipeline", "data platform",
        "analytics engineer", "big data",
    ],
    RoleCategory.DATA_SCIENTIST: [
        "data scientist", "analyst", "business intelligence",
        "quantitative analyst", "statistician",
    ],
    RoleCategory.DEVOPS: [
        "devops", "platform engineer", "sre", "site reliability",
        "infrastructure engineer", "cloud engineer", "devsecops",
        "release engineer", "build engineer",
    ],
    RoleCategory.FRONTEND: [
        "frontend", "front-end", "front end", "ui engineer",
        "react developer", "angular developer", "vue developer",
        "web developer", "ui/ux engineer",
    ],
    RoleCategory.BACKEND: [
        "backend", "back-end", "back end", "api engineer",
        "server-side", "java developer", "python developer",
        "golang engineer", "microservices engineer",
    ],
    RoleCategory.FULLSTACK: [
        "full stack", "fullstack", "full-stack",
        "full stack developer", "full stack engineer",
    ],
    RoleCategory.ENGINEERING_MANAGER: [
        "engineering manager", "tech lead", "technical lead",
        "team lead", "staff engineer", "principal engineer",
        "vp of engineering", "director of engineering", "head of engineering",
    ],
    RoleCategory.SOFTWARE_ENGINEER: [
        "software engineer", "software developer", "swe",
        "software development engineer", "sde",
    ],
}

# ─────────────────────────────────────────────
# EXPERIENCE LEVEL MAPPING
# ─────────────────────────────────────────────

EXPERIENCE_KEYWORDS: Dict[ExperienceLevel, List[str]] = {
    ExperienceLevel.ENTRY: [
        "junior", "entry", "entry-level", "associate", "new grad",
        "0-2 years", "1+ year", "fresher", "intern",
    ],
    ExperienceLevel.MID: [
        "mid", "mid-level", "intermediate", "2+ years", "3+ years",
        "2-5 years", "3-5 years",
    ],
    ExperienceLevel.SENIOR: [
        "senior", "sr.", "sr ", "5+ years", "6+ years", "7+ years",
        "5-8 years", "experienced",
    ],
    ExperienceLevel.STAFF: [
        "staff engineer", "staff software", "staff level",
        "8+ years", "9+ years", "10+ years",
    ],
    ExperienceLevel.PRINCIPAL: [
        "principal", "distinguished", "fellow",
        "10+ years", "12+ years", "15+ years",
    ],
    ExperienceLevel.MANAGER: [
        "manager", "director", "vp", "head of", "lead",
    ],
}

# ─────────────────────────────────────────────
# REGION MAPPING
# ─────────────────────────────────────────────

US_SIGNALS = {"united states", "usa", "u.s.", "u.s.a", "us", "california", "new york",
              "texas", "washington", "seattle", "san francisco", "new york city",
              "chicago", "boston", "austin", "remote us"}

INDIA_SIGNALS = {"india", "bengaluru", "bangalore", "mumbai", "hyderabad",
                 "chennai", "pune", "delhi", "ncr", "noida", "gurgaon",
                 "gurugram", "kolkata", "ahmedabad", "remote india"}


# ─────────────────────────────────────────────
# LINKEDIN HTML PARSERS
# ─────────────────────────────────────────────

def parse_linkedin_job_cards(html: str, query: str, location: str) -> List[JobPosting]:
    """
    Parse LinkedIn job search results page HTML into JobPosting objects.
    Handles both the public listing page format.
    """
    soup = BeautifulSoup(html, "lxml")
    jobs = []

    # LinkedIn public jobs list selectors (may vary over time)
    card_selectors = [
        "li.jobs-search__results-list > .job-search-card",      # older
        "ul.jobs-search__results-list li",                        # alt
        ".base-card",                                              # generic base card
        "li[data-occludable-job-id]",                             # newer format
        ".job-search-card",
    ]

    cards: List[Tag] = []
    for selector in card_selectors:
        cards = soup.select(selector)
        if cards:
            break

    if not cards:
        # Fallback: look for JSON-LD structured data
        jobs_from_schema = _parse_json_ld(soup, query, location)
        if jobs_from_schema:
            return jobs_from_schema

        console.print(f"[yellow]  No job cards found for '{query}' in '{location}'[/yellow]")
        return []

    for card in cards:
        try:
            job = _parse_job_card(card, query, location)
            if job:
                jobs.append(job)
        except Exception as e:
            console.print(f"[dim]  Card parse error: {e}[/dim]")
            continue

    return jobs


def _parse_job_card(card: Tag, query: str, location: str) -> Optional[JobPosting]:
    """Parse a single job card Tag into a JobPosting."""

    # Job ID
    job_id = (
        card.get("data-job-id")
        or card.get("data-occludable-job-id")
        or card.get("data-entity-urn", "").split(":")[-1]
    )

    # Title
    title_tag = (
        card.select_one("h3.base-search-card__title")
        or card.select_one(".job-search-card__title")
        or card.select_one("h3")
        or card.select_one("[class*='title']")
    )
    title = _clean_text(title_tag.get_text() if title_tag else "")
    if not title:
        return None

    # Company
    company_tag = (
        card.select_one("h4.base-search-card__subtitle")
        or card.select_one("a[data-tracking-control-name='public_jobs_jserp-result_job-search-card-subtitle']")
        or card.select_one(".job-search-card__company-name")
        or card.select_one("h4")
    )
    company = _clean_text(company_tag.get_text() if company_tag else "Unknown Company")

    # Location
    location_tag = (
        card.select_one(".job-search-card__location")
        or card.select_one("span.job-result-card__location")
        or card.select_one("[class*='location']")
    )
    location_raw = _clean_text(location_tag.get_text() if location_tag else location)

    # Date
    date_tag = (
        card.select_one("time")
        or card.select_one("[class*='date']")
        or card.select_one("[class*='time']")
    )
    date_posted_raw = None
    date_posted = None
    if date_tag:
        date_posted_raw = date_tag.get("datetime") or _clean_text(date_tag.get_text())
        date_posted = _parse_relative_date(date_posted_raw)

    # URL
    link_tag = card.select_one("a[href*='/jobs/view/']") or card.select_one("a[href]")
    source_url = ""
    if link_tag:
        href = link_tag.get("href", "")
        source_url = href if href.startswith("http") else f"https://www.linkedin.com{href}"

    # Resolve fields
    region = _detect_region(location_raw, location)
    city, country = _parse_location(location_raw)
    work_type = _detect_work_type(title + " " + location_raw)
    exp_level = _detect_experience_level(title)
    category = _classify_role(title)
    employment_type = _detect_employment_type(title)

    return JobPosting(
        job_id=str(job_id) if job_id else None,
        title=title,
        normalized_category=category,
        company_name=company,
        location_raw=location_raw,
        location_city=city,
        location_country=country,
        region=region,
        work_type=work_type,
        date_posted=date_posted,
        date_posted_raw=date_posted_raw,
        experience_level=exp_level,
        employment_type=employment_type,
        source_url=source_url,
        search_query=query,
        search_location=location,
    )


def _parse_json_ld(soup: BeautifulSoup, query: str, location: str) -> List[JobPosting]:
    """Extract jobs from JSON-LD structured data if available."""
    import json

    jobs = []
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
            if isinstance(data, list):
                for item in data:
                    job = _json_ld_to_job(item, query, location)
                    if job:
                        jobs.append(job)
            elif data.get("@type") == "JobPosting":
                job = _json_ld_to_job(data, query, location)
                if job:
                    jobs.append(job)
        except Exception:
            continue
    return jobs


def _json_ld_to_job(data: dict, query: str, location: str) -> Optional[JobPosting]:
    """Convert JSON-LD JobPosting schema to JobPosting model."""
    if data.get("@type") != "JobPosting":
        return None

    title = data.get("title", "")
    if not title:
        return None

    company = ""
    if org := data.get("hiringOrganization"):
        company = org.get("name", "") if isinstance(org, dict) else str(org)

    location_raw = ""
    if loc := data.get("jobLocation"):
        if isinstance(loc, dict):
            addr = loc.get("address", {})
            parts = [
                addr.get("streetAddress", ""),
                addr.get("addressLocality", ""),
                addr.get("addressRegion", ""),
                addr.get("addressCountry", ""),
            ]
            location_raw = ", ".join(p for p in parts if p)

    date_posted = None
    if dp := data.get("datePosted"):
        try:
            date_posted = parse_date(dp)
        except Exception:
            pass

    return JobPosting(
        title=title,
        company_name=company or "Unknown",
        location_raw=location_raw or location,
        location_country=_infer_country(location_raw or location),
        region=_detect_region(location_raw, location),
        work_type=_detect_work_type(data.get("jobLocationType", "") + " " + title),
        date_posted=date_posted,
        experience_level=_detect_experience_level(title),
        normalized_category=_classify_role(title),
        search_query=query,
        search_location=location,
    )


# ─────────────────────────────────────────────
# SKILL EXTRACTION
# ─────────────────────────────────────────────

def extract_skills(text: str) -> List[str]:
    """Extract tech skills from job description text."""
    if not text:
        return []

    text_lower = text.lower()
    found = set()

    for skill_lower, skill_canonical in SKILL_PATTERNS.items():
        # Use word boundaries to avoid false matches
        pattern = r'\b' + re.escape(skill_lower) + r'\b'
        if re.search(pattern, text_lower):
            found.add(skill_canonical)

    return sorted(found)


# ─────────────────────────────────────────────
# CLASSIFICATION HELPERS
# ─────────────────────────────────────────────

def _classify_role(title: str) -> RoleCategory:
    title_lower = title.lower()
    for category, keywords in ROLE_CATEGORY_KEYWORDS.items():
        for kw in keywords:
            if kw in title_lower:
                return category
    return RoleCategory.OTHER


def _detect_experience_level(text: str) -> ExperienceLevel:
    text_lower = text.lower()
    for level, keywords in EXPERIENCE_KEYWORDS.items():
        for kw in keywords:
            if kw in text_lower:
                return level
    return ExperienceLevel.NOT_SPECIFIED


def _detect_work_type(text: str) -> WorkType:
    text_lower = text.lower()
    if "hybrid" in text_lower:
        return WorkType.HYBRID
    if any(w in text_lower for w in ["remote", "work from home", "wfh", "distributed"]):
        return WorkType.REMOTE
    if any(w in text_lower for w in ["on-site", "onsite", "in-office", "in office"]):
        return WorkType.ONSITE
    return WorkType.NOT_SPECIFIED


def _detect_employment_type(text: str) -> EmploymentType:
    text_lower = text.lower()
    if "contract" in text_lower or "contractor" in text_lower:
        return EmploymentType.CONTRACT
    if "part-time" in text_lower or "part time" in text_lower:
        return EmploymentType.PART_TIME
    if "internship" in text_lower or "intern " in text_lower:
        return EmploymentType.INTERNSHIP
    return EmploymentType.FULL_TIME


def _detect_region(location_raw: str, search_location: str) -> Region:
    combined = (location_raw + " " + search_location).lower()
    for signal in US_SIGNALS:
        if signal in combined:
            return Region.US
    for signal in INDIA_SIGNALS:
        if signal in combined:
            return Region.INDIA
    return Region.OTHER


def _parse_location(location_raw: str) -> Tuple[Optional[str], Optional[str]]:
    """Extract city and country from raw location string."""
    if not location_raw:
        return None, None
    parts = [p.strip() for p in location_raw.split(",")]
    city = parts[0] if parts else None
    country = parts[-1] if len(parts) > 1 else None
    return city, country


def _infer_country(location: str) -> Optional[str]:
    loc_lower = location.lower()
    for signal in US_SIGNALS:
        if signal in loc_lower:
            return "United States"
    for signal in INDIA_SIGNALS:
        if signal in loc_lower:
            return "India"
    return None


def _parse_relative_date(date_str: Optional[str]) -> Optional[datetime]:
    """Parse relative or absolute date strings."""
    if not date_str:
        return None

    date_str = date_str.strip().lower()
    now = datetime.utcnow()

    # ISO format
    try:
        return parse_date(date_str)
    except Exception:
        pass

    # Relative: "2 days ago", "1 week ago", etc.
    patterns = [
        (r"(\d+)\s+second", lambda m: now - timedelta(seconds=int(m.group(1)))),
        (r"(\d+)\s+minute", lambda m: now - timedelta(minutes=int(m.group(1)))),
        (r"(\d+)\s+hour", lambda m: now - timedelta(hours=int(m.group(1)))),
        (r"(\d+)\s+day", lambda m: now - timedelta(days=int(m.group(1)))),
        (r"(\d+)\s+week", lambda m: now - timedelta(weeks=int(m.group(1)))),
        (r"(\d+)\s+month", lambda m: now - timedelta(days=int(m.group(1)) * 30)),
        (r"(\d+)\s+year", lambda m: now - timedelta(days=int(m.group(1)) * 365)),
    ]

    for pattern, handler in patterns:
        m = re.search(pattern, date_str)
        if m:
            try:
                return handler(m)
            except Exception:
                pass

    if "today" in date_str or "just now" in date_str:
        return now
    if "yesterday" in date_str:
        return now - timedelta(days=1)

    return None


def _clean_text(text: str) -> str:
    """Strip whitespace and normalize."""
    return re.sub(r"\s+", " ", text).strip()


# ─────────────────────────────────────────────
# DEDUPLICATION
# ─────────────────────────────────────────────

def deduplicate_jobs(jobs: List[JobPosting]) -> Tuple[List[JobPosting], int]:
    """Remove duplicate job postings by job_id, then by title+company."""
    seen_ids: set = set()
    seen_title_company: set = set()
    unique = []
    dupe_count = 0

    for job in jobs:
        if job.job_id and job.job_id in seen_ids:
            dupe_count += 1
            continue

        key = (job.title.lower().strip(), job.company_name.lower().strip())
        if key in seen_title_company:
            dupe_count += 1
            continue

        if job.job_id:
            seen_ids.add(job.job_id)
        seen_title_company.add(key)
        unique.append(job)

    return unique, dupe_count


# ─────────────────────────────────────────────
# SERPAPI DIRECT JSON PARSER
# ─────────────────────────────────────────────

def parse_serpapi_json(raw_json: str, query: str, location: str) -> List[JobPosting]:
    """
    Parse a SerpAPI google_jobs response JSON array directly into JobPosting objects.
    This bypasses the HTML parser entirely — no LinkedIn card selectors needed.

    SerpAPI google_jobs result shape:
    [
      {
        "title": "Software Engineer",
        "company_name": "Google",
        "location": "Mountain View, CA",
        "description": "...",
        "detected_extensions": {
            "posted_at": "3 days ago",
            "schedule_type": "Full-time",
            "work_from_home": true
        },
        "job_id": "eyJ...",
        "related_links": [{"link": "https://...", "text": "Apply"}],
        ...
      },
      ...
    ]
    """
    import json

    try:
        jobs_data = json.loads(raw_json)
    except json.JSONDecodeError as e:
        console.print(f"[red]SerpAPI JSON parse error: {e}[/red]")
        return []

    if not isinstance(jobs_data, list):
        console.print(f"[yellow]SerpAPI data is not a list, got: {type(jobs_data)}[/yellow]")
        return []

    jobs: List[JobPosting] = []

    for i, item in enumerate(jobs_data):
        try:
            job = _serpapi_item_to_job(item, query, location, index=i)
            if job:
                jobs.append(job)
        except Exception as e:
            console.print(f"[dim]  SerpAPI item parse error (item {i}): {e}[/dim]")
            continue

    return jobs


def _serpapi_item_to_job(
    item: Dict[str, Any],
    query: str,
    location: str,
    index: int = 0,
) -> Optional[JobPosting]:
    """Convert a single SerpAPI google_jobs result item to a JobPosting."""

    title = _clean_text(item.get("title", ""))
    if not title:
        return None

    company  = _clean_text(item.get("company_name", "Unknown Company"))
    loc_raw  = _clean_text(item.get("location", location))
    desc     = item.get("description", "")
    job_id   = str(item.get("job_id", f"serpapi_{index}"))

    # ── Extensions (schedule type, remote, posted_at) ─────────────
    ext           = item.get("detected_extensions", {}) or {}
    schedule_type = ext.get("schedule_type", "")        # e.g. "Full-time"
    work_from_home = ext.get("work_from_home", False)
    posted_raw    = ext.get("posted_at", "")            # e.g. "3 days ago"

    # ── Source URL ─────────────────────────────────────────────────
    source_url = ""
    for link in item.get("related_links", []) or []:
        href = link.get("link", "")
        if href.startswith("http"):
            source_url = href
            break
    if not source_url:
        source_url = item.get("job_apply_link", "")

    # ── Derive fields ──────────────────────────────────────────────
    combined_text = f"{title} {loc_raw} {desc} {schedule_type}"

    work_type = (
        WorkType.REMOTE if work_from_home
        else _detect_work_type(combined_text)
    )
    emp_type    = _detect_employment_type(schedule_type or combined_text)
    exp_level   = _detect_experience_level(title + " " + desc[:500])
    category    = _classify_role(title)
    region      = _detect_region(loc_raw, location)
    city, country = _parse_location(loc_raw)
    date_posted = _parse_relative_date(posted_raw)
    skills      = extract_skills(desc + " " + title)

    return JobPosting(
        job_id=job_id,
        title=title,
        normalized_category=category,
        company_name=company,
        location_raw=loc_raw,
        location_city=city,
        location_country=country or _infer_country(loc_raw + " " + location),
        region=region,
        work_type=work_type,
        date_posted=date_posted,
        date_posted_raw=posted_raw,
        required_skills=skills,
        experience_level=exp_level,
        employment_type=emp_type,
        job_description=desc[:2000] if desc else None,  # cap length
        source_url=source_url,
        search_query=query,
        search_location=location,
    )
