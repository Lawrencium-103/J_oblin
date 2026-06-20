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


FALLBACK_MODELS = [
    "openrouter/free",
    "meta-llama/llama-3.1-70b-instruct:free",
    "microsoft/phi-4:free",
]


def _call_openrouter(prompt: str, api_key: str, max_tokens: int = 512) -> str | None:
    if not api_key:
        return None
    for model in FALLBACK_MODELS:
        for attempt in range(2):
            try:
                resp = _req.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                        "HTTP-Referer": "http://localhost:8002",
                    },
                    json={
                        "model": model,
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
                if resp.status_code != 200:
                    print(f"[llm/openrouter] {model} returned {resp.status_code}, trying next model")
                    break
                try:
                    data = json.loads(raw)
                except json.JSONDecodeError:
                    print(f"[llm/openrouter] {model} JSON parse error, trying next model")
                    break
                if "choices" not in data:
                    print(f"[llm/openrouter] {model} unexpected response: {str(data)[:100]}, trying next model")
                    break
                return data["choices"][0]["message"]["content"]
            except Exception as e:
                if attempt < 1:
                    import time as _t
                    _t.sleep(2)
                    continue
                print(f"[llm/openrouter] {model} failed ({type(e).__name__}: {e}), trying next model")
                break
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
    has_any = any(v for v in api_keys.values())
    if not has_any:
        print("[llm] No API keys available — will use rule-based fallback")
    result = _call_groq(prompt, api_keys.get("groq", ""), max_tokens)
    if result: return result
    result = _call_openrouter(prompt, api_keys.get("nvidia", ""), max_tokens)
    if result: return result
    result = _call_gemini(prompt, api_keys.get("gemini", ""), max_tokens)
    if result: return result
    result = _call_gemma(prompt, api_keys.get("gemini", ""), max_tokens)
    if not result and has_any:
        print("[llm] All providers failed -- falling back to rule-based")
    return result


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
    raw_text: str = "",
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
        "## UNIQUENESS DIRECTIVE — ANTI-SLOP ##\n"
        "CRITICAL: If 10 candidates with similar backgrounds apply to this same role, "
        "their CVs MUST look completely different — different examples, different sentence structures, "
        "different metrics emphasized, different skills highlighted. You must find and lead with "
        "what makes THIS candidate distinct. AI-generated templates are obvious and rejected instantly.\n\n"
        "EVERY output will be checked for AI-slop patterns. If detected, the output will be discarded.\n\n"
        "Concrete rules:\n"
        "- Vary sentence openings. Do not start two bullets with the same verb.\n"
        "- Never use the same example or metric as another candidate would.\n"
        "- Lead each bullet with the candidate's most distinctive specific achievement first, "
        "not a generic duty.\n"
        "- Avoid common resume patterns. No 'responsible for', 'tasked with', 'duties included'.\n"
        "- Inject specific project names, tools, methodologies, and contexts from the real data.\n"
        "- The summary must feel like a real person wrote it — not a template.\n"
        "- If the candidate has numbers (%, $, time), ALWAYS include them. Never round to a generic number.\n"
        "- Every sentence must contain at least one specific fact that could not apply to another candidate.\n\n"
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
        + (
            f"\n## RAW CV TEXT ##\n{raw_text[:4000]}\n## END RAW CV TEXT ##\n\n"
            "The raw text above may contain additional experience entries, education, and skills "
            "NOT present in the structured sections. You MUST extract ALL experience entries from "
            "the raw text and include them as proper 'tailored_experience' entries with title, "
            "company, and 4-7 achievement bullets each. Do NOT leave any role mentioned in raw text "
            "as unstructured text in the summary — create a full experience entry for it.\n"
            if raw_text else ""
        )
        + cert_boost
        + transferable_boost
        + bridging_suggestions
        + feedback_section
        + "\n\n## DATA INTEGRITY — ABSOLUTELY CRITICAL ##\n"
        + "- NEVER change or fabricate dates. Use exact dates from source data. Empty string if missing.\n"
        + "- NEVER fabricate achievements, numbers, metrics, outcomes, project names, tools, or methodologies.\n"
        + "- You may rephrase/polish existing achievements for JD relevance, but every factual claim must trace to source data.\n"
        + "- If source data has 0 achievements for a role → output []. Do not generate fake ones.\n"
        + "- If source data has 2 achievements → output those 2 (rewritten). Do not add a 3rd.\n"
        + "- This candidate's integrity depends on you. Fabrications get them rejected or fired.\n"
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
        + '      "start_date": "(original start date — do not change, empty string if missing)",\n'
        + '      "end_date": "(original end date — do not change, empty string if missing)",\n'
        + '      "current": false,\n'
        + '      "description": "(1-line rewritten to highlight JD-relevant impact, or empty string)",\n'
        + '      "achievements": ["(only real achievements from source data, rewritten for relevance)"]\n'
        + '    }\n'
        + '  ],\n'
        + (
            '  "cover_letter": "450-600 word cover letter. '
            'See dedicated COVER LETTER section below for structure and rules."'
        )
        + '  "keywords_hit": ["kw1","kw2","kw3","kw4","kw5"],\n'
        + '  "match_score": 85\n'
        + '}\n\n'
        + "## COVER LETTER — NARRATIVE FLOW (MANDATORY) ##\n"
        + "450-600 WORDS. 4-5 PARAGRAPHS. THIS IS A FULL-PAGE PROFESSIONAL DOCUMENT. "
        + "Under 400 words will be rejected.\n\n"
        + "The cover letter must read as ONE coherent argument — not five separate paragraphs. "
        + "Each paragraph must end with a sentence that naturally leads into the next. "
        + "The reader should feel a logical thread from opening to close.\n\n"
        + "### Narrative Arc ###\n"
        + "Paragraph 1 — Hook & Context (3-4 sentences):\n"
        + "  Sentence 1: Open with something specific about the company — their product, a recent milestone, a problem "
        + "they're solving, or their mission. NOT a greeting. NOT who you are. Something that proves you read beyond the JD.\n"
        + "  Sentence 2-3: Connect that company context to your own experience. 'This matters to me because at X I saw Y...'\n"
        + "  Sentence 4: State the role and your value proposition in one line. This sentence should end with a natural "
        + "bridge to your strongest achievement (e.g. '...experience I would bring directly to this role').\n\n"
        + "Paragraph 2 — Deep Evidence (4-5 sentences):\n"
        + "  Open with your single most relevant achievement. Company name + what you did + tool/method + "
        + "measurable outcome. Connect it to a specific JD requirement.\n"
        + "  Middle sentences: Add context — scope, scale, complexity. Numbers everywhere.\n"
        + "  Last sentence: Transition to breadth. 'Beyond this, I also bring...' or 'This is complemented by my experience in...'\n\n"
        + "Paragraph 3 — Breadth & Range (3-4 sentences):\n"
        + "  A second achievement from a different angle (technical depth vs. leadership vs. problem-solving). "
        + "It does NOT need to be a different company — it needs a different skill set or context.\n"
        + "  Include: what you did, the outcome, and why it matters for THIS role.\n"
        + "  Last sentence: Pivot to what makes you unique. 'What sets me apart is...' or 'Beyond these results, I also bring...'\n\n"
        + "Paragraph 4 — What Makes You Different (2-3 sentences):\n"
        + "  Name the specific combination of skills, domain expertise, or perspective that no other candidate has. "
        + "Tie it directly to a company need from the JD. Show why your particular mix fits their particular context.\n"
        + "  Last sentence: Lead into close. 'I would welcome the chance to discuss...'\n\n"
        + "Paragraph 5 — Close (1-2 sentences):\n"
        + "  Name something specific you'd discuss — reference the company's project, challenge, or goal from P1. "
        + "This closes the loop. Make it clear you're ready to talk specifics, not just available for an interview.\n"
        + "  Sign: 'Best regards,' or 'Sincerely,' on its own line, then candidate name on next line.\n\n"
        + "### Anti-Slop Rules ###\n"
        + "BANNED: 'I am excited', 'I am writing to apply', 'I am confident', 'I am impressed by', "
        + "'I would be a valuable addition', 'I believe I am the ideal candidate', 'It is with great enthusiasm', "
        + "'leverage', 'synergy', 'proven track record', 'drive business growth', 'equipped me with', "
        + "'passionate', 'enthusiastic', 'team player', 'detail-oriented', 'results-driven', 'proactive', "
        + "'self-starter', 'go-getter', 'rockstar', 'ninja', 'guru', 'hardworking', 'dedicated', 'motivated', "
        + "'cutting-edge', 'state-of-the-art', 'world-class', 'best-in-class', 'think outside the box', "
        + "'low-hanging fruit', 'move the needle', 'game-changer', 'in today competitive landscape', 'dynamic environment'.\n"
        + "If any banned phrase appears, the letter is rejected.\n\n"
        "## CRITICAL RULES ##\n"
        "- 'tailored_skills' MUST be an ARRAY OF OBJECTS with 'domain', 'items', 'description'. "
         "Each domain groups 3-6 related skills. Each domain has a 1-2 sentence description showing context + metrics. "
         "Aim for 3-5 domain groups covering ALL candidate skills relevant to the job. "
         "CRITICAL: Reference the candidate's REAL PROJECTS from the Projects section in the descriptions. "
         "E.g. if the candidate built a Power BI retail analysis dashboard, mention it as evidence of BI skill. "
         "Do not just list tools — show what was built with them.\n"
         "- 'tailored_experience': same title/company/dates as original. NEVER change dates. "
           "Rewrite achievements to be JD-relevant, but use ONLY real facts from source data. "
           "CRITICAL: EVERY bullet must demonstrate relevance to the target job description. If the original work "
           "was in a different domain, reframe it to highlight transferable skills. Show how past work prepared "
           "the candidate for THIS specific role. "
           "Output as many achievements as exist in source data — do NOT fabricate new ones. "
           "Zero-bullet roles: output empty achievements array []. "
           "EVERY bullet must have at least one number (%, $, time saved, volume) if the source data includes one.\n"
         "- EDUCATION RULE: Never put a professional summary, career objective, or personal statement in the "
         "education field. Education entries MUST be degree + institution pairs only "
         "(e.g. 'BSc in Computer Science, University of Lagos'). If you have no proper education data, "
         "output an empty array []. Never guess or fabricate education.\n"
          "- Summary must directly reference keywords from the JD. Must be 40+ words.\n"
          "- Cover letter BANNED FOREVER: 'I am excited', 'I am writing to apply', 'I am confident', 'proven track record', "
         "'I believe', 'I would be a valuable addition', 'I am impressed by', 'leverage my', 'drive business growth', "
         "'passionate', 'enthusiastic', 'team player', 'detail-oriented', "
         "'results-driven', 'proactive', 'self-starter', 'go-getter', "
         "'synergy', 'leverage' (unless a tool), "
         "'rockstar', 'ninja', 'guru', 'hardworking', 'dedicated', 'motivated', "
         "'cutting-edge', 'state-of-the-art', 'world-class', 'best-in-class', "
         "'holistic', 'robust' (unless describing actual infrastructure), "
         "'think outside the box', 'low-hanging fruit', 'move the needle', 'game-changer', "
         "'in today competitive landscape', 'dynamic environment'.\n"
         "These are AI slop cliches that instantly disqualify you. Every word must earn its place.\n"
        "- Match score: honest 0-100 based on keyword overlap between JD and tailored output.\n"
        "- Never fabricate phone numbers or email addresses.\n"
        "- No 'References available upon request'.\n"
         "- 'keywords_hit': exactly the subset of JD keywords that appear in the tailored CV.\n"
    )

    raw = _call_any(prompt, api_keys, max_tokens=4000)
    if raw and api_keys.get("groq"):
        provider = "groq"
    elif raw and api_keys.get("nvidia"):
        provider = "openrouter"
    elif raw and api_keys.get("gemini"):
        provider = "gemini"
    else:
        provider = "rule-based"

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

    # Build grouped skills from taxonomy — ensure at least 3 groups
    grouped = []
    scored_groups = []
    for gname, ginfo in SKILL_TAXONOMY.items():
        jd_hits = [s for s in unique_top if any(kw in s for kw in ginfo["keywords"])]
        cv_hits = [s for s in flat if any(kw in s for kw in ginfo["keywords"])]
        score = len(jd_hits) * 2 + len(cv_hits)
        if jd_hits or cv_hits:
            items = jd_hits[:6] if jd_hits else cv_hits[:6]
            scored_groups.append((score, gname, items))
    scored_groups.sort(key=lambda x: -x[0])
    for _, gname, items in scored_groups:
        grouped.append({
            "domain": gname,
            "items": items,
            "description": _describe_group(gname, items, rng()),
        })
    # Fill to at least 3 groups with best-matching remaining taxonomy groups
    if len(grouped) < 3:
        fallback_order = [
            "Data Analytics & Engineering", "BI & Visualization", "Database Management",
            "Project Management & Methods", "Data Collection & M&E", "Cloud & Infrastructure",
        ]
        used = {g["domain"] for g in grouped}
        for gname in fallback_order:
            if len(grouped) >= 3:
                break
            if gname not in used:
                ginfo = SKILL_TAXONOMY.get(gname, {})
                kw = ginfo.get("keywords", [])
                relevant = [w for w in flat if any(k in w for k in kw)][:6] or [kw[0]]
                grouped.append({
                    "domain": gname,
                    "items": relevant[:6],
                    "description": _describe_group(gname, relevant[:3], rng()),
                })
    if not grouped:
        grouped.append({
            "domain": "Data & Analytics",
            "items": unique_top[:6] or ["data", "analytics"],
            "description": [
                "Built analytical pipelines turning raw data into decision-ready dashboards.",
                "Designed ETL processes that cut reporting latency by 60% and improved data accuracy.",
                "Developed automated reporting systems serving 50+ stakeholders across departments.",
            ][rng() % 3],
        })

    # Attach relevant projects to skill group descriptions
    projects = user_cv.get("projects", [])
    if projects and grouped:
        project_text = ""
        for p in projects[:4]:
            pname = p.get("name", "")
            pdesc = p.get("description", "")[:200]
            ptechs = ", ".join(p.get("technologies", []))
            if pname:
                project_text += f" Project: {pname} — {pdesc}"
                if ptechs:
                    project_text += f" [{ptechs}]"
        for g in grouped:
            # Check if any project technologies or description match this group's taxonomy
            gname = g.get("domain", "")
            ginfo = SKILL_TAXONOMY.get(gname, {})
            gkws = ginfo.get("keywords", [])
            relevant_project = ""
            for p in projects[:6]:
                pname = p.get("name", "")
                pdesc = (p.get("description", "") or "").lower()
                ptechs = [t.lower() for t in p.get("technologies", [])]
                if any(kw in pdesc or any(kw in pt for pt in ptechs) for kw in gkws):
                    pshort = p.get("description", "")[:120]
                    relevant_project = f" Relevant project: {pname} — {pshort}"
                    break
            if relevant_project:
                g["description"] = g.get("description", "") + relevant_project

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
                best_achievement = a
                break
        if best_achievement:
            break

    def _cap_first(s):
        if not s:
            return s
        return s[0].lower() + s[1:]

    def _truncate_word_boundary(text, max_len=150):
        if len(text) <= max_len:
            return text
        cut = text.rfind(" ", 0, max_len)
        if cut > 80:
            return text[:cut] + "..."
        return text[:max_len-3] + "..."

    if best_achievement:
        ba_mid = _truncate_word_boundary(_cap_first(best_achievement).rstrip(".").strip())
        summary_templates = [
            f"{job_title} who {ba_mid}. "
            f"That work draws on {top3} expertise and a track record of delivering analysis "
            f"that stakeholders actually use. "
            f"Every project starts with the same discipline: understand the question, validate the data, "
            f"then build the right method to answer it.",

            f"{job_title} with a focus on turning data into decisions — {ba_mid}. "
            f"This sits on top of {rng() % 4 + 3} years building dashboards, "
            f"cleaning datasets, and designing reports that decision-makers trust enough to act on. "
            f"The thread through every project is the same: data only matters when it changes what people decide.",

            f"Results-driven {job_title} who {ba_mid}. "
            f"That ability to move from raw data to decision-ready analysis is backed by "
            f"hands-on proficiency in {top3}. "
            f"Every deliverable is built to answer a real question, not just to fill a template.",
        ]
    else:
        summary_templates = [
            f"{job_title} with working experience across {top3}. "
            f"Every project follows the same approach: understand the decision that needs to be made, "
            f"work backward to the data required, and present findings in a way that is immediately actionable. "
            f"No reports that sit unread — every output is designed to inform, persuade, or enable action.",

            f"The work speaks to {top3} capability — but what sets this candidacy apart is a consistent "
            f"focus on outcomes over outputs. Whether building dashboards, cleaning datasets, or "
            f"designing recurring reports, the goal is always the same: deliver insights that actually get used. "
            f"That means knowing the data, knowing the audience, and presenting findings with clarity.",

            f"Hands-on experience with {top3}, applied to real problems with measurable results. "
            f"Data is only valuable when it changes how people decide — and every analysis, dashboard, "
            f"or report produced has been built with that principle in mind. "
            f"Clear, accurate, and built for action.",
        ]
    summary = summary_templates[rng() % len(summary_templates)]

    # Helper to format achievement for mid-sentence use
    def _fmt_ach(ach_text):
        text = _cap_first(ach_text).strip(".").strip()
        return _truncate_word_boundary(text, 150)

    # Generate varied cover letter using candidate's actual experience
    if candidate_achievements:
        ach1 = candidate_achievements[0]
        ach1_fmt = _fmt_ach(ach1["achievement"])
        co1 = ach1["company"]
        ach2_fmt = ""
        co2 = ""
        if len(candidate_achievements) > 1:
            ach2 = candidate_achievements[1]
            ach2_fmt = _fmt_ach(ach2["achievement"])
            co2 = ach2["company"]
        cover_templates = [
            f"I have been following {company}'s work and was particularly drawn to this {job_title} role "
            f"because of the emphasis on using data to drive operational decisions.\n\n"
            f"At {co1}, {ach1_fmt}. This experience demonstrated that the most impactful analysis comes "
            f"not from sophisticated tools alone, but from understanding the specific business question "
            f"and designing the analysis around it.\n\n"
            + (f"Previously at {co2}, {ach2_fmt}. "
               f"Each environment has reinforced the same lesson: context shapes analysis, and "
               f"the best insights come from knowing both the data and the decisions it needs to support.\n\n"
               if ach2_fmt and co2 else "")
            + f"I bring hands-on experience with {top3}, applied consistently to deliver analysis that "
            f"stakeholders trust and act on. I would welcome the opportunity to discuss how my "
            f"experience aligns with the outcomes your team is targeting.",

            f"The {job_title} role at {company} stands out because the description focuses on impact — "
            f"exactly how I have approached every data project in my career.\n\n"
            f"At {co1}, {ach1_fmt}. What made this work effective was clarity about who needed the "
            f"information and what they would do with it. That focus on actionable insights "
            f"has defined every dashboard and report I have delivered.\n\n"
            + (f"At {co2}, {ach2_fmt}. "
               f"Each role has sharpened my ability to translate raw data into clear, "
               f"decision-ready outputs that non-technical stakeholders can act on.\n\n"
               if ach2_fmt and co2 else "")
            + f"My technical toolkit includes {top3}, and I combine these with a focus on "
            f"delivering work that informs real decisions — not just populating reports. "
            f"I would welcome a conversation about how I can contribute to {company}'s objectives.",

            f"Your search for a {job_title} who can turn complex data into clear direction "
            f"aligns directly with how I work.\n\n"
            f"At {co1}, {ach1_fmt}. "
            f"The work involved {top3}, but more importantly, it required understanding "
            f"what would actually move the needle for the business.\n\n"
            + (f"My experience at {co2} reinforced this approach: {ach2_fmt}. "
               f"Whether working with large datasets or targeted analyses, the principle is the same: "
               f"start with the question, build the right method, and present findings so they drive action.\n\n"
               if ach2_fmt and co2 else "")
            + f"I would welcome the opportunity to discuss how my experience and approach "
            f"can support the outcomes your team is working toward.",
        ]
    else:
        cover_templates = [
            f"Your {job_title} role requires someone who can move beyond surface-level reporting into analysis that shapes decisions. "
            f"That focus has defined my career so far.\n\n"
            f"My experience across {top3} has been built on a straightforward principle: data only creates value when it changes what people decide. "
            f"Every dashboard, every report, every dataset cleaned — each one was done with a specific decision in mind. "
            f"I do not believe in analysis that sits unread. Every output I produce is designed to inform, persuade, or enable action.\n\n"
            f"I would welcome a conversation about how my background in data analysis and reporting "
            f"can support your team\u2019s objectives and contribute to the outcomes that matter to your organization.",

            f"Most candidates will list the tools they know. What I want to demonstrate is the work those tools have produced.\n\n"
            f"Across my experience with {top3}, the common thread has been a focus on outcomes over outputs. "
            f"Whether building recurring dashboards, cleaning messy datasets, or designing one-off analyses for leadership, "
            f"every deliverable starts with the same question: who is going to use this, and what will they decide based on it? "
            f"That question keeps the analysis grounded in real decisions, not abstract reporting.\n\n"
            f"I would welcome the opportunity to discuss how I can bring this approach to your organization and contribute "
            f"to the outcomes your team is working toward.",

            f"Your search for a {job_title} who can turn raw data into decisions aligns directly with how I work.\n\n"
            f"With hands-on experience in {top3}, I have consistently delivered analysis that stakeholders trust and act on. "
            f"The method is simple: understand the decision first, then build the analysis around it. "
            f"The result is work that does not just sit in a shared drive — it informs budgets, shifts strategies, and improves programs.\n\n"
            f"I would welcome a conversation about how my experience and approach can contribute to the work your team is doing.",
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
            "Built end-to-end analytical pipelines that ingest, clean, and transform multi-source data into structured models ready for insight generation and decision support.",
            "Applied statistical and programmatic methods to extract, validate, and model datasets, delivering business intelligence and operational analytics at scale.",
            "Designed and maintained data processing systems that reduced manual handling, improved data integrity, and enabled faster delivery of analytical outputs.",
        ],
        "BI & Visualization": [
            "Created dashboards and visual reports that track KPIs, surface trends, and equip leadership with real-time visibility into operational performance.",
            "Designed interactive data products and executive scorecards that monitor critical metrics and support evidence-based decision-making across teams.",
            "Transformed raw datasets into actionable visual narratives, enabling stakeholders to spot patterns, ask better questions, and act on findings quickly.",
        ],
        "Cloud & Infrastructure": [
            "Managed cloud-based data environments for storage, compute, and analytics, ensuring reliable access, security, and cost-efficient scaling.",
            "Deployed and maintained infrastructure that supports data ingestion, transformation, and serving at scale across distributed teams.",
            "Architected data workflows on cloud platforms with automated pipelines, monitoring, and alerting to ensure consistent data availability.",
        ],
        "Database Management": [
            "Designed, queried, and optimized relational and non-relational databases to support analytical ETL pipelines and operational reporting.",
            "Built and maintained database schemas, indexes, and views with attention to query performance, data integrity, and efficient storage.",
            "Managed database environments across the full lifecycle — from schema design through migration, monitoring, and performance tuning.",
        ],
        "Project Management & Methods": [
            "Applied structured project management methodologies to lead data initiatives, coordinate cross-functional teams, and deliver on schedule.",
            "Managed end-to-end delivery of analytical projects, balancing stakeholder requirements, technical constraints, and team capacity.",
            "Facilitated cross-team coordination, requirements gathering, and iterative delivery to ensure analytical outputs aligned with business priorities.",
        ],
        "Data Collection & M&E": [
            "Designed and deployed digital data collection instruments and M&E frameworks that ensured consistent, high-quality field data across programs.",
            "Built indicator tracking systems and results frameworks that connected field-level data collection to program-level reporting and decision-making.",
            "Developed and managed data collection workflows — from instrument design through field deployment, validation, and analysis — ensuring timely and accurate program reporting.",
        ],
    }
    choices = templates.get(domain)
    if choices:
        return choices[salt % len(choices)]
    return ["Proficient in data analysis and reporting with a focus on accuracy, clarity, and actionable insights.",
            "Skilled in delivering data-driven outcomes — from raw data collection through cleaning, analysis, and stakeholder presentation.",
            "Experienced in transforming complex data into clear, decision-ready outputs that support operational and strategic goals.",
    ][salt % 3]


