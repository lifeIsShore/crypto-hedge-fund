"""
fix_sandbox_cash.py — One-time reconciliation for the sandbox cash-double-count bug.

BACKGROUND (see before-go-live/PROJECT-STATE.md, 2026-08-10 entry):
engine/execution/paper_trader.py originally recorded paper BUY/SELL orders into
the `trades` table but never wrote a matching debit/credit into `cash_history`.
flask_app.py's _live_positions() computes:
    holdings value  <- reconstructed from `trades` (correct)
    cash            <- latest row in `cash_history` (never decremented on BUY)
    total           = holdings value + cash
So every paper BUY inflated the portfolio total by double-counting the cash spent:
once as the new position's market value, once as cash that was never actually
deducted. The bug is already fixed going forward (paper_trader.py now writes
cash_history correctly) — this script repairs the sandbox DB's *existing*,
already-corrupted cash_history rows so the dashboard shows a correct number.

WHAT THIS SCRIPT DOES
1. Backs up sandbox_data.db to sandbox_data.db.bak_<timestamp> before touching anything.
2. Finds the cash balance that existed immediately before the first paper trade
   (i.e. the last non-paper cash_history row, or 0.0 if none exists).
3. Deletes all existing cash_history rows whose event_type starts with 'PAPER_'
   (these are the ones that may be wrong/duplicated/missing debits).
4. Replays every trade with source='paper', in chronological order, applying the
   CORRECT logic (BUY debits cash, SELL credits cash) and inserts one clean
   cash_history row per paper trade.
5. Prints a before/after summary so you can see exactly what changed.

This only touches sandbox_data.db. Your real engine_data.db (and your actual
deposited money) is never read or modified by this script.

USAGE
    python fix_sandbox_cash.py            # apply the fix
    python fix_sandbox_cash.py --dry-run  # show what would change, write nothing
"""
import sqlite3
import shutil
import sys
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).parent.resolve()
DB_PATH = ROOT / "sandbox_data.db"

DRY_RUN = "--dry-run" in sys.argv


def main():
    if not DB_PATH.exists():
        print(f"[FAIL] {DB_PATH} does not exist. Nothing to fix.")
        return 1

    print(f"Target DB: {DB_PATH}")
    print(f"Mode: {'DRY RUN (no changes will be written)' if DRY_RUN else 'APPLY FIX'}")
    print()

    if not DRY_RUN:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = DB_PATH.with_name(f"sandbox_data.db.bak_{stamp}")
        shutil.copy2(DB_PATH, backup_path)
        print(f"[OK] Backed up sandbox DB to {backup_path.name}")

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # ── 1. Snapshot current (buggy) totals for the summary ─────────────────────
    cur.execute("SELECT cash_eur FROM cash_history ORDER BY date DESC, id DESC LIMIT 1")
    row = cur.fetchone()
    old_cash = float(row["cash_eur"]) if row else 0.0

    cur.execute("""
        SELECT ticker, action, SUM(quantity) AS qty_sum
        FROM trades
        WHERE action IN ('BUY','SELL') AND quantity IS NOT NULL
        GROUP BY ticker, action
    """)
    qty_map = {}
    for r in cur.fetchall():
        t, qty = r["ticker"], float(r["qty_sum"] or 0)
        qty_map[t] = qty_map.get(t, 0.0) + qty if r["action"] == "BUY" else qty_map.get(t, 0.0) - qty
    n_held = sum(1 for q in qty_map.values() if q > 1e-8)

    print(f"Before fix: latest cash_history balance = €{old_cash:,.2f}")
    print(f"Open positions from trades table: {n_held}")
    print()

    # ── 2. Find the cash balance just before the first paper trade ─────────────
    cur.execute("SELECT MIN(date) AS d, MIN(id) AS i FROM trades WHERE source='paper'")
    r = cur.fetchone()
    first_paper_date, first_paper_id = r["d"], r["i"]

    if first_paper_date is None:
        print("[INFO] No paper trades found in the trades table. Nothing to reconcile.")
        conn.close()
        return 0

    cur.execute("""
        SELECT cash_eur FROM cash_history
        WHERE (event_type IS NULL OR event_type NOT LIKE 'PAPER_%')
          AND (date < :d OR (date = :d))
        ORDER BY date DESC, id DESC LIMIT 1
    """, {"d": first_paper_date})
    r = cur.fetchone()
    baseline_cash = float(r["cash_eur"]) if r else 0.0

    print(f"First paper trade: {first_paper_date} (trades.id={first_paper_id})")
    print(f"Baseline cash immediately before paper trading began: €{baseline_cash:,.2f}")
    print("  (this is the last non-PAPER_* cash_history row — your real seed/deposit)")
    print()

    # ── 3. Replay all paper trades in order, applying correct debit/credit ─────
    cur.execute("""
        SELECT id, date, ticker, action, value_eur
        FROM trades
        WHERE source = 'paper'
        ORDER BY date ASC, id ASC
    """)
    paper_trades = cur.fetchall()

    running_cash = baseline_cash
    new_rows = []
    for t in paper_trades:
        value = float(t["value_eur"] or 0.0)
        if t["action"] == "BUY":
            running_cash -= value
            event = "PAPER_BUY_DEBIT"
        elif t["action"] == "SELL":
            running_cash += value
            event = "PAPER_SELL_CREDIT"
        else:
            continue
        new_rows.append((
            t["date"], round(running_cash, 4), event,
            f"[reconciled] paper {t['action']} {t['ticker']} €{value:.2f}"
        ))

    new_cash = round(running_cash, 4)
    holdings_value_from_trades = None  # unchanged by this script — trades table already correct

    print(f"Replayed {len(paper_trades)} paper trades.")
    print(f"After fix: cash would be = €{new_cash:,.2f}")
    print(f"Change in cash line: €{new_cash - old_cash:,.2f}")
    print()

    if DRY_RUN:
        print("[DRY RUN] No changes written. Re-run without --dry-run to apply.")
        conn.close()
        return 0

    # ── 4. Apply: delete old PAPER_* rows, insert corrected ones ───────────────
    cur.execute("DELETE FROM cash_history WHERE event_type LIKE 'PAPER_%'")
    cur.executemany("""
        INSERT INTO cash_history (date, cash_eur, event_type, notes)
        VALUES (?, ?, ?, ?)
    """, new_rows)
    conn.commit()
    conn.close()

    print("[OK] cash_history reconciled.")
    print(f"[OK] Reload the dashboard — cash should now read approximately €{new_cash:,.2f}")
    print("     (total portfolio value = this cash figure + current holdings value)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
