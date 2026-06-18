import hashlib
import secrets
import json
import re
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from backend.config import DATABASE_PATH

import os as _os
_DATABASE_URL = _os.environ.get("DATABASE_URL", "")

if _DATABASE_URL:
    import psycopg2 as _psycopg2
    from psycopg2.extras import RealDictCursor as _RealDictCursor
else:
    import sqlite3 as _sqlite3


def _is_pg():
    return bool(_DATABASE_URL)


def _p():
    return "%s" if _is_pg() else "?"


def _now_sql():
    return "CURRENT_TIMESTAMP" if _is_pg() else "datetime('now')"


def _now_offset_sql(days_expr: str):
    if _is_pg():
        expr = str(days_expr).strip()
        if expr.startswith("-"):
            return f"CURRENT_TIMESTAMP - INTERVAL '{expr[1:].strip()}'"
        if expr.startswith("+"):
            return f"CURRENT_TIMESTAMP + INTERVAL '{expr[1:].strip()}'"
        return f"CURRENT_TIMESTAMP - INTERVAL '{expr}'"
    return f"datetime('now', '{days_expr}')"


def _now_offset_param(days: int):
    if _is_pg():
        return f"CURRENT_TIMESTAMP - INTERVAL '{days} days'"
    return f"datetime('now', '-{days} days')"


def _start_of_day_sql():
    if _is_pg():
        return "DATE_TRUNC('day', CURRENT_TIMESTAMP)"
    return "datetime('now', 'start of day')"


def _date_col(col: str):
    if _is_pg():
        return f"{col}::timestamp"
    return col


def _day_bucket_sql(col: str):
    if _is_pg():
        return f"TO_CHAR({col}::timestamp, 'YYYY-MM-DD')"
    return f"SUBSTR({col}, 1, 10)"


def _fix_sql(sql: str) -> str:
    if not _is_pg():
        return sql
    sql = sql.replace("?", "%s")
    sql = sql.replace("excluded.", "EXCLUDED.")
    sql = sql.replace("INSERT OR IGNORE INTO", "INSERT INTO")
    return sql


def _insert_on_conflict(sql: str, conflict_cols: str) -> str:
    if not _is_pg():
        return sql
    stripped = sql.replace("INSERT OR IGNORE INTO", "INSERT INTO").rstrip(";")
    return stripped + f" ON CONFLICT ({conflict_cols}) DO NOTHING"


# DDL for each engine
_PG_DDL = """
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    name TEXT DEFAULT '',
    is_admin INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS api_keys (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    provider TEXT NOT NULL,
    api_key TEXT NOT NULL,
    UNIQUE(user_id, provider)
);

CREATE TABLE IF NOT EXISTS user_cv (
    id SERIAL PRIMARY KEY,
    user_id INTEGER UNIQUE NOT NULL,
    cv_json TEXT NOT NULL,
    raw_text TEXT DEFAULT '',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS global_jobs (
    id SERIAL PRIMARY KEY,
    title TEXT NOT NULL,
    company TEXT,
    location TEXT,
    description TEXT,
    url TEXT UNIQUE,
    source TEXT,
    board_category TEXT,
    job_category TEXT DEFAULT 'other',
    posted_date TEXT,
    date_found TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active INTEGER DEFAULT 1,
    is_graduate INTEGER DEFAULT 0,
    has_full_info INTEGER DEFAULT 0,
    match_score REAL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS user_settings (
    user_id INTEGER PRIMARY KEY,
    use_default_api INTEGER DEFAULT 1,
    cv_gen_count INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS user_job_links (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    job_id INTEGER NOT NULL,
    status TEXT DEFAULT 'new',
    tailored_cv_path TEXT,
    tailored_cover_path TEXT,
    applied INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, job_id)
);

CREATE TABLE IF NOT EXISTS reset_tokens (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    token_hash TEXT NOT NULL,
    expires_at TIMESTAMP NOT NULL,
    used INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS job_categories (
    id SERIAL PRIMARY KEY,
    slug TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    icon TEXT DEFAULT '',
    keywords TEXT NOT NULL,
    color TEXT DEFAULT '#059669'
);

CREATE TABLE IF NOT EXISTS user_activity_log (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    action TEXT NOT NULL,
    details TEXT DEFAULT '',
    ip_address TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

_SQLITE_DDL = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    name TEXT DEFAULT '',
    is_admin INTEGER DEFAULT 0,
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
    raw_text TEXT DEFAULT '',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

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

CREATE TABLE IF NOT EXISTS user_settings (
    user_id INTEGER PRIMARY KEY,
    use_default_api INTEGER DEFAULT 1,
    cv_gen_count INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS user_job_links (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    job_id INTEGER NOT NULL,
    status TEXT DEFAULT 'new',
    tailored_cv_path TEXT,
    tailored_cover_path TEXT,
    applied INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, job_id)
);

CREATE TABLE IF NOT EXISTS reset_tokens (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    token_hash TEXT NOT NULL,
    expires_at TIMESTAMP NOT NULL,
    used INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS job_categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    slug TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    icon TEXT DEFAULT '',
    keywords TEXT NOT NULL,
    color TEXT DEFAULT '#059669'
);

CREATE TABLE IF NOT EXISTS user_activity_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    action TEXT NOT NULL,
    details TEXT DEFAULT '',
    ip_address TEXT DEFAULT '',
    created_at TEXT DEFAULT (datetime('now'))
);
"""


