"""
paper_trader.py — Records order queue as executed without touching real cash.
Used in SANDBOX_MODE to simulate live execution at closing prices.
"""
import logging
from engine.db.db import get_session
from sqlalchemy import text

logger = logging.getLogger(__name__)


def execute_paper_orders(orders: list, current_prices: dict, notional_eur: float):
    """
    'Execute' all orders at current prices in the sandbox DB.
    Writes to trades table with source='paper', AND mirrors the cash impact
    into cash_history (BUY debits cash, SELL credits it).

    NOTE (2026-08-10): the cash_history write was missing entirely in the
    original version of this function. flask_app.py's _live_positions()
    reconstructs position quantities/values from the trades table (correct),
    but reads cash from the separate cash_history table's latest row. With
    no cash_history write here, a paper BUY's cost was never deducted from
    cash — so it was counted twice: once as the new position's market value,
    once as cash that was never actually spent — inflating total portfolio
    value with money that doesn't exist. See PROJECT-STATE.md.
    """
    session = get_session()
    try:
        cash_row = session.execute(text(
            "SELECT cash_eur FROM cash_history ORDER BY date DESC, id DESC LIMIT 1"
        )).fetchone()
        running_cash = float(cash_row[0]) if cash_row and cash_row[0] is not None else 0.0

        for order in orders:
            price = current_prices.get(order.ticker)
            if not price:
                logger.warning(f"[paper] No price for {order.ticker} — skipping")
                continue

            qty = order.value_eur / price
            session.execute(text("""
                INSERT INTO trades
                    (date, ticker, action, quantity, price_eur, value_eur, source, notes)
                VALUES (CURRENT_DATE, :ticker, :action, :qty, :price, :value, 'paper', 'sandbox')
            """), {
                "ticker": order.ticker,
                "action": order.action,
                "qty":    qty,
                "price":  price,
                "value":  order.value_eur,
            })

            if order.action == "BUY":
                running_cash -= order.value_eur
            else:  # SELL
                running_cash += order.value_eur

            session.execute(text("""
                INSERT INTO cash_history (date, cash_eur, event_type, notes)
                VALUES (CURRENT_DATE, :cash, :event, :notes)
            """), {
                "cash":  round(running_cash, 4),
                "event": f"PAPER_{order.action}_{'DEBIT' if order.action == 'BUY' else 'CREDIT'}",
                "notes": f"paper {order.action} {order.ticker} \u20ac{order.value_eur:.2f}",
            })

            logger.info(
                f"[paper] {order.action} {order.ticker} \u20ac{order.value_eur:.0f} @ \u20ac{price:.2f} "
                f"— cash now \u20ac{running_cash:.2f}"
            )
        session.commit()
    except Exception as e:
        session.rollback()
        logger.error(f"[paper] Failed to execute paper orders: {e}")
        raise
    finally:
        session.close()
