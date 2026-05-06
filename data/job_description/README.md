# Tech Job Descriptions — Data Collection & Analysis

This directory contains job market data and analysis notebooks for **4 countries** plus a combined global analysis.

---

## Directory Structure

```
job_description/
├── vn/                         <- Vietnam
│   ├── vn_jobs_raw.csv
│   ├── vn_jobs_final.csv
│   ├── vn_jobs_cleaning.ipynb
│   └── vn_jobs_analysis.ipynb
├── singapore/                  <- Singapore
│   ├── sg_jobs_raw.csv
│   ├── sg_jobs_final.csv
│   ├── sg_jobs_cleaning.ipynb
│   └── sg_jobs_analysis.ipynb
├── uk/                         <- United Kingdom
│   ├── uk_jobs_raw.csv
│   ├── uk_jobs_final.csv
│   ├── uk_jobs_cleaning.ipynb
│   └── uk_jobs_analysis.ipynb
├── us/                         <- United States (includes pipeline code)
│   ├── main.py
│   ├── config.py
│   ├── crawlers/
│   ├── dedup/
│   ├── parser/
│   ├── utils/
│   ├── data/
│   │   ├── us_jobs_raw.csv
│   │   ├── us_jobs_parsed.csv
│   │   └── us_jobs_final.csv
│   ├── us_jobs_cleaning.ipynb
│   └── us_jobs_analysis.ipynb
└── global/                     <- Combined all-country analysis
    ├── all_jobs_final.csv
    └── global_analysis.ipynb
```

---

## Data Pipeline

Each country follows the same 5-step pipeline:

```
Crawl  ->  Dedup  ->  LLM Parse  ->  Clean  ->  Analyze
```

### Step 1 — Crawl
Collects tech job listings using 18 keywords: `software engineer`, `data scientist`, `devops engineer`, `machine learning engineer`, etc.

- **Vietnam / Singapore / UK**: LinkedIn (Playwright headless browser)
- **United States**: LinkedIn + USAJobs API

### Step 2 — Semantic Deduplication
Removes near-duplicate listings using Google `gemini-embedding-001` embeddings.
Threshold: cosine similarity >= 0.92 and description overlap >= 55%.

### Step 3 — LLM Parsing
Extracts structured fields from raw job descriptions using **Gemini 2.5 Pro**:

| Field | Description |
|-------|-------------|
| `parsed_title` | Standardized job title |
| `seniority` | junior / mid / senior / lead / intern |
| `min_years_exp` | Minimum years of experience required |
| `employment_type` | full-time / contract / part-time |
| `remote_status` | remote / hybrid / onsite |
| `salary_min_annual` | Minimum annual salary (USD equivalent) |
| `salary_max_annual` | Maximum annual salary |
| `hard_skills` | Technical skills (comma-separated) |
| `soft_skills` | Soft skills (comma-separated) |
| `education` | bachelor / master / phd / none |
| `job_category` | software-engineering / data-science / devops / … |

### Step 4 — Cleaning (`*_jobs_cleaning.ipynb`)
Standardizes data across all countries into a unified 19-column schema:

`job_id, source, country, url, job_title, parsed_title, company, location, posted_date, seniority, min_years_exp, employment_type, remote_status, salary_min_annual, salary_max_annual, hard_skills, soft_skills, education, job_category`

### Step 5 — Analysis (`*_jobs_analysis.ipynb`)
Identical structure for all 4 countries:

| # | Section |
|---|---------|
| 1 | Dataset overview |
| 2 | Job titles & category distribution |
| 3 | Hard skills — overall |
| 4 | Most in-demand & essential skills |
| 5 | Hard skills by seniority level |
| 6 | Soft skills |
| 7 | Category signature skills |
| 8 | Skills co-occurrence heatmap |
| 9 | Location & remote trends |

---

## Global Analysis (`global/global_analysis.ipynb`)

Cross-country skill comparison using `global/all_jobs_final.csv` (6,071 jobs total).

| # | Section |
|---|---------|
| 1 | Dataset overview by country |
| 2 | Top hard skills by country — mention rate heatmap |
| 3 | Most essential skills globally |
| 4 | Country-exclusive skills |
| 5 | Hard skills by category — cross-country comparison |
| 6 | Skill vocabulary overlap (Jaccard similarity) |
| 7 | Skill gap — where countries differ most |
| 8 | Soft skills by country |
| 9 | Country skill uniqueness (lift vs global average) |

---

## Dataset Summary

| Country | Raw jobs | Final jobs | Source |
|---------|----------|------------|--------|
| Vietnam | ~1,107 | 982 | LinkedIn |
| Singapore | ~1,506 | 1,445 | LinkedIn |
| United Kingdom | ~1,706 | 1,637 | LinkedIn |
| United States | ~2,445 | 2,007 | LinkedIn + USAJobs |
| **Global** | — | **6,071** | All combined |

---

## How to Run (US pipeline)

The pipeline code lives in `us/`. Other countries use the same codebase pointed at different locations.

```bash
cd us/

# Full pipeline (crawl + dedup + parse)
python main.py

# Skip crawling, re-process existing raw data
python main.py --parse-only

# Crawl + dedup only, skip LLM parsing
python main.py --crawl-only
```

Required `.env` file in `us/`:
```
USAJOBS_API_KEY=your_key
USAJOBS_EMAIL=your_email
GOOGLE_API_KEY=your_key
LLM_MODEL=gemini-2.5-pro
EMBED_MODEL=gemini-embedding-001
CRAWL_LOCATIONS=United States
OUTPUT_DIR=data/
```

```bash
pip install -r us/requirements.txt
```