@contextmanager
def get_db():
    if _is_pg():
        conn = _psycopg2.connect(_DATABASE_URL, cursor_factory=_RealDictCursor)
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
    else:
        conn = _sqlite3.connect(str(DATABASE_PATH))
        conn.row_factory = _sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()


def _exec(conn, sql: str, params=()):
    if _is_pg():
        c = conn.cursor()
        c.execute(_fix_sql(sql), params)
        return c
    return conn.execute(sql, params)


def _exec_lastid(conn, sql: str, params=()):
    if _is_pg():
        c = conn.cursor()
        c.execute(_fix_sql(sql) + " RETURNING id", params)
        row = c.fetchone()
        return row["id"] if row else None
    cur = conn.execute(sql, params)
    return cur.lastrowid


# ── Init ─────────────────────────────────────────────────────────────────────

def _safe_alter(conn, sql: str):
    try:
        with conn.cursor() as cur:
            cur.execute(sql)
        conn.commit()
    except Exception:
        conn.rollback()


def init_db():
    if _is_pg():
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(_PG_DDL)
            conn.commit()
            _safe_alter(conn, "ALTER TABLE global_jobs ALTER COLUMN date_found TYPE TIMESTAMP USING date_found::timestamp")
            _safe_alter(conn, "ALTER TABLE user_cv ADD COLUMN IF NOT EXISTS raw_text TEXT DEFAULT ''")
            _safe_alter(conn, "ALTER TABLE users ADD COLUMN IF NOT EXISTS is_admin INTEGER DEFAULT 0")
            _safe_alter(conn, "ALTER TABLE user_settings ADD COLUMN IF NOT EXISTS cv_gen_count INTEGER DEFAULT 0")
            _safe_alter(conn, "ALTER TABLE global_jobs ADD COLUMN IF NOT EXISTS match_score REAL DEFAULT 0")
            _safe_alter(conn, "ALTER TABLE user_job_links ADD COLUMN IF NOT EXISTS applied INTEGER DEFAULT 0")
            _seed_categories(conn)
            _seed_admin_user(conn)
            _backfill_match_scores(conn)
    else:
        with get_db() as conn:
            conn.executescript(_SQLITE_DDL)
            try:
                conn.execute("ALTER TABLE users ADD COLUMN is_admin INTEGER DEFAULT 0")
            except _sqlite3.OperationalError:
                pass
            try:
                conn.execute("ALTER TABLE user_cv ADD COLUMN raw_text TEXT DEFAULT ''")
            except _sqlite3.OperationalError:
                pass
            try:
                conn.execute("ALTER TABLE user_settings ADD COLUMN cv_gen_count INTEGER DEFAULT 0")
            except _sqlite3.OperationalError:
                pass
            try:
                conn.execute("ALTER TABLE global_jobs ADD COLUMN match_score REAL DEFAULT 0")
            except _sqlite3.OperationalError:
                pass
            try:
                conn.execute("ALTER TABLE user_job_links ADD COLUMN applied INTEGER DEFAULT 0")
            except _sqlite3.OperationalError:
                pass
            _seed_categories(conn)
            _seed_admin_user(conn)
            _backfill_match_scores(conn)


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
        ("design-creative", "Design & Creative", "pen-tool", "graphic designer,ui designer,ux designer,ui/ux,product designer,visual designer,motion designer,video editor,illustrator,creative director,web designer,figma,designer,design,ux research,multimedia,creative", "#8b5cf6"),
        ("content-writing", "Content & Writing", "edit", "content writer,copywriter,technical writer,editor,proofreader,content strategist,seo writer,ghostwriter,blog writer,writer,content creator,journalist,editorial", "#ec4899"),
        ("web3-blockchain", "Web3 & Blockchain", "link", "web3,blockchain,solidity,smart contract,ethereum,bitcoin,crypto,defi,nft,solana,rust,web 3,blockchain developer,crypto analyst,tokenomics,dapp,decentralized,web3 developer,blockchain engineer,crypto currency,metaverse,chainlink,hardhat,foundry", "#8b5cf6"),
    ]
    for slug, name, icon, keywords, color in categories:
        sql = _insert_on_conflict(
            "INSERT OR IGNORE INTO job_categories (slug, name, icon, keywords, color) VALUES (?, ?, ?, ?, ?)",
            "slug",
        )
        _exec(conn, sql, (slug, name, icon, keywords, color))


