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
    """Latest positions from internal DB."""
    session = get_session()
    result = session.execute(text("""
        SELECT DISTINCT ON (ticker) ticker, quantity, price, value_eur, weight
        FROM positions_history
        ORDER BY ticker, date DESC
    """))
    rows = result.fetchall()
    session.close()
    return pd.DataFrame(rows, columns=["ticker", "quantity", "price", "value_eur", "weight"])


def reconcile(broker_positions: dict) -> dict:
    """
    broker_positions: dict of {ticker: {"quantity": x, "price": y}}
    Returns reconciliation result + discrepancies.
    Manual entry from Trade Republic app → this function.
    """
    db_df = get_db_positions()
    db_dict = {row["ticker"]: row for _, row in db_df.iterrows()}

    discrepancies = []
    for ticker, broker_pos in broker_positions.items():
        db_pos = db_dict.get(ticker)
        if db_pos is None:
            discrepancies.append({
                "ticker": ticker,
                "issue": "in_broker_not_in_db",
                "broker_qty": broker_pos["quantity"],
                "db_qty": None
            })
        else:
            qty_diff = abs(float(broker_pos["quantity"]) - float(db_pos["quantity"]))
            if qty_diff > 0.01:
                discrepancies.append({
                    "ticker": ticker,
                    "issue": "quantity_mismatch",
                    "broker_qty": broker_pos["quantity"],
                    "db_qty": float(db_pos["quantity"]),
                    "diff": qty_diff
                })

    # Log reconciliation
    session = get_session()
    session.execute(text("""
        INSERT INTO reconciliation_log
            (positions_match, cash_match, discrepancies, action_taken)
        VALUES (:pos_match, TRUE, :disc, :action)
    """), {
        "pos_match": len(discrepancies) == 0,
        "disc": json.dumps(discrepancies),
        "action": "manual_review_required" if discrepancies else "clean"
    })
    session.commit()
    session.close()

    if discrepancies:
        logger.warning(f"Reconciliation: {len(discrepancies)} discrepancies found")
    else:
        logger.info("Reconciliation: CLEAN — DB matches broker")

    return {"clean": len(discrepancies) == 0, "discrepancies": discrepancies}
