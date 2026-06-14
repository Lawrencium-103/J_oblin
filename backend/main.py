import json, os, re, random, threading
from pathlib import Path
from contextlib import asynccontextmanager
from datetime import datetime, timedelta

from fastapi import FastAPI, Depends, HTTPException, Query, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

from backend.config import GENERATED_DIR, JOB_BOARDS
from backend.cron import run_nightly_scrape
from backend.database import (
    init_db, create_user, get_user_by_email, get_user_by_id,
    save_api_keys, get_api_keys, get_effective_api_keys,
    save_user_settings, get_user_settings,
    save_cv, get_cv, get_cv_default,
    save_global_jobs, get_global_jobs, get_global_job, get_global_stats,
    get_categories, classify_job_title,
    link_user_job, get_user_job_link, get_user_linked_jobs, update_link_tailoring,
    deactivate_old_jobs,
)
from backend.auth import hash_password, verify_password, create_access_token, get_current_user
from backend.llm import tailor_application as llm_tailor, make_cv_from_scratch
from backend.cv_quality import score_cv_quality
from backend.docx_generator import generate_cv_docx, generate_cover_docx, generate_cv_pdf, generate_cover_pdf, generate_cv_preview_text


def _file_slug(name: str, title: str, company: str = "", number: str = "00") -> str:
    parts = [number]
    if name:
        parts.append(re.sub(r"[^a-zA-Z0-9]", "", name)[:20])
    if title:
        stitle = re.sub(r"[^a-zA-Z0-9 ]", "", title).strip()[:20]
        if stitle:
            words = stitle.split()
            parts.append("".join(w.capitalize() for w in words[:3]))
    if company:
        scompany = re.sub(r"[^a-zA-Z0-9]", "", company)[:10]
        if scompany:
            parts.append(scompany)
    return "_".join(parts) if parts else f"{number}_cv"
from backend.cv_diversity import randomize_tailored_cv
from backend.excel_export import export_jobs_to_excel

from backend.scrapers.base import BaseScraper
from backend.scrapers.nigeria import NigerianJobScraper
from backend.scrapers.ngos import NGOJobScraper
from backend.scrapers.international import InternationalJobScraper
from backend.scrapers.highimpact import HighImpactScraper


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    from backend.cron import setup_scheduler
    scheduler = setup_scheduler(app)
    yield
    if scheduler:
        scheduler.shutdown()