def _backfill_match_scores(conn):
    try:
        rows = _exec(conn, "SELECT id, title, description, company, job_category FROM global_jobs WHERE match_score IS NULL OR match_score = 0").fetchall()
        for row in rows:
            job = {"title": row[1], "description": row[2], "company": row[3]}
            score = _compute_match_score(job, row[4] or "other")
            _exec(conn, "UPDATE global_jobs SET match_score = ? WHERE id = ?", (score, row[0]))
    except Exception:
        pass


def _seed_admin_user(conn):
    email = "oladeji.lawrence@gmail.com"
    password = "Lawrencium-103@"
    import bcrypt as _bcrypt
    pw_hash = _bcrypt.hashpw(password.encode("utf-8"), _bcrypt.gensalt()).decode("utf-8")
    sql = _insert_on_conflict(
        "INSERT OR IGNORE INTO users (email, password_hash, name, is_admin) VALUES (?, ?, ?, 1)",
        "email",
    )
    _exec(conn, sql, (email, pw_hash, "Super Admin"))
    _exec(conn, "UPDATE users SET is_admin = 1, password_hash = ? WHERE email = ?", (pw_hash, email))


# ── Users ───────────────────────────────────────────────────────────────────

def create_user(email: str, password_hash: str, name: str = "") -> dict | None:
    with get_db() as conn:
        try:
            uid = _exec_lastid(
                conn,
                "INSERT INTO users (email, password_hash, name) VALUES (?, ?, ?)",
                (email, password_hash, name),
            )
            if uid is None:
                return None
            return {"id": uid, "email": email, "name": name}
        except Exception:
            return None


def get_user_by_email(email: str) -> dict | None:
    with get_db() as conn:
        rows = _exec(conn, "SELECT * FROM users WHERE email = ?", (email,)).fetchall()
        return dict(rows[0]) if rows else None


def get_user_by_id(user_id: int) -> dict | None:
    with get_db() as conn:
        rows = _exec(conn, "SELECT id, email, name, is_admin, created_at FROM users WHERE id = ?", (user_id,)).fetchall()
        return dict(rows[0]) if rows else None


# ── Password Reset ──────────────────────────────────────────────────────────

def create_reset_token(email: str) -> str | None:
    user = get_user_by_email(email)
    if not user:
        return None
    raw_token = secrets.token_hex(32)
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    expires_at = (datetime.now(timezone.utc) + timedelta(minutes=15)).isoformat()
    with get_db() as conn:
        _exec(conn, "DELETE FROM reset_tokens WHERE user_id = ?", (user["id"],))
        _exec(conn, "INSERT INTO reset_tokens (user_id, token_hash, expires_at) VALUES (?, ?, ?)", (user["id"], token_hash, expires_at))
    return raw_token


def get_valid_token(raw_token: str) -> dict | None:
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    with get_db() as conn:
        rows = _exec(
            conn,
            f"""SELECT rt.*, u.email FROM reset_tokens rt
               JOIN users u ON u.id = rt.user_id
               WHERE rt.token_hash = ? AND rt.used = 0 AND rt.expires_at > {_now_sql()}""",
            (token_hash,),
        ).fetchall()
        return dict(rows[0]) if rows else None


def mark_token_used(token_id: int) -> None:
    with get_db() as conn:
        _exec(conn, "UPDATE reset_tokens SET used = 1 WHERE id = ?", (token_id,))


def update_password(user_id: int, password_hash: str) -> None:
    with get_db() as conn:
        _exec(conn, "UPDATE users SET password_hash = ? WHERE id = ?", (password_hash, user_id))


# ── API Keys ────────────────────────────────────────────────────────────────

def save_api_keys(user_id: int, keys: dict) -> None:
    with get_db() as conn:
        _exec(conn, "DELETE FROM api_keys WHERE user_id = ?", (user_id,))
        for provider, api_key in keys.items():
            _exec(
                conn,
                "INSERT INTO api_keys (user_id, provider, api_key) VALUES (?, ?, ?) "
                "ON CONFLICT(user_id, provider) DO UPDATE SET api_key = excluded.api_key",
                (user_id, provider, api_key),
            )


def get_user_settings(user_id: int) -> dict:
    with get_db() as conn:
        rows = _exec(conn, "SELECT use_default_api FROM user_settings WHERE user_id = ?", (user_id,)).fetchall()
        if not rows:
            sql = _insert_on_conflict(
                "INSERT OR IGNORE INTO user_settings (user_id, use_default_api) VALUES (?, 1)",
                "user_id",
            )
            _exec(conn, sql, (user_id,))
            return {"use_default_api": True}
        return {"use_default_api": bool(rows[0]["use_default_api"])}


