# quant-research/regime_engine/regime_db.py
"""
Regime Database — Append-only CSV log + JSON state file.

Responsibilities:
  - Save daily regime classifications to regime_history.csv
  - Write latest regime state to regime_state.json (consumed by dashboard)
  - Query historical regime data for signal performance stratification
  - Detect regime changes (transitions) for alerting
"""

import os
import json
import logging
import pandas as pd
from datetime import datetime, date

log = logging.getLogger(__name__)

from config import REGIME_DB_PATH, REGIME_STATE_PATH


# ── Save / Load ───────────────────────────────────────────────────────────────

def save_regime_history(regime_df: pd.DataFrame) -> None:
    """
    Appends new rows to the regime history CSV.
    Skips dates already present (idempotent — safe to call repeatedly).
    """
    os.makedirs(os.path.dirname(REGIME_DB_PATH) if os.path.dirname(REGIME_DB_PATH) else ".", exist_ok=True)

    if os.path.exists(REGIME_DB_PATH):
        existing = pd.read_csv(REGIME_DB_PATH, index_col=0, parse_dates=True)
        new_rows  = regime_df[~regime_df.index.isin(existing.index)]
        if new_rows.empty:
            log.info("Regime history: no new rows to append.")
            return
        combined = pd.concat([existing, new_rows]).sort_index()
    else:
        combined = regime_df

    combined.to_csv(REGIME_DB_PATH)
    log.info(f"Regime history saved: {REGIME_DB_PATH} ({len(combined)} total rows)")


def load_regime_history() -> pd.DataFrame:
    """Loads full regime history from CSV. Returns empty DataFrame if not found."""
    if not os.path.exists(REGIME_DB_PATH):
        log.warning(f"No regime history at {REGIME_DB_PATH}. Run the engine first.")
        return pd.DataFrame()
    df = pd.read_csv(REGIME_DB_PATH, index_col=0, parse_dates=True)
    log.info(f"Regime history loaded: {len(df)} rows ({df.index[0].date()} → {df.index[-1].date()})")
    return df


# ── JSON State (dashboard feed) ───────────────────────────────────────────────

def write_regime_state(regime_df: pd.DataFrame) -> dict:
    """
    Writes the latest regime snapshot to regime_state.json.
    This file is consumed by the portfolio dashboard.

    Returns the state dict for convenience.
    """
    latest = regime_df.iloc[-1]
    prev   = regime_df.iloc[-2] if len(regime_df) > 1 else latest

    # Detect regime change vs. previous day
    changed = (
        latest.get("regime_composite", "") != prev.get("regime_composite", "")
    )

    # Build safe scalar values
    def _safe(val):
        try:
            if pd.isna(val):
                return None
            if isinstance(val, (bool, np.bool_)):
                return bool(val)
            if isinstance(val, (int, np.integer)):
                return int(val)
            if isinstance(val, (float, np.floating)):
                return round(float(val), 4)
            return str(val)
        except Exception:
            return str(val)

    import numpy as np

    state = {
        "generated_at":      datetime.now().isoformat(),
        "as_of_date":        str(regime_df.index[-1].date()),
        "regime_risk":       str(latest.get("regime_risk",    "Unknown")),
        "regime_rates":      str(latest.get("regime_rates",   "Unknown")),
        "regime_growth":     str(latest.get("regime_growth",  "Unknown")),
        "regime_composite":  str(latest.get("regime_composite", "Unknown")),
        "transition_warning": bool(latest.get("transition_warning", False)),
        "ew_active_count":   int(latest.get("ew_active_count", 0)),
        "ew_flags": {
            "vix_rising":       bool(latest.get("ew_vix_rising",         False)),
            "curve_flattening": bool(latest.get("ew_curve_flattening",   False)),
            "hy_widening":      bool(latest.get("ew_hy_widening",        False)),
            "rate_reprice":     bool(latest.get("ew_rate_reprice",       False)),
        },
        "macro_snapshot": {
            "vix":            _safe(latest.get("vix")),
            "yield_spread":   _safe(latest.get("yield_spread")),
            "hy_spread":      _safe(latest.get("hy_spread")),
            "ig_spread":      _safe(latest.get("ig_spread")),
            "fed_funds":      _safe(latest.get("fed_funds")),
        },
        "regime_changed_today": changed,
        "prev_regime_composite": str(prev.get("regime_composite", "Unknown")),
        # Historical distribution: how many days in each composite regime
        "regime_distribution": _compute_distribution(regime_df),
        # Streak: how many consecutive days in current regime
        "current_streak_days": _compute_streak(regime_df),
    }

    os.makedirs(os.path.dirname(REGIME_STATE_PATH) if os.path.dirname(REGIME_STATE_PATH) else ".", exist_ok=True)
    with open(REGIME_STATE_PATH, "w") as f:
        json.dump(state, f, indent=2)

    log.info(
        f"Regime state written → {REGIME_STATE_PATH} | "
        f"{state['regime_composite']} | EW={state['transition_warning']}"
    )
    return state


def _compute_distribution(regime_df: pd.DataFrame) -> dict:
    """Returns % of days in each composite regime label."""
    if "regime_composite" not in regime_df.columns or regime_df.empty:
        return {}
    counts = regime_df["regime_composite"].value_counts(normalize=True)
    return {k: round(float(v) * 100, 1) for k, v in counts.items()}


def _compute_streak(regime_df: pd.DataFrame) -> int:
    """Returns the number of consecutive days in the current composite regime."""
    if "regime_composite" not in regime_df.columns or len(regime_df) < 2:
        return 1
    current = regime_df["regime_composite"].iloc[-1]
    streak = 0
    for val in reversed(regime_df["regime_composite"].tolist()):
        if val == current:
            streak += 1
        else:
            break
    return streak


# ── Signal Performance Stratification ────────────────────────────────────────

def stratify_by_regime(
    signal_df: pd.DataFrame,
    regime_history: pd.DataFrame,
    outcome_col: str,
    signal_col: str = None,
) -> pd.DataFrame:
    """
    Joins a signal/outcome DataFrame with regime labels by date.
    Allows performance analysis like:
      "What was the PEAD hit rate during Expansion vs. Contraction?"

    Parameters
    ----------
    signal_df     : DataFrame with a date index (or 'signal_date' column)
    regime_history: Full regime history DataFrame from load_regime_history()
    outcome_col   : Column in signal_df containing the outcome (e.g., 'drift_21d')
    signal_col    : Optional column to filter on before joining

    Returns
    -------
    Merged DataFrame with regime columns added, grouped summary printed.
    """
    if regime_history.empty:
        log.warning("No regime history available for stratification.")
        return signal_df

    regime_cols = ["regime_risk", "regime_rates", "regime_growth", "regime_composite"]
    reg = regime_history[regime_cols]

    if "signal_date" in signal_df.columns:
        merged = signal_df.copy()
        merged.index = pd.to_datetime(merged["signal_date"])
    else:
        merged = signal_df.copy()

    merged = merged.join(reg, how="left")

    if outcome_col in merged.columns:
        log.info(f"\n── Stratification: {outcome_col} by Growth Regime ──")
        summary = (
            merged.groupby("regime_growth")[outcome_col]
            .agg(["count", "mean", lambda x: (x > 0).mean()])
            .rename(columns={"count": "n", "mean": "avg_outcome", "<lambda_0>": "hit_rate"})
        )
        log.info("\n" + summary.to_string())

    return merged
