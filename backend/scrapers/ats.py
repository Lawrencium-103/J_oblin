"""
Corporate ATS job scrapers — Ashby, Greenhouse.
These platforms power career pages for hundreds of companies.
Strategy: Public JSON API (most stable, never changes with UI redesigns).
Lever's public API was deprecated (all endpoints return 404 as of 2026).
"""
import re
from .base import BaseScraper

CAT = "ats"

# Companies with public Ashby posting API — verified alive June 2026
ASHBY_COMPANIES = [
    "openai", "linear", "ramp", "elevenlabs",
    "supabase", "perplexity", "notion", "replit", "cursor",
]

# Companies with public Greenhouse board API — verified alive June 2026
GREENHOUSE_COMPANIES = [
    "stripe", "gitlab", "datadog", "instacart",
    "pinterest", "reddit", "coinbase", "discord",
    "mongodb", "twilio", "robinhood", "brex", "chime",
    "betterment", "amplitude", "pagerduty", "algolia",
    "intercom", "honeycomb",
]


def _strip_html(html: str) -> str:
    """Strip HTML tags, return clean text up to 600 chars."""
    text = re.sub(r"<[^>]+>", " ", html or "")
    text = re.sub(r"\s+", " ", text).strip()
    return text[:600]


class ATSJobScraper(BaseScraper):

    # ── Ashby Public API ───────────────────────────────────────────────────
    def scrape_ashby(self, query: str) -> list[dict]:
        q_words = set(query.lower().split()) if query else set()
        all_jobs = []
        for company in ASHBY_COMPANIES:
            data = self.fetch_json(f"https://api.ashbyhq.com/posting-api/job-board/{company}")
            if not isinstance(data, dict) or not data.get("jobs"):
                continue
            for item in data["jobs"]:
                try:
                    title = item.get("title", "")
                    if not title:
                        continue
                    if q_words and not self._matches_query(title, item.get("descriptionHtml", ""), q_words):
                        continue
                    posted = (item.get("publishedAt", "") or "")[:10]
                    all_jobs.append(self._make_job(
                        title,
                        item.get("department", "") or company.title(),
                        item.get("location", "Remote"),
                        _strip_html(item.get("descriptionHtml", "")),
                        f"https://jobs.ashbyhq.com/{company}/{item.get('id', '')}",
                        "ashby", CAT, posted,
                    ))
                except Exception:
                    continue
        print(f"[ashby] {len(all_jobs)} jobs matching '{query}'")
        return self.filter_fresh(all_jobs[:50])

    # ── Greenhouse Public API ──────────────────────────────────────────────
    def scrape_greenhouse(self, query: str) -> list[dict]:
        q_words = set(query.lower().split()) if query else set()
        all_jobs = []
        for company in GREENHOUSE_COMPANIES:
            data = self.fetch_json(
                f"https://boards-api.greenhouse.io/v1/boards/{company}/jobs?content=true"
            )
            if not isinstance(data, dict) or not data.get("jobs"):
                continue
            for item in data["jobs"]:
                try:
                    title = item.get("title", "")
                    if not title:
                        continue
                    desc = _strip_html(item.get("content", ""))
                    if q_words and not self._matches_query(title, desc, q_words):
                        continue
                    offices = item.get("offices", [])
                    location = ", ".join(
                        o.get("location", "") or o.get("name", "")
                        for o in offices if isinstance(o, dict)
                    ) or "Remote"
                    depts = item.get("departments", [])
                    company_name = depts[0].get("name", "") if depts else company.title()
                    all_jobs.append(self._make_job(
                        title, company_name, location, desc,
                        f"https://boards.greenhouse.io/{company}/jobs/{item.get('id', '')}",
                        "greenhouse", CAT, (item.get("updated_at", "") or "")[:10],
                    ))
                except Exception:
                    continue
        print(f"[greenhouse] {len(all_jobs)} jobs matching '{query}'")
        return self.filter_fresh(all_jobs[:50])

    # ── Query matching helper ─────────────────────────────────────────────
    def _matches_query(self, title: str, description: str, q_words: set) -> bool:
        text = f"{title.lower()} {description.lower()}"
        return bool(q_words & set(text.split()))