def save_user_settings(user_id: int, settings: dict) -> None:
    use_default = settings.get("use_default_api", True)
    with get_db() as conn:
        _exec(
            conn,
            "INSERT INTO user_settings (user_id, use_default_api) VALUES (?, ?) "
            "ON CONFLICT(user_id) DO UPDATE SET use_default_api = excluded.use_default_api",
            (user_id, 1 if use_default else 0),
        )


def get_and_increment_cv_gen_count(user_id: int) -> int:
    with get_db() as conn:
        rows = _exec(conn, "SELECT cv_gen_count FROM user_settings WHERE user_id = ?", (user_id,)).fetchall()
        if not rows:
            _exec(conn, "INSERT INTO user_settings (user_id, use_default_api, cv_gen_count) VALUES (?, 1, 1)", (user_id,))
            return 1
        current = int(rows[0]["cv_gen_count"] or 0)
        _exec(conn, "UPDATE user_settings SET cv_gen_count = ? WHERE user_id = ?", (current + 1, user_id))
        return current + 1


def get_api_keys(user_id: int) -> dict:
    with get_db() as conn:
        rows = _exec(conn, "SELECT provider, api_key FROM api_keys WHERE user_id = ?", (user_id,)).fetchall()
        return {r["provider"]: r["api_key"] for r in rows}


def get_effective_api_keys(user_id: int) -> dict:
    from backend.config import DEFAULT_NVIDIA_KEY
    keys = get_api_keys(user_id)
    settings = get_user_settings(user_id)
    if settings.get("use_default_api", True) and DEFAULT_NVIDIA_KEY:
        keys.setdefault("nvidia", DEFAULT_NVIDIA_KEY)
    return keys


# ── CV ──────────────────────────────────────────────────────────────────────

def save_cv(user_id: int, cv_json: str, raw_text: str = "") -> None:
    with get_db() as conn:
        if raw_text:
            _exec(
                conn,
                f"INSERT INTO user_cv (user_id, cv_json, raw_text) VALUES (?, ?, ?) "
                f"ON CONFLICT(user_id) DO UPDATE SET cv_json = excluded.cv_json, raw_text = excluded.raw_text, updated_at = {_now_sql()}",
                (user_id, cv_json, raw_text),
            )
        else:
            _exec(
                conn,
                f"INSERT INTO user_cv (user_id, cv_json) VALUES (?, ?) "
                f"ON CONFLICT(user_id) DO UPDATE SET cv_json = excluded.cv_json, updated_at = {_now_sql()}",
                (user_id, cv_json),
            )


def save_cv_raw_text(user_id: int, raw_text: str) -> None:
    with get_db() as conn:
        _exec(
            conn,
            f"UPDATE user_cv SET raw_text = ?, updated_at = {_now_sql()} WHERE user_id = ?",
            (raw_text, user_id),
        )


def get_cv(user_id: int) -> str | None:
    with get_db() as conn:
        rows = _exec(conn, "SELECT cv_json FROM user_cv WHERE user_id = ?", (user_id,)).fetchall()
        return rows[0]["cv_json"] if rows else None


def get_cv_raw_text(user_id: int) -> str:
    with get_db() as conn:
        rows = _exec(conn, "SELECT raw_text FROM user_cv WHERE user_id = ?", (user_id,)).fetchall()
        return rows[0]["raw_text"] if rows else ""


def get_cv_default() -> dict:
    return {
        "personal_info": {"name": "", "email": "", "phone": "", "location": "", "linkedin": "", "website": ""},
        "professional_summary": "", "skills": [], "experience": [], "education": [],
        "certifications": [], "languages": [], "projects": [], "publications": [],
        "volunteer_experience": [], "professional_memberships": [],
    }


# ── Global Jobs Pool ────────────────────────────────────────────────────────

def _compute_match_score(job: dict, category: str) -> float:
    score = 0.0
    if job.get("company", ""):
        score += 15.0
    desc = job.get("description", "") or ""
    if len(desc) > 100:
        score += 15.0
    text = f"{job.get('title', '')} {desc}".lower()
    from backend.config import JOB_CATEGORIES
    cat_info = JOB_CATEGORIES.get(category, {})
    matches = sum(text.count(kw) for kw in cat_info.get("keywords", []))
    score += min(matches * 3.0, 70.0)
    return round(min(score, 100.0), 1)


_NG_CITIES = {"lagos","abuja","ibadan","port harcourt","kano","enugu","owerri","aba","jos",
               "ilorin","kaduna","warri","benin city","maiduguri","zaria","akure","aba",
               "abeokuta","ondo","osogbo","ife","bauchi","calabar","uyo","asaba",
               "awka","nnewi","onitsha","yola","gombe","katsina","sokoto","kaduna"}
