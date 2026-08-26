"""
engine/data/liquidity_classifier.py
====================================
Shared ticker data-quality / liquidity tiering.

Produces a per-ticker, per-date tier ('liquid' | 'thin' | 'unreliable') and a
continuous 0-1 trust score, built entirely from data already in the `prices`
table. No external calls, no new data source.

Consumers (as of 2026-08-20):
  - engine/screens/crosslisting_divergence.py (guardrail: suppress divergence
    alerts on 'thin'/'unreliable' tickers, since gaps there are noise, not signal)

Planned future consumer (not yet wired):
  - ML walk-forward reduced-fold fallback for tickers with 400-889 rows.

Run weekly (see wiring section below) — liquidity profile doesn't change fast
enough to need daily recomputation, and it's one query per ticker.
"""
import logging
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from sqlalchemy import text
from engine.db.db import get_session

logger = logging.getLogger(__name__)

# Tuning knobs — deliberately conservative; a ticker only needs to clear ALL
# thresholds to be 'liquid'. Revisit these after seeing real distributions
# from your actual universe (see "Calibration" section below).
MIN_TRADING_DAYS_90D   = 55     # ~85% of ~65 trading days in a 90-calendar-day window
MAX_AVG_RANGE_PCT      = 0.040  # 4.0% average daily high-low range
MIN_HISTORY_DAYS       = 400
MAX_STALENESS_DAYS     = 5


def _load_recent_prices(ticker: str, session, lookback_days: int = 400) -> pd.DataFrame:
    cutoff = (datetime.today() - timedelta(days=lookback_days)).strftime('%Y-%m-%d')
    rows = session.execute(text("""
        SELECT date, close, high, low, volume
        FROM prices
        WHERE ticker = :t AND date >= :cutoff
        ORDER BY date ASC
    """), {'t': ticker, 'cutoff': cutoff}).fetchall()
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows, columns=['date', 'close', 'high', 'low', 'volume'])
    df['date'] = pd.to_datetime(df['date'])
    return df


def classify_ticker(ticker: str, session, as_of_date: str = None) -> dict:
    """Returns a single tier record for one ticker. Does not persist."""
    df = _load_recent_prices(ticker, session)

    if df.empty:
        return {
            'ticker': ticker, 'tier': 'unreliable', 'trading_days_90d': 0,
            'avg_range_pct': None, 'history_days': 0,
            'days_since_update': None, 'score': 0.0,
        }

    today = pd.Timestamp(as_of_date) if as_of_date else pd.Timestamp.today().normalize()
    last_90d = df[df['date'] >= today - pd.Timedelta(days=90)]

    trading_days_90d = int((last_90d['volume'].fillna(0) > 0).sum())
    history_days = session.execute(text("SELECT COUNT(*) FROM prices WHERE ticker = :t"), {'t': ticker}).fetchone()[0]
    days_since_update = int((today - df['date'].max()).days)

    last_30 = df.tail(30)
    with np.errstate(divide='ignore', invalid='ignore'):
        ranges = (last_30['high'] - last_30['low']) / last_30['close'].replace(0, np.nan)
    avg_range_pct = float(ranges.dropna().mean()) if not ranges.dropna().empty else None

    # Composite score: each check contributes up to 0.25, clamped [0, 1]
    score = 0.0
    score += 0.25 * min(1.0, trading_days_90d / MIN_TRADING_DAYS_90D) if trading_days_90d else 0.0
    score += 0.25 * min(1.0, history_days / MIN_HISTORY_DAYS)
    score += 0.25 * (1.0 if days_since_update <= MAX_STALENESS_DAYS else
                      max(0.0, 1.0 - (days_since_update - MAX_STALENESS_DAYS) / 20))
    if avg_range_pct is not None:
        score += 0.25 * min(1.0, MAX_AVG_RANGE_PCT / max(avg_range_pct, 1e-6))
    score = round(min(1.0, max(0.0, score)), 4)

    # Tier from hard gates first (a single bad gate can't be averaged away by
    # good scores elsewhere — e.g. a stale-but-otherwise-fine-looking ticker
    # should never be called 'liquid')
    if (trading_days_90d < MIN_TRADING_DAYS_90D * 0.5
            or history_days < MIN_HISTORY_DAYS * 0.5
            or days_since_update > MAX_STALENESS_DAYS * 4):
        tier = 'unreliable'
    elif (trading_days_90d >= MIN_TRADING_DAYS_90D
            and history_days >= MIN_HISTORY_DAYS
            and days_since_update <= MAX_STALENESS_DAYS
            and (avg_range_pct is None or avg_range_pct <= MAX_AVG_RANGE_PCT)):
        tier = 'liquid'
    else:
        tier = 'thin'

    return {
        'ticker': ticker, 'tier': tier,
        'trading_days_90d': trading_days_90d,
        'avg_range_pct': round(avg_range_pct, 4) if avg_range_pct is not None else None,
        'history_days': history_days,
        'days_since_update': days_since_update,
        'score': score,
    }


def run_liquidity_classification(tickers: list, date: str) -> pd.DataFrame:
    """Classify every ticker in the universe and persist to ticker_liquidity_tier."""
    session = get_session()
    results = []
    try:
        for ticker in tickers:
            rec = classify_ticker(ticker, session, as_of_date=date)
            results.append(rec)

        for rec in results:
            session.execute(text("""
                INSERT INTO ticker_liquidity_tier
                    (date, ticker, tier, trading_days_90d, avg_range_pct,
                     history_days, days_since_update, score)
                VALUES (:date, :ticker, :tier, :td90, :range, :hist, :stale, :score)
                ON CONFLICT (date, ticker) DO UPDATE SET
                    tier = excluded.tier, trading_days_90d = excluded.trading_days_90d,
                    avg_range_pct = excluded.avg_range_pct, history_days = excluded.history_days,
                    days_since_update = excluded.days_since_update, score = excluded.score
            """), {
                'date': date, 'ticker': rec['ticker'], 'tier': rec['tier'],
                'td90': rec['trading_days_90d'], 'range': rec['avg_range_pct'],
                'hist': rec['history_days'], 'stale': rec['days_since_update'],
                'score': rec['score'],
            })
        session.commit()
    except Exception as e:
        session.rollback()
        logger.error(f"[liquidity] Classification failed: {e}")
        raise
    finally:
        session.close()

    df = pd.DataFrame(results)
    tier_counts = df['tier'].value_counts().to_dict()
    logger.info(f"[liquidity] Classified {len(df)} tickers: {tier_counts}")
    return df


def get_tier(ticker: str, date: str = None) -> str:
    """Convenience lookup for a single ticker's latest known tier. Defaults to 'thin'
    (conservative — treat unknown as untrusted, not as trusted) if never classified."""
    session = get_session()
    try:
        row = session.execute(text("""
            SELECT tier FROM ticker_liquidity_tier
            WHERE ticker = :t AND date <= :d
            ORDER BY date DESC LIMIT 1
        """), {'t': ticker, 'd': date or datetime.today().strftime('%Y-%m-%d')}).fetchone()
        return row[0] if row else 'thin'
    finally:
        session.close()
