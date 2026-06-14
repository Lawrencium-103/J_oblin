import hashlib
import secrets
import sqlite3
import json
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from backend.config import DATABASE_PATH


def init_db():
    with get_db() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                name TEXT DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS api_keys (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                provider TEXT NOT NULL,
                api_key TEXT NOT NULL,
                UNIQUE(user_id, provider)
            );

            CREATE TABLE IF NOT EXISTS user_cv (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER UNIQUE NOT NULL,
                cv_json TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            -- Global shared job pool (all scraped jobs go here)
            CREATE TABLE IF NOT EXISTS global_jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                company TEXT,
                location TEXT,
                description TEXT,
                url TEXT UNIQUE,
                source TEXT,
                board_category TEXT,
                job_category TEXT DEFAULT 'other',
                posted_date TEXT,
                date_found TEXT DEFAULT (datetime('now')),
                is_active INTEGER DEFAULT 1,
                is_graduate INTEGER DEFAULT 0,
                has_full_info INTEGER DEFAULT 0,
                match_score REAL DEFAULT 0
            );

            -- User settings (default API toggle, etc.)
            CREATE TABLE IF NOT EXISTS user_settings (
                user_id INTEGER PRIMARY KEY,
                use_default_api INTEGER DEFAULT 1
            );

            -- Per-user job interactions (bridge table)
            CREATE TABLE IF NOT EXISTS user_job_links (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                job_id INTEGER NOT NULL,
                status TEXT DEFAULT 'new',
                tailored_cv_path TEXT,
                tailored_cover_path TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, job_id)
            );

            -- Password reset tokens
            CREATE TABLE IF NOT EXISTS reset_tokens (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                token_hash TEXT NOT NULL,
                expires_at TIMESTAMP NOT NULL,
                used INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            );

            -- Job category definitions
            CREATE TABLE IF NOT EXISTS job_categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                slug TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                icon TEXT DEFAULT '',
                keywords TEXT NOT NULL,
                color TEXT DEFAULT '#059669'
            );
        """)

        _seed_categories(conn)


def _seed_categories(conn):
    categories = [
        ("data-analytics", "Data & Analytics", "chart", "data analyst,data analytics,data entry,database administrator,dashboard developer,bi analyst,business intelligence,data associate,data engineer,data scientist,data architect,analytics manager", "#059669"),
        ("monitoring-evaluation", "Monitoring & Evaluation", "clipboard", "monitoring,evaluation,m&e,meal,me officer,mea officer,monitoring officer,evaluation officer,programme officer,focal person,indicator", "#0284c7"),
        ("ai-machine-learning", "AI & Machine Learning", "brain", "ai,artificial intelligence,machine learning,deep learning,llm,langchain,prompt engineer,ai engineer,ml engineer,data scientist,ai researcher", "#7c3aed"),
        ("software-dev", "Software & IT", "code", "software engineer,software developer,full-stack,backend,frontend,web developer,react,node.js,python developer,java developer,devops,it support,it officer,network administrator,system administrator,cybersecurity", "#dc2626"),
        ("public-health", "Public Health & Medical", "heart", "public health,epidemiologist,health informatics,health data,global health,community health,health information,health analyst,ncd,doctor,nurse,pharmacist,lab technician,medical officer", "#e11d48"),
        ("graduate-entry", "Graduate / Entry Level", "graduation-cap", "graduate,entry level,junior,intern,trainee,associate,recent graduate,graduate trainee,nysc,corper", "#d97706"),
        ("ngo-development", "NGO & Development", "globe", "ngo,nonprofit,international development,humanitarian,donor,unicef,who,world bank,usaid,program manager,program officer,project officer", "#2563eb"),
        ("project-management", "Project Management", "briefcase", "project manager,project management,project coordinator,pmp,scrum master,agile,product manager,program manager,delivery manager", "#0f766e"),
        ("finance-accounting", "Finance & Accounting", "wallet", "accountant,accounting,finance,financial analyst,audit,auditor,tax,treasury,payable,receivable,budget,fp&a,chief financial officer,cfo,controller,bookkeeper", "#9333ea"),
        ("admin-operations", "Admin & Operations", "settings", "administrative,admin officer,admin manager,office manager,receptionist,executive assistant,operations officer,operations manager,facility manager,front desk", "#64748b"),
        ("human-resources", "Human Resources", "users", "hr,human resources,hr officer,hr manager,recruiter,talent acquisition,l&d,learning development,payroll,compensation,benefits,hr business partner,employee relations", "#db2777"),
        ("sales-marketing", "Sales & Marketing", "trending", "sales,sales rep,sales manager,business development,bd,marketing,digital marketing,social media,content writer,copywriter,seo,marketing manager,brand manager,communications,public relations,pr", "#ea580c"),
        ("customer-service", "Customer Service", "headphones", "customer service,customer support,call center,client service,client relationship,account manager,customer success,support officer,help desk", "#f59e0b"),
        ("engineering", "Engineering", "tool", "engineer,civil engineer,mechanical engineer,electrical engineer,structural engineer,site engineer,project engineer,construction,maintenance,technician", "#b45309"),
        ("procurement-supply", "Procurement & Supply Chain", "package", "procurement,procurement officer,purchasing,supply chain,logistics,logistics officer,warehouse,inventory,supply officer,store keeper,transport,fleet", "#0891b2"),
        ("legal-compliance", "Legal & Compliance", "shield", "legal,lawyer,compliance,regulatory,company secretary,legal officer,corporate counsel,attorney,paralegal,risk compliance", "#475569"),
        ("remote", "Remote / Anywhere", "wifi", "remote,work from home,telecommute,virtual,distributed,anywhere,global", "#0891b2"),
    ]
    for slug, name, icon, keywords, color in categories:
        conn.execute(
            "INSERT OR IGNORE INTO job_categories (slug, name, icon, keywords, color) VALUES (?, ?, ?, ?, ?)",
            (slug, name, icon, keywords, color),
        )


@contextmanager
def get_db():
    conn = sqlite3.connect(str(DATABASE_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


# ── Users ───────────────────────────────────────────────────────────────────

def create_user(email: str, password_hash: str, name: str = "") -> dict | None:
    with get_db() as conn:
        try:
            cur = conn.execute(
                "INSERT INTO users (email, password_hash, name) VALUES (?, ?, ?)",
                (email, password_hash, name),
            )
            return {"id": cur.lastrowid, "email": email, "name": name}
        except sqlite3.IntegrityError:
            return None


def get_user_by_email(email: str) -> dict | None:
    with get_db() as conn:
        row = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        return dict(row) if row else None


def get_user_by_id(user_id: int) -> dict | None:
    with get_db() as conn:
        row = conn.execute("SELECT id, email, name, created_at FROM users WHERE id = ?", (user_id,)).fetchone()
        return dict(row) if row else None


# ── Password Reset ──────────────────────────────────────────────────────────

def create_reset_token(email: str) -> str | None:
    user = get_user_by_email(email)
    if not user:
        return None
    raw_token = secrets.token_hex(32)
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    expires_at = (datetime.now(timezone.utc) + timedelta(minutes=15)).isoformat()
    with get_db() as conn:
        conn.execute(
            "DELETE FROM reset_tokens WHERE user_id = ?", (user["id"],)
        )
        conn.execute(
            "INSERT INTO reset_tokens (user_id, token_hash, expires_at) VALUES (?, ?, ?)",
            (user["id"], token_hash, expires_at),
        )
    return raw_token


def get_valid_token(raw_token: str) -> dict | None:
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    with get_db() as conn:
        row = conn.execute(
            """SELECT rt.*, u.email FROM reset_tokens rt
               JOIN users u ON u.id = rt.user_id
               WHERE rt.token_hash = ? AND rt.used = 0 AND rt.expires_at > datetime('now')""",
            (token_hash,),
        ).fetchone()
        return dict(row) if row else None


def mark_token_used(token_id: int) -> None:
    with get_db() as conn:
        conn.execute("UPDATE reset_tokens SET used = 1 WHERE id = ?", (token_id,))


def update_password(user_id: int, password_hash: str) -> None:
    with get_db() as conn:
        conn.execute("UPDATE users SET password_hash = ? WHERE id = ?", (password_hash, user_id))


# ── API Keys ────────────────────────────────────────────────────────────────

def save_api_keys(user_id: int, keys: dict) -> None:
    with get_db() as conn:
        for provider, api_key in keys.items():
            conn.execute(
                """INSERT INTO api_keys (user_id, provider, api_key)
                   VALUES (?, ?, ?)
                   ON CONFLICT(user_id, provider) DO UPDATE SET api_key = excluded.api_key""",
                (user_id, provider, api_key),
            )


def get_user_settings(user_id: int) -> dict:
    with get_db() as conn:
        row = conn.execute(
            "SELECT use_default_api FROM user_settings WHERE user_id = ?", (user_id,)
        ).fetchone()
        if not row:
            conn.execute("INSERT OR IGNORE INTO user_settings (user_id, use_default_api) VALUES (?, 1)", (user_id,))
            return {"use_default_api": True}
        return {"use_default_api": bool(row["use_default_api"])}


def save_user_settings(user_id: int, settings: dict) -> None:
    use_default = settings.get("use_default_api", True)
    with get_db() as conn:
        conn.execute(
            """INSERT INTO user_settings (user_id, use_default_api)
               VALUES (?, ?)
               ON CONFLICT(user_id) DO UPDATE SET use_default_api = excluded.use_default_api""",
            (user_id, 1 if use_default else 0),
        )


def get_api_keys(user_id: int) -> dict:
    with get_db() as conn:
        rows = conn.execute(
            "SELECT provider, api_key FROM api_keys WHERE user_id = ?", (user_id,)
        ).fetchall()
        return {r["provider"]: r["api_key"] for r in rows}


def get_effective_api_keys(user_id: int) -> dict:
    """Return user's API keys. If use_default_api is true, use default NVIDIA key (OpenRouter)."""
    from backend.config import DEFAULT_NVIDIA_KEY
    keys = get_api_keys(user_id)
    settings = get_user_settings(user_id)

    if settings.get("use_default_api", True):
        keys["nvidia"] = DEFAULT_NVIDIA_KEY

    return keys


