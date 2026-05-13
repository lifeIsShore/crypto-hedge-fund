import os
import sys

# Ensure root is in path for absolute imports
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.normpath(os.path.join(_HERE, '..', '..'))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from portfolio.src.config import ASSET_UNIVERSE
"""
Production data ingestion pipeline.
Primary source:  Polygon.io (requires POLYGON_API_KEY env var)
Fallback source: yfinance (existing data_loader.py logic)

FX conversion is applied BEFORE writing to the DB:
  All prices stored in the DB are EUR-equivalent.
  Downstream code (features, optimizer, risk) never needs to re-convert.

EUR suffix map (same as portfolio/src/data_loader.py):
  .DE  → Xetra/Frankfurt — already EUR
  .AS  → Amsterdam Euronext — already EUR
  .PA  → Paris Euronext — already EUR
  .L   → London — GBP → multiply by GBPEUR rate
  (no suffix) → US tickers — USD → multiply by USDEUR rate
"""

import asyncio
import aiohttp
import pandas as pd
import numpy as np
import yfinance as yf
import os
import logging
from datetime import datetime, timedelta
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)

# FX suffix detection (mirrors portfolio/src/data_loader.py)
EUR_SUFFIXES = ('.DE', '.AS', '.PA')
GBP_SUFFIXES = ('.L',)

POLYGON_API_KEY = os.getenv('POLYGON_API_KEY', '')
# Emergency FX fallbacks — only used when yfinance fails to fetch live rates.
# Update these whenever a persistent rate divergence exceeds ~5%.
# Source: ECB reference rates (https://www.ecb.europa.eu/stats/exchange/eurofxref/)
FALLBACK_USDEUR = float(os.getenv('FALLBACK_USDEUR', '0.92'))
FALLBACK_GBPEUR = float(os.getenv('FALLBACK_GBPEUR', '1.17'))


# ─────────────────────────────────────────────────────────────────────────────
# FX UTILITIES
# ─────────────────────────────────────────────────────────────────────────────

def fetch_fx_history(from_date: str, to_date: str) -> dict:
    """
    Fetches daily USD→EUR and GBP→EUR rates from yfinance.
    Returns: {'USDEUR': {date_str: rate}, 'GBPEUR': {date_str: rate}}
    Also persists rates to the fx_rates table (Stream 1).
    Falls back to constants on failure; logs fallback events to DB.
    """
    rates = {'USDEUR': {}, 'GBPEUR': {}}
    # yfinance EURUSD=X gives USD per 1 EUR (i.e. 1.08 = $1.08 per €1)
    # We want EUR per 1 USD, so invert.
    pairs = {
        'USDEUR': ('EURUSD=X', True),    # EURUSD=X is USD per EUR → invert to get EUR per USD
        'GBPEUR': ('GBPEUR=X', False),   # GBPEUR=X is EUR per GBP — no inversion needed
    }

    for name, (pair, invert) in pairs.items():
        try:
            data = yf.download(pair, start=from_date, end=to_date,
                               auto_adjust=True, progress=False)
            if data.empty:
                raise ValueError(f'Empty data for {pair}')
            series = data['Close'].dropna()
            if invert:
                series = 1 / series
            for date_idx, rate in series.items():
                rates[name][str(date_idx.date())] = float(rate)
            logger.info(f"FX history fetched: {name} ({len(series)} days)")
        except Exception as e:
            logger.warning(
                f"FX fetch failed for {name} ({e}) — "
                f"will use fallback constant in apply_fx_conversion"
            )
            _log_fx_fallback(name, str(e))

    # Persist to fx_rates table (Stream 1)
    _persist_fx_rates(rates)

    return rates


def _persist_fx_rates(rates: dict):
    """
    Writes fetched FX rates to the fx_rates table.
    Safe to run multiple times — upserts on (date, pair).
    Stream 1: enables FX history queries from dashboard and regime engine.
    """
    try:
        from engine.db.db import get_session
        from sqlalchemy import text

        session = get_session()
        count = 0
        try:
            for pair_name, date_rate_map in rates.items():
                for date_str, rate in date_rate_map.items():
                    session.execute(text("""
                        INSERT INTO fx_rates (date, pair, rate, source)
                        VALUES (:date, :pair, :rate, 'yfinance')
                        ON CONFLICT (date, pair) DO UPDATE SET
                            rate   = :rate,
                            source = 'yfinance'
                    """), {'date': date_str, 'pair': pair_name, 'rate': rate})
                    count += 1
            session.commit()
            logger.info(f"FX rates persisted: {count} rows across {len(rates)} pairs")
        except Exception as e:
            session.rollback()
            logger.warning(f"FX rate persistence failed: {e}")
        finally:
            session.close()
    except Exception as e:
        logger.warning(f"Could not persist FX rates: {e}")


