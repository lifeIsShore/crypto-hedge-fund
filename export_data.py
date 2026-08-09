#!/usr/bin/env python3
"""
export_data.py — Control Tower data export utility
===================================================
Exports all user-owned data from engine_data.db to a versioned JSON bundle.
Safe to run while flask_app.py is running (read-only, no writes).

Usage:
    python export_data.py                        # exports to export_YYYY-MM-DD.json
    python export_data.py --out my_backup.json   # custom filename
    python export_data.py --pretty               # human-readable JSON

What IS exported (user-owned data):
    trades, positions_history, cash_history, override_log,
    signal_queue (all statuses), watchlist, divergence_labels,
    saved_portfolios, performance_history

What is NOT exported (pipeline-derived — re-computed on next run):
    prices, feature_store, fx_rates, signals, alpha_signals,
    model_outputs, price_targets, risk_metrics, pead_setups,
    regime_history*, pipeline_runs, pipeline_logs, data_validation_log,
    reconciliation_log, risk_events, sqlite_sequence
"""

import sqlite3
import json
import argparse
import sys
import os
from datetime import datetime, date
from pathlib import Path

# ── Schema version — bump when adding new export tables or changing format ──
EXPORT_SCHEMA_VERSION = "1.0"

# ── Tables to export, in dependency order ───────────────────────────────────
EXPORT_TABLES = [
    "trades",
    "positions_history",
    "cash_history",
    "override_log",
    "signal_queue",
    "watchlist",
    "divergence_labels",
    "saved_portfolios",
    "performance_history",
]

# ── Tables that exist in DB but are intentionally skipped (logged for clarity)
SKIP_TABLES = [
    "prices",
    "feature_store",
    "fx_rates",
    "signals",
    "alpha_signals",
    "model_outputs",
    "price_targets",
    "risk_metrics",
    "pead_setups",
    "regime_history",
    "regime_history_new",
    "pipeline_runs",
    "pipeline_logs",
    "data_validation_log",
    "reconciliation_log",
    "risk_events",
    "laggard_screen_results",
    "sqlite_sequence",
]


def _find_db() -> Path:
    """Locate engine_data.db relative to this script."""
    here = Path(__file__).parent
    # Support running from root or from tools/ subdir
    for candidate in [here / "engine_data.db", here.parent / "engine_data.db"]:
        if candidate.exists():
            return candidate
    raise FileNotFoundError("engine_data.db not found. Run from the hedge-fund project root.")


def _row_to_dict(cursor, row) -> dict:
    """Convert a sqlite3 row to a dict using cursor description."""
    return {cursor.description[i][0]: val for i, val in enumerate(row)}


def export_db(db_path: Path, pretty: bool = False) -> dict:
    """
    Read user-owned tables from engine_data.db and return a versioned bundle.
    Uses isolation_level=None (autocommit) with read-only URI for safety.
    """
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.row_factory = None  # we'll use _row_to_dict manually

    bundle = {
        "export_schema_version": EXPORT_SCHEMA_VERSION,
        "exported_at": datetime.now().isoformat(),
        "db_path": str(db_path),
        "tables": {},
        "stats": {},
        "skipped_tables": SKIP_TABLES,
    }

    cur = conn.cursor()

    # Validate which tables actually exist (handles fresh DBs with fewer tables)
    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    existing = {r[0] for r in cur.fetchall()}

    for table in EXPORT_TABLES:
        if table not in existing:
            print(f"  [SKIP] {table} — table does not exist in this DB yet", file=sys.stderr)
            bundle["tables"][table] = []
            bundle["stats"][table] = {"rows": 0, "note": "table_missing"}
            continue

        cur.execute(f"SELECT * FROM [{table}]")  # noqa: S608 (internal tool, not user input)
        rows = []
        for raw_row in cur.fetchall():
            row_dict = {cur.description[i][0]: val for i, val in enumerate(raw_row)}
            rows.append(row_dict)

        bundle["tables"][table] = rows
        bundle["stats"][table] = {"rows": len(rows)}
        print(f"  [OK] {table}: {len(rows):,} rows", file=sys.stderr)

    conn.close()
    return bundle


