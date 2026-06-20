# Joblin — Product Requirements Document

**Version:** 2.0.0  
**Date:** June 18, 2026  

---

## 1. Product Overview

### 1.1 Vision

Joblin is a job discovery and AI-powered CV tailoring platform for Nigerian job seekers, remote workers, and professionals in NGO, high-impact, and Web3 sectors. It automates job hunting — finding relevant roles and crafting job-specific application documents — using scheduled web scraping, LLM-powered CV generation, and multi-format document export.

### 1.2 Problem Statement

- Nigerian job seekers manually browse 10+ job boards daily, leading to missed opportunities and fatigue.
- Writing a tailored CV and cover letter takes 30-60 minutes per application; most applicants send generic documents.
- Job categories span local, NGO, remote, international, Web3, and ATS-tracked roles — no single platform aggregates these.
- Applicants lack real-time job matching and quality feedback on their CVs.

### 1.3 Target Users

| Persona | Description |
|---------|-------------|
| Nigerian Graduate | Entry-level/graduate trainee seeking first role; needs CV from scratch |
| Mid-Career Professional | 3-7 years experience in data, M&E, finance, IT; wants tailored CVs per job |
| NGO/Development Worker | Roles at UNICEF, WHO, IRC, Devex; needs international-format CV |
| Remote/International Seeker | Global remote roles; needs international CV with visa/work rights guidance |
| Web3/Blockchain Professional | Smart contract developer, DeFi analyst; niche board seeker |
| Admin (Site Operator) | Monitors scraping health, user activity, system analytics |

---

## 2. Architecture & Tech Stack

### 2.1 System Architecture

```
GitHub Actions (4 workflows)
  │  keep-alive (5min)  scrape-6am  scrape-3pm  cleanup-4am
  ▼
Render (Docker Container)
  ┌────────────────────────────────────┐
  │  FastAPI Backend (uvicorn :8080)    │
  │  ┌──────────┐  ┌────────────────┐  │
  │  │ REST API │  │ APScheduler    │  │
  │  │ 30+ EP   │  │ (2x daily)     │  │
  │  └───┬──────┘  └───────┬────────┘  │
  │      │                 │            │
  │  ┌───▼──────┐  ┌──────▼───────┐   │
  │  │ DB Layer │  │ Scraper     │   │
  │  │psycopg2  │  │ Subsystem   │   │
  │  └───┬──────┘  │ 6 classes   │   │
  │      │         │ 38 boards   │   │
  │      │         └─────────────┘   │
  │      │                           │
  │  ┌───▼──────────────────────┐   │
  │  │ LLM Cascade               │   │
  │  │ OpenRouter → Groq →      │   │
  │  │ Gemini → Gemma →         │   │
  │  │ Rule-based fallback      │   │
  │  └──────────────────────────┘   │
  └──────────┬──────────────────────┘
             │
  ┌──────────▼──────────┐
  │ Neon PostgreSQL      │
  │ (Starter, Oregon)    │
  │ 9 tables, 20 cats   │
  └─────────────────────┘
```

### 2.2 Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend Framework | FastAPI 0.110+ (Python 3.11) |
| ASGI Server | Uvicorn 0.29+, single-worker |
| Database (Prod) | Neon PostgreSQL via psycopg2-binary |
| Database (Dev) | SQLite via sqlite3 |
| Auth | JWT (HS256) + bcrypt (python-jose) |
| AI/LLM | OpenRouter → Groq → Gemini → Gemma (4-provider cascade) |
| Scraping | requests + BeautifulSoup4 + lxml (38 boards) |
| Document Gen | python-docx (DOCX), fpdf2 (PDF), openpyxl (Excel) |
| Scheduling | APScheduler (in-app) + GitHub Actions (external cron) |
| Frontend | Vanilla HTML/CSS/JS (no framework, no build step) |
| Container | Docker (python:3.11-slim), single container |
| Hosting | Render (Starter, Oregon, Docker runtime) |
| CI/CD Cron | 4 GitHub Actions workflows |

