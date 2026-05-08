# quant-research/pead_engine/data_fetcher.py
"""
PEAD Engine — Data Fetcher

Handles:
  1. Earnings calendar + EPS/revenue actuals vs consensus (yfinance)
  2. Historical price data for PEAD universe (yfinance, with cache)
  3. Volume data for confirmation filter
  4. Xetra → NASDAQ ticker mapping for earnings lookup
"""

import os
import json
import logging
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

log = logging.getLogger(__name__)

try:
    import yfinance as yf
    _YF_AVAILABLE = True
except ImportError:
    _YF_AVAILABLE = False
    log.error("yfinance not installed. Run: pip install yfinance")

from config import (
    PEAD_UNIVERSE, EARNINGS_CACHE_PATH, EARNINGS_CACHE_TTL_HRS,
    PRICE_CACHE_PATH, PRICE_CACHE_TTL_HRS, PRICE_LOOKBACK_DAYS,
)

# ── Xetra → NASDAQ mapping ────────────────────────────────────────────────────
# yfinance earnings data for Xetra tickers is unreliable.
# Map to the underlying US ticker for earnings, but keep Xetra for price.
XETRA_TO_NASDAQ = {
    "APC.DE": "AAPL",
    "MSF.DE": "MSFT",
    "SAP.DE": "SAP",
    "ALV.DE": None,   # German-only, earnings in EUR — skip for now
    "SIE.DE": None,
    "BAYN.DE": None,
    "BMW.DE": None,
}

# GICS Sector mapping (static, good enough for drift window calibration)
TICKER_SECTOR = {
    "AAPL": "Technology",  "MSFT": "Technology",  "APC.DE": "Technology",
    "MSF.DE": "Technology","AMZN": "Technology",  "NVDA": "Technology",
    "GOOGL": "Communication","META": "Communication","TSLA": "Technology",
    "CRM": "Technology",   "ADBE": "Technology",  "NFLX": "Communication",
    "ATAI": "Healthcare",
    "AMD": "Technology",   "INTC": "Technology",  "QCOM": "Technology",
    "AMAT": "Technology",  "MU": "Technology",    "TXN": "Technology",
    "ORCL": "Technology",  "NOW": "Technology",   "SNOW": "Technology",
    "UBER": "Technology",  "PYPL": "Financials",  "SPOT": "Communication",
    "SHOP": "Technology",
    "V": "Financials",     "MA": "Financials",    "JPM": "Financials",
    "BAC": "Financials",   "GS": "Financials",    "MS": "Financials",
    "BRK-B": "Financials", "AXP": "Financials",
    "UNH": "Healthcare",   "JNJ": "Healthcare",   "PFE": "Healthcare",
    "LLY": "Healthcare",   "ABBV": "Healthcare",  "MRK": "Healthcare",
    "AMGN": "Healthcare",  "GILD": "Healthcare",
    "KO": "Consumer Staples","MCD": "Consumer Staples","WMT": "Consumer Staples",
    "HD": "Consumer Staples","COST": "Consumer Staples","NKE": "Consumer Staples",
    "SBUX": "Consumer Staples",
    "BA": "Industrials",   "CAT": "Industrials",  "LMT": "Industrials",
    "RTX": "Industrials",  "GE": "Industrials",   "HON": "Industrials",
    "SAP.DE": "Technology",
}


def _cache_is_fresh(path: str, ttl_hours: int) -> bool:
    if not os.path.exists(path):
        return False
    age = (datetime.now() - datetime.fromtimestamp(os.path.getmtime(path))).total_seconds()
    return age < ttl_hours * 3600


def _earnings_ticker(ticker: str):
    """Returns the ticker to use for earnings lookup (handles Xetra remapping)."""
    if ticker in XETRA_TO_NASDAQ:
        return XETRA_TO_NASDAQ[ticker]  # None means skip
    return ticker


# ── Earnings Data ─────────────────────────────────────────────────────────────

