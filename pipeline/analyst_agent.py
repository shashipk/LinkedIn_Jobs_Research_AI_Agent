"""
Analyst Agent — aggregates job data, identifies trends, classifies roles,
and generates LLM-powered insights using the OpenAI Agents SDK.
"""

from __future__ import annotations

import asyncio
from collections import Counter, defaultdict
from datetime import datetime
from typing import Any, Dict, List, Optional

from agents import Agent, Runner, function_tool
from rich.console import Console

from models.job_schema import (
    AnalysisResult,
    CompanyStats,
    ParsedJobBatch,
    QuarterlyTrend,
    Region,
    RoleStats,
    SkillFrequency,
    WorkType,
)

console = Console()


# ─────────────────────────────────────────────
# TOOLS
# ─────────────────────────────────────────────

@function_tool
def compute_role_statistics(parsed_batch_json: str) -> str:
    """
    Compute per-role statistics: total counts, regional breakdown,
    work type percentages, and top skills per role.

    Args:
        parsed_batch_json: JSON string of ParsedJobBatch

    Returns:
        JSON list of RoleStats objects
    """
    import json

    batch = ParsedJobBatch.model_validate_json(parsed_batch_json)
    jobs = batch.jobs

    # Group jobs by category
    by_category: Dict[str, List] = defaultdict(list)
    for job in jobs:
        by_category[job.normalized_category.value].append(job)

    role_stats = []
    for category, cat_jobs in by_category.items():
        us = sum(1 for j in cat_jobs if j.region == Region.US)
        india = sum(1 for j in cat_jobs if j.region == Region.INDIA)
        other = sum(1 for j in cat_jobs if j.region == Region.OTHER)
        total = len(cat_jobs)

        # Work type
        remote = sum(1 for j in cat_jobs if j.work_type == WorkType.REMOTE)
        hybrid = sum(1 for j in cat_jobs if j.work_type == WorkType.HYBRID)
        onsite = sum(1 for j in cat_jobs if j.work_type.value in ("Onsite", "Not Specified"))

        # Top skills
        skill_counter: Counter = Counter()
        for job in cat_jobs:
            for skill in job.required_skills:
                skill_counter[skill] += 1
        top_skills = [s for s, _ in skill_counter.most_common(10)]

        role_stats.append(RoleStats(
            category=category,
            total_count=total,
            us_count=us,
            india_count=india,
            other_count=other,
            top_skills=top_skills,
            remote_percentage=round(remote / total * 100, 1) if total else 0,
            hybrid_percentage=round(hybrid / total * 100, 1) if total else 0,
            onsite_percentage=round(onsite / total * 100, 1) if total else 0,
        ).model_dump())

    return json.dumps(role_stats)


@function_tool
def compute_quarterly_trends(parsed_batch_json: str) -> str:
    """
    Compute quarterly posting trends (last 24 months) by category and region.

    Args:
        parsed_batch_json: JSON string of ParsedJobBatch

    Returns:
        JSON list of QuarterlyTrend objects
    """
    import json

    batch = ParsedJobBatch.model_validate_json(parsed_batch_json)
    jobs = [j for j in batch.jobs if j.date_posted]

    # Count by quarter and category
    quarter_cat: Dict[tuple, int] = defaultdict(int)
    quarter_all: Dict[str, int] = defaultdict(int)

    for job in jobs:
        try:
            dt = job.date_posted
            if not dt:
                continue
            q = f"{dt.year}-Q{(dt.month - 1) // 3 + 1}"
            quarter_all[q] += 1
            quarter_cat[(q, job.normalized_category.value)] += 1
        except Exception:
            continue

    trends = []
    for quarter, count in quarter_all.items():
        trends.append(QuarterlyTrend(quarter=quarter, count=count, category="All").model_dump())

    for (quarter, category), count in quarter_cat.items():
        trends.append(QuarterlyTrend(quarter=quarter, count=count, category=category).model_dump())

    return json.dumps(trends)


