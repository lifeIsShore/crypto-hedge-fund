# engine/risk/pre_trade.py
import pandas as pd
import numpy as np
import logging
from engine.db.db import get_session
from sqlalchemy import text

logger = logging.getLogger(__name__)

MAX_POSITION    = 0.10
MAX_SECTOR      = 0.30
MAX_LEVERAGE    = 1.0
MIN_ADV_RATIO   = 0.01    # order must be < 1% of 30-day avg daily volume


def check_position_limits(suggested_weights: pd.Series) -> list:
    violations = []
    for ticker, w in suggested_weights.items():
        if w > MAX_POSITION:
            violations.append(f"{ticker}: weight {w:.1%} exceeds max {MAX_POSITION:.0%}")
    return violations


def check_leverage(suggested_weights: pd.Series) -> list:
    total = suggested_weights.sum()
    if total > MAX_LEVERAGE + 0.001:
        return [f"Total weight {total:.3f} exceeds max leverage {MAX_LEVERAGE}"]
    return []


def check_sector_exposure(suggested_weights: pd.Series, sector_map: dict) -> list:
    sector_totals = {}
    for ticker, w in suggested_weights.items():
        s = sector_map.get(ticker, "other")
        sector_totals[s] = sector_totals.get(s, 0) + w
    violations = []
    for sector, total in sector_totals.items():
        if total > MAX_SECTOR:
            violations.append(f"Sector {sector}: {total:.1%} exceeds {MAX_SECTOR:.0%} limit")
    return violations


def run_pre_trade_checks(suggested_weights: pd.Series, sector_map: dict = None) -> dict:
    """
    Runs all pre-trade checks. Returns result with pass/fail and list of violations.
    Violations block order submission.
    """
    violations = []
    violations += check_position_limits(suggested_weights)
    violations += check_leverage(suggested_weights)
    if sector_map:
        violations += check_sector_exposure(suggested_weights, sector_map)

    result = {
        "passed": len(violations) == 0,
        "violations": violations,
    }

    if not result["passed"]:
        logger.warning(f"Pre-trade FAILED: {violations}")
    else:
        logger.info("Pre-trade checks: ALL PASSED")

    # Log violations to DB
    session = get_session()
    for v in violations:
        # Try to extract ticker (e.g., "AAPL: weight...")
        ticker = v.split(':')[0] if ':' in v else None
        session.execute(text("""
            INSERT INTO risk_events (date, event_type, ticker, detail)
            VALUES (CURRENT_DATE, 'pre_trade_violation', :ticker, :detail)
        """), {"ticker": ticker, "detail": v[:200]})
    session.commit()
    session.close()

    return result

def check_tax_awareness(orders: list):
    """
    Simulates FIFO lot consumption for SELL orders.
    Warns if the sale will trigger a short-term capital gain (<365 days).
    Modifies order.notes in place.
    """
    from engine.db.db import get_session
    from sqlalchemy import text
    from datetime import datetime
    
    session = get_session()
    try:
        for order in orders:
            if order.action != 'SELL':
                continue
                
            # Get latest price to estimate quantity
            price_row = session.execute(
                text("SELECT adj_close FROM prices WHERE ticker = :t ORDER BY date DESC LIMIT 1"),
                {"t": order.ticker}
            ).fetchone()
            
            if not price_row:
                continue
                
            price_eur = float(price_row[0])
            qty_to_sell = order.value_eur / price_eur
            
            # Fetch active lots (FIFO)
            asset_base = order.ticker.split('/')[0]
            lots = session.execute(
                text("""
                    SELECT lot_id, quantity_original, quantity_remaining, acquisition_cost_eur, acquisition_timestamp
                    FROM tax_lots
                    WHERE asset = :asset AND quantity_remaining > 0
                    ORDER BY acquisition_timestamp ASC
                """),
                {"asset": asset_base}
            ).fetchall()
            
            remaining_to_sell = qty_to_sell
            short_term_gain = 0.0
            total_st_qty = 0.0
            min_holding_days = 9999
            
            now = datetime.now()
            
            for lot in lots:
                if remaining_to_sell <= 0:
                    break
                    
                lot_id, qty_orig, qty_rem, cost_eur, acq_ts_str = lot
                acq_ts = datetime.fromisoformat(acq_ts_str)
                holding_days = (now - acq_ts).days
                
                consume_qty = min(remaining_to_sell, qty_rem)
                
                if holding_days < 365:
                    # Short-term disposal detected
                    cost_basis_chunk = (consume_qty / qty_orig) * cost_eur
                    sale_value_chunk = consume_qty * price_eur
                    gain_chunk = sale_value_chunk - cost_basis_chunk
                    
                    short_term_gain += gain_chunk
                    total_st_qty += consume_qty
                    min_holding_days = min(min_holding_days, holding_days)
                
                remaining_to_sell -= consume_qty
                
            if total_st_qty > 0 and short_term_gain > 0:
                est_tax = short_term_gain * 0.25  # Roughly 25% placeholder for tax impact
                warn_msg = (
                    f"⚠️ Short-term disposal | "
                    f"Est. gain: €{short_term_gain:.0f} | "
                    f"Est. tax impact: €{est_tax:.0f} | "
                    f"Holding: {min_holding_days} days"
                )
                logger.warning(f"[tax_awareness] {order.ticker} - {warn_msg}")
                if order.notes:
                    order.notes += " | " + warn_msg
                else:
                    order.notes = warn_msg
                    
    except Exception as e:
        logger.error(f"[tax_awareness] Failed: {e}")
    finally:
        session.close()
