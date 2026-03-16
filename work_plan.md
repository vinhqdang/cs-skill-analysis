# CS Curriculum Skills Gap Analysis — Project Plan
**Goal**: Build a skills demand dataset to inform the design of a new CS undergraduate program  
**Target markets**: Vietnam (primary) · Southeast Asia · Global  
**Timeline**: ~10 weeks  
**Stack**: Python · pandas · BeautifulSoup · requests · python-jobspy

---

## Overview

```
Phase 1 │ Setup & taxonomy         │ Week 1–2
Phase 2 │ Dataset downloads        │ Week 1–2  (parallel)
Phase 3 │ Job board scraping       │ Week 2–4
Phase 4 │ API collection           │ Week 3–4  (parallel)
Phase 5 │ NLP & skills extraction  │ Week 5–6
Phase 6 │ Gap matrix & scoring     │ Week 7–8
Phase 7 │ Reporting                │ Week 9–10
```

---

## Phase 1 — Environment Setup & Skills Taxonomy

### 1.1 Python environment

```bash
pip install requests beautifulsoup4 pandas openpyxl
pip install python-jobspy spacy scikit-learn matplotlib seaborn
pip install jupyter notebook
python -m spacy download en_core_web_sm
```

### 1.2 Folder structure

```
skills-gap/
├── data/
│   ├── raw/
│   │   ├── job_postings/       # scraped job data (CSV per source)
│   │   ├── surveys/            # Stack Overflow, JetBrains CSVs
│   │   └── frameworks/         # ESCO, O*NET, CS2023 files
│   ├── processed/
│   │   ├── jobs_combined.csv
│   │   └── skills_extracted.csv
│   └── output/
│       ├── skill_gap_matrix.xlsx
│       └── report_figures/
├── notebooks/
│   ├── 01_taxonomy_builder.ipynb
│   ├── 02_job_scraping.ipynb
│   ├── 03_api_collection.ipynb
│   ├── 04_skills_extraction.ipynb
│   └── 05_gap_matrix.ipynb
├── scrapers/
│   ├── jobspy_scraper.py       # covers LinkedIn, Indeed, Google, Glassdoor
│   ├── itviec_scraper.py       # Vietnam-only, custom
│   └── vietnamworks_scraper.py # Vietnam-only, custom
└── requirements.txt
```

### 1.3 Skills taxonomy — build first

Before any scraping, build a master skills taxonomy. This is the controlled vocabulary you will match against in all job descriptions.

**Sources to combine:**
- ACM/IEEE CS2023 knowledge areas (manual — copy from PDF)
- ESCO v1.2 IT skills list (download CSV — see Phase 2)
- O*NET skills for occupations 15-1252, 15-1253, 15-1254 (see Phase 4)
- Manual additions from ITviec most-used tech tags

**Target structure** (`data/frameworks/skills_taxonomy.csv`):

| skill_id | skill_name | category | subcategory | source |
|---|---|---|---|---|
| S001 | Python | Programming | Languages | ESCO |
| S002 | Machine learning | AI/ML | Core concepts | CS2023 |
| S003 | Docker | DevOps | Containerization | O*NET |

**Skill categories** (Level 1):
1. Programming languages
2. Web & frameworks
3. Data / AI / ML
4. Cloud & DevOps
5. Databases
6. Software engineering practices
7. Security & networking
8. Professional / soft skills

---

## Phase 2 — Free Dataset Downloads

These require no scraping — download once, use throughout the project.

### 2.1 Stack Overflow Developer Survey (2024)

- **URL**: https://survey.stackoverflow.co/
- **Action**: Click "Download Full Data Set (CSV)"
- **File**: `survey_results_public.csv` (~50MB, 65,000+ rows, 114 columns)
- **Key columns**: `LanguageHaveWorkedWith`, `LanguageWantToWorkWith`, `DatabaseHaveWorkedWith`, `WebframeHaveWorkedWith`, `AISearchDevHaveWorkedWith`, `Country`, `DevType`, `EdLevel`