def apply_fx_conversion(df: pd.DataFrame, fx_rates: dict) -> pd.DataFrame:
    """
    Converts non-EUR prices to EUR using daily FX rates.
    Applied BEFORE persisting to DB — DB always stores EUR.
    """
    if df.empty:
        return df

    df = df.copy()
    usd_eur_map = fx_rates.get('USDEUR', {})
    gbp_eur_map = fx_rates.get('GBPEUR', {})
    price_cols = ['open', 'high', 'low', 'close', 'adj_close']

    for i, row in df.iterrows():
        ticker   = row['ticker']
        date_str = str(row['date'])

        if any(ticker.endswith(s) for s in EUR_SUFFIXES):
            continue  # Already EUR

        elif any(ticker.endswith(s) for s in GBP_SUFFIXES):
            rate = gbp_eur_map.get(date_str, FALLBACK_GBPEUR)
        else:
            # USD (no suffix)
            rate = usd_eur_map.get(date_str, FALLBACK_USDEUR)

        for col in price_cols:
            if col in df.columns and pd.notna(df.at[i, col]):
                df.at[i, col] = df.at[i, col] * rate

    df['currency'] = 'EUR'
    return df


def _log_fx_fallback(pair_name: str, error: str):
    try:
        from engine.db.db import get_session
        from sqlalchemy import text
        session = get_session()
        session.execute(text("""
            INSERT INTO data_validation_log
                (date, ticker, issue_type, raw_value, action, detail)
            VALUES (CURRENT_DATE, :ticker, 'fx_fallback', NULL, 'fallback_used', :detail)
        """), {'ticker': pair_name, 'detail': error[:200]})
        session.commit()
        session.close()
    except Exception:
        pass


# ─────────────────────────────────────────────────────────────────────────────
# POLYGON.IO PRIMARY SOURCE
# ─────────────────────────────────────────────────────────────────────────────

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
async def _fetch_polygon_single(
    http_session: aiohttp.ClientSession,
    ticker: str,
    from_date: str,
    to_date: str,
) -> pd.DataFrame:
    """Fetch one ticker from Polygon adjusted OHLCV endpoint."""
    url = (
        f'https://api.polygon.io/v2/aggs/ticker/{ticker}'
        f'/range/1/day/{from_date}/{to_date}'
    )
    params = {
        'adjusted': 'true',
        'sort':     'asc',
        'limit':    '50000',
        'apiKey':   POLYGON_API_KEY,
    }
    async with http_session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=60)) as resp:
        data = await resp.json()

    if data.get('status') not in ('OK', 'DELAYED') or not data.get('results'):
        raise ValueError(f"Polygon: no results for {ticker} — status={data.get('status')}")

    rows = []
    for r in data['results']:
        rows.append({
            'date':      pd.Timestamp(r['t'], unit='ms').date(),
            'ticker':    ticker,
            'open':      r.get('o'),
            'high':      r.get('h'),
            'low':       r.get('l'),
            'close':     r['c'],
            'volume':    r.get('v'),
            'adj_close': r['c'],   # Polygon returns adjusted prices when adjusted=true
            'source':    'polygon',
        })
    return pd.DataFrame(rows)


# ─────────────────────────────────────────────────────────────────────────────
# YFINANCE FALLBACK SOURCE
# ─────────────────────────────────────────────────────────────────────────────

def _fetch_yfinance_single(ticker: str, from_date: str, to_date: str) -> pd.DataFrame:
    """
    Fallback: uses existing yfinance logic (same as portfolio/src/data_loader.py).
    Returns same column structure as Polygon fetch.
    """
    try:
        raw = yf.download(
            ticker, start=from_date, end=to_date,
            auto_adjust=True, progress=False,
        )
    except Exception as e:
        logger.error(f"yfinance failed for {ticker}: {e}")
        return pd.DataFrame()

    if raw.empty:
        return pd.DataFrame()

    raw = raw.reset_index()
    # Handle multi-level columns from yfinance
    if hasattr(raw.columns, 'levels'):
        raw.columns = [c[0] if isinstance(c, tuple) else c for c in raw.columns]

    raw.columns = [str(c).lower().replace(' ', '_') for c in raw.columns]

    rows = []
    for _, row in raw.iterrows():
        rows.append({
            'date':      row['date'].date() if hasattr(row['date'], 'date') else row['date'],
            'ticker':    ticker,
            'open':      row.get('open'),
            'high':      row.get('high'),
            'low':       row.get('low'),
            'close':     row.get('close'),
            'volume':    int(row['volume']) if pd.notna(row.get('volume')) else None,
            'adj_close': row.get('close'),
            'source':    'yfinance',
        })
    return pd.DataFrame(rows)


# ─────────────────────────────────────────────────────────────────────────────
# ASYNC ORCHESTRATOR
# ─────────────────────────────────────────────────────────────────────────────

