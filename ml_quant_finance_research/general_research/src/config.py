# research/src/config.py
#
# Imports the production asset universe and base parameters from the
# portfolio layer, then adds research-specific parameters on top.
# Never modify portfolio/src/config.py from here — read only.

import sys
import os
import importlib.util

# Use dynamic loading to import from the portfolio layer without
# causing sys.path conflicts or circular imports (since both are src.config).
_portfolio_config_path = os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..', '..', '..', 'portfolio', 'src', 'config.py')
)
_spec = importlib.util.spec_from_file_location("portfolio_config", _portfolio_config_path)
_portfolio_config = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_portfolio_config)

# Proxy all variables from portfolio config to this module
for _k, _v in _portfolio_config.__dict__.items():
    if not _k.startswith('_'):
        globals()[_k] = _v

# ==========================================
# CORRELATION ENGINE PARAMETERS
# ==========================================
# Rolling windows (trading days) used throughout 01_correlation_engine.ipynb
ROLLING_WINDOWS = [30, 90, 180]

# A pair is flagged as "breaking down" when the spread between its
# 30-day and 90-day rolling correlation exceeds this threshold.
CORRELATION_BREAKDOWN_THRESHOLD = 0.20

# Minimum absolute correlation to include a pair in tradeability scoring.
# Pairs below this are noise, not signal.
MIN_CORRELATION_THRESHOLD = 0.40

# A pair's stability score is the std of its 90-day rolling correlation
# over the full lookback. Lower = more stable. Flag pairs above this.
MAX_STABILITY_STD = 0.15

# How many top pairs to export in the correlation_state.json summary.
TOP_PAIRS_N = 20

# ==========================================
# REGIME DETECTION PARAMETERS
# ==========================================
# Lookback for realised volatility used in regime classification.
REGIME_VOL_LOOKBACK = 21        # ~1 month

# Volatility thresholds for regime boundaries (annualised).
REGIME_VOL_LOW    = 0.12        # < 12% ann. vol  → low stress
REGIME_VOL_HIGH   = 0.22        # > 22% ann. vol  → high stress

# Correlation compression: average pairwise correlation of held tickers.
# When it rises sharply, assets are "all moving together" — a stress signal.
REGIME_CORR_COMPRESSION_HIGH = 0.65

# ==========================================
# FACTOR MODEL PARAMETERS
# ==========================================
# Lookback (trading days) for Fama-French OLS regressions.
FACTOR_MODEL_LOOKBACK = 252     # 1 year

# Minimum t-statistic for alpha to be considered statistically significant.
ALPHA_TSTAT_THRESHOLD = 2.0

# ==========================================
# REGIME DETECTION PARAMETERS (extended)
# ==========================================
# Lookback window for regime probability estimation.
# "What fraction of the last 60 days were in each regime?"
REGIME_PROB_LOOKBACK = 60

# ==========================================
# LEAD-LAG PARAMETERS
# ==========================================
# Maximum lag (days) to test in cross-correlation and Granger tests.
MAX_LAG_DAYS = 5

# Minimum Granger causality F-stat p-value to flag a lead-lag relationship.
GRANGER_PVALUE_THRESHOLD = 0.05

# ==========================================
# OUTPUT PATHS
# ==========================================
OUTPUTS_DIR = os.path.join(os.path.dirname(__file__), '..', 'outputs')

OUTPUT_CORRELATION = os.path.join(OUTPUTS_DIR, 'correlation_state.json')
OUTPUT_REGIME      = os.path.join(OUTPUTS_DIR, 'regime_state.json')
OUTPUT_FACTOR      = os.path.join(OUTPUTS_DIR, 'factor_state.json')
