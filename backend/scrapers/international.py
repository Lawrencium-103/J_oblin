"""
International job scraper — UK + EU + US + Remote.
Future-proof strategy (in priority order per board):
  1. Public JSON API (never changes with UI redesigns)
  2. schema.org/JobPosting JSON-LD (SEO data — admins rarely touch it)
  3. Multi-selector CSS fallback chain (catches most layout changes)
  4. Heuristic text extraction (last resort — always finds something)
"""
import json, re
from urllib.parse import quote
from .base import BaseScraper

CAT = "international"

_REMOTEOK_TAG_MAP = {
    "data analyst": "analyst", "data entry": "excel",
    "database administrator": "data", "dashboard developer": "bi",
    "monitoring and evaluation": "data", "m&e officer": "data",
    "meal officer": "data", "business intelligence analyst": "bi",
    "data associate": "analyst", "health data analyst": "analyst",
    "marketing analyst": "analyst", "ai data analyst": "ai",
}

# Common selector sets reused across scrapers
_TITLE_SELS    = ["h2 a","h3 a","h4 a","a.job-title","[class*='title'] a",
                  "a[class*='title']","a[class*='job']","a[class*='position']","a"]
_COMPANY_SELS  = ["[class*='company'] a","[class*='company']","[class*='employer']",
                  "[class*='recruiter']","[class*='org']","span[class*='name']"]
_LOCATION_SELS = ["[class*='location']","[class*='place']","[class*='city']",
                  "[class*='country']","span[class*='loc']","[class*='region']"]
_DATE_SELS     = ["time","[class*='date']","[class*='posted']","[class*='age']","span.date"]
_DESC_SELS     = ["[class*='desc']","[class*='excerpt']","[class*='snippet']","[class*='summary']","p"]


