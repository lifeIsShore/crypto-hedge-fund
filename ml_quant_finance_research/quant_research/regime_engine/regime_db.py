# quant-research/regime_engine/regime_db.py
"""
Regime Database — Append-only CSV log + JSON state file.
Supports regional partitioning (US, EU).
"""

import os
import json
import logging
import pandas as pd
import numpy as np
from datetime import datetime, date

log = logging.getLogger(__name__)

from config import REGIME_DB_PATH, REGIME_STATE_PATH


# ── Save / Load ───────────────────────────────────────────────────────────────

def save_regime_history(regime_df: pd.DataFrame, region: str = "US") -> None:
    """
    Appends new rows to the regime history CSV.
    Uses (date, region) as the unique key.
    """
    os.makedirs(os.path.dirname(REGIME_DB_PATH) if os.path.dirname(REGIME_DB_PATH) else ".", exist_ok=True)

    # Ensure region column exists in input
    df_to_save = regime_df.copy()
    df_to_save["region"] = region

    if os.path.exists(REGIME_DB_PATH):
        existing = pd.read_csv(REGIME_DB_PATH, index_col=0, parse_dates=True)
        if "region" not in existing.columns:
            existing["region"] = "US"  # Migration for old data
        
        # Filter for new rows (idempotent)
        # Check combination of index (date) and region
        existing_keys = set(zip(existing.index.astype(str), existing["region"]))
        new_mask = [
            (str(idx.date()), region) not in existing_keys 
            for idx in df_to_save.index
        ]
        new_rows = df_to_save[new_mask]
        
        if new_rows.empty:
            log.info(f"Regime history ({region}): no new rows to append.")
            return
        combined = pd.concat([existing, new_rows]).sort_index()
    else:
        combined = df_to_save

    combined.to_csv(REGIME_DB_PATH)
    log.info(f"Regime history saved: {REGIME_DB_PATH} ({region} added, {len(combined)} total rows)")


def load_regime_history(region: str = None) -> pd.DataFrame:
    """Loads regime history. Optionally filters by region."""
    if not os.path.exists(REGIME_DB_PATH):
        return pd.DataFrame()
    df = pd.read_csv(REGIME_DB_PATH, index_col=0, parse_dates=True)
    if "region" not in df.columns:
        df["region"] = "US"
    
    if region:
        return df[df["region"] == region]
    return df


# ── JSON State (dashboard feed) ───────────────────────────────────────────────

def write_regime_state(regime_df: pd.DataFrame, region: str = "US") -> dict:
    """
    Writes the latest regime snapshot to a region-specific JSON state.
    """
    latest = regime_df.iloc[-1]
    prev   = regime_df.iloc[-2] if len(regime_df) > 1 else latest

    changed = (latest.get("regime_composite", "") != prev.get("regime_composite", ""))

    def _safe(val):
        if pd.isna(val): return None
        if isinstance(val, (bool, np.bool_)): return bool(val)
        if isinstance(val, (int, np.integer)): return int(val)
        if isinstance(val, (float, np.floating)): return round(float(val), 4)
        return str(val)

    state = {
        "region":            region,
        "generated_at":      datetime.now().isoformat(),
        "as_of_date":        str(regime_df.index[-1].date()),
        "regime_risk":       str(latest.get("regime_risk",    "Unknown")),
        "regime_rates":      str(latest.get("regime_rates",   "Unknown")),
        "regime_growth":     str(latest.get("regime_growth",  "Unknown")),
        "regime_composite":  str(latest.get("regime_composite", "Unknown")),
        "transition_warning": bool(latest.get("transition_warning", False)),
        "ew_active_count":   int(latest.get("ew_active_count", 0)),
        "macro_snapshot": {
            "vix":            _safe(latest.get("vix")),
            "yield_spread":   _safe(latest.get("yield_spread")),
            "hy_spread":      _safe(latest.get("hy_spread")),
            "fed_funds":      _safe(latest.get("fed_funds")),
        },
        "regime_changed_today": changed,
    }

    # Parameterize the state path by region for the dashboard to consume
    state_path = REGIME_STATE_PATH.replace(".json", f"_{region.lower()}.json")
    os.makedirs(os.path.dirname(state_path) if os.path.dirname(state_path) else ".", exist_ok=True)

    with open(state_path, "w") as f:
        json.dump(state, f, indent=2)
    log.info(f"Regime state ({region}) written → {state_path}")

    # Always update the canonical regime_state.json so the dashboard's
    # staleness check (which monitors REGIME_STATE_PATH) sees a fresh file.
    # For multi-region runs (ALL), the last region written wins — US runs first
    # so EU will be the final snapshot, but the file_age check just needs it fresh.
    canonical_path = REGIME_STATE_PATH
    os.makedirs(os.path.dirname(canonical_path) if os.path.dirname(canonical_path) else ".", exist_ok=True)
    with open(canonical_path, "w") as f:
        json.dump(state, f, indent=2)
    log.info(f"Regime state (canonical) written → {canonical_path}")

    return state
