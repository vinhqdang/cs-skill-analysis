import sys
import os
import logging
import argparse
import pandas as pd

from config import CONFIG
from crawlers.linkedin_crawler import LinkedInCrawler
from crawlers.usajobs_crawler import USAJobsCrawler
from dedup.embedding_dedup import deduplicate_jobs
from parser.llm_parser import parse_jobs

class _OneLiner(logging.Formatter):
    def format(self, record):
        msg = super().format(record)
        return msg.replace("\r\n", " ").replace("\r", " ").replace("\n", " ")


_fmt = "%(asctime)s [%(levelname)s] %(message)s"
_formatter = _OneLiner(_fmt)

_stream_handler = logging.StreamHandler(
    stream=open(sys.stdout.fileno(), mode="w", encoding="utf-8", buffering=1)
)
_stream_handler.setFormatter(_formatter)

_file_handler = logging.FileHandler("crawler.log", encoding="utf-8")
_file_handler.setFormatter(_formatter)

logging.basicConfig(level=logging.INFO, handlers=[_stream_handler, _file_handler])
logger = logging.getLogger(__name__)

COUNTRY_SLUG = {
    "Vietnam":        "vn",
    "Singapore":      "sg",
    "United Kingdom": "uk",
    "United States":  "us",
}


def get_slug(country: str) -> str:
    return COUNTRY_SLUG.get(country, country.lower().replace(" ", "_"))


def country_paths(country: str) -> dict:
    slug = get_slug(country)
    d    = CONFIG["output_dir"]
    return {
        "raw":          os.path.join(d, f"{slug}_jobs_raw.csv"),
        "deduped":      os.path.join(d, f"{slug}_jobs_deduped.csv"),
        "parsed":       os.path.join(d, f"{slug}_jobs_parsed.csv"),
        "parse_cache":  os.path.join(d, f"{slug}_parse_cache.json"),
        "embed_cache":  os.path.join(d, f"{slug}_embed_cache.json"),
        "enrich_cache": os.path.join(d, f"{slug}_enrich_cache.json"),
    }


def _save_location_raw(loc: str, loc_jobs: list) -> pd.DataFrame:
    os.makedirs(CONFIG["output_dir"], exist_ok=True)
    paths = country_paths(loc)
    df = pd.DataFrame(loc_jobs)
    df = df[df["job_title"] != ""].drop_duplicates(subset="url", keep="first").reset_index(drop=True)
    if os.path.exists(paths["raw"]):
        existing = pd.read_csv(paths["raw"])
        df = pd.concat([existing, df], ignore_index=True)
        df = df.drop_duplicates(subset="url", keep="first").reset_index(drop=True)
        logger.info(f"[{loc}] Merged with existing: {len(df)} total")
    df.to_csv(paths["raw"], index=False, encoding="utf-8-sig")
    logger.info(f"[{loc}] Saved {len(df)} raw jobs → {paths['raw']}")
    return df


def run_crawlers() -> dict:
    keywords  = CONFIG["job_keywords"]
    max_pages = CONFIG["max_pages"]
    country_dfs = {}

    for loc in CONFIG["locations"]:
        logger.info("=" * 50)
        logger.info(f"Location: {loc}")
        logger.info("=" * 50)
        loc_jobs = []
        paths    = country_paths(loc)

        is_us = "united states" in loc.lower() or loc.lower() == "us"
        if is_us:
            logger.info(f"--- USAJobs [{loc}] ---")
            try:
                usa      = USAJobsCrawler(delay=CONFIG["delay_min"])
                usa_jobs = usa.crawl(keywords, max_pages=CONFIG["usajobs_max_pages"])
                for j in usa_jobs:
                    j["country"] = loc
                loc_jobs.extend(usa_jobs)
                logger.info(f"[{loc}] USAJobs: {len(usa_jobs)} jobs collected")
            except Exception as e:
                logger.error(f"[{loc}] USAJobs failed: {e}")

        logger.info(f"--- LinkedIn [{loc}] ---")
        try:
            existing_ids = set()
            if os.path.exists(paths["raw"]):
                existing_df  = pd.read_csv(paths["raw"], usecols=["job_id"])
                existing_ids = set(existing_df["job_id"].dropna().astype(str))
                logger.info(f"[{loc}] Skipping {len(existing_ids)} already-crawled job IDs")

            li      = LinkedInCrawler(
                location=loc,
                headless=True,
                delay_min=CONFIG["delay_min"],
                delay_max=CONFIG["delay_max"],
                existing_ids=existing_ids,
            )
            li_jobs = li.crawl(keywords, max_pages=max_pages, checkpoint_path=paths["enrich_cache"])
            for j in li_jobs:
                j["country"] = loc
            loc_jobs.extend(li_jobs)
            logger.info(f"[{loc}] LinkedIn: {len(li_jobs)} jobs collected")
        except Exception as e:
            logger.error(f"[{loc}] LinkedIn failed: {e}")

        if not loc_jobs:
            logger.warning(f"[{loc}] No jobs collected — skipping save")
            continue

        country_dfs[loc] = _save_location_raw(loc, loc_jobs)

    return country_dfs


