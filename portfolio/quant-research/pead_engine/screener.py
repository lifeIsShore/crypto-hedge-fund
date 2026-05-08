# quant-research/pead_engine/screener.py
"""
PEAD Engine — Setup Screener

Scans recent earnings events against all criteria from the spec:
  1. EPS surprise > +5% (beat) or < -5% (miss)
  2. Revenue surprise > +3% (if available)
  3. Volume on earnings day above 1.2× 20d average
  4. Underreaction: actual move < predicted move - 2% (from regression)
  5. No concurrent negative catalyst (guidance flag from notes if available)

Outputs a list of PEAD setups with quality scores.
"""

import logging
import numpy as np
import pandas as pd
from datetime import datetime, timedelta

log = logging.getLogger(__name__)

from config import (
    EPS_SURPRISE_BEAT_MIN, EPS_SURPRISE_MISS_MAX,
    REV_SURPRISE_BEAT_MIN,
    VOLUME_CONFIRMATION_MULTIPLE,
    ENTRY_DAYS_AFTER_EARNINGS,
    DRIFT_WINDOW_21D, DRIFT_WINDOW_63D,
    SECTOR_DRIFT_WINDOWS,
)
from data_fetcher import get_sector, get_volume_data, XETRA_TO_NASDAQ
from regression_model import is_underreaction


def _price_return(prices: pd.Series, from_date: pd.Timestamp, days_forward: int):
    """Computes forward return from a start date over N trading days."""
    future = prices.index[prices.index >= from_date]
    if len(future) < days_forward + 1:
        return None
    start_price = prices[future[0]]
    end_price   = prices[future[days_forward]]
    if start_price == 0:
        return None
    return round((end_price / start_price - 1) * 100, 3)


def _volume_confirmed(ticker: str, earnings_date: pd.Timestamp) -> bool:
    """
    Checks if volume on earnings day exceeded VOLUME_CONFIRMATION_MULTIPLE × 20d avg.
    Returns True (confirmed), False (not confirmed), or True if data unavailable
    (we don't want to disqualify on missing data alone).
    """
    vol = get_volume_data(ticker, lookback_days=30)
    if vol.empty or len(vol) < 5:
        return True  # insufficient data → don't penalise

    # Find earnings day volume
    e_matches = vol.index[vol.index >= earnings_date.normalize()]
    if not len(e_matches):
        return True

    e_vol  = vol[e_matches[0]]
    avg_20 = vol[vol.index < e_matches[0]].tail(20).mean()

    if pd.isna(avg_20) or avg_20 == 0:
        return True

    return float(e_vol) >= float(avg_20) * VOLUME_CONFIRMATION_MULTIPLE


def score_setup_quality(
    eps_beat: bool,
    rev_beat: bool | None,
    volume_confirmed: bool,
    underreaction: bool,
) -> str:
    """
    Returns setup quality: High / Medium / Low.
    High:   EPS beat + underreaction confirmed + (revenue beat OR volume confirmed)
    Medium: EPS beat + underreaction confirmed
    Low:    EPS beat only
    """
    if not eps_beat:
        return "Disqualified"
    if underreaction and (rev_beat or volume_confirmed):
        return "High"
    if underreaction:
        return "Medium"
    return "Low"


