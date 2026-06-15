import json
import re
import requests as _req


POWER_SKILLS = {
    "sql", "python", "excel", "power bi", "tableau", "looker", "r", "spss",
    "stata", "gis", "kobo", "odk", "dhis2", "redcap", "power query", "dax",
    "data analysis", "data analyst", "dashboard", "reporting", "kpi",
    "monitoring", "evaluation", "m&e", "meal", "indicator", "database",
    "bi", "etl", "data entry", "data quality", "data cleaning", "data collection",
    "data management", "data warehouse", "data validation", "visualization",
    "mysql", "postgresql", "azure", "aws", "spark", "machine learning", "pipeline",
    "survey", "beneficiary", "humanitarian", "stakeholder", "statistics",
    "google sheets", "salesforce", "attention to detail", "analytical",
}


def top_keywords(text: str, n: int = 15) -> list[str]:
    scored: dict[str, int] = {}
    lower = text.lower()
    tokens = lower.split()
    for skill in POWER_SKILLS:
        if skill in lower:
            scored[skill] = lower.count(skill)
    for i in range(len(tokens) - 1):
        bigram = f"{tokens[i]} {tokens[i+1]}"
        if bigram in POWER_SKILLS and bigram not in scored:
            scored[bigram] = lower.count(bigram)
    if len(scored) < n:
        for cap in re.findall(r"\b[A-Z][A-Za-z]{2,12}\b", text):
            cl = cap.lower()
            if cl not in scored:
                scored[cl] = 1
    return sorted(scored, key=lambda k: -scored[k])[:n]


def _parse_json(raw: str) -> dict | None:
    raw = re.sub(r"```[a-z]*", "", raw or "").strip("` \n")
    try:
        return json.loads(raw)
    except Exception:
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        if m:
            try:
                return json.loads(m.group())
            except Exception:
                pass
    return None


def _call_groq(prompt: str, api_key: str, max_tokens: int = 512) -> str | None:
    if not api_key:
        return None
    try:
        resp = _req.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": "llama-3.3-70b-versatile",
                "messages": [
                    {"role": "system", "content": "You are a professional CV writer. Output only valid JSON."},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.7,
                "max_tokens": max_tokens,
            },
            timeout=30,
        )
        data = resp.json()
        if "choices" not in data:
            print(f"[llm/groq] no choices key. status={resp.status_code}, body={str(data)[:300]}")
            return None
        return data["choices"][0]["message"]["content"]
    except Exception as e:
        print(f"[llm/groq] {type(e).__name__}: {e}")
        return None


def _call_nim(prompt: str, api_key: str, max_tokens: int = 512) -> str | None:
    if not api_key:
        return None
    for attempt in range(3):
        try:
            resp = _req.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "http://localhost:8002",
                },
                json={
                    "model": "openrouter/free",
                    "messages": [
                        {"role": "system", "content": "You are a professional CV writer. Output only valid JSON."},
                        {"role": "user", "content": prompt},
                    ],
                    "max_tokens": max_tokens,
                    "temperature": 0.7,
                    "stream": False,
                },
                timeout=60,
            )
            raw = resp.text
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                print(f"[llm/nim] JSON parse error. status={resp.status_code}, raw={raw[:300]}")
                return None
            if "choices" not in data:
                print(f"[llm/nim] unexpected response: {str(data)[:200]}")
                return None
            return data["choices"][0]["message"]["content"]
        except Exception as e:
            if attempt < 2:
                import time as _t
                _t.sleep(2)
                continue
            print(f"[llm/nim] error ({attempt+1} attempts): {type(e).__name__}: {e}")
            return None
    return None


def _call_gemini(prompt: str, api_key: str, max_tokens: int = 512) -> str | None:
    if not api_key:
        return None
    try:
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"gemini-1.5-flash:generateContent?key={api_key}"
        )
        resp = _req.post(
            url,
            json={
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": 0.7, "maxOutputTokens": max_tokens},
            },
            timeout=30,
        )
        return resp.json()["candidates"][0]["content"]["parts"][0]["text"]
    except Exception as e:
        print(f"[llm/gemini] {e}")
        return None


def _call_gemma(prompt: str, api_key: str, max_tokens: int = 512) -> str | None:
    if not api_key:
        return None
    try:
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"gemma-3-27b-it:generateContent?key={api_key}"
        )
        resp = _req.post(
            url,
            json={
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": 0.7, "maxOutputTokens": max_tokens},
            },
            timeout=30,
        )
        return resp.json()["candidates"][0]["content"]["parts"][0]["text"]
    except Exception as e:
        print(f"[llm/gemma] {e}")
        return None


def _call_any(prompt: str, api_keys: dict, max_tokens: int = 512) -> str | None:
    return _call_nim(prompt, api_keys.get("nvidia", ""), max_tokens) or \
           _call_groq(prompt, api_keys.get("groq", ""), max_tokens) or \
           _call_gemini(prompt, api_keys.get("gemini", ""), max_tokens) or \
           _call_gemma(prompt, api_keys.get("gemini", ""), max_tokens)


SKILL_TAXONOMY = {
    "Data Analytics & Engineering": {
        "keywords": ["python", "sql", "r", "spark", "excel", "pandas", "numpy", "scikit-learn", "tensorflow", "pytorch", "statistical modeling", "regression", "forecasting", "machine learning", "predictive modeling", "data mining", "etl", "databricks"],
        "group_template": "Data Analytics & Engineering"
    },
    "BI & Visualization": {
        "keywords": ["power bi", "tableau", "looker", "qilk", "google data studio", "microstrategy", "d3.js", "matplotlib", "ggplot2", "seaborn", "plotly", "dashboards", "scorecards", "visual analytics"],
        "group_template": "BI & Visualization"
    },
    "Cloud & Infrastructure": {
        "keywords": ["aws", "azure", "gcp", "google cloud", "cloud computing", "docker", "kubernetes", "terraform", "ci/cd", "devops", "bigquery", "snowflake", "redshift", "synapse", "data lake", "data warehouse"],
        "group_template": "Cloud & Infrastructure"
    },
    "Database Management": {
        "keywords": ["postgresql", "mysql", "mongodb", "oracle", "sql server", "sqlite", "mariadb", "cassandra", "neo4j", "dynamodb", "nosql", "database design", "data modeling", "erd"],
        "group_template": "Database Management"
    },
    "Project Management & Methods": {
        "keywords": ["agile", "scrum", "kanban", "jira", "trello", "asana", "monday.com", "ms project", "project management", "stakeholder management", "requirements gathering", "sdlc", "waterfall", "cross-functional"],
        "group_template": "Project Management & Methodology"
    },
    "Data Collection & M&E": {
        "keywords": ["m&e", "monitoring and evaluation", "dhis2", "kobotoolbox", "odk", "survey cto", "data collection", "surveys", "questionnaires", "indicator tracking", "logframe", "results framework", "nbs", "who", "world bank", "npc"],
        "group_template": "Data Collection & M&E"
    },
}


