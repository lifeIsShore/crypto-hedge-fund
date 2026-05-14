# src/config.py
# ──────────────────────────────────────────────────────────────────────────────
# CENTRAL TICKER CONFIG  (single source of truth)
# ──────────────────────────────────────────────────────────────────────────────
# To add a stock: append to ASSET_UNIVERSE below.  That's it.
# The scheduler, ML pipeline, and LSTM model all import TICKERS from here.
#
# Usage everywhere else:
#   from portfolio.src.config import ASSET_UNIVERSE
#   TICKERS = ASSET_UNIVERSE          # whole universe
#   TICKERS = TRADEABLE_UNIVERSE       # excludes ETFs (for alpha signals)
# ──────────────────────────────────────────────────────────────────────────────

"""
Configuration and Parameters for Trade Republic Quantitative Engine.
Any changes to these parameters must be documented in TUNING-LOG.md
with mathematical or logical justification.
"""

# ==========================================
# 1. ASSET UNIVERSE & MAPPING
# ==========================================
# We prefer Xetra/Frankfurt (.DE) tickers to match Trade Republic EUR pricing.
# If a ticker is US-based, we provide a mapping to its EUR equivalent.
# The ingestion engine will try the PRIMARY first, then the FALLBACK.

# Format: PRIMARY_TICKER: FALLBACK_TICKER (usually the US version)
TICKER_MAPPING = {
    # --- US Big Tech ---
    'APC.DE':  'AAPL',  # Apple
    'MSF.DE':  'MSFT',  # Microsoft
    'AMZ.DE':  'AMZN',  # Amazon
    'NVD.DE':  'NVDA',  # NVIDIA
    'ABE.DE':  'GOOGL', # Alphabet
    'FB2A.DE': 'META',  # Meta
    'TL0.DE':  'TSLA',  # Tesla
    'CAS.DE':  'CRM',   # Salesforce
    'ADB.DE':  'ADBE',  # Adobe
    'NFC.DE':  'NFLX',  # Netflix
    
    # --- US Semiconductors ---
    'AMD.DE':  'AMD',   # AMD
    'INZ.DE':  'INTC',  # Intel
    'QCI.DE':  'QCOM',  # Qualcomm
    'ASQ.DE':  'AMAT',  # Applied Materials
    'MTH.DE':  'MU',    # Micron
    'TNA.DE':  'TXN',   # Texas Instruments
    'ORC.DE':  'ORCL',  # Oracle
    'TSFA.DE': 'TSM',   # TSMC
    
    # --- US Software ---
    '6N0.DE':  'NOW',   # ServiceNow
    '6SN.DE':  'SNOW',  # Snowflake
    '18U.DE':  'UBER',  # Uber
    '2PY.DE':  'PYPL',  # PayPal
    '6SP.DE':  'SPOT',  # Spotify
    '2H1.DE':  'SHOP',  # Shopify
    '1S2.DE':  'FIG',   # Figma (1S2.DE on Xetra)
    
    # --- US Financials ---
    '3V64.DE': 'V',      # Visa
    'M9Z.DE':  'MA',     # Mastercard
    'CMC.DE':  'JPM',    # JPMorgan
    'NCB.DE':  'BAC',    # Bank of America
    'GOS.DE':  'GS',     # Goldman Sachs
    'M9N.DE':  'MS',     # Morgan Stanley
    'BRYN.DE': 'BRK-B',  # Berkshire
    'AEC.DE':  'AXP',    # Amex
    'BLA.DE':  'BLK',    # BlackRock
}

# The active universe used by the engine (Primary Tickers)
ASSET_UNIVERSE = [
    # --- Tech ---
    'APC.DE', 'MSF.DE', 'AMZ.DE', 'NVD.DE', 'ABE.DE', 'FB2A.DE', 'TL0.DE', 
    'CAS.DE', 'ADB.DE', 'NFC.DE', 'AMD.DE', 'INZ.DE', 'QCI.DE', 'ASQ.DE', 
    'MTH.DE', 'TNA.DE', 'ORC.DE', 'TSFA.DE', '6N0.DE', '6SN.DE', '18U.DE', 
    '2PY.DE', '6SP.DE', '2H1.DE', '1S2.DE',
    
    # --- European Blue Chips ---
    'SAP.DE', 'ALV.DE', 'SIE.DE', 'BAYN.DE', 'BMW.DE', 'DTE.DE', 'BAS.DE', 
    'MBG.DE', 'ADS.DE', 'MUV2.DE', 'DBK.DE', 'ENR.DE', 'IFX.DE', 'VOW3.DE', 
    'RWE.DE', 'CON.DE', 'FRE.DE', 'VNA.DE', 'HEN3.DE', 'BEI.DE', 'ZAL.DE', 
    'MTX.DE', 'NDX1.DE', 'ARGX.BR', 'UCB.BR', 'SHL.DE', 'COK.DE', 'AIR.DE',
    'AZN.L', 'SHELL.AS', 'TTE.PA', 'BP.L', 'ASML.AS', 'NOV.DE',

    # --- Financials & Health ---
    '3V64.DE', 'CMC.DE', 'NCB.DE', 'GOS.DE', 'M9N.DE', 'BRYN.DE', 'AEC.DE', 
    'BLA.DE', 'UNH', 'JNJ', 'PFE', 'LLY', 'ABBV', 'MRK', 'AMGN', 'GILD', 
    'TMO', 'BNTX', 'KO', 'MCD', 'WMT', 'HD', 'COST', 'NKE', 'SBUX', 'DIS', 
    'LOW', 'XOM', 'CVX', 'NEE', 'FSLR', 'BA', 'CAT', 'LMT', 'RTX', 'GE', 
    'HON', 'UPS', 'DE', 'RHM.DE', 'ATAI'
]

# List of broad-market ETFs. These are excluded from "Tradeable Pairs" scoring 
# because they structurally have 99% correlation with each other, muddying the signals.
ETF_TICKERS = [
    'EUNL.DE',  # iShares Core MSCI World ETF
    'VUSA.DE',  # Vanguard S&P 500 UCITS ETF
    'VWCE.DE',  # Vanguard FTSE All-World UCITS ETF
    'EXS1.DE',  # iShares Core DAX UCITS ETF
    'EXXT.DE',  # iShares Nasdaq-100 UCITS ETF
    'SPPW.DE',  # SPDR MSCI World UCITS ETF
    'IS3N.DE',  # iShares Core MSCI EM IMI UCITS ETF
    'IUSN.DE',  # iShares MSCI World Small Cap UCITS ETF
    'XDWD.DE',  # Xtrackers MSCI World Swap UCITS ETF
    'ZPRV.DE',  # SPDR MSCI USA Small Cap Value ETF
    'DBXD.DE',  # Xtrackers DAX UCITS ETF
]

ASSET_UNIVERSE.extend(ETF_TICKERS)

# Derived: stocks only (ETFs excluded) — used by alpha / ML models
# that target individual-stock alpha rather than systematic market exposure.
TRADEABLE_UNIVERSE = [t for t in ASSET_UNIVERSE if t not in ETF_TICKERS]

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