# ── CV ──────────────────────────────────────────────────────────────────────

def save_cv(user_id: int, cv_json: str) -> None:
    with get_db() as conn:
        conn.execute(
            """INSERT INTO user_cv (user_id, cv_json)
               VALUES (?, ?)
               ON CONFLICT(user_id) DO UPDATE SET cv_json = excluded.cv_json, updated_at = datetime('now')""",
            (user_id, cv_json),
        )


def get_cv(user_id: int) -> str | None:
    with get_db() as conn:
        row = conn.execute(
            "SELECT cv_json FROM user_cv WHERE user_id = ?", (user_id,)
        ).fetchone()
        return row["cv_json"] if row else None


def get_cv_default() -> dict:
    return {
        "personal_info": {"name": "", "email": "", "phone": "", "location": "", "linkedin": "", "website": ""},
        "professional_summary": "", "skills": [], "experience": [], "education": [],
        "certifications": [], "languages": [], "projects": [], "publications": [],
        "volunteer_experience": [], "professional_memberships": [],
    }


# ── Global Jobs Pool ────────────────────────────────────────────────────────

def save_global_jobs(jobs: list[dict]) -> int:
    saved = 0
    with get_db() as conn:
        for job in jobs:
            try:
                category = classify_job_title(job.get("title", ""), job.get("description", ""))
                is_graduate = _is_graduate_job(job.get("title", ""), job.get("description", ""))
                has_full_info = 1 if (
                    len(job.get("description", "") or "") > 100
                    and job.get("company", "")
                ) else 0
                conn.execute(
                    """INSERT OR IGNORE INTO global_jobs
                       (title, company, location, description, url, source, board_category,
                        job_category, posted_date, has_full_info, is_graduate)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        job.get("title", ""),
                        job.get("company", ""),
                        job.get("location", ""),
                        (job.get("description", "") or "")[:2000],
                        job.get("url", ""),
                        job.get("source", ""),
                        job.get("category", ""),
                        category,
                        job.get("posted_date", ""),
                        has_full_info,
                        is_graduate,
                    ),
                )
                if conn.total_changes > 0:
                    saved += 1
            except Exception as e:
                pass
    return saved


def classify_job_title(title: str, description: str = "") -> str:
    text = f"{title} {description}".lower()
    from backend.config import JOB_CATEGORIES
    best_cat = "other"
    best_score = 0
    for slug, info in JOB_CATEGORIES.items():
        score = 0
        for kw in info["keywords"]:
            if kw in text:
                score += text.count(kw)
        if score > best_score:
            best_score = score
            best_cat = slug
    return best_cat


def _is_graduate_job(title: str, description: str) -> int:
    text = f"{title} {description}".lower()
    grad_kw = ["graduate", "entry level", "entry-level", "junior", "intern", "trainee",
               "recent graduate", "graduate trainee", "nysc", "fresh graduate", "no experience"]
    for kw in grad_kw:
        if kw in text:
            return 1
    return 0


def get_global_jobs(
    category: str = "",
    source: str = "",
    search: str = "",
    is_graduate: bool = None,
    limit: int = 200,
    offset: int = 0,
    sort: str = "date",
):
    with get_db() as conn:
        conditions = ["is_active = 1"]
        params = []
        if category:
            conditions.append("job_category = ?")
            params.append(category)
        if source:
            conditions.append("source = ?")
            params.append(source)
        if search:
            conditions.append("(title LIKE ? OR company LIKE ? OR description LIKE ?)")
            search_param = f"%{search}%"
            params.extend([search_param, search_param, search_param])
        if is_graduate is not None:
            conditions.append("is_graduate = ?")
            params.append(1 if is_graduate else 0)

        order = "date_found DESC, posted_date DESC" if sort == "date" else "match_score DESC, date_found DESC"
        query = f"SELECT * FROM global_jobs WHERE {' AND '.join(conditions)} ORDER BY {order} LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        rows = conn.execute(query, params).fetchall()
        total = conn.execute(
            f"SELECT COUNT(*) FROM global_jobs WHERE {' AND '.join(conditions)}",
            params[:-2] if params[:-2] else [],
        ).fetchone()[0]
        return [dict(r) for r in rows], total


def get_global_job(job_id: int):
    with get_db() as conn:
        row = conn.execute("SELECT * FROM global_jobs WHERE id = ?", (job_id,)).fetchone()
        return dict(row) if row else None


# ── User-Job Links ──────────────────────────────────────────────────────────

def link_user_job(user_id: int, job_id: int) -> bool:
    with get_db() as conn:
        try:
            conn.execute(
                "INSERT OR IGNORE INTO user_job_links (user_id, job_id) VALUES (?, ?)",
                (user_id, job_id),
            )
            return True
        except Exception:
            return False


def get_user_job_link(user_id: int, job_id: int):
    with get_db() as conn:
        row = conn.execute(
            """SELECT ujl.*, gj.title, gj.company, gj.description, gj.url, gj.source,
                      gj.job_category, gj.posted_date, gj.match_score
               FROM user_job_links ujl
               JOIN global_jobs gj ON gj.id = ujl.job_id
               WHERE ujl.user_id = ? AND ujl.job_id = ?""",
            (user_id, job_id),
        ).fetchone()
        return dict(row) if row else None


def get_user_linked_jobs(user_id: int, limit: int = 50):
    with get_db() as conn:
        rows = conn.execute(
            """SELECT ujl.*, gj.title, gj.company, gj.description, gj.url, gj.source,
                      gj.job_category, gj.posted_date, gj.match_score
               FROM user_job_links ujl
               JOIN global_jobs gj ON gj.id = ujl.job_id
               WHERE ujl.user_id = ?
               ORDER BY ujl.created_at DESC LIMIT ?""",
            (user_id, limit),
        ).fetchall()
        return [dict(r) for r in rows]


def update_link_tailoring(user_id: int, job_id: int, cv_path: str, cover_path: str):
    with get_db() as conn:
        conn.execute(
            """UPDATE user_job_links SET
               tailored_cv_path = ?, tailored_cover_path = ?, status = 'tailored'
               WHERE user_id = ? AND job_id = ?""",
            (cv_path, cover_path, user_id, job_id),
        )


# ── Categories ──────────────────────────────────────────────────────────────

def get_categories():
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM job_categories ORDER BY name").fetchall()
        return [dict(r) for r in rows]


# ── Stats ───────────────────────────────────────────────────────────────────

def get_global_stats():
    with get_db() as conn:
        total = conn.execute("SELECT COUNT(*) FROM global_jobs WHERE is_active = 1").fetchone()[0]
        by_cat = conn.execute(
            "SELECT job_category, COUNT(*) as cnt FROM global_jobs WHERE is_active = 1 GROUP BY job_category ORDER BY cnt DESC"
        ).fetchall()
        by_source = conn.execute(
            "SELECT source, COUNT(*) as cnt FROM global_jobs WHERE is_active = 1 GROUP BY source ORDER BY cnt DESC"
        ).fetchall()
        recent = conn.execute(
            "SELECT COUNT(*) FROM global_jobs WHERE is_active = 1 AND date_found >= datetime('now', '-1 day')"
        ).fetchone()[0]

        last_found = conn.execute(
            "SELECT MAX(date_found) as last_scraped FROM global_jobs"
        ).fetchone()["last_scraped"]

        new_since_midnight = conn.execute(
            "SELECT COUNT(*) FROM global_jobs WHERE is_active = 1 AND date_found >= datetime('now', 'start of day')"
        ).fetchone()[0]

        new_since_yesterday = conn.execute(
            "SELECT COUNT(*) FROM global_jobs WHERE is_active = 1 AND date_found >= datetime('now', '-1 day')"
        ).fetchone()[0]

        return {
            "total": total,
            "by_category": {r["job_category"]: r["cnt"] for r in by_cat},
            "by_source": {r["source"]: r["cnt"] for r in by_source},
            "recent_24h": recent,
            "last_scraped": last_found,
            "new_today": new_since_midnight,
            "new_24h": new_since_yesterday,
        }


# ── Cleanup (for cron) ──────────────────────────────────────────────────────

def deactivate_old_jobs(days: int = 7):
    with get_db() as conn:
        conn.execute(
            "UPDATE global_jobs SET is_active = 0 WHERE date_found < datetime('now', ?)",
            (f"-{days} days",),
        )
        removed = conn.total_changes
        # Also clean orphaned user_job_links
        conn.execute(
            "DELETE FROM user_job_links WHERE job_id IN (SELECT id FROM global_jobs WHERE is_active = 0)"
        )
        return removed
