"""data_loader.py — Fetch price/macro/fundamental data. Raw data never modified after download."""
import os, json, logging
from pathlib import Path
from datetime import datetime
import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

UNIVERSE = {
    "META":"Communication Services","JPM":"Financials","XOM":"Energy",
    "UNH":"Healthcare","TSLA":"Consumer Discretionary","MSFT":"Technology",
    "CAT":"Industrials","AMZN":"Consumer Discretionary","GLD":"Commodities","BRK-B":"Diversified",
}
MACRO_SERIES = {
    "fed_funds":"FEDFUNDS","yield_10y":"DGS10","yield_2y":"DGS2",
    "vix":"VIXCLS","cpi_yoy":"CPIAUCSL","dxy":"DTWEXBGS",
}
RAW_DIR = Path(__file__).parent.parent / "data" / "raw"
RAW_DIR.mkdir(parents=True, exist_ok=True)

def fetch_price_data(tickers=None, start="2014-01-01", end=None, force_refresh=False):
    import yfinance as yf
    if tickers is None: tickers = list(UNIVERSE.keys())
    if end is None: end = datetime.today().strftime("%Y-%m-%d")
    result = {}
    for ticker in tickers:
        out_path = RAW_DIR / f"{ticker}_prices.parquet"
        if out_path.exists() and not force_refresh:
            result[ticker] = pd.read_parquet(out_path)
        else:
            log.info(f"[{ticker}] Fetching {start} to {end}")
            raw = yf.download(ticker, start=start, end=end, auto_adjust=False, progress=False)
            if raw.empty: log.warning(f"[{ticker}] No data"); continue
            if isinstance(raw.columns, pd.MultiIndex): raw.columns = raw.columns.get_level_values(0)
            df = raw[["Open","High","Low","Close","Adj Close","Volume"]].copy()
            df.index.name = "Date"
            df.to_parquet(out_path)
            result[ticker] = df
            log.info(f"[{ticker}] {len(df)} rows saved")
    return result

def fetch_macro_data(start="2014-01-01", end=None, force_refresh=False):
    import pandas_datareader.data as web
    import numpy as np
    if end is None: end = datetime.today().strftime("%Y-%m-%d")
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

def fetch_fundamentals(tickers=None, force_refresh=False):
    import yfinance as yf
    if tickers is None: tickers = list(UNIVERSE.keys())
    FIELDS = ["trailingPE","priceToBook","enterpriseToEbitda","revenueGrowth",
              "grossMargins","operatingMargins","debtToEquity","freeCashflow","marketCap"]
    result = {}
    for ticker in tickers:
        out_path = RAW_DIR / f"{ticker}_fundamentals.json"
        if out_path.exists() and not force_refresh:
            with open(out_path) as f: result[ticker] = json.load(f)
        else:
            try:
                info = yf.Ticker(ticker).info
                data = {k: info.get(k) for k in FIELDS}
                data["fetched_at"] = datetime.today().isoformat()
                with open(out_path, "w") as f: json.dump(data, f, indent=2)
                result[ticker] = data
            except Exception as e:
                log.warning(f"[{ticker}] fundamentals: {e}")
    return result

def get_data_summary(tickers=None):
    if tickers is None: tickers = list(UNIVERSE.keys())
    rows = []
    for ticker in tickers:
        pp = RAW_DIR / f"{ticker}_prices.parquet"
        fp = RAW_DIR / f"{ticker}_fundamentals.json"
        row = {"ticker": ticker, "sector": UNIVERSE.get(ticker,"?")}
        if pp.exists():
            df = pd.read_parquet(pp)
            row.update({"price_rows":len(df),"price_start":str(df.index[0].date()),"price_end":str(df.index[-1].date())})
        else:
            row.update({"price_rows":0,"price_start":"---","price_end":"---"})
        row["has_fundamentals"] = fp.exists()
        rows.append(row)
    return pd.DataFrame(rows)
