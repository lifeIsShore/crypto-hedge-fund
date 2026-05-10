# engine/screens/etf_divergence.py
"""
ETF vs Component Divergence Screen.
Implements the 4-scenario framework from todos/etf_component_divergence_strategy.md.

Detection: stock underperforms its ETF by MIN_DIVERGENCE_PCT over WINDOW_DAYS
           while ETF is rising (confirming sector strength, not market-wide weakness).

Scenarios:
  1 — Temporary Rotation:      Potential buy (best risk/reward)
  2 — Stock-specific bad news: Watch list / caution
  3 — Valuation compression:   Wait for better entry
  4 — Thesis break:            Avoid / exit existing position

Labels are collected via the Streamlit dashboard and become ML training data
once >150 observations with 30-day outcomes are available.
"""

import pandas as pd
import uuid
import logging
import json
from sqlalchemy import text

logger = logging.getLogger(__name__)

# ── ETF → top component map (extend as needed) ─────────────────────────────
ETF_COMPONENT_MAP = {
    'EXXT.DE': ['NVDA', 'META', 'AMZN', 'GOOGL', 'MSF.DE', 'APC.DE', 'TSLA', 'CRM', 'ADBE', 'NFLX'],
    'EXS1.DE': ['SAP.DE', 'SIE.DE', 'ALV.DE', 'MUV2.DE', 'DTE.DE', 'IFX.DE', 'BMW.DE', 'BAYN.DE'],
    'EUNL.DE': ['MSF.DE', 'APC.DE', 'AMZN', 'NVDA', 'GOOGL', 'META', 'ASML.AS', 'NOV.DE'],
}

MIN_DIVERGENCE_PCT = 0.05   # stock must lag ETF by at least 5%
ETF_MIN_UP         = 0.03   # ETF must be rising at least 3% (confirming sector strength)
WINDOW_DAYS        = 28     # lookback window for divergence calculation


# ─────────────────────────────────────────────────────────────────────────────
# DETECTION
# ─────────────────────────────────────────────────────────────────────────────

def detect_divergences(date: str) -> list:
    """
    Scans all ETF-component pairs for divergences over WINDOW_DAYS.
    Returns list of divergence event dicts.
    """
    # Collect all tickers needed
    all_tickers = set(ETF_COMPONENT_MAP.keys())
    for components in ETF_COMPONENT_MAP.values():
        all_tickers.update(components)
    all_tickers = list(all_tickers)

    # Load returns from DB
    from engine.features.feature_store import load_returns_from_db
    log_returns = load_returns_from_db(all_tickers, lookback_days=WINDOW_DAYS + 10)

    if log_returns.empty:
        logger.warning("ETF divergence: no price data in DB")
        return []

    divergences = []

    for etf, components in ETF_COMPONENT_MAP.items():
        if etf not in log_returns.columns:
            logger.debug(f"ETF {etf} not in price data — skipping")
            continue

        # Cumulative log return over window
        etf_log_ret = float(log_returns[etf].tail(WINDOW_DAYS).sum())
        etf_pct_ret = (pd.np.exp(etf_log_ret) - 1) if hasattr(pd, 'np') else (
            __import__('numpy').exp(etf_log_ret) - 1
        )

        if etf_pct_ret < ETF_MIN_UP:
            # ETF not rising — divergence would be market-wide, not stock-specific
            continue

        for ticker in components:
            if ticker not in log_returns.columns:
                continue

            stock_log_ret = float(log_returns[ticker].tail(WINDOW_DAYS).sum())
            import numpy as np
            stock_pct_ret = np.exp(stock_log_ret) - 1
            divergence    = etf_pct_ret - stock_pct_ret

            if divergence >= MIN_DIVERGENCE_PCT:
                divergences.append({
                    'ticker':           ticker,
                    'etf_reference':    etf,
                    'detected_at':      date,
                    'window_days':      WINDOW_DAYS,
                    'etf_return_pct':   round(float(etf_pct_ret), 4),
                    'stock_return_pct': round(float(stock_pct_ret), 4),
                    'divergence_pct':   round(float(divergence), 4),
                })

    logger.info(f"ETF divergence scan: {len(divergences)} events detected for {date}")
    return divergences


def save_divergence_events(divergences: list):
    """Saves new divergence events to DB (skips duplicates)."""
    if not divergences:
        return

    from engine.db.db import get_session

    session = get_session()
    new_count = 0
    try:
        for d in divergences:
            # Check for existing entry (UNIQUE constraint: ticker + etf + detected_at)
            existing = session.execute(text("""
                SELECT id FROM divergence_labels
                WHERE ticker = :ticker
                  AND etf_reference = :etf
                  AND detected_at = :date
            """), {
                'ticker': d['ticker'],
                'etf':    d['etf_reference'],
                'date':   d['detected_at'],
            }).fetchone()

            if existing:
                continue  # already logged

            session.execute(text("""
                INSERT INTO divergence_labels
                    (ticker, etf_reference, detected_at, window_days,
                     etf_return_pct, stock_return_pct, divergence_pct)
                VALUES
                    (:ticker, :etf, :date, :window, :etf_ret, :stock_ret, :div)
            """), {
                'ticker':    d['ticker'],
                'etf':       d['etf_reference'],
                'date':      d['detected_at'],
                'window':    d['window_days'],
                'etf_ret':   d['etf_return_pct'],
                'stock_ret': d['stock_return_pct'],
                'div':       d['divergence_pct'],
            })
            new_count += 1

        session.commit()
        if new_count:
            logger.info(f"Saved {new_count} new divergence events to DB")
    except Exception as e:
        session.rollback()
        logger.error(f"save_divergence_events failed: {e}")
        raise
    finally:
        session.close()


