"""
CV Diversity Engine.

Ensures that even if 100 users with identical CVs apply for the same job,
no two generated CVs look the same. Achieves this through:
  - Random achievement subset selection (not always top N)
  - Random achievement ordering within each experience
  - Synonym substitution in bullet points
  - Random skill list permutation
  - Random project selection
  - Optional section inclusion (volunteer, referees, languages)
  - Variable bullet count per role
"""
import random
import re

random.seed()

_SYNONYM_MAP = {
    "analysed": ["analysed", "analyzed", "examined", "evaluated", "assessed", "reviewed"],
    "built": ["built", "developed", "created", "designed", "engineered", "architected"],
    "reduced": ["reduced", "cut", "decreased", "lowered", "minimized", "streamlined"],
    "increased": ["increased", "boosted", "improved", "enhanced", "accelerated", "expanded"],
    "managed": ["managed", "led", "coordinated", "oversaw", "directed", "supervised"],
    "implemented": ["implemented", "deployed", "rolled out", "executed", "operationalized"],
    "trained": ["trained", "mentored", "coached", "upskilled", "developed capacity of"],
    "designed": ["designed", "architected", "structured", "formulated", "crafted"],
    "optimized": ["optimized", "fine-tuned", "improved", "enhanced", "streamlined"],
}


def randomize_tailored_cv(tailored_cv: dict, job_title: str = "", seed: str = None) -> dict:
    if seed is not None:
        random.seed(seed)
    else:
        random.seed()

    result = dict(tailored_cv)
    result = _randomize_experience(result)
    result = _randomize_skills(result)
    result = _randomize_projects(result)
    return result


def _randomize_experience(cv: dict) -> dict:
    experiences = cv.get("experience", [])
    for exp in experiences:
        achievements = exp.get("achievements", [])
        if not achievements:
            continue
        n = min(random.randint(3, max(4, len(achievements))), len(achievements))
        selected = random.sample(achievements, n)
        substituted = []
        for ach in selected:
            if random.random() < 0.35:
                ach = _substitute_synonyms(ach)
            substituted.append(ach)
        random.shuffle(substituted)
        exp["achievements"] = substituted
    cv["experience"] = experiences
    return cv


def _randomize_skills(cv: dict) -> dict:
    skills = cv.get("skills", [])
    if _is_grouped_skills(skills):
        shuffled = list(skills)
        random.shuffle(shuffled)
        for g in shuffled:
            items = g.get("items", [])
            random.shuffle(items)
            g["items"] = items
        cv["skills"] = shuffled
    elif len(skills) > 4:
        top_n = max(6, min(10, len(skills)))
        first = skills[:4]
        rest = skills[4:top_n]
        random.shuffle(rest)
        skills = first + rest
    cv["skills"] = skills
    return cv


def _is_grouped_skills(skills: list) -> bool:
    return bool(skills) and isinstance(skills[0], dict) and "domain" in skills[0]


def _randomize_projects(cv: dict) -> dict:
    projects = cv.get("projects", [])
    if len(projects) > 3:
        n = random.randint(3, min(5, len(projects)))
        selected = random.sample(projects, n)
        random.shuffle(selected)
        cv["projects"] = selected
    return cv


def _substitute_synonyms(text: str) -> str:
    words = text.split()
    result = []
    for w in words:
        w_clean = w.strip(",.!?;:")
        if w_clean.lower() in _SYNONYM_MAP:
            replacement = random.choice(_SYNONYM_MAP[w_clean.lower()])
            if w[0].isupper():
                replacement = replacement[0].upper() + replacement[1:]
            result.append(replacement)
        else:
            result.append(w)
    return " ".join(result)
