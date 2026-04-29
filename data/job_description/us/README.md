# US Tech Jobs Pipeline

Crawl → Deduplicate → Parse → Clean CSV

---

## What it does

Automatically collects US tech job listings from **LinkedIn** and **USAJobs**, removes duplicates, then uses an LLM to extract structured fields (skills, salary, seniority, etc.) from each job description.

---

## Pipeline Steps

### Step 1 — Crawl (`main.py`, Phase 1)

Scrapes job listings from two sources based on 18 tech job keywords (e.g. "software engineer", "data scientist"):

| Source | How |
|---|---|
| **USAJobs** | Official REST API |
| **LinkedIn** | Playwright browser scraping (headless) |

Raw results are merged and URL-deduplicated.

**Output:** `data/us_jobs_raw.csv`

---

### Step 2 — Semantic Deduplication (`dedup/embedding_dedup.py`, Phase 2)

Removes near-duplicate listings that are the same job posted multiple times or on both platforms.

How it works:
1. Embeds each job's title + company + location using **Google text-embedding-004**
2. Computes cosine similarity between all job pairs
3. If similarity ≥ 0.92 **and** description overlap ≥ 40% → keep the richer listing, drop the other

Embeddings are cached so reruns are fast.

**Output:** `data/us_jobs_deduped.csv` + `data/embed_cache.json`

---

### Step 3 — LLM Parsing (`parser/llm_parser.py`, Phase 3)

Sends each job description to **Gemini 2.5 Flash** in batches of 20.  
The model extracts structured fields from free-text descriptions:

| Field | Example |
|---|---|
| `parsed_title` | "Senior Backend Engineer" |
| `seniority` | senior / mid / junior / intern … |
| `min_years_exp` | 3 |
| `employment_type` | full-time / contract … |
| `remote_status` | remote / hybrid / onsite |
| `salary_min_annual` | 120000 |
| `salary_max_annual` | 160000 |
| `hard_skills` | ["Python", "AWS", "Docker", …] |
| `soft_skills` | ["ownership", "collaboration", …] |
| `education` | bachelor / master / phd … |
| `job_category` | software-eng / data-science / devops … |

Results are cached per job so partial runs can resume.

**Output:** `data/us_jobs_parsed.csv` + `data/parse_cache.json`

---

### Step 4 — Manual Cleaning (optional, `us_jobs_cleaning.ipynb`)

Jupyter notebook for manual review, column formatting, and any final cleanup.

**Output:** `data/us_jobs_final.csv`

---

### Step 5 — Analysis (`us_jobs_analysis.ipynb`)

Exploratory analysis of the final dataset. Sections:

| # | Topic |
|---|---|
| 1 | Dataset overview — source breakdown, categories, seniority, remote status |
| 2 | Job titles & category distribution |
| 3 | Hard skills — overall top-30 + top-15 per category + skill count stats |
| 4 | Most in-demand & most essential skills (frequency × cross-industry breadth) |
| 5 | Hard skills by seniority level (junior → senior differential) |
| 6 | Soft skills — overall + by category |
| 7 | Category signature skills (skills with ≥ 55% concentration in one field) |
| 8 | Skills co-occurrence heatmap (top 25 hard skills) |
| 9 | Location & remote trends (top hiring cities, remote vs onsite by category) |

**Input:** `data/us_jobs_final.csv`  
**Output:** visualizations only (no CSV written)

---

## File Summary

```
data/
├── us_jobs_raw.csv          ← Step 1: raw crawled jobs (all sources merged)
├── us_jobs_deduped.csv      ← Step 2: after removing duplicates
├── embed_cache.json         ← Step 2: cached embeddings (speeds up reruns)
├── us_jobs_parsed.csv       ← Step 3: structured fields extracted by LLM
├── parse_cache.json         ← Step 3: cached LLM results (resume-safe)
└── us_jobs_final.csv        ← Step 4: manually cleaned final dataset
```

---

## How to Run

```bash
# Full pipeline (crawl + dedup + parse)
python main.py

# Skip crawling, re-parse existing raw data
python main.py --parse-only

# Crawl + dedup only, no LLM parsing
python main.py --crawl-only
```

---

## Requirements

- `.env` file with: `GOOGLE_API_KEY`, `USAJOBS_API_KEY`, `USAJOBS_EMAIL`
- Chrome/Chromium installed (for LinkedIn Playwright scraping)
- Python packages: see `requirements.txt`
