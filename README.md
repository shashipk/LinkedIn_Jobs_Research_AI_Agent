# LinkedIn Jobs Research AI Agent

A production-ready multi-agent pipeline that scrapes and analyzes LinkedIn job postings to generate a comprehensive demand report for tech roles globally, with focus on the US and India markets.

## Architecture

```
main.py
  │
  ├── Scraper Agent    ← Playwright browser automation (LinkedIn public pages)
  │       └── pipeline/scraper_agent.py + tools/browser_tool.py
  │
  ├── Parser Agent     ← HTML extraction → structured Pydantic models
  │       └── pipeline/parser_agent.py + tools/parser_tool.py
  │
  ├── Analyst Agent    ← Aggregation, trend detection, LLM insights
  │       └── pipeline/analyst_agent.py
  │
  └── Report Agent     ← Markdown report + charts + JSON/CSV exports
          └── pipeline/report_agent.py + tools/chart_tool.py
```

**Framework:** [OpenAI Agents SDK](https://github.com/openai/openai-agents-python)
**Package Manager:** [uv](https://github.com/astral-sh/uv)

## Project Structure

```
linkedin_jobs_agent/
├── main.py                    # Entry point, orchestrates agents
├── config.yaml                # All configurable parameters
├── pipeline/
│   ├── scraper_agent.py       # Playwright + SerpAPI fallback
│   ├── parser_agent.py        # HTML → JobPosting objects
│   ├── analyst_agent.py       # Statistics + LLM insights
│   └── report_agent.py        # Markdown + charts + exports
├── tools/
│   ├── browser_tool.py        # Playwright stealth wrapper
│   ├── parser_tool.py         # BeautifulSoup utilities
│   └── chart_tool.py          # Matplotlib chart generators
├── models/
│   └── job_schema.py          # Pydantic models for all data
├── output/                    # Generated reports (git-ignored)
│   ├── linkedin_jobs_report.md
│   ├── jobs_data.json
│   ├── jobs_data.csv
│   └── charts/
└── pyproject.toml
```

## Quick Start

### 1. Install uv

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### 2. Install dependencies

```bash
cd linkedin_jobs_agent
uv sync
```

### 3. Install Playwright browsers

```bash
uv run playwright install chromium
# Or for all browsers:
uv run playwright install
```

### 4. Set environment variables

```bash
export OPENAI_API_KEY="sk-..."          # Required for analysis & insights
export SERPAPI_API_KEY="..."            # Optional: only if using SerpAPI mode
```

### 5. Run the pipeline

```bash
# Full run with LinkedIn scraping
uv run python main.py

# Demo mode (no scraping, uses synthetic data — great for testing)
uv run python main.py --demo

# Use SerpAPI instead of Playwright
uv run python main.py --mode serpapi

# Custom config
uv run python main.py --config my_config.yaml --max-pages 3
```

## Configuration

Edit `config.yaml` to control:

| Section | Key | Description |
|---------|-----|-------------|
| `data_source.mode` | `playwright` / `serpapi` | Data collection backend |
| `scraper.max_pages` | int | Pages per search query (LinkedIn = 25 jobs/page) |
| `scraper.min_delay` / `max_delay` | float | Random delay range between requests (seconds) |
| `scraper.headless` | bool | Run browser in headless mode |
| `search.roles` | list | Job titles to search |
| `search.locations` | list | Locations (US, India, etc.) |
| `openai.model` | string | Model for parsing agent |
| `openai.analyst_model` | string | Model for analysis + insights |

## Output

After a successful run, the `output/` directory contains:

| File | Description |
|------|-------------|
| `linkedin_jobs_report.md` | Full markdown report with embedded charts |
| `jobs_data.json` | All parsed job postings (structured JSON) |
| `jobs_data.csv` | Flat CSV for spreadsheet analysis |
| `charts/role_demand.png` | Bar chart: jobs by role category + region |
| `charts/top_skills.png` | Horizontal bar: top 20 skills |
| `charts/experience_distribution.png` | Pie: entry/mid/senior/staff split |
| `charts/work_type_distribution.png` | Donut: remote/hybrid/onsite split |
| `charts/quarterly_trends.png` | Line chart: posting trends over 24 months |
| `charts/region_split.png` | Bar: US vs India vs Other |

## Report Sections

1. **Executive Summary** — key stats and top highlights
2. **Total Jobs Found by Region** — US vs India vs Other
3. **Role Demand Breakdown** — table + chart per role category
4. **Top Skills in Demand** — top 20 skills with frequency
5. **Experience Level Distribution** — entry/mid/senior/staff/principal
6. **Work Mode Distribution** — remote/hybrid/onsite percentages
7. **Top Hiring Companies** — top 20 companies by open roles
8. **Quarterly Trends** — last 24 months, broken into quarters
9. **Observations & Insights** — LLM-generated market analysis

## Anti-Bot Measures

The scraper uses multiple techniques to avoid detection:

- **Stealth mode** via `playwright-stealth` (overrides `navigator.webdriver`)
- **Randomized delays** (2–5 seconds, configurable) between requests
- **User agent rotation** via `fake-useragent` library
- **Real browser headers** (Accept-Language, Sec-Fetch-*, etc.)
- **Human-like scrolling** behavior before content capture
- **Exponential backoff** on rate limiting
- **CAPTCHA detection** — logs and skips affected queries gracefully

## SerpAPI Fallback

If LinkedIn blocks scraping, switch to SerpAPI:

```yaml
# config.yaml
data_source:
  mode: "serpapi"
  serpapi:
    api_key: "your_key_here"  # or set SERPAPI_API_KEY env var
```

Or via CLI:
```bash
uv run python main.py --mode serpapi
```

## Troubleshooting

**`ModuleNotFoundError: No module named 'agents'`**
Run `uv sync` to install all dependencies.

**`playwright._impl._errors.Error: Executable doesn't exist`**
Run `uv run playwright install chromium`.

**LinkedIn CAPTCHA / blocked immediately**
- Try `headless: false` in config.yaml to run with a visible browser
- Reduce request frequency with higher `min_delay`/`max_delay`
- Switch to `mode: serpapi` as fallback

**No jobs parsed (0 results)**
- LinkedIn frequently changes their HTML structure
- Run `uv run python main.py --demo` to test the rest of the pipeline
- Check `output/agent.log` for detailed error messages

**OpenAI API errors**
- Verify `OPENAI_API_KEY` is set correctly
- The pipeline still works without an API key (insights section will be limited)

## Development

```bash
# Run tests
uv run pytest tests/ -v

# Format code
uv run black .

# Lint
uv run ruff check .
```

## Data Model

Each scraped job contains:

```python
JobPosting(
    job_id: str,
    title: str,                          # Raw title
    normalized_category: RoleCategory,   # ML/AI, Backend, Frontend, etc.
    company_name: str,
    company_size: str | None,
    location_raw: str,
    location_city: str | None,
    location_country: str | None,
    region: Region,                      # US | India | Other
    work_type: WorkType,                 # Remote | Hybrid | Onsite
    date_posted: datetime | None,
    required_skills: list[str],          # Extracted from title/description
    experience_level: ExperienceLevel,   # Entry | Mid | Senior | Staff | Principal
    employment_type: EmploymentType,     # Full-time | Contract | Part-time
    source_url: str,
    search_query: str,
    search_location: str,
)
```

## License

MIT
