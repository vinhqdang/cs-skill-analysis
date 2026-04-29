import os
import json
import time
import logging
import hashlib
import requests
import pandas as pd
from tqdm import tqdm

logger = logging.getLogger(__name__)

DEFAULT_SYSTEM_PROMPT = """You are an expert job data extractor. Given job listings, extract highly detailed structured fields.
Return ONLY a JSON array. No explanation, no markdown, no backticks.

For each job, thoroughly analyze the ENTIRE description text to extract:
{
  "job_id": "original id",
  "parsed_title": "cleaned title without company name or location",
  "seniority": "intern|junior|mid|senior|lead|manager|director|vp|c-level|unknown",
  "min_years_exp": number or null (Extract integer from phrases like '1+ years'),
  "employment_type": "full-time|part-time|contract|internship|unknown",
  "remote_status": "remote|hybrid|onsite|unknown",
  "salary_min_annual": number or null (HUNT IN DESCRIPTION TEXT if missing in headers),
  "salary_max_annual": number or null (HUNT IN DESCRIPTION TEXT if missing in headers),
  "hard_skills": ["Python", "Java", "AWS", "Docker", "Kubernetes", "Spark", "Hadoop", "Agile", "DevOps", "CI/CD", ...],
  "soft_skills": ["ownership", "collaboration", "autonomy", "problem-solving", ...],
  "education": "none|bachelor|master|phd|unknown",
  "job_category": "software-eng|data-science|devops|security|design|product|infrastructure|other"
}

Rules:
- EXHAUSTIVE SKILLS: Capture ALL hard/technical and soft skills mentioned in the text. Do not limit the count.

*) HARD SKILLS RULES

INCLUDE these types of hard skills:
  * Programming languages (Python, Java, SQL, JavaScript, TypeScript, Go, etc.)
  * Frameworks and libraries (Spring, Angular, React, Hibernate, Maven, etc.)
  * Platforms and tools (AWS, Azure, GCP, Databricks, Docker, Kubernetes, etc.)
  * Data technologies (Hadoop, Spark, HBase, Kafka, relational databases, etc.)
  * Methodologies and processes (Agile, DevOps, CI/CD, Scrum, TDD, SDLC,
    code review, release management)
  * Architectural concepts (big data, microservices, distributed systems)
  * Operating systems (Unix, Linux, Unix Shell Scripts)
  * Domain skills (predictive analytics, NLP, computer vision, time series
    forecasting, recommendation systems) — ONLY when the candidate performs them

CAPTURE INTEGRATION AND ARCHITECTURE SKILLS:
  When the JD asks the candidate to interact with, integrate, or architect
  a system, THAT is a skill:
  * "interact with APIs" / "working with APIs"     -> "API integration"
  * "architecting frontend systems"                -> "frontend architecture"
  * "designing microservices"                      -> "system design"
  * "integrating third-party services"             -> "third-party integrations"
  * "scaling distributed systems"                  -> "distributed systems"

CAPTURE SPECIFIC TECHNICAL CAPABILITIES even when they sound generic,
because they ARE the skill being asked of the candidate:
  * "data visualization" / "data visualization tools"
  * "web applications" / "complex web applications"
  * "RESTful APIs" / "API design"
  * "responsive design"
  * "performance optimization"
  * "accessibility (a11y)"

SKILL FAMILIES:
  If the JD mentions a skill family without naming a specific tool,
  capture the family:
  * "modern frontend frameworks"    -> "frontend frameworks"
  * "cloud platforms"               -> "cloud platforms" (only if no AWS/Azure/GCP named)
  * "containerization"              -> "containerization" (only if no Docker named)
  * "version control"               -> "version control" (only if no Git named)

REQUIRED-OF-CANDIDATE vs. ENVIRONMENTAL CONTEXT (most important rule):
  The SAME word can be a skill or not depending on phrasing. Only extract
  a skill when the candidate must perform it; skip when it's just part of
  the system's environment or marketing language.

  Skill (candidate performs it)           vs.   Not a skill (passive context)
  ------------------------------------------    ------------------------------------------
  "Build REST APIs"            -> "REST APIs"   "Frontend receives data from APIs"  -> skip
  "Train ML models"            -> "ML"          "ML-driven insights"                -> skip
  "Build predictive models"    -> "predictive analytics"  "Platform uses predictive analytics" -> skip
  "Cloud architecture design"  -> "cloud architecture"    "Cloud-based product"      -> skip
  "NLP pipeline development"   -> "NLP"         "Our NLP-powered assistant"         -> skip

  Rule of thumb: If the candidate needs to write non-trivial code or make
  technical decisions to use something, it IS a skill. If they just
  consume its output or it's company marketing, it is not.

CANONICAL NAMES: Use ONE standard name per skill. Merge clear synonyms:
  * "React" + "React.js"                     -> "React"
  * "JS" + "JavaScript"                      -> "JavaScript"
  * "k8s" + "Kubernetes"                     -> "Kubernetes"
  * "CI" + "CD" + "CI/CD"                    -> "CI/CD"
  * "REST" + "REST APIs" + "RESTful services" -> "REST APIs"

  BUT preserve meaningful specificity when the JD clearly distinguishes:
  * "operational dashboards" is MORE SPECIFIC than "data visualization" —
    keep "operational dashboards" when the JD explicitly emphasizes
    operational/real-time/mission-critical context
  * "cloud architecture" is MORE SPECIFIC than "cloud" — keep the specific
    form when the JD asks for design/architecture work

  Never include both a general skill and its specific sub-skill — pick
  the more specific one when the JD warrants it, otherwise the general one.

DO NOT include in hard_skills:
  * Generic activities ("testing", "coding", "shipping", "development") —
    only specific types count (e.g., "unit testing", "TDD", "test automation")
  * Experience indicators ("track record of X", "proven ability to Y",
    "comfort working with Z") — having done something is not a skill
  * Goals or deliverables ("data solutions", "applications", "products")
  * Vague categories when specific ones are already captured
    (e.g., if "AWS" is listed, don't add "cloud")
  * Mindsets or methodologies better suited to soft_skills
    ("continuous improvement", "innovation", "ownership")
  * Passive environmental references — see REQUIRED-OF-CANDIDATE rule above


*) SOFT SKILLS RULES

Soft skills are TRANSFERABLE personal or interpersonal qualities
the candidate brings to work. Examples: ownership, collaboration,
problem-solving, adaptability, communication, leadership.

THE TEST — for each candidate phrase, ask two questions:

  1. Is it a quality of the CANDIDATE (how they think, behave,
     or work with others)?
     NOT a quality of the product, company, or outcome.

  2. Could this phrase appear on a resume as a personal strength,
     independent of any specific job?

  If both answers are YES, include it. If either is NO, skip it.

NORMALIZE TO STANDARD NOUN FORM:
  Convert JD phrasing to the underlying skill as a short noun phrase.
  Use your judgment to pick the clearest, most common name.

  "Owns a problem to the end"              -> "ownership"
  "Work in a team setting"                 -> "collaboration"
  "Do your best work autonomously"         -> "autonomy"
  "Wants to grow a career"                 -> "growth mindset"
  "Solving difficult problems"             -> "problem-solving"
  "Care deeply about quality"              -> "attention to detail"
  "Strong technical judgment"              -> "critical thinking"
  "Comfortable with ambiguity"             -> "adaptability"
  "Self-starter"                           -> "initiative"

COMMON MISTAKES TO AVOID:
  - Do NOT copy raw JD phrases — infer the underlying skill.
  - Do NOT include values or outcomes ("quality", "performance",
    "reliability", "security"). These describe what the CANDIDATE
    CARES ABOUT, not a skill they possess. Map to "attention to detail"
    if strongly emphasized, otherwise skip.
  - Do NOT include company/role context ("fast-paced", "mission-driven",
    "impact-focused") — these describe the environment, not the candidate.
  - Do NOT duplicate across hard_skills and soft_skills.
- SALARY EXTRACTION: Scan the description carefully for salary ranges (e.g., "Base Salary: $73,500.00 - $136,500.00"). Convert hourly/monthly to annual (hourly*2080, monthly*12). Return ONLY raw numbers (e.g., 73500) without symbols or commas.

- If info is truly not found anywhere in the text, use null or "unknown".
- Return a valid JSON array only."""

