"""
Visualization utilities for generating charts from analysis results.
Uses matplotlib for static charts saved to PNG files.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from rich.console import Console

console = Console()


def _setup_matplotlib():
    import matplotlib
    matplotlib.use("Agg")  # Non-interactive backend
    import matplotlib.pyplot as plt
    import matplotlib.ticker as mticker

    plt.rcParams.update({
        "figure.facecolor": "white",
        "axes.facecolor": "#f8f9fa",
        "axes.grid": True,
        "grid.color": "#dee2e6",
        "grid.linewidth": 0.5,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "font.family": "DejaVu Sans",
        "font.size": 11,
        "axes.titlesize": 13,
        "axes.titleweight": "bold",
        "figure.dpi": 120,
    })
    return plt, mticker


# ─────────────────────────────────────────────
# COLOR PALETTE
# ─────────────────────────────────────────────

COLORS = {
    "primary": "#2563EB",
    "secondary": "#7C3AED",
    "success": "#059669",
    "warning": "#D97706",
    "danger": "#DC2626",
    "info": "#0891B2",
    "palette": [
        "#2563EB", "#7C3AED", "#059669", "#D97706",
        "#DC2626", "#0891B2", "#DB2777", "#65A30D",
        "#EA580C", "#0369A1",
    ],
    "us": "#2563EB",
    "india": "#F97316",
    "other": "#6B7280",
}


# ─────────────────────────────────────────────
# CHART: ROLE DEMAND BAR CHART
# ─────────────────────────────────────────────

def chart_role_demand(
    role_stats: List[Dict],
    output_dir: str,
    filename: str = "role_demand.png",
) -> Optional[str]:
    """Bar chart showing total job counts per role category."""
    plt, mticker = _setup_matplotlib()

    if not role_stats:
        console.print("[yellow]No role stats for chart[/yellow]")
        return None

    # Sort by total count descending
    sorted_stats = sorted(role_stats, key=lambda x: x.get("total_count", 0), reverse=True)
    categories = [s["category"] for s in sorted_stats]
    us_counts = [s.get("us_count", 0) for s in sorted_stats]
    india_counts = [s.get("india_count", 0) for s in sorted_stats]
    other_counts = [s.get("other_count", 0) for s in sorted_stats]

    x = range(len(categories))
    width = 0.27

    fig, ax = plt.subplots(figsize=(14, 7))

    bars1 = ax.bar([i - width for i in x], us_counts, width, label="United States", color=COLORS["us"], alpha=0.9)
    bars2 = ax.bar(x, india_counts, width, label="India", color=COLORS["india"], alpha=0.9)
    bars3 = ax.bar([i + width for i in x], other_counts, width, label="Other", color=COLORS["other"], alpha=0.9)

    ax.set_xlabel("Role Category", fontsize=12)
    ax.set_ylabel("Number of Job Postings", fontsize=12)
    ax.set_title("Tech Role Demand by Category and Region", fontsize=14, fontweight="bold")
    ax.set_xticks(list(x))
    ax.set_xticklabels(categories, rotation=35, ha="right", fontsize=10)
    ax.legend(framealpha=0.9)
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"{int(v):,}"))

    # Add value labels on top of bars
    for bars in [bars1, bars2, bars3]:
        for bar in bars:
            height = bar.get_height()
            if height > 0:
                ax.annotate(
                    f"{int(height):,}",
                    xy=(bar.get_x() + bar.get_width() / 2, height),
                    xytext=(0, 3),
                    textcoords="offset points",
                    ha="center", va="bottom",
                    fontsize=8,
                )

    fig.tight_layout()
    output_path = os.path.join(output_dir, filename)
    fig.savefig(output_path, bbox_inches="tight")
    plt.close(fig)
    console.print(f"[green]Chart saved:[/green] {output_path}")
    return output_path


# ─────────────────────────────────────────────
# CHART: TOP SKILLS
# ─────────────────────────────────────────────

def chart_top_skills(
    skills: List[Dict],
    output_dir: str,
    top_n: int = 20,
    filename: str = "top_skills.png",
) -> Optional[str]:
    """Horizontal bar chart for top N skills by frequency."""
    plt, mticker = _setup_matplotlib()

    if not skills:
        return None

    top = skills[:top_n]
    skill_names = [s["skill"] for s in reversed(top)]
    counts = [s["count"] for s in reversed(top)]

    fig, ax = plt.subplots(figsize=(12, 9))

    colors = [COLORS["palette"][i % len(COLORS["palette"])] for i in range(len(skill_names))]
    bars = ax.barh(skill_names, counts, color=colors, alpha=0.88)

    ax.set_xlabel("Number of Mentions", fontsize=12)
    ax.set_title(f"Top {top_n} In-Demand Tech Skills", fontsize=14, fontweight="bold")
    ax.xaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"{int(v):,}"))

    for bar, count in zip(bars, counts):
        ax.text(
            bar.get_width() + max(counts) * 0.005,
            bar.get_y() + bar.get_height() / 2,
            f"{count:,}",
            va="center", ha="left",
            fontsize=9,
        )

    fig.tight_layout()
    output_path = os.path.join(output_dir, filename)
    fig.savefig(output_path, bbox_inches="tight")
    plt.close(fig)
    console.print(f"[green]Chart saved:[/green] {output_path}")
    return output_path


# ─────────────────────────────────────────────
# CHART: EXPERIENCE LEVEL PIE
# ─────────────────────────────────────────────

def chart_experience_distribution(
    distribution: Dict[str, int],
    output_dir: str,
    filename: str = "experience_distribution.png",
) -> Optional[str]:
    """Pie chart for experience level distribution."""
    plt, _ = _setup_matplotlib()

    if not distribution:
        return None

    labels = list(distribution.keys())
    sizes = list(distribution.values())
    colors = COLORS["palette"][:len(labels)]

    fig, ax = plt.subplots(figsize=(9, 7))
    wedges, texts, autotexts = ax.pie(
        sizes,
        labels=labels,
        autopct="%1.1f%%",
        colors=colors,
        startangle=140,
        pctdistance=0.82,
        wedgeprops={"edgecolor": "white", "linewidth": 2},
    )

    for text in autotexts:
        text.set_fontsize(10)

    ax.set_title("Experience Level Distribution", fontsize=14, fontweight="bold")
    fig.tight_layout()
    output_path = os.path.join(output_dir, filename)
    fig.savefig(output_path, bbox_inches="tight")
    plt.close(fig)
    console.print(f"[green]Chart saved:[/green] {output_path}")
    return output_path


# ─────────────────────────────────────────────
# CHART: WORK TYPE PIE
# ─────────────────────────────────────────────

def chart_work_type_distribution(
    distribution: Dict[str, int],
    output_dir: str,
    filename: str = "work_type_distribution.png",
) -> Optional[str]:
    """Donut chart for remote/hybrid/onsite split."""
    plt, _ = _setup_matplotlib()

    if not distribution:
        return None

    labels = list(distribution.keys())
    sizes = list(distribution.values())
    work_colors = {
        "Remote": "#059669",
        "Hybrid": "#2563EB",
        "Onsite": "#D97706",
        "Not Specified": "#9CA3AF",
    }
    colors = [work_colors.get(l, "#6B7280") for l in labels]

    fig, ax = plt.subplots(figsize=(8, 7))
    wedges, texts, autotexts = ax.pie(
        sizes,
        labels=labels,
        autopct="%1.1f%%",
        colors=colors,
        startangle=90,
        pctdistance=0.75,
        wedgeprops={"edgecolor": "white", "linewidth": 2.5, "width": 0.6},
    )

    for text in autotexts:
        text.set_fontsize(11)
        text.set_fontweight("bold")

    ax.set_title("Work Mode Distribution (Remote / Hybrid / Onsite)", fontsize=13, fontweight="bold")
    fig.tight_layout()
    output_path = os.path.join(output_dir, filename)
    fig.savefig(output_path, bbox_inches="tight")
    plt.close(fig)
    console.print(f"[green]Chart saved:[/green] {output_path}")
    return output_path


# ─────────────────────────────────────────────
# CHART: QUARTERLY TREND LINE
# ─────────────────────────────────────────────

def chart_quarterly_trends(
    trends: List[Dict],
    output_dir: str,
    filename: str = "quarterly_trends.png",
) -> Optional[str]:
    """Line chart for quarterly job posting trends."""
    plt, _ = _setup_matplotlib()

    if not trends:
        return None

    # Group by category
    from collections import defaultdict

    by_category: Dict[str, Dict[str, int]] = defaultdict(dict)
    all_quarters: set = set()

    for t in trends:
        cat = t.get("category") or "All"
        quarter = t.get("quarter", "")
        count = t.get("count", 0)
        by_category[cat][quarter] = count
        all_quarters.add(quarter)

    sorted_quarters = sorted(all_quarters)
    if not sorted_quarters:
        return None

    fig, ax = plt.subplots(figsize=(14, 7))

    for i, (category, quarter_data) in enumerate(by_category.items()):
        y_vals = [quarter_data.get(q, 0) for q in sorted_quarters]
        color = COLORS["palette"][i % len(COLORS["palette"])]
        ax.plot(sorted_quarters, y_vals, marker="o", linewidth=2, label=category, color=color)
        ax.fill_between(sorted_quarters, y_vals, alpha=0.08, color=color)

    ax.set_xlabel("Quarter", fontsize=12)
    ax.set_ylabel("Job Postings", fontsize=12)
    ax.set_title("Quarterly Job Posting Trends (Last 24 Months)", fontsize=14, fontweight="bold")
    ax.tick_params(axis="x", rotation=45)
    ax.legend(bbox_to_anchor=(1.01, 1), loc="upper left", fontsize=9)
    fig.tight_layout()
    output_path = os.path.join(output_dir, filename)
    fig.savefig(output_path, bbox_inches="tight")
    plt.close(fig)
    console.print(f"[green]Chart saved:[/green] {output_path}")
    return output_path


# ─────────────────────────────────────────────
# CHART: REGION SPLIT
# ─────────────────────────────────────────────

def chart_region_split(
    us: int, india: int, other: int,
    output_dir: str,
    filename: str = "region_split.png",
) -> Optional[str]:
    """Bar chart for US vs India vs Other region split."""
    plt, mticker = _setup_matplotlib()

    regions = ["United States", "India", "Other"]
    counts = [us, india, other]
    colors = [COLORS["us"], COLORS["india"], COLORS["other"]]

    fig, ax = plt.subplots(figsize=(8, 5))
    bars = ax.bar(regions, counts, color=colors, alpha=0.9, width=0.5)

    ax.set_ylabel("Job Postings", fontsize=12)
    ax.set_title("Job Distribution by Region", fontsize=14, fontweight="bold")
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"{int(v):,}"))

    for bar, count in zip(bars, counts):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + max(counts) * 0.01,
            f"{count:,}",
            ha="center", va="bottom",
            fontsize=12, fontweight="bold",
        )

    fig.tight_layout()
    output_path = os.path.join(output_dir, filename)
    fig.savefig(output_path, bbox_inches="tight")
    plt.close(fig)
    console.print(f"[green]Chart saved:[/green] {output_path}")
    return output_path


# ─────────────────────────────────────────────
# BATCH CHART GENERATOR
# ─────────────────────────────────────────────

def generate_all_charts(analysis: dict, output_dir: str) -> List[str]:
    """
    Generate all charts for the report.

    Args:
        analysis: AnalysisResult as dict
        output_dir: Directory to save charts

    Returns:
        List of generated chart file paths
    """
    os.makedirs(output_dir, exist_ok=True)
    generated = []

    try:
        path = chart_role_demand(analysis.get("role_stats", []), output_dir)
        if path:
            generated.append(path)
    except Exception as e:
        console.print(f"[red]role_demand chart error: {e}[/red]")

    try:
        path = chart_top_skills(analysis.get("top_skills", []), output_dir)
        if path:
            generated.append(path)
    except Exception as e:
        console.print(f"[red]top_skills chart error: {e}[/red]")

    try:
        path = chart_experience_distribution(
            analysis.get("experience_distribution", {}), output_dir
        )
        if path:
            generated.append(path)
    except Exception as e:
        console.print(f"[red]experience chart error: {e}[/red]")

    try:
        path = chart_work_type_distribution(
            analysis.get("work_type_distribution", {}), output_dir
        )
        if path:
            generated.append(path)
    except Exception as e:
        console.print(f"[red]work_type chart error: {e}[/red]")

    try:
        path = chart_quarterly_trends(
            analysis.get("quarterly_trends", []), output_dir
        )
        if path:
            generated.append(path)
    except Exception as e:
        console.print(f"[red]quarterly_trends chart error: {e}[/red]")

    try:
        path = chart_region_split(
            analysis.get("us_jobs", 0),
            analysis.get("india_jobs", 0),
            analysis.get("other_jobs", 0),
            output_dir,
        )
        if path:
            generated.append(path)
    except Exception as e:
        console.print(f"[red]region_split chart error: {e}[/red]")

    return generated
