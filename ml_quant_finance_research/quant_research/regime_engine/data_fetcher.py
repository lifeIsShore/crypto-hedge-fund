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

from dotenv import load_dotenv

log = logging.getLogger(__name__)
load_dotenv()
AV_KEY = os.getenv("ALPHAVANTAGE_API_KEY")
TD_KEY = os.getenv("TWELVEDATA_API_KEY")
FRED_KEY = os.getenv("FRED_API_KEY")

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
    import requests
    import io
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/csv,application/csv'
    }
    import time
    fred_down = False
    
    for name, series_id in series_map.items():
        if series_id.startswith("^"): continue
        
        # 1. Try Official FRED API (Best stability)
        success = False
        if FRED_KEY:
            try:
                url = f"https://api.stlouisfed.org/fred/series/observations?series_id={series_id}&api_key={FRED_KEY}&file_type=json"
                res = requests.get(url, timeout=10).json()
                obs = res.get("observations", [])
                if obs:
                    s_df = pd.DataFrame(obs)
                    s_df["date"] = pd.to_datetime(s_df["date"])
                    s_df.set_index("date", inplace=True)
                    s_df["value"] = pd.to_numeric(s_df["value"], errors="coerce")
                    s_df = s_df[s_df.index >= start]
                    if not s_df.empty:
                        frames[name] = s_df["value"]
                        log.info(f"  Fetched Official FRED API: {name}")
                        success = True
            except Exception as e:
                log.warning(f"  Official FRED API failed for {name}: {e}")

        # 2. Try FRED CSV Scraper (Fallback)
        if not success:
            try:
                url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"
                response = requests.get(url, headers=headers, timeout=15)
                if response.status_code == 200:
                    s_df = pd.read_csv(io.StringIO(response.text), index_col=0, parse_dates=True, na_values=".")
                    if series_id in s_df.columns:
                        s_df[series_id] = pd.to_numeric(s_df[series_id], errors="coerce")
                    s_df = s_df[s_df.index >= start]
                    if not s_df.empty:
                        frames[name] = s_df[series_id]
                        log.info(f"  Fetched FRED CSV Scraper: {name}")
                        success = True
            except Exception:
                pass
            
        # Fallback to AlphaVantage / yfinance
        if not success:
            try:
                if name == "vix":
                    ticker = "^VIX" if region == "US" else "^V2TX"
                    yf_df = yf.download(ticker, start=start, end=end, progress=False)
                    if yf_df.empty and region == "EU": yf_df = yf.download("^VIX", start=start, end=end, progress=False)
                    if not yf_df.empty:
                        frames[name] = yf_df["Adj Close"] if "Adj Close" in yf_df.columns else yf_df["Close"]
                        success = True
                elif name == "fed_funds":
                    # Use AV if possible, else yf proxy
                    if AV_KEY:
                        url = f"https://www.alphavantage.co/query?function=FEDERAL_FUNDS_RATE&interval=daily&apikey={AV_KEY}&datatype=csv"
                        av_res = requests.get(url, timeout=10)
                        if av_res.status_code == 200:
                            av_df = pd.read_csv(io.StringIO(av_res.text), index_col=0, parse_dates=True)
                            if "value" in av_df.columns:
                                frames[name] = pd.to_numeric(av_df["value"], errors="coerce")
                                success = True
                    if not success:
                        yf_df = yf.download("^IRX", start=start, end=end, progress=False)
                        if not yf_df.empty:
                            frames[name] = yf_df["Adj Close"] if "Adj Close" in yf_df.columns else yf_df["Close"]
                            success = True
                elif name in ["yield_spread", "yield_10y"]:
                    # Proxy via TNX
                    yf_df = yf.download("^TNX", start=start, end=end, progress=False)
                    if not yf_df.empty:
                        frames[name] = yf_df["Adj Close"] if "Adj Close" in yf_df.columns else yf_df["Close"]
                        if name == "yield_spread": frames[name] = frames[name] - 3.5 # simple proxy
                        success = True
                
                if success: log.info(f"  Fallback success for {name}")
            except Exception:
                pass

    # --- Regional Logic / Calculations ---
    # EU Yield Spread Calculation
    if region == "EU" and "yield_10y" in frames and "yield_3m" in frames:
        frames["yield_spread"] = frames["yield_10y"] - frames["yield_3m"]
        log.info("  Calculated EU yield_spread (10Y - 3M proxy)")

    # EU Fed Funds Fallback
    if region == "EU" and "fed_funds" not in frames and "fed_funds_alt" in frames:
        frames["fed_funds"] = frames["fed_funds_alt"]
        log.info("  Using EU fed_funds_alt fallback")

    # Ensure essential columns exist
    critical_cols = ["vix", "yield_spread", "hy_spread", "fed_funds"]
    missing_count = 0
    for col in critical_cols:
        if col not in frames:
            log.warning(f"  Missing critical column: {col}")
            frames[col] = pd.Series(np.nan, index=[end])
            missing_count += 1

    df = pd.DataFrame(frames)
    bday_index = pd.bdate_range(start=start, end=end)
    df = df.reindex(bday_index).ffill().tail(LOOKBACK_DAYS)
    
    # If all values are NaN, don't drop everything
    if df.dropna(how="all").empty:
        log.error(f"  CRITICAL: No data fetched for {region}!")
    
    # Only save to cache if we actually got some data (don't overwrite good cache with NaNs)
    if not df.empty and missing_count < len(critical_cols):
        df.to_csv(cache_path)
    elif df.empty:
        log.warning(f"  Not saving empty DataFrame to cache for {region}")
    else:
        log.warning(f"  Not overwriting cache for {region} because {missing_count} critical columns are missing.")
    
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
    
    # Final safety check: if 'vix' still missing or all NaN, fill with default
    if "vix" not in df.columns or df["vix"].isna().all():
        df["vix"] = 20.0
    
    # Smarter fill for rates: if ECB rate (fed_funds) is missing in EU, 
    # try to use US fed_funds as proxy rather than 0
    if region == "EU" and (df["fed_funds"].isna().all() or (df["fed_funds"] == 0).all()):
        us_df = fetch_fred_series(region="US")
        if not us_df.empty and "fed_funds" in us_df.columns:
            log.info("  ECB rate missing — using US Fed Funds as proxy")
            df["fed_funds"] = us_df["fed_funds"].reindex(df.index).ffill()

    # Final fill
    return df.ffill().fillna(0)