def _get_system_prompt(config: dict) -> str:
    external = config.get("llm_system_prompt")
    if external:
        logger.info("Using external system prompt from file")
        return external
    return DEFAULT_SYSTEM_PROMPT


def load_cache(path: str) -> dict:
    if os.path.exists(path):
        try:
            with open(path, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            logger.warning("Cache corrupt, starting fresh")
    return {}


def save_cache(cache: dict, path: str):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w") as f:
        json.dump(cache, f)


def make_job_hash(job_id: str, description: str) -> str:
    content = f"{job_id}:{description[:500]}"
    return hashlib.md5(content.encode()).hexdigest()


def truncate_description(desc: str, max_len: int) -> str:
    if not desc or len(desc) <= max_len:
        return desc or ""
    head_len = int(max_len * 0.6)
    tail_len = max_len - head_len
    return desc[:head_len] + " [...] " + desc[-tail_len:]


def build_batch_prompt(jobs_batch: list, max_desc_len: int) -> str:
    entries = []
    for job in jobs_batch:
        desc = truncate_description(
            str(job.get("full_description", "")), max_desc_len
        )

        # Clean up missing data so the LLM doesn't get confused by "nan" or blank spaces
        sal_min = job.get('salary_min', '')
        sal_max = job.get('salary_max', '')

        entry = (
            f"---JOB---\n"
            f"id: {job.get('job_id', '')}\n"
            f"title: {job.get('job_title', '')}\n"
            f"company: {job.get('company', '')}\n"
            f"location: {job.get('location', '')}\n"
            f"provided_salary_min: {sal_min if pd.notna(sal_min) and sal_min else 'MISSING - CHECK DESCRIPTION'}\n"
            f"provided_salary_max: {sal_max if pd.notna(sal_max) and sal_max else 'MISSING - CHECK DESCRIPTION'}\n"
            f"description_body: {desc}\n"
        )
        entries.append(entry)
    return f"Parse these {len(entries)} jobs. Extract all skills and meticulously search the description_body for missing salaries.\n\n" + "\n".join(entries)


def call_llm(prompt: str, system_prompt: str, config: dict, retry_count: int = 0) -> list:
    MAX_RETRIES = 5
    api_key = config["google_api_key"]
    model   = config["llm_model"]

    url = (
        f"https://generativelanguage.googleapis.com/v1beta/"
        f"models/{model}:generateContent?key={api_key}"
    )

    payload = {
        "contents": [
            {"role": "user", "parts": [{"text": prompt}]}
        ],
        "systemInstruction": {
            "parts": [{"text": system_prompt}]
        },
        "generationConfig": {
            "temperature": config["llm_temperature"],
            "maxOutputTokens": config["llm_max_tokens"],
            "responseMimeType": "application/json",
        },
    }

    text = ""
    try:
        response = requests.post(url, json=payload, timeout=120)
        response.raise_for_status()
        data = response.json()

        for candidate in data.get("candidates", []):
            for part in candidate.get("content", {}).get("parts", []):
                text += part.get("text", "")

        text = text.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[-1]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()

        parsed = json.loads(text)
        if isinstance(parsed, list):
            return parsed
        elif isinstance(parsed, dict):
            return [parsed]
        return []

    except json.JSONDecodeError as e:
        logger.error(f"JSON parse error: {e}\nRaw: {text[:500]}")
        return []
    except (requests.exceptions.HTTPError, requests.exceptions.ReadTimeout, requests.exceptions.ConnectionError) as e:
        status_code = getattr(e.response, 'status_code', None) if hasattr(e, 'response') else 'Network Error'
        
        if status_code in (429, 500, 502, 503, 504) or status_code == 'Network Error':
            if retry_count < MAX_RETRIES:
                sleep_time = 30 * (2 ** retry_count)  # 30s, 60s, 120s, 240s, 480s
                logger.warning(f"Error {status_code} — waiting {sleep_time}s then retrying (Attempt {retry_count + 1}/{MAX_RETRIES})...")
                time.sleep(sleep_time)
                return call_llm(prompt, system_prompt, config, retry_count + 1)
            else:
                logger.error(f"Max retries reached. Error {status_code}")
                return []
        
        logger.error(f"Gemini API error {status_code}: {e}")
        return []


def parse_jobs(
    raw_csv_path: str,
    parsed_csv_path: str,
    cache_path: str,
    config: dict,
) -> pd.DataFrame:
    system_prompt = _get_system_prompt(config)

    df = pd.read_csv(raw_csv_path)
    logger.info(f"Loaded {len(df)} raw jobs from {raw_csv_path}")

    df["full_description"] = df["full_description"].fillna("")
    df = df[df["full_description"].str.len() > 100].copy()
    logger.info(f"After filtering short descriptions: {len(df)} jobs")

    cache = load_cache(cache_path)
    logger.info(f"Cache has {len(cache)} previously parsed jobs")

    jobs_to_parse = []
    for _, row in df.iterrows():
        job_dict = row.to_dict()
        h = make_job_hash(
            str(job_dict.get("job_id", "")),
            str(job_dict.get("full_description", ""))
        )
        if h not in cache:
            job_dict["_hash"] = h
            jobs_to_parse.append(job_dict)

    logger.info(
        f"To parse: {len(jobs_to_parse)} new "
        f"(skipping {len(df) - len(jobs_to_parse)} cached)"
    )

    if not jobs_to_parse:
        logger.info("All jobs already parsed — loading from cache")
        return _build_final_df(df, cache, parsed_csv_path)

    batch_size   = config["llm_batch_size"]
    max_desc_len = config["llm_max_desc_len"]
    rate_delay   = config["llm_rate_limit_delay"]
    total_batches = (len(jobs_to_parse) + batch_size - 1) // batch_size

    logger.info(f"Processing {total_batches} batches of {batch_size}")

    for i in tqdm(range(0, len(jobs_to_parse), batch_size),
                  desc="LLM parsing", total=total_batches):

        batch = jobs_to_parse[i : i + batch_size]
        prompt = build_batch_prompt(batch, max_desc_len)
        results = call_llm(prompt, system_prompt, config)

        for idx, job in enumerate(batch):
            if idx < len(results):
                parsed = results[idx]
                if parsed and parsed.get("parsed_title"):
                    cache[job["_hash"]] = parsed

        save_cache(cache, cache_path)

        if i + batch_size < len(jobs_to_parse):
            time.sleep(rate_delay)

    return _build_final_df(df, cache, parsed_csv_path)


def _build_final_df(
    raw_df: pd.DataFrame,
    cache: dict,
    output_path: str,
) -> pd.DataFrame:
    rows = []
    for _, row in raw_df.iterrows():
        job = row.to_dict()
        h = make_job_hash(
            str(job.get("job_id", "")),
            str(job.get("full_description", ""))
        )
        parsed = cache.get(h, {})

        rows.append({
            "source"            : job.get("source", ""),
            "job_id"            : job.get("job_id", ""),
            "job_title"         : job.get("job_title", ""),
            "company"           : job.get("company", ""),
            "location"          : job.get("location", ""),
            "posted_date"       : job.get("posted_date", ""),
            "url"               : job.get("url", ""),
            "salary_min_raw"    : job.get("salary_min", ""),
            "salary_max_raw"    : job.get("salary_max", ""),
            "parsed_title"      : parsed.get("parsed_title", ""),
            "seniority"         : parsed.get("seniority", "unknown"),
            "min_years_exp"     : parsed.get("min_years_exp"),
            "employment_type"   : parsed.get("employment_type", "unknown"),
            "remote_status"     : parsed.get("remote_status", "unknown"),
            "salary_min_annual" : parsed.get("salary_min_annual"),
            "salary_max_annual" : parsed.get("salary_max_annual"),
            "hard_skills"       : ", ".join(parsed.get("hard_skills", []) if isinstance(parsed.get("hard_skills"), list) else []),
            "soft_skills"       : ", ".join(parsed.get("soft_skills", []) if isinstance(parsed.get("soft_skills"), list) else []),
            "education"         : parsed.get("education", "unknown"),
            "job_category"      : parsed.get("job_category", "other"),
        })

    result_df = pd.DataFrame(rows)
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    result_df.to_csv(output_path, index=False, encoding="utf-8-sig")
    logger.info(f"Saved {len(result_df)} parsed jobs to {output_path}")
    return result_df