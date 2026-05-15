import os
import sys

# Ensure root is in path for absolute imports
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.normpath(os.path.join(_HERE, '..', '..'))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from portfolio.src.config import ASSET_UNIVERSE, TICKER_MAPPING

# Load .env if present
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass
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
# Emergency FX fallbacks — only used when all APIs fail.
FALLBACK_USDEUR = float(os.getenv('FALLBACK_USDEUR', '0.92'))
FALLBACK_GBPEUR = float(os.getenv('FALLBACK_GBPEUR', '1.17'))

# API Keys for backups (loaded from .env)
API_KEYS = {
    'twelvedata':   os.getenv('TWELVEDATA_API_KEY', ''),
    'alphavantage': os.getenv('ALPHAVANTAGE_API_KEY', ''),
    'finnhub':      os.getenv('FINNHUB_API_KEY', '')
}

def fetch_fx_history(from_date: str, to_date: str) -> dict:
    """
    Fetches daily USD→EUR and GBP→EUR rates.
    Tries yfinance (Primary) -> TwelveData (Backup 1) -> AlphaVantage (Backup 2) -> Finnhub (Backup 3)
    Returns: {'USDEUR': {date_str: rate}, 'GBPEUR': {date_str: rate}}
    """
    rates = {'USDEUR': {}, 'GBPEUR': {}}
    pairs = {
        'USDEUR': ('EURUSD=X', True),    # invert
        'GBPEUR': ('GBPEUR=X', False),   # direct
    }

    for name, (pair, invert) in pairs.items():
        # 1. Try yfinance
        try:
            data = yf.download(pair, start=from_date, end=to_date, auto_adjust=True, progress=False)
            if not data.empty:
                # Handle MultiIndex and extract 'Close'
                if isinstance(data.columns, pd.MultiIndex):
                    series = data.xs('Close', axis=1, level=0)
                else:
                    series = data['Close']
                
                # Squeeze to handle redundant dimensions
                series = series.squeeze()
                if isinstance(series, pd.DataFrame):
                    series = series.iloc[:, 0]
                
                series = series.dropna()
                if invert: series = 1 / series
                
                for date_idx, val in series.items():
                    rates[name][str(date_idx.date())] = float(val)
                logger.info(f"FX fetched from yfinance: {name}")
                continue
        except Exception as e:
            logger.warning(f"yfinance FX failed for {name}: {e}")

        # 2. Try Twelve Data Backup
        try:
            symbol = "EUR/USD" if name == "USDEUR" else "GBP/EUR"
            url = f"https://api.twelvedata.com/time_series?symbol={symbol}&interval=1day&start_date={from_date}&end_date={to_date}&apikey={API_KEYS['twelvedata']}"
            import requests
            resp = requests.get(url).json()
            if resp.get('status') == 'ok':
                for val in resp.get('values', []):
                    dt = val['datetime']
                    rate = float(val['close'])
                    if name == "USDEUR": rate = 1 / rate
                    rates[name][dt] = rate
                logger.info(f"FX fetched from TwelveData: {name}")
                continue
        except Exception as e:
            logger.warning(f"TwelveData FX failed: {e}")

        # 3. Try AlphaVantage Backup
        try:
            from_sym = "USD" if name == "USDEUR" else "GBP"
            url = f"https://www.alphavantage.co/query?function=FX_DAILY&from_symbol={from_sym}&to_symbol=EUR&apikey={API_KEYS['alphavantage']}"
            resp = requests.get(url).json()
            time_series = resp.get('Time Series FX (Daily)', {})
            if time_series:
                for dt, vals in time_series.items():
                    # AlphaVantage returns last 100 days, filter by range
                    if from_date <= dt <= to_date:
                        rates[name][dt] = float(vals['4. close'])
                logger.info(f"FX fetched from AlphaVantage: {name}")
                continue
        except Exception as e:
            logger.warning(f"AlphaVantage FX failed: {e}")

        # 4. Try Finnhub Backup
        try:
            # Finnhub uses OANDA symbols for FX candles
            symbol = "OANDA:EUR_USD" if name == "USDEUR" else "OANDA:GBP_EUR"
            from_ts = int(pd.Timestamp(from_date).timestamp())
            to_ts = int(pd.Timestamp(to_date).timestamp())
            url = f"https://finnhub.io/api/v1/forex/candle?symbol={symbol}&resolution=D&from={from_ts}&to={to_ts}&token={API_KEYS['finnhub']}"
            resp = requests.get(url).json()
            if resp.get('s') == 'ok':
                for t, c in zip(resp['t'], resp['c']):
                    dt = str(pd.Timestamp(t, unit='s').date())
                    rate = float(c)
                    if name == "USDEUR": rate = 1 / rate
                    rates[name][dt] = rate
                logger.info(f"FX fetched from Finnhub: {name}")
                continue
        except Exception as e:
            logger.warning(f"Finnhub FX failed: {e}")

    # Persist to fx_rates table
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
                val = float(df.at[i, col])
                # UK stocks are in pence, convert to GBP first
                if any(ticker.endswith(s) for s in GBP_SUFFIXES):
                    val = val / 100.0
                df.at[i, col] = val * rate

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
# BACKUP STOCK SOURCES (TwelveData & Finnhub)
# ─────────────────────────────────────────────────────────────────────────────