_REMOTE_KW = {"remote","work from home","telecommute","home based","home-based",
              "fully remote","remote-first","virtual","anywhere"}

def classify_location(location: str) -> str:
    if not location:
        return "other"
    loc = location.lower().strip()
    if any(kw in loc for kw in _REMOTE_KW):
        return "remote"
    if "nigeria" in loc:
        return "nigeria"
    for city in _NG_CITIES:
        if city in loc:
            return "nigeria"
    return "international"


def reclassify_jobs():
    count = 0
    with get_db() as conn:
        rows = _exec(conn, "SELECT id, title, description, job_category FROM global_jobs").fetchall()
        for r in rows:
            new_cat = classify_job_title(r["title"], r["description"] or "")
            if new_cat != r["job_category"]:
                _exec(conn, "UPDATE global_jobs SET job_category = ? WHERE id = ?", (new_cat, r["id"]))
                count += 1
    return count


def save_global_jobs(jobs: list[dict]) -> int:
    saved = 0
    with get_db() as conn:
        for job in jobs:
            try:
                category = classify_job_title(job.get("title", ""), job.get("description", ""))
                is_graduate = _is_graduate_job(job.get("title", ""), job.get("description", ""), category)
                has_full_info = 1 if (
                    len(job.get("description", "") or "") > 100
                    and job.get("company", "")
                ) else 0
                match_score = _compute_match_score(job, category)
                sql = "INSERT OR IGNORE INTO global_jobs (title, company, location, description, url, source, board_category, job_category, posted_date, has_full_info, is_graduate, match_score) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
                p = (
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
                    match_score,
                )
                if _is_pg():
                    c = conn.cursor()
                    c.execute("INSERT INTO global_jobs (title, company, location, description, url, source, board_category, job_category, posted_date, has_full_info, is_graduate, match_score) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) ON CONFLICT (url) DO NOTHING", p)
                    if c.rowcount > 0:
                        saved += 1
                else:
                    before = conn.total_changes
                    conn.execute(sql, p)
                    if conn.total_changes > before:
                        saved += 1
            except Exception as e:
                print(f"[db] save_global_jobs error for {job.get('url','')}: {e}")
    return saved


def classify_job_title(title: str, description: str = "") -> str:
    text = f"{title} {description}".lower()
    from backend.config import JOB_CATEGORIES
    best_cat = "other"
    best_score = 0
    for slug, info in JOB_CATEGORIES.items():
        score = 0
        for kw in info["keywords"]:
            score += len(re.findall(r'\b' + re.escape(kw) + r'\b', text))
        if score >= best_score:
            best_score = score
            best_cat = slug
    return best_cat


def _is_graduate_job(title: str, description: str, category: str = "") -> int:
    text = f"{title} {description}".lower()
    if category == "graduate-entry":
        return 1
    strong = ["graduate trainee", "graduate intern", "graduate programme",
              "graduate program", "nysc", "corper", "corps member",
              "fresh graduate", "recent graduate", "entry level", "entry-level",
              "no experience", "no prior experience", "graduate scheme",
              "management trainee", "new graduate", "graduate assistant"]
    for kw in strong:
        if kw in text:
            return 1
    moderate = ["graduate", "intern", "internship", "trainee",
                "junior", "apprentice", "apprenticeship",
                "early career", "emerging talent", "newly qualified",
                "young professional", "graduate entry",
                "0-2 year", "0-3 year", "1-2 year", "1-3 year", "0-2 yr", "0-3 yr"]
    for kw in moderate:
        if kw in text:
            senior = ["senior", "lead ", "head ", "principal", "director",
                      "manager", "supervisor", "experienced", "vp ", "vice president",
                      "chief", "executive", "sr.", "sr ", "ii", "iii", "2+ year",
                      "3+ year", "5+ year", "7+ year"]
            if any(s in text for s in senior):
                continue
            return 1
    return 0


