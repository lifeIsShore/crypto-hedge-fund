"""
options_scraper.py
==================
Fetches options-derived features (IV, put/call ratio, skew)
and short interest data via yfinance — completely free.

Outputs cached JSON per ticker to data/raw/{TICKER}_options.json.
Integrated into feature_builder.py as a new feature family.

Signals:
  iv_atm            — ATM implied vol (nearest expiry)
  iv_rv_spread      — IV minus 21d realised vol (vol risk premium)
  iv_skew           — OTM put IV minus OTM call IV, normalised (fear gauge)
  pc_ratio          — put / call volume ratio (contrarian)
  iv_change_5d      — 5-day change in ATM IV (momentum of fear)
  short_pct_float   — % of float sold short
  short_ratio       — days to cover (short squeeze fuel)
  short_change      — recent change in short interest (trend)
"""

import json
import logging
import warnings
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
log = logging.getLogger(__name__)

RAW_DIR = Path(__file__).parent.parent / "data" / "raw"
RAW_DIR.mkdir(parents=True, exist_ok=True)

# Only US tickers support options via yfinance
US_ONLY_TICKERS = {
    "META", "JPM", "XOM", "UNH", "TSLA", "MSFT",
    "CAT", "AMZN", "BRK-B", "AAPL", "NVDA", "GOOGL",
    "NFLX", "AMD", "INTC", "QCOM", "CRM", "ADBE",
    "V", "MA", "BAC", "GS", "MS", "AXP",
    "JNJ", "PFE", "LLY", "ABBV", "MRK", "AMGN", "GILD",
    "KO", "MCD", "WMT", "HD", "COST", "NKE", "SBUX",
    "BA", "LMT", "RTX", "GE", "HON",
    "UBER", "PYPL", "SPOT", "SHOP", "SNOW", "NOW", "ORCL", "MU", "TXN", "AMAT",
}

STALE_HOURS = 23   # re-fetch if cache older than this


def _cache_path(ticker: str) -> Path:
    return RAW_DIR / f"{ticker}_options.json"


def _is_stale(path: Path) -> bool:
    if not path.exists():
        return True
    age_hours = (datetime.now().timestamp() - path.stat().st_mtime) / 3600
    return age_hours > STALE_HOURS


def _get_atm_iv(option_chain, spot_price: float) -> dict:
    """
    Extracts ATM implied vol from the nearest expiry.
    Returns dict with iv_call, iv_put, iv_atm, iv_skew, pc_ratio.
    """
    result = {
        "iv_atm": np.nan,
        "iv_call_atm": np.nan,
        "iv_put_atm": np.nan,
        "iv_skew": np.nan,
        "pc_ratio": np.nan,
    }
    try:
        calls = option_chain.calls
        puts  = option_chain.puts

        if calls.empty or puts.empty:
            return result

        # ATM: closest strike to spot
        call_atm = calls.iloc[(calls["strike"] - spot_price).abs().argsort()[:1]]
        put_atm  = puts.iloc[(puts["strike"]  - spot_price).abs().argsort()[:1]]

        iv_call = float(call_atm["impliedVolatility"].values[0])
        iv_put  = float(put_atm["impliedVolatility"].values[0])
        iv_atm  = (iv_call + iv_put) / 2

        # Skew: OTM put IV (90% moneyness) vs OTM call IV (110% moneyness)
        otm_put_strike  = spot_price * 0.90
        otm_call_strike = spot_price * 1.10
        otm_put  = puts.iloc[(puts["strike"]   - otm_put_strike).abs().argsort()[:1]]
        otm_call = calls.iloc[(calls["strike"] - otm_call_strike).abs().argsort()[:1]]
        iv_otm_put  = float(otm_put["impliedVolatility"].values[0])  if not otm_put.empty  else np.nan
        iv_otm_call = float(otm_call["impliedVolatility"].values[0]) if not otm_call.empty else np.nan

        skew = (iv_otm_put - iv_otm_call) / iv_atm if iv_atm > 0 else np.nan

        # Put/Call volume ratio
        pc_ratio = float(puts["volume"].sum()) / max(float(calls["volume"].sum()), 1)

        result.update({
            "iv_atm":      round(iv_atm,  4),
            "iv_call_atm": round(iv_call, 4),
            "iv_put_atm":  round(iv_put,  4),
            "iv_skew":     round(skew, 4) if not np.isnan(skew) else np.nan,
            "pc_ratio":    round(pc_ratio, 4),
        })
    except Exception as e:
        log.debug(f"IV extraction error: {e}")
    return result


