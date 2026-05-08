# quant-research/regime_engine/config.py
"""
Macro Regime Detection Engine — Configuration
All thresholds derived from the quantitative_research_techniques.md spec.
Edit here only, all other modules import from this file.
"""

# ── FRED Series IDs ─────────────────────────────────────────────────────────
FRED_SERIES = {
    "vix":           "VIXCLS",       # CBOE Volatility Index
    "yield_spread":  "T10Y2Y",       # 10Y - 2Y Treasury spread (recession proxy)
    "hy_spread":     "BAMLH0A0HYM2", # ICE BofA HY OAS (credit stress)
    "ig_spread":     "BAMLC0A0CMEY", # ICE BofA IG OAS
    "fed_funds":     "FEDFUNDS",     # Effective Fed Funds Rate
    "ism_mfg":       "MANEMP",       # ISM Manufacturing proxy (nonfarm mfg employment)
}

# ── Regime Axis 1: Risk Appetite ─────────────────────────────────────────────
RISK_ON_VIX_MAX        = 20.0   # VIX below this → Risk-On territory
RISK_OFF_VIX_MIN       = 28.0   # VIX above this → Risk-Off territory
RISK_VIX_TREND_WINDOW  = 21     # days to measure VIX direction
HY_TIGHT_THRESHOLD     = 4.0    # HY spread below → credit benign
HY_WIDE_THRESHOLD      = 6.0    # HY spread above → credit stressed

# ── Regime Axis 2: Rate Environment ─────────────────────────────────────────
RATE_EASING_THRESHOLD    = -0.25  # Fed funds 3-month change below → Easing
RATE_TIGHTENING_THRESHOLD = 0.25  # Fed funds 3-month change above → Tightening
RATE_LOOKBACK_DAYS       = 63     # ~3 months

# ── Regime Axis 3: Growth Cycle ──────────────────────────────────────────────
YIELD_CURVE_EXPANSION_MIN = 0.3   # 10Y-2Y spread above → expansionary
YIELD_CURVE_INVERSION_MAX = -0.1  # 10Y-2Y spread below → contraction signal
YIELD_CURVE_TREND_WINDOW  = 63    # days to measure curve direction

# ── Early Warning Thresholds ─────────────────────────────────────────────────
EW_VIX_RISING_FROM       = 18.0  # VIX was below this
EW_VIX_RISING_TO         = 22.0  # and moved above this in EW_WINDOW days
EW_VIX_WINDOW            = 14    # days
EW_YIELD_FLATTEN_BPS     = -20.0 # curve flattened more than this (bps) in 4w
EW_YIELD_FLATTEN_WINDOW  = 28    # days
EW_HY_WIDEN_BPS          = 50.0  # HY spread widened more than this in 3w
EW_HY_WIDEN_WINDOW       = 21    # days
EW_RATE_REPRICE_THRESHOLD = 0.50  # Fed funds moved > 50bps in 4w
EW_RATE_REPRICE_WINDOW   = 28    # days
EW_TRIGGER_COUNT         = 2     # how many EW signals must fire to raise warning

# ── Output / Cache ───────────────────────────────────────────────────────────
import os
_base = os.path.join(os.path.dirname(__file__), "data")

REGIME_DB_PATH     = os.path.join(_base, "regime_history.csv")
REGIME_STATE_PATH  = os.path.join(_base, "regime_state.json")
LOOKBACK_DAYS      = 504   # match main engine
FRED_CACHE_PATH    = os.path.join(_base, "fred_cache.csv")
FRED_CACHE_TTL_HRS = 6     # refresh FRED data every 6 hours