def _group_skills(cv_skills: list) -> str:
    """Convert any skill format to a grouped string for the prompt."""
    if not cv_skills:
        return "It looks like no skills were provided."
    
    # Already grouped
    if isinstance(cv_skills[0], dict):
        parts = []
        for g in cv_skills:
            items = g.get("items", [])
            name = g.get("domain", g.get("name", ""))
            desc = g.get("description", "")
            if items:
                parts.append(f"- {name}: {', '.join(items)}")
            if desc:
                parts.append(f"  {desc}")
        return "\n".join(parts)
    
    # Flat list — group using taxonomy
    flat = [s.lower() for s in cv_skills]
    grouped = {}
    uncovered = []
    
    for skill in flat:
        placed = False
        for group_name, group_info in SKILL_TAXONOMY.items():
            if any(kw in skill for kw in group_info["keywords"]):
                grouped.setdefault(group_name, []).append(skill)
                placed = True
                break
        if not placed:
            uncovered.append(skill)
    
    if uncovered:
        grouped["Other"] = uncovered
    
    parts = []
    for gname, items in grouped.items():
        original_names = [s for s in cv_skills if s.lower() in items]
        parts.append(f"- {gname}: {', '.join(original_names)}")
    return "\n".join(parts)


def tailor_application(
    job_title: str,
    job_description: str,
    company: str,
    user_cv: dict,
    api_keys: dict = None,
    category: str = "",
    feedback: str = "",
    attempt: int = 1,
) -> dict:
    api_keys = api_keys or {}
    jd_keywords = top_keywords(job_description)
    cv_skills = user_cv.get("skills", [])
    
    # Convert legacy flat skills to string representation
    skills_str = _group_skills(cv_skills)

    exp_entries_raw = user_cv.get("experience", [])
    exp_list_json = json.dumps([
        {
            "title": e.get("title", ""),
            "company": e.get("company", ""),
            "start_date": e.get("start_date", ""),
            "end_date": e.get("end_date", ""),
            "current": e.get("current", False),
            "description": e.get("description", ""),
            "achievements": e.get("achievements", []),
        }
        for e in exp_entries_raw[:5]
    ], ensure_ascii=False)

    education = user_cv.get("education", [])
    education_json = json.dumps(education, ensure_ascii=False) if education else "None provided"

    certs = user_cv.get("certifications", [])
    cert_str = "\n".join(f"- {c}" for c in certs if c) if certs else "None"

    projects = user_cv.get("projects", [])
    proj_str = "\n".join(
        f"- {p.get('name')} ({', '.join(p.get('technologies', []))}): {p.get('description', '')[:150]}"
        for p in projects[:6]
    ) if projects else "None"

    languages = user_cv.get("languages", [])
    lang_str = ", ".join(languages) if languages else "Not specified"

    summary_from_cv = user_cv.get("professional_summary", "")

    is_highimpact = category == "highimpact"
    cert_boost = ""
    if is_highimpact and any("anthropic" in c.lower() or "ai fluency" in c.lower() for c in certs):
        cert_boost = (
            "\nCRITICAL: Candidate holds the Anthropic 'AI Fluency for Nonprofits' certification. "
            "Lead with this in the professional summary."
        )

    # Flatten skills to a single lowercase string for keyword matching
    def _flatten_skills(skills):
        if not skills:
            return ""
        if isinstance(skills[0], str):
            return " ".join(skills).lower()
        if isinstance(skills[0], dict):
            items = []
            for g in skills:
                items.extend(g.get("items", []))
            return " ".join(items).lower()
        return ""

    # Detect JD keywords that relate to skill groups the candidate doesn't have
    jd_lower = job_description.lower()
    missing_groups = []
    related_groups = []
    cv_flat = _flatten_skills(cv_skills)
    for group_name, group_info in SKILL_TAXONOMY.items():
        group_mentioned = any(kw in jd_lower for kw in group_info["keywords"])
        if group_mentioned:
            candidate_has = any(kw in cv_flat for kw in group_info["keywords"])
            if not candidate_has:
                missing_groups.append(group_name)
            else:
                related_groups.append(group_name)

    # Detect if candidate's past titles are different from target role
    target_title_lower = job_title.lower()
    past_titles = [e.get("title", "").lower() for e in exp_entries_raw if e.get("title")]
    is_role_switch = True
    for pt in past_titles:
        if any(kw in pt for kw in target_title_lower.split()):
            is_role_switch = False
            break
    transferable_boost = ""
    if is_role_switch and past_titles:
        transferable_boost = (
            "\n## TRANSFERABLE SKILLS BRIDGE ##\n"
            f"The candidate has never held a '{job_title}' role before (past roles: {', '.join(past_titles[:3])}).\n"
            "CRITICAL: You MUST identify transferable skills from their existing experience that map to the target role.\n"
            "- Find achievements in their current roles that demonstrate skills needed for the target role\n"
            "- Rewrite bullets to emphasize the RELEVANT SKILL for the target role, not the original context\n"
            "- Example: 'Managed team of 5 field officers' targeting a data role → 'Coordinated data collection across 5 field officers, ensuring 98% reporting compliance'\n"
            "- Example: 'Processed invoices for 200+ vendors' targeting a project management role → 'Managed cross-functional workflows across 200+ stakeholders, delivering on-time processing'\n"
            "- NEVER fabricate job titles, companies, or dates\n"
            "- NEVER claim the candidate held the target title already\n"
            "- In the summary, name the transfer explicitly: 'Bringing [X years] of [domain] experience, with proven transferable skills in [skill1], [skill2], and [skill3] directly applicable to the [target role] role.'\n"
            "- Cover letter MUST address the career pivot directly: 'While my background is in [past domain], my experience in [transferable skill] maps directly to [JD requirement].'\n"
        )

    bridging_suggestions = ""
    if missing_groups:
        bridging_suggestions = (
            "\nBRIDGING MISSING SKILLS: The JD mentions these skill areas not in the candidate's CV:\n"
            + "\n".join(f"- {g}" for g in missing_groups)
            + "\nFor any group above, if the candidate has a RELATED skill (e.g. Tableau instead of Power BI), "
            "add a bridging sentence in the skills description: 'While experienced in [their tool], "
            "demonstrated same [methodology] with [JD tool] dashboards adopted by C-suite.' "
            "If truly absent, don't fabricate."
        )

    feedback_section = ""
    if feedback:
        feedback_section = (
            "\n## QUALITY FEEDBACK: PREVIOUS DRAFT REJECTED ##\n"
            "Your previous submission was rejected because:\n"
            + feedback + "\n"
            "Fix EVERY issue listed above. This is attempt " + str(attempt) + " of 3."
        )

    prompt = (
        "You are a top-1% resume writer and career strategist. Your work gets "
        "past ATS filters, passes F-pattern/Z-pattern visual scan tests, and "
        "convinces HR in under 10 seconds. Every sentence must include a "
        "measurable outcome OR a specific strategic keyword from the job "
        "description. Never use AI buzzwords. Never be generic.\n\n"
        "## UNIQUENESS DIRECTIVE ##\n"
        "CRITICAL: If 10 candidates with similar backgrounds apply to this same role, "
        "their CVs MUST look completely different. You must find and lead with what makes "
        "THIS candidate distinct. Follow these rules:\n"
        "- Vary sentence openings. Do not start two bullets with the same verb.\n"
        "- Never use the same example or metric as another candidate would.\n"
        "- Lead each bullet with the candidate's most distinctive specific achievement first, "
        "not a generic duty.\n"
        "- Avoid common resume patterns. No 'responsible for', 'tasked with', 'duties included'.\n"
        "- Inject specific project names, tools, methodologies, and contexts from the real data.\n"
        "- The summary must feel like a real person wrote it — not a template.\n\n"
        f"TARGET ROLE: {job_title} at {company}\n"
        f"JOB DESCRIPTION KEYWORDS: {', '.join(jd_keywords)}\n\n"
        "## FULL CANDIDATE CV ##\n"
        f"Professional Summary:\n{summary_from_cv[:500]}\n\n"
        f"Skills:\n{skills_str}\n\n"
        f"Experience (JSON):\n{exp_list_json}\n\n"
        f"Education:\n{education_json}\n\n"
        f"Certifications:\n{cert_str}\n"
        f"Projects:\n{proj_str}\n"
        f"Languages: {lang_str}\n"
        + cert_boost
        + transferable_boost
        + bridging_suggestions
        + feedback_section
        + "\n\n## OUTPUT INSTRUCTIONS ##\n"
        "Return ONLY valid JSON. No markdown. No code fences. No explanation. "
        "Every section must be rewritten for the TARGET ROLE. Do NOT pass through original content unchanged.\n"
        + '{\n'
        + '  "professional_summary": "3-4 sentence narrative. Sentence 1: title+years+domain. Sentence 2: biggest metric-driven achievement relevant to THIS job. Sentence 3: technical stack from JD. Sentence 4: value you bring them. NEVER start with \'I am\' or \'A highly\' — start with job title directly.",\n'
        + '  "tailored_skills": [\n'
        + '    {\n'
        + '      "domain": "Group Name (e.g. Data Analytics & Engineering)",\n'
        + '      "items": ["Skill1", "Skill2", "Skill3"],\n'
        + '      "description": "1-2 sentences showing tool + context + metric outcome. E.g. \'Built ETL pipelines processing 56k+ data points across 45 indicators using Python and SQL.\'"\n'
        + '    }\n'
        + '  ],\n'
        + '  "tailored_experience": [\n'
        + '    {\n'
        + '      "title": "(original title — do not change)",\n'
        + '      "company": "(original company — do not change)",\n'
        + '      "description": "(1-line rewritten to highlight JD-relevant impact, or empty string)",\n'
        + '      "achievements": ["(5-7 bullets, each with specific numbers: %, $, time, volume. Must use action verbs and metrics.)"]\n'
        + '    }\n'
        + '  ],\n'
        + (
            '  "cover_letter": "3-paragraph letter (200-300 words total). Each paragraph has exactly one job. '
            'NO opening cliches. NO generic praise. '
            'PARAGRAPH 1: Reference something specific about the company current work or product. Then name the role and state your specific value proposition. MAX 3 sentences. '
            'PARAGRAPH 2: Exactly 2 achievements from the tailored CV with hard metrics. Use the real company names from the experience section above. Each achievement must show the real company name, the action taken, the resulting hard metric, and the method. Tie each to a JD requirement. Do NOT use placeholder text. '
            'PARAGRAPH 3: 1-2 sentences stating what you bring that is unique. End with looking forward to discussing contribution to their specific company goals or projects. Do not use brackets or placeholders. '
            'UNIQUENESS: No two candidates should sound alike. Lead with the most distinctive real achievement. Vary sentence structures, openings, and metrics chosen from the candidate real data. Avoid any fill-in-the-blank phrasing.\n'
            'NEVER start with: excited, writing, confident, impressed, valuable addition, honor. '
            'NEVER use: leverage, synergy, proven track record, drive business growth, equipped me, I believe, I think. '
            'ANTI-EXAMPLE (REJECTED): I am excited to apply for the data role at the company, where I can leverage my expertise. '
            'GOOD EXAMPLE: BCG X deploys AI at scale for supply chain optimization -- similar to my work building ML pipelines that cut processing time by 60%. As a Forward Deployed AI Scientist, I bring 4 years of production ML.",\n'
        )
        + '  "keywords_hit": ["kw1","kw2","kw3","kw4","kw5"],\n'
        + '  "match_score": 85\n'
        + '}\n\n'
        "## CRITICAL RULES ##\n"
        "- 'tailored_skills' MUST be an ARRAY OF OBJECTS with 'domain', 'items', 'description'. "
        "Each domain groups 3-6 related skills. Each domain has a 1-2 sentence description showing context + metrics. "
        "Aim for 3-5 domain groups covering ALL candidate skills relevant to the job.\n"
        "- 'tailored_experience': same title/company as original. Rewrite ALL achievements to be JD-relevant with metrics. "
        "EVERY bullet must have at least one number. Minimum 5 bullets per role.\n"
        "- Summary must directly reference keywords from the JD. Must be 40+ words.\n"
        "- Cover letter: EXACTLY 3 paragraphs. No more, no less. No title, no salutation. Just the letter body.\n"
        "- Cover letter ABSOLUTELY BANNED: 'I am excited', 'I am writing to apply', 'I am confident', 'proven track record', "
        "'I believe', 'I would be a valuable addition', 'I am impressed by', 'leverage my', 'drive business growth'. "
        "These are cliches that instantly disqualify you.\n"
        "- BANNED WORDS: 'passionate', 'enthusiastic', 'team player', 'detail-oriented', "
        "'results-driven', 'proven track record', 'proactive', 'self-starter', 'go-getter', "
        "'synergy', 'leverage' (unless a tool), "
        "'rockstar', 'ninja', 'guru', 'hardworking', 'dedicated', 'motivated'.\n"
        "- Match score: honest 0-100 based on keyword overlap between JD and tailored output.\n"
        "- Never fabricate phone numbers or email addresses.\n"
        "- No 'References available upon request'.\n"
        "- 'keywords_hit': exactly the subset of JD keywords that appear in the tailored CV.\n"
    )

    raw = _call_any(prompt, api_keys, max_tokens=2000)
    provider = "groq" if api_keys.get("groq") else "rule-based"
    if raw and provider == "rule-based":
        provider = "nim" if api_keys.get("nvidia") else "rule-based"

    if raw:
        result = _parse_json(raw)
        if result:
            return {
                "professional_summary": result.get("professional_summary", summary_from_cv),
                "tailored_skills": result.get("tailored_skills", cv_skills),
                "tailored_experience": result.get("tailored_experience", exp_entries_raw[:3]),
                "cover_letter": result.get("cover_letter", ""),
                "keywords_hit": result.get("keywords_hit", jd_keywords[:8]),
                "match_score": int(result.get("match_score", 0)),
                "provider": provider,
            }

    return _rule_based(job_title, jd_keywords, cv_skills, user_cv, company)


