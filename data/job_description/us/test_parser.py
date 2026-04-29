#type: ignore
# test_parser.py
"""
Quick test script: runs the LLM parser on the first 5 rows of the deduped CSV.
Uses isolated test output files so your real cache and parsed CSV are untouched.
"""

import logging
from unittest import result
import pandas as pd
from config import CONFIG
from parser.llm_parser import parse_jobs

# ---------- Logging setup ----------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


def main():
    # ---------- Paths ----------
    source_csv       = "data/us_jobs_deduped.csv"          # input: deduped data
    test_input_csv   = "data/us_jobs_deduped_test5.csv"    # temp: 5-row slice
    test_output_csv  = "data/us_jobs_parsed_test5.csv"     # output: parsed result
    test_cache_json  = "data/parse_cache_test5.json"       # isolated cache

    # ---------- Step 1: Load deduped CSV and take first 5 rows ----------
    logger.info(f"Loading {source_csv}")
    df = pd.read_csv(source_csv)
    logger.info(f"Full deduped file has {len(df)} rows")

    df_small = df.head(5).copy()
    logger.info(f"Taking first {len(df_small)} rows for test")

    # ---------- Step 2: Save the slice to a temp CSV ----------
    df_small.to_csv(test_input_csv, index=False, encoding="utf-8-sig")
    logger.info(f"Saved 5-row test input to {test_input_csv}")

    # ---------- Step 3: Run the parser on the small file ----------
    logger.info("Starting LLM parser...")
    result = parse_jobs(
        raw_csv_path=test_input_csv,
        parsed_csv_path=test_output_csv,
        cache_path=test_cache_json,
        config=CONFIG,
    )

    # ---------- Step 4: Show what came back ----------
    if result.empty:
        logger.error("Parser returned empty DataFrame — check logs above for errors")
        return

    logger.info(f"Parsed {len(result)} rows")
    logger.info(f"Output saved to {test_output_csv}")

    print("\n" + "=" * 70)
    print("  PARSED RESULTS (key fields)")
    print("=" * 70)

    preview_cols = [
        "job_title",
        "parsed_title",
        "seniority",
        "min_years_exp",
        "employment_type",
        "remote_status",
        "salary_min_annual",
        "salary_max_annual",
        "education",
        "job_category",
    ]
    available = [c for c in preview_cols if c in result.columns]
    print(result[available].to_string(index=False))

    print("\n" + "=" * 70)
    print("  SKILLS EXTRACTED")
    print("=" * 70)
    for i, row in result.iterrows():
        print(f"\n[{i+1}] {row.get('parsed_title', 'N/A')}")
        print(f"    Hard skills: {row.get('hard_skills', '')}")
        print(f"    Soft skills: {row.get('soft_skills', '')}")

    print("\nDone.")


if __name__ == "__main__":
    main()