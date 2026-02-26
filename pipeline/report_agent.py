"""
Report Agent — generates the final Markdown report, charts, JSON, and CSV exports.
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from agents import Agent, function_tool
from rich.console import Console

from models.job_schema import AnalysisResult, ParsedJobBatch, ReportResult

console = Console()


# ─────────────────────────────────────────────
# TOOLS
# ─────────────────────────────────────────────

@function_tool
def save_jobs_json(parsed_batch_json: str, output_path: str) -> str:
    """
    Save job data to a JSON file.

    Args:
        parsed_batch_json: JSON string of ParsedJobBatch
        output_path: Full file path for JSON output

    Returns:
        Saved file path or error message
    """
    batch = ParsedJobBatch.model_validate_json(parsed_batch_json)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    jobs_data = [job.to_dict() for job in batch.jobs]
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(jobs_data, f, indent=2, default=str)

    console.print(f"  [green]✓[/green] JSON saved: {output_path} ({len(jobs_data)} jobs)")
    return output_path


@function_tool
def save_jobs_csv(parsed_batch_json: str, output_path: str) -> str:
    """
    Save job data to a CSV file.

    Args:
        parsed_batch_json: JSON string of ParsedJobBatch
        output_path: Full file path for CSV output

    Returns:
        Saved file path or error message
    """
    import pandas as pd

    batch = ParsedJobBatch.model_validate_json(parsed_batch_json)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    rows = [job.to_dict() for job in batch.jobs]
    if not rows:
        console.print(f"  [yellow]No jobs to save to CSV[/yellow]")
        return output_path

    df = pd.DataFrame(rows)
    df.to_csv(output_path, index=False, encoding="utf-8")

    console.print(f"  [green]✓[/green] CSV saved: {output_path} ({len(rows)} rows)")
    return output_path


@function_tool
def generate_charts(analysis_json: str, charts_dir: str) -> str:
    """
    Generate all report charts from analysis data.

    Args:
        analysis_json: JSON string of AnalysisResult
        charts_dir: Directory to save chart images

    Returns:
        JSON list of generated chart paths
    """
    from tools.chart_tool import generate_all_charts

    analysis = json.loads(analysis_json)
    chart_paths = generate_all_charts(analysis, charts_dir)
    return json.dumps(chart_paths)


@function_tool
def generate_markdown_report(
    analysis_json: str,
    chart_paths_json: str,
    output_path: str,
    charts_dir: str,
) -> str:
    """
    Generate the full Markdown report.

    Args:
        analysis_json: JSON string of AnalysisResult
        chart_paths_json: JSON list of chart file paths
        output_path: Full file path for the .md report
        charts_dir: Relative path to charts directory for image embeds

    Returns:
        Path to generated report
    """
    analysis = AnalysisResult.model_validate_json(analysis_json)
    chart_paths = json.loads(chart_paths_json)

    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    report_content = _build_markdown_report(analysis, chart_paths, charts_dir)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(report_content)

    console.print(f"  [green]✓[/green] Report saved: {output_path}")
    return output_path


# ─────────────────────────────────────────────
# MARKDOWN BUILDER
# ─────────────────────────────────────────────

def _build_markdown_report(
    analysis: AnalysisResult,
    chart_paths: List[str],
    charts_dir: str,
) -> str:
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    lines = []

    def chart_embed(filename: str) -> str:
        for path in chart_paths:
            if filename in path:
                rel = os.path.relpath(path, os.path.dirname(charts_dir) or ".")
                return f"![{filename}]({rel})\n"
        return f"*Chart not generated: {filename}*\n"

    # ── Header
    lines += [
        "# LinkedIn Tech Jobs Demand Report\n",
        f"> **Generated:** {now}  \n",
        f"> **Total Jobs Analyzed:** {analysis.total_jobs:,}  \n",
        f"> **Data Period:** Last 24 months  \n",
        f"> **Regions:** United States · India · Global\n",
        "\n---\n",
    ]

    # ── Table of Contents
    lines += [
        "## Table of Contents\n",
        "1. [Executive Summary](#1-executive-summary)\n",
        "2. [Total Jobs Found by Region](#2-total-jobs-found-by-region)\n",
        "3. [Role Demand Breakdown](#3-role-demand-breakdown)\n",
        "4. [Top Skills in Demand](#4-top-skills-in-demand)\n",
        "5. [Experience Level Distribution](#5-experience-level-distribution)\n",
        "6. [Work Mode Distribution](#6-work-mode-distribution)\n",
        "7. [Top Hiring Companies](#7-top-hiring-companies)\n",
        "8. [Quarterly Trends](#8-quarterly-trends)\n",
        "9. [AI/ML Knowledge Expected by Role](#9-aiml-knowledge-expected-by-role)\n",
        "10. [Observations & Insights](#10-observations--insights)\n",
        "\n---\n",
    ]

    # ── 1. Executive Summary
    lines += [
        "## 1. Executive Summary\n\n",
        f"This report analyzes **{analysis.total_jobs:,} tech job postings** scraped from LinkedIn "
        f"across the United States and India over the past 24 months.\n\n",
        "**Key Highlights:**\n\n",
    ]

    if analysis.insights:
        for insight in analysis.insights[:3]:
            lines.append(f"- {insight}\n")
    else:
        us_pct = round(analysis.us_jobs / analysis.total_jobs * 100) if analysis.total_jobs else 0
        lines += [
            f"- US market: **{analysis.us_jobs:,} jobs** ({us_pct}% of total)\n",
            f"- India market: **{analysis.india_jobs:,} jobs** ({round(analysis.india_jobs / analysis.total_jobs * 100) if analysis.total_jobs else 0}% of total)\n",
        ]

    if analysis.role_stats:
        top_role = max(analysis.role_stats, key=lambda r: r.total_count)
        lines.append(f"- Most in-demand role: **{top_role.category}** ({top_role.total_count:,} openings)\n")

    if analysis.top_skills:
        top3 = ", ".join(f"**{s.skill}**" for s in analysis.top_skills[:3])
        lines.append(f"- Top skills: {top3}\n")

    lines.append("\n---\n")

    # ── 2. Region Split
    lines += [
        "## 2. Total Jobs Found by Region\n\n",
        chart_embed("region_split.png"),
        "\n",
        "| Region | Job Count | % of Total |\n",
        "|--------|----------:|-----------:|\n",
    ]

    total = analysis.total_jobs or 1
    for label, count in [
        ("🇺🇸 United States", analysis.us_jobs),
        ("🇮🇳 India", analysis.india_jobs),
        ("🌍 Other", analysis.other_jobs),
    ]:
        lines.append(f"| {label} | {count:,} | {round(count/total*100, 1)}% |\n")

    lines.append(f"| **Total** | **{analysis.total_jobs:,}** | **100%** |\n")
    lines.append("\n---\n")

    # ── 3. Role Demand Breakdown
    lines += [
        "## 3. Role Demand Breakdown\n\n",
        chart_embed("role_demand.png"),
        "\n",
        "| Role Category | Total | 🇺🇸 US | 🇮🇳 India | Other | Remote% | Hybrid% |\n",
        "|---------------|------:|------:|---------:|------:|--------:|--------:|\n",
    ]

    sorted_roles = sorted(analysis.role_stats, key=lambda r: r.total_count, reverse=True)
    for rs in sorted_roles:
        lines.append(
            f"| {rs.category} | {rs.total_count:,} | {rs.us_count:,} | "
            f"{rs.india_count:,} | {rs.other_count:,} | "
            f"{rs.remote_percentage}% | {rs.hybrid_percentage}% |\n"
        )

    lines.append("\n### Top Skills Per Role\n\n")
    for rs in sorted_roles[:5]:
        if rs.top_skills:
            skills_str = " · ".join(f"`{s}`" for s in rs.top_skills[:8])
            lines.append(f"**{rs.category}:** {skills_str}\n\n")

    lines.append("\n---\n")

    # ── 4. Top Skills
    lines += [
        "## 4. Top Skills in Demand\n\n",
        chart_embed("top_skills.png"),
        "\n",
        "| Rank | Skill | Mentions | % of Jobs | Top Role Categories |\n",
        "|-----:|-------|--------:|---------:|---------------------|\n",
    ]

    for i, skill in enumerate(analysis.top_skills[:20], 1):
        cats = ", ".join(skill.top_categories[:2]) if skill.top_categories else "—"
        lines.append(
            f"| {i} | **{skill.skill}** | {skill.count:,} | {skill.percentage}% | {cats} |\n"
        )

    lines.append("\n---\n")

    # ── 5. Experience Level Distribution
    lines += [
        "## 5. Experience Level Distribution\n\n",
        chart_embed("experience_distribution.png"),
        "\n",
        "| Experience Level | Count | % |\n",
        "|------------------|------:|--:|\n",
    ]

    for level, count in sorted(
        analysis.experience_distribution.items(), key=lambda x: -x[1]
    ):
        pct = round(count / total * 100, 1)
        lines.append(f"| {level} | {count:,} | {pct}% |\n")

    lines.append("\n---\n")

    # ── 6. Work Mode Distribution
    lines += [
        "## 6. Work Mode Distribution\n\n",
        chart_embed("work_type_distribution.png"),
        "\n",
        "| Work Mode | Count | % |\n",
        "|-----------|------:|--:|\n",
    ]

    for wt, count in sorted(
        analysis.work_type_distribution.items(), key=lambda x: -x[1]
    ):
        pct = round(count / total * 100, 1)
        lines.append(f"| {wt} | {count:,} | {pct}% |\n")

    lines.append("\n**Employment Type Breakdown:**\n\n")
    lines.append("| Employment Type | Count | % |\n")
    lines.append("|-----------------|------:|--:|\n")
    for et, count in sorted(
        analysis.employment_type_distribution.items(), key=lambda x: -x[1]
    ):
        pct = round(count / total * 100, 1)
        lines.append(f"| {et} | {count:,} | {pct}% |\n")

    lines.append("\n---\n")

    # ── 7. Top Hiring Companies
    lines += [
        "## 7. Top Hiring Companies\n\n",
        "| Rank | Company | Open Roles | Remote | Key Role Types |\n",
        "|-----:|---------|----------:|-------:|----------------|\n",
    ]

    for i, company in enumerate(analysis.top_companies[:20], 1):
        cats = ", ".join(company.categories[:3]) if company.categories else "—"
        lines.append(
            f"| {i} | **{company.company_name}** | {company.total_openings:,} | "
            f"{company.remote_count} | {cats} |\n"
        )

    lines.append("\n---\n")

    # ── 8. Quarterly Trends
    lines += [
        "## 8. Quarterly Trends\n\n",
        chart_embed("quarterly_trends.png"),
        "\n",
    ]

    # Table: quarterly totals for "All"
    all_trends = [t for t in analysis.quarterly_trends if t.category == "All"]
    if all_trends:
        sorted_trends = sorted(all_trends, key=lambda t: t.quarter)
        lines += [
            "| Quarter | Total Postings |\n",
            "|---------|---------------:|\n",
        ]
        for t in sorted_trends:
            lines.append(f"| {t.quarter} | {t.count:,} |\n")

    lines.append("\n---\n")

    # ── 9. AI/ML Mention by Role
    lines += [
        "## 9. AI/ML Knowledge Expected by Role\n\n",
        "> Which roles are expecting AI/ML knowledge — even outside core AI/ML job titles?\n\n",
        chart_embed("ai_mention_by_role.png"),
        "\n",
        "| Role Category | Jobs Analyzed | AI/ML Mentions | % Adoption |\n",
        "|---------------|----------:|----------:|----------:|\n",
    ]

    if analysis.ai_mention_by_role:
        # Get total count per role from role_stats for the table
        role_totals = {rs.category: rs.total_count for rs in analysis.role_stats}

        sorted_ai = sorted(
            analysis.ai_mention_by_role.items(),
            key=lambda x: x[1], reverse=True,
        )
        for role, pct in sorted_ai:
            total_c = role_totals.get(role, 0)
            ai_count = round(total_c * pct / 100)
            bar = "🟩" * min(int(pct / 10), 10)
            lines.append(f"| {role} | {total_c:,} | ~{ai_count:,} | {bar} {pct}% |\n")

        # Highlight top finding
        top_role, top_pct = sorted_ai[0]
        lines.append(
            f"\n> 💡 **{top_role}** has the highest AI/ML adoption signal at **{top_pct}%** "
            f"of job postings — meaning employers already expect AI familiarity even in this role.\n"
        )
    else:
        lines.append("*AI/ML mention data not available for this run.*\n")

    lines.append("\n**Keywords detected:** `AI` · `ML` · `LLM` · `GenAI` · `Generative AI` · "
                 "`Machine Learning` · `Deep Learning` · `Neural Network` · `RAG` · "
                 "`Agents` · `AI Agents` · `Foundation Model` · `Prompt` · "
                 "`Vector Database` · `Embeddings`\n")

    lines.append("\n---\n")

    # ── 10. Insights
    lines += [
        "## 10. Observations & Insights\n\n",
    ]

    if analysis.insights:
        for i, insight in enumerate(analysis.insights, 1):
            lines.append(f"**{i}.** {insight}\n\n")
    else:
        lines.append("*Insights not generated — run with an OpenAI API key for LLM-powered insights.*\n")

    lines += [
        "\n---\n",
        f"\n*Report generated by LinkedIn Jobs Research AI Agent on {now}*\n",
        "*Data sourced from LinkedIn public job listings.*\n",
    ]

    return "".join(lines)


# ─────────────────────────────────────────────
# AGENT DEFINITION
# ─────────────────────────────────────────────

def create_report_agent(config: Dict[str, Any]) -> Agent:
    """Create and return the Report Agent."""
    output_cfg = config.get("output", {})
    output_dir = output_cfg.get("directory", "output")

    return Agent(
        name="ReportAgent",
        model=config.get("openai", {}).get("model", "gpt-4o-mini"),
        instructions=f"""
