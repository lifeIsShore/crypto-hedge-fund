"""data_loader.py — Fetch price/macro/fundamental data.
Raw data never modified after download.

Stream 2 / Stream 7: Universe expanded to ~90 tickers matching
portfolio/src/config.py ASSET_UNIVERSE. European tickers (.DE/.AS/.PA/.L)
are fetched via yfinance; missing Adj Close falls back to Close silently.
"""
import os, json, logging, time
from pathlib import Path
from datetime import datetime
import pandas as pd

# Bug fix (2026-08-20): price-cache parquet files used to be cached forever
# once written (even a bad/short initial fetch, e.g. a delisted-ticker
# fallback that only returned 21 rows). Since force_refresh defaulted to
# False everywhere and was never flipped, ~43% of tickers were permanently
# stuck skipping ML training run after run. A TTL forces periodic refetches
# without requiring callers to remember force_refresh=True.
PRICE_CACHE_TTL_DAYS = 7

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# UNIVERSE  (Single Source of Truth: syncs with portfolio/src/config.py)
# ─────────────────────────────────────────────────────────────────────────────
import sys
from pathlib import Path

# Resolve repo root and add to sys.path to import central config
_HERE = Path(__file__).resolve()
_ROOT = _HERE.parents[4]  # ml_research/stock_ml_lab/utils/data_loader.py -> root
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

try:
    from portfolio.src.config import ASSET_UNIVERSE, TICKER_SECTORS, TICKER_MAPPING
    # Create the UNIVERSE dict expected by the ML pipeline (ticker -> sector)
    UNIVERSE = {t: TICKER_SECTORS.get(t, "Unknown") for t in ASSET_UNIVERSE}
except ImportError:
    log.error("Could not import central config from portfolio.src.config. Check PYTHONPATH.")
    # Fallback to empty if absolutely necessary, but this should error in production
    UNIVERSE = {}
    TICKER_MAPPING = {}

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


# ─────────────────────────────────────────────────────────────────────────────
# PRICE DATA
# ─────────────────────────────────────────────────────────────────────────────

def fetch_price_data(tickers=None, start="2014-01-01", end=None, force_refresh=False):
    """
    Fetches adjusted closing prices from yfinance for each ticker.

    European tickers (.DE, .AS, .PA, .L) are fetched natively.
    If 'Adj Close' is missing (some European feeds), falls back to 'Close' silently.
    Dead tickers (no data) are skipped with a warning.

    Returns: dict {ticker: DataFrame(OHLCV + Adj Close)}
    """
    import yfinance as yf
    if tickers is None:
        tickers = list(UNIVERSE.keys())
    if end is None:
        end = datetime.today().strftime("%Y-%m-%d")

    result = {}
    for ticker in tickers:
        safe_name = ticker.replace("/", "_").replace("CON.DE", "CONT.DE")
        out_path = RAW_DIR / f"{safe_name}_prices.parquet"

        cache_fresh = False
        if out_path.exists():
            age_days = (time.time() - out_path.stat().st_mtime) / 86400
            cache_fresh = age_days < PRICE_CACHE_TTL_DAYS

        if cache_fresh and not force_refresh:
            result[ticker] = pd.read_parquet(out_path)
            continue
        elif out_path.exists() and not force_refresh:
            log.info(f"[{ticker}] Cache stale (>{PRICE_CACHE_TTL_DAYS}d old) — refetching")

        log.info(f"[{ticker}] Fetching {start} → {end}")
        try:
            raw = yf.download(ticker, start=start, end=end,
                              auto_adjust=False, progress=False)
        except Exception as e:
            log.warning(f"[{ticker}] Download error: {e} — skipped")
            continue

        if raw.empty:
            # Fallback logic
            fallback = TICKER_MAPPING.get(ticker)
            if fallback and fallback != ticker:
                log.info(f"[{ticker}] Primary failed — trying fallback: {fallback}")
                try:
                    raw = yf.download(fallback, start=start, end=end,
                                      auto_adjust=False, progress=False)
                except Exception as e:
                    log.warning(f"[{ticker}] Fallback {fallback} also failed: {e}")
            
            if raw.empty:
                log.warning(f"[{ticker}] No data returned (even after fallback) — skipped")
                continue

        # Handle yfinance multi-level column output
        if isinstance(raw.columns, pd.MultiIndex):
            raw.columns = raw.columns.get_level_values(0)

        # Ensure Adj Close exists — fall back to Close for European tickers
        if "Adj Close" not in raw.columns:
            if "Close" in raw.columns:
                raw["Adj Close"] = raw["Close"]
                log.debug(f"[{ticker}] No Adj Close — using Close as fallback")
            else:
                log.warning(f"[{ticker}] Missing both Close and Adj Close — skipped")
                continue

        cols_available = [c for c in ["Open", "High", "Low", "Close", "Adj Close", "Volume"]
                          if c in raw.columns]
        df = raw[cols_available].copy()
        df.index.name = "Date"
        df.to_parquet(out_path)
        result[ticker] = df
        log.info(f"[{ticker}] {len(df)} rows saved")

    log.info(f"fetch_price_data complete: {len(result)}/{len(tickers)} tickers loaded")
    return result