async def _fetch_all_async(tickers: list, from_date: str, to_date: str) -> pd.DataFrame:
    """
    Async multi-ticker fetch with per-ticker Polygon→yfinance fallback.
    """
    frames = []
    use_polygon = bool(POLYGON_API_KEY)

    if not use_polygon:
        logger.info("POLYGON_API_KEY not set — using yfinance for all tickers")

    async with aiohttp.ClientSession() as http_session:
        for ticker in tickers:
            if use_polygon:
                try:
                    df = await _fetch_polygon_single(http_session, ticker, from_date, to_date)
                    frames.append(df)
                    logger.debug(f"[Polygon] {ticker}: {len(df)} rows")
                    continue
                except Exception as e:
                    logger.warning(f"[Polygon] {ticker} failed ({e}) → yfinance fallback")

            # yfinance fallback (sync inside async — acceptable for small universes)
            df = _fetch_yfinance_single(ticker, from_date, to_date)
            if not df.empty:
                frames.append(df)
                logger.debug(f"[yfinance] {ticker}: {len(df)} rows")
            else:
                logger.warning(f"[yfinance] {ticker}: no data returned — skipped")

    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


# ─────────────────────────────────────────────────────────────────────────────
# DB PERSISTENCE
# ─────────────────────────────────────────────────────────────────────────────

def persist_prices(df: pd.DataFrame):
    """
    Upserts EUR-converted price rows into the prices table.
    ON CONFLICT: updates adj_close and source (handles data corrections).
    """
    if df.empty:
        logger.warning("persist_prices: empty DataFrame — nothing to write")
        return

    from engine.db.db import get_session
    from sqlalchemy import text

    session = get_session()
    count = 0
    try:
        for _, row in df.iterrows():
            session.execute(text("""
                INSERT INTO prices
                    (date, ticker, open, high, low, close, volume, adj_close, currency, source)
                VALUES
                    (:date, :ticker, :open, :high, :low, :close, :volume, :adj_close, :currency, :source)
                ON CONFLICT (date, ticker) DO UPDATE SET
                    adj_close = EXCLUDED.adj_close,
                    source    = EXCLUDED.source,
                    currency  = EXCLUDED.currency
            """), {
                'date':      row['date'],
                'ticker':    row['ticker'],
                'open':      row.get('open'),
                'high':      row.get('high'),
                'low':       row.get('low'),
                'close':     row.get('close'),
                'volume':    row.get('volume'),
                'adj_close': row.get('adj_close'),
                'currency':  row.get('currency', 'EUR'),
                'source':    row.get('source', 'unknown'),
            })
            count += 1

        session.commit()
        logger.info(f"Persisted {count} price rows to DB.")
    except Exception as e:
        session.rollback()
        logger.error(f"persist_prices failed: {e}")
        raise
    finally:
        session.close()


# ─────────────────────────────────────────────────────────────────────────────
# PUBLIC ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────

def run_ingestion(
    tickers: list,
    from_date: str,
    to_date: str,
    apply_fx: bool = True,
) -> pd.DataFrame:
    """
    Full ingestion pipeline:
      1. Fetch OHLCV from Polygon (fallback: yfinance)
      2. Validate prices (spike filter, zero-price filter)
      3. Apply FX conversion → all prices in EUR
      4. Persist prices to DB
      5. Persist FX rates to fx_rates table (Stream 1)

    Args:
        tickers:   list of ticker strings
        from_date: 'YYYY-MM-DD'
        to_date:   'YYYY-MM-DD'
        apply_fx:  set False only for testing (skips FX conversion)

    Returns:
        EUR-converted, validated DataFrame (same as what was persisted).
    """
    logger.info(
        f"Ingestion starting: {len(tickers)} tickers, "
        f"{from_date} → {to_date}, polygon={'yes' if POLYGON_API_KEY else 'no (yfinance only)'}"
    )

    # Step 1: Fetch
    df_raw = asyncio.run(_fetch_all_async(tickers, from_date, to_date))
    if df_raw.empty:
        logger.error("Ingestion: no data returned from any source")
        return pd.DataFrame()

    # Step 2: Validate
    from engine.data.validation import validate_prices
    df_clean = validate_prices(df_raw)

    if df_clean.empty:
        logger.error("Ingestion: all rows rejected by validation")
        return pd.DataFrame()

    # Step 3 + 5: FX conversion (also persists rates to fx_rates table)
    if apply_fx:
        fx_rates = fetch_fx_history(from_date, to_date)
        df_eur = apply_fx_conversion(df_clean, fx_rates)
    else:
        df_eur = df_clean
        df_eur['currency'] = 'EUR'

    # Step 4: Persist prices
    persist_prices(df_eur)

    logger.info(f"Ingestion complete: {len(df_eur)} rows persisted.")
    return df_eur


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('tickers', nargs='*', help='Tickers to ingest (defaults to config universe)')
    parser.add_argument('--days', type=int, default=30, help='Days of history to fetch')
    args = parser.parse_args()

    from datetime import date
    today = str(date.today())
    start_date = str(date.today() - timedelta(days=args.days))

    # Use CLI args if provided, otherwise the full config universe
    tickers_to_run = args.tickers if args.tickers else ASSET_UNIVERSE

    logging.basicConfig(level=logging.INFO)
    result = run_ingestion(tickers_to_run, start_date, today)
    print(f"\nResult: {len(result)} rows, tickers: {result['ticker'].unique().tolist()}")
