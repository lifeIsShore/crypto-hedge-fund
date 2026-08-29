"""
finra_short_volume.py
=====================
Phase 4 Alternative Data: Daily Short Volume from FINRA RegSHO API.

Uses the official FINRA Open Data API (POST):
  https://api.finra.org/data/group/otcMarket/name/regShoDaily

Signals produced (all stationary — ratios/changes):
  sv_short_ratio       — short volume / total volume (0–1). High = strong bearish activity.
  sv_short_ratio_5d    — 5-day rolling mean of short_ratio (smoothed signal)
  sv_short_ratio_z21   — 21-day z-score of short_ratio (unusual vs. recent history)
  sv_short_ratio_chg5  — 5-day change in short_ratio (momentum of bearish sentiment)
  sv_rel_short_vol     — short volume / 21-day avg short volume (relative spike detector)

Coverage: US equities only (tickers without '.DE', '.PA', etc. suffixes).
           European .DE tickers are mapped to their US equivalents via TICKER_MAPPING.

Caching: Per-ticker parquet files in data/raw/ with a 7-day TTL (avoids repeated API calls).

No third-party dependencies beyond pandas and numpy — fetches via urllib.
"""

import io
import json
import logging
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

log = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Paths
# ─────────────────────────────────────────────────────────────────────────────
_HERE     = Path(__file__).resolve()
_RAW_DIR  = _HERE.parent.parent / "data" / "raw"
_RAW_DIR.mkdir(parents=True, exist_ok=True)

# ─────────────────────────────────────────────────────────────────────────────
# FINRA Open Data API
# ─────────────────────────────────────────────────────────────────────────────
FINRA_API_URL     = "https://api.finra.org/data/group/otcMarket/name/regShoDaily"
LOOKBACK_TRADING_DAYS = 63    # how many recent trading days of history to fetch
CACHE_TTL_DAYS        = 7     # per-ticker feature cache TTL
FINRA_PAGE_SIZE       = 500   # records per API call (API max is 5000)
FINRA_REQUEST_DELAY   = 1.0   # seconds between API requests


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _date_range(n_days: int) -> tuple[str, str]:
    """Return (start_date, end_date) strings for the last n_days trading days."""
    end   = datetime.today()
    # Rough: look back ~1.5x calendar days to cover weekends/holidays
    start = end - timedelta(days=int(n_days * 1.5))
    return start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")