```python
import pandas as pd
so = pd.read_csv("data/raw/surveys/survey_results_public.csv")
# Filter Vietnam respondents (small sample, ~300)
vn = so[so["Country"] == "Viet Nam"]
# Filter global by dev type
devs = so[so["DevType"].str.contains("Developer", na=False)]
```

### 2.2 ESCO Skills Taxonomy v1.2

- **URL**: https://esco.ec.europa.eu/en/use-esco/download
- **Action**: Select "Skills" → CSV format → English → Download
- **File**: `skills_en.csv` (3,000+ skills with descriptions and related occupations)

```python
esco = pd.read_csv("data/frameworks/skills_en.csv")
# Filter IT-related skills
it_skills = esco[esco["broaderConceptUri"].str.contains("ict", na=False, case=False)]
```

### 2.3 ACM/IEEE CS2023

- **URL**: https://ieeecs-media.computer.org/media/education/reports/CS2023.pdf
- **Action**: Download PDF — manually extract knowledge areas into a CSV
- **File**: `data/frameworks/cs2023_knowledge_areas.csv`
- **Key sections to extract**: Table of knowledge areas + core hours (Appendix B)

### 2.4 JetBrains Developer Ecosystem Report

- **URL**: https://www.jetbrains.com/lp/devecosystem-2023/
- **Action**: Download summary PDF; key data tables must be manually extracted
- **File**: `data/raw/surveys/jetbrains_2023_summary.pdf`

---

## Phase 3 — Job Board Scraping

**Strategy**: use `python-jobspy` for everything it supports (LinkedIn, Indeed, Google, Glassdoor), and write custom scrapers only for the two Vietnam-specific boards it does not cover.

| Board | Tool | Why |
|---|---|---|
| LinkedIn | `python-jobspy` | Built-in support |
| Indeed (Vietnam) | `python-jobspy` | Built-in, no rate limit |
| Google Jobs | `python-jobspy` | Built-in |
| Glassdoor | `python-jobspy` | Built-in |
| **ITviec** | Custom scraper | Not in JobSpy — Vietnam IT-only, highest local value |
| **VietnamWorks** | Custom scraper | Not in JobSpy — largest Vietnam job board |
| TopDev | ❌ Skip | Overlap with Indeed/LinkedIn; not worth custom scraper |

---

### 3.1 Global boards — JobSpy (start here, covers ~80% of data)

```bash
pip install python-jobspy
```

```python
# scrapers/jobspy_scraper.py
import time
import pandas as pd
from jobspy import scrape_jobs

SEARCH_TERMS = [
    "software engineer", "data engineer", "machine learning engineer",
    "frontend developer", "backend developer", "DevOps engineer",
    "cybersecurity engineer", "cloud engineer", "mobile developer"
]

all_jobs = []
for term in SEARCH_TERMS:
    print(f"Scraping: {term}")
    df = scrape_jobs(
        site_name=["indeed", "linkedin", "google"],
        search_term=term,
        location="Vietnam",
        country_indeed="Vietnam",
        results_wanted=200,
        hours_old=720,               # last 30 days
        description_format="markdown"
    )
    df["search_term"] = term
    all_jobs.append(df)
    time.sleep(3)                    # be polite between search terms

combined = pd.concat(all_jobs).drop_duplicates(subset="job_url")
combined.to_csv("data/raw/job_postings/jobspy_vietnam.csv", index=False)
print(f"Total: {len(combined)} jobs")
```

**Expected output**: 1,000–2,000 job postings with title, company, full description, salary, date.

> ⚠️ LinkedIn rate-limits at ~page 10. Add proxies for large runs: `proxies=["host:port"]`  
> ⚠️ Google Jobs requires very specific query syntax — test in browser first.

---

### 3.2 ITviec — custom scraper (Vietnam IT-only, high priority)

ITviec is the most valuable Vietnam-specific source. Two-step scrape: list → detail.

