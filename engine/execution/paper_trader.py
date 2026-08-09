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
    Writes to trades table with source='paper'.
    """
    session = get_session()
    try:
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
            logger.info(f"[paper] {order.action} {order.ticker} €{order.value_eur:.0f} @ €{price:.2f}")
        session.commit()
    except Exception as e:
        session.rollback()
        logger.error(f"[paper] Failed to execute paper orders: {e}")
        raise
    finally:
        session.close()
