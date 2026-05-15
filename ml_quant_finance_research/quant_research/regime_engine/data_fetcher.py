# quant-research/regime_engine/data_fetcher.py
"""
Fetches and caches macro data.
Supports multi-regional data (US, EU).
"""

import os
import logging
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

log = logging.getLogger(__name__)

try:
    import pandas_datareader.data as web
    _PDR_AVAILABLE = True
except ImportError:
    _PDR_AVAILABLE = False

try:
    import yfinance as yf
    _YF_AVAILABLE = True
except ImportError:
    _YF_AVAILABLE = False

from config import REGIONAL_SERIES, LOOKBACK_DAYS, FRED_CACHE_TTL_HRS, get_cache_path


def _cache_is_fresh(cache_path: str, ttl_hours: int) -> bool:
    if not os.path.exists(cache_path):
        return False
    mtime = datetime.fromtimestamp(os.path.getmtime(cache_path))
    return (datetime.now() - mtime).total_seconds() < ttl_hours * 3600


def fetch_fred_series(region: str = "US", force_refresh: bool = False) -> pd.DataFrame:
    cache_path = get_cache_path(region)
    os.makedirs(os.path.dirname(cache_path) if os.path.dirname(cache_path) else ".", exist_ok=True)

    if not force_refresh and _cache_is_fresh(cache_path, FRED_CACHE_TTL_HRS):
        log.info(f"Loading {region} macro data from cache.")
        return pd.read_csv(cache_path, index_col=0, parse_dates=True)

    series_map = REGIONAL_SERIES.get(region, REGIONAL_SERIES["US"])
    end   = datetime.today()
    start = end - timedelta(days=LOOKBACK_DAYS + 120)

    frames = {}
    if _PDR_AVAILABLE:
        for name, series_id in series_map.items():
            if series_id.startswith("^"): continue
            try:
                s = web.DataReader(series_id, "fred", start, end)[series_id]
                frames[name] = s
            except Exception:
                pass

    # Ensure essential columns exist
    for col in ["vix", "yield_spread", "hy_spread", "fed_funds"]:
        if col not in frames:
            frames[col] = pd.Series(np.nan, index=[end])

    df = pd.DataFrame(frames)
    bday_index = pd.bdate_range(start=start, end=end)
    df = df.reindex(bday_index).ffill().tail(LOOKBACK_DAYS).dropna(how="all")
    
    if not df.empty:
        df.to_csv(cache_path)
    return df


def fetch_yf_series(region: str = "US") -> pd.Series:
    ticker = "^VIX" if region == "US" else "^V2TX"
    try:
        if not _YF_AVAILABLE: raise ImportError()
        data = yf.download(ticker, period="2y", progress=False)
        if data.empty and region == "EU":
            # Fallback to VIX if VSTOXX fails
            log.warning("VSTOXX failed, falling back to VIX for EU proxy")
            data = yf.download("^VIX", period="2y", progress=False)
        
        s = data["Close"].squeeze()
        s.name = "vix"
        return s
    except Exception:
        return pd.Series(dtype=float, name="vix")


def get_macro_data(region: str = "US", force_refresh: bool = False) -> pd.DataFrame:
    df = fetch_fred_series(region=region, force_refresh=force_refresh)
    yf_vix = fetch_yf_series(region=region)
    if not yf_vix.empty:
        df["vix"] = yf_vix.reindex(df.index).ffill()
    
    # Final safety check: if 'vix' still missing or all NaN, fill with something
    if "vix" not in df.columns or df["vix"].isna().all():
        df["vix"] = 20.0
    
    return df.ffill().fillna(0)