```python
# scrapers/itviec_scraper.py
import requests
from bs4 import BeautifulSoup
import pandas as pd
import time

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; research-bot/1.0)"
}
BASE_URL = "https://itviec.com"

def get_job_links(keyword="it", pages=20):
    links = []
    for page in range(1, pages + 1):
        url = f"{BASE_URL}/it-jobs/{keyword}?page={page}"
        r = requests.get(url, headers=HEADERS)
        soup = BeautifulSoup(r.text, "html.parser")
        cards = soup.select("[data-search--job-selection-job-url]")
        for card in cards:
            path = card.get("data-search--job-selection-job-url")
            if path:
                links.append(BASE_URL + path)
        time.sleep(1.5)
    return list(set(links))

def get_job_detail(url):
    r = requests.get(url, headers=HEADERS)
    soup = BeautifulSoup(r.text, "html.parser")
    return {
        "url": url,
        "title": soup.select_one("h1").text.strip() if soup.select_one("h1") else "",
        "company": soup.select_one(".company-name").text.strip() if soup.select_one(".company-name") else "",
        "description": soup.select_one(".job-description").text.strip() if soup.select_one(".job-description") else "",
        "skills_tags": [t.text.strip() for t in soup.select(".tag-item")],
        "location": soup.select_one(".address").text.strip() if soup.select_one(".address") else "",
    }

if __name__ == "__main__":
    keywords = ["", "python", "java", "javascript", "data", "ai", "cloud", "devops", "security"]
    all_jobs = []
    for kw in keywords:
        print(f"Fetching links for: {kw or 'all'}")
        links = get_job_links(keyword=kw, pages=10)
        for link in links:
            try:
                job = get_job_detail(link)
                job["keyword"] = kw
                all_jobs.append(job)
                time.sleep(1)
            except Exception as e:
                print(f"Error: {e}")
    df = pd.DataFrame(all_jobs).drop_duplicates(subset="url")
    df.to_csv("data/raw/job_postings/itviec.csv", index=False)
    print(f"Saved {len(df)} jobs")
```

**Expected output**: 500–1,500 IT job postings with skills tags already extracted.

---

### 3.3 VietnamWorks — custom scraper (Algolia backend, cleanest approach)

VietnamWorks uses Algolia for search. Hit the Algolia endpoint directly — faster and more reliable than HTML parsing.

```python
# scrapers/vietnamworks_scraper.py
import requests
import pandas as pd
import time

# Algolia credentials for VietnamWorks (public, embedded in frontend JS)
ALGOLIA_APP_ID = "JF2OLIS6ZB"
ALGOLIA_API_KEY = "your_public_key_here"  # inspect network tab on vietnamworks.com
ALGOLIA_INDEX   = "vnw_job_v2"

def search_jobs(keyword, pages=10):
    results = []
    for page in range(pages):
        url = f"https://{ALGOLIA_APP_ID}-dsn.algolia.net/1/indexes/{ALGOLIA_INDEX}/query"
        payload = {
            "params": f"query={keyword}&page={page}&hitsPerPage=50&filters=category_ids:35"
            # category_ids:35 = IT / Software
        }
        headers = {
            "X-Algolia-Application-Id": ALGOLIA_APP_ID,
            "X-Algolia-API-Key": ALGOLIA_API_KEY,
        }
        r = requests.post(url, json=payload, headers=headers)
        hits = r.json().get("hits", [])
        if not hits:
            break
        results.extend(hits)
        time.sleep(0.5)
    return results

# Alternative: plain requests scrape of search results page
def scrape_html_fallback(keyword="software-engineer", pages=10):
    import requests
    from bs4 import BeautifulSoup
    jobs = []
    for page in range(1, pages + 1):
        url = f"https://www.vietnamworks.com/{keyword}-jobs-i35+en?page={page}"
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})
        soup = BeautifulSoup(r.text, "html.parser")
        for card in soup.select(".job-item"):
            jobs.append({
                "title": card.select_one(".title").text.strip() if card.select_one(".title") else "",
                "company": card.select_one(".company").text.strip() if card.select_one(".company") else "",
                "location": card.select_one(".location").text.strip() if card.select_one(".location") else "",
            })
        time.sleep(1.5)
    return pd.DataFrame(jobs)
```

