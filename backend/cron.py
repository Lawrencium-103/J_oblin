import time
import asyncio
from datetime import datetime, timedelta

from backend.config import PUBLIC_BOARDS, CRON_QUERIES
from backend.database import save_global_jobs, deactivate_old_jobs, get_global_stats

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


def run_nightly_scrape() -> dict:
    start = time.time()
    all_jobs = []
    queries = CRON_QUERIES

    print(f"[cron] Nightly scrape starting at {datetime.now().isoformat()}")

    board_yields = {}
    for cat, name, cfg in PUBLIC_BOARDS:
        if not cfg.get("enabled", True):
            continue
        board_got_jobs = False
        board_start = time.time()
        for query in queries:
            if len(all_jobs) >= _MAX_JOBS * 2:
                break
            if time.time() - board_start > _BOARD_TIMEOUT:
                print(f"[cron] Timeout for {name} ({cat}) after {_BOARD_TIMEOUT}s")
                break
            jobs = _scrape_board(name, cat, query)
            if jobs:
                all_jobs.extend(jobs)
                board_got_jobs = True
                board_yields[name] = board_yields.get(name, 0) + len(jobs)
                if board_got_jobs:
                    break

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
    saved = save_global_jobs(unique)

    # Log per-board yield
    print(f"[cron] Board yields:")
    for bname, cnt in sorted(board_yields.items(), key=lambda x: -x[1]):
        print(f"  {bname}: {cnt}")

    # Clean old jobs
    removed = deactivate_old_jobs(7)

    elapsed = time.time() - start
    result = {
        "scraped": len(all_jobs),
        "unique": len(unique),
        "saved": saved,
        "removed_old": removed,
        "elapsed_seconds": round(elapsed, 1),
        "timestamp": datetime.now().isoformat(),
    }
    print(f"[cron] Done: {result}")
    return result


def setup_scheduler(app):
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        from apscheduler.triggers.cron import CronTrigger

        scheduler = BackgroundScheduler()

        # Run at 6:00 AM daily
        scheduler.add_job(
            run_nightly_scrape,
            CronTrigger(hour=6, minute=0),
            id="morning_scrape",
            replace_existing=True,
        )

        # Run at 3:00 PM daily
        scheduler.add_job(
            run_nightly_scrape,
            CronTrigger(hour=15, minute=0),
            id="afternoon_scrape",
            replace_existing=True,
        )

        # Also run once on startup (after 60s delay — lets the server warm up)
        scheduler.add_job(
            run_nightly_scrape,
            trigger="date",
            run_date=datetime.now() + timedelta(seconds=60),
            id="startup_scrape",
            replace_existing=True,
            max_instances=1,
        )

        scheduler.start()
        print("[cron] Scheduler started. Scrapes at 6:00 AM and 3:00 PM daily.")
        return scheduler
    except ImportError:
        print("[cron] APScheduler not installed. Install with: pip install apscheduler")
        return None
    except Exception as e:
        print(f"[cron] Failed to start scheduler: {e}")
        return None
