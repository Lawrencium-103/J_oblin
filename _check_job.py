import sys
sys.path.insert(0, ".")
from backend.database import get_db
with get_db() as conn:
    r = conn.execute(
        "SELECT id, title, company, source, board_category, job_category, match_score, description "
        "FROM global_jobs WHERE title LIKE ? AND company LIKE ?",
        ("%Data Analyst%", "%eHealth%")
    ).fetchone()
    if r:
        print(f"ID: {r[0]}")
        print(f"Title: {r[1]}")
        print(f"Company: {r[2]}")
        print(f"Source: {r[3]}")
        print(f"Board category: {r[4]}")
        print(f"Job category: {r[5]}")
        print(f"Match score: {r[6]}")
        desc = r[7] or "(none)"
        print(f"Description (first 300): {desc[:300]}")
    else:
        print("Not found")
        rows = conn.execute(
            "SELECT id, title, company FROM global_jobs WHERE company LIKE ?",
            ("%eHealth%",)
        ).fetchall()
        if rows:
            for row in rows:
                print(f"  Found: ID={row[0]}, Title={row[1]}, Company={row[2]}")
        else:
            print("No jobs with 'eHealth' in company name either")
