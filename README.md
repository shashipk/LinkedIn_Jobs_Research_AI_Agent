# 🤖 LinkedIn Jobs Research AI Agent

> A production-ready multi-agent pipeline that scrapes, parses, analyzes, and reports on LinkedIn job postings — powered by the **OpenAI Agents SDK**.

[![Python](https://img.shields.io/badge/Python-3.11%2B-blue?logo=python)](https://www.python.org/)
[![OpenAI Agents SDK](https://img.shields.io/badge/OpenAI%20Agents%20SDK-0.0.9%2B-green?logo=openai)](https://github.com/openai/openai-agents-python)
[![uv](https://img.shields.io/badge/package%20manager-uv-purple)](https://github.com/astral-sh/uv)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## 📋 Table of Contents

- [What It Does](#-what-it-does)
- [Pipeline Architecture](#-pipeline-architecture)
- [Project Structure](#-project-structure)
- [Prerequisites](#-prerequisites)
- [Installation](#-installation)
- [API Keys Setup](#-api-keys-setup)
- [Configuration](#-configuration)
- [Running the Agent](#-running-the-agent)
- [Output Files](#-output-files)
- [Report Sections](#-report-sections)
- [Data Model](#-data-model)
- [Troubleshooting](#-troubleshooting)
- [Contributing](#-contributing)
- [License](#-license)

---

## ✨ What It Does

This agent automatically:

1. **Scrapes** live job postings from LinkedIn (via Playwright browser automation or SerpAPI)
2. **Parses** raw HTML/JSON into structured data — titles, companies, skills, locations, experience levels
3. **Analyzes** the data — role demand, top skills, work-type trends, hiring companies, regional splits
4. **Generates** a full Markdown report + 6 charts + CSV/JSON exports

**Use cases:**
- Understand which tech roles are in highest demand
- See which skills are most requested across thousands of real job listings
- Compare US vs India job markets
- Track hiring trends over the last 24 months
- Research before a job search or career pivot

---

## 🏗 Pipeline Architecture

```
main.py (orchestrator)
  │
  ├── 1. Scraper Agent    ← Collects raw job pages
  │       └── pipeline/scraper_agent.py
  │           ├── Mode A: Playwright (browser automation, stealth)
  │           └── Mode B: SerpAPI (Google Jobs API — recommended)
  │
  ├── 2. Parser Agent     ← Extracts structured data from raw pages
  │       └── pipeline/parser_agent.py + tools/parser_tool.py
  │
  ├── 3. Analyst Agent    ← Computes stats + generates LLM insights
  │       └── pipeline/analyst_agent.py
  │
  └── 4. Report Agent     ← Writes report, charts, CSV, JSON
          └── pipeline/report_agent.py + tools/chart_tool.py
```

**Framework:** [OpenAI Agents SDK](https://github.com/openai/openai-agents-python) &nbsp;|&nbsp; **Package Manager:** [uv](https://github.com/astral-sh/uv)

---

## 📁 Project Structure

```
linkedin_jobs_agent/
├── main.py                    # Entry point & CLI
├── config.yaml                # All settings (roles, locations, API keys, etc.)
├── pyproject.toml             # Dependencies (managed by uv)
│
├── pipeline/
│   ├── scraper_agent.py       # Playwright + SerpAPI scraper
│   ├── parser_agent.py        # HTML/JSON → JobPosting objects
│   ├── analyst_agent.py       # Stats aggregation + LLM insights
│   └── report_agent.py        # Report builder + chart exporter
│
├── tools/
│   ├── browser_tool.py        # Playwright stealth browser wrapper
│   ├── parser_tool.py         # BeautifulSoup + SerpAPI JSON parsers
│   └── chart_tool.py          # Matplotlib chart generators (6 chart types)
│
├── models/
│   └── job_schema.py          # Pydantic v2 models for all data structures
│
└── output/                    # Auto-generated (git-ignored)
    ├── linkedin_jobs_report.md
    ├── jobs_data.json
    ├── jobs_data.csv
    └── charts/
        ├── role_demand.png
        ├── top_skills.png
        ├── experience_distribution.png
        ├── work_type_distribution.png
        ├── quarterly_trends.png
        └── region_split.png
```

---

## ✅ Prerequisites

Before you start, make sure you have:

| Requirement | Version | Notes |
|---|---|---|
| **Python** | 3.11 or higher | [Download](https://www.python.org/downloads/) |
| **uv** | latest | Fast Python package manager (replaces pip + venv) |
| **OpenAI API Key** | — | Required for analysis & insights |
| **SerpAPI Key** | — | Required only for `--mode serpapi` (recommended) |

> **Don't have uv?** Install it in one command — see [Installation](#-installation) step 1.

---

## 🚀 Installation

### Step 1 — Install `uv` (package manager)

**macOS / Linux:**
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**Windows (PowerShell):**
```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

After installing, restart your terminal, then verify:
```bash
uv --version
```

---

### Step 2 — Clone the repository

```bash
git clone https://github.com/shashipk/linkedin-jobs-agent.git
cd linkedin-jobs-agent
```

---

### Step 3 — Install Python dependencies

```bash
uv sync
```

This creates a virtual environment (`.venv/`) and installs all packages from `pyproject.toml` automatically. No need to run `pip install` manually.

---

### Step 4 — Install Playwright browsers

```bash
uv run playwright install chromium
```

> This downloads the Chromium browser used for LinkedIn scraping. Only needed for Playwright mode.

---

## 🔑 API Keys Setup

### OpenAI API Key (Required)

The agent uses OpenAI for LLM-powered insights in the Analyst step.

1. Go to [platform.openai.com/api-keys](https://platform.openai.com/api-keys)
2. Create a new key
3. Set it as an environment variable:

**macOS / Linux:**
```bash
export OPENAI_API_KEY="sk-..."
```

**Windows (Command Prompt):**
```cmd
set OPENAI_API_KEY=sk-...
```

**Windows (PowerShell):**
```powershell
$env:OPENAI_API_KEY = "sk-..."
```

> 💡 **Tip:** Add the export line to your `~/.zshrc` or `~/.bashrc` to avoid re-entering it every session.

---

### SerpAPI Key (Required for `serpapi` mode — Recommended)

SerpAPI is the most reliable way to collect real job data. It queries Google Jobs and returns clean structured results.

1. Sign up at [serpapi.com](https://serpapi.com/) — free plan gives **100 searches/month**
2. Copy your API key from the dashboard
3. Set it via environment variable **or** in `config.yaml`:

**Option A — Environment variable (recommended, keeps key out of code):**
```bash
export SERPAPI_API_KEY="your_key_here"
```

**Option B — Directly in `config.yaml`:**
```yaml
data_source:
  serpapi:
    api_key: "your_key_here"
```

> ⚠️ **Security:** Never commit your API key to Git. The `.gitignore` already excludes `.env` files. Use environment variables when possible.

---

## ⚙️ Configuration

All settings live in `config.yaml`. Open it and customize before running.

### Key Settings

#### Data Source
```yaml
data_source:
  mode: "serpapi"      # "serpapi" (recommended) or "playwright"
  serpapi:
    api_key: "PASTE_YOUR_SERPAPI_KEY_HERE"  # or use SERPAPI_API_KEY env var
    pages_per_query: 3  # Each page ≈ 10 jobs, costs 1 API credit
```

**How many jobs will I get?**

| `pages_per_query` | Approx. Jobs | API Credits Used | Plan Needed |
|---|---|---|---|
| `1` | ~245 jobs | ~26 credits | Free plan ✅ |
| `3` | ~600 jobs | ~78 credits | Free plan ✅ |
| `5` | ~900 jobs | ~130 credits | Free plan limit ⚠️ |
| `10` | ~1,500 jobs | ~260 credits | Paid plan ($50/mo) |

> Formula: `roles × locations × pages_per_query = total credits`

---

#### Job Roles to Search
```yaml
search:
  roles:
    - "Software Engineer"
    - "Machine Learning Engineer"
    - "Data Scientist"
    - "DevOps Engineer"
    # Add or remove roles as needed
```

---

#### Locations
```yaml
search:
  locations:
    # Country-level (works on free plan)
    - name: "United States"
    - name: "India"

    # City-level (uncomment for more diverse results — uses more credits)
    # - name: "San Francisco, California"
    # - name: "New York, New York"
    # - name: "Bengaluru, Karnataka, India"
```

---

#### OpenAI Model
```yaml
openai:
  model: "gpt-4o-mini"          # Used by Parser Agent
  analyst_model: "gpt-4o-mini"  # Used by Analyst Agent
  temperature: 0.2
  max_tokens: 65536
```

---

## ▶️ Running the Agent

### Quick Test (No API keys needed)
```bash
uv run python main.py --demo
```
Runs the full pipeline on **1,000 synthetic jobs** — great for testing the setup before spending API credits.

---

### Real Run with SerpAPI (Recommended)
```bash
export OPENAI_API_KEY="sk-..."
export SERPAPI_API_KEY="your_serpapi_key"

uv run python main.py --mode serpapi
```

---

### Real Run with Playwright (LinkedIn direct scraping)
```bash
export OPENAI_API_KEY="sk-..."

uv run python main.py --mode playwright
```

> ⚠️ LinkedIn may block automated browsers. If you see CAPTCHAs, switch to `--mode serpapi`.

---

### All CLI Options

```bash
uv run python main.py [OPTIONS]
```

| Flag | Default | Description |
|---|---|---|
| `--demo` | off | Run with synthetic data (no API keys needed) |
| `--mode` | from config | `serpapi` or `playwright` |
| `--config` | `config.yaml` | Path to a custom config file |
| `--output` | `output/` | Directory to save results |
| `--max-pages` | from config | Override `pages_per_query` at runtime |

**Examples:**
```bash
# Demo mode — test the pipeline
uv run python main.py --demo

# SerpAPI with 5 pages per query
uv run python main.py --mode serpapi --max-pages 5

# Custom config file
uv run python main.py --config my_custom_config.yaml

# Custom output directory
uv run python main.py --output ./results/run1
```

---

## 📊 Output Files

After a successful run, the `output/` folder contains:

| File | Description |
|---|---|
| `linkedin_jobs_report.md` | Full research report in Markdown |
| `jobs_data.json` | All parsed job postings (structured JSON) |
| `jobs_data.csv` | Flat CSV — open in Excel / Google Sheets |
| `charts/role_demand.png` | Bar chart: job count by role + region |
| `charts/top_skills.png` | Top 20 in-demand skills |
| `charts/experience_distribution.png` | Entry / Mid / Senior / Staff split |
| `charts/work_type_distribution.png` | Remote / Hybrid / Onsite split |
| `charts/quarterly_trends.png` | Posting trends over last 24 months |
| `charts/region_split.png` | US vs India vs Other |

### Viewing the Markdown Report

**Option 1 — VS Code:**
Open `linkedin_jobs_report.md` → press `Cmd+Shift+V` (Mac) or `Ctrl+Shift+V` (Windows)

**Option 2 — Convert to HTML and open in browser:**
```bash
uv run python -c "
import markdown, pathlib
md = pathlib.Path('output/linkedin_jobs_report.md').read_text()
html = '<meta charset=utf-8>' + markdown.markdown(md, extensions=['tables','fenced_code'])
pathlib.Path('output/report.html').write_text(html)
print('Saved → output/report.html')
"
open output/report.html   # macOS
# xdg-open output/report.html   # Linux
# start output/report.html      # Windows
```

---

## 📄 Report Sections

The generated report includes:

1. **Executive Summary** — total jobs found, date range, data source, top highlights
2. **Total Jobs by Region** — US vs India vs Other breakdown
3. **Role Demand Breakdown** — table + chart showing which roles are most in demand
4. **Top 20 Skills in Demand** — extracted from job titles and descriptions
5. **Experience Level Distribution** — Entry / Mid / Senior / Staff / Principal
6. **Work Mode Distribution** — Remote / Hybrid / Onsite percentages
7. **Top Hiring Companies** — top 20 companies by number of open roles
8. **Quarterly Trends** — job posting volume by quarter over 24 months
9. **Observations & Insights** — LLM-generated market analysis

---

## 🗂 Data Model

Each scraped job is stored as a `JobPosting` object:

```python
JobPosting(
    job_id: str,
    title: str,                          # Raw job title from listing
    normalized_category: RoleCategory,   # ML/AI, Backend, Frontend, DevOps, etc.
    company_name: str,
    company_size: str | None,
    location_raw: str,
    location_city: str | None,
    location_country: str | None,
    region: Region,                      # US | India | Other
    work_type: WorkType,                 # Remote | Hybrid | Onsite
    date_posted: datetime | None,
    required_skills: list[str],          # Extracted from title + description
    experience_level: ExperienceLevel,   # Entry | Mid | Senior | Staff | Principal
    employment_type: EmploymentType,     # Full-time | Contract | Part-time
    source_url: str,
    search_query: str,
    search_location: str,
)
```

---

## 🔧 Troubleshooting

### `ModuleNotFoundError: No module named 'agents'`
```bash
uv sync
```
Re-runs dependency installation. All packages will be installed into the `.venv/` folder.

---

### `playwright._impl._errors.Error: Executable doesn't exist`
```bash
uv run playwright install chromium
```

---

### LinkedIn blocks scraping / CAPTCHA detected
- Switch to SerpAPI mode: `uv run python main.py --mode serpapi`
- Or try running with a visible browser: set `headless: false` in `config.yaml`
- Increase delay: raise `min_delay` and `max_delay` in `config.yaml`

---

### SerpAPI returns 0 results
- Make sure your key is valid and not expired
- Check you have remaining credits at [serpapi.com/dashboard](https://serpapi.com/dashboard)
- Make sure `SERPAPI_API_KEY` env var is set (takes priority over config.yaml)
- Try: `uv run python main.py --demo` to verify the rest of the pipeline works

---

### OpenAI API errors
- Verify `OPENAI_API_KEY` is set: `echo $OPENAI_API_KEY`
- Check you have API credits at [platform.openai.com/usage](https://platform.openai.com/usage)
- The pipeline still runs without an API key — insights section will be skipped

---

### `uv: command not found`
Re-install uv and restart your terminal:
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
source ~/.zshrc   # or source ~/.bashrc
```

---

### Virtual environment issues
```bash
rm -rf .venv
uv sync
```

---

## 🤝 Contributing

Contributions are welcome!

1. Fork the repo
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Make your changes
4. Run linting: `uv run ruff check .`
5. Format code: `uv run black .`
6. Commit: `git commit -m "feat: describe your change"`
7. Push and open a Pull Request

---

## 📜 License

MIT — free to use, modify, and distribute.

---

## 🙏 Acknowledgements

- [OpenAI Agents SDK](https://github.com/openai/openai-agents-python) — multi-agent framework
- [SerpAPI](https://serpapi.com/) — Google Jobs data
- [Playwright](https://playwright.dev/) — browser automation
- [uv](https://github.com/astral-sh/uv) — blazing fast Python package manager
- [Rich](https://github.com/Textualize/rich) — beautiful terminal output