# ─────────────────────────────────────────────────────────────────────────────
# LABELING (called from dashboard)
# ─────────────────────────────────────────────────────────────────────────────

def apply_scenario_label(
    divergence_id: str,
    scenario: int,
    confidence: str,
    notes: str,
    checklist: dict,
):
    """
    Saves a human label for a divergence event.
    Called from dashboard/pages/divergence_labeler.py.

    Args:
        divergence_id: UUID from divergence_labels table
        scenario:      1, 2, 3, or 4
        confidence:    'low', 'medium', or 'high'
        notes:         analyst's free-text reasoning
        checklist:     dict of boolean answers from the checklist
    """
    from engine.db.db import get_session

    session = get_session()
    try:
        session.execute(text("""
            UPDATE divergence_labels SET
                scenario_label    = :scenario,
                confidence        = :confidence,
                notes             = :notes,
                checklist_answers = :checklist,
                labeled_at        = datetime('now')
            WHERE id = :id
        """), {
            'id':         divergence_id,
            'scenario':   scenario,
            'confidence': confidence,
            'notes':      notes,
            'checklist':  json.dumps(checklist),
        })
        session.commit()
        logger.info(f"Divergence {divergence_id} labeled: Scenario {scenario}, {confidence} confidence")
    except Exception as e:
        session.rollback()
        logger.error(f"apply_scenario_label failed: {e}")
        raise
    finally:
        session.close()


def get_unlabeled_divergences(limit: int = 20) -> pd.DataFrame:
    """Returns unlabeled divergence events for the labeler UI."""
    from engine.db.db import get_session

    session = get_session()
    try:
        result = session.execute(text("""
            SELECT id, ticker, etf_reference, detected_at,
                   etf_return_pct, stock_return_pct, divergence_pct
            FROM divergence_labels
            WHERE scenario_label IS NULL
            ORDER BY detected_at DESC
            LIMIT :limit
        """), {'limit': limit})
        rows = result.fetchall()
    finally:
        session.close()

    return pd.DataFrame(rows, columns=[
        'id', 'ticker', 'etf', 'detected_at',
        'etf_return_pct', 'stock_return_pct', 'divergence_pct'
    ])


# ─────────────────────────────────────────────────────────────────────────────
# OUTCOME FILLING (daily scheduler job)
# ─────────────────────────────────────────────────────────────────────────────

def fill_outcome_data():
    """
    Fills outcome_30d and outcome_90d for labeled events where
    30 or 90 days have elapsed since detection.
    Safe to run daily — skips already-filled outcomes.
    """
    from engine.db.db import get_session
    import datetime

    session = get_session()
    try:
        result = session.execute(text("""
            SELECT id, ticker, detected_at
            FROM divergence_labels
            WHERE scenario_label IS NOT NULL
              AND (outcome_30d IS NULL OR outcome_90d IS NULL)
        """))
        rows = result.fetchall()

        filled = 0
        today  = datetime.date.today()

        for div_id, ticker, detected_at in rows:
            if isinstance(detected_at, str):
                detected_at = datetime.date.fromisoformat(detected_at)

            for horizon_days, col in [(30, 'outcome_30d'), (90, 'outcome_90d')]:
                # Check if enough days have passed
                if (today - detected_at).days < horizon_days:
                    continue

                target_date = detected_at + datetime.timedelta(days=horizon_days)

                # Entry price (closest day on or after detected_at)
                entry = session.execute(text("""
                    SELECT adj_close FROM prices
                    WHERE ticker = :ticker AND date >= :detected
                    ORDER BY date ASC LIMIT 1
                """), {'ticker': ticker, 'detected': str(detected_at)}).fetchone()

                # Exit price (closest day on or after target_date)
                exit_ = session.execute(text("""
                    SELECT adj_close FROM prices
                    WHERE ticker = :ticker AND date >= :target
                    ORDER BY date ASC LIMIT 1
                """), {'ticker': ticker, 'target': str(target_date)}).fetchone()

                if entry and exit_ and entry[0] and exit_[0]:
                    fwd_return = round((exit_[0] - entry[0]) / entry[0], 4)
                    session.execute(text(f"""
                        UPDATE divergence_labels
                        SET {col} = :ret
                        WHERE id = :id
                    """), {'ret': fwd_return, 'id': div_id})
                    filled += 1

        session.commit()
        if filled:
            logger.info(f"Outcome fill: updated {filled} divergence outcomes")

    except Exception as e:
        session.rollback()
        logger.error(f"fill_outcome_data failed: {e}")
    finally:
        session.close()
