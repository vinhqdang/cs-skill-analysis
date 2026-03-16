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