### 2.3 Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `PORT` | Yes | `8080` | Uvicorn listen port |
| `DATA_DIR` | Yes | `/data` | Persistent storage root |
| `DATABASE_URL` | Yes (prod) | — | PostgreSQL connection string |
| `JOBLIN_JWT_SECRET` | Yes | auto-generated on Render | HS256 signing key |
| `JOBLIN_CRON_TOKEN` | Optional | empty | Bearer token for cron endpoints |
| `JOBLIN_OPENROUTER_KEY` | Optional | empty | Shared OpenRouter API key |

### 2.4 GitHub Secrets

| Secret | Purpose |
|--------|---------|
| `HF_SPACE_URL` | Deployed app base URL (Render URL; legacy name from HuggingFace) |
| `JOBLIN_CRON_TOKEN` | Shared secret for cron API authentication |

---

## 3. Database Schema

### 3.1 Tables (9 total)

#### `users`
| Column | Type | Constraints |
|--------|------|-------------|
| id | SERIAL/INTEGER | PK, AUTO INCREMENT |
| email | TEXT | UNIQUE, NOT NULL |
| password_hash | TEXT | NOT NULL |
| name | TEXT | DEFAULT '' |
| is_admin | INTEGER | DEFAULT 0 |
| created_at | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP |

#### `user_cv`
| Column | Type | Constraints |
|--------|------|-------------|
| id | SERIAL/INTEGER | PK |
| user_id | INTEGER | UNIQUE, NOT NULL, FK→users |
| cv_json | TEXT | NOT NULL |
| raw_text | TEXT | DEFAULT '' |
| updated_at | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP |

#### `user_settings`
| Column | Type | Constraints |
|--------|------|-------------|
| user_id | INTEGER | PK, FK→users |
| use_default_api | INTEGER | DEFAULT 1 |
| cv_gen_count | INTEGER | DEFAULT 0 |

#### `api_keys`
| Column | Type | Constraints |
|--------|------|-------------|
| id | SERIAL/INTEGER | PK |
| user_id | INTEGER | NOT NULL, FK→users |
| provider | TEXT | NOT NULL (groq/nvidia/gemini) |
| api_key | TEXT | NOT NULL |
| — | — | UNIQUE(user_id, provider) |

#### `global_jobs`
| Column | Type | Constraints |
|--------|------|-------------|
| id | SERIAL/INTEGER | PK |
| title | TEXT | NOT NULL |
| company | TEXT | |
| location | TEXT | |
| description | TEXT | (max 600 chars from scraper) |
| url | TEXT | UNIQUE (dedup key) |
| source | TEXT | Board identifier |
| board_category | TEXT | nigeria/ngo/international/highimpact/web3/ats |
| job_category | TEXT | DEFAULT 'other' (20 categories) |
| posted_date | TEXT | |
| date_found | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP |
| is_active | INTEGER | DEFAULT 1 |
| is_graduate | INTEGER | DEFAULT 0 |
| has_full_info | INTEGER | DEFAULT 0 |
| match_score | REAL | DEFAULT 0 (0-100) |

#### `user_job_links`
| Column | Type | Constraints |
|--------|------|-------------|
| id | SERIAL/INTEGER | PK |
| user_id | INTEGER | NOT NULL, FK→users |
| job_id | INTEGER | NOT NULL, FK→global_jobs |
| status | TEXT | DEFAULT 'new' (new/tailored) |
| tailored_cv_path | TEXT | |
| tailored_cover_path | TEXT | |
| applied | INTEGER | DEFAULT 0 |
| created_at | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP |
| — | — | UNIQUE(user_id, job_id) |

#### `reset_tokens`
| Column | Type | Constraints |
|--------|------|-------------|
| id | SERIAL/INTEGER | PK |
| user_id | INTEGER | NOT NULL, FK→users |
| token_hash | TEXT | NOT NULL (SHA-256) |
| expires_at | TIMESTAMP | NOT NULL (15 min) |
| used | INTEGER | DEFAULT 0 |
| created_at | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP |

#### `job_categories`
| Column | Type | Constraints |
|--------|------|-------------|
| id | SERIAL/INTEGER | PK |
| slug | TEXT | UNIQUE, NOT NULL |
| name | TEXT | NOT NULL |
| icon | TEXT | DEFAULT '' |
| keywords | TEXT | NOT NULL (comma-separated) |
| color | TEXT | DEFAULT '#059669' |

#### `user_activity_log`
| Column | Type | Constraints |
|--------|------|-------------|
| id | SERIAL/INTEGER | PK |
| user_id | INTEGER | NOT NULL |
| action | TEXT | NOT NULL |
| details | TEXT | DEFAULT '' |
| ip_address | TEXT | DEFAULT '' |
| created_at | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP |

### 3.2 Job Category Taxonomy (20 categories)

data-analytics, monitoring-evaluation, ai-machine-learning, software-dev, public-health, graduate-entry, ngo-development, project-management, finance-accounting, admin-operations, human-resources, sales-marketing, customer-service, engineering, procurement-supply, legal-compliance, remote, design-creative, content-writing, web3-blockchain

### 3.3 Dual-Engine Database

- **SQLite (dev):** When `DATABASE_URL` is not set
- **PostgreSQL (prod):** When `DATABASE_URL` is set (psycopg2 + RealDictCursor)
- **Dialect adapters:** Automatic translation of `?` ↔ `%s` placeholders, timestamp functions, INSERT OR IGNORE ↔ ON CONFLICT DO NOTHING, lastrowid ↔ RETURNING id
- **Migrations:** Safe ALTER TABLE ADD COLUMN IF NOT EXISTS on every init

---

## 4. Features

### 4.1 Authentication & User Management

| Feature | Detail |
|---------|--------|
| Registration | Email + password + name. bcrypt hash. Returns JWT. |
| Login | Email + password. bcrypt verify. JWT with is_admin claim. |
| JWT Sessions | HS256 signed, 24h expiry. localStorage `joblin_token`. |
| Auto-logout | 401 responses clear token + redirect to login. |
| Password Reset | 2-step: request token → 15-min SHA-256 hashed token → submit + new password. No email sending — token displayed inline. |
| Admin User | Seeded: `oladeji.lawrence@gmail.com` / `Lawrencium-103@`, is_admin=1 |
| Admin Toggle | localStorage `admin_mode` flag controls `.admin-only` UI visibility. |

### 4.2 CV Management

- **Structured Editor:** Multi-section form (Personal Info, Skills, Experience, Education, Projects, Certifications, Languages, Volunteer, Memberships, Referees)
- **JSON Editor Mode:** Raw JSON editing with validation badges
- **Raw Text Import:** Paste raw text → AI parses → regex fallback extracts name, email, phone, sections
- **Auto-save:** 2-second debounced save to API with visual status indicator
- **Default Template:** Blank CV returned for new users

### 4.3 AI CV Generation (Make CV)

- **Voice Narration:** Web Speech API (en-NG locale, continuous mode)
- **Target Job Tags:** Add/remove multiple target job titles
- **CV Type Toggle:** **Local Nigerian** (+234 phone, NYSC, local certs, referees) / **International** (Remote/Anywhere, US/UK format, visa guidance)
- **Remote Preferences:** Timezone selector, remote checkbox
- **AI Generation:** Sends raw text + targets to LLM cascade → regex fallback
- **Output:** Structured JSON, plain-text preview, DOCX + PDF downloads

### 4.4 Job Scraping (38 Boards)

#### Scraping Infrastructure

| Feature | Detail |
|---------|--------|
| Safe Scraping | 6-UA rotation, 3-8s domain rate limit, circuit breaker (5 fails → exponential backoff up to 80 min) |
| Robots.txt | Fetched per domain, 24h cache, self-identifies as `JobApply/1.0` |
| HTTP Cache | 5-minute in-memory cache per URL |
| Freshness Filter | 72-hour window (relative terms + dateutil parsing) |
| Strategy Chain | JSON API → JSON-LD (schema.org) → Multi-selector CSS → Heuristic text extraction |
| URL Dedup | Per-board → per-collection → DB INSERT OR IGNORE |
| Classification | Keyword overlap scoring vs 20 categories; location (nigeria/remote/international); graduate flag (35+ patterns) |
| Match Score | 0-100: company present (+15), description > 100 chars (+15), keyword overlap (+70) |

