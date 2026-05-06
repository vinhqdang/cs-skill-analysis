# US Tech Jobs — Data Pipeline

Automated pipeline to collect, deduplicate, parse, and analyze US tech job postings from LinkedIn and USAJobs.

---

## Pipeline Overview

```
Crawl  →  Dedup  →  LLM Parse  →  Clean  →  Analyze
```

| Step | Script | Output |
|------|--------|--------|
| 1. Crawl | `main.py` (Phase 1) | `data/us_jobs_raw.csv` |
| 2. Dedup | `dedup/embedding_dedup.py` (Phase 2) | `data/us_jobs_deduped.csv` |
| 3. Parse | `parser/llm_parser.py` (Phase 3) | `data/us_jobs_parsed.csv` |
| 4. Clean | `us_jobs_cleaning.ipynb` | `data/us_jobs_final.csv` |
| 5. Analyze | `us_jobs_analysis.ipynb` | charts only |

---

## Step 1 — Crawl

Scrapes job listings from two sources using 18 tech keywords (`"software engineer"`, `"data scientist"`, `"devops engineer"`, etc.):

| Source | Method |
|--------|--------|
| **LinkedIn** | Playwright headless browser scraping |
| **USAJobs** | Official REST API |

---

## Step 2 — Semantic Deduplication

1. Embeds each job's title + company + location via **Google `gemini-embedding-001`**
2. Cosine similarity >= 0.92 **and** description overlap >= 55% → keep the richer listing, drop the other
3. Embeddings cached to `embed_cache.json` for fast reruns

---

## Step 3 — LLM Parsing

Sends each job description to **Gemini 2.5 Pro** in batches of 10.

Extracted fields:

| Field | Example |
|-------|---------|
| `parsed_title` | "Senior Backend Engineer" |
| `seniority` | senior / mid / junior / intern |
| `min_years_exp` | 3 |
| `employment_type` | full-time / contract / part-time |
| `remote_status` | remote / hybrid / onsite |
| `salary_min_annual` | 120000 |
| `salary_max_annual` | 160000 |
| `hard_skills` | python, aws, docker, kubernetes |
| `soft_skills` | communication, ownership, collaboration |
| `education` | bachelor / master / phd / none |
| `job_category` | software-engineering / data-science / devops / ... |

Results cached per job — safe to resume after interruption.

---

## Step 4 — Cleaning (`us_jobs_cleaning.ipynb`)

| # | Step |
|---|------|
| 1 | Fix `job_id` — strip float `.0` suffix |
| 2 | Fix `posted_date` to `YYYY-MM-DD` |
| 3 | Set `country` column |
| 4 | Drop rows with missing `hard_skills` |
| 5 | Drop rows with missing `parsed_title` |
| 6 | Nullify zeros in salary columns (0 -> NaN) |
| 7 | Strip whitespace from all text columns |
| 8 | Drop `job_category == 'other'` |
| 9 | Drop raw salary columns |

**Output columns (19):**
`job_id, source, country, url, job_title, parsed_title, company, location, posted_date, seniority, min_years_exp, employment_type, remote_status, salary_min_annual, salary_max_annual, hard_skills, soft_skills, education, job_category`

---

## Step 5 — Analysis (`us_jobs_analysis.ipynb`)

| # | Section |
|---|---------|
| 1 | Dataset overview — categories, seniority, remote status, education |
| 2 | Job titles & category distribution |
| 3 | Hard skills — overall top skills |
| 4 | Most in-demand & essential skills (frequency x cross-industry breadth) |
| 5 | Hard skills by seniority level |
| 6 | Soft skills — overall + by category |
| 7 | Category signature skills (>=55% concentration in one field) |
| 8 | Skills co-occurrence heatmap (top 25 skills) |
| 9 | Location & remote trends |

---

## File Structure

```
us/
├── main.py                     <- pipeline entry point
├── config.py                   <- settings (loaded from .env)
├── requirements.txt
├── crawlers/
│   ├── linkedin_crawler.py
│   └── usajobs_crawler.py
├── dedup/
│   └── embedding_dedup.py
├── parser/
│   └── llm_parser.py
├── utils/
│   └── data_cleaner.py
├── data/
│   ├── us_jobs_raw.csv         <- Step 1 output
│   ├── us_jobs_parsed.csv      <- Step 3 output
│   └── us_jobs_final.csv       <- Step 4 output (clean, analysis-ready)
├── us_jobs_cleaning.ipynb      <- Step 4
└── us_jobs_analysis.ipynb      <- Step 5
```

---

## How to Run

```bash
# Full pipeline
python main.py

# Skip crawling — dedup + parse existing raw data
python main.py --parse-only

# Crawl + dedup only, skip LLM parsing
python main.py --crawl-only
```

---

## Requirements

Create a `.env` file:

```
USAJOBS_API_KEY=your_key
USAJOBS_EMAIL=your_email
GOOGLE_API_KEY=your_key

LLM_MODEL=gemini-2.5-pro
LLM_BATCH_SIZE=10
EMBED_MODEL=gemini-embedding-001

CRAWL_LOCATIONS=United States
OUTPUT_DIR=data/
```

Install dependencies:
```bash
pip install -r requirements.txt
```
