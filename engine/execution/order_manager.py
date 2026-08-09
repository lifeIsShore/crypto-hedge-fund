# engine/execution/order_manager.py
"""
Order state machine for manual execution.
You review the queue, execute on your broker (Trade Republic),
then confirm execution via the dashboard form.
States: CREATED → REVIEWED → CONFIRMED / SKIPPED
"""
import pandas as pd
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
from sqlalchemy import text
from engine.db.db import get_session
import logging

logger = logging.getLogger(__name__)


class OrderState(Enum):
    CREATED   = "CREATED"
    REVIEWED  = "REVIEWED"
    CONFIRMED = "CONFIRMED"
    SKIPPED   = "SKIPPED"
    FAILED    = "FAILED"


@dataclass
class Order:
    ticker:      str
    action:      str       # BUY or SELL
    value_eur:   float
    state:       OrderState = OrderState.CREATED
    order_id:    str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    notes:       str = ""
    slippage_pct:float = 0.0005


from portfolio.src.config import DRIFT_THRESHOLD_BUY, DRIFT_THRESHOLD_SELL

def generate_order_queue(
    suggested_weights: pd.Series,
    current_weights: pd.Series,
    total_portfolio_eur: float,
    min_trade_eur: float = 25.0,
) -> list:
    """
    Generates a list of Orders from the weight delta.
    Applies your existing MIN_TRADE_EUR_FLOOR and drift thresholds.
    """
    orders = []
    for ticker in suggested_weights.index:
        target_w  = float(suggested_weights.get(ticker, 0))
        current_w = float(current_weights.get(ticker, 0))
        delta_w   = target_w - current_w
        delta_eur = delta_w * total_portfolio_eur

        # Hard size floor
        if abs(delta_eur) < min_trade_eur:
            continue

        # Tolerance band check — asymmetric (let winners run, cut losers faster)
        if delta_w > 0:   # BUY signal
            drift_pct = delta_w / target_w if target_w > 0 else 0
            if drift_pct < abs(DRIFT_THRESHOLD_BUY):
                continue
        elif delta_w < 0:  # SELL signal
            drift_pct = abs(delta_w) / current_w if current_w > 0 else 0
            if drift_pct < DRIFT_THRESHOLD_SELL:
                continue

        action = "BUY" if delta_eur > 0 else "SELL"
        orders.append(Order(
            ticker=ticker, action=action, value_eur=abs(delta_eur)
        ))

    orders.sort(key=lambda o: abs(o.value_eur), reverse=True)
    logger.info(f"Order queue: {len(orders)} orders generated (tolerance bands applied)")
    return orders


def confirm_order(order_id: str, ticker: str, action: str, actual_value_eur: float, price_eur: float, notes: str = ""):
    """
    Called from dashboard when you confirm you executed an order manually.
    All fields must be passed explicitly — nothing is hardcoded.
    """
    session = get_session()
    try:
        qty = actual_value_eur / price_eur if price_eur > 0 else 0
        session.execute(text("""
            INSERT INTO trades (date, ticker, action, quantity, price_eur, value_eur, source, notes)
            VALUES (CURRENT_DATE, :ticker, :action, :qty, :price, :value, 'manual', :notes)
        """), {
            "ticker": ticker,
            "action": action,
            "qty":    qty,
            "price":  price_eur,
            "value":  actual_value_eur,
            "notes":  notes,
        })
        session.commit()
        logger.info(f"Trade confirmed: {action} {ticker} €{actual_value_eur:.2f} @ €{price_eur:.4f}")
    except Exception as e:
        session.rollback()
        logger.error(f"confirm_order failed: {e}")
        raise
    finally:
        session.close()
