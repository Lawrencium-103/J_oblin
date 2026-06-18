"""
Robust base scraper with:
  - Safe scraping: polite delays per domain, UA rotation, retry on 403/429
  - Circuit breaker: auto-disables sources that fail repeatedly
  - 72-hour freshness filter (relaxed from 48h for better coverage)
  - JSON-LD / RSS / multi-selector / text-heuristic fallback chain
  - Title-from-text heuristic: extracts job data even from unstructured pages
  - Domain health tracker: exponential backoff per failing domain
"""
import re
import time
import json
import random
import hashlib
import requests
from datetime import datetime, timedelta, timezone
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin

_UA_POOL = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:127.0) Gecko/20100101 Firefox/127.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36 Edg/126.0.0.0",
]

# Domain-level rate tracking (shared across all instances)
_DOMAIN_LAST_HIT: dict[str, float] = {}
_MIN_DELAY = 3.0   # seconds min between hits to same domain
_MAX_DELAY = 8.0   # seconds max — looks more human

# Circuit breaker: track consecutive failures per domain
_DOMAIN_FAILURES: dict[str, int] = {}
_DOMAIN_BACKOFF_UNTIL: dict[str, float] = {}
_MAX_FAILURES = 5      # consecutive failures before backing off
_BACKOFF_SECONDS = 300 # 5 minutes backoff

# Simple robots.txt allowlist cache: domain -> set of disallowed path prefixes
_ROBOTS_DISALLOWED: dict[str, list[str]] = {}
_ROBOTS_CHECKED: dict[str, float] = {}  # domain -> timestamp; refetch after 24h
_ROBOTS_TTL = 86400  # 24 hours

# HTTP response cache per URL (in-memory, TTL per domain)
_HTTP_CACHE: dict[str, tuple[float, str]] = {}  # url -> (expires_at, text)
_HTTP_CACHE_TTL = 300  # 5 minutes default

# Freshness window — 72 hours gives better coverage without letting stale jobs in
_FRESHNESS_HOURS = 72


def filter_fresh(jobs: list[dict]) -> list[dict]:
    """Standalone freshness filter. Unknown dates pass through."""
    fresh = [j for j in jobs if is_within_window(j.get("posted_date", ""))]
    stale = len(jobs) - len(fresh)
    if stale:
        print(f"  [freshness] dropped {stale} stale jobs (>{_FRESHNESS_HOURS}h)")
    return fresh


def is_within_window(date_text: str) -> bool:
    """True = keep job, False = discard (too old). Unknown dates always kept."""
    if not date_text:
        return True
    dt = date_text.lower().strip()
    # Explicit fresh indicators
    if any(w in dt for w in ["today", "just now", "moments", "1 hour", "2 hour",
                               "3 hour", "4 hour", "5 hour", "6 hour", "12 hour",
                               "yesterday", "1 day ago", "2 day", "3 day"]):
        return True
    # Explicit stale indicators
    stale_days = [str(n) for n in range(4, 365)]
    for n in stale_days:
        if f"{n} day" in dt:
            return False
    if any(w in dt for w in ["week", "month", "year", "30+", "60", "90"]):
        return False
    # Try parsing as a date
    try:
        from dateutil import parser as dateutil_parser
        parsed = dateutil_parser.parse(date_text, fuzzy=True)
        if parsed.tzinfo is not None:
            parsed = parsed.replace(tzinfo=None)
        hours_ago = (datetime.now() - parsed).total_seconds() / 3600
        return hours_ago <= _FRESHNESS_HOURS
    except Exception:
        pass
    return True


# Backward compat alias
is_within_48h = is_within_window


def is_job_valid(job: dict) -> bool:
    """Check if a job has the required fields and is not stale."""
    if not job.get("title") or not job.get("url"):
        return False
    posted_date = job.get("posted_date", "")
    if posted_date and not is_within_window(posted_date):
        return False
    return True


def _url_fingerprint(url: str) -> str:
    """Stable short fingerprint for deduplication — survives minor URL param changes."""
    parsed = urlparse(url)
    # Use scheme + netloc + path only (ignore tracking params)
    core = f"{parsed.scheme}://{parsed.netloc}{parsed.path}".rstrip("/")
    return hashlib.md5(core.encode()).hexdigest()[:12]