async def _fetch_twelvedata_single(http_session: aiohttp.ClientSession, ticker: str, from_date: str, to_date: str) -> pd.DataFrame:
    """Fetch history from TwelveData (Backup 1)."""
    api_key = API_KEYS['twelvedata']
    if not api_key: return pd.DataFrame()
    
    url = f"https://api.twelvedata.com/time_series?symbol={ticker}&interval=1day&start_date={from_date}&end_date={to_date}&apikey={api_key}"
    async with http_session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
        data = await resp.json()
    
    if data.get('status') != 'ok' or not data.get('values'):
        return pd.DataFrame()
    
    rows = []
    for v in data['values']:
        rows.append({
            'date':      pd.to_datetime(v['datetime']).date(),
            'ticker':    ticker,
            'open':      float(v['open']),
            'high':      float(v['high']),
            'low':       float(v['low']),
            'close':     float(v['close']),
            'volume':    int(v['volume']) if v.get('volume') else None,
            'adj_close': float(v['close']),
            'source':    'twelvedata',
        })
    return pd.DataFrame(rows)


async def _fetch_finnhub_single(http_session: aiohttp.ClientSession, ticker: str, from_date: str, to_date: str) -> pd.DataFrame:
    """Fetch history from Finnhub (Backup 2)."""
    api_key = API_KEYS['finnhub']
    if not api_key: return pd.DataFrame()
    
    from_ts = int(pd.Timestamp(from_date).timestamp())
    to_ts = int(pd.Timestamp(to_date).timestamp())
    url = f"https://finnhub.io/api/v1/stock/candle?symbol={ticker}&resolution=D&from={from_ts}&to={to_ts}&token={api_key}"
    
    async with http_session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
        data = await resp.json()
    
    if data.get('s') != 'ok':
        return pd.DataFrame()
    
    rows = []
    for t, o, h, l, c, v in zip(data['t'], data['o'], data['h'], data['l'], data['c'], data['v']):
        rows.append({
            'date':      pd.Timestamp(t, unit='s').date(),
            'ticker':    ticker,
            'open':      float(o),
            'high':      float(h),
            'low':       float(l),
            'close':     float(c),
            'volume':    int(v),
            'adj_close': float(c),
            'source':    'finnhub',
        })
    return pd.DataFrame(rows)