def _rule_based(job_title, jd_kw, cv_skills, user_cv, company) -> dict:
    import hashlib
    import re as _re

    _STOPS = {"the","a","an","is","are","was","were","be","been","have","has","had",
               "do","does","did","will","would","could","should","may","might","shall",
               "to","of","in","for","on","with","at","by","from","as","into","through",
               "during","before","after","between","out","off","over","under","then",
               "once","here","there","when","where","why","how","all","each","every",
               "both","few","more","most","other","some","such","no","nor","not",
               "only","own","same","so","than","too","very","just","because","but",
               "and","or","if","while","about","up","down","this","that","these",
               "those","it","its","current","present","new","old","good","best",
               "great","high","team","work","role","job","position","looking",
               "seeking","hire","apply","join","available","including","based",
               "within","without","across","using","various","provide","manage",
               "support","develop","create","implement","apply","part","full",
               "time","remote","hybrid","anywhere","global","international",
               "nigeria","africa","london","usa","uk","canada"}

    skills_list = [s.lower() if isinstance(s, str) else s.get("items", []) for s in (cv_skills or [])]
    if isinstance(skills_list, list) and skills_list and isinstance(skills_list[0], list):
        flat = [item for sublist in skills_list for item in sublist]
    else:
        flat = skills_list if skills_list else []
    flat = [s for s in flat if isinstance(s, str)]
    matched = [k for k in jd_kw if any(k in s.lower() for s in flat)]
    score = min(100, int(len(matched) / max(len(jd_kw), 1) * 100))
    top = matched[:8] or jd_kw[:5] or flat[:5]
    unique_top = list(dict.fromkeys(top))
    unique_top = [w for w in unique_top if w.lower() not in _STOPS and len(w) > 1]
    if not unique_top:
        unique_top = ["data", "analytics", "reporting"]

    # Deterministic seed from candidate data for template variation
    seed_str = user_cv.get("professional_summary", "") + job_title + company + str(user_cv.get("experience", []))
    seed = int(hashlib.md5(seed_str.encode()).hexdigest(), 16)
    rng_seed = seed

    def rng():
        nonlocal rng_seed
        rng_seed = (rng_seed * 1103515245 + 12345) & 0x7fffffff
        return rng_seed

    # Build grouped skills from taxonomy
    grouped = []
    for gname, ginfo in SKILL_TAXONOMY.items():
        hits = [s for s in unique_top if any(kw in s for kw in ginfo["keywords"])]
        if hits:
            grouped.append({
                "domain": gname,
                "items": hits,
                "description": _describe_group(gname, hits, rng()),
            })
    if not grouped:
        grouped.append({
            "domain": "Data & Analytics",
            "items": unique_top[:6],
            "description": [
                "Built analytical pipelines turning raw data into decision-ready dashboards.",
                "Designed ETL processes that cut reporting latency by 60% and improved data accuracy.",
                "Developed automated reporting systems serving 50+ stakeholders across departments.",
            ][rng() % 3],
        })

    exp_raw = user_cv.get("experience", [])
    exp_out = []
    candidate_achievements = []

    # Filter experience - skip entries where company is missing or malformed
    _INVALID_COMPANY = {"", "present", "none", "na", "n/a", "tbd"}
    valid_exps = []
    for e in exp_raw:
        company_raw = (e.get("company") or "").strip()
        title_raw = e.get("title", "").strip()
        # If company is missing/invalid, try extracting from title (e.g. "Title, CompanyName Date")
        if company_raw.lower() in _INVALID_COMPANY and "," in title_raw:
            parts = title_raw.split(",", 1)
            if len(parts) == 2:
                after_comma = parts[1].strip()
                date_match = _re.search(r'\b(19|20)\d{2}\b', after_comma)
                if date_match:
                    company_raw = after_comma[:date_match.start()].strip().rstrip(",").strip()
                else:
                    company_raw = after_comma
        company_raw = company_raw.strip().rstrip(",").strip()
        # Strip trailing date artifacts like "May 2024" or "July-August 2019"
        _MONTHS = r'(?:January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Oct|Nov|Dec)'
        company_raw = _re.sub(
            r'\s+' + _MONTHS + r'[-\s]*(?:\d{4})?.*$', '', company_raw, flags=_re.IGNORECASE
        )
        company_raw = company_raw.strip().rstrip(",").strip()
        if not company_raw or company_raw.lower() in _INVALID_COMPANY or len(company_raw) < 2:
            continue
        valid = dict(e)
        valid["company"] = company_raw
        valid_exps.append(valid)

    for e in valid_exps[:3]:
        end = "Present" if e.get("current") else e.get("end_date", "")
        achievements = e.get("achievements", [])
        if not achievements:
            achievements = _generate_varied_bullets(e.get("description", ""), e.get("title", ""), unique_top, rng)
        else:
            achievements = list(achievements)
            for i in range(len(achievements) - 1, 0, -1):
                j = rng() % (i + 1)
                achievements[i], achievements[j] = achievements[j], achievements[i]
            achievements = achievements[:7]

        if achievements:
            ach_text = achievements[0]
            if len(ach_text) > 220:
                cut = ach_text.rfind(" ", 0, 220)
                if cut > 100:
                    ach_text = ach_text[:cut] + "..."
            candidate_achievements.append({
                "company": e.get("company", ""),
                "title": e.get("title", ""),
                "achievement": ach_text,
            })

        exp_out.append({
            "title": e.get("title", ""),
            "company": e.get("company", ""),
            "description": e.get("description", "")[:200],
            "start_date": e.get("start_date", ""),
            "end_date": end,
            "current": e.get("current", False),
            "achievements": achievements[:7],
        })

    top3 = ", ".join(unique_top[:3])
    top2 = ", ".join(unique_top[:2])

    # Generate varied summary from actual experience
    best_achievement = ""
    for e in exp_raw:
        for a in (e.get("achievements", []) or []):
            if any(c.isdigit() for c in a):
                best_achievement = a[:150]
                break
        if best_achievement:
            break

    def _cap_first(s):
        if not s:
            return s
        return s[0].lower() + s[1:]

    if best_achievement:
        ba_mid = _cap_first(best_achievement).rstrip(".").strip()
        if len(ba_mid) > 150:
            cut = ba_mid.rfind(" ", 0, 150)
            if cut > 80:
                ba_mid = ba_mid[:cut] + "..."
        summary_templates = [
            f"{job_title} with proven experience applying {top3} to deliver measurable outcomes. "
            f"Notable achievement: {ba_mid}. "
            f"Combines technical proficiency in {top2} with a structured, methodical approach "
            f"to problem-solving, data quality, and stakeholder communication. "
            f"Consistently produces analysis that drives decisions and improves operational efficiency.",

            f"Results-focused {job_title} with hands-on experience across {top3}. "
            f"Known for {ba_mid}. "
            f"Brings expertise in {top2} to every project, along with a commitment to data accuracy, "
            f"clear reporting, and actionable insights that teams trust and use.",

            f"{job_title} experienced in applying {top3} to solve complex problems and deliver impact. "
            f"Track record includes {ba_mid}. "
            f"Skilled in {top2} with a focused approach to turning raw data into decisions "
            f"that improve outcomes for organisations and the people they serve.",
        ]
    else:
        summary_templates = [
            f"{job_title} with applied experience in {top3}. Combines technical proficiency in {top2} "
            f"with a structured approach to problem-solving, data quality, and stakeholder communication. "
            f"Committed to delivering accurate, actionable analysis that supports better decisions.",
            f"Results-oriented {job_title} with hands-on experience across {top3}. "
            f"Brings expertise in {top2} along with a disciplined approach to data accuracy "
            f"and reporting. Known for producing analysis that stakeholders trust and act on.",
            f"{job_title} experienced in applying {top3} to solve real-world problems. "
            f"Skilled in {top2} and committed to data-driven decision-making. "
            f"Focuses on delivering clear, accurate insights that improve outcomes.",
        ]
    summary = summary_templates[rng() % len(summary_templates)]

    # Helper to format achievement for mid-sentence use
    def _fmt_ach(ach_text):
        text = _cap_first(ach_text).strip(".").strip()
        if len(text) > 150:
            # Truncate at last space before 150
            cut = text.rfind(" ", 0, 150)
            if cut > 80:
                text = text[:cut] + "..."
        return text

    # Generate varied cover letter using candidate's actual experience
    if candidate_achievements:
        ach1 = candidate_achievements[0]
        ach1_fmt = _fmt_ach(ach1["achievement"])
        co1 = ach1["company"]
        mid_section = ""
        if len(candidate_achievements) > 1:
            ach2 = candidate_achievements[1]
            ach2_fmt = _fmt_ach(ach2["achievement"])
            co2 = ach2["company"]
            mid_opts = [
                f" At {co2}, I {ach2_fmt}. This dual experience across different contexts taught me "
                f"how to adapt my approach without compromising on depth or accuracy. ",
                f" My earlier work at {co2} reinforced this approach: {ach2_fmt}. "
                f"Each role taught me that data only creates value when it changes how people decide. ",
                f" Earlier, at {co2}, I {ach2_fmt}. "
                f"That experience taught me to work across teams and adapt quickly to new data environments. ",
            ]
            mid_section = mid_opts[rng() % len(mid_opts)]
        cover_templates = [
            f"Your search for a {job_title} who combines technical precision with measurable impact "
            f"directly reflects the work I have been doing. At {co1}, I {ach1_fmt}. "
            f"This is not a one-off \u2014 every analysis I deliver follows the same standard: "
            f"clean data, rigorous methods, and findings that stakeholders actually use to make decisions. "
            f"My proficiency in {top3} means I can contribute from day one, whether the team needs "
            f"ad-hoc insights or a structured reporting framework.{mid_section}"
            f"I would welcome the chance to discuss how my background in data analysis and reporting "
            f"can support your team\u2019s objectives and help drive the outcomes that matter to your organization.",

            f"Most candidates list tools they have used. Let me show you what I have built. "
            f"At {co1}, I {ach1_fmt}. That work did not happen by accident \u2014 it came from "
            f"a structured approach to understanding the data, cleaning it thoroughly, and presenting "
            f"findings in a way that non-technical stakeholders could act on. "
            f"I bring the same discipline to every project, backed by hands-on experience with {top3}.{mid_section}"
            f"I am not looking for a role where I simply run reports. I want to build the systems "
            f"and analyses that help your team make smarter, faster decisions. "
            f"I would welcome a conversation about how my experience fits what you need.",

            f"Your {job_title} role requires someone who can move beyond surface-level reporting "
            f"into analysis that drives real decisions. That has been the focus of my career so far. "
            f"At {co1}, I {ach1_fmt}. I did this by combining technical skills in {top3} "
            f"with a clear focus on what decision-makers actually needed to see.{mid_section}"
            f"I approach every analysis the same way: understand the question first, then build "
            f"the right methodology to answer it. The result is work that gets used \u2014 not filed away. "
            f"I would welcome the opportunity to bring this approach to your organization and contribute "
            f"to the outcomes your team is working toward.",
        ]
    else:
        cover_templates = [
            f"Your need for a {job_title} who can deliver analysis that actually gets used "
            f"aligns with how I have approached every project in my career. "
            f"My work across {top3} has focused on one thing: turning raw information into "
            f"decisions that stick. Whether building dashboards, cleaning messy datasets, "
            f"or designing recurring reports, I prioritise clarity, accuracy, and usefulness. "
            f"I do not just deliver numbers \u2014 I deliver context, so stakeholders know "
            f"what the data means and what to do next. I would welcome a conversation about "
            f"how my experience can support the outcomes your team is driving.",

            f"I am writing because your {job_title} role calls for someone who connects "
            f"analytical depth with practical business judgment. My experience in {top3} "
            f"has been built on that principle: data only matters when it changes how people decide. "
            f"Every dashboard I have built, every dataset I have cleaned, and every report I have "
            f"delivered was designed with that question in mind. I bring the same philosophy "
            f"to your team \u2014 along with the technical skills and process discipline needed "
            f"to produce work that stakeholders trust and act on. I would welcome the chance "
            f"to discuss what I can contribute.",

            f"Most candidates list what they know. I focus on what I have achieved. "
            f"With expertise in {top3}, I have consistently delivered analysis that gets used — "
            f"from dashboards that track KPIs to ad-hoc analyses that reallocate budgets. "
            f"My approach is simple: start with the decision that needs to be made, work backward "
            f"to the data required, and present findings in a way that is immediately actionable. "
            f"I do not believe in reports that sit unread. Every output I produce is designed "
            f"to inform, persuade, or enable action. I would welcome a conversation about "
            f"how I can bring this mindset to your organization.",
        ]
    cover = cover_templates[rng() % len(cover_templates)]

    return {
        "professional_summary": summary,
        "tailored_skills": grouped,
        "tailored_experience": exp_out,
        "cover_letter": cover,
        "keywords_hit": matched[:8],
        "match_score": score,
        "provider": "rule-based",
    }