def fetch_earnings_history(ticker: str) -> pd.DataFrame:
    """
    Fetches quarterly earnings history for a single ticker via yfinance.
    Returns DataFrame with columns:
      earnings_date, reported_eps, consensus_eps, surprise_pct,
      reported_revenue, consensus_revenue, revenue_surprise_pct
    """
    earn_ticker = _earnings_ticker(ticker)
    if earn_ticker is None:
        return pd.DataFrame()

    if not _YF_AVAILABLE:
        return pd.DataFrame()

    try:
        t = yf.Ticker(earn_ticker)

        # Earnings history (EPS)
        earnings = t.earnings_history
        if earnings is None or earnings.empty:
            log.warning(f"  No earnings history for {earn_ticker}")
            return pd.DataFrame()

        df = earnings.copy()
        df = df.reset_index()

        # Normalise column names (yfinance returns vary by version)
        col_map = {}
        for c in df.columns:
            cl = c.lower()
            if "date" in cl or "quarter" in cl:              col_map[c] = "earnings_date"
            elif "eps actual" in cl or "epsactual" in cl:    col_map[c] = "reported_eps"
            elif "eps estimate" in cl or "epsestimate" in cl: col_map[c] = "consensus_eps"
            elif "surprise" in cl and "%" in cl:             col_map[c] = "surprise_pct"
        df = df.rename(columns=col_map)

        # Compute surprise if not present
        if "surprise_pct" not in df.columns:
            if "reported_eps" in df.columns and "consensus_eps" in df.columns:
                eps_r = pd.to_numeric(df["reported_eps"], errors="coerce")
                eps_c = pd.to_numeric(df["consensus_eps"], errors="coerce")
                df["surprise_pct"] = ((eps_r - eps_c) / eps_c.abs() * 100).round(2)

        # Ensure date column is datetime
        if "earnings_date" in df.columns:
            df["earnings_date"] = pd.to_datetime(df["earnings_date"], errors="coerce", utc=True)
            df["earnings_date"] = df["earnings_date"].dt.tz_localize(None)

        # Add ticker reference
        df["ticker_original"] = ticker
        df["ticker_earnings"] = earn_ticker

        # Try to get revenue estimates (not always available in yfinance)
        df["reported_revenue"]    = np.nan
        df["consensus_revenue"]   = np.nan
        df["revenue_surprise_pct"] = np.nan

        try:
            fin = t.quarterly_financials
            if fin is not None and not fin.empty:
                rev_row = [r for r in fin.index if "Total Revenue" in str(r) or "Revenue" in str(r)]
                if rev_row:
                    rev = fin.loc[rev_row[0]]
                    # Match by quarter — approximate by sorting dates
                    pass  # Revenue matching is best-effort; EPS is primary signal
        except Exception:
            pass

        keep_cols = ["earnings_date", "reported_eps", "consensus_eps", "surprise_pct",
                     "ticker_original", "ticker_earnings",
                     "reported_revenue", "consensus_revenue", "revenue_surprise_pct"]
        df = df[[c for c in keep_cols if c in df.columns]]

        df = df.dropna(subset=["earnings_date"])
        df = df.sort_values("earnings_date").reset_index(drop=True)

        log.info(f"  {earn_ticker}: {len(df)} earnings quarters fetched")
        return df

    except Exception as e:
        log.warning(f"  Earnings fetch failed for {earn_ticker}: {e}")
        return pd.DataFrame()