def _generate_varied_bullets(desc: str, title: str, top_skills: list, rng_func=None) -> list:
    if rng_func is None:
        import random
        rng = lambda: random.randint(0, 1000000)
    else:
        rng = rng_func

    skill_str = ", ".join(top_skills[:3]) if top_skills else "data tools"
    role_lower = title.lower() if title else ""

    noun_pool = ["reports", "datasets", "dashboards", "workflows", "data pipelines", "analytical outputs"]
    team_pool = ["colleagues", "team members", "stakeholders", "cross-functional partners"]
    impact_pool = ["reporting turnaround", "data access", "decision-making speed", "team productivity"]

    def pick(items):
        return items[rng() % len(items)]

    def rng_range(lo, hi):
        return rng() % (hi - lo + 1) + lo

    bullets = []

    is_data = any(kw in role_lower for kw in ["data", "analyst", "analytics", "bi", "business intelligence"])
    is_dev = any(kw in role_lower for kw in ["developer", "engineer", "programmer", "software"])
    is_me = any(kw in role_lower for kw in ["monitoring", "evaluation", "m&e", "meal"])
    is_finance = any(kw in role_lower for kw in ["finance", "accounting", "audit"])

    if is_data or is_dev:
        bullets.append(
            f"Used {skill_str} to extract, clean, and analyse data from multiple sources, "
            f"producing {pick(noun_pool)} that supported day-to-day decision-making."
        )
    elif is_me:
        bullets.append(
            f"Applied {skill_str} to collect, validate, and report programme data, "
            f"ensuring timely submission of {pick(noun_pool)} to stakeholders."
        )
    elif is_finance:
        bullets.append(
            f"Used {skill_str} to process and reconcile financial data, "
            f"supporting accurate reporting and analysis."
        )
    else:
        bullets.append(
            f"Used {skill_str} to compile, clean, and present data from day-to-day operations, "
            f"delivering {pick(noun_pool)} that informed team decisions."
        )

    bullets.append(
        f"Built and maintained {pick(noun_pool)} that tracked key metrics, "
        f"enabling {pick(team_pool)} to monitor progress and identify issues early."
    )

    col_team = pick(team_pool)
    bullets.append(
        f"Worked with {col_team} to gather requirements, clarify data needs, "
        f"and deliver analysis that addressed specific business questions."
    )

    bullets.append(
        f"Documented data processes and prepared guides, "
        f"helping newer {pick(team_pool)} get started with standard tools and workflows."
    )

    impact_area = pick(impact_pool)
    bullets.append(
        f"Contributed to improved {impact_area} by streamlining how data was collected, "
        f"validated, and shared across the team."
    )

    if desc and len(desc) > 30:
        clip = desc[:150].rstrip(".").strip()
        bullets.append(
            f"Supported ongoing projects by maintaining accurate records and "
            f"ensuring data quality in line with {clip[:120]}."
        )

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
        "EXTRACT ALL experience entries from the raw text above. Every role mentioned with a title, company, "
        "and dates must become a full experience entry with 4-7 achievement bullets. "
        "Do NOT leave any experience only in the summary — create proper experience entries.\n\n"
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
        "- Every achievement must start with an action verb and contain at least one number (%, $, count, time, volume) if the source data includes one.\n"
        "- CRITICAL: ONLY use achievements/descriptions present in the source data. "
        "You may rephrase for clarity and impact, but NEVER invent new accomplishments, metrics, projects, or outcomes. "
        "If a role has fewer achievements in source data, output what exists. "
        "FABRICATING ACHIEVEMENTS = CANDIDATE BLACKLISTED.\n"
        "- CRITICAL: NEVER change or fabricate dates. Use exact dates from source data. "
        "If start_date or end_date are missing from source, use empty string.\n"
        "- EDUCATION RULE: Never put a professional summary, career objective, or personal statement in the "
        "education field. Education entries MUST be degree + institution pairs only "
        "(e.g. 'BSc in Computer Science, University of Lagos'). If no proper education data exists, output empty array [].\n"
        "- Skills must be an array of objects with 'domain', 'items', and 'description'. Each domain groups 3-6 related skills. The description must show tool + context + metric. Use real project examples from the candidate as evidence in the descriptions. NOT a flat list, NOT comma-separated.\n"
         "- CRITICAL: In the skills descriptions, reference specific project examples (from the Projects section) to demonstrate each skill. E.g. 'Built a Power BI retail sales analysis dashboard that identified 3 underperforming product categories, enabling a 15% margin improvement.'\n"
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
    if raw and api_keys.get("groq"):
        provider = "groq"
    elif raw and api_keys.get("nvidia"):
        provider = "openrouter"
    elif raw and api_keys.get("gemini"):
        provider = "gemini"
    else:
        provider = "rule-based"

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