> 💡 **Tip**: Open VietnamWorks in Chrome DevTools → Network tab → filter by "algolia" → copy the API key from request headers. This key is public and safe to use for research.


---

## Phase 4 — API Collection

### 4.1 O*NET Web Services API (free, register required)

- **Register**: https://services.onetcenter.org/
- **Target occupations**:

| O*NET Code | Title |
|---|---|
| 15-1252.00 | Software Developers |
| 15-1253.00 | Software Quality Assurance Analysts |
| 15-1254.00 | Web Developers |
| 15-1211.00 | Computer Systems Analysts |
| 15-1212.00 | Information Security Analysts |
| 15-2051.00 | Data Scientists |

```python
# notebooks/03_api_collection.ipynb
import requests
import pandas as pd

USERNAME = "your_onet_username"  # from registration
PASSWORD = "your_onet_password"

OCCUPATIONS = [
    "15-1252.00", "15-1253.00", "15-1254.00",
    "15-1211.00", "15-1212.00", "15-2051.00"
]

def get_skills(onet_code):
    url = f"https://services.onetcenter.org/ws/online/occupations/{onet_code}/summary/skills"
    r = requests.get(url, auth=(USERNAME, PASSWORD),
                     headers={"Accept": "application/json"})
    data = r.json()
    skills = []
    for item in data.get("element", []):
        skills.append({
            "onet_code": onet_code,
            "skill": item["name"],
            "importance": item["score"]["value"],
            "level": item.get("level", {}).get("value", None)
        })
    return skills

def get_technology_skills(onet_code):
    url = f"https://services.onetcenter.org/ws/online/occupations/{onet_code}/details/technology_skills"
    r = requests.get(url, auth=(USERNAME, PASSWORD),
                     headers={"Accept": "application/json"})
    return r.json()

all_skills = []
for code in OCCUPATIONS:
    all_skills.extend(get_skills(code))

df = pd.DataFrame(all_skills)
df.to_csv("data/raw/frameworks/onet_skills.csv", index=False)
```

### 4.2 ESCO REST API (no key needed)

```python
import requests

def search_esco_skills(keyword):
    url = "https://ec.europa.eu/esco/api/search"
    params = {"text": keyword, "type": "skill", "language": "en", "limit": 20}
    r = requests.get(url, params=params)
    return r.json().get("_embedded", {}).get("results", [])

def get_esco_occupation_skills(occupation_uri):
    # e.g. occupation_uri = "http://data.europa.eu/esco/occupation/f2b4b291-..."
    url = "https://ec.europa.eu/esco/api/resource/occupation"
    params = {"uri": occupation_uri, "language": "en"}
    r = requests.get(url, params=params)
    return r.json()

# Example: search for skills related to "machine learning"
ml_skills = search_esco_skills("machine learning")
for s in ml_skills:
    print(s["title"], "|", s["uri"])
```

### 4.3 Stack Exchange API (tag popularity over time)

```python
import requests

def get_so_tags(page=1, pagesize=100, min_count=1000):
    url = "https://api.stackexchange.com/2.3/tags"
    params = {
        "order": "desc", "sort": "popular",
        "site": "stackoverflow",
        "pagesize": pagesize, "page": page,
        "min": min_count,
        "key": ""   # optional — higher quota with key from stackapps.com
    }
    r = requests.get(url, params=params)
    return r.json().get("items", [])

# Fetch top 500 tags
all_tags = []
for page in range(1, 6):
    all_tags.extend(get_so_tags(page=page))

df_tags = pd.DataFrame(all_tags)[["name", "count"]]
df_tags.to_csv("data/raw/surveys/so_tags.csv", index=False)
```

---

## Phase 5 — NLP Skills Extraction

Extract skill mentions from raw job description text using the taxonomy built in Phase 1.