# ─────────────────────────────────────────────────────────────────────────────
# MACRO DATA
# ─────────────────────────────────────────────────────────────────────────────

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


# ─────────────────────────────────────────────────────────────────────────────
# FUNDAMENTALS
# ─────────────────────────────────────────────────────────────────────────────

def fetch_fundamentals(tickers=None, force_refresh=False):
    import yfinance as yf

    if tickers is None:
        tickers = list(UNIVERSE.keys())

    FIELDS = [
        "trailingPE", "priceToBook", "enterpriseToEbitda", "revenueGrowth",
        "grossMargins", "operatingMargins", "debtToEquity", "freeCashflow", "marketCap",
    ]

    result = {}
    for ticker in tickers:
        safe_name = ticker.replace("/", "_").replace("CON.DE", "CONT.DE")
        out_path = RAW_DIR / f"{safe_name}_fundamentals.json"

        if out_path.exists() and not force_refresh:
            with open(out_path) as f:
                result[ticker] = json.load(f)
            continue

        try:
            info = yf.Ticker(ticker).info
            if not info or "symbol" not in info:
                # Try fallback for fundamentals
                fallback = TICKER_MAPPING.get(ticker)
                if fallback and fallback != ticker:
                    log.info(f"[{ticker}] Fundamental primary failed — trying fallback: {fallback}")
                    info = yf.Ticker(fallback).info
            
            data = {k: info.get(k) for k in FIELDS}
            data["fetched_at"] = datetime.today().isoformat()
            with open(out_path, "w") as f:
                json.dump(data, f, indent=2)
            result[ticker] = data
        except Exception as e:
            log.warning(f"[{ticker}] fundamentals: {e}")
            result[ticker] = {}

    return result


# ─────────────────────────────────────────────────────────────────────────────
# DATA SUMMARY
# ─────────────────────────────────────────────────────────────────────────────

def get_data_summary(tickers=None):
    if tickers is None:
        tickers = list(UNIVERSE.keys())
    rows = []
    for ticker in tickers:
        safe_name = ticker.replace("/", "_").replace("CON.DE", "CONT.DE")
        pp = RAW_DIR / f"{safe_name}_prices.parquet"
        fp = RAW_DIR / f"{safe_name}_fundamentals.json"
        row = {"ticker": ticker, "sector": UNIVERSE.get(ticker, "?")}
        if pp.exists():
            df = pd.read_parquet(pp)
            row.update({
                "price_rows":  len(df),
                "price_start": str(df.index[0].date()),
                "price_end":   str(df.index[-1].date()),
            })
        else:
            row.update({"price_rows": 0, "price_start": "---", "price_end": "---"})
        row["has_fundamentals"] = fp.exists()
        rows.append(row)
    return pd.DataFrame(rows)
