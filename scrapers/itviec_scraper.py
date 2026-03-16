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
