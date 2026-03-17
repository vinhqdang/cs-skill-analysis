import cloudscraper
from bs4 import BeautifulSoup

url = "https://itviec.com/it-jobs/data-engineer-python-sql-cong-ty-co-phan-nghien-cuu-phat-trien-va-ung-dung-nguoi-may-da-nang-vinmotion-2823"
scraper = cloudscraper.create_scraper()
r = scraper.get(url)
soup = BeautifulSoup(r.text, "html.parser")

company_node = soup.select_one(".employer-name, .company-name")
if company_node: print("Company node text:", company_node.text.strip())

desc_node = soup.select_one(".job-details__paragraph, .paragraph")
if desc_node: print("Desc node text:", desc_node.text.strip()[:100])

print("\n--- Body Snippet ---")
# Find some headings like "Company", "Job Description"
print(soup.prettify()[10000:12000])
