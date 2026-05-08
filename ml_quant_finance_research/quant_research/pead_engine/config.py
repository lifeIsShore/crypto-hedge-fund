# quant-research/pead_engine/config.py
"""
PEAD Engine — Configuration
All thresholds from quantitative_research_techniques.md §Technique 2.
Edit only here — all other modules import from this file.
"""

# ── Universe (subset of main engine that has earnings data) ─────────────────
# These are the tickers we actively screen for PEAD setups.
# Xetra-listed US stocks (APC.DE, MSF.DE) map to their NASDAQ equivalents
# for earnings data fetching — see XETRA_TO_NASDAQ in data_fetcher.py.
PEAD_UNIVERSE = [
    # US Big Tech
    "APC.DE", "MSF.DE", "AMZN", "NVDA", "GOOGL", "META", "TSLA",
    "CRM", "ADBE", "NFLX",
    # Psychedelic Biotech
    "ATAI",
    # US Semis
    "AMD", "INTC", "QCOM", "AMAT", "MU", "TXN", "ORCL",
    # US Software
    "NOW", "SNOW", "UBER", "PYPL", "SPOT", "SHOP",
    # US Financials
    "V", "MA", "JPM", "BAC", "GS", "MS", "BRK-B", "AXP",
    # US Healthcare
    "UNH", "JNJ", "PFE", "LLY", "ABBV", "MRK", "AMGN", "GILD",
    # US Consumer
    "KO", "MCD", "WMT", "HD", "COST", "NKE", "SBUX",
    # US Industrials
    "BA", "CAT", "LMT", "RTX", "GE", "HON",
    # European (earnings data available via yfinance)
    "SAP.DE", "ALV.DE", "SIE.DE", "BAYN.DE", "BMW.DE",
]

# ── PEAD Core Thresholds ─────────────────────────────────────────────────────

# Minimum EPS surprise % to qualify as a meaningful beat
EPS_SURPRISE_BEAT_MIN    =  5.0   # +5% beat minimum
EPS_SURPRISE_MISS_MAX    = -5.0   # -5% miss minimum
EPS_SURPRISE_MAX_VALID   = 200.0  # cap — above this the % is mathematically meaningless

# Revenue surprise threshold (weaker signal alone, strong in combination)
REV_SURPRISE_BEAT_MIN    =  3.0   # +3% revenue beat

# Underreaction detection: if actual move < predicted move by this margin → PEAD setup
UNDERREACTION_MARGIN_PCT =  2.0   # 2 percentage points

# Minimum history required to fit the surprise→reaction regression
MIN_QUARTERS_FOR_REGRESSION = 4   # at least 4 past earnings events

# How many past quarters to use for the regression
REGRESSION_LOOKBACK_QUARTERS = 12

# ── Entry / Exit Rules ───────────────────────────────────────────────────────

# Don't enter on earnings day itself (volatile, wide spreads)
# Enter 1-3 days after. We use day 2 as the default.
ENTRY_DAYS_AFTER_EARNINGS  = 2

# Primary drift monitoring windows (trading days)
DRIFT_WINDOW_21D  =  21
DRIFT_WINDOW_63D  =  63

# Exit: if stock gives back more than this fraction of post-earnings gain → reassess
TRAILING_STOP_RETRACE = 0.50  # 50% retrace

# ── Setup Quality Scoring ────────────────────────────────────────────────────
# A setup is scored High / Medium / Low based on how many quality criteria pass.

# High: EPS beat + Revenue beat + volume above avg + underreaction confirmed
# Medium: EPS beat + underreaction confirmed (revenue neutral)
# Low: EPS beat only, no underreaction or revenue data

# Volume confirmation: earnings day volume must exceed this multiple of 20d avg
VOLUME_CONFIRMATION_MULTIPLE = 1.2   # 1.2× average

# ── Sector Drift Calibration ─────────────────────────────────────────────────
# From spec: different sectors have different typical drift windows.
# Used to set the expected drift horizon per ticker.

SECTOR_DRIFT_WINDOWS = {
    "Technology":         (45, 90),   # (typical_days, max_days)
    "Healthcare":         (30, 60),
    "Financials":         (21, 45),
    "Consumer Staples":   (21, 30),
    "Energy":             (14, 30),
    "Industrials":        (30, 60),
    "Communication":      (30, 60),
    "Default":            (30, 63),
}

# ── Paths ────────────────────────────────────────────────────────────────────
import os
_base = os.path.join(os.path.dirname(__file__), "data")

PEAD_DB_PATH         = os.path.join(_base, "pead_setups.csv")
PEAD_STATE_PATH      = os.path.join(_base, "pead_state.json")
EARNINGS_CACHE_PATH  = os.path.join(_base, "earnings_cache.csv")
PRICE_CACHE_PATH     = os.path.join(_base, "pead_prices.csv")
REGRESSION_CACHE_PATH = os.path.join(_base, "regression_models.json")

EARNINGS_CACHE_TTL_HRS = 12   # refresh earnings calendar every 12 hours
PRICE_CACHE_TTL_HRS    = 6

# Lookback for price fetching (to compute historical reaction regressions)
PRICE_LOOKBACK_DAYS = 756   # ~3 years to get 12 quarters of earnings history
