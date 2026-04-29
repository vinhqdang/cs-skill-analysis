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

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(
            stream=open(sys.stdout.fileno(), mode="w", encoding="utf-8", buffering=1)
        ),
        logging.FileHandler("crawler.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)


def run_crawlers() -> pd.DataFrame:
    keywords  = CONFIG["job_keywords"]
    max_pages = CONFIG["max_pages"]
    all_jobs  = []

    logger.info("=" * 50)
    logger.info("Phase 1a: USAJobs Crawler")
    logger.info("=" * 50)
    try:
        usa = USAJobsCrawler(delay=CONFIG["delay_min"])
        usa_jobs = usa.crawl(keywords, max_pages=CONFIG["usajobs_max_pages"])
        all_jobs.extend(usa_jobs)
        logger.info(f"USAJobs: {len(usa_jobs)} jobs")
    except Exception as e:
        logger.error(f"USAJobs failed: {e}")

    logger.info("=" * 50)
    logger.info("Phase 1b: LinkedIn Crawler")
    logger.info("=" * 50)
    try:
        li = LinkedInCrawler(
            location=CONFIG["us_location"],
            headless=True,
            delay_min=CONFIG["delay_min"],
            delay_max=CONFIG["delay_max"],
        )
        li_jobs = li.crawl(keywords, max_pages=max_pages)
        all_jobs.extend(li_jobs)
        logger.info(f"LinkedIn: {len(li_jobs)} jobs")
    except Exception as e:
        logger.error(f"LinkedIn failed: {e}")

    if not all_jobs:
        logger.warning("No jobs collected!")
        return pd.DataFrame()

    os.makedirs(CONFIG["output_dir"], exist_ok=True)
    df = pd.DataFrame(all_jobs)
    df = df[df["job_title"] != ""]
    df = df.drop_duplicates(subset="url", keep="first")
    df = df.reset_index(drop=True)

    raw_path = CONFIG["raw_csv"]
    if os.path.exists(raw_path):
        df_existing = pd.read_csv(raw_path)
        df = pd.concat([df_existing, df], ignore_index=True)
        df = df.drop_duplicates(subset="url", keep="first")
        df = df.reset_index(drop=True)
        logger.info(f"Merged with existing data: {len(df)} total jobs")
    df.to_csv(raw_path, index=False, encoding="utf-8-sig")
    logger.info(f"Saved {len(df)} raw jobs to {raw_path}")
    return df


def run_dedup(df: pd.DataFrame) -> pd.DataFrame:
    logger.info("=" * 50)
    logger.info("Phase 2: Semantic Deduplication")
    logger.info("=" * 50)

    google_key = CONFIG.get("google_api_key", "")
    if not google_key:
        logger.warning("GOOGLE_API_KEY not set — skipping semantic dedup")
        return df

    df = deduplicate_jobs(
        df=df,
        google_api_key=google_key,
        similarity_threshold=CONFIG["dedup_sim_threshold"],
        description_overlap=CONFIG["dedup_desc_overlap"],
        embed_cache_path=CONFIG["embed_cache_path"],
        embed_model=CONFIG["embed_model"],
        embed_batch_size=CONFIG["embed_batch_size"],
    )
    logger.info(f"After dedup: {len(df)} unique jobs")
    return df


def run_parser(raw_override: str | None = None) -> pd.DataFrame:
    logger.info("=" * 50)
    logger.info("Phase 3: LLM Parser (Gemini 2.5 Flash)")
    logger.info("=" * 50)

    raw_path = raw_override if raw_override else CONFIG["raw_csv"]
    if not os.path.exists(raw_path):
        logger.error(f"Raw CSV not found: {raw_path}")
        logger.error("Run crawlers first, or check OUTPUT paths in .env")
        return pd.DataFrame()

    return parse_jobs(
        raw_csv_path=raw_path,
        parsed_csv_path=CONFIG["parsed_csv"],
        cache_path=CONFIG["parse_cache"],
        config=CONFIG,
    )


def main():
    parser = argparse.ArgumentParser(description="US Jobs Pipeline")
    parser.add_argument("--parse-only", action="store_true",
                        help="Skip crawling, dedup + parse existing raw CSV")
    parser.add_argument("--crawl-only", action="store_true",
                        help="Crawl + dedup only, skip LLM parsing")
    args = parser.parse_args()

    print("=" * 62)
    print("  US Tech Jobs Pipeline")
    print("  Crawl -> Dedup -> Parse -> CSV")
    print("=" * 62)

    if args.parse_only:
        raw_path = CONFIG["raw_csv"]
        if os.path.exists(raw_path):
            df = pd.read_csv(raw_path)
            df = run_dedup(df)
            # Save deduped data to a temp file for parser to read
            deduped_path = CONFIG["parsed_csv"].replace("parsed", "deduped")
            df.to_csv(deduped_path, index=False, encoding="utf-8-sig")
            run_parser(raw_override=deduped_path)
        else:
            run_parser()

    elif args.crawl_only:
        df = run_crawlers()
        if not df.empty:
            run_dedup(df)

    else:
        df = run_crawlers()
        if not df.empty:
            df = run_dedup(df)
            deduped_path = CONFIG["parsed_csv"].replace("parsed", "deduped")
            df.to_csv(deduped_path, index=False, encoding="utf-8-sig")
            run_parser(raw_override=deduped_path)
        else:
            run_parser()

    logger.info("Pipeline complete!")
    print(f"\nOutput: {CONFIG['parsed_csv']}")


if __name__ == "__main__":
    main()