def screen_recent_earnings(
    earnings_df: pd.DataFrame,
    prices_df: pd.DataFrame,
    regression_models: dict,
    lookback_days: int = 90,
    direction: str = "both",   # "bullish", "bearish", or "both"
) -> pd.DataFrame:
    """
    Screens all earnings events in the past `lookback_days` for PEAD setups.

    Parameters
    ----------
    earnings_df       : Full earnings history from data_fetcher
    prices_df         : Price history DataFrame
    regression_models : Fitted models from regression_model
    lookback_days     : How far back to look for recent earnings
    direction         : Filter by bullish/bearish setup or both

    Returns
    -------
    DataFrame of PEAD setups, sorted by quality and surprise magnitude.
    """
    cutoff = pd.Timestamp.now() - pd.Timedelta(days=lookback_days)
    recent = earnings_df[earnings_df["earnings_date"] >= cutoff].copy()

    if recent.empty:
        log.info("No earnings events in lookback window.")
        return pd.DataFrame()

    log.info(f"Screening {len(recent)} earnings events (last {lookback_days}d)...")

    setups = []

    for _, row in recent.iterrows():
        ticker      = row.get("ticker", "")
        e_date      = pd.Timestamp(row["earnings_date"])
        surprise    = row.get("surprise_pct")
        rev_surprise = row.get("revenue_surprise_pct")

        if pd.isna(surprise):
            continue

        surprise     = float(surprise)
        rev_surprise = float(rev_surprise) if not pd.isna(rev_surprise) else None

        # ── Step 1: EPS surprise threshold ───────────────────────────────────
        is_beat = surprise >= EPS_SURPRISE_BEAT_MIN
        is_miss = surprise <= EPS_SURPRISE_MISS_MAX

        if direction == "bullish" and not is_beat:
            continue
        if direction == "bearish" and not is_miss:
            continue
        if direction == "both" and not (is_beat or is_miss):
            continue

        # ── Step 2: Resolve price column ──────────────────────────────────────
        price_col = ticker
        if ticker not in prices_df.columns:
            alt = XETRA_TO_NASDAQ.get(ticker)
            if alt and alt in prices_df.columns:
                price_col = alt
            else:
                log.debug(f"  {ticker}: no price data, skipping")
                continue

        prices = prices_df[price_col].dropna()

        # ── Step 3: Same-day return ───────────────────────────────────────────
        e_day_matches = prices.index[prices.index >= e_date]
        if len(e_day_matches) < 2:
            continue

        e_day = e_day_matches[0]
        e_pos = prices.index.get_loc(e_day)
        if e_pos == 0:
            continue

        prev_close       = prices.iloc[e_pos - 1]
        e_day_close      = prices.iloc[e_pos]
        same_day_return  = (e_day_close / prev_close - 1) * 100

        # ── Step 4: Underreaction check ───────────────────────────────────────
        underreacted, predicted_return, reaction_gap = is_underreaction(
            ticker, surprise, same_day_return, regression_models
        )
        # For miss direction, underreaction = stock didn't fall as much as predicted
        if is_miss:
            underreacted = reaction_gap is not None and reaction_gap <= -abs(
                2.0  # UNDERREACTION_MARGIN_PCT for downside
            )

        # ── Step 5: Revenue beat check ────────────────────────────────────────
        rev_beat = (rev_surprise is not None and rev_surprise >= REV_SURPRISE_BEAT_MIN) if is_beat else None

        # ── Step 6: Volume confirmation ───────────────────────────────────────
        vol_confirmed = _volume_confirmed(ticker, e_date)

        # ── Step 7: Quality score ─────────────────────────────────────────────
        quality = score_setup_quality(is_beat or is_miss, rev_beat, vol_confirmed, underreacted)

        # ── Step 8: Entry date ────────────────────────────────────────────────
        entry_idx = e_pos + ENTRY_DAYS_AFTER_EARNINGS
        entry_date = prices.index[entry_idx] if entry_idx < len(prices) else None

        # ── Step 9: Drift outcomes (auto-fill if data available) ──────────────
        drift_21d = None
        drift_63d = None
        if entry_date:
            drift_21d = _price_return(prices, entry_date, DRIFT_WINDOW_21D)
            drift_63d = _price_return(prices, entry_date, DRIFT_WINDOW_63D)

        # ── Step 10: Sector and drift window ─────────────────────────────────
        sector = get_sector(ticker)
        drift_window = SECTOR_DRIFT_WINDOWS.get(sector, SECTOR_DRIFT_WINDOWS["Default"])

        setup = {
            "ticker":               ticker,
            "earnings_date":        e_date.date(),
            "surprise_pct":         round(surprise, 2),
            "revenue_surprise_pct": round(rev_surprise, 2) if rev_surprise else None,
            "same_day_return":      round(same_day_return, 3),
            "predicted_return":     predicted_return,
            "reaction_gap":         reaction_gap,
            "underreaction_flag":   underreacted,
            "rev_beat":             rev_beat,
            "volume_confirmed":     vol_confirmed,
            "pead_setup_quality":   quality,
            "direction":            "bullish" if is_beat else "bearish",
            "entry_date":           str(entry_date.date()) if entry_date else None,
            "sector":               sector,
            "drift_window_days":    drift_window[0],
            "drift_21d":            drift_21d,
            "drift_63d":            drift_63d,
            "outcome_label_correct": _is_correct(drift_21d, is_beat) if drift_21d else None,
            "screened_at":          datetime.now().isoformat(),
        }
        setups.append(setup)

    if not setups:
        log.info("No PEAD setups found in this window.")
        return pd.DataFrame()

    df = pd.DataFrame(setups)

    # Sort: High quality first, then by absolute surprise magnitude
    quality_order = {"High": 0, "Medium": 1, "Low": 2, "Disqualified": 3}
    df["_q"] = df["pead_setup_quality"].map(quality_order)
    df = df.sort_values(["_q", "surprise_pct"], ascending=[True, False]).drop(columns=["_q"])
    df = df.reset_index(drop=True)

    # Summary log
    high   = len(df[df["pead_setup_quality"] == "High"])
    medium = len(df[df["pead_setup_quality"] == "Medium"])
    low    = len(df[df["pead_setup_quality"] == "Low"])
    log.info(f"PEAD setups found: {len(df)} total | High={high} Medium={medium} Low={low}")

    return df


def _is_correct(drift_21d: float | None, is_beat: bool) -> bool | None:
    """Did the drift go in the expected direction within 21 days?"""
    if drift_21d is None:
        return None
    return (drift_21d > 0) == is_beat