@function_tool
def compute_skill_frequencies(parsed_batch_json: str, top_n: int = 20) -> str:
    """
    Compute skill frequency across all job postings.

    Args:
        parsed_batch_json: JSON string of ParsedJobBatch
        top_n: Number of top skills to return

    Returns:
        JSON list of SkillFrequency objects
    """
    import json

    batch = ParsedJobBatch.model_validate_json(parsed_batch_json)
    total_jobs = len(batch.jobs)

    skill_counter: Counter = Counter()
    skill_categories: Dict[str, Counter] = defaultdict(Counter)

    for job in batch.jobs:
        for skill in job.required_skills:
            skill_counter[skill] += 1
            skill_categories[skill][job.normalized_category.value] += 1

    result = []
    for skill, count in skill_counter.most_common(top_n):
        pct = round(count / total_jobs * 100, 1) if total_jobs else 0
        top_cats = [cat for cat, _ in skill_categories[skill].most_common(3)]
        result.append(SkillFrequency(
            skill=skill,
            count=count,
            percentage=pct,
            top_categories=top_cats,
        ).model_dump())

    return json.dumps(result)


@function_tool
def compute_distributions(parsed_batch_json: str) -> str:
    """
    Compute experience level, work type, and employment type distributions.

    Args:
        parsed_batch_json: JSON string of ParsedJobBatch

    Returns:
        JSON with experience_distribution, work_type_distribution, employment_type_distribution
    """
    import json

    batch = ParsedJobBatch.model_validate_json(parsed_batch_json)
    jobs = batch.jobs

    exp_dist: Counter = Counter()
    work_dist: Counter = Counter()
    emp_dist: Counter = Counter()

    for job in jobs:
        exp_dist[job.experience_level.value] += 1
        work_dist[job.work_type.value] += 1
        emp_dist[job.employment_type.value] += 1

    return json.dumps({
        "experience_distribution": dict(exp_dist),
        "work_type_distribution": dict(work_dist),
        "employment_type_distribution": dict(emp_dist),
    })


@function_tool
def compute_top_companies(parsed_batch_json: str, top_n: int = 20) -> str:
    """
    Identify top hiring companies by number of open roles.

    Args:
        parsed_batch_json: JSON string of ParsedJobBatch
        top_n: Number of top companies to return

    Returns:
        JSON list of CompanyStats objects
    """
    import json

    batch = ParsedJobBatch.model_validate_json(parsed_batch_json)

    company_jobs: Dict[str, list] = defaultdict(list)
    for job in batch.jobs:
        company_jobs[job.company_name].append(job)

    stats = []
    for company, jobs in sorted(company_jobs.items(), key=lambda x: -len(x[1]))[:top_n]:
        categories = list({j.normalized_category.value for j in jobs})
        locations = list({j.location_raw for j in jobs if j.location_raw})[:5]
        remote_count = sum(1 for j in jobs if j.work_type == WorkType.REMOTE)

        stats.append(CompanyStats(
            company_name=company,
            total_openings=len(jobs),
            categories=categories,
            locations=locations,
            remote_count=remote_count,
        ).model_dump())

    return json.dumps(stats)