app = FastAPI(title="Joblin", version="2.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"
CRON_TOKEN = os.environ.get("JOBLIN_CRON_TOKEN", "")


# ── Models ──────────────────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    email: str; password: str; name: str = ""

class LoginRequest(BaseModel):
    email: str; password: str

class ScrapeRequest(BaseModel):
    title: str = ""; boards: list[str] = []

class KeysRequest(BaseModel):
    groq: str = ""; nvidia: str = ""; gemini: str = ""; use_default_api: bool = True


# ── Auth Routes ─────────────────────────────────────────────────────────────

@app.post("/api/auth/register")
def register(req: RegisterRequest):
    if not req.email or not req.password:
        raise HTTPException(400, "Email and password required")
    if len(req.password) < 6:
        raise HTTPException(400, "Password must be at least 6 characters")
    if get_user_by_email(req.email):
        raise HTTPException(409, "Email already registered")
    user = create_user(req.email, hash_password(req.password), req.name)
    if not user:
        raise HTTPException(500, "Failed to create user")
    token = create_access_token(user["id"], user["email"])
    return {"token": token, "user": user}


@app.post("/api/auth/login")
def login(req: LoginRequest):
    user = get_user_by_email(req.email)
    if not user or not verify_password(req.password, user["password_hash"]):
        raise HTTPException(401, "Invalid email or password")
    token = create_access_token(user["id"], user["email"])
    return {"token": token, "user": {"id": user["id"], "email": user["email"], "name": user.get("name", "")}}


@app.get("/api/auth/me")
def me(current_user: dict = Depends(get_current_user)):
    return get_user_by_id(current_user["user_id"])


# ── CV Routes ───────────────────────────────────────────────────────────────

@app.get("/api/cv")
def get_user_cv(current_user: dict = Depends(get_current_user)):
    cv_json = get_cv(current_user["user_id"])
    if not cv_json:
        return get_cv_default()
    try:
        return json.loads(cv_json)
    except json.JSONDecodeError:
        return get_cv_default()


@app.put("/api/cv")
def put_user_cv(data: dict = Body(...), current_user: dict = Depends(get_current_user)):
    try:
        save_cv(current_user["user_id"], json.dumps(data, ensure_ascii=False))
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(500, detail=f"Failed to save CV: {str(e)}")


# ── Make CV from Scratch (for users without a CV) ──────────────────────────

class MakeCVRequest(BaseModel):
    raw_text: str = ""
    target_jobs: list[str] = []
    target_type: str = "local"  # "local" or "international"
    remote: bool = False
    timezone: str = "Africa/Lagos"


@app.post("/api/cv/make-cv")
def make_cv(req: MakeCVRequest, current_user: dict = Depends(get_current_user)):
    user_id = current_user["user_id"]
    api_keys = get_effective_api_keys(user_id)

    if not req.raw_text.strip():
        return {
            "status": "template",
            "cv": get_cv_default(),
            "preview": "Paste your information and click Generate to create your CV.",
            "provider": "none",
        }

    if not api_keys:
        raise HTTPException(400, "No API keys found. Add keys in Settings or enable default AI.")

    cv_data, provider = make_cv_from_scratch(
        raw_text=req.raw_text,
        target_jobs=req.target_jobs,
        target_type=req.target_type,
        remote_preferences={"remote": req.remote, "timezone": req.timezone},
        api_keys=api_keys,
    )

    # Save the generated CV
    try:
        save_cv(user_id, json.dumps(cv_data, ensure_ascii=False))
    except Exception as e:
        raise HTTPException(500, f"Failed to save CV: {str(e)}")

    # Generate preview text + documents
    from docx_generator import generate_cv_preview_text, generate_cv_docx, generate_cv_pdf
    preview = generate_cv_preview_text(cv_data)

    name = (cv_data.get("personal_info") or {}).get("name", "")
    slug = _file_slug(name, req.target_jobs[0] if req.target_jobs else "CV", "", number="00")
    cv_path = str(GENERATED_DIR / f"{slug}_cv.docx")
    cv_pdf_path = str(GENERATED_DIR / f"{slug}_cv.pdf")
    generate_cv_docx(cv_data, cv_path, target_type=req.target_type)
    generate_cv_pdf(cv_data, cv_pdf_path, target_type=req.target_type)

    return {
        "status": "ok",
        "cv": cv_data,
        "preview": preview,
        "provider": provider,
        "target_jobs": req.target_jobs,
        "target_type": req.target_type,
        "cv_path": cv_path,
        "cv_pdf_path": cv_pdf_path,
    }


# ── API Keys ────────────────────────────────────────────────────────────────

@app.get("/api/keys")
def get_user_keys(current_user: dict = Depends(get_current_user)):
    keys = get_api_keys(current_user["user_id"])
    settings = get_user_settings(current_user["user_id"])
    keys["use_default_api"] = settings.get("use_default_api", True)
    return keys


@app.put("/api/keys")
def put_user_keys(keys: KeysRequest, current_user: dict = Depends(get_current_user)):
    data = {k: v.strip() for k, v in {"groq": keys.groq, "nvidia": keys.nvidia, "gemini": keys.gemini}.items() if v and v.strip()}
    save_api_keys(current_user["user_id"], data)
    save_user_settings(current_user["user_id"], {"use_default_api": keys.use_default_api})
    return {"status": "ok"}


# ── Scrape Routes ───────────────────────────────────────────────────────────

SCRAPER_MAP = {
    "nigeria": NigerianJobScraper(),
    "ngo": NGOJobScraper(),
    "international": InternationalJobScraper(),
    "highimpact": HighImpactScraper(),
}

def _scrape_board(board_name: str, cat: str, query: str) -> list[dict]:
    scraper = SCRAPER_MAP.get(cat)
    if not scraper:
        return []
    method = getattr(scraper, f"scrape_{board_name}", None)
    if not method:
        return []
    try:
        result = method(query)
        if isinstance(result, list):
            for j in result:
                j["source"] = board_name; j["category"] = cat
            return result
    except Exception as e:
        pass
    return []


@app.post("/api/scrape")
def scrape(req: ScrapeRequest):
    query = req.title.strip() or "Data Analyst"
    all_jobs = []
    for cat, boards in JOB_BOARDS.items():
        for name, cfg in boards.items():
            if req.boards and name not in req.boards and cat not in req.boards:
                continue
            if not cfg.get("enabled", True) or cfg.get("type") in ("login_required", "login_optional", "playwright"):
                continue
            jobs = _scrape_board(name, cat, query)
            all_jobs.extend(jobs)

    saved = save_global_jobs(all_jobs)
    return {"jobs": all_jobs[:50], "count": len(all_jobs), "saved": saved}


# ── Global Jobs Routes ──────────────────────────────────────────────────────

@app.post("/api/scrape/cron")
def scrape_cron(req: ScrapeRequest, token: str = Query("")):
    if CRON_TOKEN and token != CRON_TOKEN:
        raise HTTPException(403, "Invalid token")
    threading.Thread(target=run_nightly_scrape, daemon=True).start()
    return {"status": "started", "message": "Scraping in background"}


@app.get("/api/jobs")
def list_global_jobs(
    category: str = Query(""), source: str = Query(""), search: str = Query(""),
    is_graduate: bool = Query(None), sort: str = Query("date"),
    limit: int = Query(100), offset: int = Query(0),
):
    jobs, total = get_global_jobs(category, source, search, is_graduate, limit, offset, sort)
    return {"jobs": jobs, "total": total, "count": len(jobs)}


@app.get("/api/jobs/{job_id}")
def get_job(job_id: int):
    job = get_global_job(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    return job


# ── User-Job Link Routes ────────────────────────────────────────────────────

@app.post("/api/jobs/{job_id}/link")
def link_job(job_id: int, current_user: dict = Depends(get_current_user)):
    job = get_global_job(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    link_user_job(current_user["user_id"], job_id)
    return {"status": "linked"}


@app.get("/api/my/jobs")
def my_jobs(current_user: dict = Depends(get_current_user)):
    jobs = get_user_linked_jobs(current_user["user_id"])
    return {"jobs": jobs, "count": len(jobs)}


# ── Manual Job Entry ────────────────────────────────────────────────────────

_scraper_base = BaseScraper()

@app.post("/api/jobs/extract-url")
def extract_job_url(url: str = Body(..., embed=True)):
    if not url:
        raise HTTPException(400, "URL required")
    
    # Try multiple ways to fetch the HTML
    html = None
    
    # Method 1: Using the BaseScraper (respects robots.txt, has delays)
    try:
        html = _scraper_base.fetch(url, timeout=15)
    except Exception:
        pass
        
    # Method 2: Direct requests with a common UA (bypass robots.txt check if it's the bottleneck)
    if not html:
        try:
            import requests
            resp = requests.get(url, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            }, timeout=15)
            if resp.status_code == 200:
                html = resp.text
        except Exception:
            pass

    if not html:
        raise HTTPException(400, "Could not fetch URL. The site might be blocking automated access. Try pasting details manually.")

    from bs4 import BeautifulSoup
    import json as _json
    soup = BeautifulSoup(html, "html.parser")

    # Priority 0: Parse LD+JSON structured data (most reliable if available)
    title = ""
    company = ""
    location = ""
    desc = ""
    for script in soup.find_all("script", type="application/ld+json"):
        text = script.string or ""
        if not text.strip(): continue
        try:
            data = _json.loads(text)
        except _json.JSONDecodeError:
            continue
        if not isinstance(data, dict) or data.get("@type") != "JobPosting":
            continue
        if data.get("title"):
            title = data["title"]
        ho = data.get("hiringOrganization") or {}
        if isinstance(ho, dict) and ho.get("name"):
            company = ho["name"]
        jl = data.get("jobLocation") or {}
        if isinstance(jl, dict):
            addr = jl.get("address") or jl
            parts = []
            for key in ("addressLocality", "addressRegion", "addressCountry"):
                v = addr.get(key, "") if isinstance(addr, dict) else ""
                if v: parts.append(v)
            if parts: location = ", ".join(parts)
        if data.get("description"):
            import html as _html
            from bs4 import BeautifulSoup as _BS
            desc_text = _html.unescape(data["description"])
            desc_soup = _BS(desc_text, "html.parser")
            for br in desc_soup.find_all("br"): br.replace_with("\n")
            for p_tag in desc_soup.find_all("p"): p_tag.append("\n")
            desc = desc_soup.get_text("\n", strip=True)
        break  # Use first JobPosting found

    # Fallback to HTML scraping if LD+JSON didn't yield enough
    meta_title = soup.find("meta", property="og:title") or soup.find("meta", name="twitter:title")
    meta_desc = soup.find("meta", property="og:description") or soup.find("meta", name="twitter:description") or soup.find("meta", name="description")
    
    if not title:
        if meta_title:
            title = meta_title.get("content", "")
        if not title:
            for sel in ["h1", "h2", "title", "[class*='title'] h1", "[class*='job-title']", "[data-testid='job-title']", ".job-header h1"]:
                el = soup.select_one(sel)
                if el:
                    title = el.get_text(strip=True)
                    break

    if not desc:
        for sel in ["[class*='description']", "[class*='job-description']", "[data-testid='job-description']",
                    ".job-details", ".vacancy-desc", "article", "main", "[role='main']"]:
            el = soup.select_one(sel)
            if el:
                for br in el.find_all("br"): br.replace_with("\n")
                for p_tag in el.find_all("p"): p_tag.append("\n")
                desc = el.get_text("\n", strip=True)
                break
        if not desc and meta_desc:
            desc = meta_desc.get("content", "")

    if not company:
        for sel in ["[class*='company']", "[class*='employer']", "[class*='org']",
                    "[data-testid='company-name']", ".hiring-org", "meta[name='author']"]:
            el = soup.select_one(sel)
            if el:
                company = el.get("content", el.get_text(strip=True))
                break

    if not location:
        for sel in ["[class*='location']", "[class*='place']", "[class*='city']", "[class*='country']", ".job-location"]:
            el = soup.select_one(sel)
            if el:
                location = el.get_text(strip=True)
                break

    job_data = {
        "title": title or "Unknown Position",
        "company": company or "",
        "location": location or "",
        "description": (desc or "")[:5000] if desc else "No description extracted",
        "url": url,
        "source": "manual",
        "category": classify_job_title(title, desc or ""),
    }
    return job_data


# ── Tailor Routes ───────────────────────────────────────────────────────────
def _tailor_with_quality(job_title, job_description, company, cv_data, api_keys, category):
    """Tailor with quality gate + up to 3 regeneration attempts."""
    MAX_ATTEMPTS = 3
    best_result = None
    best_score = -1
    feedback = ""

    for attempt in range(1, MAX_ATTEMPTS + 1):
        result = llm_tailor(
            job_title=job_title,
            job_description=job_description,
            company=company,
            user_cv=cv_data,
            api_keys=api_keys,
            category=category,
            feedback=feedback,
            attempt=attempt,
        )

        tailored_cv = dict(cv_data)
        if result.get("professional_summary"):
            tailored_cv["professional_summary"] = result["professional_summary"]
        if result.get("tailored_skills"):
            tailored_cv["skills"] = result["tailored_skills"]
        if result.get("tailored_experience"):
            tailored_cv["experience"] = result["tailored_experience"]
        if result.get("cover_letter"):
            tailored_cv["cover_letter"] = result["cover_letter"]

        quality = score_cv_quality(tailored_cv)
        total = sum(v["score"] for v in quality["scores"].values())
        if total > best_score:
            best_result = (result, tailored_cv, quality)
            best_score = total

        if quality["pass"]:
            return best_result

        feedback = quality["feedback"]

    return best_result


# NOTE: /api/tailor/from-data MUST be defined before /api/tailor/{job_id}
# to prevent FastAPI from matching "from-data" as a job_id int parameter.

@app.post("/api/tailor/from-data")
def tailor_from_job_data(
    job: dict = Body(...),
    current_user: dict = Depends(get_current_user),
):
    user_id = current_user["user_id"]
    user_cv_json = get_cv(user_id)
    if not user_cv_json:
        raise HTTPException(400, "No CV found. Save your CV first.")
    cv_data = json.loads(user_cv_json)

    api_keys = get_effective_api_keys(user_id)
    if not api_keys:
        raise HTTPException(400, "No API keys found. Add keys in Settings or enable default AI.")

    target_type = job.get("target_type", "local")

    tailored = _tailor_with_quality(
        job_title=job.get("title", ""),
        job_description=job.get("description", ""),
        company=job.get("company", ""),
        cv_data=cv_data,
        api_keys=api_keys,
        category=job.get("category", ""),
    )
    result, tailored_cv, quality = tailored

    if tailored_cv.get("experience"):
        tailored_cv = randomize_tailored_cv(tailored_cv, job.get("title", ""), seed=user_id)

    name = (tailored_cv.get("personal_info") or {}).get("name", "")
    score = result.get("match_score", 0)
    slug = _file_slug(name, job.get("title", ""), job.get("company", ""), number=str(score).zfill(2))
    cv_path = str(GENERATED_DIR / f"{slug}_cv.docx")
    cover_path = str(GENERATED_DIR / f"{slug}_cover.docx")
    cv_pdf_path = str(GENERATED_DIR / f"{slug}_cv.pdf")
    cover_pdf_path = str(GENERATED_DIR / f"{slug}_cover.pdf")
    generate_cv_docx(tailored_cv, cv_path, target_type=target_type)
    generate_cover_docx(result.get("cover_letter", "") or "", cover_path, personal_info=tailored_cv.get("personal_info"), company=job.get("company", ""))
    generate_cv_pdf(tailored_cv, cv_pdf_path, target_type=target_type)
    generate_cover_pdf(result.get("cover_letter", "") or "", cover_pdf_path, personal_info=tailored_cv.get("personal_info"), company=job.get("company", ""))

    return {
        "status": "ok",
        "match_score": score,
        "provider": result.get("provider", "rule-based"),
        "keywords_hit": result.get("keywords_hit", []),
        "professional_summary": result.get("professional_summary", ""),
        "cover_letter": result.get("cover_letter", "") or "",
        "cv_preview": generate_cv_preview_text(tailored_cv),
        "quality_scores": quality["scores"],
        "cv_path": cv_path,
        "cover_path": cover_path,
        "cv_pdf_path": cv_pdf_path,
        "cover_pdf_path": cover_pdf_path,
    }


@app.post("/api/tailor/{job_id}")
def tailor_job(job_id: int, current_user: dict = Depends(get_current_user)):
    user_id = current_user["user_id"]
    job = get_global_job(job_id)
    if not job:
        raise HTTPException(404, "Job not found")

    user_cv_json = get_cv(user_id)
    if not user_cv_json:
        raise HTTPException(400, "No CV found. Save your CV first.")
    cv_data = json.loads(user_cv_json)

    api_keys = get_effective_api_keys(user_id)
    if not api_keys:
        raise HTTPException(400, "No API keys found. Add keys in Settings or enable default AI.")

    # Link job to user if not already
    link_user_job(user_id, job_id)

    target_type = job.get("category", "") if job.get("category", "") in ("international", "remote") else "local"

    tailored = _tailor_with_quality(
        job_title=job.get("title", ""),
        job_description=job.get("description", ""),
        company=job.get("company", ""),
        cv_data=cv_data,
        api_keys=api_keys,
        category=job.get("job_category", ""),
    )
    result, tailored_cv, quality = tailored

    if tailored_cv.get("experience"):
        tailored_cv = randomize_tailored_cv(tailored_cv, job.get("title", ""), seed=user_id)

    name = (tailored_cv.get("personal_info") or {}).get("name", "")
    score = result.get("match_score", 0)
    slug = _file_slug(name, job.get("title", ""), job.get("company", ""), number=str(score).zfill(2))
    cv_path = str(GENERATED_DIR / f"{slug}_cv.docx")
    cover_path = str(GENERATED_DIR / f"{slug}_cover.docx")
    cv_pdf_path = str(GENERATED_DIR / f"{slug}_cv.pdf")
    cover_pdf_path = str(GENERATED_DIR / f"{slug}_cover.pdf")

    generate_cv_docx(tailored_cv, cv_path, target_type=target_type)
    generate_cover_docx(result.get("cover_letter", "") or "", cover_path, personal_info=tailored_cv.get("personal_info"), company=job.get("company", ""))
    generate_cv_pdf(tailored_cv, cv_pdf_path, target_type=target_type)
    generate_cover_pdf(result.get("cover_letter", "") or "", cover_pdf_path, personal_info=tailored_cv.get("personal_info"), company=job.get("company", ""))

    update_link_tailoring(user_id, job_id, cv_path, cover_path)

    return {
        "status": "ok",
        "job_title": job.get("title", ""),
        "match_score": result.get("match_score", 0),
        "provider": result.get("provider", "rule-based"),
        "keywords_hit": result.get("keywords_hit", []),
        "professional_summary": result.get("professional_summary", ""),
        "cover_letter": result.get("cover_letter", "") or "",
        "cv_preview": generate_cv_preview_text(tailored_cv),
        "quality_scores": quality["scores"],
        "cv_path": cv_path,
        "cover_path": cover_path,
        "cv_pdf_path": cv_pdf_path,
        "cover_pdf_path": cover_pdf_path,
    }


# ── Download Routes ─────────────────────────────────────────────────────────
# NOTE: /api/download/manual must be defined before /api/download/{job_id}

@app.get("/api/download/manual/{filename}")
def download_manual(filename: str, current_user: dict = Depends(get_current_user)):
    file_path = GENERATED_DIR / filename
    if not file_path.exists():
        raise HTTPException(404, "File not found")
    ext = Path(filename).suffix.lower()
    media_type = {
        ".pdf": "application/pdf",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    }.get(ext, "application/octet-stream")
    return FileResponse(str(file_path), filename=filename, media_type=media_type, headers={
        "Content-Disposition": f'attachment; filename="{filename}"',
    })


@app.get("/api/download/{job_id}/{doc_type}")
def download(job_id: int, doc_type: str, current_user: dict = Depends(get_current_user)):
    if doc_type not in ("cv", "cover"):
        raise HTTPException(400, "doc_type must be 'cv' or 'cover'")
    link = get_user_job_link(current_user["user_id"], job_id)
    if not link:
        raise HTTPException(404, "Job not linked. Tailor first.")
    path = link.get("tailored_cv_path") if doc_type == "cv" else link.get("tailored_cover_path")
    if not path or not os.path.exists(path):
        raise HTTPException(404, "No tailored file found. Tailor first.")
    filename = f"{doc_type}_{link.get('title', 'job')[:30].replace(' ', '_')}.docx"
    return FileResponse(path, filename=filename, media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document")


# ── Excel Export ────────────────────────────────────────────────────────────

@app.get("/api/export/excel")
def export_excel(
    category: str = Query(""), source: str = Query(""), search: str = Query(""),
    current_user: dict = Depends(get_current_user),
):
    jobs, _ = get_global_jobs(category, source, search, limit=5000)
    path = export_jobs_to_excel(jobs)
    return FileResponse(path, filename="joblin_jobs.xlsx", media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


# ── Dashboard / Stats ──────────────────────────────────────────────────────

@app.get("/api/stats")
def stats():
    return get_global_stats()


@app.get("/api/health")
def health():
    return {"status": "ok", "timestamp": datetime.now().isoformat()}


@app.get("/api/cleanup")
def cleanup_old_jobs(token: str = Query("")):
    if CRON_TOKEN and token != CRON_TOKEN:
        raise HTTPException(403, "Invalid token")
    from database import deactivate_old_jobs
    removed = deactivate_old_jobs(7)
    return {"removed": removed, "status": "ok"}


@app.get("/api/config")
def get_config():
    from config import JOB_BOARDS as JB
    boards = {}
    for cat, cat_boards in JB.items():
        boards[cat] = {name: {"name": name, "region": cfg.get("region", ""), "type": cfg.get("type", "public"), "enabled": cfg.get("enabled", True)} for name, cfg in cat_boards.items()}
    categories = get_categories()
    return {"boards": boards, "categories": categories}


# ── Serve frontend ──────────────────────────────────────────────────────────

@app.api_route("/{full_path:path}", methods=["GET"])
def serve_frontend(full_path: str):
    if full_path.startswith("api/"):
        raise HTTPException(404, "Not found")
    if not full_path:
        full_path = "index.html"
    file_path = FRONTEND_DIR / full_path
    if file_path.is_file():
        return FileResponse(str(file_path))
    html_path = file_path.with_suffix(".html")
    if html_path.is_file():
        return FileResponse(str(html_path))
    login_path = FRONTEND_DIR / "login.html"
    if login_path.is_file():
        return FileResponse(str(login_path))
    raise HTTPException(404, "Not found")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8002, reload=True)