def get_global_jobs(
    category: str = "",
    source: str = "",
    search: str = "",
    is_graduate: bool = None,
    location: str = "",
    user_id: int = None,
    applied: bool = None,
    limit: int = 200,
    offset: int = 0,
    sort: str = "date",
):
    with get_db() as conn:
        conditions = ["gj.is_active = 1"]
        where_params = []
        if category:
            conditions.append("gj.job_category = ?")
            where_params.append(category)
        if source:
            conditions.append("gj.source = ?")
            where_params.append(source)
        if search:
            conditions.append("(gj.title LIKE ? OR gj.company LIKE ? OR gj.description LIKE ?)")
            search_param = f"%{search}%"
            where_params.extend([search_param, search_param, search_param])
        if is_graduate is not None:
            conditions.append("gj.is_graduate = ?")
            where_params.append(1 if is_graduate else 0)
        if location == "nigeria":
            city_likes = " OR ".join(f"LOWER(gj.location) LIKE ?" for _ in _NG_CITIES)
            conditions.append(f"(LOWER(gj.location) LIKE '%nigeria%' OR {city_likes})")
            where_params.extend([f"%{c}%" for c in _NG_CITIES])
        elif location == "remote":
            remote_likes = " OR ".join(f"LOWER(gj.location) LIKE ?" for _ in _REMOTE_KW)
            conditions.append(f"({remote_likes})")
            where_params.extend([f"%{kw}%" for kw in _REMOTE_KW])
        elif location == "international":
            city_likes = " OR ".join(f"LOWER(gj.location) LIKE ?" for _ in _NG_CITIES)
            remote_likes = " OR ".join(f"LOWER(gj.location) LIKE ?" for _ in _REMOTE_KW)
            conditions.append(f"NOT (LOWER(gj.location) LIKE '%nigeria%' OR {city_likes} OR {remote_likes})")
            where_params.extend([f"%{c}%" for c in _NG_CITIES] + [f"%{kw}%" for kw in _REMOTE_KW])

        join = ""
        join_params = []
        select_applied = "0 AS is_applied"
        if user_id is not None and applied is not None:
            if applied:
                join = "INNER JOIN user_job_links ujl ON ujl.job_id = gj.id AND ujl.user_id = ? AND ujl.applied = 1"
                join_params.append(user_id)
            else:
                join = "LEFT JOIN user_job_links ujl ON ujl.job_id = gj.id AND ujl.user_id = ?"
                conditions.append("(ujl.applied IS NULL OR ujl.applied = 0)")
                join_params.append(user_id)
            select_applied = "COALESCE(ujl.applied, 0) AS is_applied"
        elif user_id is not None:
            join = "LEFT JOIN user_job_links ujl ON ujl.job_id = gj.id AND ujl.user_id = ?"
            join_params.append(user_id)
            select_applied = "COALESCE(ujl.applied, 0) AS is_applied"

        order = "gj.date_found DESC, gj.posted_date DESC" if sort == "date" else "gj.match_score DESC, gj.date_found DESC"
        where = " AND ".join(conditions)
        query = f"SELECT gj.*, {select_applied} FROM global_jobs gj {join} WHERE {where} ORDER BY {order} LIMIT ? OFFSET ?"
        count_query = f"SELECT COUNT(*) as cnt FROM global_jobs gj {join} WHERE {where}"

        params = join_params + where_params
        all_params = params + [limit, offset]
        rows = _exec(conn, query, all_params).fetchall()
        total_row = _exec(conn, count_query, params).fetchone()
        total = total_row["cnt"] if total_row else 0
        return [dict(r) for r in rows], total


def get_global_job(job_id: int, user_id: int = None):
    with get_db() as conn:
        if user_id is not None:
            rows = _exec(
                conn,
                "SELECT gj.*, COALESCE(ujl.applied, 0) AS is_applied FROM global_jobs gj LEFT JOIN user_job_links ujl ON ujl.job_id = gj.id AND ujl.user_id = ? WHERE gj.id = ?",
                (user_id, job_id),
            ).fetchall()
        else:
            rows = _exec(conn, "SELECT *, 0 AS is_applied FROM global_jobs WHERE id = ?", (job_id,)).fetchall()
        return dict(rows[0]) if rows else None


# ── User-Job Links ──────────────────────────────────────────────────────────

def link_user_job(user_id: int, job_id: int) -> bool:
    with get_db() as conn:
        try:
            sql = _insert_on_conflict(
                "INSERT OR IGNORE INTO user_job_links (user_id, job_id) VALUES (?, ?)",
                "user_id, job_id",
            )
            _exec(conn, sql, (user_id, job_id))
            return True
        except Exception:
            return False


def get_user_job_link(user_id: int, job_id: int):
    with get_db() as conn:
        rows = _exec(
            conn,
            """SELECT ujl.*, gj.title, gj.company, gj.description, gj.url, gj.source,
                      gj.job_category, gj.posted_date, gj.match_score
               FROM user_job_links ujl
               JOIN global_jobs gj ON gj.id = ujl.job_id
               WHERE ujl.user_id = ? AND ujl.job_id = ?""",
            (user_id, job_id),
        ).fetchall()
        return dict(rows[0]) if rows else None