@function_tool
def generate_insights(analysis_summary_json: str) -> str:
    """
    Generate qualitative insights from the analysis summary.
    This is a structured summary prompt — the LLM will reason through the data.

    Args:
        analysis_summary_json: JSON summary of all analysis metrics

    Returns:
        JSON list of insight strings
    """
    import json

    summary = json.loads(analysis_summary_json)

    # Build insights programmatically (no LLM call in tool — insights come from Analyst Agent's reasoning)
    insights = []

    total = summary.get("total_jobs", 0)
    us = summary.get("us_jobs", 0)
    india = summary.get("india_jobs", 0)

    if total > 0:
        us_pct = round(us / total * 100)
        india_pct = round(india / total * 100)
        insights.append(
            f"US market dominates with {us_pct}% of total postings ({us:,} jobs), "
            f"while India accounts for {india_pct}% ({india:,} jobs)."
        )

    role_stats = summary.get("role_stats", [])
    if role_stats:
        top_role = max(role_stats, key=lambda r: r.get("total_count", 0))
        insights.append(
            f"'{top_role['category']}' is the most in-demand role with "
            f"{top_role['total_count']:,} open positions globally."
        )
        ml_ai = next((r for r in role_stats if "ML" in r["category"] or "AI" in r["category"]), None)
        if ml_ai:
            insights.append(
                f"ML/AI roles show strong demand ({ml_ai['total_count']:,} postings), "
                f"reflecting the ongoing AI adoption wave across industries."
            )

    top_skills = summary.get("top_skills", [])
    if top_skills:
        top_3 = [s["skill"] for s in top_skills[:3]]
        insights.append(
            f"The top 3 most in-demand skills are: {', '.join(top_3)}. "
            f"Cloud and AI/ML competencies appear frequently across all role types."
        )

    work_dist = summary.get("work_type_distribution", {})
    remote = work_dist.get("Remote", 0)
    hybrid = work_dist.get("Hybrid", 0)
    if total > 0 and (remote + hybrid) > 0:
        flex_pct = round((remote + hybrid) / total * 100)
        insights.append(
            f"{flex_pct}% of roles offer flexible work arrangements "
            f"(Remote or Hybrid), indicating a sustained shift post-pandemic."
        )

    exp_dist = summary.get("experience_distribution", {})
    senior = exp_dist.get("Senior", 0)
    if total > 0 and senior > 0:
        senior_pct = round(senior / total * 100)
        insights.append(
            f"Senior-level roles constitute {senior_pct}% of all postings, "
            f"suggesting companies prioritize experienced talent over entry-level hiring."
        )

    return json.dumps(insights)


# ─────────────────────────────────────────────
# AGENT DEFINITION
# ─────────────────────────────────────────────

def create_analyst_agent(config: Dict[str, Any]) -> Agent:
    """Create and return the Analyst Agent."""
    return Agent(
        name="AnalystAgent",
        model=config.get("openai", {}).get("analyst_model", "gpt-4o"),
        instructions="""
You are the LinkedIn Jobs Analyst Agent. Your job is to produce a comprehensive
analysis of job market trends from parsed job data.

Steps to follow:
1. Call compute_role_statistics to get per-role stats
2. Call compute_quarterly_trends to get quarterly trend data
3. Call compute_skill_frequencies to get the top 20 skills
4. Call compute_distributions to get experience, work type, employment type breakdowns
5. Call compute_top_companies to identify top hiring companies
6. Build an analysis summary JSON and call generate_insights for qualitative observations
7. Return a complete AnalysisResult with all computed data

Ensure all statistics are accurate. The analysis should cover:
- Total jobs (globally, US, India, Other)
- Per-role category breakdown
- Quarterly trends (last 24 months)
- Top 20 skills by demand
- Experience level distribution
- Remote/Hybrid/Onsite split
- Top 20 hiring companies
- 5-8 key market insights
""",
        tools=[
            compute_role_statistics,
            compute_quarterly_trends,
            compute_skill_frequencies,
            compute_distributions,
            compute_top_companies,
            generate_insights,
        ],
        output_type=AnalysisResult,
    )


# ─────────────────────────────────────────────
# STANDALONE RUNNER
# ─────────────────────────────────────────────

