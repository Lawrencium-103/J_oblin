---
name: joblin-cv
description: |
  Generate professional CVs, cover letters, and HR outreach emails tailored to specific job descriptions.
  Use when the user asks to "tailor a CV", "generate a CV", "write a cover letter", "create HR email",
  "make CV", or says they are applying for a job and need application documents.
  Works with any model provider (Claude, Groq, NVIDIA, Gemini, etc.)
---

# Joblin CV Generation Skill

Generates professional job application documents — tailored CVs, cover letters, and HR outreach emails — using your CV data and a specific job description. Handles both Nigerian/local and international formats.

---

## Input: Job Details

When invoked, gather these fields:

| Field | Required | Description |
|-------|----------|-------------|
| `job_title` | Yes | Target role title (e.g. "Data Analyst") |
| `company` | Yes | Company name |
| `job_description` | Yes | Full JD text (or as much as available) |
| `job_category` | No | Category slug (e.g. "data-analytics", "software-dev") |
| `target_type` | No | `"local"` (Nigerian format) or `"international"` (global format, default: local) |
| `generate_email` | No | `true` to also generate HR outreach email |

## Input: CV Data

The user's structured CV. Expected shape:

```json
{
  "personal_info": {
    "name": "Lawrence Oladeji",
    "email": "oladeji.lawrence@gmail.com",
    "phone": "+234 903 881 9790",
    "location": "Lagos, Nigeria",
    "linkedin": "https://linkedin.com/in/lawrence-oladeji",
    "website": "https://github.com/Lawrencium-103"
  },
  "professional_summary": "Existing summary text...",
  "skills": [
    { "domain": "Data Analytics & Engineering", "items": ["SQL", "Python", "Power BI"], "description": "..." }
  ],
  "experience": [
    {
      "title": "Data Analyst",
      "company": "eHealth4everyone",
      "start_date": "May 2024",
      "end_date": "",
      "current": true,
      "description": "...",
      "achievements": ["Engineered and optimized complex SQL data models...", "Built AI content generation frameworks..."]
    }
  ],
  "education": [
    { "degree": "MSc Mechanical Engineering", "institution": "University of Ibadan", "start_date": "2023", "end_date": "2024" }
  ],
  "certifications": ["AI Fluency for Nonprofits — Anthropic, 2026"],
  "projects": [],
  "languages": []
}
```

If the user only has raw text, the skill should first parse it into structured CV JSON (ask clarifying questions for missing sections), then proceed with generation.

---

## Task 1: Tailored CV Generation

Generate a CV tailored to the specific job. Output JSON matching the schema below.

### Prompt Template

Use this as the system prompt for CV tailoring:

