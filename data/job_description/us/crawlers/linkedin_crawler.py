# type: ignore

import re
import os
import json
import time
import random
import logging
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
from utils.data_cleaner import clean

logger = logging.getLogger(__name__)

TRIGGERS = (
    "develop", "design", "build", "maintain", "manage", "implement",
    "collaborate", "deploy", "support", "ensure", "monitor", "create",
    "write", "test", "analyse", "analyze", "responsible", "require",
    "must", "skill", "ability", "work with", "familiar", "bachelor",
    "degree", "year", "strong", "understanding", "proven", "hands-on",
    "minimum", "experience", "knowledge", "proficient",
)


def extract_job_id(url: str) -> str:
    for pattern in [r"/view/(\d+)", r"-(\d+)\?", r"-(\d+)$", r"jobPosting/(\d+)"]:
        m = re.search(pattern, url)
        if m:
            return m.group(1)
    return ""


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


def parse_search_page(html: str, keyword: str, seen_ids: set) -> list:
    soup = BeautifulSoup(html, "lxml")
    found = []

    cards = (
        soup.find_all("div", class_=re.compile(r"base-card")) or
        soup.find_all("li", class_=re.compile(r"jobs-search-results__list-item")) or
        soup.find_all("div", class_=re.compile(r"job-search-card")) or
        soup.find_all("li", class_=re.compile(r"result-card")) or
        soup.find_all("div", attrs={"data-entity-urn": re.compile(r"jobPosting")})
    )

    for card in cards:
        title_el = (
            card.find("h3", class_=re.compile(r"base-search-card__title|title")) or
            card.find("h3") or card.find("h2")
        )
        company_el = (
            card.find("h4", class_=re.compile(r"base-search-card__subtitle|company")) or
            card.find("a", class_=re.compile(r"hidden-nested-link")) or
            card.find("h4")
        )
        loc_el = (
            card.find("span", class_=re.compile(r"job-search-card__location|location")) or
            card.find("span", class_=re.compile(r"subtitle"))
        )
        date_el = card.find("time")

        url = ""
        urn = card.get("data-entity-urn", "")
        if urn:
            job_num = re.search(r":(\d+)$", urn)
            if job_num:
                url = f"https://www.linkedin.com/jobs/view/{job_num.group(1)}"
        if not url:
            link_el = (
                card.find("a", class_=re.compile(r"base-card__full-link|result-card__full-card-link")) or
                card.find("a", href=re.compile(r"/jobs/view/"))
            )
            if link_el:
                url = link_el.get("href", "").split("?")[0]

        title   = clean(title_el.get_text())   if title_el   else ""
        company = clean(company_el.get_text()) if company_el else ""
        loc     = clean(loc_el.get_text())     if loc_el     else ""
        date    = date_el.get("datetime", "")  if date_el    else ""
        job_id  = extract_job_id(url)

        if not title or not job_id or job_id in seen_ids:
            continue

        seen_ids.add(job_id)
        found.append({
            "source"          : "LinkedIn",
            "search_keyword"  : keyword,
            "job_id"          : job_id,
            "job_title"       : title,
            "company"         : company,
            "location"        : loc,
            "posted_date"     : date,
            "url"             : url,
            "seniority_level" : "",
            "employment_type" : "",
            "job_function"    : "",
            "industries"      : "",
            "skills"          : "",
            "key_points"      : "",
            "full_description": "",
        })

    return found