def _describe_group(domain: str, skills: list, salt: int = 0) -> str:
    templates = {
        "Data Analytics & Engineering": [
            f"Built analytical workflows using {', '.join(skills[:3])} to process and transform data for reporting.",
            f"Applied {', '.join(skills[:3])} to extract, clean, and model data for business intelligence and operational analytics.",
            f"Used {', '.join(skills[:3])} to design data pipelines that reduced processing time and improved reporting accuracy.",
        ],
        "BI & Visualization": [
            f"Created dashboards and visual reports using {', '.join(skills[:3])} to track KPIs and support decision-making.",
            f"Designed interactive visualizations and executive scorecards in {', '.join(skills[:3])} to monitor performance metrics.",
            f"Transformed raw data into actionable dashboards using {', '.join(skills[:3])}, enabling faster stakeholder decisions.",
        ],
        "Cloud & Infrastructure": [
            f"Managed data infrastructure using {', '.join(skills[:3])} for storage, processing, and analytics.",
            f"Deployed and maintained cloud-based data solutions using {', '.join(skills[:3])} to support scalable analytics.",
            f"Architected data workflows on {', '.join(skills[:3])} ensuring reliable data ingestion and transformation.",
        ],
        "Database Management": [
            f"Designed and queried databases using {', '.join(skills[:3])} to support ETL and reporting pipelines.",
            f"Managed relational and non-relational databases in {', '.join(skills[:3])} with a focus on performance and data integrity.",
            f"Built and optimized database schemas and queries using {', '.join(skills[:3])} to support analytics workflows.",
        ],
        "Project Management & Methods": [
            f"Applied {', '.join(skills[:3])} to manage data projects and coordinate cross-functional teams.",
            f"Led project delivery using {', '.join(skills[:3])} methodologies to ensure on-time, on-scope outcomes.",
            f"Coordinated cross-team initiatives using {', '.join(skills[:3])}, balancing stakeholder needs with technical delivery.",
        ],
        "Data Collection & M&E": [
            f"Designed data collection tools using {', '.join(skills[:3])} and tracked indicators across programmes.",
            f"Built M&E frameworks and digital data collection systems using {', '.join(skills[:3])} to support program reporting.",
            f"Developed and deployed data collection instruments in {', '.join(skills[:3])}, ensuring data quality and timely reporting.",
        ],
    }
    choices = templates.get(domain)
    if choices:
        return choices[salt % len(choices)]
    return [f"Proficient in {', '.join(skills[:3])} for data analysis and reporting.",
            f"Skilled in applying {', '.join(skills[:3])} to deliver data-driven insights and operational improvements.",
            f"Experienced in using {', '.join(skills[:3])} to support decision-making and drive measurable outcomes.",
    ][salt % 3]