def fetch_options_features(ticker: str, realized_vol_21d: float = None,
                           force_refresh: bool = False) -> dict:
    """
    Fetches options and short interest features for one US ticker.
    Returns a dict of features (NaN for unavailable fields).
    Uses daily cache to avoid hammering Yahoo.
    """
    cache = _cache_path(ticker)

    if not force_refresh and not _is_stale(cache):
        with open(cache) as f:
            cached = json.load(f)
        log.debug(f"[{ticker}] options features loaded from cache")
        return cached

    if ticker not in US_ONLY_TICKERS:
        return _null_features()

    import yfinance as yf
    result = _null_features()
    result["ticker"] = ticker
    result["fetched_at"] = datetime.now().isoformat(timespec="seconds")

    try:
        t = yf.Ticker(ticker)

        # ── Short interest ─────────────────────────────────────────────
        info = t.info
        result["short_pct_float"] = _safe_float(info.get("shortPercentOfFloat"))
        result["short_ratio"]     = _safe_float(info.get("shortRatio"))        # days to cover
        result["shares_short"]    = _safe_float(info.get("sharesShort"))
        result["shares_short_prior"] = _safe_float(info.get("sharesShortPriorMonth"))

        # Short change: (current - prior) / prior  (positive = shorts building)
        if result["shares_short"] and result["shares_short_prior"] and result["shares_short_prior"] > 0:
            result["short_change"] = round(
                (result["shares_short"] - result["shares_short_prior"]) / result["shares_short_prior"], 4
            )

        # ── Options chain (IV) ─────────────────────────────────────────
        exps = t.options   # list of expiry date strings
        if exps:
            # Nearest expiry at least 7 days out (avoid expiring-today distortion)
            today = datetime.today().date()
            valid_exps = [e for e in exps
                          if (datetime.strptime(e, "%Y-%m-%d").date() - today).days >= 7]
            if valid_exps:
                nearest_exp = valid_exps[0]
                chain = t.option_chain(nearest_exp)

                # Get spot price
                hist = t.history(period="2d")
                if not hist.empty:
                    spot = float(hist["Close"].iloc[-1])
                    iv_data = _get_atm_iv(chain, spot)
                    result.update(iv_data)

                    # Vol risk premium: ATM IV vs realised vol
                    if realized_vol_21d is not None and not np.isnan(result["iv_atm"]):
                        result["iv_rv_spread"] = round(result["iv_atm"] - realized_vol_21d, 4)

        # ── IV change (5-day) ──────────────────────────────────────────
        # Load prior cache to compute delta
        if cache.exists():
            try:
                with open(cache) as f:
                    prior = json.load(f)
                prior_iv  = prior.get("iv_atm", np.nan)
                prior_date = prior.get("fetched_at", "")
                if prior_iv and not np.isnan(prior_iv) and not np.isnan(result["iv_atm"]):
                    result["iv_change_5d"] = round(result["iv_atm"] - prior_iv, 4)
            except Exception:
                pass

        log.info(f"[{ticker}] options features fetched: "
                 f"IV={result['iv_atm']}, PC={result['pc_ratio']}, "
                 f"short%={result['short_pct_float']}")

    except Exception as e:
        log.warning(f"[{ticker}] options fetch failed: {e}")

    # Cache result
    try:
        with open(cache, "w") as f:
            json.dump(result, f, indent=2, default=str)
    except Exception:
        pass

    return result


def fetch_all_options_features(tickers: list, realized_vols: dict = None,
                               force_refresh: bool = False) -> pd.DataFrame:
    """
    Fetches options features for all US tickers in the list.
    realized_vols: dict of {ticker: annualised_vol_21d}
    Returns a DataFrame indexed by ticker.
    """
    rows = []
    us_tickers = [t for t in tickers if t in US_ONLY_TICKERS]
    log.info(f"Fetching options features for {len(us_tickers)}/{len(tickers)} US tickers...")

    for ticker in us_tickers:
        rv = (realized_vols or {}).get(ticker)
        features = fetch_options_features(ticker, realized_vol_21d=rv,
                                          force_refresh=force_refresh)
        features["ticker"] = ticker
        rows.append(features)

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows).set_index("ticker")
    numeric_cols = [c for c in df.columns
                    if c not in ("fetched_at",) and df[c].dtype != object]
    return df[numeric_cols]


def _null_features() -> dict:
    return {
        "ticker":             None,
        "fetched_at":         None,
        "iv_atm":             np.nan,
        "iv_call_atm":        np.nan,
        "iv_put_atm":         np.nan,
        "iv_skew":            np.nan,
        "iv_rv_spread":       np.nan,
        "iv_change_5d":       np.nan,
        "pc_ratio":           np.nan,
        "short_pct_float":    np.nan,
        "short_ratio":        np.nan,
        "shares_short":       np.nan,
        "shares_short_prior": np.nan,
        "short_change":       np.nan,
    }


def _safe_float(val) -> float:
    try:
        return float(val) if val is not None else np.nan
    except (TypeError, ValueError):
        return np.nan


# ─────────────────────────────────────────────────────────────────────────────
# CLI test
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    tickers = sys.argv[1:] if len(sys.argv) > 1 else ["MSFT", "TSLA", "META"]
    df = fetch_all_options_features(tickers, force_refresh=True)
    print("\n=== OPTIONS FEATURES ===")
    print(df.to_string())
