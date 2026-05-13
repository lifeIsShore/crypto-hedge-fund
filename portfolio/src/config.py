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
# 1. ASSET UNIVERSE
# ==========================================
# All tickers must use the Xetra/Frankfurt (.DE) suffix to match EUR
# pricing on the Trade Republic app (routed via Lang & Schwarz).
# US-only tickers fall back to NASDAQ/NYSE quotes via yfinance.
# EUR/USD FX conversion is applied automatically by the engine.
ASSET_UNIVERSE = [
    # --- US Big Tech ---
    'APC.DE',   # Apple Inc.
    'MSF.DE',   # Microsoft Corp.
    'AMZN',     # Amazon Inc.
    'NVDA',     # NVIDIA Corp.
    'GOOGL',    # Alphabet Inc. (Class A)
    'META',     # Meta Platforms
    'TSLA',     # Tesla Inc.
    'CRM',      # Salesforce Inc.
    'ADBE',     # Adobe Inc.
    'NFLX',     # Netflix Inc.
    'MSFT',     # Microsoft Corp. (US)

    # --- US Semiconductors & Hardware ---
    'AMD',      # Advanced Micro Devices
    'INTC',     # Intel Corp.
    'QCOM',     # Qualcomm Inc.
    'AMAT',     # Applied Materials
    'MU',       # Micron Technology
    'TXN',      # Texas Instruments
    'ORCL',     # Oracle Corp.
    'TSM',      # Taiwan Semiconductor (TSMC)

    # --- US Software & Internet ---
    'NOW',      # ServiceNow
    'SNOW',     # Snowflake
    'UBER',     # Uber Technologies
    'PYPL',     # PayPal Holdings
    'SPOT',     # Spotify Technology
    'SHOP',     # Shopify Inc.

    # --- European Blue Chips — DAX (.DE) ---
    'SAP.DE',   # SAP SE
    'ALV.DE',   # Allianz SE
    'SIE.DE',   # Siemens AG
    'BAYN.DE',  # Bayer AG
    'BMW.DE',   # BMW AG
    'DTE.DE',   # Deutsche Telekom AG
    'BAS.DE',   # BASF SE
    'MBG.DE',   # Mercedes-Benz Group AG
    'ADS.DE',   # adidas AG
    'MUV2.DE',  # Munich Re (Münchener Rück)
    'DBK.DE',   # Deutsche Bank AG
    'ENR.DE',   # Siemens Energy AG
    'IFX.DE',   # Infineon Technologies AG
    'VOW3.DE',  # Volkswagen AG (Pref.)
    'RWE.DE',   # RWE AG
    'CON.DE',   # Continental AG
    'FRE.DE',   # Fresenius SE
    'VNA.DE',   # Vonovia SE
    'HEN3.DE',  # Henkel AG (Pref.)
    'BEI.DE',   # Beiersdorf AG
    'ZAL.DE',   # Zalando SE
    'MTX.DE',   # MTU Aero Engines AG
    'NDX1.DE',  # Nordex SE
    'ARGX.BR',  # Argenx SE
    'UCB.BR',   # UCB SA
    'SHL.DE',   # Siemens Healthineers AG
    'COK.DE',   # Cancom SE

    # --- European Blue Chips — Other (primary exchange) ---
    'AIR.DE',   # Airbus SE (Xetra)
    'AZN.L',    # AstraZeneca PLC (London — no Xetra data via yfinance)
    'SHELL.AS', # Shell PLC (Amsterdam Euronext)
    'TTE.PA',   # TotalEnergies SE (Paris Euronext)
    'BP.L',     # BP PLC (London — no Xetra data via yfinance)
    'ASML.AS',  # ASML Holding NV (Amsterdam Euronext)
    'NOV.DE',   # Novo Nordisk A/S (Xetra)

    # --- US Financials ---
    'V',        # Visa Inc.
    'MA',       # Mastercard Inc.
    'JPM',      # JPMorgan Chase & Co.
    'BAC',      # Bank of America Corp.
    'GS',       # Goldman Sachs Group
    'MS',       # Morgan Stanley
    'BRK-B',    # Berkshire Hathaway Class B
    'AXP',      # American Express Co.
    'BLK',      # BlackRock Inc.

    # --- US Healthcare ---
    'UNH',      # UnitedHealth Group Inc.
    'JNJ',      # Johnson & Johnson
    'PFE',      # Pfizer Inc.
    'LLY',      # Eli Lilly and Company
    'ABBV',     # AbbVie Inc.
    'MRK',      # Merck & Co. Inc.
    'AMGN',     # Amgen Inc.
    'GILD',     # Gilead Sciences Inc.
    'TMO',      # Thermo Fisher Scientific
    'BNTX',     # BioNTech SE

    # --- US Consumer & Retail ---
    'KO',       # Coca-Cola Co.
    'MCD',      # McDonald's Corp.
    'WMT',      # Walmart Inc.
    'HD',       # Home Depot Inc.
    'COST',     # Costco Wholesale Corp.
    'NKE',      # Nike Inc.
    'SBUX',     # Starbucks Corp.
    'DIS',      # Walt Disney Co.
    'LOW',      # Lowe's Companies Inc.

    # --- US Energy ---
    'XOM',      # ExxonMobil Corp.
    'CVX',      # Chevron Corp.
    'NEE',      # NextEra Energy Inc.
    'FSLR',     # First Solar Inc.

    # --- Psychedelic Biotech ---
    'ATAI',     # AtaiBeckley Inc. (NASDAQ)

    # --- Industrials & Defense ---
    'BA',       # Boeing Co.
    'CAT',      # Caterpillar Inc.
    'LMT',      # Lockheed Martin Corp.
    'RTX',      # RTX Corp. (Raytheon)
    'GE',       # GE Aerospace
    'HON',      # Honeywell International
    'UPS',      # United Parcel Service
    'DE',       # Deere & Company
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