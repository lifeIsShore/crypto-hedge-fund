# engine/reconciliation/state_reconciler.py
"""
State reconciliation — compare internal DB to your actual broker positions.
Since Trade Republic has no public API, this uses a manual entry form.
The dashboard shows a side-by-side view: DB positions vs. what you enter from the app.
"""
import pandas as pd
from sqlalchemy import text
from engine.db.db import get_session
import json
import logging

logger = logging.getLogger(__name__)


def get_db_positions() -> pd.DataFrame:
    """Latest positions from internal DB (SQLite-compatible — no DISTINCT ON)."""
    session = get_session()
    result = session.execute(text("""
        SELECT p.ticker, p.quantity, p.price, p.value_eur, p.weight
        FROM positions_history p
        INNER JOIN (
            SELECT ticker, MAX(date) AS max_date
            FROM positions_history
            GROUP BY ticker
        ) latest ON p.ticker = latest.ticker AND p.date = latest.max_date
    """))
    rows = result.fetchall()
    session.close()
    return pd.DataFrame(rows, columns=["ticker", "quantity", "price", "value_eur", "weight"])


def get_db_cash() -> float:
    """Latest cash balance from internal DB."""
    session = get_session()
    result = session.execute(text("""
        SELECT cash_eur FROM cash_history
        ORDER BY date DESC, id DESC
        LIMIT 1
    """))
    row = result.fetchone()
    session.close()
    return float(row[0]) if row else 0.0


def reconcile(broker_positions: dict, broker_cash_eur: float = None) -> dict:
    """
    broker_positions: dict of {ticker: {"quantity": x, "price": y}}
    broker_cash_eur:  cash balance from broker app (optional; pass None to skip cash check)
    Returns reconciliation result + discrepancies.
    Manual entry from Trade Republic app → this function.
    """
    db_df = get_db_positions()
    db_dict = {row["ticker"]: row for _, row in db_df.iterrows()}

    discrepancies = []

    # ── Position reconciliation ───────────────────────────────────────────────
    for ticker, broker_pos in broker_positions.items():
        db_pos = db_dict.get(ticker)
        if db_pos is None:
            discrepancies.append({
                "ticker":     ticker,
                "issue":      "in_broker_not_in_db",
                "broker_qty": broker_pos["quantity"],
                "db_qty":     None,
            })
        else:
            qty_diff = abs(float(broker_pos["quantity"]) - float(db_pos["quantity"]))
            if qty_diff > 0.01:
                discrepancies.append({
                    "ticker":     ticker,
                    "issue":      "quantity_mismatch",
                    "broker_qty": broker_pos["quantity"],
                    "db_qty":     float(db_pos["quantity"]),
                    "diff":       qty_diff,
                })

    # Tickers in DB but missing from broker entry
    for ticker in db_dict:
        if ticker not in broker_positions:
            discrepancies.append({
                "ticker": ticker,
                "issue":  "in_db_not_in_broker",
                "db_qty": float(db_dict[ticker]["quantity"]),
            })

    # ── Cash reconciliation ───────────────────────────────────────────────────
    cash_match = True
    if broker_cash_eur is not None:
        db_cash = get_db_cash()
        cash_diff = abs(broker_cash_eur - db_cash)
        if cash_diff > 1.0:   # €1 tolerance for rounding
            cash_match = False
            discrepancies.append({
                "ticker":  "_CASH",
                "issue":   "cash_mismatch",
                "broker":  broker_cash_eur,
                "db":      db_cash,
                "diff":    cash_diff,
            })
            logger.warning(f"Cash mismatch: broker=€{broker_cash_eur:.2f}, DB=€{db_cash:.2f}")

    positions_match = not any(d.get("issue") != "cash_mismatch" for d in discrepancies)

    # ── Log reconciliation ────────────────────────────────────────────────────
    session = get_session()
    session.execute(text("""
        INSERT INTO reconciliation_log
            (positions_match, cash_match, discrepancies, action_taken)
        VALUES (:pos_match, :cash_match, :disc, :action)
    """), {
        "pos_match":  int(positions_match),
        "cash_match": int(cash_match),
        "disc":       json.dumps(discrepancies),
        "action":     "manual_review_required" if discrepancies else "clean",
    })
    session.commit()
    session.close()

    if discrepancies:
        logger.warning(f"Reconciliation: {len(discrepancies)} discrepancies found")
    else:
        logger.info("Reconciliation: CLEAN — DB matches broker")

    return {
        "clean":            len(discrepancies) == 0,
        "positions_match":  positions_match,
        "cash_match":       cash_match,
        "discrepancies":    discrepancies,
    }
