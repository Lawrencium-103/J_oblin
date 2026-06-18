"""
Web3 job scraper — Solana ecosystem, crypto, and blockchain job boards.
Strategy (in priority order per board):
  1. Inline JSON (__NEXT_DATA__, etc.) — full structured data
  2. JSON-LD (schema.org/JobPosting)
  3. Heuristic text extraction (robust against layout changes)
  4. Multi-selector CSS card parsing (last resort — most fragile)
"""
import re
from urllib.parse import quote
from .base import BaseScraper

CAT = "web3"

_TITLE_SELS  = ["h2 a","h3 a","h4 a","a[class*='title']","a[class*='job-title']",
                "[class*='title'] a","a[class*='position']","strong a","a"]
_COMPANY_SELS = ["[class*='company'] a","[class*='company']","[class*='employer']",
                 "[class*='org']","span.custom_fields_company_name_display_search_results",
                 "[class*='recruiter']","[class*='name']"]
_LOCATION_SELS = ["[class*='location']","[class*='place']","[class*='city']",
                  "[class*='country']","span[class*='loc']","[class*='region']"]
_DATE_SELS = ["time","[class*='date']","[class*='posted']","[class*='age']","span.date"]
_DESC_SELS = ["[class*='desc']","[class*='excerpt']","[class*='snippet']",
              "[class*='summary']","p"]


