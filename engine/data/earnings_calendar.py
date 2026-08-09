# engine/data/earnings_calendar.py
"""
J4 — Earnings Calendar Integration.
See before-go-live/J4-earnings-calendar.md for design rationale.

Weekly fetch of upcoming earnings dates via Finnhub (key already in .env).
Feeds two consumers:
  1. Pre-earnings position throttle in engine/execution/order_manager.py
  2. A forward-looking trigger for the PEAD engine (checks for tickers that
     reported 1-2 days ago instead of only scanning for price anomalies)

Finnhub free tier: 60 calls/min, calendar endpoint covers ~30 days forward.
Coverage is thin for non-US tickers (.DE, .PA, etc.) — this degrades
gracefully, same pattern as other European-data gaps in this codebase.

IMPORTANT ticker-mapping note: Finnhub's calendar returns US-style symbols
(e.g. 'NVDA'), but this engine trades most of those under a .DE-suffixed
primary ticker (e.g. 'NVD.DE', per TICKER_MAPPING in portfolio/src/config.py).
run_earnings_ingestion() takes a `symbol_to_primary` dict so rows are stored
under the SAME ticker key the rest of the engine (order_manager, PEAD) uses —
otherwise earnings_calendar rows would silently never match anything.
"""
import requests
import logging
import os
from datetime import date, timedelta
from sqlalchemy import text
from engine.db.db import get_session

logger = logging.getLogger(__name__)

FINNHUB_BASE = "https://finnhub.io/api/v1/calendar/earnings"
LOOKAHEAD_DAYS = 30


def fetch_earnings_calendar(api_key: str = None) -> list:
    """Fetches upcoming earnings dates for the next LOOKAHEAD_DAYS. Returns raw Finnhub rows."""
    api_key = api_key or os.getenv("FINNHUB_API_KEY")
    if not api_key:
        logger.error("[earnings_calendar] FINNHUB_API_KEY not set — skipping")
        return []

    today = date.today()
    to_date = today + timedelta(days=LOOKAHEAD_DAYS)

    try:
        resp = requests.get(FINNHUB_BASE, params={
            "from": today.isoformat(),
            "to": to_date.isoformat(),
            "token": api_key,
        }, timeout=15)
        resp.raise_for_status()
        return resp.json().get("earningsCalendar", [])
    except Exception as e:
        logger.error(f"[earnings_calendar] Fetch failed: {e}")
        return []


def run_earnings_ingestion(symbol_to_primary: dict) -> int:
    """
    Fetches and persists earnings dates, filtered + remapped to this engine's
    tradeable universe.

    symbol_to_primary: dict mapping the US-style symbol Finnhub returns
    (e.g. 'NVDA') to the primary ticker this engine actually trades
    (e.g. 'NVD.DE'). Build this once in the scheduler from TICKER_MAPPING +
    identity entries for tickers already in US form (see scheduler.py wiring).
    Rows for symbols not in this dict are skipped — no point storing
    thousands of tickers never traded here.
    """
    rows = fetch_earnings_calendar()
    if not rows:
        return 0

    session = get_session()
    count = 0
    try:
        for row in rows:
            symbol = row.get("symbol")
            ticker = symbol_to_primary.get(symbol)
            if ticker is None:
                continue
            session.execute(text("""
                INSERT INTO earnings_calendar
                    (ticker, report_date, report_time, eps_estimate, revenue_estimate)
                VALUES (:ticker, :report_date, :report_time, :eps_est, :rev_est)
                ON CONFLICT (ticker, report_date) DO UPDATE SET
                    report_time      = :report_time,
                    eps_estimate     = :eps_est,
                    revenue_estimate = :rev_est,
                    fetched_at       = datetime('now')
            """), {
                "ticker": ticker,
                "report_date": row.get("date"),
                "report_time": row.get("hour"),  # Finnhub returns 'bmo'/'amc'/'dmh'
                "eps_est": row.get("epsEstimate"),
                "rev_est": row.get("revenueEstimate"),
            })
            count += 1
        session.commit()
    except Exception as e:
        session.rollback()
        logger.error(f"[earnings_calendar] Persist failed: {e}")
        raise
    finally:
        session.close()

    logger.info(f"[earnings_calendar] {count} earnings dates persisted (of {len(rows)} fetched)")
    return count


def get_reporting_soon(tickers: list, within_days: int = 3) -> set:
    """
    Returns the subset of `tickers` (primary form, e.g. 'NVD.DE') reporting
    within `within_days` of today. Used by order_manager's pre-earnings
    throttle (J4 Step 3).
    """
    if not tickers:
        return set()
    session = get_session()
    try:
        placeholders = ','.join([f':t{i}' for i in range(len(tickers))])
        params = {f't{i}': t for i, t in enumerate(tickers)}
        rows = session.execute(text(f"""
            SELECT DISTINCT ticker FROM earnings_calendar
            WHERE ticker IN ({placeholders})
            AND date(report_date) BETWEEN date('now') AND date('now', '+{int(within_days)} days')
        """), params).fetchall()
        return {r[0] for r in rows}
    except Exception as e:
        logger.warning(f"[earnings_calendar] get_reporting_soon failed (non-fatal): {e}")
        return set()
    finally:
        session.close()


def get_recently_reported(tickers: list, within_days: int = 2) -> set:
    """
    Returns tickers (primary form) that reported earnings in the last
    `within_days` days. Forward-looking trigger for the PEAD engine (J4
    Step 4) — lets PEAD prioritize these tickers first instead of scanning
    the full universe for post-hoc price/volume anomalies.
    """
    if not tickers:
        return set()
    session = get_session()
    try:
        placeholders = ','.join([f':t{i}' for i in range(len(tickers))])
        params = {f't{i}': t for i, t in enumerate(tickers)}
        rows = session.execute(text(f"""
            SELECT DISTINCT ticker FROM earnings_calendar
            WHERE ticker IN ({placeholders})
            AND date(report_date) BETWEEN date('now', '-{int(within_days)} days') AND date('now')
        """), params).fetchall()
        return {r[0] for r in rows}
    except Exception as e:
        logger.warning(f"[earnings_calendar] get_recently_reported failed (non-fatal): {e}")
        return set()
    finally:
        session.close()