#### Boards by Category

**Nigeria (10):** SmartyAcad (WP REST API), MyJobMag (JSON-LD→CSS), Jobberman, Jobgurus, HotNigerianJobs, NGCareers, Jobzilla, NaijaJobPortal, LEEP (Govt Portal), Oil & Gas sector scrap

**NGO (9):** MyNGOJob, ReliefWeb (RSS→HTML), Devex, ImpactPool, Idealist, UNICEF (Multi-URL), WHO (Multi-URL), DevNetJobs, IRC (Multi-URL Cornerstone ATS)

**International/Remote (17):** RemoteOK, Remotive, Himalayas, RealWorkFromAnywhere, Reed.co.uk, Adzuna, WeWorkRemotely, Indeed, Glassdoor, CWJobs, EuroJobs, LetsWorkRemotely, RemoteWork.ng, WorkingNomads, SkipTheDrive, Rigzone, LinkedIn (stub)

**High-Impact (3):** Idealist (nonprofit), 80000Hours (Algolia API), Anthropic (Multi-URL, Greenhouse ATS)

**Web3 (4):** JobSolana (`__NEXT_DATA__` JSON), CryptocurrencyJobs, Web3.Career, CryptoJobsList

**ATS (2 providers, 29 companies):** Ashby (9 companies), Greenhouse (20 companies) — both via public JSON API

#### Scraping Schedule

| Time | Trigger | Action |
|------|---------|--------|
| 6:00 AM UTC daily | APScheduler + GitHub Actions | Full public board scrape (6 queries × all boards) |
| 3:00 PM UTC daily | APScheduler + GitHub Actions | Same as morning |
| 4:00 AM UTC daily | GitHub Actions | Deactivate jobs older than 7 days |
| Every 5 min | GitHub Actions | `/api/health` keep-alive |
| 60s after boot | APScheduler (one-shot) | Initial scrape on startup |

### 4.5 Job Browsing & Filtering

- **Paginated list:** 50 jobs/page with pagination controls
- **6-filter bar:** Category, Source, Level (graduate/all), Status (applied/new), Location (Nigeria/Remote/International), Sort (date/score)
- **Full-text search:** Across title, company, description
- **URL state sync:** Filters saved to URL query params + localStorage per user
- **Color-coded badges:** Category badges, graduate badge, new badge
- **Excel export:** Filtered jobs as styled .xlsx (13 columns)

### 4.6 Job Detail & CV Tailoring

- **Job detail view:** Full info + match score + applied toggle
- **AI CV tailoring:** 3-attempt quality gate with feedback regeneration
- **Cover letter:** 450-600 word, 5-paragraph narrative structure
- **HR email:** Cold outreach email (max 250 words body), skill gap analysis, role switch detection
- **Document downloads:** DOCX + PDF for both CV and cover letter
- **Quality scores:** 6 metrics (achievement density, bullet depth, skills, summary, education, cover letter)
- **CV diversity:** Synonym substitution (35% probability), bullet/project shuffling, random subset selection

### 4.7 Manual Job Entry

- **URL extraction:** Fetch page → extract schema.org/JSON-LD → fallback meta tags/CSS
- **Manual text entry:** Title, company, description form fields
- **Tailor from data:** Generate CV + cover letter from extracted or manual entry
- **Optional HR email:** Checkbox for cold outreach generation

### 4.8 Document Generation

#### 6 CV Visual Profiles

