"""
Extract CV data from Joblin's database for use with the joblin-cv skill.

Usage:
    python extract_cv.py [user_id]

If user_id is omitted and only one user exists, that user is used.
If the DB is empty or no user has a CV, you'll be prompted to paste CV JSON.
"""

import json
import sqlite3
import sys
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "backend" / "joblin.db"


def get_users():
    if not DB_PATH.exists() or DB_PATH.stat().st_size == 0:
        return []
    conn = sqlite3.connect(str(DB_PATH))
    try:
        cur = conn.execute("SELECT id, email FROM users ORDER BY id")
        return cur.fetchall()
    except sqlite3.OperationalError:
        return []
    finally:
        conn.close()


def get_cv_json(user_id: int) -> str | None:
    conn = sqlite3.connect(str(DB_PATH))
    try:
        row = conn.execute(
            "SELECT cv_json FROM user_cv WHERE user_id = ?", (user_id,)
        ).fetchone()
        return row[0] if row else None
    except sqlite3.OperationalError:
        return None
    finally:
        conn.close()


def main():
    users = get_users()

    if not users:
        print("Database is empty or has no users.")
        print("Paste your CV JSON below (then Ctrl+Z then Enter, or Ctrl+D):")
        raw = sys.stdin.read().strip()
        if raw:
            print("\n--- CV JSON ---")
            print(raw)
        else:
            print("No input provided.")
        return

    user_id = None
    if len(sys.argv) > 1:
        user_id = int(sys.argv[1])
    elif len(users) == 1:
        user_id = users[0][0]
    else:
        print("Available users:")
        for uid, email in users:
            print(f"  {uid}: {email}")
        user_id = int(input("Enter user id: "))

    cv = get_cv_json(user_id)
    if not cv:
        print(f"No CV found for user {user_id}.")
        return

    try:
        parsed = json.loads(cv)
        print(json.dumps(parsed, indent=2, ensure_ascii=False))
    except json.JSONDecodeError:
        print(cv)


if __name__ == "__main__":
    main()
