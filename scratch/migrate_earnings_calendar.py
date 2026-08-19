"""
Apply earnings_calendar migration to both engine_data.db and sandbox_data.db.
Safe to run multiple times -- uses IF NOT EXISTS.
"""
import sqlite3
import os

ROOT = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(ROOT, '..'))

DDL = """
CREATE TABLE IF NOT EXISTS earnings_calendar (
    ticker           TEXT NOT NULL,
    report_date      TEXT NOT NULL,
    report_time      TEXT,
    eps_estimate     REAL,
    revenue_estimate REAL,
    fetched_at       TEXT DEFAULT (datetime('now')),
    PRIMARY KEY (ticker, report_date)
);
CREATE INDEX IF NOT EXISTS idx_earnings_date ON earnings_calendar (report_date);
"""

for db_name in ('engine_data.db', 'sandbox_data.db'):
    db_path = os.path.join(ROOT, db_name)
    if not os.path.exists(db_path):
        print(f"SKIP: {db_name} not found")
        continue
    conn = sqlite3.connect(db_path)
    conn.executescript(DDL)
    conn.commit()
    tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
    conn.close()
    status = "OK" if 'earnings_calendar' in tables else "FAIL"
    print(f"{status}: {db_name}")
