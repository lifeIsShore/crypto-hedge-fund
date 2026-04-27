# src/config.py

"""
Configuration and Parameters for Trade Republic Quantitative Engine.
Any changes to these parameters must be documented in TUNING-LOG.md
with mathematical or logical justification.
"""

# ==========================================
# 1. ASSET UNIVERSE
# ==========================================
# All tickers must use the Xetra/Frankfurt (.DE) suffix to match EUR 
# pricing on the Trade Republic app (routed via Lang & Schwarz).
ASSET_UNIVERSE = [
    'APC.DE',   # Apple Inc.
    'MSF.DE',   # Microsoft Corp.
    'SAP.DE',   # SAP SE
    'ALV.DE',   # Allianz SE
    'MOH.DE',   # LVMH
    'EUNL.DE',  # iShares Core MSCI World ETF
    'AMZN',     # Amazon Inc.
    'TSLA'      # Tesla Inc.
]

BENCHMARK_TICKER = 'EUNL.DE'

# ==========================================
# 2. MATHEMATICAL & TIME PARAMETERS
# ==========================================
# 504 trading days roughly equals 2 years.
LOOKBACK_DAYS = 504

# Current Trade Republic interest rate on uninvested cash.
RISK_FREE_RATE = 0.02  # 2.00% p.a.

# 200-day Simple Moving Average for the Regime/Trend Filter.
TREND_FILTER_MA_PERIODS = 200

# ==========================================
# 3. OPTIMIZER CONSTRAINTS
# ==========================================
# Maximum allowable weight for any single asset to prevent concentration risk.
MAX_WEIGHT = 0.25  # 25%

# ==========================================
# 4. REBALANCING & FEE LOGIC
# ==========================================
# Execute engine checks on the 1st and 3rd Friday of every month.
REBALANCE_FREQUENCY = [1, 3]

# Asymmetric drift to minimize German capital gains tax (Abgeltungsteuer).
# Tighter to buy losers, looser to let winners run.
DRIFT_THRESHOLD_BUY = -0.05  # -5% below target
DRIFT_THRESHOLD_SELL = 0.07  # +7% above target

# Dynamic Minimum Trade Size to cap the €1 TR fee drag at <= 4%.
# Engine will use MAX(MIN_TRADE_EUR_FLOOR, portfolio_value * FEE_DRAG_TARGET)
MIN_TRADE_EUR_FLOOR = 25.00
FEE_DRAG_TARGET = 0.005  # 0.5% of total portfolio value

# ==========================================
# 5. DATA SAFETY GATES
# ==========================================
# Halt engine if yfinance reports a daily move greater than this threshold 
# (protects against unadjusted stock splits).
MAX_DAILY_MOVE_ANOMALY = 0.30  # +/- 30%