def _post_finra(body: dict, timeout: int = 30) -> list[dict]:
    """
    POST to FINRA API with the given body, returns parsed JSON list.
    Raises on HTTP errors.
    """
    payload = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        FINRA_API_URL,
        data=payload,
        headers={
            "User-Agent":   "research-bot/1.0",
            "Accept":       "application/json",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


# ─────────────────────────────────────────────────────────────────────────────
# Fetch short volume time series for a single US ticker
# ─────────────────────────────────────────────────────────────────────────────

def fetch_short_volume_series(us_ticker: str, n_days: int = LOOKBACK_TRADING_DAYS,
                               force_refresh: bool = False) -> pd.DataFrame:
    """
    Returns a daily DataFrame with short volume ratio history for one US ticker.

    Columns: [Date (index), short_ratio, short_volume, total_volume]

    Multiple reporting facilities (NQTRF, NYTRF, NCTRF) are aggregated by summing
    shortParQuantity and totalParQuantity per date.

    Caches the per-ticker result as a parquet file. If the cache is fresh
    (< CACHE_TTL_DAYS), it's returned immediately without hitting FINRA again.
    """
    safe_name  = us_ticker.replace("/", "_")
    cache_path = _RAW_DIR / f"{safe_name}_finra_sv.parquet"

    if not force_refresh and cache_path.exists():
        age_days = (time.time() - cache_path.stat().st_mtime) / 86400
        if age_days < CACHE_TTL_DAYS:
            try:
                return pd.read_parquet(cache_path)
            except Exception:
                pass

    start_date, end_date = _date_range(n_days)

    try:
        body = {
            "compareFilters": [
                {
                    "fieldName":   "securitiesInformationProcessorSymbolIdentifier",
                    "compareType": "EQUAL",
                    "fieldValue":  us_ticker,
                }
            ],
            "dateRangeFilters": [
                {
                    "fieldName": "tradeReportDate",
                    "startDate": start_date,
                    "endDate":   end_date,
                }
            ],
            "limit": FINRA_PAGE_SIZE,
        }
        records = _post_finra(body)
        time.sleep(FINRA_REQUEST_DELAY)

    except Exception as e:
        log.debug(f"[FINRA] {us_ticker}: API error: {e}")
        return pd.DataFrame(columns=["short_ratio", "short_volume", "total_volume"])

    if not records:
        log.debug(f"[FINRA] {us_ticker}: no records returned")
        return pd.DataFrame(columns=["short_ratio", "short_volume", "total_volume"])

    df = pd.DataFrame(records)
    df = df.rename(columns={
        "tradeReportDate":                              "Date",
        "securitiesInformationProcessorSymbolIdentifier": "Symbol",
        "shortParQuantity":                             "short_volume",
        "totalParQuantity":                             "total_volume",
    })
    df["Date"] = pd.to_datetime(df["Date"])

    # Aggregate across reporting facilities (NASDAQ, NYSE, BX) by summing volumes
    agg = df.groupby("Date").agg(
        short_volume=("short_volume", "sum"),
        total_volume=("total_volume", "sum"),
    ).reset_index()
    agg = agg[agg["total_volume"] > 0].copy()
    agg["short_ratio"] = agg["short_volume"] / agg["total_volume"]
    agg = agg.set_index("Date").sort_index()

    try:
        agg.to_parquet(cache_path)
    except Exception:
        pass

    log.debug(f"[FINRA] {us_ticker}: {len(agg)} trading days fetched ({start_date} → {end_date})")
    return agg


# ─────────────────────────────────────────────────────────────────────────────
# Compute ML-ready features from the time series
# ─────────────────────────────────────────────────────────────────────────────

def compute_short_volume_features(sv_df: pd.DataFrame, price_index: pd.DatetimeIndex,
                                   ticker: str = "") -> pd.DataFrame:
    """
    Aligns the FINRA short volume time series to the ML feature DataFrame index
    and computes all derived signals.

    Args:
        sv_df:        Output of fetch_short_volume_series()
        price_index:  The DatetimeIndex of the ML feature DataFrame
        ticker:       For logging only

    Returns:
        DataFrame indexed by price_index with columns:
          sv_short_ratio, sv_short_ratio_5d, sv_short_ratio_z21,
          sv_short_ratio_chg5, sv_rel_short_vol
        All NaN for dates before FINRA coverage or missing data.
    """
    out_cols = [
        "sv_short_ratio",
        "sv_short_ratio_5d",
        "sv_short_ratio_z21",
        "sv_short_ratio_chg5",
        "sv_rel_short_vol",
    ]
    empty = pd.DataFrame(np.nan, index=price_index, columns=out_cols)

    if sv_df.empty or "short_ratio" not in sv_df.columns:
        log.debug(f"[FINRA] No short volume data for {ticker} — returning NaN block")
        return empty

    # Align to full price index (forward-fill up to 5 days for weekends/gaps)
    sr = sv_df["short_ratio"].reindex(price_index, method="ffill", limit=5)

    out = pd.DataFrame(index=price_index)
    out["sv_short_ratio"] = sr

    # 5-day smoothed ratio (reduce noise)
    out["sv_short_ratio_5d"] = sr.rolling(5, min_periods=2).mean()

    # 21-day z-score (stationary: unusual vs recent history)
    roll_mean = sr.rolling(21, min_periods=10).mean()
    roll_std  = sr.rolling(21, min_periods=10).std()
    out["sv_short_ratio_z21"] = (sr - roll_mean) / (roll_std + 1e-9)

    # 5-day change (momentum of bearish sentiment)
    out["sv_short_ratio_chg5"] = sr.diff(5)

    # Relative short volume: vs 21-day avg short vol (spike detector)
    short_vol = sv_df["short_volume"].reindex(price_index, method="ffill", limit=5)
    avg_short_vol = short_vol.rolling(21, min_periods=10).mean()
    out["sv_rel_short_vol"] = short_vol / (avg_short_vol + 1e-9)

    log.debug(f"[FINRA] {ticker}: computed {out.notna().any(axis=1).sum()} rows with short vol features")
    return out


# ─────────────────────────────────────────────────────────────────────────────
# CLI test
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    tickers = sys.argv[1:] if len(sys.argv) > 1 else ["MSFT", "TSLA", "NVDA"]
    print(f"Testing FINRA short volume fetcher for: {tickers}\n")
    for t in tickers:
        sv = fetch_short_volume_series(t, n_days=30, force_refresh=True)
        print(f"=== {t} ({len(sv)} trading days) ===")
        if sv.empty:
            print("  No data returned.\n")
        else:
            print(sv.tail(5).to_string())
            print(f"  short_ratio range: {sv['short_ratio'].min():.3f} – {sv['short_ratio'].max():.3f}")
            print()
