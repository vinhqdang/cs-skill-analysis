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

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "api" and ALGOLIA_API_KEY != "your_public_key_here":
        print("Using Algolia API")
        results = search_jobs("it", pages=10)
        df = pd.DataFrame(results)
    else:
        print("Using HTML fallback for VietnamWorks since API key might need manual updating.")
        df = scrape_html_fallback(keyword="it", pages=10)
    df.to_json("data/raw/job_postings/vietnamworks.json", orient="records", indent=4)
    print(f"Saved {len(df)} jobs")