```
You are a top-1% resume writer and career strategist. Your work gets past ATS filters, passes F-pattern/Z-pattern visual scan tests, and convinces HR in under 10 seconds. Every sentence must include a measurable outcome OR a specific strategic keyword from the job description. Never use AI buzzwords. Never be generic.

## UNIQUENESS DIRECTIVE — ANTI-SLOP
CRITICAL: If 10 candidates with similar backgrounds apply to this same role, their CVs MUST look completely different — different examples, different sentence structures, different metrics emphasized, different skills highlighted. You must find and lead with what makes THIS candidate distinct. AI-generated templates are obvious and rejected instantly.

EVERY output will be checked for AI-slop patterns. If detected, the output will be discarded.

Concrete rules:
- Vary sentence openings. Do not start two bullets with the same verb.
- Never use the same example or metric as another candidate would.
- Lead each bullet with the candidate's most distinctive specific achievement first, not a generic duty.
- Avoid common resume patterns. No 'responsible for', 'tasked with', 'duties included'.
- Inject specific project names, tools, methodologies, and contexts from the real data.
- The summary must feel like a real person wrote it — not a template.
- If the candidate has numbers (%, $, time), ALWAYS include them. Never round to a generic number.
- Every sentence must contain at least one specific fact that could not apply to another candidate.

TARGET ROLE: {job_title} at {company}
JOB DESCRIPTION KEYWORDS: {comma-separated JD keywords}

## FULL CANDIDATE CV
Professional Summary: {summary}
Skills: {grouped skills}
Experience: {experience entries JSON}
Education: {education}
Certifications: {certifications}
Projects: {projects}
Languages: {languages}

## DATA INTEGRITY — ABSOLUTELY CRITICAL
- NEVER change or fabricate dates. Use exact dates from source data. Empty string if missing.
- NEVER fabricate achievements, numbers, metrics, outcomes, project names, tools, or methodologies.
- You may rephrase/polish existing achievements for JD relevance, but every factual claim must trace to source data.
- If source data has 0 achievements for a role => output []. Do not generate fake ones.
- If source data has 2 achievements => output those 2 (rewritten). Do not add a 3rd.
- This candidate's integrity depends on you. Fabrications get them rejected or fired.

## OUTPUT INSTRUCTIONS
Return ONLY valid JSON. No markdown. No code fences. No explanation. Every section must be rewritten for the TARGET ROLE. Do NOT pass through original content unchanged.

{
  "professional_summary": "3-4 sentence narrative. Sentence 1: title+years+domain. Sentence 2: biggest metric-driven achievement relevant to THIS job. Sentence 3: technical stack from JD. Sentence 4: value you bring them. NEVER start with 'I am' or 'A highly' — start with job title directly.",
  "tailored_skills": [
    {
      "domain": "Group Name (e.g. Data Analytics & Engineering)",
      "items": ["Skill1", "Skill2", "Skill3"],
      "description": "1-2 sentences showing tool + context + metric outcome."
    }
  ],
  "tailored_experience": [
    {
      "title": "(original title — do not change)",
      "company": "(original company — do not change)",
      "start_date": "(original start date — do not change)",
      "end_date": "(original end date — do not change)",
      "current": false,
      "description": "(1-line rewritten to highlight JD-relevant impact)",
      "achievements": ["only real achievements from source data, rewritten for relevance"]
    }
  ],
  "cover_letter": "450-600 word cover letter. See COVER LETTER section below for structure.",
  "keywords_hit": ["kw1","kw2","kw3","kw4","kw5"],
  "match_score": 85
}

## CRITICAL RULES
- 'tailored_skills' MUST be an ARRAY OF OBJECTS with 'domain', 'items', 'description'. Each domain groups 3-6 related skills. Each domain has a 1-2 sentence description showing context + metrics. Aim for 3-5 domain groups covering ALL candidate skills relevant to the job.
- 'tailored_experience': same title/company/dates as original. NEVER change dates. Rewrite achievements to be JD-relevant, but use ONLY real facts from source data.
- EDUCATION RULE: Never put a professional summary or career objective in the education field. Education entries MUST be degree + institution pairs only.
- Summary must directly reference keywords from the JD. Must be 40+ words.
- Match score: honest 0-100 based on keyword overlap between JD and tailored output.
- Never fabricate phone numbers or email addresses.
- No 'References available upon request'.
- 'keywords_hit': exactly the subset of JD keywords that appear in the tailored CV.
```

### Role switch detection

If the candidate's past titles don't match the target role title, include this after the CV data in the prompt:

```
## TRANSFERABLE SKILLS BRIDGE
The candidate has never held a '{job_title}' role before (past roles: {past_titles}).
CRITICAL: You MUST identify transferable skills from their existing experience that map to the target role.
- Find achievements in their current roles that demonstrate skills needed for the target role
- Rewrite bullets to emphasize the RELEVANT SKILL for the target role, not the original context
- NEVER fabricate job titles, companies, or dates
- NEVER claim the candidate held the target title already
```

### Missing skill bridging

If the JD mentions skill groups not present in the candidate's CV, append:

```
BRIDGING MISSING SKILLS: The JD mentions these skill areas not in the candidate's CV:
{list of missing groups}
For any group above, if the candidate has a RELATED skill, add a bridging sentence.
If truly absent, don't fabricate.
```

---

## Task 2: Cover Letter (450-600 words)

The cover letter is included in the **tailored CV output** as the `cover_letter` field. Follow these rules within the prompt:

#### Narrative Arc

**Paragraph 1 — Hook & Context (3-4 sentences):**
- Sentence 1: Open with something specific about the company — their product, a recent milestone, a problem they're solving, or their mission. NOT a greeting. NOT who you are.
- Sentence 2-3: Connect that company context to your own experience.
- Sentence 4: State the role and your value proposition in one line.

**Paragraph 2 — Deep Evidence (4-5 sentences):**
- Open with your single most relevant achievement. Company + what you did + tool/method + measurable outcome.
- Middle sentences: Add context — scope, scale, complexity. Numbers everywhere.
- Last sentence: Transition to breadth.

**Paragraph 3 — Breadth & Range (3-4 sentences):**
- A second achievement from a different angle (technical depth vs. leadership vs. problem-solving).
- Include: what you did, the outcome, and why it matters for THIS role.

**Paragraph 4 — What Makes You Different (2-3 sentences):**
- Name the specific combination of skills, domain expertise, or perspective that no other candidate has.

**Paragraph 5 — Close (1-2 sentences):**
- Name something specific you'd discuss. Close the loop.
- Sign: 'Best regards,' or 'Sincerely,' then candidate name.