```python
# notebooks/04_skills_extraction.ipynb
import pandas as pd
import re

# Load taxonomy
taxonomy = pd.read_csv("data/frameworks/skills_taxonomy.csv")
skill_names = taxonomy["skill_name"].str.lower().tolist()

# Load combined job postings
jobs = pd.read_csv("data/processed/jobs_combined.csv")

def extract_skills(text, skill_list):
    if not isinstance(text, str):
        return []
    text_lower = text.lower()
    found = []
    for skill in skill_list:
        # Word boundary match to avoid false positives (e.g. "R" in "React")
        pattern = r'\b' + re.escape(skill) + r'\b'
        if re.search(pattern, text_lower):
            found.append(skill)
    return found

jobs["skills_found"] = jobs["description"].apply(
    lambda x: extract_skills(x, skill_names)
)

# Explode to one row per skill mention
skills_flat = jobs.explode("skills_found").dropna(subset=["skills_found"])
skill_freq = skills_flat.groupby("skills_found").size().reset_index(name="job_count")
skill_freq["demand_pct"] = skill_freq["job_count"] / len(jobs) * 100
skill_freq = skill_freq.sort_values("demand_pct", ascending=False)
skill_freq.to_csv("data/processed/skills_extracted.csv", index=False)
```

**Output**: A frequency table of how often each skill appears across job postings.

---

## Phase 6 — Gap Matrix & Scoring

### 6.1 Scoring dimensions

| Column | Description | Source | Scale |
|---|---|---|---|
| `demand_freq` | % of job postings mentioning this skill | Phase 5 NLP | 0–100% |
| `employer_importance` | Mean rating from employer survey | Manual survey | 1–5 |
| `curriculum_coverage` | Current/planned coverage | Faculty self-assessment | 0–5 |
| `gap_score` | `employer_importance − curriculum_coverage` | Calculated | −5 to +5 |
| `growth_trend` | Rising/stable/declining in SO survey trend | Phase 2 SO data | 1–3 |
| `priority_score` | Weighted composite | Calculated | 0–100 |

### 6.2 Priority scoring formula

```python
# notebooks/05_gap_matrix.ipynb
import pandas as pd

df = pd.read_csv("data/processed/skills_extracted.csv")

# Normalize demand_freq to 0–5 scale
df["demand_norm"] = df["demand_pct"] / df["demand_pct"].max() * 5

# Gap score (higher = bigger gap = higher priority to add to curriculum)
df["gap_score"] = df["employer_importance"] - df["curriculum_coverage"]
df["gap_score_norm"] = df["gap_score"].clip(0, 5)  # only positive gaps count

# Weighted priority score (weights sum to 1.0)
W_DEMAND     = 0.30
W_GAP        = 0.25
W_EMPLOYER   = 0.20
W_TREND      = 0.15
W_FEASIBILITY = 0.10

df["priority_score"] = (
    df["demand_norm"]       * W_DEMAND +
    df["gap_score_norm"]    * W_GAP +
    df["employer_importance"] * W_EMPLOYER +
    df["growth_trend"]      * W_TREND +
    df["feasibility"]       * W_FEASIBILITY
) * 20  # scale to 0–100

df = df.sort_values("priority_score", ascending=False)
df.to_excel("data/output/skill_gap_matrix.xlsx", index=False)
```

### 6.3 Action classification (MoSCoW)

| Priority score | Label | Curriculum action |
|---|---|---|
| 70–100 | **Must Have** | New course or major module |
| 50–69 | **Should Have** | Add to existing course |
| 30–49 | **Could Have** | Lab / elective / co-curricular |
| 0–29 | **Won't Have (now)** | Monitor, revisit next cycle |

---

## Phase 7 — Output & Reporting

### Deliverables

- [ ] `skill_gap_matrix.xlsx` — full scored matrix, filterable by category
- [ ] `top30_priority_skills.pdf` — bar chart + heatmap for stakeholders  
- [ ] `curriculum_mapping.xlsx` — gap matrix mapped to proposed course list
- [ ] `data_collection_report.md` — methodology notes, sample sizes, limitations

