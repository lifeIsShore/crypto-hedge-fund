# quant-research/pead_engine/pead_db.py
"""
PEAD Engine — Database & State Writer

Responsibilities:
  - Append-only CSV log of all PEAD setups (pead_setups.csv)
  - JSON state file for dashboard consumption (pead_state.json)
  - Outcome auto-fill: update drift columns for past setups as new prices arrive
  - Performance analytics: hit rate, avg drift, regime-stratified performance
"""

import os
import json
import logging
import numpy as np
import pandas as pd
from datetime import datetime

log = logging.getLogger(__name__)

from config import PEAD_DB_PATH, PEAD_STATE_PATH, DRIFT_WINDOW_21D, DRIFT_WINDOW_63D
from data_fetcher import XETRA_TO_NASDAQ


# ── Save / Load ───────────────────────────────────────────────────────────────

def save_setups(new_setups_df: pd.DataFrame) -> None:
    """
    Appends new PEAD setups to the CSV log.
    Deduplicates on (ticker, earnings_date) — safe to call repeatedly.
    """
    if new_setups_df.empty:
        log.info("No new PEAD setups to save.")
        return

    os.makedirs(os.path.dirname(PEAD_DB_PATH) if os.path.dirname(PEAD_DB_PATH) else ".", exist_ok=True)

    if os.path.exists(PEAD_DB_PATH):
        existing = pd.read_csv(PEAD_DB_PATH)
        # Drop all-NA columns from new_setups to avoid FutureWarning
        new_setups_df = new_setups_df.dropna(axis=1, how="all")
        combined = pd.concat([existing, new_setups_df], ignore_index=True)
        combined = combined.drop_duplicates(subset=["ticker", "earnings_date"], keep="last")
    else:
        combined = new_setups_df.copy()

    combined.to_csv(PEAD_DB_PATH, index=False)
    log.info(f"PEAD DB saved: {PEAD_DB_PATH} ({len(combined)} total setups)")


def load_setups() -> pd.DataFrame:
    """Loads full PEAD setup history. Returns empty DataFrame if not found."""
    if not os.path.exists(PEAD_DB_PATH):
        log.warning(f"No PEAD DB at {PEAD_DB_PATH}. Run the engine first.")
        return pd.DataFrame()
    df = pd.read_csv(PEAD_DB_PATH, parse_dates=["earnings_date"])
    return df


# ── Outcome Auto-Fill ─────────────────────────────────────────────────────────

def backfill_outcomes(prices_df: pd.DataFrame) -> pd.DataFrame:
    """
    For past PEAD setups where drift_21d or drift_63d is missing,
    attempts to fill them from current price data.

    Returns the updated DataFrame (also saves it).
    """
    db = load_setups()
    if db.empty:
        return db

    updated = 0

    for i, row in db.iterrows():
        ticker    = row["ticker"]
        entry_str = row.get("entry_date")

        if pd.isna(entry_str):
            continue

        entry_date = pd.Timestamp(entry_str)

        # Resolve price column
        price_col = ticker
        if ticker not in prices_df.columns:
            alt = XETRA_TO_NASDAQ.get(ticker)
            if alt and alt in prices_df.columns:
                price_col = alt
            else:
                continue

        prices = prices_df[price_col].dropna()
        future = prices.index[prices.index >= entry_date]

        def _fwd(n):
            if len(future) <= n:
                return None
            start = prices[future[0]]
            end   = prices[future[n]]
            return round((end / start - 1) * 100, 3) if start != 0 else None

        # Only update if currently null
        if pd.isna(row.get("drift_21d")):
            val = _fwd(DRIFT_WINDOW_21D)
            if val is not None:
                db.at[i, "drift_21d"] = val
                updated += 1

        if pd.isna(row.get("drift_63d")):
            val = _fwd(DRIFT_WINDOW_63D)
            if val is not None:
                db.at[i, "drift_63d"] = val
                updated += 1

        # Auto-update outcome_label_correct
        if not pd.isna(db.at[i, "drift_21d"]) and pd.isna(row.get("outcome_label_correct")):
            is_beat = row.get("direction", "bullish") == "bullish"
            db.at[i, "outcome_label_correct"] = (db.at[i, "drift_21d"] > 0) == is_beat

    if updated:
        db.to_csv(PEAD_DB_PATH, index=False)
        log.info(f"Backfilled {updated} outcome cells in PEAD DB.")

    return db


# ── Performance Analytics ─────────────────────────────────────────────────────

