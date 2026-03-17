import cloudscraper
import pandas as pd
import time
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}
BASE_URL = "https://itviec.com"
scraper = cloudscraper.create_scraper()

def get_job_links(keyword="it", pages=20):
    links = []
    for page in range(1, pages + 1):
        url = f"{BASE_URL}/it-jobs/{keyword}?page={page}"
        try:
            r = scraper.get(url)
            soup = BeautifulSoup(r.text, "html.parser")
            cards = soup.select(".job-card")
            for card in cards:
                uri = card.get("data-search--job-selection-job-url-value")
                if uri and "/content" in uri:
                    uri = uri.split("/content")[0]
                    links.append(BASE_URL + uri)
            time.sleep(1.5)
        except Exception as e:
            print(f"Error fetching list page {page}: {e}")
    return list(set(links))

def get_job_detail(url):
    r = scraper.get(url)
    soup = BeautifulSoup(r.text, "html.parser")
    title_el = soup.select_one("h1")
    company_el = soup.select_one(".employer-name, .company-name, .employer-long-overview__name")
    desc_el = soup.select_one(".job-details__paragraph, .paragraph, .job-description")
    tags = soup.select(".itag, .tag-item, .job-details__tag")
    loc_el = soup.select_one(".address, .job-details__overview .text-truncate")

    return {
        "url": url,
        "title": title_el.text.strip() if title_el else "",
        "company": company_el.text.strip() if company_el else "",
        "description": desc_el.text.strip() if desc_el else "",
        "skills_tags": [t.text.strip() for t in tags] if tags else [],
        "location": loc_el.text.strip() if loc_el else "",
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
                print(f"Error reading detail: {e}")
    
    if all_jobs:
        df = pd.DataFrame(all_jobs).drop_duplicates(subset="url")
        df.to_json("data/raw/job_postings/itviec.json", orient="records", indent=4)
        print(f"Saved {len(df)} jobs")
    else:
        print("No jobs found")
