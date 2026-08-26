"""
better-alpha/gate1_holdout.py
===============================
Gate 1 — Holdout Lock (see 00-OVERVIEW.md).

Read-only. Queries the prices table for the 127th most recent distinct
trading date and writes better-alpha/holdout_config.txt with:
    HOLDOUT_START=YYYY-MM-DD

Run from the repo root:
    python before-go-live/better-alpha/gate1_holdout.py

After this runs, the rule (documented, not code-enforced yet) is:
    feature_builder.py, run_ml_pipeline.py, and all IC evaluation code
    must filter training data to date < HOLDOUT_START until Gate 4.
"""
import os
import sys
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, ROOT)

OUT_PATH = os.path.join(HERE, "holdout_config.txt")


def main():
    if os.path.exists(OUT_PATH):
        print(f"REFUSING TO OVERWRITE: {OUT_PATH} already exists.")
        print(f"Current contents:\n{open(OUT_PATH).read()}")
        print("The holdout period must not move once feature work has begun "
              "against it. If you genuinely need to change it, do so by hand "
              "and note why in this file.")
        sys.exit(1)

    from engine.db.db import get_session
    from sqlalchemy import text

    session = get_session()
    try:
        rows = session.execute(text(
            "SELECT DISTINCT date FROM prices ORDER BY date DESC LIMIT 127"
        )).fetchall()
    finally:
        session.close()

    if len(rows) < 127:
        print(f"Only {len(rows)} distinct dates found in prices table "
              "(need 127). Cannot establish a 126-trading-day holdout yet.")
        sys.exit(1)

    holdout_start = rows[-1][0]  # 127th most recent date

    lines = [
        f"# Gate 1 holdout lock — recorded {date.today().isoformat()}",
        f"HOLDOUT_START={holdout_start}",
        "",
        "# Rule: feature_builder.py, run_ml_pipeline.py, and all IC evaluation",
        "# code must filter training data to date < HOLDOUT_START.",
        "# This window is evaluated exactly once, at Gate 4. Never before.",
    ]
    out = "\n".join(lines) + "\n"

    with open(OUT_PATH, "w", encoding="utf-8") as f:
        f.write(out)

    print("=" * 60)
    print("GATE 1 — holdout locked")
    print("=" * 60)
    print(out)
    print(f"Written to: {OUT_PATH}")


if __name__ == "__main__":
    main()