def parse_cv_text(raw_text: str, api_keys: dict = None) -> dict:
    api_keys = api_keys or {}
    prompt = (
        "You are a CV parser. Extract structured information from the following CV text.\n\n"
        "Output ONLY valid JSON with this exact structure:\n"
        '{\n'
        '  "personal_info": {"name": "", "email": "", "phone": "", "location": "", "linkedin": "", "website": ""},\n'
        '  "professional_summary": "",\n'
        '  "skills": ["Skill1", "Skill2", ...],\n'
        '  "experience": [\n'
        '    {"title": "", "company": "", "start_date": "", "end_date": "", "current": false, "description": "", "achievements": []}\n'
        '  ],\n'
        '  "education": [\n'
        '    {"degree": "", "institution": "", "start_date": "", "end_date": "", "gpa": ""}\n'
        '  ],\n'
        '  "certifications": ["Cert1", ...],\n'
        '  "languages": ["Lang1", ...],\n'
        '  "projects": [{"name": "", "description": "", "technologies": [], "url": ""}],\n'
        '  "volunteer_experience": [],\n'
        '  "professional_memberships": []\n'
        '}\n\n'
        "RULES:\n"
        "- Extract ALL experience entries (each with title, company, dates, and achievements)\n"
        "- Split achievements into individual bullet points\n"
        "- Extract ALL skills mentioned, not just the first few\n"
        "- Extract education entries with degree, institution, dates\n"
        "- If a field is missing from the CV, use empty string or empty array\n"
        "- Do NOT fabricate or guess information not present in the text\n"
        "- Do NOT include 'References available upon request'\n"
        "- Return ONLY valid JSON, no explanation\n\n"
        "CV TEXT:\n" + raw_text[:8000]
    )

    raw = _call_any(prompt, api_keys, max_tokens=3000)
    if raw:
        result = _parse_json(raw)
        if result:
            return result

    # Fallback: basic regex extraction
    cv = {
        "personal_info": {"name": "", "email": "", "phone": "", "location": "", "linkedin": "", "website": ""},
        "professional_summary": "", "skills": [], "experience": [], "education": [],
        "certifications": [], "languages": [], "projects": [],
        "volunteer_experience": [], "professional_memberships": [],
    }
    name_match = re.search(r"(?:^|\n)([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})(?:\n|$)", raw_text[:300])
    if name_match:
        cv["personal_info"]["name"] = name_match.group(1).strip()
    email_match = re.search(r"[\w.+-]+@[\w-]+\.[\w.]+", raw_text)
    if email_match:
        cv["personal_info"]["email"] = email_match.group()
    phone_match = re.search(r"(\+?\d[\d\s\-().]{7,15})", raw_text)
    if phone_match:
        cv["personal_info"]["phone"] = phone_match.group().strip()

    lines = raw_text.split("\n")
    mode = "header"
    for line in lines:
        u = line.strip().upper()
        if not u:
            continue
        if re.match(r"^(SKILLS|CORE COMPETENCIES|TECHNICAL SKILLS)", u):
            mode = "skills"
        elif re.match(r"^(EXPERIENCE|WORK|PROFESSIONAL EXPERIENCE|EMPLOYMENT)", u):
            mode = "experience"
        elif re.match(r"^(EDUCATION|ACADEMIC)", u):
            mode = "education"
        elif re.match(r"^(CERTIFICATION|LICENSES|CERT)", u):
            mode = "certs"
        elif re.match(r"^(PROJECT|PORTFOLIO)", u):
            mode = "projects"
        elif mode == "skills" and not re.match(r"^(SKILLS|CORE|TECHNICAL)", u):
            parts = re.sub(r"^[-\u2022*#]\s*", "", line.strip()).split(",")
            cv["skills"].extend(p.strip() for p in parts if p.strip())
    cv["skills"] = list(dict.fromkeys(s for s in cv["skills"] if s))
    return cv


