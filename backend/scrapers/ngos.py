"""
NGO / Development / Humanitarian job scrapers.
Future-proof: RSS/JSON API first → JSON-LD → multi-selector CSS → heuristic text.
"""
from urllib.parse import quote
from .base import BaseScraper

CAT = "ngo"

_TITLE_SELS    = ["h2 a","h3 a","h4 a","a.job-title","[class*='title'] a",
                  "a[class*='title']","a[class*='job']",".job-name a","a"]
_COMPANY_SELS  = ["[class*='company'] a","[class*='company']","[class*='employer']",
                  "[class*='org']","[class*='recruiter']","span[class*='name']"]
_LOCATION_SELS = ["[class*='location']","[class*='country']","[class*='place']",
                  "[class*='city']","span[class*='loc']"]
_DATE_SELS     = ["time","[class*='date']","[class*='posted']","[class*='deadline']","span.date"]
_DESC_SELS     = ["[class*='desc']","[class*='excerpt']","[class*='summary']","p"]


class NGOJobScraper(BaseScraper):

    # ── MyNGOJob ────────────────────────────────────────────────────────────
    def scrape_myngojob(self, query: str) -> list[dict]:
        url  = f"https://www.myngojob.com/search?q={quote(query)}"
        soup = self.fetch_soup(url)
        if not soup:
            return []
        ld = self.fetch_json_ld(soup)
        if ld:
            for j in ld: j.update({"source": "myngojob", "category": CAT})
            return self.filter_fresh(ld[:20])
        cards = self.multi_select(soup, [
            "article.job-item","div.job-item","li.job-item",
            "div[class*='job-list'] > div","article","li[class*='job']",
        ])
        result = self._parse_cards(cards, "myngojob", "https://www.myngojob.com")
        if not result:
            return self._extract_from_text(soup, "myngojob", "https://www.myngojob.com", CAT)
        return result

    # ── ReliefWeb — RSS feed (extremely stable, UN-backed) ──────────────────
    def scrape_reliefweb(self, query: str) -> list[dict]:
        # Try multiple RSS URL patterns in case they update their URL structure
        for rss_url in [
            f"https://reliefweb.int/jobs/rss.xml?search={quote(query)}",
            f"https://reliefweb.int/jobs/rss?q={quote(query)}",
            f"https://reliefweb.int/rss/jobs?q={quote(query)}",
        ]:
            items = self.fetch_rss(rss_url)
            if items:
                jobs = [
                    self._make_job(it["title"], "ReliefWeb", "Global",
                                   it["description"], it["url"], "reliefweb", CAT, it["posted_date"])
                    for it in items[:20]
                ]
                return self.filter_fresh(jobs)
        # HTML fallback
        soup = self.fetch_soup(f"https://reliefweb.int/jobs?search={quote(query)}")
        if not soup:
            return []
        ld = self.fetch_json_ld(soup)
        if ld:
            for j in ld: j.update({"source": "reliefweb", "category": CAT})
            return self.filter_fresh(ld[:20])
        cards = self.multi_select(soup, [
            "article[class*='rw-entity']","article.job","div.job-card",
            "li.job-item","article","div[class*='card']",
        ])
        result = self._parse_cards(cards, "reliefweb", "https://reliefweb.int")
        if not result:
            return self._extract_from_text(soup, "reliefweb", "https://reliefweb.int", CAT)
        return result

    # ── Devex ───────────────────────────────────────────────────────────────
    def scrape_devex(self, query: str) -> list[dict]:
        url  = f"https://www.devex.com/jobs/search?keywords={quote(query)}"
        soup = self.fetch_soup(url)
        if not soup:
            return []
        ld = self.fetch_json_ld(soup)
        if ld:
            for j in ld: j.update({"source": "devex", "category": CAT})
            return self.filter_fresh(ld[:20])
        cards = self.multi_select(soup, [
            "li[class*='job']","div[class*='job-list-item']",
            "article[class*='job']","div.js-job-item","li","article",
        ])
        result = self._parse_cards(cards, "devex", "https://www.devex.com")
        if not result:
            return self._extract_from_text(soup, "devex", "https://www.devex.com", CAT)
        return result

    # ── ImpactPool ──────────────────────────────────────────────────────────
    def scrape_impactpool(self, query: str) -> list[dict]:
        url  = f"https://www.impactpool.org/search?q={quote(query)}"
        soup = self.fetch_soup(url)
        if not soup:
            return []
        ld = self.fetch_json_ld(soup)
        if ld:
            for j in ld: j.update({"source": "impactpool", "category": CAT})
            return self.filter_fresh(ld[:20])
        cards = self.multi_select(soup, [
            "div.job-card","div[class*='vacancy']","li.job",
            "div[class*='job-item']","article","li",
        ])
        result = self._parse_cards(cards, "impactpool", "https://www.impactpool.org")
        if not result:
            return self._extract_from_text(soup, "impactpool", "https://www.impactpool.org", CAT)
        return result

    # ── Idealist ────────────────────────────────────────────────────────────
    def scrape_idealist(self, query: str) -> list[dict]:
        url  = f"https://www.idealist.org/en/jobs?q={quote(query)}"
        soup = self.fetch_soup(url)
        if not soup:
            return []
        ld = self.fetch_json_ld(soup)
        if ld:
            for j in ld: j.update({"source": "idealist", "category": CAT})
            return self.filter_fresh(ld[:20])
        cards = self.multi_select(soup, [
            "[data-testid='listing-card']","article[class*='listing']",
            "li[class*='job']","div[class*='card']","article","li",
        ])
        result = self._parse_cards(cards, "idealist", "https://www.idealist.org")
        if not result:
            return self._extract_from_text(soup, "idealist", "https://www.idealist.org", CAT)
        return result

    # ── UNICEF ──────────────────────────────────────────────────────────────
    def scrape_unicef(self, query: str) -> list[dict]:
        # Try multiple URL patterns — UN sites restructure their career portals
        for url in [
            f"https://jobs.unicef.org/en-us/search?searchbykeyword={quote(query)}",
            f"https://careers.unicef.org/search?q={quote(query)}",
        ]:
            soup = self.fetch_soup(url)
            if not soup:
                continue
            ld = self.fetch_json_ld(soup)
            if ld:
                for j in ld: j.update({"source": "unicef", "category": CAT})
                return self.filter_fresh(ld[:20])
            cards = self.multi_select(soup, [
                "div.search-result-item","div.opportunity-card","div.vacancy-card",
                "tr.job-row","div.job-item","li.job","article",
                "div[class*='job']","div[class*='vacancy']","div[class*='result']",
            ])
            TITLE = ["a.job-title","[class*='title'] a","td a","a[class*='title']","h2 a","h3 a","a"]
            jobs, seen = [], set()
            for card in cards[:20]:
                title    = self.first_text(card, TITLE)
                href     = self.first_href(card, TITLE, url.split("/en-us")[0] or url.split("/search")[0])
                if not title or href in seen: continue
                seen.add(href)
                location = self.first_text(card, _LOCATION_SELS)
                jobs.append(self._make_job(title, "UNICEF", location, "", href, "unicef", CAT))
            if jobs:
                return self.filter_fresh(jobs)
            result = self._extract_from_text(soup, "unicef", url.split("/en-us")[0], CAT)
            if result:
                return result
        return []

    # ── WHO ─────────────────────────────────────────────────────────────────
    def scrape_who(self, query: str) -> list[dict]:
        for url in [
            f"https://careers.who.int/search?q={quote(query)}&location=all",
            f"https://careers.who.int/careersection/ex/jobsearch.ftl?lang=en&keyword={quote(query)}",
        ]:
            soup = self.fetch_soup(url)
            if not soup:
                continue
            ld = self.fetch_json_ld(soup)
            if ld:
                for j in ld: j.update({"source": "who", "category": CAT})
                return self.filter_fresh(ld[:20])
            cards = self.multi_select(soup, [
                "tr.job-row","div.job-listing","li.job",
                "div[class*='position']","article","tr","div[class*='job']",
            ])
            TITLE = ["a.job-title","[class*='title'] a","a[class*='title']","td a","a"]
            jobs, seen = [], set()
            base = "https://careers.who.int"
            for card in cards[:20]:
                title    = self.first_text(card, TITLE)
                href     = self.first_href(card, TITLE, base)
                if not title or href in seen: continue
                seen.add(href)
                location = self.first_text(card, _LOCATION_SELS)
                jobs.append(self._make_job(title, "WHO", location, "", href, "who", CAT))
            if jobs:
                return self.filter_fresh(jobs)
            result = self._extract_from_text(soup, "who", base, CAT)
            if result:
                return result
        return []

    # ── DevNetJobs ──────────────────────────────────────────────────────────
    def scrape_devnetjobs(self, query: str) -> list[dict]:
        url  = f"https://www.devnetjobs.org/jobs?search={quote(query)}"
        soup = self.fetch_soup(url)
        if not soup:
            return []
        cards = self.multi_select(soup, [
            "div.job-item","div.listing","article","li.job",
            "tr[class*='job']","div[class*='vacancy']",
        ])
        result = self._parse_cards(cards, "devnetjobs", "https://www.devnetjobs.org")
        if not result:
            return self._extract_from_text(soup, "devnetjobs", "https://www.devnetjobs.org", CAT)
        return result

    # ── IRC (Cornerstone ATS) ───────────────────────────────────────────────
    def scrape_irc(self, query: str) -> list[dict]:
        for url in [
            f"https://rescue.csod.com/ux/ats/careersite/1/home?q={quote(query)}",
            f"https://careers.rescue.org/en/search-jobs?keywords={quote(query)}",
        ]:
            soup = self.fetch_soup(url)
            if not soup:
                continue
            ld = self.fetch_json_ld(soup)
            if ld:
                for j in ld: j.update({"source": "irc", "category": CAT})
                return self.filter_fresh(ld[:15])
            cards = self.multi_select(soup, [
                "div[class*='job-listing']","div[class*='csod-job']",
                "div.panel","li[class*='job']","div[class*='card']","article",
            ])
            result = self._parse_cards(cards, "irc", url.split("/ux")[0] or url.split("/en")[0], limit=15)
            if result:
                return result
        return []

    # ── Shared card parser ──────────────────────────────────────────────────
    def _parse_cards(self, cards: list, source: str, base: str, limit: int = 20) -> list[dict]:
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