def _generate_varied_bullets(desc: str, title: str, top_skills: list, rng_func=None) -> list:
    if rng_func is None:
        import random
        rng = lambda: random.randint(0, 1000000)
    else:
        rng = rng_func

    metric_pools = {
        "records": [(f"{v}+", u) for v in [5000, 10000, 25000, 50000, 75000, 100000] for u in ["records", "data points", "entries", "transactions"]],
        "kpis": [(f"{v}+", u) for v in [8, 10, 15, 20, 25] for u in ["KPIs", "metrics", "indicators", "performance measures"]],
        "reports": [(f"{v}+", u) for v in [5, 8, 10, 15, 20] for u in ["reports", "dashboards", "data products", "analytical outputs"]],
        "teams": [(f"{v}+", u) for v in [3, 5, 7, 10, 12] for u in ["cross-functional teams", "stakeholder groups", "departments", "business units"]],
        "accuracy": [(f"{v}%", u) for v in [95, 97, 98, 99] for u in ["accuracy", "completeness", "data integrity", "quality scores"]],
        "time": [(f"{v}x", u) for v in [2, 3, 4] for u in ["faster turnaround", "quicker reporting cycles", "speed improvements"]] + [
                 (f"reduced by {v}%", u) for v in [20, 25, 30, 35, 40, 50] for u in ["processing time", "report generation time", "manual effort"]],
    }

    metric_categories = list(metric_pools.keys())

    def pick_metric(category):
        pool = metric_pools[category]
        return pool[rng() % len(pool)]

    verb_pool = ["Extracted", "Cleaned", "Transformed", "Analysed", "Processed", "Validated",
                 "Reconciled", "Consolidated", "Standardised", "Reviewed", "Audited", "Compiled"]
    build_verbs = ["Built", "Designed", "Developed", "Created", "Deployed", "Launched", "Implemented", "Automated"]
    collab_verbs = ["Partnered with", "Collaborated with", "Worked with", "Coordinated with", "Advised"]
    impact_verbs = ["Improved", "Reduced", "Increased", "Streamlined", "Optimised", "Accelerated", "Enhanced"]

    bullets = []

    # Bullet 1: Data extraction/processing
    rec_val, rec_unit = pick_metric("records")
    skill_str = ", ".join(top_skills[:2])
    verb1 = verb_pool[rng() % len(verb_pool)]
    bullets.append(
        f"{verb1} and transformed {rec_val} {rec_unit} from multiple sources using {skill_str}, "
        f"supporting data-driven decision-making across the organisation."
    )

    # Bullet 2: Quality / cleaning
    acc_val, acc_unit = pick_metric("accuracy")
    verb2 = verb_pool[rng() % len(verb_pool)]
    bullets.append(
        f"{verb2} {rng() % 15 + 10}+ datasets and improved {acc_unit} to {acc_val} through "
        f"standardised validation processes and data quality checks."
    )

    # Bullet 3: Reports/dashboards
    rep_val, rep_unit = pick_metric("reports")
    verb3 = build_verbs[rng() % len(build_verbs)]
    bullets.append(
        f"{verb3} {rep_val} {rep_unit} for leadership and programme teams, "
        f"enabling faster access to critical metrics."
    )

    # Bullet 4: Collaboration
    team_val, team_unit = pick_metric("teams")
    verb4 = collab_verbs[rng() % len(collab_verbs)]
    bullets.append(
        f"{verb4} {team_val} {team_unit} to define data requirements and translate business needs "
        f"into analytical deliverables."
    )

    # Bullet 5: Time impact
    time_val, time_unit = pick_metric("time")
    verb5 = impact_verbs[rng() % len(impact_verbs)]
    bullets.append(
        f"{verb5} {time_val} {time_unit} by introducing automated workflows and template-driven reporting."
    )

    # Bullet 6: Training / capacity building
    verb6 = verb_pool[rng() % len(verb_pool)]
    bullets.append(
        f"{verb6} and documented data processes, training {rng() % 6 + 3} team members "
        f"on best practices for data entry, validation, and reporting."
    )

    # Bullet 7: Stakeholder impact
    kpi_val, kpi_unit = pick_metric("kpis")
    verb7 = impact_verbs[rng() % len(impact_verbs)]
    bullets.append(
        f"Tracked and reported {kpi_val} {kpi_unit} monthly, helping leadership "
        f"identify trends and reallocate resources for maximum impact."
    )

    # Shuffle to avoid same-order on every CV
    shuffled = list(bullets)
    for i in range(len(shuffled) - 1, 0, -1):
        j = rng() % (i + 1)
        shuffled[i], shuffled[j] = shuffled[j], shuffled[i]

    return shuffled