def run_dedup(df: pd.DataFrame, embed_cache_path: str) -> pd.DataFrame:
    google_key = CONFIG.get("google_api_key", "")
    if not google_key:
        logger.warning("GOOGLE_API_KEY not set — skipping semantic dedup")
        return df

    df = deduplicate_jobs(
        df=df,
        google_api_key=google_key,
        similarity_threshold=CONFIG["dedup_sim_threshold"],
        description_overlap=CONFIG["dedup_desc_overlap"],
        embed_cache_path=embed_cache_path,
        embed_model=CONFIG["embed_model"],
        embed_batch_size=CONFIG["embed_batch_size"],
    )
    logger.info(f"After dedup: {len(df)} unique jobs")
    return df


def run_parser(raw_path: str, parsed_path: str, cache_path: str) -> pd.DataFrame:
    if not os.path.exists(raw_path):
        logger.error(f"Raw CSV not found: {raw_path}")
        return pd.DataFrame()

    return parse_jobs(
        raw_csv_path=raw_path,
        parsed_csv_path=parsed_path,
        cache_path=cache_path,
        config=CONFIG,
    )


def process_country(country: str, df: pd.DataFrame):
    paths = country_paths(country)

    logger.info("=" * 50)
    logger.info(f"Phase 2: Dedup — {country}")
    logger.info("=" * 50)
    df = run_dedup(df, paths["embed_cache"])
    df.to_csv(paths["deduped"], index=False, encoding="utf-8-sig")

    logger.info("=" * 50)
    logger.info(f"Phase 3: LLM Parse — {country}")
    logger.info("=" * 50)
    run_parser(paths["deduped"], paths["parsed"], paths["parse_cache"])


def main():
    parser = argparse.ArgumentParser(description="Tech Jobs Pipeline (per-country)")
    parser.add_argument("--parse-only", action="store_true",
                        help="Skip crawling; dedup + parse existing raw CSVs")
    parser.add_argument("--crawl-only", action="store_true",
                        help="Crawl + dedup only, skip LLM parsing")
    args = parser.parse_args()

    print("=" * 62)
    print("  Tech Jobs Pipeline  —  per-country output")
    print("  Crawl -> Dedup -> Parse -> CSV")
    print("=" * 62)

    if args.parse_only:
        deduped = {}
        for country in CONFIG["locations"]:
            paths = country_paths(country)
            if not os.path.exists(paths["raw"]):
                logger.warning(f"No raw data for {country}: {paths['raw']}")
                continue
            logger.info("=" * 50)
            logger.info(f"Phase 2: Dedup — {country}")
            logger.info("=" * 50)
            df = pd.read_csv(paths["raw"])
            df = run_dedup(df, paths["embed_cache"])
            df.to_csv(paths["deduped"], index=False, encoding="utf-8-sig")
            deduped[country] = paths

        for country, paths in deduped.items():
            logger.info("=" * 50)
            logger.info(f"Phase 3: LLM Parse — {country}")
            logger.info("=" * 50)
            run_parser(paths["deduped"], paths["parsed"], paths["parse_cache"])

    elif args.crawl_only:
        country_dfs = run_crawlers()
        for country, df in country_dfs.items():
            paths = country_paths(country)
            df    = run_dedup(df, paths["embed_cache"])
            df.to_csv(paths["deduped"], index=False, encoding="utf-8-sig")

    else:
        country_dfs = run_crawlers()
        deduped = {}
        for country, df in country_dfs.items():
            paths = country_paths(country)
            logger.info("=" * 50)
            logger.info(f"Phase 2: Dedup — {country}")
            logger.info("=" * 50)
            df = run_dedup(df, paths["embed_cache"])
            df.to_csv(paths["deduped"], index=False, encoding="utf-8-sig")
            deduped[country] = paths

        for country, paths in deduped.items():
            logger.info("=" * 50)
            logger.info(f"Phase 3: LLM Parse — {country}")
            logger.info("=" * 50)
            run_parser(paths["deduped"], paths["parsed"], paths["parse_cache"])

    logger.info("Pipeline complete!")
    print()
    for country in CONFIG["locations"]:
        paths = country_paths(country)
        if os.path.exists(paths["parsed"]):
            print(f"Output ({country}): {paths['parsed']}")


if __name__ == "__main__":
    main()
