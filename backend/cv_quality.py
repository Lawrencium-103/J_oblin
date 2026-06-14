import re

PLACEHOLDER_PATTERNS = [
    r"company\s*name", r"\bname\s+of\s+company\b",
    r"\byour\s+company\b", r"\[\w+\]", r"\bplaceholder\b",
    r"\bcompany\b.*\bname\b",
]

CLICHES = [
    "i am excited", "i am writing", "i am confident", "i would be a valuable addition",
    "i am impressed by", "proven track record", "leverage my", "drive business growth",
    "i believe", "i think", "i am passionate", "i am enthusiastic",
    "i am eager", "i am thrilled", "it would be an honor", "i would love to",
    "i am prepared", "i look forward to",
]

THRESHOLDS = {
    "achievement_density": 0.60,
    "bullets_per_role": 3,
    "min_skills": 5,
    "summary_min_words": 30,
    "education_required": False,
}


def _has_metric(text: str) -> bool:
    return bool(re.search(r"\d+%|\$\d+|\d+[kKmMx×+]|\b\d+\b", text))


def _check_achievement_density(experience: list) -> dict:
    bullets = []
    for exp in experience:
        bullets.extend(exp.get("achievements", []))
    if not bullets:
        return {"pass": False, "score": 0.0, "reason": "No achievement bullets found"}
    scored = sum(1 for b in bullets if _has_metric(b))
    ratio = scored / len(bullets)
    return {
        "pass": ratio >= THRESHOLDS["achievement_density"],
        "score": ratio,
        "reason": f"{scored}/{len(bullets)} bullets have metrics ({ratio:.0%})"
    }


def _check_bullet_depth(experience: list) -> dict:
    if not experience:
        return {"pass": False, "score": 0, "reason": "No experience entries"}
    counts = [len(e.get("achievements", [])) for e in experience]
    avg = sum(counts) / len(counts)
    return {
        "pass": avg >= THRESHOLDS["bullets_per_role"],
        "score": avg,
        "reason": f"Average {avg:.1f} bullets per role (need {THRESHOLDS['bullets_per_role']})"
    }


def _check_skills(skills: list) -> dict:
    if not skills:
        return {"pass": False, "score": 0, "reason": "No skills"}
    if isinstance(skills[0], str):
        count = len(skills)
        return {
            "pass": count >= THRESHOLDS["min_skills"],
            "score": count,
            "reason": f"{count} skills listed (need {THRESHOLDS['min_skills']})"
        }
    if isinstance(skills[0], dict):
        all_items = []
        has_all_descriptions = True
        for g in skills:
            items = g.get("items", [])
            all_items.extend(items)
            if not g.get("description", ""):
                has_all_descriptions = False
        count = len(all_items)
        return {
            "pass": count >= THRESHOLDS["min_skills"] and has_all_descriptions,
            "score": count,
            "reason": f"{count} skill items across {len(skills)} groups" + ("" if has_all_descriptions else " — missing descriptions")
        }
    return {"pass": False, "score": 0, "reason": "Unknown skills format"}


def _check_summary(summary: str) -> dict:
    words = len(summary.split()) if summary else 0
    return {
        "pass": words >= THRESHOLDS["summary_min_words"],
        "score": words,
        "reason": f"{words} words (need {THRESHOLDS['summary_min_words']})"
    }


def _check_cover_letter(cover_letter: str) -> dict:
    if not cover_letter:
        return {"pass": False, "score": 0, "reason": "Missing cover letter"}
    lower = cover_letter.lower()
    for pat in PLACEHOLDER_PATTERNS:
        if re.search(pat, lower):
            return {"pass": False, "score": 0, "reason": f"Placeholder text detected: '{pat}'"}
    cliches_found = [c for c in CLICHES if c in lower]
    if cliches_found:
        return {
            "pass": False,
            "score": 0,
            "reason": f"Cliche phrases found: {', '.join(cliches_found[:3])}"
        }
    words = len(cover_letter.split())
    if words < 50:
        return {"pass": False, "score": words, "reason": f"Only {words} words (need 50+)"}
    return {"pass": True, "score": words, "reason": f"{words} words, no cliches"}


def _check_education(education: list) -> dict:
    has = bool(education)
    return {
        "pass": not THRESHOLDS["education_required"] or has,
        "score": 1 if has else 0,
        "reason": "Present" if has else "Missing — required"
    }


CHECKERS = [
    ("achievement_density", _check_achievement_density, "experience"),
    ("bullet_depth", _check_bullet_depth, "experience"),
    ("skills", _check_skills, "skills"),
    ("summary", _check_summary, "professional_summary"),
    ("education", _check_education, "education"),
    ("cover_letter", _check_cover_letter, "cover_letter"),
]


def score_cv_quality(tailored_cv: dict) -> dict:
    scores = {}
    feedback_parts = []
    all_pass = True

    for name, checker, var_name in CHECKERS:
        value = tailored_cv.get(var_name, [])
        result = checker(value)
        scores[name] = {"pass": result["pass"], "score": result["score"], "reason": result["reason"]}
        if not result["pass"]:
            all_pass = False
            feedback_parts.append(f"- {result['reason']}")

    feedback = "\n".join(feedback_parts) if feedback_parts else "All quality checks passed."
    return {"pass": all_pass, "scores": scores, "feedback": feedback}