def make_cv_from_scratch(
    raw_text: str,
    target_jobs: list[str],
    target_type: str = "local",
    remote_preferences: dict = None,
    api_keys: dict = None,
) -> dict:
    api_keys = api_keys or {}
    remote = remote_preferences or {}
    targets = ", ".join(target_jobs) if target_jobs else "Not specified"

    if target_type == "international":
        location_guidance = (
            "LOCATION: Use 'Remote / Anywhere' as the location. "
            "Do NOT include Nigeria-specific address or phone format. "
            "Include the candidate's timezone preference: " + remote.get("timezone", "flexible") + ". "
            "If the candidate prefers remote-only work, mention this in the summary."
        )
        personal_fields = (
            "PERSONAL INFO FIELDS:\n"
            "- name: Full Name\n"
            "- email: Professional email (firstname.lastname@gmail.com style)\n"
            "- phone: Country code + number (e.g., +234 800 000 0000)\n"
            "- location: 'City, Country' format, or 'Remote / Timezone'\n"
            "- linkedin: Full LinkedIn URL\n"
            "- website: Portfolio/GitHub URL if applicable, else empty string\n\n"
            "MANDATORY: Do NOT include date of birth, age, gender, marital status, "
            "religion, state of origin, LGA, or photo. These are illegal for recruiters "
            "in the US, UK, Canada, and EU to request and will get the CV rejected."
        )
        context_translation = (
            "TRANSLATE NIGERIAN CONTEXT:\n"
            "- 'NYSC' -> 'Mandatory National Youth Service'\n"
            "- 'WASC'/'WAEC' -> 'High School Diploma'\n"
            "- 'N50,000,000' -> '$65,000 USD' or use percentages\n"
            "- 'Corper' -> 'Youth Service participant'\n"
            "- 'First Bank' -> 'First Bank of Nigeria (top-tier commercial bank)'\n"
            "- Large Nigerian companies may be unknown internationally — add brief context\n\n"
            "VISA/WORK RIGHTS: If the user mentions work authorization, include it clearly. "
            "If not, the recruiter assumes sponsorship is needed."
        )
        format_guidance = (
            "FORMAT: International CV standard (US/UK/Global).\n"
            "- Strictly 1 page for entry-level, 2 pages max for experienced\n"
            "- No photo, no personal details (DOB, age, gender, marital status, religion)\n"
            "- Use globally recognized job titles: 'Software Engineer', not 'Programmer'\n"
            "- Emphasize remote collaboration tools, timezone management, cross-cultural work\n"
            "- Use USD or percentages for metrics\n"
            "- Simple single-column format (ATS-friendly)\n"
        )
    else:
        location_guidance = (
            "LOCATION: Use a Nigerian city (Lagos, Abuja, Port Harcourt, Ibadan, Enugu) as the location. "
            "Include Nigerian phone format (+234 8XX XXX XXXX). "
        )
        personal_fields = (
            "PERSONAL INFO FIELDS:\n"
            "- name: Full Name\n"
            "- email: Professional email\n"
            "- phone: +234 8XX XXX XXXX format\n"
            "- location: 'City, State, Nigeria'\n"
            "- linkedin: Full LinkedIn URL\n"
            "- website: Portfolio URL if applicable, else empty string\n\n"
            "For traditional/government roles: include date of birth and state of origin "
            "in the personal_info as extra fields: 'date_of_birth', 'state_of_origin'. "
            "For tech/multinational roles: leave these out."
        )
        context_translation = ""
        format_guidance = (
            "FORMAT: Nigerian CV standard.\n"
            "- 1-2 pages\n"
            "- Include NYSC as an experience entry if applicable\n"
            "- Nigerian phone format (+234)\n"
            "- Local certifications (ICAN, COREN, HSE, etc.) are highly valued — feature them\n"
            "- Referees: Include 2-3 referees at the end (name, title, company, email, phone)\n"
            "- No photo (unnecessary for most roles)\n"
            "- Bold section headers, single-column, ATS-friendly\n"
        )

    prompt = (
        "You are the world's #1 CV writer for Nigerian professionals targeting both local and global roles. "
        "Your CVs consistently achieve interview rates above 40% because they:\n"
        "1) Beat ATS (Applicant Tracking Systems) with perfect keyword optimization and clean formatting\n"
        "2) Pass the 10-second human scan with F-pattern visual hierarchy\n"
        "3) Use the FORMULA: Action Verb + Task + Result (with metrics) on EVERY bullet point\n"
        "4) Never contain generic phrases that 90% of applicants use\n\n"
        "## UNIQUENESS RULE ##\n"
        "If 10 candidates with similar backgrounds apply for the same role, their CVs must feel distinct. "
        "Lead each section with the most distinctive real achievement first. Vary sentence openings — "
        "never start two bullets with the same verb. Choose different metrics, different examples, "
        "different structures. Avoid any phrase that sounds like a template or fill-in-the-blank. "
        "Every candidate has unique context; find it and feature it.\n\n"
        "## ATS RULES (FOLLOW STRICTLY) ##\n"
        "- Use STANDARD section headings: 'Professional Summary', 'Core Competencies', "
        "'Professional Experience', 'Education', 'Certifications', 'Projects'\n"
        "- Keyword mirroring: if target roles mention 'data analysis', 'project management', use those EXACT phrases\n"
        "- No tables, columns, text boxes, graphics, or icons (ATS cannot parse them)\n"
        "- Single-column layout throughout\n"
        "- Skills must contain keywords the ATS looks for — they must match target roles\n\n"
        "## THE ACHIEVEMENT FORMULA ##\n"
        "Every bullet point in experience MUST follow this pattern: "
        "Accomplished an objective as measured by a specific metric, by taking a specific action.\n\n"
        "WRONG: 'Managed social media accounts.' (duty-listing)\n"
        "WRONG: 'Responsible for customer service.' (duty-listing)\n"
        "RIGHT: 'Grew Instagram engagement by 65% within 6 months through content optimization and audience analysis.'\n"
        "RIGHT: 'Resolved 50+ customer inquiries daily maintaining 95% satisfaction rating.'\n"
        "RIGHT: 'Developed a customer onboarding system that reduced processing time by 30% and improved NPS by 12 points.'\n\n"
        "If you put 'etc.' at the end of a bullet point, delete the bullet point entirely. Every bullet must be specific.\n\n"
        "## CV SAMPLE (use this structure and level of detail) ##\n\n"
        "CONTACT HEADER\n"
        "Lawrence OLADEJI\n"
        "+234 903 881 9790 | Oladeji.lawrence@gmail.com | linkedin.com/in/lawrence-oladeji/\n\n"
        "Professional Summary\n"
        "Skilled data professional with a strong track record of transforming complex datasets into actionable "
        "insights through intuitive dashboards and contributing meaningfully by helping organizations create "
        "and maintain a Monitoring and Evaluation framework. My ability to streamline processes, improve team "
        "efficiency, and deliver clear, data-backed results can bring immediate value to any organization "
        "looking to enhance decision-making and operational effectiveness.\n\n"
        "Core Competencies\n"
        "- Data Collection & Analysis: Extracted data from 14 international and local repositories "
        "(World Bank, WHO, NBS, DHIS2), transforming 56,000+ data points across 45 indicators\n"
        "- Dashboard Development: Built scorecards and PM dashboards in Power BI, Tableau, and Google Sheets\n"
        "- Statistical Analysis: Regression, correlation, predictive modeling, chi-square using Python, R, SPSS\n"
        "- Database Management: PostgreSQL, Google BigQuery, SQL for data extraction and transformation\n\n"
        "Professional Experience\n"
        "Data Analyst, eHealth4everyone, May 2024 - Present\n"
        "- Extracted data from 14 international and local data repositories and sources, including World Bank, "
        "WHO, GHO, NBS, NPC, DHIS2, EMR and others, covering 50+ key health, climate, energy and financial indicators\n"
        "- Replicated quarterly performance scorecards and dashboards in Google Sheets supporting C-suite decision-making\n"
        "- Reviewed, cleaned, and transformed 56,000+ data points across 45 indicators, uploading to Google BigQuery\n"
        "- Trained 6 team members on database design and implementation using PostgreSQL and ERDPlus\n"
        "- Troubleshot and resolved 4 critical PM dashboard issues in Power BI and Tableau\n\n"
        "Education\n"
        "- Master's Degree in Mechanical Engineering, University of Ibadan, 2022/2023\n"
        "- Bachelor's Degree in Mechanical Engineering, Federal University of Agriculture Abeokuta, "
        "[Second Class Upper], 2011 - 2017\n\n"
        "Certifications\n"
        "- Microsoft Azure Fundamental, 2023\n"
        "- Data Monitoring and Evaluation, USAID Global Health e-Learning Center, 2023\n"
        "- Data Visualization with Power BI, LinkedIn Learning, 2021\n\n"
        "END SAMPLE\n\n"
        "## TARGET ROLES ##\n"
        + targets + "\n\n"
        + location_guidance + "\n\n"
        + personal_fields + "\n\n"
        + context_translation + "\n\n"
        + format_guidance + "\n\n"
        "## RAW USER INFORMATION ##\n"
        + (raw_text[:6000] if raw_text else "No information provided. Create a minimal CV template.") + "\n\n"
        "## OUTPUT FORMAT ##\n"
        "Return ONLY valid JSON. No markdown, no explanation, no code fences. Use this exact structure:\n"
        '{\n'
        '  "personal_info": {\n'
        '    "name": "Full Name",\n'
        '    "email": "professional email or empty string",\n'
        '    "phone": "with country code or empty string",\n'
        '    "location": "City, Country" or "Remote / Timezone",\n'
        '    "linkedin": "URL or empty string",\n'
        '    "website": "URL or empty string"\n'
        '  },\n'
        '  "professional_summary": "3-4 sentences. NEVER start with \'I am\' or \'A highly\'. '
        'Start with job title: \'Data Analyst with 4+ years...\' '
        'Sentence 1: title + years + domain. Sentence 2: biggest achievement with metric. '
        'Sentence 3: technical stack. Sentence 4: value you bring them.",\n'
        '  "skills": [\n'
        '    {\n'
        '      "domain": "Group Name (e.g. Data Analytics & Engineering)",\n'
        '      "items": ["Skill1", "Skill2", "Skill3"],\n'
        '      "description": "1-2 sentences showing tool + context + metric outcome. E.g. \'Built ETL pipelines processing 56k+ data points across 45 indicators using Python and SQL.\'"\n'
        '    },\n'
        '    {\n'
        '      "domain": "Next Group Name",\n'
        '      "items": ["Skill4", "Skill5"],\n'
        '      "description": "..."\n'
        '    }\n'
        '  ],\n'
        '  "experience": [\n'
        '    {\n'
        '      "title": "Job Title",\n'
        '      "company": "Company/Organization",\n'
        '      "start_date": "Month YYYY",\n'
        '      "end_date": "Month YYYY or Present",\n'
        '      "current": false,\n'
        '      "achievements": [\n'
        '        "Accomplished a specific objective as measured by a metric, by taking an action — with specific numbers",\n'
        '        "Built/fixed/created/led/increased/reduced/designed/implemented ...",\n'
        '        "4-6 bullets, each using action verbs and metrics"\n'
        '      ]\n'
        '    }\n'
        '  ],\n'
        '  "education": [\n'
        '    {\n'
        '      "degree": "Degree Name",\n'
        '      "institution": "University/School",\n'
        '      "start_date": "YYYY",\n'
        '      "end_date": "YYYY",\n'
        '      "gpa": "optional classification or grade"\n'
        '    }\n'
        '  ],\n'
        '  "certifications": ["Cert Name, Year", ...],\n'
        '  "languages": ["Language (Proficiency)", ...],\n'
        '  "projects": [\n'
        '    {\n'
        '      "name": "Project Name",\n'
        '      "description": "2-3 sentences selling the project: what problem, what tech, what result",\n'
        '      "technologies": ["Tech1", "Tech2"],\n'
        '      "url": "https://..." or empty string\n'
        '    }\n'
        '  ],\n'
        '  "professional_memberships": ["Member1, Org", ...],\n'
        '  "volunteer_experience": [\n'
        '    {\n'
        '      "title": "Role",\n'
        '      "company": "Organization",\n'
        '      "start_date": "YYYY",\n'
        '      "end_date": "YYYY",\n'
        '      "achievements": ["achievement bullet"]\n'
        '    }\n'
        '  ]\n'
        '}\n\n'
        "## CRITICAL RULES ##\n"
        "- Never fabricate information. If missing, use empty string or omit.\n"
        "- CRITICAL: Do NOT invent phone numbers or email addresses. "
        "Leave as empty string \"\" if not provided.\n"
        "- Do NOT include 'References available upon request'.\n"
        "- Do NOT include a photo.\n"
        "- Every achievement must start with an action verb and contain at least one number (%, $, count, time, volume).\n"
        "- Skills must be an array of objects with 'domain', 'items', and 'description'. Each domain groups 3-6 related skills. The description must show tool + context + metric. NOT a flat list, NOT comma-separated.\n"
        "- Experience in reverse chronological order (most recent first).\n"
        "- Summary must NEVER start with 'I am', 'A highly', 'A dedicated', 'An experienced'. "
        "Start directly with the job title.\n"
        "- BANNED WORDS (never use): 'passionate', 'enthusiastic', 'team player', "
        "'detail-oriented', 'results-driven', 'proven track record', 'I believe', 'I think', "
        "'proactive', 'self-starter', 'go-getter', 'synergy', 'leverage' (unless a tool), "
        "'rockstar', 'ninja', 'guru', 'hardworking', 'dedicated', 'motivated'.\n"
        "- If the candidate mentions NYSC, include it as an experience entry with title "
        "'Youth Service Participant (NYSC)'.\n"
        "- For international: translate all Nigerian context — no assumption that foreign "
        "recruiters understand Naira, NYSC, WASC, or local company prestige.\n"
        "- Projects section: each project gets a selling description (problem → tech → result) "
        "and a URL if the user mentioned one.\n"
    )

    raw = _call_any(prompt, api_keys, max_tokens=3000)
    provider = "rule-based"
    if raw:
        provider = "groq" if api_keys.get("groq") else "gemini"
        if provider == "gemini" and api_keys.get("nvidia"):
            provider = "nim"

    if raw:
        result = _parse_json(raw)
        if result:
            result["_generated_for"] = targets
            result["_target_type"] = target_type
            return result, provider

    # Fallback: parse raw text into basic structure
    fallback = {
        "personal_info": {"name": "", "email": "", "phone": "", "location": "", "linkedin": "", "website": ""},
        "professional_summary": "",
        "skills": [],
        "experience": [],
        "education": [],
        "certifications": [],
        "languages": [],
        "projects": [],
        "professional_memberships": [],
        "_generated_for": targets,
        "_target_type": target_type,
    }

    # Try to extract names, emails, phones from raw text
    name_match = re.search(r"(?:My name is |I(?:')?m |I am )([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)", raw_text[:500])
    if name_match:
        fallback["personal_info"]["name"] = name_match.group(1).strip()
    email_match = re.search(r"[\w.+-]+@[\w-]+\.[\w.]+", raw_text)
    if email_match:
        fallback["personal_info"]["email"] = email_match.group()
    phone_match = re.search(r"(\+?\d[\d\s\-().]{7,15})", raw_text)
    if phone_match:
        fallback["personal_info"]["phone"] = phone_match.group().strip()

    # Detect skills mentioned
    skill_set = set()
    for skill in POWER_SKILLS:
        if skill in raw_text.lower():
            skill_set.add(skill.title() if len(skill) > 3 else skill.upper())
    if skill_set:
        fallback["skills"] = sorted(skill_set)[:12]

    # Build summary from available data
    name = fallback["personal_info"]["name"] or "Candidate"
    skill_str = ", ".join(list(skill_set)[:5]) if skill_set else targets
    fallback["professional_summary"] = (
        f"{name} brings practical experience in {skill_str}, "
        f"with a focus on delivering measurable results. "
        f"Combines technical skills with a structured approach to problem-solving "
        f"and a commitment to producing accurate, decision-ready work."
    )

    # Try to extract education
    edu_keywords = ["studied", "university", "college", "degree", "bachelor", "master", "phd", "diploma",
                    "bs", "ba", "ms", "ma", "mba", "b.sc", "m.sc", "b.eng", "m.eng"]
    sentences = re.split(r'[.!?\n]+', raw_text)
    for s in sentences:
        s_lower = s.lower().strip()
        if any(kw in s_lower for kw in edu_keywords) and len(s) > 20:
            # Extract institution name (capitalized words after known keywords)
            for kw in ["at ", "from ", "of "]:
                idx = s_lower.find(kw)
                if idx >= 0:
                    after = s[idx + len(kw):].strip().rstrip(".,")
                    if after:
                        fallback["education"].append({
                            "degree": s.strip()[:100],
                            "institution": after[:80],
                            "start_date": "", "end_date": "",
                        })
                        break
            if fallback["education"]:
                break

    return fallback, provider


def score_job_match(job_title: str, job_description: str, user_cv: dict) -> int:
    skills_str = " ".join(user_cv.get("skills", [])).lower()
    jd_kw = top_keywords(job_description)
    hits = sum(1 for k in jd_kw if k in skills_str)
    return min(100, int(hits / max(len(jd_kw), 1) * 100))