async def _fetch_alphavantage_single(http_session: aiohttp.ClientSession, ticker: str, from_date: str, to_date: str) -> pd.DataFrame:
    """Fetch history from AlphaVantage (Deep Backup)."""
    api_key = API_KEYS['alphavantage']
    if not api_key: return pd.DataFrame()
    
    # Using TIME_SERIES_DAILY_ADJUSTED for stock history
    url = f"https://www.alphavantage.co/query?function=TIME_SERIES_DAILY_ADJUSTED&symbol={ticker}&apikey={api_key}"
    async with http_session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
        data = await resp.json()
    
    time_series = data.get('Time Series (Daily)', {})
    if not time_series:
        return pd.DataFrame()
    
    rows = []
    for dt, v in time_series.items():
        if from_date <= dt <= to_date:
            rows.append({
                'date':      pd.to_datetime(dt).date(),
                'ticker':    ticker,
                'open':      float(v['1. open']),
                'high':      float(v['2. high']),
                'low':       float(v['3. low']),
                'close':     float(v['4. close']),
                'volume':    int(v['6. volume']),
                'adj_close': float(v['5. adjusted close']),
                'source':    'alphavantage',
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
    Async multi-ticker fetch with per-ticker Polygon→TwelveData→Finnhub→yfinance fallback.
    Now includes a secondary fallback to a US ticker if the primary (Xetra) fails.
    """
    frames = []
    use_polygon = bool(POLYGON_API_KEY)

    async with aiohttp.ClientSession() as http_session:
        for ticker in tickers:
            df = pd.DataFrame()
            
            # --- Try Primary Ticker ---
            # Sequence: yfinance (Free) -> Polygon -> TwelveData -> Finnhub -> AlphaVantage
            try:
                # 1. yfinance
                df = _fetch_yfinance_single(ticker, from_date, to_date)
                
                # 2. Polygon
                if df.empty and use_polygon:
                    df = await _fetch_polygon_single(http_session, ticker, from_date, to_date)
                
                # 3. TwelveData
                if df.empty:
                    df = await _fetch_twelvedata_single(http_session, ticker, from_date, to_date)
                
                # 4. Finnhub
                if df.empty:
                    df = await _fetch_finnhub_single(http_session, ticker, from_date, to_date)

                # 5. AlphaVantage
                if df.empty:
                    df = await _fetch_alphavantage_single(http_session, ticker, from_date, to_date)
                    
            except Exception as e:
                logger.warning(f"Primary fetch chain failed for {ticker}: {e}")

            # --- Fallback to US Ticker if Primary fails ---
            if df.empty and ticker in TICKER_MAPPING:
                fallback_ticker = TICKER_MAPPING[ticker]
                logger.info(f"Primary {ticker} failed or empty — trying fallback: {fallback_ticker}")
                try:
                    # 1. yfinance
                    df = _fetch_yfinance_single(fallback_ticker, from_date, to_date)
                    
                    # 2. Polygon
                    if df.empty and use_polygon:
                        df = await _fetch_polygon_single(http_session, fallback_ticker, from_date, to_date)
                    
                    # 3. TwelveData
                    if df.empty:
                        df = await _fetch_twelvedata_single(http_session, fallback_ticker, from_date, to_date)
                    
                    # 4. Finnhub
                    if df.empty:
                        df = await _fetch_finnhub_single(http_session, fallback_ticker, from_date, to_date)

                    # 5. AlphaVantage
                    if df.empty:
                        df = await _fetch_alphavantage_single(http_session, fallback_ticker, from_date, to_date)
                    
                    if not df.empty:
                        # CRITICAL: We tag the data with the ORIGINAL (Primary) ticker
                        # so the rest of the engine (ledger, optimizer) recognizes it.
                        df['ticker'] = ticker
                        logger.info(f"Successfully fetched fallback data for {ticker} using {fallback_ticker}")
                except Exception as e:
                    logger.warning(f"Fallback fetch chain failed for {fallback_ticker}: {e}")

            if not df.empty:
                frames.append(df)
            else:
                logger.warning(f"All sources failed for {ticker} — skipped")

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