def parse_job_detail(html: str) -> dict:
    soup = BeautifulSoup(html, "lxml")
    result = {
        "seniority_level" : "",
        "employment_type" : "",
        "job_function"    : "",
        "industries"      : "",
        "skills"          : "",
        "key_points"      : "",
        "full_description": "",
    }

    desc_el = (
        soup.find("div", class_=re.compile(r"show-more-less-html__markup")) or
        soup.find("div", class_=re.compile(r"description__text")) or
        soup.find("div", class_=re.compile(r"job-view-layout")) or
        soup.find("section", class_=re.compile(r"description")) or
        soup.find("div", {"id": re.compile(r"job-details|jobDescriptionText")})
    )
    desc_text = clean(desc_el.get_text(separator=" ")) if desc_el else ""
    result["full_description"] = desc_text[:3000]
    result["key_points"]       = extract_key_points(desc_text)

    for item in soup.find_all("li", class_=re.compile(r"description__job-criteria-item")):
        lbl = item.find("h3") or item.find("span", class_=re.compile(r"label"))
        val = (
            item.find("span", class_=re.compile(r"description__job-criteria-text")) or
            item.find("span", recursive=False)
        )
        if lbl and val:
            k, v = clean(lbl.get_text()), clean(val.get_text())
            if "Seniority"  in k: result["seniority_level"] = v
            if "Employment" in k: result["employment_type"] = v
            if "function"   in k: result["job_function"]    = v
            if "Industr"    in k: result["industries"]       = v

    for dt in soup.find_all("dt"):
        dd = dt.find_next_sibling("dd")
        if not dd:
            continue
        k, v = clean(dt.get_text()), clean(dd.get_text())
        if "Seniority"  in k: result["seniority_level"] = result["seniority_level"] or v
        if "Employment" in k: result["employment_type"] = result["employment_type"] or v
        if "function"   in k: result["job_function"]    = result["job_function"]    or v
        if "Industr"    in k: result["industries"]       = result["industries"]       or v

    skill_els = (
        soup.select("button.job-details-preferences-and-skills__pill span") or
        soup.select(".job-details-skill-match-status-list span") or
        soup.select("[class*='skill-pill'] span") or
        soup.select("a[data-tracking-control-name*='skill']") or
        soup.select("[class*='skills'] li")
    )
    skills_from_page = ", ".join(
        clean(s.get_text())
        for s in skill_els
        if clean(s.get_text()) and len(clean(s.get_text())) < 50
    )

    result["skills"] = skills_from_page
    return result


