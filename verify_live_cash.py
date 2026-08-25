"""
verify_live_cash.py — read-only check on the REAL engine_data.db (not sandbox).
Writes a plain-text summary to live_verification.txt. Makes no changes.
"""
import sqlite3
from pathlib import Path

ROOT = Path(__file__).parent.resolve()
DB_PATH = ROOT / "engine_data.db"
OUT_PATH = ROOT / "live_verification.txt"

lines = []
def log(s=""):
    lines.append(s)

conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

log("=== LIVE (engine_data.db) CASH VERIFICATION ===")
log(f"DB: {DB_PATH}")
log()

# All cash_history rows (chronological) so we can see every deposit/trade event
cur.execute("SELECT date, cash_eur, event_type, notes FROM cash_history ORDER BY date ASC, id ASC")
rows = cur.fetchall()
log(f"cash_history rows: {len(rows)}")
log("--- Full cash_history ledger ---")
for r in rows:
    log(f"  {r['date']}  cash_eur={r['cash_eur']:.2f}  event={r['event_type']}  notes={r['notes']}")
log()

# Deposits total (from trades table, action=DEPOSIT — matches /api/performance logic)
cur.execute("SELECT date, ticker, action, quantity, price_eur, value_eur, fee_eur, notes, source FROM trades ORDER BY date ASC, id ASC")
trade_rows = cur.fetchall()
total_deposited = sum(float(t["value_eur"] or 0) for t in trade_rows if t["action"] == "DEPOSIT")
total_dividends = sum(float(t["value_eur"] or 0) for t in trade_rows if t["action"] == "DIVIDEND")
log(f"Total deposited (trades.action='DEPOSIT'): EUR {total_deposited:,.2f}")
log(f"Total dividends: EUR {total_dividends:,.2f}")
log()
log("--- All DEPOSIT/WITHDRAWAL/FEE/DIVIDEND rows in trades table ---")
for t in trade_rows:
    if t["action"] in ("DEPOSIT", "WITHDRAWAL", "FEE", "DIVIDEND"):
        log(f"  {t['date']}  {t['action']}  value_eur={t['value_eur']}  fee_eur={t['fee_eur']}  notes={t['notes']}  source={t['source']}")
log()

# Reconstructed holdings value (same logic as flask_app.py's _live_positions)
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

log("--- Reconstructed holdings (BUY/SELL from trades table) ---")
total_holdings_value = 0.0
for t, q in qty_map.items():
    cur.execute("SELECT adj_close, currency FROM prices WHERE ticker = :t ORDER BY date DESC LIMIT 1", {"t": t})
    pr = cur.fetchone()
    price = float(pr["adj_close"]) if pr and pr["adj_close"] is not None else None
    if price is not None:
        val = q * price
        total_holdings_value += val
        log(f"  {t}: qty={q:.4f} last_price={price:.2f} value_eur~={val:.2f}")
    else:
        log(f"  {t}: qty={q:.4f} (no price found)")

log()
cash_eur = float(rows[-1]["cash_eur"]) if rows else 0.0
log(f"Latest cash_eur (last cash_history row): EUR {cash_eur:,.2f}")
log(f"Sum of holdings value (approx): EUR {total_holdings_value:,.2f}")
log(f"Approx total portfolio value: EUR {total_holdings_value + cash_eur:,.2f}")
log()
log(f"Deposited - (Holdings + Cash) = EUR {total_deposited - (total_holdings_value + cash_eur):,.2f}  (should be roughly 0 minus fees, plus/minus gains/losses)")

conn.close()
with open(OUT_PATH, "w", encoding="utf-8") as f:
    f.write("\n".join(lines))
print(f"Wrote {OUT_PATH}")
