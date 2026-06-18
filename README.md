---
title: Joblin
emoji: 📋
colorFrom: green
colorTo: blue
sdk: docker
pinned: false
app_port: 7860
---

# Joblin

Joblin is a job discovery and CV tailoring platform for Nigerian, remote,
international, NGO, high-impact, and Web3 roles.

The app combines scheduled job scraping, a searchable global job pool, user CV
storage, AI-assisted CV generation, job-specific tailoring, cover letter
generation, document downloads, and lightweight admin analytics.

## Deployment

- **App host:** Render
- **Database:** Neon PostgreSQL via `DATABASE_URL`
- **Scheduled jobs:** GitHub Actions call the public cron endpoints
- **Backend:** FastAPI
- **Frontend:** Static HTML, CSS, and JavaScript
- **Generated files:** Stored under `DATA_DIR/generated`

## Main Features

- User registration, login, JWT sessions, and password reset tokens.
- CV editor, raw CV text storage, CV parsing, and CV generation from notes.
- Job scraping across Nigeria, NGO, international, high-impact, Web3, and ATS
  sources.
- Deduplicated global job pool with categories, job detail pages, and recent
  jobs.
- Job-to-user linking, application status tracking, and applied toggles.
- Job-specific tailored CV and cover letter generation.
- DOCX/PDF downloads for CVs and cover letters.
- Excel export for jobs.
- Admin analytics for activity, users, generation counts, and trends.

## Recent Session Updates

- Fixed logo links across authenticated pages so dashboard, jobs, CV, manual
  job, settings, and related pages return to `index.html`.
- Added an API key setup guide for NVIDIA/OpenRouter and Groq to
  `frontend/about.html`.
- Rewrote project descriptions in `frontend/about.html` to sound more direct
  and less generic.
- Changed the homepage testimonial phrase from "Game changer" to
  "It worked for me".
- Updated download file naming to include sequence number, job title, company,
  job ID, and date.
- Expanded admin analytics backend data with generation counts, user lists,
  daily/monthly/yearly heatmap data, trend cards, and top users.
- Rebuilt `frontend/admin-analytics.html` with user list, heatmap, trend cards,
  and top-user views.
- Added `frontend/twitter-jobs.html`.
- Added CV generation tracking with `log_activity` for `cv_generated` events.
- Changed local development port from `8000` to `8001` because `8000` has a
  lingering process.
- Updated the recent jobs route from `/api/jobs/recent` to `/api/recent-jobs`.
- Added the `escHtml` helper usage and fixed the silent failure in
  `loadLatestJobs`.
- Fixed `_file_slug` sequence padding to use dynamic width instead of a fixed
  `zfill(3)`.

## Notes

- GitHub workflow secret names still reference `HF_SPACE_URL`, but the value can
  point to the current Render URL.
- Password reset currently returns a reset token through the API; it does not
  send email by itself.
- Some login-required job boards are listed in config, but full scraping depends
  on credentials or public access limits.
