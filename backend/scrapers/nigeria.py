"""
Nigerian job boards: MyJobMag, Jobberman, Jobgurus, HotNigerianJobs, NGCareers, Jobzilla, SmartyAcad.
Future-proof: JSON-LD first → multi-selector CSS → heuristic text extraction.
"""
from urllib.parse import quote
from .base import BaseScraper

CAT = "nigeria"

_TITLE_SELS    = ["h2 a","h3 a","h4 a","a.job-title","[class*='title'] a",
                  "a[class*='title']","a[class*='job']",".job-name a","a[rel='bookmark']",
                  "h2.entry-title a","h3.entry-title a",".job_title a",".job-title a",
                  "h2","h3","a"]
_COMPANY_SELS  = ["[class*='company'] a","[class*='company']","[class*='employer']",
                  "[class*='recruiter']","[class*='org']","span[class*='name']",
                  "[class*='logo'] a img","[class*='logo'] img",
                  "[class*='organization']","[class*='employer-name']",
                  "[class*='recruiter-name']",".job-org",".job-company"]
_LOCATION_SELS = ["[class*='location']","[class*='place']","[class*='city']",
                  "[class*='state']","span[class*='loc']","[class*='area']",
                  "[class*='address']",".job-location","[class*='country']"]
_DATE_SELS     = ["time","[class*='date']","[class*='posted']","[class*='time']",
                  "span.date","#job-date","[class*='ago']","[datetime]",
                  "[class*='published']","[class*='meta'] time"]
_DESC_SELS     = ["[class*='desc']","[class*='excerpt']","[class*='summary']",
                  "[class*='content'] p","p","[class*='text']"]


