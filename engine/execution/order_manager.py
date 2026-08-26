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

# ── J4: pre-earnings throttle tuning ────────────────────────────────────────
EARNINGS_THROTTLE_DAYS   = 3     # start throttling this many days before report
EARNINGS_THROTTLE_SCALAR = 0.5   # cut new BUY size in half heading into earnings


def get_adv_eur(ticker: str, days: int = 21) -> float:
    """Computes the average daily volume in EUR over the last `days`."""
    session = get_session()
    try:
        row = session.execute(text("""
            SELECT AVG(volume * close)
            FROM (
                SELECT volume, close 
                FROM prices 
                WHERE ticker = :ticker AND volume IS NOT NULL AND volume > 0
                ORDER BY date DESC 
                LIMIT :days
            )
        """), {"ticker": ticker, "days": days}).fetchone()
        
        if row and row[0] is not None:
            return float(row[0])
        return 1e9  # Fallback: effectively no limit if volume data is missing
    except Exception as e:
        logger.warning(f"Failed to fetch ADV for {ticker}: {e}")
        return 1e9
    finally:
        session.close()

def get_kelly_scalars(tickers: list) -> dict:
    """
    J3 — fetches kelly_half per ticker from the latest price_targets row.
    Clipped to [0.1, 1.0]: never let Kelly increase size beyond the
    optimizer's own suggestion (MAX_POSITION already governs that ceiling),
    and never let it zero out a trade entirely (0.1 floor keeps small
    rebalancing trades flowing even on low-confidence signals).
    """
    if not tickers:
        return {}
    session = get_session()
    try:
        placeholders = ','.join([f':t{i}' for i in range(len(tickers))])
        params = {f't{i}': t for i, t in enumerate(tickers)}
        rows = session.execute(text(f"""
            SELECT ticker, kelly_half
            FROM price_targets
            WHERE date = (SELECT MAX(date) FROM price_targets)
            AND ticker IN ({placeholders})
        """), params).fetchall()
    except Exception as e:
        logger.warning(f"[kelly_sizing] get_kelly_scalars failed (non-fatal, defaulting to neutral): {e}")
        return {}
    finally:
        session.close()

    scalars = {}
    for ticker, kelly_half in rows:
        if kelly_half is None or kelly_half != kelly_half:  # NaN check
            scalars[ticker] = 0.5   # neutral default when data is missing
            continue
        scalars[ticker] = max(0.1, min(1.0, float(kelly_half)))
    return scalars


def get_regime_scalar() -> float:
    """J3 — reads current risk regime and returns a sizing multiplier."""
    try:
        import json
        from shared.state_paths import REGIME_STATE_PATH
        with open(REGIME_STATE_PATH) as f:
            state = json.load(f)
        risk = state.get('regime_risk', '').lower()
        return 0.6 if 'risk-off' in risk or 'risk_off' in risk else 1.0
    except Exception as e:
        logger.warning(f"[kelly_sizing] regime read failed, defaulting to 1.0: {e}")
        return 1.0

def get_portfolio_drawdown() -> float:
    """Computes current portfolio drawdown from all-time high-water mark."""
    session = get_session()
    try:
        row_max = session.execute(text("SELECT MAX(portfolio_value_eur) FROM performance_history")).fetchone()
        hwm = float(row_max[0]) if row_max and row_max[0] else 0.0
        
        row_cur = session.execute(text("SELECT portfolio_value_eur FROM performance_history ORDER BY date DESC LIMIT 1")).fetchone()
        cur = float(row_cur[0]) if row_cur and row_cur[0] else 0.0
        
        if hwm <= 0:
            return 0.0
        
        return (cur - hwm) / hwm
    except Exception as e:
        logger.warning(f"[drawdown] failed to compute: {e}")
        return 0.0
    finally:
        session.close()

def _log_drawdown_event(drawdown: float, tier: str, action: str):
    session = get_session()
    try:
        # Only log once per day per tier to avoid spam
        exists = session.execute(text("""
            SELECT 1 FROM risk_events 
            WHERE date = CURRENT_DATE AND event_type = 'drawdown_alert' AND detail LIKE :tier_like
        """), {"tier_like": f"%{tier}%"}).fetchone()
        if not exists:
            session.execute(text("""
                INSERT INTO risk_events (date, event_type, ticker, detail)
                VALUES (CURRENT_DATE, 'drawdown_alert', 'PORTFOLIO', :detail)
            """), {"detail": f"{tier} threshold breached (drawdown {drawdown*100:.1f}%). Action: {action}"})
            session.commit()
    except Exception as e:
        session.rollback()
        logger.warning(f"Failed to log drawdown event: {e}")
    finally:
        session.close()


