"""data_loader.py — Fetch price/macro data for crypto ML pipeline.
"""
import os, json, logging, time
from pathlib import Path
from datetime import datetime, timedelta
import pandas as pd
import asyncio
import ccxt.async_support as ccxt

PRICE_CACHE_TTL_DAYS = 7

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

import sys

_HERE = Path(__file__).resolve()
_ROOT = _HERE.parents[4]  
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

try:
    from portfolio.src.config import ASSET_UNIVERSE, TICKER_SECTORS
    UNIVERSE = {t: TICKER_SECTORS.get(t, "Unknown") for t in ASSET_UNIVERSE}
except ImportError:
    log.error("Could not import central config from portfolio.src.config.")
    UNIVERSE = {}

MACRO_SERIES = {
    "fed_funds":  "FEDFUNDS",
    "yield_10y":  "DGS10",
    "yield_2y":   "DGS2",
    "vix":        "VIXCLS",
    "cpi_yoy":    "CPIAUCSL",
    "dxy":        "DTWEXBGS",
}

RAW_DIR = Path(__file__).parent.parent / "data" / "raw"
RAW_DIR.mkdir(parents=True, exist_ok=True)


async def _fetch_ccxt_single(exchange, ticker, start_date_str, end_date_str):
    from_ts = int(pd.Timestamp(start_date_str).timestamp() * 1000)
    to_ts = int(pd.Timestamp(end_date_str).timestamp() * 1000)
    
    limit = 1000
    all_ohlcv = []
    current_ts = from_ts
    
    while current_ts < to_ts:
        try:
            ohlcv = await exchange.fetch_ohlcv(ticker, timeframe='1d', since=current_ts, limit=limit)
            if not ohlcv:
                break
            all_ohlcv.extend(ohlcv)
            current_ts = ohlcv[-1][0] + 1
        except Exception as e:
            log.warning(f"CCXT fetch error for {ticker}: {e}")
            break
            
    if not all_ohlcv:
        return pd.DataFrame()
        
    df = pd.DataFrame(all_ohlcv, columns=['timestamp', 'Open', 'High', 'Low', 'Close', 'Volume'])
    df['Date'] = pd.to_datetime(df['timestamp'], unit='ms').dt.date
    df['Adj Close'] = df['Close']
    df = df.set_index('Date')
    df = df[['Open', 'High', 'Low', 'Close', 'Adj Close', 'Volume']]
    return df


def fetch_price_data(tickers=None, start="2014-01-01", end=None, force_refresh=False):
    if tickers is None:
        tickers = list(UNIVERSE.keys())
    if end is None:
        end = datetime.today().strftime("%Y-%m-%d")

    result = {}
    tickers_to_fetch = []
    
    for ticker in tickers:
        safe_name = ticker.replace("/", "_")
        out_path = RAW_DIR / f"{safe_name}_prices.parquet"

        cache_fresh = False
        if out_path.exists():
            age_days = (time.time() - out_path.stat().st_mtime) / 86400
            cache_fresh = age_days < PRICE_CACHE_TTL_DAYS

        if cache_fresh and not force_refresh:
            result[ticker] = pd.read_parquet(out_path)
        else:
            tickers_to_fetch.append(ticker)

    if tickers_to_fetch:
        async def fetch_missing():
            exchange = ccxt.binance({'enableRateLimit': True})
            try:
                for t in tickers_to_fetch:
                    log.info(f"[{t}] Fetching {start} → {end} from Binance")
                    df = await _fetch_ccxt_single(exchange, t, start, end)
                    if not df.empty:
                        safe_name = t.replace("/", "_")
                        out_path = RAW_DIR / f"{safe_name}_prices.parquet"
                        df.to_parquet(out_path)
                        result[t] = df
                        log.info(f"[{t}] {len(df)} rows saved")
                    else:
                        log.warning(f"[{t}] No data returned — skipped")
            finally:
                await exchange.close()

        asyncio.run(fetch_missing())

    log.info(f"fetch_price_data complete: {len(result)}/{len(tickers)} tickers loaded")
    return result


def fetch_macro_data(start="2014-01-01", end=None, force_refresh=False):
    import pandas_datareader.data as web
    import numpy as np

    if end is None:
        end = datetime.today().strftime("%Y-%m-%d")

    out_path = RAW_DIR / "macro.parquet"
    if out_path.exists() and not force_refresh:
        return pd.read_parquet(out_path)

    frames = {}
    for name, sid in MACRO_SERIES.items():
        try:
            s = web.DataReader(sid, "fred", start, end)
            frames[name] = s[sid]
        except Exception as e:
            log.warning(f"FRED {sid}: {e}")

    macro = pd.DataFrame(frames)
    macro.index.name = "Date"
    macro = macro.resample("D").last().ffill()

    if "yield_10y" in macro and "yield_2y" in macro:
        macro["yield_curve"] = macro["yield_10y"] - macro["yield_2y"]
    if "vix" in macro:
        macro["vix_change_5d"] = macro["vix"].pct_change(5)

    macro.to_parquet(out_path)
    return macro


def get_data_summary(tickers=None):
    if tickers is None:
        tickers = list(UNIVERSE.keys())
    rows = []
    for ticker in tickers:
        safe_name = ticker.replace("/", "_")
        pp = RAW_DIR / f"{safe_name}_prices.parquet"
        row = {"ticker": ticker, "sector": UNIVERSE.get(ticker, "?")}
        if pp.exists():
            df = pd.read_parquet(pp)
            row.update({
                "price_rows":  len(df),
                "price_start": str(df.index[0]),
                "price_end":   str(df.index[-1]),
            })
        else:
            row.update({"price_rows": 0, "price_start": "---", "price_end": "---"})
        rows.append(row)
    return pd.DataFrame(rows)
