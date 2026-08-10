"""
verify_sandbox_cash.py — read-only check after running fix_sandbox_cash.py.
Writes a plain-text summary to sandbox_verification.txt so it can be reviewed
without needing to run a SQL client. Makes no changes to the database.
"""
import sqlite3
from pathlib import Path

ROOT = Path(__file__).parent.resolve()
DB_PATH = ROOT / "sandbox_data.db"
OUT_PATH = ROOT / "sandbox_verification.txt"

lines = []

def log(s=""):
    lines.append(s)

conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

log("=== SANDBOX CASH VERIFICATION ===")
log(f"DB: {DB_PATH}")
log()

# Latest cash
cur.execute("SELECT date, cash_eur, event_type, notes FROM cash_history ORDER BY date DESC, id DESC LIMIT 1")
r = cur.fetchone()
if r:
    log(f"Latest cash_history row: date={r['date']} cash_eur={r['cash_eur']:.2f} event_type={r['event_type']}")
else:
    log("No cash_history rows found.")

# Any remaining PAPER_% rows with no matching debit (sanity check count)
cur.execute("SELECT COUNT(*) AS n FROM cash_history WHERE event_type LIKE 'PAPER_%'")
n_paper_rows = cur.fetchone()["n"]
log(f"PAPER_* cash_history rows present: {n_paper_rows}")

cur.execute("SELECT COUNT(*) AS n FROM trades WHERE source='paper'")
n_paper_trades = cur.fetchone()["n"]
log(f"Paper trades in trades table: {n_paper_trades}")

log()
log("--- Reconstructed holdings value (same logic as dashboard's _live_positions) ---")
cur.execute("""
    SELECT ticker, action, SUM(quantity) AS qty_sum
    FROM trades
    WHERE action IN ('BUY','SELL') AND quantity IS NOT NULL
    GROUP BY ticker, action
""")
qty_map = {}
for row in cur.fetchall():
    t, qty = row["ticker"], float(row["qty_sum"] or 0)
    qty_map[t] = qty_map.get(t, 0.0) + qty if row["action"] == "BUY" else qty_map.get(t, 0.0) - qty
qty_map = {t: q for t, q in qty_map.items() if q > 1e-8}

total_holdings_value = 0.0
for t, q in qty_map.items():
    cur.execute("""
        SELECT adj_close FROM prices
        WHERE ticker = :t
        ORDER BY date DESC LIMIT 1
    """, {"t": t})
    pr = cur.fetchone()
    price = float(pr["adj_close"]) if pr and pr["adj_close"] is not None else None
    if price is not None:
        val = q * price
        total_holdings_value += val
        log(f"  {t}: qty={q:.4f} last_price={price:.2f} value_eur={val:.2f}")
    else:
        log(f"  {t}: qty={q:.4f} (no price found)")

log()
log(f"Sum of holdings value (approx, using last known price per ticker): €{total_holdings_value:,.2f}")
cash_eur = float(r["cash_eur"]) if r else 0.0
log(f"Cash: €{cash_eur:,.2f}")
log(f"Approx total portfolio value: €{total_holdings_value + cash_eur:,.2f}")
log()

# Backup files present
import glob
backups = sorted(ROOT.glob("sandbox_data.db.bak_*"))
log(f"Backup files found: {len(backups)}")
for b in backups:
    log(f"  {b.name}")

conn.close()

with open(OUT_PATH, "w", encoding="utf-8") as f:
    f.write("\n".join(lines))

print(f"Wrote {OUT_PATH}")