class LinkedInCrawler:
    SEARCH_API = (
        "https://www.linkedin.com/jobs-guest/jobs/api/"
        "seeMoreJobPostings/search"
    )
    DETAIL_API = (
        "https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{job_id}"
    )

    def __init__(
        self,
        location    : str   = "United States",
        headless    : bool  = True,
        delay_min   : float = 3.0,
        delay_max   : float = 5.5,
        existing_ids: set   = None,
    ):
        self.location  = location
        self.headless  = headless
        self.delay_min = delay_min
        self.delay_max = delay_max
        self.seen_ids: set = set(existing_ids) if existing_ids else set()

    def _launch_browser(self, playwright):
        browser = playwright.chromium.launch(
            headless=self.headless,
            args=[
                "--no-sandbox",
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
            ],
        )
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1366, "height": 768},
            locale="en-US",
            extra_http_headers={"Accept-Language": "en-US,en;q=0.9"},
        )
        return browser, context

    def _collect_cards(self, page, keywords: list, jobs_per_keyword: int) -> list:
        all_cards = []

        for keyword in keywords:
            logger.info(f"[{self.location}] keyword: '{keyword}'")
            kw_count = 0
            start    = 0

            while kw_count < jobs_per_keyword:
                url = (
                    f"{self.SEARCH_API}"
                    f"?keywords={keyword.replace(' ', '%20')}"
                    f"&location={self.location.replace(' ', '%20')}"
                    f"&f_TPR=r2592000"
                    f"&start={start}"
                )

                try:
                    page.goto(url, wait_until="domcontentloaded", timeout=25000)
                    page.wait_for_timeout(2000)
                    html = page.content()
                except PlaywrightTimeout:
                    logger.warning(f"   Timeout at offset {start}")
                    break

                batch = parse_search_page(html, keyword, self.seen_ids)

                if not batch:
                    if any(w in html.lower() for w in ["authwall", "sign in", "join now"]):
                        logger.warning("   LinkedIn block detected - pausing 15s.")
                        time.sleep(15)
                    else:
                        logger.info(f"   No more jobs found at offset {start}")
                    break

                all_cards.extend(batch)
                kw_count += len(batch)
                start    += 25
                time.sleep(random.uniform(self.delay_min, self.delay_max))

            logger.info(f"   [{self.location}] {kw_count} cards for '{keyword}'")

        return all_cards

    BROWSER_RESTART_EVERY = 100

    def _enrich_jobs(self, playwright, jobs: list, checkpoint_path: str = None) -> list:
        loc = self.location
        checkpoint = {}
        if checkpoint_path and os.path.exists(checkpoint_path):
            try:
                with open(checkpoint_path, "r", encoding="utf-8") as f:
                    checkpoint = json.load(f)
                logger.info(f"[{loc}] Enrich checkpoint loaded: {len(checkpoint)} jobs cached")
            except Exception:
                checkpoint = {}

        total       = len(jobs)
        cached_count = sum(1 for j in jobs if str(j["job_id"]) in checkpoint)
        logger.info(f"[{loc}] Enriching {total} jobs — {cached_count} from cache, {total - cached_count} to fetch")

        browser, context = self._launch_browser(playwright)
        page = context.new_page()
        fetch_count = 0
        restarts    = 0

        for i, job in enumerate(jobs):
            job_id = str(job["job_id"])

            if job_id in checkpoint:
                job.update(checkpoint[job_id])
                logger.info(f"   [{loc}] [{i+1:>3}/{total}] {job['job_title'][:38]:<38} [cached]")
                continue

            if fetch_count > 0 and fetch_count % self.BROWSER_RESTART_EVERY == 0:
                try:
                    browser.close()
                except Exception:
                    pass
                restarts += 1
                logger.info(f"   [{loc}] Browser restart #{restarts} at fetch {fetch_count}")
                browser, context = self._launch_browser(playwright)
                page = context.new_page()

            detail_url = self.DETAIL_API.format(job_id=job_id)

            try:
                page.goto(detail_url, wait_until="domcontentloaded", timeout=25000)
                page.wait_for_timeout(2000)
                html = page.content()
            except PlaywrightTimeout:
                logger.warning(f"   [{loc}] Timeout - job_id {job_id}")
                fetch_count += 1
                continue
            except Exception as e:
                if "Connection closed" in str(e) or "Target closed" in str(e):
                    logger.warning(f"   [{loc}] Browser disconnected at job {i} — restarting")
                    try:
                        browser.close()
                    except Exception:
                        pass
                    browser, context = self._launch_browser(playwright)
                    page = context.new_page()
                    try:
                        page.goto(detail_url, wait_until="domcontentloaded", timeout=25000)
                        page.wait_for_timeout(2000)
                        html = page.content()
                    except Exception:
                        logger.warning(f"   [{loc}] Retry failed - job_id {job_id}")
                        fetch_count += 1
                        continue
                else:
                    logger.warning(f"   [{loc}] Error fetching job_id {job_id}: {e}")
                    fetch_count += 1
                    continue

            details = parse_job_detail(html)
            job.update(details)
            fetch_count += 1

            if checkpoint_path:
                checkpoint[job_id] = details
                try:
                    with open(checkpoint_path, "w", encoding="utf-8") as f:
                        json.dump(checkpoint, f, ensure_ascii=False)
                except Exception:
                    pass

            logger.info(
                f"   [{loc}] [{i+1:>3}/{total}] {job['job_title'][:38]:<38} "
                f"skills={len(job['skills'].split(',')) if job['skills'] else 0} "
                f"desc={len(job['full_description']):>4}ch"
            )
            time.sleep(random.uniform(self.delay_min, self.delay_max))

        try:
            browser.close()
        except Exception:
            pass

        return jobs

    def crawl(self, keywords: list, max_pages: int = 3, checkpoint_path: str = None) -> list:
        jobs_per_keyword = max_pages * 25
        all_jobs = []
        loc = self.location

        with sync_playwright() as p:
            browser, context = self._launch_browser(p)
            page = context.new_page()

            try:
                all_jobs = self._collect_cards(page, keywords, jobs_per_keyword)
                logger.info(f"[{loc}] Total cards collected: {len(all_jobs)}")
            except Exception as e:
                logger.error(f"[{loc}] LinkedIn crawl error (collect): {e}")
            finally:
                try:
                    browser.close()
                except Exception:
                    pass

            try:
                all_jobs = self._enrich_jobs(p, all_jobs, checkpoint_path=checkpoint_path)
            except Exception as e:
                logger.error(f"[{loc}] LinkedIn crawl error (enrich): {e}")

        return all_jobs