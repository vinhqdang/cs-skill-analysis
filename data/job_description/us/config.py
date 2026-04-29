# type: ignore

import os
from dotenv import load_dotenv

load_dotenv()


def _env(key: str, default=None, cast=None):
    val = os.getenv(key, default)
    if val is None:
        return None
    if cast is not None:
        try:
            return cast(val)
        except (ValueError, TypeError):
            return cast(default) if default is not None else None
    return val


def _load_prompt_from_file(path: str) -> str | None:
    if path and os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return f.read().strip()
    return None


_prompt_file = _env("LLM_SYSTEM_PROMPT_FILE", "") or ""
_external_prompt = _load_prompt_from_file(_prompt_file)

CONFIG = {
    "usajobs_api_key"       : _env("USAJOBS_API_KEY", ""),
    "usajobs_email"         : _env("USAJOBS_EMAIL", ""),
    "google_api_key"        : _env("GOOGLE_API_KEY", ""),

    "llm_model"             : _env("LLM_MODEL", "gemini-2.5-flash-preview-05-20"),
    "llm_batch_size"        : _env("LLM_BATCH_SIZE", "20", int),
    "llm_max_desc_len"      : _env("LLM_MAX_DESC_LEN", "1500", int),
    "llm_max_tokens"        : _env("LLM_MAX_TOKENS", "8192", int),
    "llm_temperature"       : _env("LLM_TEMPERATURE", "0.0", float),
    "llm_rate_limit_delay"  : _env("LLM_RATE_LIMIT_DELAY", "2.5", float),
    "llm_system_prompt"     : _external_prompt,

    "embed_model"           : _env("EMBED_MODEL", "text-embedding-004"),
    "dedup_sim_threshold"   : _env("DEDUP_SIMILARITY_THRESHOLD", "0.92", float),
    "dedup_desc_overlap"    : _env("DEDUP_DESCRIPTION_OVERLAP", "0.40", float),
    "embed_batch_size"      : _env("EMBED_BATCH_SIZE", "100", int),

    "us_location"           : _env("CRAWL_LOCATION", "United States"),
    "delay_min"             : _env("CRAWL_DELAY_MIN", "3.0", float),
    "delay_max"             : _env("CRAWL_DELAY_MAX", "5.5", float),
    "max_pages"             : _env("CRAWL_MAX_PAGES", "5", int),
    "usajobs_max_pages"     : _env("USAJOBS_MAX_PAGES", "3", int),

    "output_dir"            : _env("OUTPUT_DIR", "data/"),
    "raw_csv"               : _env("RAW_CSV", "data/us_jobs_raw.csv"),
    "parsed_csv"            : _env("PARSED_CSV", "data/us_jobs_parsed.csv"),
    "parse_cache"           : _env("PARSE_CACHE", "data/parse_cache.json"),
    "embed_cache_path"      : _env("EMBED_CACHE", "data/embed_cache.json"),

    "job_keywords": [
        "software engineer",
        "backend developer",
        "frontend developer",
        "full stack developer",
        "data scientist",
        "data analyst",
        "data engineer",
        "machine learning engineer",
        "AI engineer",
        "devops engineer",
        "cloud engineer",
        "cybersecurity analyst",
        "mobile developer",
        "site reliability engineer",
        "product manager",
        "UI UX designer",
        "solutions architect",
        "QA engineer",
    ],
}