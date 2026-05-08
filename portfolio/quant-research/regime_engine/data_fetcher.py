# quant-research/regime_engine/data_fetcher.py
"""
Fetches and caches macro data from FRED (via pandas_datareader).
Falls back to cached CSV if network is unavailable.
All series are aligned to a common daily date index (forward-filled for
monthly/weekly series like ISM).
"""

import os
import json
import logging
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

log = logging.getLogger(__name__)

# Try pandas_datareader; if missing, guide user
try:
    import pandas_datareader.data as web
    _PDR_AVAILABLE = True
except ImportError:
    _PDR_AVAILABLE = False
    log.warning("pandas_datareader not installed. Run: pip install pandas-datareader")

from config import FRED_SERIES, FRED_CACHE_PATH, FRED_CACHE_TTL_HRS, LOOKBACK_DAYS


def _cache_is_fresh(cache_path: str, ttl_hours: int) -> bool:
    """Returns True if the cache file exists and is newer than ttl_hours."""
    if not os.path.exists(cache_path):
        return False
    mtime = datetime.fromtimestamp(os.path.getmtime(cache_path))
    return (datetime.now() - mtime).total_seconds() < ttl_hours * 3600


def fetch_fred_series(force_refresh: bool = False) -> pd.DataFrame:
    """
    Downloads all FRED series defined in config.FRED_SERIES.
    Returns a daily-indexed DataFrame, forward-filled.
    Falls back to local CSV cache on failure.
    """
    os.makedirs(os.path.dirname(FRED_CACHE_PATH) if os.path.dirname(FRED_CACHE_PATH) else ".", exist_ok=True)

    if not force_refresh and _cache_is_fresh(FRED_CACHE_PATH, FRED_CACHE_TTL_HRS):
        log.info(f"Loading FRED data from cache: {FRED_CACHE_PATH}")
        df = pd.read_csv(FRED_CACHE_PATH, index_col=0, parse_dates=True)
        return df

    if not _PDR_AVAILABLE:
        log.error("pandas_datareader unavailable. Cannot fetch live FRED data.")
        return _load_cache_or_raise()

    end   = datetime.today()
    start = end - timedelta(days=LOOKBACK_DAYS + 120)  # extra buffer for monthly series

    frames = {}
    for name, series_id in FRED_SERIES.items():
        try:
            s = web.DataReader(series_id, "fred", start, end)[series_id]
            frames[name] = s
            log.info(f"  Fetched FRED: {series_id} ({name}) — {len(s)} obs")
        except Exception as e:
            log.warning(f"  Failed to fetch {series_id}: {e}")

    if not frames:
        log.error("All FRED fetches failed. Falling back to cache.")
        return _load_cache_or_raise()

    # Combine into a single DataFrame, align to business-day calendar
    df = pd.DataFrame(frames)
    bday_index = pd.bdate_range(start=start, end=end)
    df = df.reindex(bday_index)
    df = df.ffill()   # forward-fill monthly/weekly series to daily
    df = df.tail(LOOKBACK_DAYS)
    df = df.dropna(how="all")

    df.to_csv(FRED_CACHE_PATH)
    log.info(f"FRED data saved to cache: {FRED_CACHE_PATH} ({len(df)} rows, {len(df.columns)} series)")
    return df


def _load_cache_or_raise() -> pd.DataFrame:
    if os.path.exists(FRED_CACHE_PATH):
        log.info(f"Loading stale cache: {FRED_CACHE_PATH}")
        return pd.read_csv(FRED_CACHE_PATH, index_col=0, parse_dates=True)
    raise FileNotFoundError(
        f"No FRED cache at {FRED_CACHE_PATH} and live fetch failed. "
        "Run with internet access first to populate the cache."
    )


def fetch_vix_from_yfinance(lookback_days: int = LOOKBACK_DAYS) -> pd.Series:
    """
    Supplement: fetch VIX directly from yfinance (^VIX) as a fallback
    or cross-check. Returns a daily Series named 'vix'.
    """
    try:
        import yfinance as yf
        end   = datetime.today()
        start = end - timedelta(days=lookback_days + 30)
        data  = yf.download("^VIX", start=start.strftime("%Y-%m-%d"),
                             end=end.strftime("%Y-%m-%d"),
                             auto_adjust=True, progress=False)
        if data.empty:
            raise ValueError("Empty VIX data from yfinance")
        s = data["Close"].squeeze()
        s.name = "vix"
        log.info(f"VIX fetched from yfinance: {len(s)} obs, latest={float(s.iloc[-1]):.2f}")
        return s
    except Exception as e:
        log.warning(f"yfinance VIX fetch failed: {e}")
        return pd.Series(dtype=float, name="vix")


def get_macro_data(force_refresh: bool = False) -> pd.DataFrame:
    """
    Main entry point. Returns a clean, daily-indexed macro DataFrame.
    Merges FRED data with yfinance VIX (yfinance is more current than FRED for VIX).
    """
    fred_df = fetch_fred_series(force_refresh=force_refresh)

    # Prefer yfinance VIX (updated same day) over FRED VIX (1-day lag)
    yf_vix = fetch_vix_from_yfinance()
    if not yf_vix.empty:
        fred_df = fred_df.copy()
        fred_df["vix"] = yf_vix.reindex(fred_df.index).ffill()

    return fred_df
