# src/config.py
# ──────────────────────────────────────────────────────────────────────────────
# CENTRAL TICKER CONFIG  (single source of truth)
# ──────────────────────────────────────────────────────────────────────────────
# To add a crypto asset: append to ASSET_UNIVERSE below.  That's it.
# The scheduler, ML pipeline, and LSTM model all import TICKERS from here.
#
# Usage everywhere else:
#   from portfolio.src.config import ASSET_UNIVERSE
#   TICKERS = ASSET_UNIVERSE          # whole universe
# ──────────────────────────────────────────────────────────────────────────────

"""
Configuration and Parameters for Crypto Hedge Fund Engine.
Any changes to these parameters must be documented in TUNING-LOG.md
with mathematical or logical justification.
"""

# ==========================================
# 1. ASSET UNIVERSE & MAPPING
# ==========================================
# We prefer EUR pricing for Binance (e.g. BTC/EUR, ETH/EUR).

TICKER_MAPPING = {
    'BTC/EUR': 'BTC/USDT',
    'ETH/EUR': 'ETH/USDT',
    'SOL/EUR': 'SOL/USDT',
    'BNB/EUR': 'BNB/USDT',
    'XRP/EUR': 'XRP/USDT',
    'DOGE/EUR': 'DOGE/USDT',
    'ADA/EUR': 'ADA/USDT',
    'TRX/EUR': 'TRX/USDT',
    'LINK/EUR': 'LINK/USDT',
    'DOT/EUR': 'DOT/USDT',
}

# --- HUMAN READABLE NAMES ---
TICKER_NAMES = {
    'BTC/EUR': 'Bitcoin',
    'ETH/EUR': 'Ethereum',
    'SOL/EUR': 'Solana',
    'BNB/EUR': 'Binance Coin',
    'XRP/EUR': 'Ripple',
    'DOGE/EUR': 'Dogecoin',
    'ADA/EUR': 'Cardano',
    'TRX/EUR': 'Tron',
    'LINK/EUR': 'Chainlink',
    'DOT/EUR': 'Polkadot',
}

# --- ASSET SECTORS ---
TICKER_SECTORS = {
    'BTC/EUR': 'Layer 1',
    'ETH/EUR': 'Layer 1',
    'SOL/EUR': 'Layer 1',
    'BNB/EUR': 'Exchange Token',
    'XRP/EUR': 'Payments',
    'DOGE/EUR': 'Meme',
    'ADA/EUR': 'Layer 1',
    'TRX/EUR': 'Layer 1',
    'LINK/EUR': 'Oracle',
    'DOT/EUR': 'Layer 0',
}

# The active universe used by the engine
ASSET_UNIVERSE = [
    'BTC/EUR', 'ETH/EUR', 'SOL/EUR', 'BNB/EUR', 'XRP/EUR', 
    'DOGE/EUR', 'ADA/EUR', 'TRX/EUR', 'LINK/EUR', 'DOT/EUR'
]

# Derived: active universe used by alpha / ML models
TRADEABLE_UNIVERSE = ASSET_UNIVERSE.copy()

BENCHMARK_TICKER = 'BTC/EUR'

# ==========================================
# 2. MATHEMATICAL & TIME PARAMETERS
# ==========================================
# 730 days roughly equals 2 years in crypto (365 days/year).
LOOKBACK_DAYS = 730

# Risk-free rate (e.g., short-term US Treasury yield or stablecoin staking yield).
RISK_FREE_RATE = 0.05  # 5.00% p.a.

# 200-day Simple Moving Average for the Regime/Trend Filter.
TREND_FILTER_MA_PERIODS = 200

# ==========================================
# 3. OPTIMIZER CONSTRAINTS
# ==========================================
# Maximum allowable weight for any single asset to prevent concentration risk.
MAX_WEIGHT = 0.35  # 35% (higher for crypto since BTC/ETH dominate)

# ==========================================
# 4. REBALANCING & FEE LOGIC
# ==========================================
# Execute engine checks every 7 days (or continuous)
REBALANCE_FREQUENCY = [7]

# Asymmetric drift
DRIFT_THRESHOLD_BUY = -0.05  # -5% below target
DRIFT_THRESHOLD_SELL = 0.07  # +7% above target

# Binance fee drag
MIN_TRADE_EUR_FLOOR = 10.00
FEE_DRAG_TARGET = 0.001  # 0.1% spot fee

# ==========================================
# 5. DATA SAFETY GATES
# ==========================================
# Halt engine if daily move is insanely large to protect against anomalies
MAX_DAILY_MOVE_ANOMALY = 0.50  # +/- 50% for crypto

# Sanity check: benchmark must be in the universe for beta computation
assert BENCHMARK_TICKER in ASSET_UNIVERSE, (
    f"BENCHMARK_TICKER '{BENCHMARK_TICKER}' is not in ASSET_UNIVERSE. "
    f"Beta computation will fail."
)