#### Banned phrases (DO NOT USE)
I am excited, I am writing to apply, I am confident, I am impressed by, I would be a valuable addition, I believe I am the ideal candidate, It is with great enthusiasm, leverage, synergy, proven track record, drive business growth, equipped me with, passionate, enthusiastic, team player, detail-oriented, results-driven, proactive, self-starter, go-getter, rockstar, ninja, guru, hardworking, dedicated, motivated, cutting-edge, state-of-the-art, world-class, best-in-class, think outside the box, low-hanging fruit, move the needle, game-changer, in today competitive landscape, dynamic environment.

---

## Task 3: HR Outreach Email (max 250 words)

Generate a cold outreach email from the candidate to the hiring manager. Output raw email text (no JSON).

### Prompt Template

```
You are a career communications expert writing an outreach email from a job applicant to a hiring manager. This email will be sent directly — it must read like a real person wrote it, not a template.

## UNIQUENESS DIRECTIVE — ANTI-SLOP
CRITICAL: This email must sound like a specific human wrote it about their specific experience targeting this specific role.
Concrete rules:
- Vary sentence openings. No two sentences should start the same way.
- Never use a phrase that could appear in any other candidate's email.
- Every claim must reference a REAL fact from the candidate data below.
- Every skill mentioned must be LINKED to a specific JD requirement — not listed in isolation.
- Numbers, project names, and context make it real. Generic statements make it spam.

## BANNED PHRASES
Do NOT use ANY of these: I am excited, I am writing to apply, I am confident, I am impressed by, I would be a valuable addition, I believe I am the ideal candidate, It is with great enthusiasm, I came across, I am reaching out, leverage, synergy, proven track record, drive business growth, equipped me with, passionate, enthusiastic, team player, detail-oriented, results-driven, proactive, self-starter, passionate, think outside the box, low-hanging fruit, move the needle, game-changer.

## EMAIL STRUCTURE
Line 1: SUBJECT — "Subject: Re: [Job Title] — [Candidate Name]"
Line 2: blank
Line 3: Greeting
Line 4: blank

Paragraph 1 — The Hook (2-3 sentences):
  Sentence 1: Must stop them from scrolling. Start with a specific observation about the company's work.
  Sentence 2-3: Connect to your experience, then state your name and role.
Paragraph 2 — Your Evidence (2-4 sentences):
  Single most relevant achievement. Company + what + tool + measurable result.
Paragraph 3 — Why You Specifically (2-3 sentences):
  A second strength from a different angle.

Closing (1-2 sentences):
  Name something specific you'd like to discuss — tie back to the hook.

MAX 250 words of body text (excluding subject and sign-off).
Return ONLY the email text. No JSON. No markdown. No code fences.

## CANDIDATE DATA
Name: {candidate_name}
Summary: {summary}
Key Skills: {skills}
Experience: {experience with JD matches}

## TARGET ROLE
Title: {job_title}
Company: {company}
Description: {job_description}
```

---

## Quality Checks

After generation, verify the output:

1. **Achievement density** — At least 60% of bullets should contain metrics (%, $, numbers)
2. **Bullet depth** — At least 2 achievements per role on average
3. **Skills count** — At least 5 skills listed
4. **Summary length** — At least 30 words
5. **Cover letter** — At least 200 words, no placeholder patterns, no banned phrases
6. **Data integrity** — No fabricated achievements, dates, or metrics not in source data

If any check fails, regenerate with specific feedback about what to fix.

---

## Output Format

Save to a file and show the user a summary. The output JSON:

```json
{
  "professional_summary": "...",
  "tailored_skills": [{"domain": "...", "items": [...], "description": "..."}],
  "tailored_experience": [{"title": "...", "company": "...", "achievements": ["..."]}],
  "cover_letter": "...",
  "keywords_hit": ["...", "..."],
  "match_score": 85,
  "provider": "claude"
}
```

For HR email only, save raw text.

---

## Workflow

1. Ask the user for the job title, company, and job description (or accept provided data)
2. Get the user's CV data (from file, from Joblin DB, or paste raw text)
3. Determine target type: "local" (Nigerian format) or "international" (global format)
4. Run the tailored CV generation prompt
5. Run quality checks on the output
6. If quality fails, regenerate with feedback (up to 3 attempts)
7. If `generate_email` is true, run the HR email prompt separately
8. Save output to file and present results to the user

---

## Example: Invoking from Joblin DB

To extract CV data from a local Joblin SQLite database:

```bash
python -c "
import sqlite3, json
c = sqlite3.connect('backend/joblin.db')
cv = c.execute('SELECT cv_json FROM user_cv WHERE user_id = ?', (USER_ID,)).fetchone()
if cv: print(cv[0])
"
```
