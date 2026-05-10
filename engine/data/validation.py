# engine/data/validation.py
"""
Data validation layer.
Formalises the existing MAX_DAILY_MOVE_ANOMALY = 0.30 gate from portfolio/src/config.py
and adds missing-day detection and FX fallback logging.
All violations are written to data_validation_log in the DB.
"""

import pandas as pd
import numpy as np
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Mirrors portfolio/src/config.py MAX_DAILY_MOVE_ANOMALY — keep in sync
MAX_DAILY_MOVE = 0.30


def validate_prices(df: pd.DataFrame, log_to_db: bool = True) -> pd.DataFrame:
    """
    Runs all validation checks. Returns only clean rows.
    Rejected rows are logged to data_validation_log.

    Args:
        df: DataFrame with columns: date, ticker, open, high, low, close,
            volume, adj_close, source
        log_to_db: whether to write violations to the DB

    Returns:
        Cleaned DataFrame (rejected rows removed).
    """
    if df.empty:
        return df

    clean_rows = []
    violations = []

    for ticker, group in df.groupby('ticker'):
        group = group.sort_values('date').reset_index(drop=True)
        group['daily_return'] = group['adj_close'].pct_change()

        for _, row in group.iterrows():
            ret = row.get('daily_return', np.nan)

            # ── Gate 1: Price spike / unadjusted split detection ──────────────
            if not np.isnan(ret) and abs(ret) > MAX_DAILY_MOVE:
                violations.append({
                    'date':       row['date'],
                    'ticker':     ticker,
                    'issue_type': 'price_spike',
                    'raw_value':  round(float(ret), 6),
                    'action':     'rejected',
                    'detail':     f'{ret:.1%} daily move exceeds {MAX_DAILY_MOVE:.0%} gate',
                })
                logger.warning(
                    f"⚠️  REJECTED {ticker} on {row['date']}: "
                    f"{ret:.1%} move > {MAX_DAILY_MOVE:.0%} gate"
                )
                continue  # drop this row

            # ── Gate 2: Zero or negative price ────────────────────────────────
            if row['adj_close'] <= 0:
                violations.append({
                    'date':       row['date'],
                    'ticker':     ticker,
                    'issue_type': 'zero_price',
                    'raw_value':  float(row['adj_close']),
                    'action':     'rejected',
                    'detail':     'adj_close <= 0',
                })
                logger.warning(f"⚠️  REJECTED {ticker} on {row['date']}: adj_close <= 0")
                continue

            clean_rows.append(row.to_dict())

    # ── Log violations to DB ──────────────────────────────────────────────────
    if violations and log_to_db:
        _log_violations_to_db(violations)

    result = pd.DataFrame(clean_rows)
    if not result.empty:
        result = result.drop(columns=['daily_return'], errors='ignore')

    logger.info(
        f"Validation complete: {len(result)} clean rows, "
        f"{len(violations)} rejected"
    )
    return result


def _log_violations_to_db(violations: list):
    """Write validation violations to data_validation_log table."""
    try:
        from engine.db.db import get_session
        from sqlalchemy import text
        session = get_session()
        for v in violations:
            session.execute(text("""
                INSERT INTO data_validation_log
                    (date, ticker, issue_type, raw_value, action, detail)
                VALUES (:date, :ticker, :issue_type, :raw_value, :action, :detail)
            """), v)
        session.commit()
        session.close()
    except Exception as e:
        logger.warning(f"Could not log violations to DB: {e}")


def check_staleness(df: pd.DataFrame, max_gap_days: int = 5) -> list:
    """
    Detects tickers with gaps larger than max_gap_days.
    Returns list of {ticker, last_date, gap_days} dicts.
    """
    import datetime
    today = datetime.date.today()
    stale = []

    if df.empty:
        return stale

    for ticker, group in df.groupby('ticker'):
        last_date = pd.to_datetime(group['date']).max().date()
        gap = (today - last_date).days
        # Allow weekend gap (2 days) + buffer
        if gap > max_gap_days:
            stale.append({
                'ticker':    ticker,
                'last_date': str(last_date),
                'gap_days':  gap,
            })
            logger.warning(f"⚠️  Stale data: {ticker} last seen {last_date} ({gap} days ago)")

    return stale
