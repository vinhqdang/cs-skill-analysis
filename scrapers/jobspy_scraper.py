import time
import pandas as pd
from jobspy import scrape_jobs

SEARCH_TERMS = [
    "software engineer", "data engineer", "machine learning engineer",
    "frontend developer", "backend developer", "DevOps engineer",
    "cybersecurity engineer", "cloud engineer", "mobile developer"
]

# Defining target markets: Vietnam (primary), Asia, and Global
LOCATIONS = [
    {"name": "Vietnam", "location": "Vietnam", "country_indeed": "Vietnam"},
    {"name": "Asia", "location": "Singapore", "country_indeed": "Singapore"},
    {"name": "Global", "location": "United States", "country_indeed": "USA"}
]

for loc in LOCATIONS:
    all_jobs = []
    print(f"\n--- Starting scraping for {loc['name']} ---")
    for term in SEARCH_TERMS:
        print(f"Scraping: {term} in {loc['name']}")
        try:
            df = scrape_jobs(
                site_name=["indeed", "linkedin"],
                search_term=term,
                location=loc["location"],
                country_indeed=loc["country_indeed"],
                results_wanted=300,
                hours_old=43800,             # last 5 years
                description_format="markdown"
            )
            df["search_term"] = term
            df["region"] = loc["name"]
            all_jobs.append(df)
        except Exception as e:
            print(f"Error scraping {term} in {loc['name']}: {e}")
        time.sleep(3)                    # be polite between search terms

    if all_jobs:
        combined = pd.concat(all_jobs).drop_duplicates(subset="job_url")
        filename = f"data/raw/job_postings/jobspy_{loc['name'].lower()}.json"
        combined.to_json(filename, orient="records", indent=4)
        print(f"Total: {len(combined)} jobs saved to {filename}")