def generate_order_queue(
    suggested_weights: pd.Series,
    current_weights: pd.Series,
    total_portfolio_eur: float,
    min_trade_eur: float = 25.0,
    adv_limit_pct: float = 0.05,
    apply_kelly_sizing: bool = True,       # NEW (J3) — disable for sandbox A/B comparison
    apply_earnings_throttle: bool = True,  # NEW (J4) — disable for sandbox A/B comparison
) -> list:
    """
    Generates a list of Orders from the weight delta.
    Applies your existing MIN_TRADE_EUR_FLOOR, drift thresholds, and ADV liquidity limits,
    then (BUY orders only) a Kelly-sizing scalar (J3) and a pre-earnings throttle (J4).
    """
    orders = []

    # Portfolio Drawdown Protocol (J6)
    drawdown = get_portfolio_drawdown()
    drawdown_buy_scalar = 1.0
    pause_buys = False
    
    if drawdown <= -0.20:
        pause_buys = True
        _log_drawdown_event(drawdown, "Tier 3 (-20%)", "New BUY orders paused")
        logger.warning(f"[Drawdown Protocol] -20% threshold breached (drawdown {drawdown*100:.1f}%). New BUYs paused.")
    elif drawdown <= -0.15:
        drawdown_buy_scalar = 0.5
        _log_drawdown_event(drawdown, "Tier 2 (-15%)", "New BUY sizing reduced by 50%")
        logger.warning(f"[Drawdown Protocol] -15% threshold breached (drawdown {drawdown*100:.1f}%). New BUYs scaled by 0.5.")
    elif drawdown <= -0.10:
        _log_drawdown_event(drawdown, "Tier 1 (-10%)", "Alert only")
        logger.info(f"[Drawdown Protocol] -10% threshold breached (drawdown {drawdown*100:.1f}%).")

    # J3 — fetch Kelly + regime scalars once, outside the loop
    kelly_scalars = get_kelly_scalars(list(suggested_weights.index)) if apply_kelly_sizing else {}
    regime_scalar = get_regime_scalar() if apply_kelly_sizing else 1.0

    # J4 — fetch tickers reporting earnings soon, once, outside the loop
    upcoming_earnings = set()
    if apply_earnings_throttle:
        try:
            from engine.data.earnings_calendar import get_reporting_soon
            upcoming_earnings = get_reporting_soon(
                list(suggested_weights.index), within_days=EARNINGS_THROTTLE_DAYS
            )
        except Exception as e:
            logger.warning(f"[earnings_throttle] lookup failed (non-fatal): {e}")

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

        abs_delta_eur = abs(delta_eur)

        # Liquidity Gating: limit order size to a % of Average Daily Volume (ADV)
        adv_eur = get_adv_eur(ticker)
        max_order_eur = adv_eur * adv_limit_pct
        if abs_delta_eur > max_order_eur:
            logger.warning(f"[Liquidity Gate] {ticker} order capped at {adv_limit_pct*100}% ADV (€{max_order_eur:,.0f} vs original €{abs_delta_eur:,.0f})")
            abs_delta_eur = max_order_eur

        # J3 + J4 — Kelly sizing and earnings throttle apply to BUYS ONLY.
        # Never shrink a SELL: a smaller sell just delays reaching the BL
        # target on the way down, which fights risk reduction instead of
        # helping it — especially heading into an unpredictable earnings print.
        action = "BUY" if delta_eur > 0 else "SELL"
        
        if action == "BUY" and pause_buys:
            logger.info(f"[Drawdown Protocol] Skipping BUY order for {ticker} due to portfolio pause.")
            continue

        if action == "BUY" and apply_kelly_sizing:
            k_scalar = kelly_scalars.get(ticker, 0.5)
            combined_scalar = k_scalar * regime_scalar * drawdown_buy_scalar
            pre_kelly_eur = abs_delta_eur
            abs_delta_eur = abs_delta_eur * combined_scalar
            if abs_delta_eur < min_trade_eur:
                continue  # scaled below the floor — skip rather than send a dust order
            logger.info(
                f"[Kelly Sizing] {ticker}: \u20ac{pre_kelly_eur:,.0f} -> \u20ac{abs_delta_eur:,.0f} "
                f"(kelly={k_scalar:.2f}, regime={regime_scalar:.2f})"
            )

        if action == "BUY" and apply_earnings_throttle and ticker in upcoming_earnings:
            pre_throttle_eur = abs_delta_eur
            abs_delta_eur *= EARNINGS_THROTTLE_SCALAR
            if abs_delta_eur < min_trade_eur:
                continue
            logger.info(
                f"[Earnings Throttle] {ticker}: \u20ac{pre_throttle_eur:,.0f} -> \u20ac{abs_delta_eur:,.0f} "
                f"(reports within {EARNINGS_THROTTLE_DAYS}d)"
            )

        orders.append(Order(
            ticker=ticker, action=action, value_eur=abs_delta_eur
        ))

    orders.sort(key=lambda o: abs(o.value_eur), reverse=True)
    logger.info(
        f"Order queue: {len(orders)} orders generated "
        f"(tolerance bands, ADV gating, Kelly sizing, earnings throttle applied)"
    )
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