class InternationalJobScraper(BaseScraper):

    # ── RemoteOK — JSON API (most reliable, never changes) ─────────────────
    def scrape_remoteok(self, query: str) -> list[dict]:
        tag = _REMOTEOK_TAG_MAP.get(query.lower(), "data")
        data = self.fetch_json(f"https://remoteok.com/api?tag={quote(tag)}")
        if not isinstance(data, list):
            return []
        jobs = []
        for item in data[1:26]:
            if not isinstance(item, dict):
                continue
            title = item.get("position", "")
            url   = item.get("url", "") or f"https://remoteok.com/l/{item.get('slug','')}"
            if not title or not url:
                continue
            jobs.append(self._make_job(
                title, item.get("company",""), item.get("location","Remote"),
                (item.get("description","") or "")[:400],
                url, "remoteok", CAT, (item.get("date","") or "")[:10],
            ))
        return self.filter_fresh(jobs)

    # ── Remotive — JSON API ─────────────────────────────────────────────────
    def scrape_remotive(self, query: str) -> list[dict]:
        data = self.fetch_json(f"https://remotive.io/api/remote-jobs?search={quote(query)}&limit=25")
        if isinstance(data, dict) and data.get("jobs"):
            jobs = []
            for item in data["jobs"][:25]:
                title   = item.get("title","")
                url_val = item.get("url","") or f"https://remotive.com/remote-jobs/{item.get('id','')}"
                if not title:
                    continue
                jobs.append(self._make_job(
                    title, item.get("company_name",""),
                    item.get("candidate_required_location","Remote"),
                    re.sub(r"<[^>]+>","", (item.get("description","") or ""))[:400],
                    url_val, "remotive", CAT,
                    (item.get("publication_date","") or "")[:10],
                ))
            print(f"[remotive] {len(jobs)} jobs for '{query}'")
            return self.filter_fresh(jobs)
        # HTML fallback
        soup = self.fetch_soup(f"https://remotive.com/?search={quote(query)}")
        if not soup:
            return []
        cards = self.multi_select(soup, ["div.job","article.job","div[class*='job-card']","article","li"])
        return self._parse_cards(cards, "remotive", "https://remotive.com", 25)

    # ── Himalayas — JSON API ────────────────────────────────────────────────
    def scrape_himalayas_app(self, query: str) -> list[dict]:
        for api_url in [
            f"https://himalayas.app/jobs/api?q={quote(query)}",
            f"https://himalayas.app/jobs/api?query={quote(query)}",
        ]:
            data = self.fetch_json(api_url)
            if isinstance(data, dict) and data.get("jobs"):
                jobs = []
                for item in data["jobs"][:25]:
                    title   = item.get("title","")
                    url_val = item.get("url","")
                    if not title or not url_val:
                        continue
                    jobs.append(self._make_job(
                        title, item.get("company",""), item.get("location","Remote"),
                        (item.get("description","") or "")[:400],
                        url_val, "himalayas", CAT, (item.get("posted_date","") or "")[:10],
                    ))
                print(f"[himalayas] {len(jobs)} jobs for '{query}'")
        return self.filter_fresh(jobs)

    # ── Config name aliases ──────────────────────────────────────────────
    def scrape_himalayas(self, query: str) -> list[dict]:
        return self.scrape_himalayas_app(query)

    def scrape_remoteworkng(self, query: str) -> list[dict]:
        return self.scrape_remotework_ng(query)

    def scrape_realworkfromanywhere(self, query: str) -> list[dict]:
        from bs4 import BeautifulSoup
        url = "https://realworkfromanywhere.com/"
        soup = self.fetch_soup(url)
        if not soup:
            return []
        return self._extract_from_text(soup, "realworkfromanywhere", "https://realworkfromanywhere.com", CAT)
        # HTML fallback
        soup = self.fetch_soup(f"https://himalayas.app/jobs?q={quote(query)}")
        if soup:
            cards = self.multi_select(soup, ["div[class*='job-card']","div[class*='listing']","article","li"])
            result = self._parse_cards(cards, "himalayas", "https://himalayas.app", 25)
            if result:
                return result
            return self._extract_from_text(soup, "himalayas", "https://himalayas.app", CAT)
        return []

    # ── Reed.co.uk ─────────────────────────────────────────────────────────
    def scrape_reed(self, query: str) -> list[dict]:
        url  = f"https://www.reed.co.uk/jobs?keywords={quote(query)}&sortby=DisplayDate"
        soup = self.fetch_soup(url)
        if not soup:
            return []
        ld = self.fetch_json_ld(soup)
        if ld:
            for j in ld: j.update({"source": "reed", "category": CAT})
            return self.filter_fresh(ld[:25])
        cards = self.multi_select(soup, [
            "[data-qa='job-card']","article.job-result","[data-qa='job-result']",
            "article[class*='job']","div[class*='job-result']","article",
        ])
        jobs, seen = [], set()
        for card in cards[:25]:
            title = self.first_text(card, ["[data-qa='job-card-title']","h2 a","a[class*='title']"])
            href  = self.first_href(card, ["[data-qa='job-card-title']","h2 a","a[class*='title']"], "https://www.reed.co.uk")
            if not title or href in seen: continue
            seen.add(href)
            company_el = card.select_one("[class*='profileUrl'],[class*='recruiter'],[class*='company']")
            company    = self._clean_text(company_el.get_text()) if company_el else ""
            location   = self.first_text(card, ["[class*='jobMetadata__item']","[class*='location']"], "UK")
            posted     = self.first_text(card, _DATE_SELS)
            jobs.append(self._make_job(title, company, location, "", href, "reed", CAT, posted))
        if not jobs:
            return self._extract_from_text(soup, "reed", "https://www.reed.co.uk", CAT)
        return self.filter_fresh(jobs)

    # ── Adzuna UK ──────────────────────────────────────────────────────────
    def scrape_adzuna(self, query: str) -> list[dict]:
        url  = f"https://www.adzuna.co.uk/search?q={quote(query)}"
        soup = self.fetch_soup(url)
        if not soup:
            return []
        ld = self.fetch_json_ld(soup)
        if ld:
            for j in ld: j.update({"source": "adzuna", "category": CAT})
            return self.filter_fresh(ld[:20])
        cards = self.multi_select(soup, ["article[data-aid]","article.a","article","div[class*='result']"])
        jobs, seen = [], set()
        for card in cards[:20]:
            title    = self.first_text(card, ["h2 a","h3 a","[class*='title'] a"])
            href     = self.first_href(card, ["h2 a","h3 a"], "https://www.adzuna.co.uk")
            if not title or href in seen: continue
            seen.add(href)
            company  = self.first_text(card, [".ui-company","[class*='company']","[class*='employer']"])
            location = self.first_text(card, [".ui-location","[class*='location']"], "UK")
            salary   = self.first_text(card, [".ui-salary","[class*='salary']"])
            posted   = self.first_text(card, _DATE_SELS)
            desc     = self.first_text(card, [".max-snippet-height","[class*='snippet']"])
            if salary and "JOBSWORTH" not in salary.upper():
                desc = f"Salary: {salary} | {desc}"[:500]
            jobs.append(self._make_job(title, company, location, desc, href, "adzuna", CAT, posted))
        if not jobs:
            return self._extract_from_text(soup, "adzuna", "https://www.adzuna.co.uk", CAT)
        return self.filter_fresh(jobs)

    # ── WeWorkRemotely ─────────────────────────────────────────────────────
    def scrape_weworkremotely(self, query: str) -> list[dict]:
        url  = f"https://weworkremotely.com/remote-jobs/search?term={quote(query)}"
        soup = self.fetch_soup(url)
        if not soup:
            return []
        cards = self.multi_select(soup, ["li.job","li[class*='job']","section.jobs li","article","li"])
        jobs, seen = [], set()
        for card in cards[:25]:
            title    = self.first_text(card, ["span.title","h2","h3","a[class*='title']","a"])
            href     = self.first_href(card, ["a[href*='/remote-jobs/']","a"], "https://weworkremotely.com")
            if not title or href in seen: continue
            seen.add(href)
            company  = self.first_text(card, ["span.company","[class*='company']","[class*='employer']"])
            location = self.first_text(card, ["[class*='location']","[class*='region']","span.region"], "Remote")
            posted   = self.first_text(card, _DATE_SELS)
            jobs.append(self._make_job(title, company, location, "", href, "weworkremotely", CAT, posted))
        print(f"[weworkremotely] {len(jobs)} jobs for '{query}'")
        if not jobs:
            return self._extract_from_text(soup, "weworkremotely", "https://weworkremotely.com", CAT)
        return self.filter_fresh(jobs)

    # ── Indeed ─────────────────────────────────────────────────────────────
    def scrape_indeed(self, query: str) -> list[dict]:
        url  = f"https://www.indeed.com/jobs?q={quote(query)}&fromage=7"
        soup = self.fetch_soup(url)
        if not soup:
            return []
        ld = self.fetch_json_ld(soup)
        if ld:
            for j in ld: j.update({"source": "indeed", "category": CAT})
            return self.filter_fresh(ld[:20])
        cards = self.multi_select(soup, [
            "div[class*='job_seen_beacon']","div.jobsearch-SerpJobCard",
            "div[data-jk]","li[class*='result']","div[class*='tapItem']",
            "div.slider_item","td.resultContent","div[class*='css-'] article",
        ])
        result = self._parse_cards(cards, "indeed", "https://www.indeed.com")
        if not result:
            return self._extract_from_text(soup, "indeed", "https://www.indeed.com", CAT)
        return result

    # ── Glassdoor ──────────────────────────────────────────────────────────
    def scrape_glassdoor(self, query: str) -> list[dict]:
        url  = f"https://www.glassdoor.com/Job/jobs.htm?sc.keyword={quote(query)}"
        soup = self.fetch_soup(url)
        if not soup:
            return []
        ld = self.fetch_json_ld(soup)
        if ld:
            for j in ld: j.update({"source": "glassdoor", "category": CAT})
            return self.filter_fresh(ld[:20])
        cards = self.multi_select(soup, [
            "li[class*='JobsList_jobListItem']","li[class*='react-job-listing']",
            "article.jobCard","li.jl","div[data-test='job-listing']","li",
        ])
        result = self._parse_cards(cards, "glassdoor", "https://www.glassdoor.com")
        if not result:
            return self._extract_from_text(soup, "glassdoor", "https://www.glassdoor.com", CAT)
        return result

    # ── CWJobs (UK tech) ───────────────────────────────────────────────────
    def scrape_cwjobs(self, query: str) -> list[dict]:
        url  = f"https://www.cwjobs.co.uk/jobs?q={quote(query)}&sort=2"
        soup = self.fetch_soup(url)
        if not soup:
            return []
        ld = self.fetch_json_ld(soup)
        if ld:
            for j in ld: j.update({"source": "cwjobs", "category": CAT})
            return self.filter_fresh(ld[:20])
        cards = self.multi_select(soup, [
            "article[data-jobid]","article.job","div[class*='jobCard']",
            "div[class*='job-result']","article","div[data-jobid]",
        ])
        result = self._parse_cards(cards, "cwjobs", "https://www.cwjobs.co.uk")
        if not result:
            return self._extract_from_text(soup, "cwjobs", "https://www.cwjobs.co.uk", CAT)
        return result

    # ── EuroJobs ───────────────────────────────────────────────────────────
    def scrape_eurojobs(self, query: str) -> list[dict]:
        url  = f"https://www.eurojobs.com/jobs/?keywords={quote(query)}"
        soup = self.fetch_soup(url)
        if not soup:
            return []
        ld = self.fetch_json_ld(soup)
        if ld:
            for j in ld: j.update({"source": "eurojobs", "category": CAT})
            return self.filter_fresh(ld[:20])
        cards = self.multi_select(soup, [
            "div.job-item","article.job","li.job-item",
            "[class*='job-list-item']",".jobs-list > div","article",
        ])
        result = self._parse_cards(cards, "eurojobs", "https://www.eurojobs.com")
        if not result:
            return self._extract_from_text(soup, "eurojobs", "https://www.eurojobs.com", CAT)
        return result

    # ── LetsWorkRemotely ───────────────────────────────────────────────────
    def scrape_letsworkremotely(self, query: str) -> list[dict]:
        url  = f"https://letsworkremotely.com/remote-jobs/?search={quote(query)}"
        soup = self.fetch_soup(url)
        if not soup:
            return []
        cards = self.multi_select(soup, ["li.job-list","li[class*='job_listing']","article","li"])
        jobs, seen = [], set()
        for card in cards[:25]:
            title    = self.first_text(card, ["a[href*='/job/']","h2 a","h3 a","a"])
            href     = self.first_href(card, ["a[href*='/job/']","h2 a","a"], "https://letsworkremotely.com")
            if not title or href in seen: continue
            seen.add(href)
            company  = self.first_text(card, _COMPANY_SELS)
            location = self.first_text(card, _LOCATION_SELS)
            posted   = self.first_text(card, _DATE_SELS)
            desc     = self.first_text(card, _DESC_SELS)
            jobs.append(self._make_job(title, company, location, desc, href, "letsworkremotely", CAT, posted))
        if not jobs:
            return self._extract_from_text(soup, "letsworkremotely", "https://letsworkremotely.com", CAT)
        return self.filter_fresh(jobs)

    # ── RemoteWork.ng ──────────────────────────────────────────────────────
    def scrape_remotework_ng(self, query: str) -> list[dict]:
        url  = f"https://remotework.ng/?s={quote(query)}"
        soup = self.fetch_soup(url)
        if not soup:
            return []
        ld = self.fetch_json_ld(soup)
        if ld:
            for j in ld: j.update({"source": "remoteworkng", "category": CAT})
            return self.filter_fresh(ld[:20])
        cards = self.multi_select(soup, [
            "article.job","div.job-listing","div.job-card",
            "li.job_listing","article[class*='post']","div[class*='job']","article",
        ])
        result = self._parse_cards(cards, "remoteworkng", "https://remotework.ng", 20)
        if not result:
            return self._extract_from_text(soup, "remoteworkng", "https://remotework.ng", CAT)
        return result

    # ── WorkingNomads — JSON API ────────────────────────────────────────────
    def scrape_workingnomads(self, query: str) -> list[dict]:
        data = self.fetch_json("https://www.workingnomads.com/api/exposed_jobs/")
        if not isinstance(data, list):
            return []
        q_words = set(query.lower().split())
        jobs = []
        for item in data:
            title = item.get("title", "")
            combined = (
                title.lower() + " "
                + (item.get("tags", "") or "").lower() + " "
                + (item.get("category_name", "") or "").lower()
            )
            if not title or not q_words & set(combined.split()):
                continue
            url_val = item.get("url", "")
            if not url_val:
                continue
            posted_raw = item.get("date", "") or ""
            posted = posted_raw[:10] if posted_raw else ""
            if not posted:
                pub_date = item.get("publication_date", "") or ""
                posted = pub_date[:10] if pub_date else ""
            jobs.append(self._make_job(
                title, item.get("company_name", ""),
                item.get("location", "Remote"),
                re.sub(r"<[^>]+>", "", (item.get("description", "") or ""))[:400],
                url_val, "workingnomads", CAT,
                posted,
            ))
        return jobs[:25]

    # ── SkipTheDrive — HTML ──────────────────────────────────────────────────
    def scrape_skipthedrive(self, query: str) -> list[dict]:
        url = f"https://www.skipthedrive.com/?s={quote(query)}"
        soup = self.fetch_soup(url)
        if not soup:
            return []
        ld = self.fetch_json_ld(soup)
        if ld:
            for j in ld: j.update({"source": "skipthedrive", "category": CAT})
            return ld[:25]
        cards = self.multi_select(soup, [
            "article.post","article.job","div.job-listing","li.job-listing",
            "div[class*='job-card']","article","li",
        ])
        jobs, seen = [], set()
        for card in cards[:25]:
            try:
                title = self.first_text(card, ["h2 a","h3 a","a[class*='title']","strong a","a"])
                href = self.first_href(card, ["h2 a","h3 a","a[class*='title']","strong a","a"], "https://www.skipthedrive.com")
                if not title or not href or href in seen:
                    continue
                seen.add(href)
                company = self.first_text(card, [
                    "span.custom_fields_company_name_display_search_results",
                    "[class*='company_name']","[class*='company']","strong",
                ])
                location = self.first_text(card, _LOCATION_SELS, "Remote")
                posted = self.first_text(card, _DATE_SELS)
                desc = self.first_text(card, _DESC_SELS)
                jobs.append(self._make_job(title, company, location, desc, href, "skipthedrive", CAT, posted))
            except Exception:
                continue
        if not jobs:
            return self._extract_from_text(soup, "skipthedrive", "https://www.skipthedrive.com", CAT)
        return jobs[:25]

    # ── Playwright scrapers (JS-heavy / login sites) ───────────────────────

    def scrape_linkedin(self, query: str) -> list[dict]:
        return []

    async def scrape_indeed_playwright(self, page, query: str) -> list[dict]:
        from bs4 import BeautifulSoup
        try:
            await page.goto(f"https://www.indeed.com/jobs?q={quote(query)}&fromage=1", wait_until="domcontentloaded", timeout=45000)
            await page.wait_for_timeout(4000)
            soup = BeautifulSoup(await page.content(), "html.parser")
            ld = self.fetch_json_ld(soup)
            if ld:
                for j in ld: j.update({"source": "indeed", "category": CAT})
                return self.filter_fresh(ld[:20])
            cards = self.multi_select(soup, [
                "div[class*='job_seen_beacon']","div.jobsearch-SerpJobCard",
                "div[data-jk]","li[class*='result']","td.resultContent","article",
            ])
            result = self._parse_cards(cards, "indeed", "https://www.indeed.com")
            return result or self._extract_from_text(soup, "indeed", "https://www.indeed.com", CAT)
        except Exception as e:
            print(f"[indeed] playwright error: {e}")
        return []

    async def scrape_linkedin_playwright(self, page, query: str) -> list[dict]:
        from bs4 import BeautifulSoup
        try:
            await page.goto(f"https://www.linkedin.com/jobs/search/?keywords={quote(query)}&f_TPR=r86400", wait_until="domcontentloaded", timeout=45000)
            await page.wait_for_timeout(5000)
            soup = BeautifulSoup(await page.content(), "html.parser")
            cards = self.multi_select(soup, [
                "div.job-card-container","li[class*='job-card']",
                "div[class*='job-card']","div.base-card","article","li",
            ])
            seen = set()
            jobs = []
            for card in cards[:25]:
                try:
                    title_el = card.select_one("a[class*='title'],span[class*='title'],a[class*='job-title']")
                    if not title_el: continue
                    title = self._clean_text(title_el.get_text())
                    link_el = title_el if title_el.name == "a" else card.select_one("a[href*='jobs/view']")
                    href = link_el.get("href","") if link_el else ""
                    if not href: continue
                    job_url = href.split("?")[0]
                    if not job_url.startswith("http"):
                        job_url = f"https://www.linkedin.com{job_url}"
                    if job_url in seen: continue
                    seen.add(job_url)
                    company  = self.first_text(card, _COMPANY_SELS)
                    location = self.first_text(card, _LOCATION_SELS)
                    posted   = self.first_text(card, _DATE_SELS)
                    jobs.append(self._make_job(title, company, location, "", job_url, "linkedin", CAT, posted))
                except Exception:
                    continue
            return self.filter_fresh(jobs)
        except Exception as e:
            print(f"[linkedin] playwright error: {e}")
        return []

    # ── Rigzone (Oil & Gas) ─────────────────────────────────────────────────
    def scrape_rigzone(self, query: str) -> list[dict]:
        url  = f"https://www.rigzone.com/jobs/?searchterm={quote(query)}"
        soup = self.fetch_soup(url)
        if not soup:
            return []
        ld = self.fetch_json_ld(soup)
        if ld:
            for j in ld: j.update({"source": "rigzone", "category": CAT})
            return self.filter_fresh(ld[:20])
        cards = self.multi_select(soup, [
            "div.job-row","div[class*='job-card']","tr.job","div[class*='listing']",
            "article.job","div[class*='result']","article","li",
        ])
        result = self._parse_cards(cards, "rigzone", "https://www.rigzone.com")
        if not result:
            return self._extract_from_text(soup, "rigzone", "https://www.rigzone.com", CAT)
        return result

    # ── SalesJobs.com — sync HTML (fully accessible) ──────────────────────
    def scrape_salesjobs(self, query: str) -> list[dict]:
        from urllib.parse import urljoin
        cities = ["new-york-ny", "chicago-il", "los-angeles-ca", "remote"]
        result, seen = [], set()
        for city in cities:
            for page in range(2):
                soup = self.fetch_soup(f"https://www.salesjobs.com/sales-jobs/in/{city}?page={page}")
                if not soup:
                    break
                for card in soup.select("#jobSearchResults div.border-bottom.p-2.my-2"):
                    try:
                        title_el = card.select_one("h2 a.job-link")
                        if not title_el:
                            continue
                        title = self._clean_text(title_el.get_text())
                        href = title_el.get("href", "")
                        if not title or not href or href in seen:
                            continue
                        seen.add(href)
                        if query.lower() not in title.lower():
                            continue
                        company = self._clean_text(card.select_one("strong").get_text()) if card.select_one("strong") else ""
                        location = title_el.get("data-jobcitymatch", "") or ""
                        result.append(self._make_job(title, company, location, "",
                                                     urljoin("https://www.salesjobs.com", href),
                                                     "salesjobs", CAT, ""))
                    except Exception:
                        continue
                if len(result) >= 20:
                    return self.filter_fresh(result)
        return self.filter_fresh(result)

    # ── Dice.com — WAF blocked; sync stub + Playwright variant ────────────
    def scrape_dice(self, query: str) -> list[dict]:
        return []

    async def scrape_dice_playwright(self, page, query: str) -> list[dict]:
        from bs4 import BeautifulSoup
        try:
            await page.goto(f"https://www.dice.com/jobs?q={quote(query)}", wait_until="domcontentloaded", timeout=45000)
            await page.wait_for_timeout(5000)
            soup = BeautifulSoup(await page.content(), "html.parser")
            cards = self.multi_select(soup, [
                "a[href*='job-detail']", "[class*='card']", "[data-testid*='job']",
                "div[class*='job-card']", "article", "li",
            ])
            return self._parse_cards(cards, "dice", "https://www.dice.com")
        except Exception as e:
            print(f"[dice] playwright error: {e}")
        return []

    # ── Monster.com — WAF blocked; sync stub + Playwright variant ────────
    def scrape_monster(self, query: str) -> list[dict]:
        return []

    async def scrape_monster_playwright(self, page, query: str) -> list[dict]:
        from bs4 import BeautifulSoup
        try:
            await page.goto(f"https://www.monster.com/jobs/search/?q={quote(query)}", wait_until="domcontentloaded", timeout=45000)
            await page.wait_for_timeout(5000)
            soup = BeautifulSoup(await page.content(), "html.parser")
            cards = self.multi_select(soup, [
                "div[class*='job-card']", "article[class*='job']", "[data-testid*='svx-job']",
                "li[class*='result']", "div[class*='listing']", "article", "li",
            ])
            return self._parse_cards(cards, "monster", "https://www.monster.com")
        except Exception as e:
            print(f"[monster] playwright error: {e}")
        return []

    # ── Naukri.com — Next.js SPA; needs nkparam header for JSON API ──────
    def scrape_naukri(self, query: str) -> list[dict]:
        return []

    # ── Shared multi-selector card parser ─────────────────────────────────
    def _parse_cards(self, cards: list, source: str, base: str, limit: int = 25) -> list[dict]:
        jobs, seen = [], set()
        for card in cards[:limit]:
            try:
                title    = self.first_text(card, _TITLE_SELS)
                href     = self.first_href(card, ["h2 a","h3 a","a.job-title","[class*='title'] a","a"], base)
                if not title or not href or href in seen: continue
                seen.add(href)
                company  = self.first_text(card, _COMPANY_SELS)
                location = self.first_text(card, _LOCATION_SELS)
                posted   = self.first_text(card, _DATE_SELS)
                desc     = self.first_text(card, _DESC_SELS)
                jobs.append(self._make_job(title, company, location, desc, href, source, CAT, posted))
            except Exception:
                continue
        return self.filter_fresh(jobs)