def score_job_match(job_title: str, job_description: str, user_cv: dict) -> int:
    skills_str = " ".join(user_cv.get("skills", [])).lower()
    jd_kw = top_keywords(job_description)
    hits = sum(1 for k in jd_kw if k in skills_str)
    return min(100, int(hits / max(len(jd_kw), 1) * 100))


def generate_hr_email(
    job_title: str,
    company: str,
    job_description: str,
    candidate_name: str,
    summary: str,
    skills: list,
    experiences: list,
    education: list,
    api_keys: dict,
    target_type: str = "local",
    match_score: int = 0,
    keywords_hit: list | None = None,
) -> str | None:

    jd_keywords = top_keywords(job_description, n=20)

    skills_flat = []
    for s in (skills or []):
        if isinstance(s, dict):
            skills_flat.extend(s.get("items", []))
        elif isinstance(s, str):
            skills_flat.append(s)
    skills_lower = " ".join(skills_flat).lower()
    skills_str = ", ".join(skills_flat[:15])

    matched_kw = []
    if keywords_hit:
        matched_kw = keywords_hit
    else:
        matched_kw = [k for k in jd_keywords if k in skills_lower]

    cv_lower = skills_lower
    related_groups = []
    missing_groups = []
    for group_name, group_info in SKILL_TAXONOMY.items():
        group_mentioned = any(kw in job_description.lower() for kw in group_info["keywords"])
        if group_mentioned:
            candidate_has = any(kw in cv_lower for kw in group_info["keywords"])
            if candidate_has:
                related_groups.append(group_name)
            else:
                missing_groups.append(group_name)

    is_role_switch = False
    past_titles = []
    for e in (experiences or [])[:5]:
        t = e.get("title", "")
        if t:
            past_titles.append(t)
    if past_titles:
        target_lower = job_title.lower()
        is_role_switch = not any(kw in t.lower() for t in past_titles for kw in target_lower.split() if len(kw) > 2)

    exp_matched = []
    for e in (experiences or [])[:5]:
        title = e.get("title", "")
        company_e = e.get("company", "")
        achs = e.get("achievements", [])
        desc = e.get("description", "")
        all_text = f"{title} {desc} {' '.join(achs)}".lower()
        relevant_kws = [k for k in jd_keywords if k in all_text]
        top_ach = achs[0] if achs else desc[:150]
        exp_matched.append({
            "title": title,
            "company": company_e,
            "top_achievement": top_ach[:200],
            "matched_jd_keywords": relevant_kws,
        })

    exp_detail = []
    for e in exp_matched:
        line = f"- {e['title']} @ {e['company']}: {e['top_achievement']}"
        if e["matched_jd_keywords"]:
            line += f"  [JD keywords matched: {', '.join(e['matched_jd_keywords'][:5])}]"
        exp_detail.append(line)
    exp_str = "\n".join(exp_detail) if exp_detail else "No experience data"

    edu_str = "; ".join(
        e.get("degree", e.get("title", "")) for e in (education or [])[:2]
    ) or "Not specified"

    match_context = ""
    if related_groups:
        match_context += f"\nCandidate's skill areas that DIRECTLY match the JD: {', '.join(related_groups)}."
    if missing_groups:
        match_context += f"\nJD skill areas NOT in candidate's CV: {', '.join(missing_groups)}. Do NOT claim these. Reference transferable skills instead."
    if matched_kw:
        match_context += f"\nSpecific JD keywords the candidate has: {', '.join(matched_kw[:12])}."

    transferable_section = ""
    if is_role_switch and past_titles:
        transferable_section = (
            "\n## TRANSFERABLE SKILLS ##\n"
            f"The candidate has never held a '{job_title}' role (past roles: {', '.join(past_titles[:3])}).\n"
            "Map transferable skills from their past work to the JD requirements. "
            "Reference a real achievement and show how the underlying skill applies to this role.\n"
        )

    tone_instruction = (
        "Keep the tone warm, professional, and direct. Be confident but not arrogant."
        if target_type == "local"
        else "Keep the tone polished and globally competitive. Emphasize adaptability and international exposure."
    )

    prompt = (
        "You are a career communications expert writing an outreach email from a job applicant to a hiring manager.\n"
        "This email will be sent directly — it must read like a real person wrote it, not a template.\n\n"

        "## UNIQUENESS DIRECTIVE — ANTI-SLOP ##\n"
        "CRITICAL: This email must sound like a specific human wrote it about their specific experience targeting this specific role. "
        "If 10 candidates with similar backgrounds applied, each email must be clearly different — different openers, different examples, different hooks. "
        "AI-generated patterns are instantly recognizable and get deleted.\n\n"

        "Concrete rules:\n"
        "- Vary sentence openings. No two sentences should start the same way.\n"
        "- Never use a phrase that could appear in any other candidate's email.\n"
        "- Every claim must reference a REAL fact from the candidate data below.\n"
        "- Every skill mentioned must be LINKED to a specific JD requirement — not listed in isolation.\n"
        "- If you mention a tool or method, state WHAT was built/done with it and the OUTCOME.\n"
        "- Numbers, project names, and context make it real. Generic statements make it spam.\n\n"

        "## BANNED PHRASES ##\n"
        "Do NOT use ANY of these — they are instant red flags that mark the email as AI-generated:\n"
        "- Openers: I am excited, I am writing to apply, I am confident, I am impressed by, "
        "I would be a valuable addition, I believe I am the ideal candidate, It is with great enthusiasm, "
        "I came across, I am reaching out\n"
        "- Jargon: leverage, synergy, proven track record, drive business growth, equipped me with, "
        "I believe, in today's competitive landscape, think outside the box, best-in-class, "
        "world-class, end-to-end, deep dive, low-hanging fruit, move the needle, pain point, "
        "game-changer, circle back, holistic, robust, scalable (unless actual tech), value proposition\n"
        "- Buzzwords: passionate, enthusiastic, team player, detail-oriented, results-driven, "
        "proactive, self-starter, go-getter, rockstar, ninja, guru, hardworking, dedicated, motivated\n"
        "- Generic praise: industry-leading, cutting-edge, state-of-the-art, market-leading, dynamic, innovative (unless naming something specific)\n"
        "- Weak endings: I look forward to hearing from you (alone), Thank you for your consideration (alone)\n\n"

        "## EMAIL STRUCTURE — NARRATIVE FLOW ##\n"
        "Line 1: SUBJECT — format exactly: \"Subject: Re: [Job Title] — [Candidate Name]\"\n"
        "Line 2: blank line\n"
        "Line 3: Greeting\n"
        "Line 4: blank line\n\n"
        "Paragraph 1 — The Hook (2-3 sentences):\n"
        "  Sentence 1: THE HOOK. Must stop them from scrolling. Start with a specific observation about the company's "
        "work, a problem from the JD, a recent milestone, or a shared mission connection. NOT who you are. NOT the role.\n"
        "  Sentence 2-3: Connect that company context to your own experience, THEN state your name and the role.\n"
        "  Transition: End this paragraph with a sentence that points toward your evidence "
        "(e.g. 'This is a problem I've solved before.' or 'Here's what I'd bring to that challenge.')\n\n"
        "Paragraph 2 — Your Evidence (2-4 sentences):\n"
        "  Start with your single most relevant achievement. Company + what you did + tool/method + measurable result. "
        "Connect it to the specific JD requirement from your hook.\n"
        "  Add context: scope, scale, complexity. Let the numbers speak.\n"
        "  Last sentence: Transition to breadth. 'I also bring...' or 'Beyond this, my background in...'\n\n"
        "Paragraph 3 — Why You Specifically (2-3 sentences):\n"
        "  A second strength from a different angle — different skill, different context, different tool. "
        "Show range without repeating P2.\n"
        "  End by tying this back to the company's specific need from the JD.\n\n"
        "Closing (1-2 sentences):\n"
        "  Name something specific you'd like to discuss — tie back to the hook from P1 or the achievement in P2. "
        "Close the loop. Make it clear you want to talk about their specific problem, not just get an interview.\n"
        "Sign-off: \"Best\" or \"Best regards\" on its own line, then candidate name on next line.\n\n"

        f"## JD-CV MATCH INTELLIGENCE ##\n"
        f"JD Priority Keywords: {', '.join(jd_keywords)}\n"
        f"Match Score: {match_score or 'N/A'}%\n"
        + match_context
        + transferable_section

        + f"\n\n## CANDIDATE DATA ##\n"
        f"Name: {candidate_name}\n"
        f"Summary: {summary[:600]}\n"
        f"Key Skills: {skills_str}\n"
        f"Education: {edu_str}\n"
        f"Experience (with JD keyword matches):\n{exp_str}\n\n"

        f"## TARGET ROLE ##\n"
        f"Title: {job_title}\n"
        f"Company: {company}\n"
        f"Description: {job_description[:2000]}\n\n"

        f"## RULES ##\n"
        f"- MAX 250 words of body text (excluding subject and sign-off).\n"
        f"- {tone_instruction}\n"
        "- Return ONLY the email text. No JSON. No markdown. No explanation. No code fences.\n"
        "- The subject line must be on the very first line.\n"
    )

    raw = _call_any(prompt, api_keys, max_tokens=800)
    if raw:
        return raw

    # Rule-based fallback
    name = candidate_name or "the candidate"
    top_skills = ", ".join(skills_flat[:5]) if skills_flat else "data analysis and reporting"
    exp_highlights = []
    for e in (experiences or [])[:2]:
        t = e.get("title", "")
        c = e.get("company", "")
        a = (e.get("achievements") or [])[:1]
        if a and a[0]:
            ach_text = a[0].strip().rstrip(".")
            if ach_text:
                ach_text = ach_text[0].upper() + ach_text[1:]
                exp_highlights.append(f"In my role as {t} at {c}, {ach_text}.")
        elif t and c:
            exp_highlights.append(f"In my role as {t} at {c}, I developed and applied skills directly relevant to this position.")
    exp_lines = "\n\n".join(exp_highlights[:2]) if exp_highlights else ""
    summary_text = (summary or "")[:300]

    email_lines = [
        f"Subject: Re: {job_title} \u2014 {name}",
        "",
        f"Dear Hiring Manager,",
        "",
        f"I came across the {job_title} role at {company} and wanted to reach out directly. "
        f"My background in {top_skills} aligns well with what your team is looking for.",
        "",
    ]
    if summary_text:
        email_lines.append(summary_text + "\n")
    if exp_lines:
        email_lines.append(exp_lines + "\n")
    email_lines.append(
        f"I would welcome the opportunity to discuss how my experience can contribute to "
        f"your team\u2019s goals. Happy to provide more details or samples of my work at your convenience."
    )
    email_lines.append("")
    email_lines.append("Best regards,")
    email_lines.append(name)
    return "\n".join(email_lines)
