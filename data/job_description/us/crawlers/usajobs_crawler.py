import re
import time
import logging
import requests
from config import CONFIG
from utils.data_cleaner import clean, clean_job_entry

logger = logging.getLogger(__name__)

ALL_SKILLS = [
    "Python", "Java", "JavaScript", "TypeScript", "C++", "C#", "Go",
    "Rust", "Kotlin", "Swift", "PHP", "Ruby", "Scala", "R", "MATLAB",
    "React", "Vue", "Angular",
    "Node.js", "Django", "FastAPI", "Spring Boot", ".NET",
    "SQL", "MySQL", "PostgreSQL", "MongoDB", "Redis", "Elasticsearch",
    "AWS", "GCP", "Azure",
    "Docker", "Kubernetes", "Terraform", "Ansible", "Jenkins",
    "Git", "CI/CD", "Linux",
    "Machine Learning", "Deep Learning", "TensorFlow", "PyTorch",
    "Pandas", "Spark", "Kafka", "Hadoop", "Tableau", "Power BI",
    "OpenCV",
    "REST", "GraphQL",
    "Figma", "Agile", "Scrum",
    "Flutter",
]

TRIGGERS = (
    "develop", "design", "build", "maintain", "manage", "implement",
    "collaborate", "deploy", "support", "ensure", "monitor", "create",
    "write", "test", "analyse", "analyze", "responsible", "require",
    "must", "skill", "ability", "work with", "familiar", "bachelor",
    "degree", "year", "strong", "understanding", "proven", "hands-on",
    "minimum", "experience", "knowledge", "proficient",
)


def extract_key_points(description: str, max_points: int = 7) -> str:
    lines = re.split(r"[\n•\-–●▪◆]|(?<=[.!?])\s{1,3}", description)
    points = []
    for line in lines:
        line = clean(line)
        if 25 <= len(line) <= 250 and any(t in line.lower() for t in TRIGGERS):
            points.append("- " + line)
        if len(points) >= max_points:
            break
    return "\n".join(points) if points else ""


def extract_skills(text: str) -> str:
    if not text:
        return ""
    found = [s for s in ALL_SKILLS if re.search(rf"\b{re.escape(s)}\b", text, re.I)]
    return ", ".join(found)


class USAJobsCrawler:
    BASE_URL = "https://data.usajobs.gov/api/search"

    def __init__(self, delay: float = 1.0):
        self.delay   = delay
        self.api_key = CONFIG["usajobs_api_key"]
        self.email   = CONFIG["usajobs_email"]

    def _get_headers(self) -> dict:
        return {
            "Host"             : "data.usajobs.gov",
            "User-Agent"       : self.email,
            "Authorization-Key": self.api_key,
        }

    def fetch_jobs(self, keyword: str, page: int = 1) -> list:
        params = {
            "Keyword"       : keyword,
            "ResultsPerPage": 25,
            "Page"          : page,
        }

        try:
            response = requests.get(
                self.BASE_URL,
                params=params,
                headers=self._get_headers(),
                timeout=15,
            )
            response.raise_for_status()
            data = response.json()
        except Exception as e:
            logger.error(f"USAJobs API error for '{keyword}': {e}")
            return []

        items = data.get("SearchResult", {}).get("SearchResultItems", [])
        jobs  = []

        for item in items:
            d = item.get("MatchedObjectDescriptor", {})

            title   = d.get("PositionTitle", "")
            company = d.get("OrganizationName", "")
            url     = d.get("PositionURI", "")
            job_id  = d.get("MatchedObjectId", "")

            locations = d.get("PositionLocation", [{}])
            location  = ", ".join(
                loc.get("LocationName", "") for loc in locations
            )

            pay         = d.get("PositionRemuneration", [{}])
            salary_min  = pay[0].get("MinimumRange", "") if pay else ""
            salary_max  = pay[0].get("MaximumRange", "") if pay else ""
            salary_type = pay[0].get("RateIntervalCode", "") if pay else ""

            categories   = d.get("JobCategory", [{}])
            job_function = ", ".join(cat.get("Name", "") for cat in categories)

            posted_date = d.get("PublicationStartDate", "")[:10] if d.get("PublicationStartDate") else ""
            close_date  = d.get("ApplicationCloseDate", "")[:10] if d.get("ApplicationCloseDate") else ""

            employment_type = d.get("PositionSchedule", [{}])[0].get("Name", "") if d.get("PositionSchedule") else ""
            seniority_level = d.get("JobGrade", [{}])[0].get("Code", "")          if d.get("JobGrade")         else ""

            details        = d.get("UserArea", {}).get("Details", {})
            description    = clean(details.get("JobSummary",     ""))
            requirements   = clean(details.get("Requirements",   ""))
            qualifications = clean(details.get("Qualifications", ""))

            full_desc  = " ".join(filter(None, [description, requirements, qualifications]))
            skills     = extract_skills(full_desc)
            key_points = extract_key_points(full_desc)

            job = {
                "source"          : "USAJobs",
                "search_keyword"  : keyword,
                "job_id"          : job_id,
                "job_title"       : title,
                "company"         : company,
                "location"        : location,
                "posted_date"     : posted_date,
                "close_date"      : close_date,
                "salary_min"      : salary_min,
                "salary_max"      : salary_max,
                "salary_type"     : salary_type,
                "seniority_level" : seniority_level,
                "employment_type" : employment_type,
                "job_function"    : job_function,
                "industries"      : "Government",
                "skills"          : skills,
                "key_points"      : key_points,
                "full_description": full_desc[:3000],
                "url"             : url,
            }

            jobs.append(clean_job_entry(job))

        logger.info(f"   Page {page}: {len(jobs)} jobs fetched")
        return jobs

    def crawl(self, keywords: list, max_pages: int = 3) -> list:
        all_jobs = []

        for keyword in keywords:
            logger.info(f"USAJobs - keyword: '{keyword}'")
            for page in range(1, max_pages + 1):
                logger.info(f"   Page {page}/{max_pages}")
                jobs = self.fetch_jobs(keyword, page=page)

                if not jobs:
                    logger.info(f"   No more results for '{keyword}'")
                    break

                all_jobs.extend(jobs)
                time.sleep(self.delay)

        logger.info(f"USAJobs total: {len(all_jobs)} jobs collected")
        return all_jobs