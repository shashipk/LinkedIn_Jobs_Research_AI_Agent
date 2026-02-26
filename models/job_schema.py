"""
Pydantic models for LinkedIn job data.
All agents use these for structured input/output.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


# ─────────────────────────────────────────────
# ENUMERATIONS
# ─────────────────────────────────────────────

class RoleCategory(str, Enum):
    BACKEND = "Backend Engineer"
    FRONTEND = "Frontend Engineer"
    FULLSTACK = "Full Stack Engineer"
    ML_AI = "ML/AI Engineer"
    DATA_ENGINEER = "Data Engineer"
    DATA_SCIENTIST = "Data Scientist"
    DEVOPS = "DevOps/Platform/SRE"
    ENGINEERING_MANAGER = "Engineering Manager/Tech Lead"
    SOFTWARE_ENGINEER = "Software Engineer"
    FORWARD_DEPLOYED_ENGINEER = "Forward Deployed Engineer"   # FDE, Solutions Engineer, Field Engineer
    PRODUCT_PROGRAM_MANAGEMENT = "Product/Program Management" # Tech PM, AI PM, TPM, Tech Program Manager
    OTHER = "Other"


class ExperienceLevel(str, Enum):
    ENTRY = "Entry"
    MID = "Mid"
    SENIOR = "Senior"
    STAFF = "Staff"
    PRINCIPAL = "Principal"
    MANAGER = "Manager"
    NOT_SPECIFIED = "Not Specified"


class WorkType(str, Enum):
    REMOTE = "Remote"
    HYBRID = "Hybrid"
    ONSITE = "Onsite"
    NOT_SPECIFIED = "Not Specified"


class EmploymentType(str, Enum):
    FULL_TIME = "Full-time"
    PART_TIME = "Part-time"
    CONTRACT = "Contract"
    INTERNSHIP = "Internship"
    NOT_SPECIFIED = "Not Specified"


class Region(str, Enum):
    US = "United States"
    INDIA = "India"
    OTHER = "Other"


# ─────────────────────────────────────────────
# CORE JOB MODEL
# ─────────────────────────────────────────────

class JobPosting(BaseModel):
    """Represents a single LinkedIn job posting."""

    job_id: Optional[str] = None
    title: str
    normalized_category: RoleCategory = RoleCategory.OTHER
    company_name: str
    company_size: Optional[str] = None
    location_city: Optional[str] = None
    location_country: Optional[str] = None
    location_raw: str = ""
    region: Region = Region.OTHER
    work_type: WorkType = WorkType.NOT_SPECIFIED
    date_posted: Optional[datetime] = None
    date_posted_raw: Optional[str] = None
    required_skills: List[str] = Field(default_factory=list)
    experience_level: ExperienceLevel = ExperienceLevel.NOT_SPECIFIED
    employment_type: EmploymentType = EmploymentType.NOT_SPECIFIED
    job_description: Optional[str] = None
    source_url: str = ""
    scraped_at: datetime = Field(default_factory=datetime.utcnow)
    search_query: Optional[str] = None
    search_location: Optional[str] = None
    # ── AI/ML mention detection ──────────────────────────────────────
    has_ai_mention: bool = False                              # True if any AI/ML keyword found
    ai_keywords_found: List[str] = Field(default_factory=list)  # e.g. ["LLM", "RAG", "embeddings"]

    @field_validator("required_skills", mode="before")
    @classmethod
    def deduplicate_skills(cls, v: Any) -> List[str]:
        if isinstance(v, list):
            seen = set()
            result = []
            for item in v:
                lower = item.strip().lower()
                if lower and lower not in seen:
                    seen.add(lower)
                    result.append(item.strip())
            return result
        return v

    def to_dict(self) -> Dict[str, Any]:
        d = self.model_dump()
        d["date_posted"] = self.date_posted.isoformat() if self.date_posted else None
        d["scraped_at"] = self.scraped_at.isoformat()
        d["required_skills"] = ", ".join(self.required_skills)
        d["normalized_category"] = self.normalized_category.value
        d["experience_level"] = self.experience_level.value
        d["work_type"] = self.work_type.value
        d["employment_type"] = self.employment_type.value
        d["region"] = self.region.value
        d["ai_keywords_found"] = ", ".join(self.ai_keywords_found)
        return d


# ─────────────────────────────────────────────
# SCRAPER OUTPUT
# ─────────────────────────────────────────────

class RawJobPage(BaseModel):
    """Raw HTML page returned by the scraper."""

    url: str
    html: str
    query: str
    location: str
    page_number: int = 1
    scraped_at: datetime = Field(default_factory=datetime.utcnow)
    success: bool = True
    error_message: Optional[str] = None


class ScraperResult(BaseModel):
    """Aggregated result from the Scraper Agent."""

    pages: List[RawJobPage] = Field(default_factory=list)
    total_pages_scraped: int = 0
    total_queries_run: int = 0
    failed_queries: List[str] = Field(default_factory=list)
    captcha_encountered: bool = False
    source: str = "playwright"  # "playwright" | "serpapi"


# ─────────────────────────────────────────────
# PARSER OUTPUT
# ─────────────────────────────────────────────

class ParsedJobBatch(BaseModel):
    """Batch of parsed job postings from Parser Agent."""

    jobs: List[JobPosting] = Field(default_factory=list)
    total_parsed: int = 0
    total_failed: int = 0
    duplicate_count: int = 0
    source_pages: int = 0


# ─────────────────────────────────────────────
# ANALYST OUTPUT
# ─────────────────────────────────────────────

class RoleStats(BaseModel):
    """Statistics for a specific role category."""

    category: str
    total_count: int
    us_count: int = 0
    india_count: int = 0
    other_count: int = 0
    avg_experience_level: str = "Mid"
    top_skills: List[str] = Field(default_factory=list)
    remote_percentage: float = 0.0
    hybrid_percentage: float = 0.0
    onsite_percentage: float = 0.0


class QuarterlyTrend(BaseModel):
    """Job count for a specific quarter."""

    quarter: str          # e.g. "2024-Q1"
    count: int
    category: Optional[str] = None
    region: Optional[str] = None


class SkillFrequency(BaseModel):
    """Frequency of a skill across all postings."""

    skill: str
    count: int
    percentage: float
    top_categories: List[str] = Field(default_factory=list)


class CompanyStats(BaseModel):
    """Hiring stats for a company."""

    company_name: str
    total_openings: int
    categories: List[str] = Field(default_factory=list)
    locations: List[str] = Field(default_factory=list)
    remote_count: int = 0


class AnalysisResult(BaseModel):
    """Full analysis result from the Analyst Agent."""

    total_jobs: int
    us_jobs: int
    india_jobs: int
    other_jobs: int
    role_stats: List[RoleStats] = Field(default_factory=list)
    quarterly_trends: List[QuarterlyTrend] = Field(default_factory=list)
    top_skills: List[SkillFrequency] = Field(default_factory=list)
    experience_distribution: Dict[str, int] = Field(default_factory=dict)
    work_type_distribution: Dict[str, int] = Field(default_factory=dict)
    employment_type_distribution: Dict[str, int] = Field(default_factory=dict)
    top_companies: List[CompanyStats] = Field(default_factory=list)
    insights: List[str] = Field(default_factory=list)
    ai_mention_by_role: Dict[str, float] = Field(default_factory=dict)  # role → % of jobs mentioning AI/ML
    generated_at: datetime = Field(default_factory=datetime.utcnow)


# ─────────────────────────────────────────────
# REPORT OUTPUT
# ─────────────────────────────────────────────

class ReportResult(BaseModel):
    """Final report output metadata."""

    report_path: str
    json_path: str
    csv_path: str
    charts_generated: List[str] = Field(default_factory=list)
    total_jobs_in_report: int = 0
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    success: bool = True
    error_message: Optional[str] = None


# ─────────────────────────────────────────────
# PIPELINE STATE
# ─────────────────────────────────────────────

class PipelineState(BaseModel):
    """Shared state passed through the agent pipeline."""

    config: Dict[str, Any] = Field(default_factory=dict)
    scraper_result: Optional[ScraperResult] = None
    parsed_jobs: Optional[ParsedJobBatch] = None
    analysis: Optional[AnalysisResult] = None
    report: Optional[ReportResult] = None
    started_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    errors: List[str] = Field(default_factory=list)