### Key visualizations to produce

```python
import matplotlib.pyplot as plt
import seaborn as sns

# 1. Heatmap of top 30 skills × scoring dimensions
pivot = df.head(30).set_index("skill_name")[
    ["demand_norm", "employer_importance", "curriculum_coverage", "gap_score_norm"]
]
sns.heatmap(pivot, annot=True, cmap="RdYlGn", fmt=".1f")
plt.title("Skill gap heatmap — top 30 skills")
plt.tight_layout()
plt.savefig("data/output/report_figures/heatmap.png", dpi=150)

# 2. Bubble chart — demand vs gap, size = employer importance
plt.figure(figsize=(12, 8))
plt.scatter(
    df["demand_pct"], df["gap_score"],
    s=df["employer_importance"] * 40,
    alpha=0.6, c=df["priority_score"], cmap="RdYlGn"
)
for _, row in df.head(20).iterrows():
    plt.annotate(row["skill_name"], (row["demand_pct"], row["gap_score"]), fontsize=8)
plt.xlabel("Market demand (% of job postings)")
plt.ylabel("Gap score (employer need − current coverage)")
plt.title("Skill demand vs gap — bubble size = employer importance")
plt.savefig("data/output/report_figures/bubble_chart.png", dpi=150)
```

---

## Data Collection Targets

| Source | Tool | Target volume | Priority |
|---|---|---|---|
| Indeed + LinkedIn + Google (Vietnam) | `python-jobspy` | 1,000–2,000 postings | High |
| ITviec | Custom scraper | 500–1,000 postings | High |
| VietnamWorks | Custom scraper | 300–500 postings | High |
| Stack Overflow Developer Survey CSV | Direct download | 65,000 rows (filter ~300 VN) | High |
| O*NET API | `requests` | 6 occupations × ~50 skills | High |
| ESCO CSV | Direct download | ~3,000 IT skills | Medium |
| Employer survey (Google Forms) | Manual | 50–100 responses | High |

---

## Important Notes

**Ethical / legal**
- Always read `robots.txt` before scraping (e.g. `https://itviec.com/robots.txt`)
- Add `time.sleep(1–2)` between requests — do not hammer servers
- This is academic research — label your user agent accordingly
- Do not resell or redistribute scraped data

**Vietnamese language**
- ITviec and VietnamWorks mix English and Vietnamese in job descriptions
- Run descriptions through Google Translate API or `googletrans` library for Vietnamese-only postings
- Key Vietnamese terms to watch: `lập trình viên` (developer), `kỹ năng` (skill), `yêu cầu` (requirement)

**Data quality checks**
- Deduplicate on job URL before analysis
- Filter out postings older than 12 months
- Flag postings where `description` is empty or under 100 characters
- Validate skill taxonomy matches — review top 50 by frequency manually

---

## Week-by-Week Checklist

- [ ] **Week 1**: Set up environment · Download SO survey CSV · Download ESCO CSV · Draft skills taxonomy (60–80 skills)
- [ ] **Week 2**: Run JobSpy scraper (Indeed + LinkedIn + Google, Vietnam) · Register O*NET API · Scrape ITviec (first 500 jobs)
- [ ] **Week 3**: Scrape VietnamWorks · Hit O*NET API for 6 occupations · Hit ESCO API
- [ ] **Week 4**: Combine all job CSVs · Deduplicate · Quality check
- [ ] **Week 5**: Run NLP skills extraction on all job descriptions
- [ ] **Week 6**: Compute demand frequencies · Cross-reference with SO + O*NET importance scores
- [ ] **Week 7**: Design & send Google Forms employer survey (target: 50+ responses)
- [ ] **Week 8**: Add employer survey data · Compute gap scores · Build priority matrix
- [ ] **Week 9**: Build visualizations (heatmap, bubble chart, bar charts)
- [ ] **Week 10**: Write methodology report · Prepare curriculum recommendation deck

---

*Last updated: March 2026 · Đặng Quang Vinh / BUV*