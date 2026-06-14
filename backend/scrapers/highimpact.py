"""
High-impact nonprofit / AI for good job scrapers.
Boards: Idealist, 80000Hours (Algolia API), Anthropic Careers.
Future-proof: Algolia API → JSON-LD → multi-selector → heuristic text.
"""
import re as _re
from datetime import datetime
from urllib.parse import quote
from .base import BaseScraper

CAT = "highimpact"

# 80000hours Algolia public credentials — if these rotate, fall through to HTML
ALGOLIA_ID    = "W6KM1UDIB3"
ALGOLIA_KEY   = "d1d7f2c8696e7b36837d5ed337c4a319"
ALGOLIA_INDEX = "jobs_prod"

_TITLE_SELS   = ["h2 a","h3 a","h4 a","a.job-title","[class*='title'] a",
                 "a[class*='title']","a[class*='job']",".job-name a","a"]
_COMPANY_SELS = ["[class*='company'] a","[class*='company']","[class*='employer']",
                 "[class*='org']","[class*='recruiter']","span[class*='name']"]
_LOC_SELS     = ["[class*='location']","[class*='country']","[class*='place']",
                 "[class*='city']","[class*='remote']","span[class*='loc']"]
_DATE_SELS    = ["time","[class*='date']","[class*='posted']","[class*='deadline']","span.date"]
_DESC_SELS    = ["[class*='desc']","[class*='excerpt']","[class*='summary']","p"]


class HighImpactScraper(BaseScraper):

    # ── Idealist (nonprofit tech/AI roles) ──────────────────────────────────
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

    # ── 80000Hours — Algolia API (vastly more reliable than HTML) ───────────
    def scrape_eightythousandhours(self, query: str) -> list[dict]:
        # Method 1: Algolia API
        try:
            url  = f"https://{ALGOLIA_ID}.algolia.net/1/indexes/{ALGOLIA_INDEX}/query"
            data = self.post_json(url, {"params": f"query={quote(query)}&hitsPerPage=25&page=0"}, headers={
                "X-Algolia-API-Key": ALGOLIA_KEY,
                "X-Algolia-Application-Id": ALGOLIA_ID,
            })
            if data and data.get("hits"):
                jobs, seen = [], set()
                for h in data["hits"]:
                    title   = h.get("title","")
                    ext_url = h.get("url_external","")
                    if not title or not ext_url or ext_url in seen:
                        continue
                    seen.add(ext_url)
                    company  = h.get("company_name","") or ""
                    location = ", ".join(h.get("card_locations",[]) or h.get("tags_city",[]))
                    desc     = _re.sub(r"<[^>]+>","", (h.get("description_short","") or ""))[:500]
                    posted_ts = h.get("posted_at")
                    posted   = ""
                    if posted_ts:
                        try:
                            posted = datetime.fromtimestamp(posted_ts).strftime("%Y-%m-%d")
                        except Exception:
                            posted = h.get("posted_at_relative","")
                    salary = h.get("salary","")
                    if salary:
                        desc = f"{salary} | {desc}" if desc else salary
                    tags = h.get("tags_area",[]) + h.get("tags_skill",[])
                    if tags:
                        desc = f"[{', '.join(tags[:4])}] {desc}" if desc else ", ".join(tags[:4])
                    jobs.append(self._make_job(title, company, location, desc, ext_url, "80000hours", CAT, posted))
                return self.filter_fresh(jobs)
        except Exception as e:
            print(f"[80000hours] Algolia API error: {e}")
        # Method 2: HTML fallback
        soup = self.fetch_soup(f"https://80000hours.org/job-board/?search={quote(query)}")
        if not soup:
            return []
        ld = self.fetch_json_ld(soup)
        if ld:
            for j in ld: j.update({"source": "80000hours", "category": CAT})
            return self.filter_fresh(ld[:20])
        cards = self.multi_select(soup, [
            "div[class*='job-card']","article[class*='job']",
            "li[class*='job']","div[class*='listing']","article","li",
        ])
        result = self._parse_cards(cards, "80000hours", "https://80000hours.org")
        if not result:
            return self._extract_from_text(soup, "80000hours", "https://80000hours.org", CAT)
        return result

    # ── Anthropic Careers ───────────────────────────────────────────────────
    def scrape_anthropic(self, query: str) -> list[dict]:
        # Try multiple URL patterns — startup career pages move around
        for url in [
            f"https://www.anthropic.com/careers?query={quote(query)}",
            f"https://boards.greenhouse.io/anthropic?q={quote(query)}",
            f"https://www.anthropic.com/careers",
        ]:
            soup = self.fetch_soup(url)
            if not soup:
                continue
            ld = self.fetch_json_ld(soup)
            if ld:
                for j in ld: j.update({"source": "anthropic", "category": CAT})
                return self.filter_fresh(ld[:20])
            cards = self.multi_select(soup, [
                "a[class*='career']","div[class*='position']","li[class*='job']",
                "tr[class*='job']","div[class*='opening']","article","li","tr",
            ])
            result = self._parse_cards(cards, "anthropic", "https://www.anthropic.com", limit=20)
            if result:
                return result
            result = self._extract_from_text(soup, "anthropic", "https://www.anthropic.com", CAT)
            if result:
                return result
        return []

    # ── Shared card parser ─────────────────────────────────────────────────
    def _parse_cards(self, cards: list, source: str, base: str, limit: int = 20) -> list[dict]:
        jobs, seen = [], set()
        for card in cards[:limit]:
            try:
                title    = self.first_text(card, _TITLE_SELS)
                href     = self.first_href(card, ["h2 a","h3 a","a.job-title","[class*='title'] a","a"], base)
                if not title or not href or href in seen: continue
                seen.add(href)
                company  = self.first_text(card, _COMPANY_SELS)
                location = self.first_text(card, _LOC_SELS)
                posted   = self.first_text(card, _DATE_SELS)
                desc     = self.first_text(card, _DESC_SELS)
                jobs.append(self._make_job(title, company, location, desc, href, source, CAT, posted))
            except Exception:
                continue
        return self.filter_fresh(jobs)