def run_analyst(batch: ParsedJobBatch, config: Dict[str, Any]) -> AnalysisResult:
    """
    Run the analyst pipeline synchronously.

    Args:
        batch: ParsedJobBatch from the Parser Agent
        config: Application config

    Returns:
        AnalysisResult with complete analysis
    """
    import json

    console.print(f"\n[bold cyan]Analyst Agent[/bold cyan] — analyzing {batch.total_parsed} jobs")

    jobs = batch.jobs
    total = len(jobs)

    # ── Regional split
    us_jobs = sum(1 for j in jobs if j.region == Region.US)
    india_jobs = sum(1 for j in jobs if j.region == Region.INDIA)
    other_jobs = total - us_jobs - india_jobs

    console.print(f"  Regions → US: {us_jobs} | India: {india_jobs} | Other: {other_jobs}")

    # ── Role statistics
    by_category: Dict[str, List] = defaultdict(list)
    for job in jobs:
        by_category[job.normalized_category.value].append(job)

    role_stats_list = []
    for category, cat_jobs in by_category.items():
        us_c = sum(1 for j in cat_jobs if j.region == Region.US)
        india_c = sum(1 for j in cat_jobs if j.region == Region.INDIA)
        other_c = len(cat_jobs) - us_c - india_c
        total_c = len(cat_jobs)

        remote_c = sum(1 for j in cat_jobs if j.work_type == WorkType.REMOTE)
        hybrid_c = sum(1 for j in cat_jobs if j.work_type.value == "Hybrid")
        onsite_c = total_c - remote_c - hybrid_c

        skill_ctr: Counter = Counter()
        for j in cat_jobs:
            skill_ctr.update(j.required_skills)
        top_skills = [s for s, _ in skill_ctr.most_common(10)]

        role_stats_list.append(RoleStats(
            category=category,
            total_count=total_c,
            us_count=us_c,
            india_count=india_c,
            other_count=other_c,
            top_skills=top_skills,
            remote_percentage=round(remote_c / total_c * 100, 1) if total_c else 0,
            hybrid_percentage=round(hybrid_c / total_c * 100, 1) if total_c else 0,
            onsite_percentage=round(onsite_c / total_c * 100, 1) if total_c else 0,
        ))

    # ── Quarterly trends
    quarter_cat: Dict[tuple, int] = defaultdict(int)
    for job in jobs:
        if job.date_posted:
            dt = job.date_posted
            q = f"{dt.year}-Q{(dt.month - 1) // 3 + 1}"
            quarter_cat[(q, job.normalized_category.value)] += 1

    quarterly_trends = [
        QuarterlyTrend(quarter=q, count=cnt, category=cat)
        for (q, cat), cnt in quarter_cat.items()
    ]

    # ── Skill frequencies
    skill_ctr_global: Counter = Counter()
    skill_cats: Dict[str, Counter] = defaultdict(Counter)
    for job in jobs:
        for skill in job.required_skills:
            skill_ctr_global[skill] += 1
            skill_cats[skill][job.normalized_category.value] += 1

    top_skills_list = [
        SkillFrequency(
            skill=skill,
            count=count,
            percentage=round(count / total * 100, 1) if total else 0,
            top_categories=[c for c, _ in skill_cats[skill].most_common(3)],
        )
        for skill, count in skill_ctr_global.most_common(20)
    ]

    # ── Distributions
    exp_dist: Counter = Counter(j.experience_level.value for j in jobs)
    work_dist: Counter = Counter(j.work_type.value for j in jobs)
    emp_dist: Counter = Counter(j.employment_type.value for j in jobs)

    # ── AI/ML mention rate by role
    ai_mention_by_role: Dict[str, float] = {}
    for category, cat_jobs in by_category.items():
        total_c = len(cat_jobs)
        ai_count = sum(1 for j in cat_jobs if j.has_ai_mention)
        ai_mention_by_role[category] = round(ai_count / total_c * 100, 1) if total_c else 0.0

    console.print(f"  AI/ML mention rates computed across {len(ai_mention_by_role)} role categories")

    # ── Top companies
    company_jobs: Dict[str, list] = defaultdict(list)
    for job in jobs:
        company_jobs[job.company_name].append(job)

    top_companies = [
        CompanyStats(
            company_name=company,
            total_openings=len(cjobs),
            categories=list({j.normalized_category.value for j in cjobs}),
            locations=list({j.location_raw for j in cjobs if j.location_raw})[:5],
            remote_count=sum(1 for j in cjobs if j.work_type == WorkType.REMOTE),
        )
        for company, cjobs in sorted(company_jobs.items(), key=lambda x: -len(x[1]))[:20]
    ]

    # ── Generate insights
    summary = {
        "total_jobs": total,
        "us_jobs": us_jobs,
        "india_jobs": india_jobs,
        "other_jobs": other_jobs,
        "role_stats": [r.model_dump() for r in role_stats_list],
        "top_skills": [s.model_dump() for s in top_skills_list],
        "work_type_distribution": dict(work_dist),
        "experience_distribution": dict(exp_dist),
    }

    # Generate rule-based insights first
    insights_json = _compute_rule_based_insights(summary)
    insights = json.loads(insights_json) if isinstance(insights_json, str) else []

    # Upgrade with LLM-powered insights if OpenAI key is available
    try:
        llm_insights = _generate_llm_insights(summary, config)
        if llm_insights:
            insights = llm_insights
    except Exception as e:
        console.print(f"[dim]LLM insights skipped: {e}[/dim]")

    result = AnalysisResult(
        total_jobs=total,
        us_jobs=us_jobs,
        india_jobs=india_jobs,
        other_jobs=other_jobs,
        role_stats=role_stats_list,
        quarterly_trends=quarterly_trends,
        top_skills=top_skills_list,
        experience_distribution=dict(exp_dist),
        work_type_distribution=dict(work_dist),
        employment_type_distribution=dict(emp_dist),
        top_companies=top_companies,
        insights=insights,
        ai_mention_by_role=ai_mention_by_role,
    )

    console.print(f"  [green]✓[/green] Analysis complete")
    return result