You are the LinkedIn Jobs Report Agent.

Your job is to produce the final deliverables from the analysis:
1. Call save_jobs_json to export raw job data as JSON
2. Call save_jobs_csv to export raw job data as CSV
3. Call generate_charts to create all visualizations
4. Call generate_markdown_report to produce the final report

All output files go in the '{output_dir}/' directory.
Charts go in '{output_dir}/charts/'.

Return a ReportResult with the paths and stats for all generated files.
""",
        tools=[save_jobs_json, save_jobs_csv, generate_charts, generate_markdown_report],
        output_type=ReportResult,
    )


# ─────────────────────────────────────────────
# STANDALONE RUNNER
# ─────────────────────────────────────────────

def run_report(
    batch: ParsedJobBatch,
    analysis: AnalysisResult,
    config: Dict[str, Any],
) -> ReportResult:
    """
    Run the report generation pipeline.

    Args:
        batch: ParsedJobBatch from the Parser Agent
        analysis: AnalysisResult from the Analyst Agent
        config: Application config

    Returns:
        ReportResult with paths to all generated files
    """
    from tools.chart_tool import generate_all_charts

    output_cfg = config.get("output", {})
    output_dir = output_cfg.get("directory", "output")
    charts_dir = output_cfg.get("charts_directory", os.path.join(output_dir, "charts"))
    report_filename = output_cfg.get("report_filename", "linkedin_jobs_report.md")
    json_filename = output_cfg.get("json_filename", "jobs_data.json")
    csv_filename = output_cfg.get("csv_filename", "jobs_data.csv")

    report_path = os.path.join(output_dir, report_filename)
    json_path = os.path.join(output_dir, json_filename)
    csv_path = os.path.join(output_dir, csv_filename)

    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(charts_dir, exist_ok=True)

    console.print(f"\n[bold cyan]Report Agent[/bold cyan] — generating outputs")

    errors = []

    # ── Save JSON
    try:
        import json as _json
        jobs_data = [job.to_dict() for job in batch.jobs]
        with open(json_path, "w", encoding="utf-8") as f:
            _json.dump(jobs_data, f, indent=2, default=str)
        console.print(f"  [green]✓[/green] JSON: {json_path}")
    except Exception as e:
        errors.append(f"JSON export failed: {e}")
        console.print(f"  [red]✗[/red] JSON: {e}")

    # ── Save CSV
    try:
        import pandas as pd
        rows = [job.to_dict() for job in batch.jobs]
        if rows:
            df = pd.DataFrame(rows)
            df.to_csv(csv_path, index=False, encoding="utf-8")
            console.print(f"  [green]✓[/green] CSV: {csv_path}")
    except Exception as e:
        errors.append(f"CSV export failed: {e}")
        console.print(f"  [red]✗[/red] CSV: {e}")

    # ── Generate charts
    chart_paths = []
    try:
        chart_paths = generate_all_charts(analysis.model_dump(), charts_dir)
        console.print(f"  [green]✓[/green] Charts: {len(chart_paths)} generated in {charts_dir}")
    except Exception as e:
        errors.append(f"Chart generation failed: {e}")
        console.print(f"  [red]✗[/red] Charts: {e}")

    # ── Generate Markdown report
    try:
        content = _build_markdown_report(analysis, chart_paths, charts_dir)
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(content)
        console.print(f"  [green]✓[/green] Report: {report_path}")
    except Exception as e:
        errors.append(f"Markdown report failed: {e}")
        console.print(f"  [red]✗[/red] Report: {e}")
        return ReportResult(
            report_path=report_path,
            json_path=json_path,
            csv_path=csv_path,
            success=False,
            error_message=str(e),
        )

    return ReportResult(
        report_path=report_path,
        json_path=json_path,
        csv_path=csv_path,
        charts_generated=chart_paths,
        total_jobs_in_report=batch.total_parsed,
        success=True,
    )
