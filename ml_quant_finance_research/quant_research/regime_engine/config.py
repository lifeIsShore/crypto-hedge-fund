# quant-research/regime_engine/config.py
"""
Macro Regime Detection Engine — Configuration
All thresholds derived from the quantitative_research_techniques.md spec.
Edit here only, all other modules import from this file.
"""

# ── FRED / yfinance Series IDs ───────────────────────────────────────────────
# US Series (Default)
FRED_SERIES_US = {
    "vix":           "VIXCLS",       # CBOE Volatility Index
    "yield_spread":  "T10Y2Y",       # 10Y - 2Y Treasury spread (recession proxy)
    "hy_spread":     "BAMLH0A0HYM2", # ICE BofA HY OAS (credit stress)
    "ig_spread":     "BAMLC0A0CMEY", # ICE BofA IG OAS
    "fed_funds":     "FEDFUNDS",     # Effective Fed Funds Rate
    "ism_mfg":       "MANEMP",       # ISM Manufacturing proxy (nonfarm mfg employment)
}

# EU Series
FRED_SERIES_EU = {
    "vix":           "^V2TX",        # VSTOXX (via yfinance)
    "yield_10y":     "IRLTLT01DEM156N", # API Compatible German 10Y
    "yield_3m":      "IR3TIB01DEM156N", # API Compatible German 3M
    "hy_spread":     "BAMLHE00EHYIOAS", 
    "ig_spread":     "BAMLC0A0CMEY",    
    "fed_funds":     "ECBDFR",          # API Compatible ECB Rate
    "fed_funds_alt": "ECBMLFR",        
    "ism_mfg":       "MANEMP",       
}

# Mapping for data fetcher
REGIONAL_SERIES = {
    "US": FRED_SERIES_US,
    "EU": FRED_SERIES_EU
}

# ── Regime Thresholds (Region-Aware) ─────────────────────────────────────────

THRESHOLDS = {
    "US": {
        "RISK_ON_VIX_MAX":        20.0,
        "RISK_OFF_VIX_MIN":       28.0,
        "RISK_VIX_TREND_WINDOW":  21,
        "HY_TIGHT_THRESHOLD":     4.0,
        "HY_WIDE_THRESHOLD":      6.0,
        "RATE_EASING_THRESHOLD":    -0.25,
        "RATE_TIGHTENING_THRESHOLD": 0.25,
        "RATE_LOOKBACK_DAYS":       63,
        "YIELD_CURVE_EXPANSION_MIN": 0.3,
        "YIELD_CURVE_INVERSION_MAX": -0.1,
        "YIELD_CURVE_TREND_WINDOW":  63,
    },
    "EU": {
        "RISK_ON_VIX_MAX":        22.0,  # VSTOXX usually trades higher than VIX
        "RISK_OFF_VIX_MIN":       30.0,
        "RISK_VIX_TREND_WINDOW":  21,
        "HY_TIGHT_THRESHOLD":     3.5,  # Euro spreads often tighter than US
        "HY_WIDE_THRESHOLD":      5.5,
        "RATE_EASING_THRESHOLD":    -0.15, # ECB moves in smaller increments often
        "RATE_TIGHTENING_THRESHOLD": 0.15,
        "RATE_LOOKBACK_DAYS":       63,
        "YIELD_CURVE_EXPANSION_MIN": 0.2,
        "YIELD_CURVE_INVERSION_MAX": -0.05,
        "YIELD_CURVE_TREND_WINDOW":  63,
    }
}

# ── Early Warning Thresholds (Static for now) ────────────────────────────────
EW_VIX_RISING_FROM       = 18.0
EW_VIX_RISING_TO         = 22.0
EW_VIX_WINDOW            = 14
EW_YIELD_FLATTEN_BPS     = -20.0
EW_YIELD_FLATTEN_WINDOW  = 28
EW_HY_WIDEN_BPS          = 50.0
EW_HY_WIDEN_WINDOW       = 21
EW_RATE_REPRICE_THRESHOLD = 0.50
EW_RATE_REPRICE_WINDOW   = 28
EW_TRIGGER_COUNT         = 2

# ── Output / Cache ───────────────────────────────────────────────────────────
import os
import sys

# Ensure root is in path for shared imports
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.normpath(os.path.join(_HERE, "..", "..", ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

try:
    from shared.state_paths import REGIME_HISTORY_PATH as REGIME_DB_PATH
    from shared.state_paths import REGIME_STATE_PATH
except ImportError:
    # Fallback if run in isolation
    _base = os.path.join(_HERE, "data")
    REGIME_DB_PATH     = os.path.join(_base, "regime_history.csv")
    REGIME_STATE_PATH  = os.path.join(_base, "regime_state.json")

LOOKBACK_DAYS      = 504
_base_local = os.path.join(_HERE, "data")
# Cache path is parameterized by region
def get_cache_path(region: str) -> str:
    return os.path.join(_base_local, f"fred_cache_{region.lower()}.csv")

FRED_CACHE_TTL_HRS = 6
