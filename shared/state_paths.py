# shared/state_paths.py
"""
Single source of truth for all inter-project state file paths.

Both engine/ and ml_quant_finance_research/ import from here.
No path strings are hardcoded anywhere else.

Directory layout:
    hedge-fund/
        shared/
            state/
                ml_state.json          <- written by stock_ml_lab, read by engine/alpha/ml_alpha.py
                pead_setups.csv        <- written by pead_engine,   read by engine/alpha/pead_alpha.py
                regime_state.json      <- written by regime_engine,  read by engine/features/feature_store.py
                regime_history.csv     <- written by regime_engine,  read by pead_engine (regime tagging)
                factor_state.json      <- written by general_research notebooks (optional)
                correlation_state.json <- written by general_research notebooks (optional)
"""

import os

# Resolve hedge-fund/ root regardless of where this file is imported from.
# shared/state_paths.py sits one level below the project root.
_HERE      = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.normpath(os.path.join(_HERE, ".."))
STATE_DIR  = os.path.join(PROJECT_ROOT, "shared", "state")

# ── Primary inter-project contracts ──────────────────────────────────────────

ML_STATE_PATH         = os.path.join(STATE_DIR, "ml_state.json")
PEAD_SETUPS_PATH      = os.path.join(STATE_DIR, "pead_setups.csv")
PEAD_STATE_PATH       = os.path.join(STATE_DIR, "pead_state.json")
REGIME_STATE_PATH     = os.path.join(STATE_DIR, "regime_state.json")
REGIME_HISTORY_PATH   = os.path.join(STATE_DIR, "regime_history.csv")

# ── General research notebook outputs (optional inputs to engine) ─────────────
FACTOR_STATE_PATH      = os.path.join(STATE_DIR, "factor_state.json")
CORRELATION_STATE_PATH = os.path.join(STATE_DIR, "correlation_state.json")


def ensure_state_dir() -> None:
    """Creates the shared/state directory if it doesn't exist. Call at startup."""
    os.makedirs(STATE_DIR, exist_ok=True)


def state_file_ages() -> dict:
    """
    Returns the age in hours of each primary state file.
    Useful for freshness checks in the dashboard or scheduler.
    """
    import time
    paths = {
        "ml_state":       ML_STATE_PATH,
        "pead_setups":    PEAD_SETUPS_PATH,
        "pead_state":     PEAD_STATE_PATH,
        "regime_state":   REGIME_STATE_PATH,
        "regime_history": REGIME_HISTORY_PATH,
    }
    ages = {}
    now = time.time()
    for name, path in paths.items():
        if os.path.exists(path):
            ages[name] = round((now - os.path.getmtime(path)) / 3600, 1)
        else:
            ages[name] = None   # file doesn't exist yet
    return ages