def import_db(bundle: dict, db_path: Path, dry_run: bool = False) -> dict:
    """
    Import a bundle produced by export_db() into engine_data.db.

    Strategy: INSERT OR IGNORE for idempotent re-import.
    Tables are cleared first only if --replace flag is passed (not default).
    Default mode: skip rows that already exist (safe for merge/restore).

    Returns a summary dict with row counts per table.
    """
    schema_ver = bundle.get("export_schema_version", "unknown")
    if schema_ver != EXPORT_SCHEMA_VERSION:
        print(
            f"  [WARN] Schema version mismatch: bundle={schema_ver} "
            f"expected={EXPORT_SCHEMA_VERSION}. Proceeding cautiously.",
            file=sys.stderr,
        )

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    # Ensure target tables exist (idempotent CREATE IF NOT EXISTS)
    _ensure_tables(cur)

    summary = {}
    tables = bundle.get("tables", {})

    for table, rows in tables.items():
        if table not in EXPORT_TABLES:
            print(f"  [SKIP] Unknown table in bundle: {table}", file=sys.stderr)
            continue
        if not rows:
            summary[table] = {"imported": 0, "skipped": 0}
            continue

        # Build INSERT OR IGNORE from the first row's keys
        keys = list(rows[0].keys())
        placeholders = ", ".join("?" * len(keys))
        col_list = ", ".join(f"[{k}]" for k in keys)
        sql = f"INSERT OR IGNORE INTO [{table}] ({col_list}) VALUES ({placeholders})"  # noqa: S608

        imported = 0
        for row in rows:
            values = [row.get(k) for k in keys]
            if not dry_run:
                try:
                    cur.execute(sql, values)
                    if cur.rowcount > 0:
                        imported += 1
                except Exception as e:
                    print(f"  [WARN] {table} row insert failed: {e}", file=sys.stderr)
            else:
                imported += 1  # In dry run, count everything as "would import"

        summary[table] = {"imported": imported, "skipped": len(rows) - imported}
        print(
            f"  {'[DRY]' if dry_run else '[OK]'} {table}: "
            f"{imported} imported, {len(rows) - imported} already existed",
            file=sys.stderr,
        )

    if not dry_run:
        conn.commit()
    conn.close()
    return summary


def _ensure_tables(cur: sqlite3.Cursor):
    """
    Create user-owned tables if they don't exist.
    This allows importing into a fresh DB before flask_app.py has run.
    Schemas must stay in sync with flask_app.py and engine bootstrap.
    """
    statements = [
        """CREATE TABLE IF NOT EXISTS trades (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            date        TEXT,
            ticker      TEXT,
            action      TEXT,
            quantity    REAL,
            price_eur   REAL,
            value_eur   REAL,
            slippage_pct REAL,
            fee_eur     REAL,
            source      TEXT,
            notes       TEXT,
            executed_at TEXT
        )""",
        """CREATE TABLE IF NOT EXISTS positions_history (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            date        TEXT,
            ticker      TEXT,
            quantity    REAL,
            price       REAL,
            value_eur   REAL,
            weight      REAL,
            recorded_at TEXT
        )""",
        """CREATE TABLE IF NOT EXISTS cash_history (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            date        TEXT,
            cash_eur    REAL,
            event_type  TEXT,
            notes       TEXT,
            recorded_at TEXT
        )""",
        """CREATE TABLE IF NOT EXISTS override_log (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            date             TEXT,
            ticker           TEXT,
            model_suggestion TEXT,
            action_taken     TEXT,
            reason           TEXT,
            outcome_30d      REAL,
            outcome_90d      REAL,
            outcome_correct  INTEGER,
            logged_at        TEXT
        )""",
        """CREATE TABLE IF NOT EXISTS signal_queue (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            generated_at     TEXT DEFAULT (datetime('now')),
            ticker           TEXT NOT NULL,
            signal_type      TEXT,
            conviction       REAL,
            short_score      REAL,
            up_proba         REAL,
            auc              REAL,
            rr_ratio         REAL,
            current_price    REAL,
            target_price     REAL,
            stop_price       REAL,
            vol_ann          REAL,
            expires_at       TEXT,
            status           TEXT DEFAULT 'pending',
            reviewed_at      TEXT,
            review_note      TEXT,
            reason_category  TEXT,
            source           TEXT DEFAULT 'ml'
        )""",
        """CREATE TABLE IF NOT EXISTS watchlist (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker           TEXT NOT NULL UNIQUE,
            added_at         TEXT DEFAULT (datetime('now')),
            notes            TEXT,
            side             TEXT DEFAULT 'LONG',
            snap_up_proba    REAL,
            snap_conviction  REAL,
            snap_price       REAL,
            alert_threshold  REAL DEFAULT 0.70
        )""",
        """CREATE TABLE IF NOT EXISTS divergence_labels (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker          TEXT,
            etf_reference   TEXT,
            detected_at     TEXT,
            labeled_at      TEXT,
            window_days     INTEGER,
            etf_return_pct  REAL,
            stock_return_pct REAL,
            divergence_pct  REAL,
            scenario_label  TEXT,
            confidence      REAL,
            notes           TEXT,
            checklist_answers TEXT,
            outcome_30d     REAL,
            outcome_90d     REAL,
            outcome_correct INTEGER
        )""",
        """CREATE TABLE IF NOT EXISTS saved_portfolios (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            name      TEXT,
            tickers   TEXT,
            weights   TEXT,
            objective TEXT,
            metrics   TEXT,
            saved_at  TEXT
        )""",
        """CREATE TABLE IF NOT EXISTS performance_history (
            date                  TEXT PRIMARY KEY,
            portfolio_value_eur   REAL,
            cash_eur              REAL,
            invested_eur          REAL,
            benchmark_value_eur   REAL,
            daily_return_pct      REAL,
            cumulative_return_pct REAL,
            computed_at           TEXT
        )""",
    ]
    for stmt in statements:
        cur.execute(stmt)


