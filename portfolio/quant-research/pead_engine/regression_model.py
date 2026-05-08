# quant-research/pead_engine/regression_model.py
"""
PEAD Engine — Per-Ticker Surprise→Reaction Regression

For each ticker, fits an OLS regression:
  same_day_return (%) = a + b × earnings_surprise (%)

This gives us the "expected" stock reaction for a given surprise magnitude.
If actual_move < predicted_move - UNDERREACTION_MARGIN → PEAD setup confirmed.

Models are cached to JSON and rebuilt whenever new earnings data arrives.
"""

import json
import logging
import numpy as np
import pandas as pd
import os

log = logging.getLogger(__name__)

from config import (
    MIN_QUARTERS_FOR_REGRESSION,
    REGRESSION_LOOKBACK_QUARTERS,
    UNDERREACTION_MARGIN_PCT,
    REGRESSION_CACHE_PATH,
)


# ── Model Fitting ─────────────────────────────────────────────────────────────

def fit_regression(ticker: str, earnings_df: pd.DataFrame, prices_df: pd.DataFrame):
    """
    Fits the surprise→reaction regression for a single ticker.

    Parameters
    ----------
    ticker      : ticker symbol (as stored in earnings_df["ticker"])
    earnings_df : Full earnings history DataFrame from data_fetcher
    prices_df   : Daily close prices DataFrame

    Returns
    -------
    dict with keys: ticker, slope, intercept, r_squared, n_quarters, observations
    Returns None if insufficient data.
    """
    ticker_earnings = earnings_df[earnings_df["ticker"] == ticker].copy()
    ticker_earnings = ticker_earnings.dropna(subset=["earnings_date", "surprise_pct"])
    ticker_earnings = ticker_earnings.sort_values("earnings_date")
    ticker_earnings = ticker_earnings.tail(REGRESSION_LOOKBACK_QUARTERS)

    if len(ticker_earnings) < MIN_QUARTERS_FOR_REGRESSION:
        log.debug(f"  {ticker}: only {len(ticker_earnings)} quarters, need {MIN_QUARTERS_FOR_REGRESSION}. Skipping.")
        return None

    # Determine price column: Xetra or NASDAQ equivalent
    from data_fetcher import XETRA_TO_NASDAQ
    price_col = ticker
    if ticker not in prices_df.columns:
        alt = XETRA_TO_NASDAQ.get(ticker)
        if alt and alt in prices_df.columns:
            price_col = alt
        else:
            log.debug(f"  {ticker}: no price column in prices_df. Skipping.")
            return None

    prices = prices_df[price_col].dropna()

    observations = []
    for _, row in ticker_earnings.iterrows():
        e_date = pd.Timestamp(row["earnings_date"])
        surprise = float(row["surprise_pct"])

        if pd.isna(surprise):
            continue

        # Find the earnings day in price data (±1 day tolerance for market holidays)
        for offset in [0, 1, -1, 2]:
            target_date = e_date + pd.Timedelta(days=offset)
            # Find nearest trading day
            idx_matches = prices.index[prices.index >= target_date]
            if len(idx_matches) == 0:
                continue
            e_day = idx_matches[0]
            # Need the previous trading day for the pre-earnings close
            e_pos = prices.index.get_loc(e_day)
            if e_pos == 0:
                continue
            prev_day = prices.index[e_pos - 1]
            same_day_return = (prices[e_day] / prices[prev_day] - 1) * 100
            observations.append({
                "earnings_date": e_date,
                "surprise_pct": surprise,
                "same_day_return": same_day_return,
                "e_day_used": e_day,
            })
            break

    if len(observations) < MIN_QUARTERS_FOR_REGRESSION:
        log.debug(f"  {ticker}: only {len(observations)} valid observations. Skipping.")
        return None

    obs_df = pd.DataFrame(observations)
    x = obs_df["surprise_pct"].values
    y = obs_df["same_day_return"].values

    # OLS: y = a + b*x
    n  = len(x)
    x_mean, y_mean = x.mean(), y.mean()
    b = np.sum((x - x_mean) * (y - y_mean)) / np.sum((x - x_mean) ** 2)
    a = y_mean - b * x_mean

    # R-squared
    y_pred = a + b * x
    ss_res = np.sum((y - y_pred) ** 2)
    ss_tot = np.sum((y - y_mean) ** 2)
    r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 0.0

    model = {
        "ticker":      ticker,
        "slope":       round(float(b), 4),
        "intercept":   round(float(a), 4),
        "r_squared":   round(float(r2), 4),
        "n_quarters":  n,
        "fitted_on":   pd.Timestamp.now().isoformat(),
        "observations": obs_df.to_dict(orient="records"),
    }

    log.debug(f"  {ticker}: slope={b:.3f}, intercept={a:.3f}, R²={r2:.3f}, n={n}")
    return model


def fit_all_regressions(earnings_df: pd.DataFrame, prices_df: pd.DataFrame) -> dict:
    """
    Fits regression models for all tickers in earnings_df.
    Returns a dict: {ticker: model_dict}
    Saves to REGRESSION_CACHE_PATH.
    """
    tickers = earnings_df["ticker"].unique()
    models = {}
    fitted = 0

    log.info(f"Fitting surprise→reaction regressions for {len(tickers)} tickers...")
    for ticker in tickers:
        model = fit_regression(ticker, earnings_df, prices_df)
        if model:
            models[ticker] = model
            fitted += 1

    log.info(f"Regressions fitted: {fitted}/{len(tickers)} tickers")

    os.makedirs(os.path.dirname(REGRESSION_CACHE_PATH) if os.path.dirname(REGRESSION_CACHE_PATH) else ".", exist_ok=True)

    # Serialise: convert observation dicts (contain Timestamps) to strings
    def _serialise(obj):
        if isinstance(obj, pd.Timestamp):
            return str(obj)
        if isinstance(obj, (np.integer,)):
            return int(obj)
        if isinstance(obj, (np.floating,)):
            return float(obj)
        raise TypeError(f"Not serialisable: {type(obj)}")

    with open(REGRESSION_CACHE_PATH, "w") as f:
        json.dump(models, f, indent=2, default=_serialise)

    log.info(f"Regression models saved: {REGRESSION_CACHE_PATH}")
    return models


def load_regression_models() -> dict:
    """Loads cached regression models. Returns {} if not found."""
    if not os.path.exists(REGRESSION_CACHE_PATH):
        return {}
    with open(REGRESSION_CACHE_PATH) as f:
        return json.load(f)


# ── Prediction ────────────────────────────────────────────────────────────────

def predict_reaction(ticker: str, surprise_pct: float, models: dict):
    """
    Given an earnings surprise %, returns the model-predicted same-day stock move %.
    Returns None if no model exists for this ticker.
    """
    model = models.get(ticker)
    if not model:
        return None
    return round(model["intercept"] + model["slope"] * surprise_pct, 3)


def is_underreaction(
    ticker: str,
    surprise_pct: float,
    actual_same_day_return: float,
    models: dict,
):
    """
    Returns (underreaction_flag, predicted_return, gap).
    underreaction_flag = True if actual_move < predicted_move - UNDERREACTION_MARGIN_PCT

    Gap is positive when the stock underreacted (opportunity) and negative when it overreacted.
    """
    predicted = predict_reaction(ticker, surprise_pct, models)
    if predicted is None:
        return False, None, None

    gap = predicted - actual_same_day_return  # positive = underreacted
    underreacted = gap >= UNDERREACTION_MARGIN_PCT

    return underreacted, round(predicted, 3), round(gap, 3)
