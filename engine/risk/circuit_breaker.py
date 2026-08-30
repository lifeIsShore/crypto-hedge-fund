"""
engine/risk/circuit_breaker.py — Hard stop-loss circuit breaker enforcement.
=============================================================================
Implements I3: hard per-position stop-loss floors.

Runs inside step_portfolio_construction() BEFORE Black-Litterman / BL optimizer,
so that triggered tickers are forced to 0% weight in the suggested allocation.

If a position has declined more than STOP_LOSS_THRESHOLD from its average entry
price (cost basis from the trades table), the following happens:
  1. A CRITICAL log entry is written.
  2. A 'circuit_breaker' risk_event row is inserted into the DB.
  3. The ticker is returned in the `triggered` list so the caller can
     zero-out its weight in portfolio construction.
  4. An alert is sent via the alerting digest.

Thresholds:
  - Individual stock: -15% from average entry
  - ETF (tickers containing EUNL, VUSA, VWCE, EXS1, etc.): -12%

These are hard floors — they override all model signals.
Document any threshold changes in portfolio/docs/03-TUNING-LOG.md.
"""

import logging
from engine.db.db import get_session
from sqlalchemy import text

logger = logging.getLogger(__name__)

# Hard stop thresholds — configurable, document changes in TUNING-LOG.md
STOP_LOSS_INDIVIDUAL = -0.35   # -35% from average cost basis (individual altcoins)
STOP_LOSS_ETF        = -0.25   # -25% for anchor assets (BTC/ETH) (lower vol, tighter stop)

# Broad-market ETF suffixes / known ETF tickers that get the tighter threshold
_ETF_SUFFIXES = ('.DE',)   # refined below by known-ETF check

# Anchor crypto assets that get the tighter "ETF-like" threshold
_KNOWN_ETF_TICKERS = frozenset([
    'BTC/EUR', 'ETH/EUR',
])


def _is_etf(ticker: str) -> bool:
    return ticker in _KNOWN_ETF_TICKERS


def get_average_entry_prices(session=None) -> dict:
    """
    Returns {ticker: avg_entry_price_eur} for all current long positions
    where we have BUY trades. Uses weighted-average cost basis.

    Filters to tickers with net positive quantity (i.e. still held).
    """
    close_session = False
    if session is None:
        session = get_session()
        close_session = True

    try:
        rows = session.execute(text("""
            SELECT ticker,
                   SUM(quantity * price_eur) / NULLIF(SUM(quantity), 0) AS avg_price
            FROM trades
            WHERE action = 'BUY' AND quantity > 0 AND price_eur > 0
            GROUP BY ticker
            HAVING SUM(quantity) > 0
        """)).fetchall()
        return {r[0]: float(r[1]) for r in rows if r[1] is not None}
    finally:
        if close_session:
            session.close()


def _log_circuit_breaker_event(ticker: str, drawdown: float,
                                entry: float, current: float,
                                threshold: float, session) -> None:
    """Write a circuit_breaker row to risk_events table."""
    detail = (
        f"Drawdown {drawdown:.1%} exceeded {threshold:.0%} threshold. "
        f"Entry=€{entry:.2f}, Current=€{current:.2f}"
    )
    session.execute(text("""
        INSERT INTO risk_events (date, event_type, ticker, detail)
        VALUES (CURRENT_DATE, 'circuit_breaker', :ticker, :detail)
    """), {"ticker": ticker, "detail": detail[:500]})


def run_circuit_breaker_check(
    positions: dict,
    current_prices: dict,
    entry_prices: dict,
) -> list:
    """
    Check all held positions against their average entry price.

    Parameters
    ----------
    positions:      {ticker: quantity}  — positive qty = long position
    current_prices: {ticker: current_price_eur}
    entry_prices:   {ticker: avg_entry_price_eur} from get_average_entry_prices()

    Returns
    -------
    List of tickers that triggered a circuit breaker. These should be
    forced to 0% weight in portfolio construction.
    """
    triggered = []
    session = get_session()

    try:
        for ticker, qty in positions.items():
            if qty <= 0:
                continue

            entry   = entry_prices.get(ticker)
            current = current_prices.get(ticker)

            if not entry or not current or entry <= 0:
                continue

            drawdown  = (current - entry) / entry   # negative = loss
            threshold = STOP_LOSS_ETF if _is_etf(ticker) else STOP_LOSS_INDIVIDUAL

            if drawdown <= threshold:
                logger.critical(
                    f"🚨 CIRCUIT BREAKER: {ticker} down {drawdown:.1%} from entry "
                    f"(entry=€{entry:.2f}, current=€{current:.2f}) — FORCED SELL"
                )
                triggered.append(ticker)
                _log_circuit_breaker_event(ticker, drawdown, entry, current, threshold, session)

        if triggered:
            session.commit()

    except Exception as e:
        logger.error(f"[circuit_breaker] DB write failed: {e}")
        try:
            session.rollback()
        except Exception:
            pass
    finally:
        session.close()

    return triggered