modern-blue (Calibri/20pt/#1a3a5c), classic-green (Arial/19pt/#2d5016), serif-maroon (Georgia/21pt/#5c1a1a), compact-navy (Tahoma/18pt/#1a1a5c), classic-warm (Garamond/22pt/#5c3a1a), wide-purple (Verdana/20pt/#3a1a5c)

Profile selection is deterministic (MD5 hash of seed + counter) for visual diversity per generation.

#### CV Section Layout
- **Fixed top 3:** Summary → Skills → Experience
- **Shuffled:** Education, Certifications, Projects, Languages (Fisher-Yates)
- **Always last:** Volunteer Experience, Professional Memberships
- **Local only:** Referees section ("Available upon request")
- Right-aligned dates on experience entries

#### Skill Grouping (6 groups with descriptive paragraphs)
- Data Analytics & Engineering (python, sql, r, spark, etc.)
- BI & Visualization (power bi, tableau, looker, etc.)
- Cloud & Infrastructure (aws, azure, gcp, docker, etc.)
- Database Management (postgresql, mysql, mongodb, etc.)
- Project Management & Methods (agile, scrum, jira, etc.)
- Data Collection & M&E (dhis2, kobotoolbox, odk, etc.)

### 4.9 AI/LLM Integration

#### Provider Cascade

| Priority | Provider | Model |
|----------|----------|-------|
| 1st | OpenRouter (NVIDIA) | `openrouter/free` |
| 2nd | Groq | `llama-3.3-70b-versatile` |
| 3rd | Google Gemini | `gemini-1.5-flash` |
| 4th | Google Gemma | `gemma-3-27b-it` |
| Fallback | Rule-based | Deterministic seed-based engine |

#### API Key Resolution
1. User's saved keys (api_keys table)
2. If `use_default_api=True` → supplement with platform `JOBLIN_OPENROUTER_KEY`
3. System prompt: "You are a professional CV writer. Output only valid JSON."

#### Quality Gate (3-attempt loop)
1. `llm_tailor()` → merge → `score_cv_quality()`
2. If PASS (all 6 checks) → return
3. If FAIL → feed quality feedback → retry (up to 3)

#### 6 Quality Checks
- Achievement Density: ≥60% bullets with metrics
- Bullet Depth: ≥2 average per role
- Skills Count: ≥5 skills
- Summary Length: ≥30 words
- Education: present (non-blocking)
- Cover Letter: ≥200 words, no placeholders (6 regex patterns), no clichés (14 banned phrases)

#### Tailoring Prompt Features
- Anti-slop directives, data integrity rules, JD keyword mirroring
- Output JSON schema: `professional_summary`, `tailored_skills` (grouped), `tailored_experience`, `cover_letter`, `keywords_hit`, `match_score`
- Cover letter 5-paragraph narrative structure specification
- Extensive banned phrase list (~50+ entries)
- Role switch detection with transferable skills bridge
- Missing skill group bridging suggestions

### 4.10 Admin Analytics

- **Stat cards:** Total Users, Active Today, CVs Generated, Total Actions, Total Jobs
- **Action Distribution:** Doughnut chart (Chart.js v4)
- **Activity Trend:** Line chart (30-day)
- **Top Users:** Top 10 with medal icons
- **Users Table:** Last 50 users (name, email, role, join date)
- **Usage Heatmap:** Daily (60d) / Monthly (12m) / Yearly (3y)
- **Activity Log:** Paginated table with user, action, details, IP, timestamp

### 4.11 Twitter Jobs

- Job count selector (10/15/20), category filter
- Junk job filtering (non-job titles, Unknown companies, empty descriptions)
- Uses original job board URL instead of Joblin detail link
- Formatted tweet-ready text with character count and thread calculation

---

## 5. API Reference (31 Endpoints)

### Auth
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/api/auth/register` | None | Register → JWT |
| POST | `/api/auth/login` | None | Login → JWT + is_admin |
| GET | `/api/auth/me` | Bearer | Current user profile |
| POST | `/api/auth/forgot-password` | None | Request 15-min reset token |
| POST | `/api/auth/reset-password` | None | Reset with token |

### CV
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/api/cv` | Bearer | Get CV JSON or default template |
| PUT | `/api/cv` | Bearer | Save CV JSON |
| GET | `/api/cv/raw-text` | Bearer | Get raw CV text |
| PUT | `/api/cv/raw-text` | Bearer | Save raw CV text |
| POST | `/api/cv/parse` | Bearer | AI-parse raw text → structured CV |
| POST | `/api/cv/make-cv` | Bearer | AI-generate CV from scratch |

### API Keys
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/api/keys` | Bearer | Get keys + use_default_api |
| PUT | `/api/keys` | Bearer | Save keys (groq/nvidia/gemini) |

### Scrape
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/api/scrape` | Admin | Manual scrape (selected boards + query) |
| POST | `/api/scrape/cron` | Admin/Cron token | Trigger nightly scrape (daemon thread) |
| GET | `/api/scrape/test` | Admin | Test scrapers |
| GET | `/api/check-network` | None | Test connectivity |

### Jobs
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/api/jobs` | Bearer | Filtered paginated job list |
| GET | `/api/jobs/{id}` | Bearer | Single job detail |
| POST | `/api/jobs/{id}/link` | Bearer | Link job to user |
| PATCH | `/api/jobs/{id}/applied` | Bearer | Toggle applied status |
| GET | `/api/my/jobs` | Bearer | User's linked jobs |
| POST | `/api/jobs/extract-url` | Bearer | Extract job from URL |

### Tailor
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/api/tailor/{id}` | Bearer | Tailor CV to job (+ email optional) |
| POST | `/api/tailor/from-data` | Bearer | Tailor from arbitrary job dict |
| POST | `/api/jobs/{id}/email-hr` | Bearer | Generate HR email |

### Download & Export
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/api/download/{id}/{type}` | Bearer | Download CV or cover letter |
| GET | `/api/download/manual/{filename}` | Bearer | Download manual file |
| GET | `/api/export/excel` | Bearer | Export filtered jobs as .xlsx |

### Dashboard & Public
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/api/stats` | None | Global job statistics |
| GET | `/api/recent-jobs` | None | 15 most recent active jobs |
| GET | `/api/config` | None | Board config + categories |
| POST | `/api/track` | Bearer | Log custom user activity |
| GET | `/api/health` | None | Health check |

### Admin
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/api/admin/analytics/overview` | Admin | Activity stats + charts data |
| GET | `/api/admin/analytics/log` | Admin | Paginated activity log |
| GET | `/api/cleanup` | Cron token | Deactivate jobs older than 7 days |

### Frontend Catch-all
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/{path}` | None | Serve static frontend files (`.html` fallback → login fallback) |

---

## 6. Frontend (13 Pages, Vanilla HTML/CSS/JS)

| Page | Auth | Key Sections |
|------|------|-------------|
| `index.html` | Public | Neon/cyberpunk landing: hero + email CTA, canvas grid, job showcase carousel, latest jobs, testimonials, features, footer |
| `about.html` | Public | Developer portfolio, skills cloud, 11 project cards, API key setup guide |
| `login.html` | Public | Auth card with email, password (visibility toggle) |
| `register.html` | Public | Auth card with name, email, password; email pre-fill from URL param |
| `forgot-password.html` | Public | 2-step: email → token display → new password |
| `dashboard.html` | Required | 14 rotating motivation messages, 6 stat cards, category/location bar charts, admin scrape button |
| `jobs.html` | Required | 6-filter bar, paginated 50/page, Excel export, filter persistence |
| `job-detail.html` | Required | Job info, apply toggle, tailor generate, HR email, quality scores, downloads |
| `make-cv.html` | Required | Voice narration (Web Speech API), raw text input, target tags, CV type toggle, AI generate |
| `cv-editor.html` | Required | Structured form, dynamic entries, JSON editor toggle, auto-save |
| `manual-job.html` | Required | URL extraction, manual entry, tailor generate, downloads |
| `settings.html` | Required | Default AI toggle, personal API keys (groq/nvidia/gemini) |
| `admin-analytics.html` | Admin | Stat cards, doughnut/line charts, top users, heatmap, activity log |
| `twitter-jobs.html` | Required | Job count selector, category filter, junk filtering, original URLs, copy to clipboard |

### Design System

**Two themes:**
- **Neon/Cyberpunk:** Landing + auth pages. Dark bg, Orbitron headings, canvas animation, scanlines, neon accents (cyan, magenta, green, purple, yellow)
- **Light Minimal:** All authenticated pages. oklch colors, white bg, teal/green primary, Inter font, frosted glass sidebar

**Design tokens:** 10-shade primary + neutral scales (oklch), 12-step spacing (4-80px), 7 radius steps, 5 shadow depths, 3 transition speeds

**Browser APIs:** Web Speech (make-cv), Canvas 2D (index), IntersectionObserver (index), Clipboard API, URLSearchParams, Blob downloads, localStorage, history.replaceState, requestAnimationFrame

---

## 7. Deployment Infrastructure

### 7.1 Render (Active)

- **Web Service:** joblin-hx5a, Docker runtime, starter plan, Oregon, main branch
- **Health check:** `/api/health`
- **Persistent disk:** 1 GB at `/data` (generated/ directory for DOCX/PDF/Excel)
- **Database:** Neon PostgreSQL (starter, Oregon, db `joblin`)

### 7.2 Docker

- **Base:** `python:3.11-slim`
- **Build:** Install gcc → pip install -r requirements.txt → COPY source → runtime: uvicorn
- **Port:** 8080

### 7.3 GitHub Actions (4 workflows)

| Workflow | Schedule | Action |
|----------|----------|--------|
| `keep-alive.yml` | `*/5 * * * *` | GET `/api/health` |
| `scrape-6am.yml` | `0 6 * * *` | POST `/api/scrape/cron` |
| `scrape-3pm.yml` | `0 15 * * *` | POST `/api/scrape/cron` |
| `cleanup.yml` | `0 4 * * *` | GET `/api/cleanup` |

All support `workflow_dispatch` manual trigger.

---

## 8. Non-Functional Requirements

### 8.1 Performance
- Single uvicorn worker (Render starter plan)
- HTTP connection pooling (`requests.Session`)
- 5-min in-memory cache for scraper HTTP responses
- 72-hour freshness filter reduces storage
- URL dedup at scrape-time, collection-time, DB-insert-time

### 8.2 Reliability
- Circuit breaker: 5 consecutive failures → exponential backoff (300s base, up to ~80 min)
- 4-level LLM cascade with rule-based fallback
- Quality gate with 3-attempt feedback loop for CV generation
- Keep-alive ping every 5 minutes prevents Render spin-down
- Multiple URL patterns per board for resilience against site restructuring

### 8.3 Security
- bcrypt password hashing
- JWT HS256 with configurable secret (auto-generated on Render)
- Bearer token required for authenticated endpoints
- Admin-only endpoints check `is_admin` flag
- Cron endpoints protected by `JOBLIN_CRON_TOKEN`
- Reset tokens SHA-256 hashed, 15-min expiry, single-use
- `.env` and `data/` excluded from Git/Docker

### 8.4 Scraping Ethics
- Robots.txt respected (24h cache, identifies as `JobApply/1.0`)
- 3-8s random delay between requests to same domain
- 6-UA rotation reduces footprint
- Circuit breaker stops hitting failing domains
- Public API boards preferred over HTML scraping

### 8.5 Known Limitations
- No email sending (password reset tokens displayed inline)
- LinkedIn scraping is a stub (login required)
- Some login-required boards non-functional without credentials
- Single uvicorn worker (no horizontal scaling)
- No ORM (raw SQL — schema changes need manual migration)
- No automated test suite detected
- Playwright scraping defined but not integrated into cron pipeline
- No WebSocket or real-time updates
- Admin credentials hardcoded in seed function
- CORS allows all origins (`allow_origins=["*"]`)

---

## 9. Future Considerations

- Email sending for password reset and application tracking
- LinkedIn API integration for the largest professional job board
- Playwright scraping in cron pipeline for JS-rendered boards
- Automated test suite (unit + integration)
- ORM migration (SQLAlchemy + Alembic) for safer schema evolution
- Role-based access control beyond admin/user binary
- Multi-language CV generation (e.g., French for West African markets)
- Application tracking pipeline (saved → tailored → applied → interviewed → offered)
- Rate limiting on API endpoints
- CORS origin restriction in production
- CI/CD pipeline with automated testing before deploy