class BaseScraper:
    def __init__(self):
        self.session = requests.Session()
        self._ua_idx = random.randint(0, len(_UA_POOL) - 1)
        self._set_ua(self._ua_idx)

    # ── Headers ────────────────────────────────────────────────────────────

    def _set_ua(self, idx: int | None = None):
        if idx is None:
            self._ua_idx = (self._ua_idx + 1) % len(_UA_POOL)
            idx = self._ua_idx
        ua = _UA_POOL[idx % len(_UA_POOL)]
        self.session.headers.update({
            "User-Agent": ua,
            "Accept-Language": "en-US,en;q=0.9",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
            "DNT": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Upgrade-Insecure-Requests": "1",
        })

    # ── Circuit breaker ────────────────────────────────────────────────────

    def _is_domain_backed_off(self, url: str) -> bool:
        domain = urlparse(url).netloc
        until = _DOMAIN_BACKOFF_UNTIL.get(domain, 0)
        if time.time() < until:
            remaining = int(until - time.time())
            print(f"  [circuit] {domain} backed off for {remaining}s more — skipping")
            return True
        return False

    def _record_domain_success(self, url: str):
        domain = urlparse(url).netloc
        _DOMAIN_FAILURES[domain] = 0

    def _record_domain_failure(self, url: str):
        domain = urlparse(url).netloc
        _DOMAIN_FAILURES[domain] = _DOMAIN_FAILURES.get(domain, 0) + 1
        count = _DOMAIN_FAILURES[domain]
        if count >= _MAX_FAILURES:
            backoff = _BACKOFF_SECONDS * (2 ** min(count - _MAX_FAILURES, 4))  # exp backoff up to ~80m
            _DOMAIN_BACKOFF_UNTIL[domain] = time.time() + backoff
            print(f"  [circuit] {domain} failed {count}x — backing off {backoff}s")

    # ── Robots.txt check ──────────────────────────────────────────────────

    def _respect_robots(self, url: str) -> bool:
        """Check URL against cached robots.txt disallow rules. True = allowed."""
        domain = urlparse(url).netloc
        path   = urlparse(url).path
        now = time.time()
        if domain not in _ROBOTS_CHECKED or now - _ROBOTS_CHECKED.get(domain, 0) > _ROBOTS_TTL:
            _ROBOTS_CHECKED[domain] = now
            try:
                robots_url = f"https://{domain}/robots.txt"
                resp = requests.get(robots_url,
                    headers={"User-Agent": "Mozilla/5.0 (compatible; JobApply/1.0)"},
                    timeout=8,
                )
                if resp.status_code == 200:
                    disallowed = []
                    in_our_block = False
                    for line in resp.text.splitlines():
                        line = line.strip()
                        if line.lower().startswith("user-agent:"):
                            agent = line.split(":", 1)[1].strip().lower()
                            in_our_block = agent in ("*", "jobapply", "mozilla")
                        elif in_our_block and line.lower().startswith("disallow:"):
                            dis_path = line.split(":", 1)[1].strip()
                            if dis_path:
                                disallowed.append(dis_path)
                    _ROBOTS_DISALLOWED[domain] = disallowed
                    if disallowed:
                        print(f"  [robots] {domain}: {len(disallowed)} disallowed paths")
                else:
                    _ROBOTS_DISALLOWED[domain] = []
            except Exception as e:
                print(f"  [robots] {domain}: could not fetch ({e})")
                _ROBOTS_DISALLOWED[domain] = []
        for dis_path in _ROBOTS_DISALLOWED.get(domain, []):
            if dis_path and dis_path != "/" and path.startswith(dis_path):
                print(f"  [robots] BLOCKED by robots.txt: {url[:80]}")
                return False
        return True

    # ── Safe polite delay ──────────────────────────────────────────────────

    def _polite_wait(self, url: str):
        """Sleep enough so we hit each domain at most 1 req / _MIN_DELAY seconds."""
        domain = urlparse(url).netloc
        last   = _DOMAIN_LAST_HIT.get(domain, 0)
        wait   = random.uniform(_MIN_DELAY, _MAX_DELAY) - (time.time() - last)
        if wait > 0:
            time.sleep(wait)
        _DOMAIN_LAST_HIT[domain] = time.time()

    # ── HTTP helpers ───────────────────────────────────────────────────────

    def fetch(self, url: str, timeout: int = 25, _attempt: int = 0) -> str | None:
        if _attempt == 0:
            self._set_ua()
        if self._is_domain_backed_off(url):
            return None
        if not self._respect_robots(url):
            return None
        cached = _HTTP_CACHE.get(url)
        if cached:
            expires, text = cached
            if time.time() < expires:
                return text
        self._polite_wait(url)
        try:
            resp = self.session.get(url, timeout=timeout, allow_redirects=True)
            # Back off + rotate UA on rate-limit / anti-bot responses
            if resp.status_code in (403, 429, 503) and _attempt < 3:
                wait = (2 ** _attempt) * random.uniform(3, 7)
                print(f"[scraper] {resp.status_code} on {url[:60]} — waiting {wait:.1f}s, rotating UA")
                time.sleep(wait)
                self._set_ua()
                return self.fetch(url, timeout, _attempt + 1)
            if resp.status_code == 200:
                self._record_domain_success(url)
                _HTTP_CACHE[url] = (time.time() + _HTTP_CACHE_TTL, resp.text)
                return resp.text
            print(f"[scraper] HTTP {resp.status_code} for {url[:60]}")
            self._record_domain_failure(url)
            return None
        except requests.exceptions.Timeout:
            print(f"[scraper] Timeout: {url[:60]}")
            self._record_domain_failure(url)
            return None
        except Exception as e:
            print(f"[scraper] Error: {url[:60]} — {e}")
            self._record_domain_failure(url)
            return None

    def fetch_soup(self, url: str, timeout: int = 25) -> BeautifulSoup | None:
        html = self.fetch(url, timeout)
        return BeautifulSoup(html, "html.parser") if html else None

    def fetch_json(self, url: str, timeout: int = 20, extra_headers: dict = None) -> dict | list | None:
        self._set_ua()
        if self._is_domain_backed_off(url):
            return None
        cached = _HTTP_CACHE.get(url)
        if cached:
            expires, text = cached
            if time.time() < expires:
                try:
                    return json.loads(text)
                except Exception:
                    pass
        self._polite_wait(url)
        try:
            headers = {**self.session.headers, "Accept": "application/json"}
            if extra_headers:
                headers.update(extra_headers)
            resp = self.session.get(url, timeout=timeout, headers=headers, allow_redirects=True)
            resp.raise_for_status()
            self._record_domain_success(url)
            _HTTP_CACHE[url] = (time.time() + _HTTP_CACHE_TTL, resp.text)
            return resp.json()
        except Exception as e:
            print(f"[scraper] JSON error: {url[:60]} — {e}")
            self._record_domain_failure(url)
            return None

    def post_json(self, url: str, body: dict, headers: dict = None, timeout: int = 20) -> dict | list | None:
        """POST JSON — used for Algolia and similar APIs."""
        self._set_ua()
        if self._is_domain_backed_off(url):
            return None
        try:
            h = {**self.session.headers, "Content-Type": "application/json", "Accept": "application/json"}
            if headers:
                h.update(headers)
            resp = self.session.post(url, json=body, headers=h, timeout=timeout)
            resp.raise_for_status()
            self._record_domain_success(url)
            return resp.json()
        except Exception as e:
            print(f"[scraper] POST JSON error: {url[:60]} — {e}")
            self._record_domain_failure(url)
            return None

    def fetch_rss(self, url: str) -> list[dict]:
        """Parse RSS/Atom feed — much more stable than HTML scraping."""
        html = self.fetch(url)
        if not html:
            return []
        soup  = BeautifulSoup(html, "xml")
        items = soup.find_all("item") or soup.find_all("entry")
        out   = []
        for it in items[:40]:
            title   = self._tag_text(it, ["title"])
            link_el = it.find("link")
            link    = ""
            if link_el:
                link = link_el.get("href", "") or link_el.get_text(strip=True) or ""
            desc_el = it.find("description") or it.find("summary") or it.find("content")
            desc    = self._clean_text(desc_el.get_text()[:400]) if desc_el else ""
            date_el = it.find("pubDate") or it.find("published") or it.find("updated")
            posted  = self._extract_date(date_el) if date_el else ""
            if title and link:
                out.append({"title": title, "url": link, "description": desc, "posted_date": posted})
        return out

    def fetch_json_ld(self, soup: BeautifulSoup) -> list[dict]:
        """Extract schema.org/JobPosting — very stable, preferred over HTML selectors."""
        jobs = []
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                raw = script.string or script.get_text()
                if not raw or not raw.strip():
                    continue
                data    = json.loads(raw)
                entries = []
                if isinstance(data, dict):
                    if data.get("@type") == "JobPosting":
                        entries = [data]
                    elif isinstance(data.get("@graph"), list):
                        entries = [e for e in data["@graph"] if e.get("@type") == "JobPosting"]
                elif isinstance(data, list):
                    entries = [e for e in data if isinstance(e, dict) and e.get("@type") == "JobPosting"]
                for e in entries:
                    loc  = e.get("jobLocation", {}) or {}
                    if isinstance(loc, list):
                        loc = loc[0] if loc else {}
                    addr = (loc.get("address", {}) or {}) if isinstance(loc, dict) else {}
                    location_parts = []
                    for key in ("addressLocality", "addressRegion", "addressCountry"):
                        v = addr.get(key, "") if isinstance(addr, dict) else ""
                        if v and isinstance(v, str):
                            location_parts.append(v)
                    location = ", ".join(location_parts)
                    url  = (e.get("url", "") or
                            (e.get("identifier", {}) or {}).get("url", "") or
                            e.get("sameAs", "") or "")
                    posted = (e.get("datePosted", "") or "")[:10]
                    title  = e.get("title", "") or e.get("name", "")
                    if title and url:
                        company = ((e.get("hiringOrganization") or {}).get("name", ""))
                        if not company:
                            for sep in [" at ", " – ", " — ", " - ", " / ", " | ", " @ "]:
                                parts = title.split(sep)
                                if len(parts) >= 2:
                                    company = parts[-1].strip()
                                    title = sep.join(parts[:-1]).strip()
                                    break
                        desc_raw = e.get("description", "") or ""
                        # Strip HTML from LD+JSON description
                        desc_soup = BeautifulSoup(desc_raw[:1000], "html.parser")
                        desc = self._clean_text(desc_soup.get_text())[:600]
                        jobs.append({
                            "title": title,
                            "company": company,
                            "location": location,
                            "description": desc,
                            "url": url,
                            "posted_date": posted,
                        })
            except Exception:
                pass
        return jobs

    # ── 72-hour freshness gate ────────────────────────────────────────────

    def is_within_48h(self, date_text: str) -> bool:
        return is_within_window(date_text)

    def filter_fresh(self, jobs: list[dict]) -> list[dict]:
        return filter_fresh(jobs)

    # ── Multi-selector helpers ────────────────────────────────────────────

    def multi_select(self, parent, selectors: list[str]) -> list:
        for sel in selectors:
            try:
                found = parent.select(sel)
                if found:
                    return found
            except Exception:
                pass
        return []

    def first_text(self, el, selectors: list[str], default: str = "") -> str:
        for sel in selectors:
            try:
                found = el.select_one(sel)
                if found:
                    text = self._clean_text(found.get_text())
                    if text:
                        return text
            except Exception:
                pass
        return default

    def first_href(self, el, selectors: list[str], base_url: str = "") -> str:
        for sel in selectors:
            try:
                found = el.select_one(sel)
                if found:
                    href = found.get("href", "")
                    if href:
                        return urljoin(base_url, href) if not href.startswith("http") else href
            except Exception:
                pass
        return ""

    # ── Heuristic text extractor (last resort) ────────────────────────────

    def _extract_from_text(self, soup: BeautifulSoup, source: str, base_url: str, cat: str, limit: int = 25) -> list[dict]:
        JOB_KEYWORDS = [
            "analyst", "officer", "manager", "engineer", "developer", "coordinator",
            "specialist", "associate", "consultant", "director", "intern", "trainee",
            "researcher", "advisor", "supervisor", "lead", "head", "assistant",
            "analytics", "scientist", "architect", "analyst/programmer", "professor",
        ]
        SKIP_TITLES = ["job openings", "job vacancies", "job recruitment",
                       "subscribe", "newsletter", "affiliate", "success stories",
                       "reviews", "goody bag", "sign up", "create account",
                       "forgot password", "privacy policy", "terms of service",
                       "sitemap", "contact us", "about us", "career tips",
                       "interview tips", "cv writing", "resume writing"]
        jobs, seen = [], set()
        for a in soup.find_all("a", href=True)[:250]:
            text = self._clean_text(a.get_text())
            if not text or len(text) < 5 or len(text) > 120:
                continue
            text_lower = text.lower()
            if not any(kw in text_lower for kw in JOB_KEYWORDS):
                continue
            if any(sk in text_lower for sk in SKIP_TITLES):
                continue
            href = a.get("href", "")
            full_url = urljoin(base_url, href) if not href.startswith("http") else href
            fp = _url_fingerprint(full_url)
            if fp in seen:
                continue
            seen.add(fp)

            # Try to extract company/location from surrounding context
            company = ""
            location = ""
            desc = ""
            parent = a.parent
            for _ in range(5):
                if not parent or parent.name in ("html", "body", "div", "section"):
                    break
                parent = parent.parent
            if parent:
                parent_text = parent.get_text(" ", strip=True)
                # Try common separators
                for sep in [" at ", " – ", " — ", " - ", " | ", " @ "]:
                    if sep in text and text.index(sep) < len(text) * 0.7:
                        parts = text.split(sep, 1)
                        candidate = parts[-1].strip()
                        if candidate and len(candidate) < 60:
                            company = candidate
                            text = parts[0].strip()
                            break
                # Try to find company from surrounding elements
                if not company:
                    for sel in [".company", "[class*='company']", "[class*='employer']",
                                "[class*='org']", ".organization", "span[class*='name']",
                                ".job-meta", ".meta", "small", ".text-muted"]:
                        el = parent.select_one(sel)
                        if el:
                            ct = self._clean_text(el.get_text())
                            if ct and len(ct) < 60 and ct not in text:
                                company = ct
                                break
                # Try to find location
                for sel in ["[class*='location']", "[class*='place']", "[class*='city']",
                            "[class*='state']", "[class*='country']", ".job-location"]:
                    el = parent.select_one(sel)
                    if el:
                        lt = self._clean_text(el.get_text())
                        if lt and len(lt) < 60:
                            location = lt
                            break
                # Try to get posted date from nearby text
                posted = ""
                for sel in ["time", "[class*='date']", "[class*='posted']",
                            "[class*='ago']", "[class*='published']", "[datetime]"]:
                    el = parent.select_one(sel)
                    if el:
                        dt = el.get("datetime", "") or self._clean_text(el.get_text())
                        if dt:
                            posted = dt[:20]
                            break
                # Try to get description from nearby text
                for sel in ["p", "[class*='desc']", "[class*='summary']",
                            "[class*='excerpt']", ".text", ".content"]:
                    el = parent.select_one(sel)
                    if el and el != a:
                        dt = self._clean_text(el.get_text())
                        if dt and len(dt) > 20 and dt != text:
                            desc = dt[:400]
                            break

            jobs.append(self._make_job(text, company, location, desc, full_url, source, cat, posted))
            if len(jobs) >= limit:
                break
        if jobs:
            print(f"  [heuristic] {source}: extracted {len(jobs)} jobs via text fallback")
        return jobs

    # ── Text helpers ──────────────────────────────────────────────────────

    def _tag_text(self, el, tags: list[str]) -> str:
        for tag in tags:
            found = el.find(tag)
            if found:
                return self._clean_text(found.get_text())
        return ""

    def _clean_text(self, text: str) -> str:
        if not text:
            return ""
        # Collapse whitespace, strip HTML entities
        text = re.sub(r"\s+", " ", str(text)).strip()
        # Remove common boilerplate
        for noise in ["View job", "Apply now", "Apply Now", "Read more", "See more"]:
            text = text.replace(noise, "").strip()
        return text

    def _extract_date(self, element) -> str:
        if not element:
            return ""
        raw = self._clean_text(element.get("datetime", "") or element.get_text())
        patterns = [
            r"(\d{4}-\d{2}-\d{2})",
            r"(\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{4})",
            r"(\d{1,2}/\d{1,2}/\d{4})",
        ]
        for p in patterns:
            m = re.search(p, raw, re.IGNORECASE)
            if m:
                return m.group(1)
        lower = raw.lower()
        if any(w in lower for w in ["today", "just now", "moment", "1 hour", "hour"]):
            return "Today"
        if "yesterday" in lower:
            return "Yesterday"
        return raw[:25]

    def _make_job(self, title, company, location, description, url,
                  source, category, posted="") -> dict:
        company = self._clean_text(company)
        title   = self._clean_text(title)
        # Extract company from title if missing (e.g. "Engineer at Acme Corp")
        if not company and title:
            for sep in [" at ", " – ", " — ", " - ", " / ", " | ", " @ "]:
                parts = title.split(sep)
                if len(parts) >= 2:
                    company = parts[-1].strip()
                    title   = sep.join(parts[:-1]).strip()
                    break
        return {
            "title":       title,
            "company":     company,
            "location":    self._clean_text(location),
            "description": self._clean_text(description)[:600],
            "url":         url.strip() if url else "",
            "source":      source,
            "category":    category,
            "posted_date": posted or "",
        }
