import time
import asyncio
from datetime import datetime

from backend.config import PUBLIC_BOARDS, CRON_QUERIES
from backend.database import save_global_jobs, deactivate_old_jobs, get_global_stats, create_scrape_log, update_scrape_log

from backend.scrapers.nigeria import NigerianJobScraper
from backend.scrapers.ngos import NGOJobScraper
from backend.scrapers.international import InternationalJobScraper
from backend.scrapers.highimpact import HighImpactScraper
from backend.scrapers.web3 import Web3JobScraper
from backend.scrapers.ats import ATSJobScraper

_MAX_JOBS = 1000
_BOARD_TIMEOUT = 45  # seconds max per board (all queries combined)

SCRAPER_MAP = {
    "nigeria": NigerianJobScraper(),
    "ngo": NGOJobScraper(),
    "international": InternationalJobScraper(),
    "highimpact": HighImpactScraper(),
    "web3": Web3JobScraper(),
    "ats": ATSJobScraper(),
}


def _scrape_board(board_name: str, cat: str, query: str) -> list[dict]:
    scraper = SCRAPER_MAP.get(cat)
    if not scraper:
        return []
    method_name = f"scrape_{board_name}"
    method = getattr(scraper, method_name, None)
    if not method:
        return []
    try:
        if asyncio.iscoroutinefunction(method):
            return []
        result = method(query)
        if isinstance(result, list):
            for j in result:
                j["source"] = board_name
                j["category"] = cat
            return result
    except Exception as e:
        print(f"[cron] Error scraping {board_name} ({cat}/{query}): {e}")
    return []


_current_log_id = None


def run_nightly_scrape() -> dict:
    global _current_log_id
    start = time.time()
    all_jobs = []
    queries = CRON_QUERIES

    _current_log_id = create_scrape_log()
    print(f"[cron] Nightly scrape #{_current_log_id} starting at {datetime.now().isoformat()}")

    board_yields = {}
    error_msg = ""
    try:
        for cat, name, cfg in PUBLIC_BOARDS:
            if not cfg.get("enabled", True):
                continue
            board_start = time.time()
            board_urls = set()
            for query in queries:
                if len(all_jobs) >= _MAX_JOBS * 2:
                    break
                if time.time() - board_start > _BOARD_TIMEOUT:
                    print(f"[cron] Timeout for {name} ({cat}) after {_BOARD_TIMEOUT}s")
                    break
                jobs = _scrape_board(name, cat, query)
                if jobs:
                    all_jobs.extend(jobs)
                    board_yields[name] = board_yields.get(name, 0) + len(jobs)
                    new_urls = {j.get("url", "") for j in jobs if j.get("url")}
                    if board_urls and new_urls and new_urls.issubset(board_urls):
                        break
                    board_urls.update(new_urls)
    except Exception as e:
        error_msg = f"{type(e).__name__}: {e}"
        print(f"[cron] Fatal error during scrape loop: {error_msg}")

    # Dedup by URL
    seen = set()
    unique = []
    for j in all_jobs:
        u = j.get("url", "")
        if u and u not in seen:
            seen.add(u)
            unique.append(j)
            if len(unique) >= _MAX_JOBS:
                break

    # Save to global pool
    saved = 0
    try:
        saved = save_global_jobs(unique)
    except Exception as e:
        err = f"{type(e).__name__}: {e}"
        error_msg = f"{error_msg}; save error: {err}" if error_msg else f"save error: {err}"
        print(f"[cron] Error saving jobs: {err}")

    # Log per-board yield
    print(f"[cron] Board yields:")
    for bname, cnt in sorted(board_yields.items(), key=lambda x: -x[1]):
        print(f"  {bname}: {cnt}")

    # Clean old jobs
    removed = 0
    try:
        removed = deactivate_old_jobs(7)
    except Exception as e:
        err = f"{type(e).__name__}: {e}"
        error_msg = f"{error_msg}; cleanup error: {err}" if error_msg else f"cleanup error: {err}"
        print(f"[cron] Error cleaning old jobs: {err}")

    elapsed = time.time() - start
    import json
    update_scrape_log(
        _current_log_id,
        finished_at=datetime.now().isoformat(),
        status="error" if error_msg else "complete",
        board_yields=json.dumps(board_yields),
        total_scraped=len(all_jobs),
        total_saved=saved,
        total_removed=removed,
        error=error_msg,
    )
    result = {
        "scraped": len(all_jobs),
        "unique": len(unique),
        "saved": saved,
        "removed_old": removed,
        "elapsed_seconds": round(elapsed, 1),
        "timestamp": datetime.now().isoformat(),
        "error": error_msg,
    }
    print(f"[cron] Done: {result}")
    return result