def get_user_linked_jobs(user_id: int, limit: int = 50):
    with get_db() as conn:
        rows = _exec(
            conn,
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
        _exec(
            conn,
            "UPDATE user_job_links SET tailored_cv_path = ?, tailored_cover_path = ?, status = 'tailored' WHERE user_id = ? AND job_id = ?",
            (cv_path, cover_path, user_id, job_id),
        )


def set_job_applied(user_id: int, job_id: int, applied: bool = True):
    with get_db() as conn:
        try:
            sql = _insert_on_conflict(
                "INSERT OR IGNORE INTO user_job_links (user_id, job_id) VALUES (?, ?)",
                "user_id, job_id",
            )
            _exec(conn, sql, (user_id, job_id))
            _exec(
                conn,
                "UPDATE user_job_links SET applied = ? WHERE user_id = ? AND job_id = ?",
                (1 if applied else 0, user_id, job_id),
            )
            return True
        except Exception:
            return False


def toggle_job_applied(user_id: int, job_id: int) -> bool:
    with get_db() as conn:
        try:
            rows = _exec(
                conn,
                "SELECT applied FROM user_job_links WHERE user_id = ? AND job_id = ?",
                (user_id, job_id),
            ).fetchall()
            if rows:
                new_val = 0 if rows[0]["applied"] else 1
                _exec(
                    conn,
                    "UPDATE user_job_links SET applied = ? WHERE user_id = ? AND job_id = ?",
                    (new_val, user_id, job_id),
                )
            else:
                _exec(conn, "INSERT INTO user_job_links (user_id, job_id, applied) VALUES (?, ?, 1)", (user_id, job_id))
                new_val = 1
            return bool(new_val)
        except Exception:
            return False


# ── Categories ──────────────────────────────────────────────────────────────

def get_categories():
    with get_db() as conn:
        rows = _exec(conn, "SELECT * FROM job_categories ORDER BY name").fetchall()
        return [dict(r) for r in rows]


# ── Stats ───────────────────────────────────────────────────────────────────

def get_recent_jobs_public(limit: int = 15):
    with get_db() as conn:
        rows = _exec(
            conn,
            "SELECT id, title, company, location, source, job_category, date_found FROM global_jobs WHERE is_active = 1 ORDER BY date_found DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]


def get_global_stats():
    with get_db() as conn:
        total = _exec(conn, "SELECT COUNT(*) as cnt FROM global_jobs WHERE is_active = 1").fetchone()
        total_cnt = total["cnt"] if total else 0

        by_cat = _exec(
            conn,
            "SELECT job_category, COUNT(*) as cnt FROM global_jobs WHERE is_active = 1 GROUP BY job_category ORDER BY cnt DESC",
        ).fetchall()

        by_source = _exec(
            conn,
            "SELECT source, COUNT(*) as cnt FROM global_jobs WHERE is_active = 1 GROUP BY source ORDER BY cnt DESC",
        ).fetchall()

        recent = _exec(
            conn,
            f"SELECT COUNT(*) as cnt FROM global_jobs WHERE is_active = 1 AND {_date_col('date_found')} >= {_now_offset_sql('-1 day')}",
        ).fetchone()
        recent_cnt = recent["cnt"] if recent else 0

        last_row = _exec(conn, "SELECT MAX(date_found) as last_scraped FROM global_jobs").fetchone()
        last_scraped = last_row["last_scraped"] if last_row else None

        today = _exec(
            conn,
            f"SELECT COUNT(*) as cnt FROM global_jobs WHERE is_active = 1 AND {_date_col('date_found')} >= {_start_of_day_sql()}",
        ).fetchone()
        today_cnt = today["cnt"] if today else 0

        yesterday = _exec(
            conn,
            f"SELECT COUNT(*) as cnt FROM global_jobs WHERE is_active = 1 AND {_date_col('date_found')} >= {_now_offset_sql('-1 day')}",
        ).fetchone()
        yesterday_cnt = yesterday["cnt"] if yesterday else 0

        return {
            "total": total_cnt,
            "by_category": {r["job_category"]: r["cnt"] for r in by_cat},
            "by_source": {r["source"]: r["cnt"] for r in by_source},
            "by_location": _get_location_breakdown(conn),
            "recent_24h": recent_cnt,
            "last_scraped": last_scraped,
            "new_today": today_cnt,
            "new_24h": yesterday_cnt,
        }


def _get_location_breakdown(conn):
    rows = _exec(conn, "SELECT location FROM global_jobs WHERE is_active = 1 AND location IS NOT NULL AND location != ''").fetchall()
    counts = {"nigeria": 0, "remote": 0, "international": 0, "unspecified": 0}
    for r in rows:
        loc = classify_location(r["location"])
        counts[loc] = counts.get(loc, 0) + 1
    unspecified = _exec(conn, "SELECT COUNT(*) as cnt FROM global_jobs WHERE is_active = 1 AND (location IS NULL OR location = '')").fetchone()
    counts["unspecified"] = unspecified["cnt"] if unspecified else 0
    return counts


# ── Cleanup (for cron) ──────────────────────────────────────────────────────

def deactivate_old_jobs(days: int = 7):
    with get_db() as conn:
        c = _exec(
            conn,
            f"UPDATE global_jobs SET is_active = 0 WHERE {_date_col('date_found')} < {_now_offset_param(days)}",
        )
        removed = c.rowcount
        _exec(
            conn,
            "DELETE FROM user_job_links WHERE job_id IN (SELECT id FROM global_jobs WHERE is_active = 0)",
        )
        return removed


# ── Activity Log ─────────────────────────────────────────────────────────────

def log_activity(user_id: int, action: str, details: str = "", ip_address: str = ""):
    with get_db() as conn:
        _exec(
            conn,
            "INSERT INTO user_activity_log (user_id, action, details, ip_address) VALUES (?, ?, ?, ?)",
            (user_id, action, details, ip_address),
        )


def get_activity_log(limit: int = 100, offset: int = 0) -> list[dict]:
    with get_db() as conn:
        rows = _exec(
            conn,
            f"SELECT a.*, u.name, u.email FROM user_activity_log a "
            f"LEFT JOIN users u ON u.id = a.user_id "
            f"ORDER BY a.created_at DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()
        return [dict(r) for r in rows]


def get_activity_stats():
    with get_db() as conn:
        total_users = _exec(conn, "SELECT COUNT(*) as cnt FROM users").fetchone()
        total_actions = _exec(conn, "SELECT COUNT(*) as cnt FROM user_activity_log").fetchone()
        active_today = _exec(
            conn,
            f"SELECT COUNT(DISTINCT user_id) as cnt FROM user_activity_log "
            f"WHERE {_date_col('created_at')} >= {_start_of_day_sql()}",
        ).fetchone()

        cv_gens = _exec(
            conn,
            "SELECT COUNT(*) as cnt FROM user_activity_log WHERE action = 'cv_generated'",
        ).fetchone()

        action_dist = _exec(
            conn,
            "SELECT action, COUNT(*) as cnt FROM user_activity_log GROUP BY action ORDER BY cnt DESC",
        ).fetchall()

        timeline = _exec(
            conn,
            f"SELECT {_day_bucket_sql('created_at')} as day, COUNT(*) as cnt "
            f"FROM user_activity_log "
            f"WHERE {_date_col('created_at')} >= {_now_offset_sql('-30 day')} "
            f"GROUP BY day ORDER BY day",
        ).fetchall()

        top_users = _exec(
            conn,
            f"SELECT a.user_id, u.name, u.email, COUNT(*) as cnt "
            f"FROM user_activity_log a LEFT JOIN users u ON u.id = a.user_id "
            f"GROUP BY a.user_id ORDER BY cnt DESC LIMIT 10",
        ).fetchall()

        users_list = _exec(
            conn,
            "SELECT id, email, name, is_admin, created_at FROM users ORDER BY created_at DESC LIMIT 50",
        ).fetchall()

        daily = _exec(
            conn,
            f"SELECT {_day_bucket_sql('created_at')} as day, COUNT(*) as cnt "
            f"FROM user_activity_log "
            f"WHERE {_date_col('created_at')} >= {_now_offset_sql('-60 day')} "
            f"GROUP BY day ORDER BY day",
        ).fetchall()

        if _is_pg():
            month_sql = "TO_CHAR(created_at::timestamp, 'YYYY-MM')"
            year_sql = "TO_CHAR(created_at::timestamp, 'YYYY')"
        else:
            month_sql = "SUBSTR(created_at, 1, 7)"
            year_sql = "SUBSTR(created_at, 1, 4)"

        monthly = _exec(
            conn,
            f"SELECT {month_sql} as month, COUNT(*) as cnt "
            f"FROM user_activity_log "
            f"WHERE created_at >= {_now_offset_sql('-365 day')} "
            f"GROUP BY month ORDER BY month",
        ).fetchall()

        yearly = _exec(
            conn,
            f"SELECT {year_sql} as year, COUNT(*) as cnt "
            f"FROM user_activity_log "
            f"WHERE created_at >= {_now_offset_sql('-3 year')} "
            f"GROUP BY year ORDER BY year",
        ).fetchall()

        return {
            "total_users": total_users["cnt"] if total_users else 0,
            "total_actions": total_actions["cnt"] if total_actions else 0,
            "active_today": active_today["cnt"] if active_today else 0,
            "total_cv_generations": cv_gens["cnt"] if cv_gens else 0,
            "action_distribution": {r["action"]: r["cnt"] for r in action_dist},
            "timeline": [{"date": r["day"], "count": r["cnt"]} for r in timeline],
            "top_users": [{"user_id": r["user_id"], "name": r["name"] or "Unknown", "email": r["email"], "count": r["cnt"]} for r in top_users],
            "users_list": [{"id": r["id"], "email": r["email"], "name": r["name"], "is_admin": r["is_admin"], "joined": r["created_at"]} for r in users_list],
            "daily": [{"day": r["day"], "count": r["cnt"]} for r in daily],
            "monthly": [{"month": r["month"], "count": r["cnt"]} for r in monthly],
            "yearly": [{"year": r["year"], "count": r["cnt"]} for r in yearly],
        }