def fetch_all_earnings(tickers: list, force_refresh: bool = False) -> pd.DataFrame:
    """
    Fetches earnings history for all tickers and returns a combined DataFrame.
    Cached to EARNINGS_CACHE_PATH with TTL.
    """
    os.makedirs(os.path.dirname(EARNINGS_CACHE_PATH) if os.path.dirname(EARNINGS_CACHE_PATH) else ".", exist_ok=True)

    if not force_refresh and _cache_is_fresh(EARNINGS_CACHE_PATH, EARNINGS_CACHE_TTL_HRS):
        log.info(f"Loading earnings from cache: {EARNINGS_CACHE_PATH}")
        return pd.read_csv(EARNINGS_CACHE_PATH, parse_dates=["earnings_date"])

    frames = []
    for ticker in tickers:
        df = fetch_earnings_history(ticker)
        if not df.empty:
            df["ticker"] = ticker
            frames.append(df)

    if not frames:
        log.warning("No earnings data fetched for any ticker.")
        return pd.DataFrame()

    combined = pd.concat(frames, ignore_index=True)
    combined.to_csv(EARNINGS_CACHE_PATH, index=False)
    log.info(f"Earnings cache saved: {EARNINGS_CACHE_PATH} ({len(combined)} rows, {combined['ticker'].nunique()} tickers)")
    return combined


# ── Price Data ────────────────────────────────────────────────────────────────

def fetch_prices(tickers: list, force_refresh: bool = False) -> pd.DataFrame:
    """
    Fetches daily close prices for PEAD universe.
    Handles Xetra tickers by fetching both Xetra (for price) and NASDAQ equivalent.
    """
    os.makedirs(os.path.dirname(PRICE_CACHE_PATH) if os.path.dirname(PRICE_CACHE_PATH) else ".", exist_ok=True)

    if not force_refresh and _cache_is_fresh(PRICE_CACHE_PATH, PRICE_CACHE_TTL_HRS):
        log.info(f"Loading prices from cache: {PRICE_CACHE_PATH}")
        return pd.read_csv(PRICE_CACHE_PATH, index_col=0, parse_dates=True)

    if not _YF_AVAILABLE:
        raise ImportError("yfinance required for price fetching.")

    # Build full fetch list: include both Xetra and NASDAQ equivalents
    fetch_list = list(set(tickers + [v for v in XETRA_TO_NASDAQ.values() if v]))

    end   = datetime.today()
    start = end - timedelta(days=PRICE_LOOKBACK_DAYS + 60)

    log.info(f"Fetching prices for {len(fetch_list)} tickers ({PRICE_LOOKBACK_DAYS}d history)...")

    try:
        data = yf.download(
            fetch_list, start=start.strftime("%Y-%m-%d"),
            end=end.strftime("%Y-%m-%d"),
            auto_adjust=True, progress=False
        )
        prices = data["Close"] if len(fetch_list) > 1 else pd.DataFrame({fetch_list[0]: data["Close"]})
        prices = prices.tail(PRICE_LOOKBACK_DAYS)
        if prices.index.tz is not None:
            prices.index = prices.index.tz_localize(None)
        prices.to_csv(PRICE_CACHE_PATH)
        log.info(f"Prices cached: {PRICE_CACHE_PATH} ({len(prices)} rows, {len(prices.columns)} tickers)")
        return prices
    except Exception as e:
        log.error(f"Price fetch failed: {e}")
        if os.path.exists(PRICE_CACHE_PATH):
            log.info("Falling back to price cache.")
            return pd.read_csv(PRICE_CACHE_PATH, index_col=0, parse_dates=True)
        raise


def get_volume_data(ticker: str, lookback_days: int = 30) -> pd.Series:
    """
    Fetches daily volume for a ticker. Returns Series with date index.
    Used for the volume confirmation filter.
    """
    earn_ticker = _earnings_ticker(ticker) or ticker
    try:
        t = yf.Ticker(earn_ticker)
        hist = t.history(period=f"{lookback_days + 10}d")
        if hist.empty:
            return pd.Series(dtype=float)
        if hist.index.tz is not None:
            hist.index = hist.index.tz_localize(None)
        return hist["Volume"].tail(lookback_days)
    except Exception as e:
        log.warning(f"Volume fetch failed for {earn_ticker}: {e}")
        return pd.Series(dtype=float)


def get_sector(ticker: str) -> str:
    """Returns GICS sector for a ticker, or 'Default' if unknown."""
    return TICKER_SECTOR.get(ticker, TICKER_SECTOR.get(_earnings_ticker(ticker), "Default"))