class Web3JobScraper(BaseScraper):

    # ── Solana Ecosystem Board (Getro/Next.js platform) ───────────────────
    def scrape_jobsolana(self, query: str) -> list[dict]:
        url = "https://jobs.solana.com/jobs"
        soup = self.fetch_soup(url)
        if not soup:
            return []
        import json
        next_data = soup.find("script", id="__NEXT_DATA__")
        if next_data:
            try:
                raw = next_data.string or ""
                data = json.loads(raw)
                jobs_list = (
                    data.get("props", {}).get("pageProps", {})
                    .get("initialState", {}).get("jobs", {}).get("found", [])
                ) or (
                    data.get("props", {}).get("pageProps", {})
                    .get("jobs", [])
                )
                if jobs_list:
                    jobs = []
                    for item in jobs_list[:50]:
                        title = item.get("title", "")
                        if not title:
                            continue
                        url_val = item.get("url", "") or f"https://jobs.solana.com/jobs/{item.get('slug','')}"
                        company = item.get("organization", {}).get("name", "")
                        locations = item.get("locations", [])
                        location = ", ".join(locations) if locations else "Remote"
                        created = item.get("createdAt", 0)
                        posted = ""
                        if created:
                            from datetime import datetime
                            posted = datetime.utcfromtimestamp(created).strftime("%Y-%m-%d")
                        jobs.append(self._make_job(title, company, location, "",
                                                        url_val, "jobsolana", CAT, posted))
                    return self._filter_by_query(self.filter_fresh(jobs), query)
            except Exception as e:
                print(f"[jobsolana] __NEXT_DATA__ parse: {e}")
        ld = self.fetch_json_ld(soup)
        if ld:
            for j in ld: j.update({"source": "jobsolana", "category": CAT})
            return self._filter_by_query(ld[:25], query)
        return self._filter_by_query(
            self._extract_from_text(soup, "jobsolana",
                                    "https://jobs.solana.com", CAT),
            query)

    # ── CryptocurrencyJobs (Hugo SSR site) ────────────────────────────────
    def scrape_cryptocurrencyjobs(self, query: str) -> list[dict]:
        # Try main listing; board doesn't support search params
        for url in [
            "https://cryptocurrencyjobs.co/remote/",
            "https://cryptocurrencyjobs.co/",
        ]:
            soup = self.fetch_soup(url)
            if not soup:
                continue
            ld = self.fetch_json_ld(soup)
            if ld:
                for j in ld: j.update({"source": "cryptocurrencyjobs", "category": CAT})
                return self._filter_by_query(ld[:25], query)
            result = self._filter_by_query(
                self._extract_from_text(soup, "cryptocurrencyjobs",
                                        "https://cryptocurrencyjobs.co", CAT),
                query)
            if result:
                return result
            cards = soup.select("li.grid, li[class*='job'], article, div[class*='card'], div[class*='listing']")
            if cards:
                jobs, seen = [], set()
                for card in cards[:50]:
                    try:
                        for img in card.find_all("img"):
                            img.decompose()
                        h2 = card.find("h2")
                        if not h2:
                            continue
                        a = h2.find("a") if h2 else None
                        title = (a or h2).get_text(strip=True)
                        href = ""
                        if a:
                            href = a.get("href", "")
                            if href and not href.startswith("http"):
                                href = "https://cryptocurrencyjobs.co" + href
                        if not title or not href or href in seen:
                            continue
                        company = ""
                        co_link = card.find("a", href=lambda x: x and x.startswith("/startups/"))
                        if co_link:
                            company = co_link.get_text(strip=True)
                        if not company:
                            all_texts = card.get_text("|", strip=True).split("|")
                            for idx, t in enumerate(all_texts):
                                if t == title and idx + 1 < len(all_texts):
                                    nxt = all_texts[idx + 1].strip()
                                    if nxt and nxt not in ("Remote",):
                                        company = nxt
                                    break
                        seen.add(href)
                        date_match = re.search(r'(\d+[dhm])\s*(?:Featured)?', card.get_text())
                        posted = date_match.group(1) if date_match else ""
                        jobs.append(self._make_job(title, company, "Remote", "",
                                                    href, "cryptocurrencyjobs", CAT, posted))
                    except Exception:
                        continue
                if jobs:
                    return self._filter_by_query(self.filter_fresh(jobs), query)
        return []

    # ── Web3.Career ───────────────────────────────────────────────────────
    def scrape_web3career(self, query: str) -> list[dict]:
        soup = self.fetch_soup("https://web3.career/remote-jobs")
        if not soup:
            return []
        ld = self.fetch_json_ld(soup)
        if ld:
            for j in ld: j.update({"source": "web3career", "category": CAT})
            return self._filter_by_query(ld[:25], query)
        result = self._filter_by_query(
            self._extract_from_text(soup, "web3career",
                                    "https://web3.career", CAT),
            query)
        if result:
            return result
        cards = self.multi_select(soup, [
            "tr[class*='job']","tr","div[class*='job-row']","div[class*='job-card']",
            "div[class*='table'] > div","div[class*='listing']","article","li",
        ])
        jobs, seen = [], set()
        for card in cards[:40]:
            try:
                title = self.first_text(card, [
                    "td:first-child a","td:nth-child(2) a","td:nth-child(1) a",
                    "h2 a","h3 a","strong a","a",
                ])
                href = self.first_href(card, [
                    "td:first-child a","a[href*='/job/']","a[href*='/position/']","a",
                ], "https://web3.career")
                if not title or not href or href in seen:
                    continue
                seen.add(href)
                company = self.first_text(card, [
                    "td:nth-child(2)","[class*='company']","[class*='org']",
                ])
                location = self.first_text(card, _LOCATION_SELS, "Remote")
                posted = self.first_text(card, _DATE_SELS)
                salary = self.first_text(card, ["[class*='salary']","td:nth-child(4)"])
                desc = f"Salary: {salary}" if salary else ""
                jobs.append(self._make_job(title, company, location, desc, href,
                                           "web3career", CAT, posted))
            except Exception:
                continue
        return self._filter_by_query(self.filter_fresh(jobs), query)

    # ── CryptoJobsList ────────────────────────────────────────────────────
    def scrape_cryptojobslist(self, query: str) -> list[dict]:
        soup = self.fetch_soup("https://cryptojobslist.com/")
        if not soup:
            return []
        ld = self.fetch_json_ld(soup)
        if ld:
            for j in ld: j.update({"source": "cryptojobslist", "category": CAT})
            return self._filter_by_query(ld[:25], query)
        result = self._filter_by_query(
            self._extract_from_text(soup, "cryptojobslist",
                                    "https://cryptojobslist.com", CAT),
            query)
        if result:
            return result
        cards = self.multi_select(soup, [
            "div[class*='job-card']","div[class*='listing']","div[class*='job']",
            "article","li","a[class*='job']","div[class*='card']",
        ])
        jobs, seen = [], set()
        for card in cards[:40]:
            try:
                title = self.first_text(card, _TITLE_SELS)
                href = self.first_href(card, [
                    "a[href*='/']","h2 a","h3 a",
                ], "https://cryptojobslist.com")
                if not title or not href or href in seen:
                    continue
                seen.add(href)
                company = self.first_text(card, _COMPANY_SELS)
                location = self.first_text(card, _LOCATION_SELS, "Remote")
                posted = self.first_text(card, _DATE_SELS)
                desc = self.first_text(card, _DESC_SELS)
                jobs.append(self._make_job(title, company, location, desc, href,
                                           "cryptojobslist", CAT, posted))
            except Exception:
                continue
        return self._filter_by_query(self.filter_fresh(jobs), query)

    # ── Shared: filter results by query keywords ───────────────────────────
    def _filter_by_query(self, jobs: list[dict], query: str) -> list[dict]:
        if not query or not jobs:
            return jobs
        q_words = set(query.lower().split())
        filtered = []
        for j in jobs:
            text = (j.get("title", "") + " " + j.get("company", "") + " " + j.get("description", "")).lower()
            if q_words & set(text.split()):
                filtered.append(j)
        return filtered[:25]