def main():
    parser = argparse.ArgumentParser(
        description="Control Tower — export / import user data"
    )
    sub = parser.add_subparsers(dest="cmd")

    # export
    ep = sub.add_parser("export", help="Export user data to JSON bundle")
    ep.add_argument("--out", default=None, help="Output filename (default: export_YYYY-MM-DD.json)")
    ep.add_argument("--pretty", action="store_true", help="Pretty-print JSON (larger file)")
    ep.add_argument("--db", default=None, help="Path to engine_data.db (auto-detected if not set)")

    # import
    ip = sub.add_parser("import", help="Import a JSON bundle into engine_data.db")
    ip.add_argument("file", help="Path to the .json bundle to import")
    ip.add_argument("--db", default=None, help="Path to engine_data.db (auto-detected if not set)")
    ip.add_argument("--dry-run", action="store_true", help="Show what would be imported without writing")

    args = parser.parse_args()

    if args.cmd is None:
        parser.print_help()
        sys.exit(1)

    # Resolve DB path
    try:
        db_path = Path(args.db) if args.db else _find_db()
    except FileNotFoundError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    if args.cmd == "export":
        out_path = Path(args.out) if args.out else Path(f"export_{date.today()}.json")
        print(f"\nExporting from: {db_path}", file=sys.stderr)
        bundle = export_db(db_path, pretty=args.pretty)
        indent = 2 if args.pretty else None
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(bundle, f, indent=indent, default=str, ensure_ascii=False)
        total_rows = sum(s["rows"] for s in bundle["stats"].values())
        print(f"\nDONE: Exported {total_rows:,} rows -> {out_path} ({out_path.stat().st_size // 1024} KB)")

    elif args.cmd == "import":
        in_path = Path(args.file)
        if not in_path.exists():
            print(f"ERROR: File not found: {in_path}", file=sys.stderr)
            sys.exit(1)
        with open(in_path, encoding="utf-8") as f:
            bundle = json.load(f)
        print(f"\nImporting from: {in_path} (schema v{bundle.get('export_schema_version','?')})", file=sys.stderr)
        print(f"Into DB: {db_path}", file=sys.stderr)
        if args.dry_run:
            print("[DRY RUN — no writes will happen]\n", file=sys.stderr)
        summary = import_db(bundle, db_path, dry_run=args.dry_run)
        total_imported = sum(s["imported"] for s in summary.values())
        print(f"\n{'[DRY] Would import' if args.dry_run else 'DONE: Imported'} {total_imported:,} rows total")


if __name__ == "__main__":
    main()