def _compute_rule_based_insights(summary: dict) -> str:
    """Generate deterministic insights from analysis data (no LLM required)."""
    import json as _json

    insights = []
    total = summary.get("total_jobs", 0)
    us = summary.get("us_jobs", 0)
    india = summary.get("india_jobs", 0)

    if total > 0:
        us_pct = round(us / total * 100)
        india_pct = round(india / total * 100)
        insights.append(
            f"US market dominates with {us_pct}% of total postings ({us:,} jobs), "
            f"while India accounts for {india_pct}% ({india:,} jobs)."
        )

    role_stats = summary.get("role_stats", [])
    if role_stats:
        top_role = max(role_stats, key=lambda r: r.get("total_count", 0))
        insights.append(
            f"'{top_role['category']}' is the most in-demand role with "
            f"{top_role['total_count']:,} open positions globally."
        )
        ml_ai = next((r for r in role_stats if "ML" in r["category"] or "AI" in r["category"]), None)
        if ml_ai:
            insights.append(
                f"ML/AI roles show strong demand ({ml_ai['total_count']:,} postings), "
                f"reflecting the ongoing AI adoption wave across industries."
            )

    top_skills = summary.get("top_skills", [])
    if top_skills:
        top_3 = [s["skill"] for s in top_skills[:3]]
        insights.append(
            f"The top 3 most in-demand skills are: {', '.join(top_3)}. "
            f"Cloud and AI/ML competencies appear frequently across all role types."
        )

    work_dist = summary.get("work_type_distribution", {})
    remote = work_dist.get("Remote", 0)
    hybrid = work_dist.get("Hybrid", 0)
    if total > 0 and (remote + hybrid) > 0:
        flex_pct = round((remote + hybrid) / total * 100)
        insights.append(
            f"{flex_pct}% of roles offer flexible work arrangements "
            f"(Remote or Hybrid), indicating a sustained shift post-pandemic."
        )

    exp_dist = summary.get("experience_distribution", {})
    senior = exp_dist.get("Senior", 0)
    if total > 0 and senior > 0:
        senior_pct = round(senior / total * 100)
        insights.append(
            f"Senior-level roles constitute {senior_pct}% of all postings, "
            f"suggesting companies prioritize experienced talent over entry-level hiring."
        )

    return _json.dumps(insights)


def _generate_llm_insights(summary: dict, config: Dict[str, Any]) -> Optional[List[str]]:
    """Use OpenAI to generate qualitative market insights."""
    import json
    from openai import OpenAI

    api_key = __import__("os").getenv("OPENAI_API_KEY")
    if not api_key:
        return None

    client = OpenAI()
    model = config.get("openai", {}).get("analyst_model", "gpt-4o-mini")

    prompt = f"""
You are a tech labor market analyst. Based on the following LinkedIn job data summary,
generate 6-8 concise, data-backed insights about the global tech job market,
with focus on US and India markets.

Data Summary:
{json.dumps(summary, indent=2)}

Return ONLY a JSON array of insight strings. Each insight should be 1-2 sentences,
factual, and reference specific numbers from the data.
"""
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            response_format={"type": "json_object"},
        )
        content = response.choices[0].message.content
        parsed = json.loads(content)
        if isinstance(parsed, list):
            return parsed
        for key in ("insights", "data", "results"):
            if key in parsed and isinstance(parsed[key], list):
                return parsed[key]
    except Exception as e:
        console.print(f"[dim]LLM insight generation error: {e}[/dim]")

    return None