def compute_performance_stats(db: pd.DataFrame) -> dict:
    """
    Computes overall PEAD performance statistics.
    Returns a dict suitable for JSON serialisation.
    """
    if db.empty:
        return {}

    def _safe_mean(series):
        s = series.dropna()
        return round(float(s.mean()), 3) if len(s) > 0 else None

    def _hit_rate(series, direction_series=None):
        s = series.dropna()
        if len(s) == 0:
            return None
        if direction_series is not None:
            dirs = direction_series.loc[s.index]
            hits = sum((v > 0) == (d == "bullish") for v, d in zip(s, dirs))
        else:
            hits = (s > 0).sum()
        return round(float(hits / len(s)), 3)

    high = db[db["pead_setup_quality"] == "High"]
    med  = db[db["pead_setup_quality"] == "Medium"]

    stats = {
        "total_setups":           len(db),
        "high_quality_setups":    len(high),
        "medium_quality_setups":  len(med),
        # Overall drift stats
        "overall_avg_drift_21d":  _safe_mean(db["drift_21d"]),
        "overall_avg_drift_63d":  _safe_mean(db["drift_63d"]),
        "overall_hit_rate_21d":   _hit_rate(db["drift_21d"], db["direction"]),
        # High quality only
        "high_avg_drift_21d":     _safe_mean(high["drift_21d"]) if len(high) else None,
        "high_avg_drift_63d":     _safe_mean(high["drift_63d"]) if len(high) else None,
        "high_hit_rate_21d":      _hit_rate(high["drift_21d"], high["direction"]) if len(high) else None,
        # By direction
        "bullish_avg_drift_21d":  _safe_mean(db[db["direction"]=="bullish"]["drift_21d"]),
        "bearish_avg_drift_21d":  _safe_mean(db[db["direction"]=="bearish"]["drift_21d"]),
        # Computed at
        "stats_computed_at": datetime.now().isoformat(),
    }

    # Regime-stratified (if regime column exists)
    if "regime_growth" in db.columns:
        for regime in db["regime_growth"].dropna().unique():
            r_db = db[db["regime_growth"] == regime]
            stats[f"hit_rate_21d_{regime.lower()}"] = _hit_rate(r_db["drift_21d"], r_db["direction"])
            stats[f"avg_drift_21d_{regime.lower()}"] = _safe_mean(r_db["drift_21d"])

    return stats


# ── JSON State ─────────────────────────────────────────────────────────────────

def write_pead_state(setups_df: pd.DataFrame, db: pd.DataFrame) -> dict:
    """
    Writes pead_state.json for dashboard consumption.
    Includes: active setups, entry windows, performance stats.
    """
    perf = compute_performance_stats(db)

    # Active setups: quality High or Medium, within entry window
    today = pd.Timestamp.now().normalize()
    active = []
    if not setups_df.empty:
        for _, row in setups_df.iterrows():
            if row.get("pead_setup_quality") not in ["High", "Medium"]:
                continue
            entry = pd.Timestamp(row["entry_date"]) if row.get("entry_date") else None
            # Consider active if entry date is today or in the past 5 days
            if entry and (today - entry).days <= 5:
                active.append({
                    "ticker":           row["ticker"],
                    "direction":        row["direction"],
                    "quality":          row["pead_setup_quality"],
                    "earnings_date":    str(row["earnings_date"]),
                    "surprise_pct":     row["surprise_pct"],
                    "entry_date":       str(entry.date()),
                    "sector":           row.get("sector", ""),
                    "drift_window":     row.get("drift_window_days"),
                    "underreaction":    bool(row.get("underreaction_flag", False)),
                    "reaction_gap":     row.get("reaction_gap"),
                })

    # Recent setups (last 30 days, all qualities)
    recent_list = []
    if not setups_df.empty:
        for _, row in setups_df.head(20).iterrows():
            recent_list.append({
                "ticker":       row["ticker"],
                "direction":    row["direction"],
                "quality":      row["pead_setup_quality"],
                "surprise_pct": row["surprise_pct"],
                "drift_21d":    row.get("drift_21d"),
                "drift_63d":    row.get("drift_63d"),
            })

    state = {
        "generated_at":    datetime.now().isoformat(),
        "active_setups":   active,
        "recent_setups":   recent_list,
        "performance":     perf,
        "total_in_db":     len(db),
    }

    os.makedirs(os.path.dirname(PEAD_STATE_PATH) if os.path.dirname(PEAD_STATE_PATH) else ".", exist_ok=True)
    with open(PEAD_STATE_PATH, "w") as f:
        json.dump(state, f, indent=2, default=str)

    log.info(f"PEAD state written: {PEAD_STATE_PATH} | {len(active)} active setups")
    return state