class NigerianJobScraper(BaseScraper):

    _smartyacad_cache = None

    # ── SmartyAcad / Dixcover Hub (WordPress REST API) ─────────────────────
    def scrape_smartyacad(self, query: str = "") -> list[dict]:
        if NigerianJobScraper._smartyacad_cache is None:
            url  = "https://jobs.smartyacad.com/wp-json/wp/v2/posts?categories=10&per_page=100&_fields=id,title,content,date,link"
            data = self.fetch_json(url)
            if not data:
                return []
            from bs4 import BeautifulSoup
            parsed = []
            for post in data:
                title        = (post.get("title",{}) or {}).get("rendered","")
                content_html = (post.get("content",{}) or {}).get("rendered","")
                soup         = BeautifulSoup(content_html, "html.parser")
                clean_desc   = soup.get_text(" ", strip=True)[:800]
                link         = post.get("link","")
                date_str     = post.get("date","")[:10]
                company      = ""
                for sep in [" at "," – "," — "," - ","–","—"]:
                    if sep in title:
                        parts = title.rsplit(sep, 1)
                        company = parts[-1].strip()
                        break
                parsed.append({
                    "title": title, "company": company,
                    "description": clean_desc, "url": link,
                    "source": "smartyacad", "category": CAT,
                    "posted_date": date_str,
                })
            NigerianJobScraper._smartyacad_cache = parsed
        return list(NigerianJobScraper._smartyacad_cache)

    # ── MyJobMag ────────────────────────────────────────────────────────────
    def scrape_myjobmag(self, query: str) -> list[dict]:
        url  = f"https://www.myjobmag.com/search?q={quote(query)}"
        soup = self.fetch_soup(url)
        if not soup:
            return []
        ld = self.fetch_json_ld(soup)
        if ld:
            for j in ld: j.update({"source": "myjobmag", "category": CAT})
            return self.filter_fresh(ld[:20])
        # Try common card selectors first, then site-specific
        cards = self.multi_select(soup, [
            "li.job-list-li",
            "article.job-item","div.job-item","li.job-item",
            "div[class*='job-list'] > div","ul.jobs-list > li",
            "div[class*='joblist'] article",
            "div.search-result","div.job-listing","div.job-post",
            "div.listing-item","div.post-item","li.listing-item",
            "tr","div.row","div[class*='list'] > div","article",
        ])
        result = self._parse_cards(cards, "myjobmag", "https://www.myjobmag.com", 20)
        if not result:
            return self._extract_from_text(soup, "myjobmag", "https://www.myjobmag.com", CAT)
        return result

    # ── Jobberman ───────────────────────────────────────────────────────────
    def scrape_jobberman(self, query: str) -> list[dict]:
        url  = f"https://www.jobberman.com/jobs?q={quote(query)}"
        soup = self.fetch_soup(url)
        if not soup:
            return []
        ld = self.fetch_json_ld(soup)
        if ld:
            for j in ld: j.update({"source": "jobberman", "category": CAT})
            return self.filter_fresh(ld[:20])
        cards = self.multi_select(soup, [
            "article[class*='job']","div[class*='job-listing']",
            "div[class*='listingCard']","li[class*='job']",
            "div[data-job-id]","div[class*='card']","article",
        ])
        result = self._parse_cards(cards, "jobberman", "https://www.jobberman.com", 20)
        if not result:
            return self._extract_from_text(soup, "jobberman", "https://www.jobberman.com", CAT)
        return result

    # ── Jobgurus Nigeria ────────────────────────────────────────────────────
    def scrape_jobgurus(self, query: str) -> list[dict]:
        url  = f"https://www.jobgurus.com.ng/?s={quote(query)}"
        soup = self.fetch_soup(url)
        if not soup:
            return []
        ld = self.fetch_json_ld(soup)
        if ld:
            for j in ld: j.update({"source": "jobgurus", "category": CAT})
            return self.filter_fresh(ld[:15])
        cards = self.multi_select(soup, [
            "div.panel.panel-default.job-post-panel",
            "article.job_listing","article[class*='job']",
            "li.job_listing","div.job_listing","article","div[class*='listing']",
        ])
        result = self._parse_cards(cards, "jobgurus", "https://www.jobgurus.com.ng", 15)
        if not result:
            return self._extract_from_text(soup, "jobgurus", "https://www.jobgurus.com.ng", CAT)
        return result

    # ── HotNigerianJobs ─────────────────────────────────────────────────────
    def scrape_hotnigerianjobs(self, query: str) -> list[dict]:
        url  = f"https://www.hotnigerianjobs.com/?s={quote(query)}"
        soup = self.fetch_soup(url)
        if not soup:
            return []
        ld = self.fetch_json_ld(soup)
        if ld:
            for j in ld: j.update({"source": "hotnigerianjobs", "category": CAT})
            return self.filter_fresh(ld[:15])
        cards = self.multi_select(soup, [
            "div.job-post","article.post","div.post",
            "li.job","article[class*='post']","div[class*='job']",
            "div.search-result","div.job-listing","li.post",
            "div[class*='list'] > div","tr","div.row","article",
        ])
        result = self._parse_cards(cards, "hotnigerianjobs", "https://www.hotnigerianjobs.com", 15)
        if not result:
            return self._extract_from_text(soup, "hotnigerianjobs", "https://www.hotnigerianjobs.com", CAT)
        return result

    # ── NGCareers ───────────────────────────────────────────────────────────
    def scrape_ngcareers(self, query: str) -> list[dict]:
        url  = f"https://ngcareers.com/jobs?q={quote(query)}"
        soup = self.fetch_soup(url)
        if not soup:
            return []
        ld = self.fetch_json_ld(soup)
        if ld:
            for j in ld: j.update({"source": "ngcareers", "category": CAT})
            return self.filter_fresh(ld[:15])
        cards = self.multi_select(soup, [
            "div.job-card","article.job","li.job","div[class*='vacancy']",
            "div.job-listing","div.job-post","div.search-result",
            "li.job-listing","div[class*='listing']","div.post",
            "li.post","tr","div.row","div[class*='list'] > div","article",
        ])
        result = self._parse_cards(cards, "ngcareers", "https://ngcareers.com", 15)
        if not result:
            return self._extract_from_text(soup, "ngcareers", "https://ngcareers.com", CAT)
        return result

    # ── Jobzilla Nigeria ────────────────────────────────────────────────────
    def scrape_jobzilla(self, query: str) -> list[dict]:
        url  = f"https://www.jobzilla.ng/jobs?q={quote(query)}"
        soup = self.fetch_soup(url)
        if not soup:
            return []
        ld = self.fetch_json_ld(soup)
        if ld:
            for j in ld: j.update({"source": "jobzilla", "category": CAT})
            print(f"[jobzilla] {len(ld)} jobs for '{query}'")
            return self.filter_fresh(ld[:20])
        cards = self.multi_select(soup, [
            "div.card.border-0.shadow",
            "div.job-item","div.job-listing","div.search-result","div.job-row",
            "div.job-card","article.job","li.job-item","div[class*='job']","article",
        ])
        result = self._parse_cards(cards, "jobzilla", "https://www.jobzilla.ng", 20)
        if not result:
            return self._extract_from_text(soup, "jobzilla", "https://www.jobzilla.ng", CAT)
        return result

    # ── Shared card parser ──────────────────────────────────────────────────
    def _parse_cards(self, cards: list, source: str, base: str, limit: int) -> list[dict]:
        jobs, seen = [], set()
        for card in cards[:limit]:
            try:
                title    = self.first_text(card, _TITLE_SELS)
                href     = self.first_href(card, ["h2 a","h3 a","h4 a","a[class*='title']","a"], base)
                if not title or not href or href in seen: continue
                seen.add(href)
                company  = self.first_text(card, _COMPANY_SELS)
                if not company:
                    logo = card.select_one("[class*='logo'] img")
                    if logo and logo.get("alt"):
                        company = logo["alt"]
                location = self.first_text(card, _LOCATION_SELS, "Nigeria")
                posted   = self.first_text(card, _DATE_SELS)
                desc     = self.first_text(card, _DESC_SELS)
                jobs.append(self._make_job(title, company, location, desc, href, source, CAT, posted))
            except Exception:
                continue
        return self.filter_fresh(jobs)
