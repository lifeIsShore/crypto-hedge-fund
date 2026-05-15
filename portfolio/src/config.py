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
    'ABEA.DE': 'GOOGL', # Alphabet
    'FB2A.DE': 'META',  # Meta
    'TL0.DE':  'TSLA',  # Tesla
    'SFC.DE':  'CRM',   # Salesforce
    'ADB.DE':  'ADBE',  # Adobe
    'NFC.DE':  'NFLX',  # Netflix
    
    # --- US Semiconductors ---
    'AMD.DE':  'AMD',   # AMD
    '1IN.DE':  'INTC',  # Intel
    'QCI.DE':  'QCOM',  # Qualcomm
    'AP2.DE':  'AMAT',  # Applied Materials
    'MTU.DE':  'MU',    # Micron
    'TII.DE':  'TXN',   # Texas Instruments
    'ORC.DE':  'ORCL',  # Oracle
    'TSM.DE':  'TSM',   # TSMC
    'KLA.DE':  'KLAC',  # KLA Corp
    
    # --- US Software ---
    'NOW.DE':  'NOW',   # ServiceNow
    'SNW.DE':  'SNOW',  # Snowflake
    'UT8.DE':  'UBER',  # Uber
    'PYPL.DE': 'PYPL',  # PayPal
    '639.DE':  'SPOT',  # Spotify
    'SHOP.DE': 'SHOP',  # Shopify
    '1S2.DE':  'FIG',   # Figma
    
    # --- US Financials ---
    '3V64.DE': 'V',      # Visa
    'M9Z.DE':  'MA',     # Mastercard
    'CMC.DE':  'JPM',    # JPMorgan
    'NCB.DE':  'BAC',    # Bank of America
    'GOS.DE':  'GS',     # Goldman Sachs
    'DWD.DE':  'MS',     # Morgan Stanley
    'BRYN.DE': 'BRK-B',  # Berkshire
    'AXP.DE':  'AXP',    # Amex
    'BLQA.DE': 'BLK',    # BlackRock

    # --- New Energy & Mining (US fallback) ---
    'GEV.DE':  'GEV',   # GE Vernova
    'CJJ.DE':  'CCJ',   # Cameco
    'CEG.DE':  'CEG',   # Constellation
    'NUS.DE':  'SMR',   # NuScale
    'OKL.DE':  'OKLO',  # Oklo
    'REP.DE':  'REPYY',   # Repsol
    'ENB.DE':  'ENB',     # Enbridge
    'EGI.DE':  'ENGIY',   # Engie
    'BLM.DE':  'BE',      # Bloom Energy
    'BRP.DE':  'BEP',     # Brookfield
    'RIO.DE':  'RIO',   # Rio Tinto
    'ERO.DE':  'ERO',   # Ero Copper
    'FPM.DE':  'FCX',   # Freeport
    'ALB.DE':  'ALB',   # Albemarle
    'MNR.DE':  'MIN',   # Mineral Resources
    'C1E.DE':  'LEU',   # Centrus Energy
    'VRT.DE':  'VRTX',  # Vertex
    'AXS.DE':  'AXSM',  # Axsome
}

# --- HUMAN READABLE NAMES ---
# --- HUMAN READABLE NAMES ---
TICKER_NAMES = {
    'APC.DE': 'Apple Inc.', 'AAPL': 'Apple Inc.',
    'MSF.DE': 'Microsoft Corporation', 'MSFT': 'Microsoft Corporation',
    'AMZ.DE': 'Amazon.com, Inc.', 'AMZN': 'Amazon.com, Inc.',
    'NVD.DE': 'NVIDIA Corporation', 'NVDA': 'NVIDIA Corporation',
    'ABEA.DE': 'Alphabet Inc.', 'GOOGL': 'Alphabet Inc.',
    'FB2A.DE': 'Meta Platforms, Inc.', 'META': 'Meta Platforms, Inc.',
    'TL0.DE': 'Tesla, Inc.', 'TSLA': 'Tesla, Inc.',
    'SFC.DE': 'Salesforce, Inc.', 'CRM': 'Salesforce, Inc.',
    'ADB.DE': 'Adobe Inc.', 'ADBE': 'Adobe Inc.',
    'NFC.DE': 'Netflix, Inc.', 'NFLX': 'Netflix, Inc.',
    'AMD.DE': 'Advanced Micro Devices, Inc.', 'AMD': 'Advanced Micro Devices, Inc.',
    '1IN.DE': 'Intel Corporation', 'INTC': 'Intel Corporation',
    'QCI.DE': 'QUALCOMM Incorporated', 'QCOM': 'QUALCOMM Incorporated',
    'AP2.DE': 'Applied Materials, Inc.', 'AMAT': 'Applied Materials, Inc.',
    'MTU.DE': 'Micron Technology, Inc.', 'MU': 'Micron Technology, Inc.',
    'TII.DE': 'Texas Instruments Incorporated', 'TXN': 'Texas Instruments Incorporated',
    'ORC.DE': 'Oracle Corporation', 'ORCL': 'Oracle Corporation',
    'TSM.DE': 'Taiwan Semiconductor Manufacturing Co.', 'TSM': 'Taiwan Semiconductor Manufacturing Co.',
    'KLA.DE': 'KLA Corporation', 'KLAC': 'KLA Corporation',
    'NOW.DE': 'ServiceNow, Inc.', 'NOW': 'ServiceNow, Inc.',
    'SNW.DE': 'Snowflake Inc.', 'SNOW': 'Snowflake Inc.',
    'UT8.DE': 'Uber Technologies, Inc.', 'UBER': 'Uber Technologies, Inc.',
    'PYPL.DE': 'PayPal Holdings, Inc.', 'PYPL': 'PayPal Holdings, Inc.',
    '639.DE': 'Spotify Technology S.A.', 'SPOT': 'Spotify Technology S.A.',
    'SHOP.DE': 'Shopify Inc.', 'SHOP': 'Shopify Inc.',
    '1S2.DE': 'Figma', 'FIG': 'Figma',
    '3V64.DE': 'Visa Inc.', 'V': 'Visa Inc.',
    'M9Z.DE': 'Mastercard Incorporated', 'MA': 'Mastercard Incorporated',
    'CMC.DE': 'JPMorgan Chase & Co.', 'JPM': 'JPMorgan Chase & Co.',
    'NCB.DE': 'Bank of America Corporation', 'BAC': 'Bank of America Corporation',
    'GOS.DE': 'The Goldman Sachs Group, Inc.', 'GS': 'The Goldman Sachs Group, Inc.',
    'DWD.DE': 'Morgan Stanley', 'MS': 'Morgan Stanley',
    'BRYN.DE': 'Berkshire Hathaway Inc.', 'BRK-B': 'Berkshire Hathaway Inc.',
    'AXP.DE': 'American Express Company', 'AXP': 'American Express Company',
    'BLQA.DE': 'BlackRock, Inc.', 'BLK': 'BlackRock, Inc.',
    'SAP.DE': 'SAP SE', 'ALV.DE': 'Allianz SE', 'SIE.DE': 'Siemens AG',
    'BAYN.DE': 'Bayer AG', 'BMW.DE': 'BMW AG', 'DTE.DE': 'Deutsche Telekom AG',
    'BAS.DE': 'BASF SE', 'MBG.DE': 'Mercedes-Benz Group AG', 'ADS.DE': 'Adidas AG',
    'MUV2.DE': 'Munich Re', 'DBK.DE': 'Deutsche Bank AG', 'ENR.DE': 'Siemens Energy AG',
    'IFX.DE': 'Infineon Technologies AG', 'VOW3.DE': 'Volkswagen AG', 'RWE.DE': 'RWE AG',
    'CON.DE': 'Continental AG', 'FRE.DE': 'Fresenius SE & Co. KGaA', 'VNA.DE': 'Vonovia SE',
    'HEN3.DE': 'Henkel AG & Co. KGaA', 'BEI.DE': 'Beiersdorf AG', 'ZAL.DE': 'Zalando SE',
    'MTX.DE': 'MTU Aero Engines AG', 'NDX1.DE': 'Nordex SE',
    'ARGX.BR': 'argenx SE',
    'UCB.BR': 'UCB S.A.',
    'SHL.DE': 'Siemens Healthineers AG', 'COK.DE': 'CANCOM SE', 'AIR.DE': 'Airbus SE',
    'AZN.L': 'AstraZeneca PLC', 'SHELL.AS': 'Shell PLC', 'TTE.PA': 'TotalEnergies SE',
    'BP.L': 'BP p.l.c.', 'ASML.AS': 'ASML Holding N.V.',
    'NOV.DE': 'Novartis AG', 'NVS': 'Novartis AG', 'S92.DE': 'SMA Solar Technology AG',
    'UNH': 'UnitedHealth Group Incorporated', 'JNJ': 'Johnson & Johnson',
    'PFE': 'Pfizer Inc.', 'LLY': 'Eli Lilly and Company', 'ABBV': 'AbbVie Inc.',
    'MRK': 'Merck & Co., Inc.', 'AMGN': 'Amgen Inc.', 'GILD': 'Gilead Sciences, Inc.',
    'TMO': 'Thermo Fisher Scientific Inc.', 'BNTX': 'BioNTech SE',
    'VRTX': 'Vertex Pharmaceuticals Incorporated', 'VRT.DE': 'Vertex Pharmaceuticals Incorporated',
    'AXSM': 'Axsome Therapeutics, Inc.', 'AXS.DE': 'Axsome Therapeutics, Inc.',
    'ATAI': 'ATAI Life Sciences N.V.',
    'XOM': 'Exxon Mobil Corporation', 'CVX': 'Chevron Corporation',
    'NEE': 'NextEra Energy, Inc.', 'FSLR': 'First Solar, Inc.',
    'GEV': 'GE Vernova Inc.', 'GEV.DE': 'GE Vernova Inc.',
    'CCJ': 'Cameco Corporation', 'CJJ.DE': 'Cameco Corporation',
    'CEG': 'Constellation Energy Corporation', 'CEG.DE': 'Constellation Energy Corporation',
    'SMR': 'NuScale Power Corporation', 'NUS.DE': 'NuScale Power Corporation',
    'OKLO': 'Oklo Inc.', 'OKL.DE': 'Oklo Inc.',
    'REP': 'Repsol S.A.', 'REP.DE': 'Repsol S.A.',
    'ENB': 'Enbridge Inc.', 'ENB.DE': 'Enbridge Inc.',
    'ENGI': 'ENGIE S.A.', 'EGI.DE': 'ENGIE S.A.',
    'BE': 'Bloom Energy Corporation', 'BLM.DE': 'Bloom Energy Corporation',
    'BEP': 'Brookfield Renewable Partners L.P.', 'BRP.DE': 'Brookfield Renewable Partners L.P.',
    'RIO': 'Rio Tinto Group', 'RIO.DE': 'Rio Tinto Group',
    'ERO': 'Ero Copper Corp.', 'ERO.DE': 'Ero Copper Corp.',
    'FCX': 'Freeport-McMoRan Inc.', 'FPM.DE': 'Freeport-McMoRan Inc.',
    'ALB': 'Albemarle Corporation', 'ALB.DE': 'Albemarle Corporation',
    'MIN': 'Mineral Resources Limited', 'MNR.DE': 'Mineral Resources Limited',
    'LEU': 'Centrus Energy Corp.', 'C1E.DE': 'Centrus Energy Corp.',
    'BA': 'The Boeing Company', 'CAT': 'Caterpillar Inc.',
    'LMT': 'Lockheed Martin Corporation', 'RTX': 'RTX Corporation',
    'GE': 'General Electric Company', 'HON': 'Honeywell International Inc.',
    'UPS': 'United Parcel Service, Inc.', 'DE': 'Deere & Company',
    'RHM.DE': 'Rheinmetall AG', 'KO': 'The Coca-Cola Company',
    'MCD': 'McDonald\'s Corporation', 'WMT': 'Walmart Inc.',
    'HD': 'The Home Depot, Inc.', 'COST': 'Costco Wholesale Corporation',
    'NKE': 'NIKE, Inc.', 'SBUX': 'Starbucks Corporation',
    'DIS': 'The Walt Disney Company', 'LOW': 'Lowe\'s Companies, Inc.',
    'EUNL.DE': 'iShares Core MSCI World', 'VUSA.DE': 'Vanguard S&P 500',
    'VWCE.DE': 'Vanguard FTSE All-World', 'EXS1.DE': 'iShares Core DAX',
    'EXXT.DE': 'iShares Nasdaq-100', 'SPPW.DE': 'SPDR MSCI World',
    'IS3N.DE': 'iShares Core EM IMI', 'IUSN.DE': 'iShares MSCI World Small Cap',
    'XDWD.DE': 'Xtrackers MSCI World Swap', 'ZPRV.DE': 'SPDR MSCI USA Small Cap Value',
    'DBXD.DE': 'Xtrackers DAX', 'IS04.DE': 'iShares MSCI World', 'EGLN.DE': 'iShares Physical Gold',
}

# --- ASSET SECTORS ---
TICKER_SECTORS = {
    'APC.DE': 'Technology', 'AAPL': 'Technology',
    'MSF.DE': 'Technology', 'MSFT': 'Technology',
    'AMZ.DE': 'Ecommerce', 'AMZN': 'Ecommerce',
    'NVD.DE': 'Semiconductors', 'NVDA': 'Semiconductors',
    'ABE.DE': 'Technology', 'GOOGL': 'Technology',
    'FB2A.DE': 'Technology', 'META': 'Technology',
    'TL0.DE': 'Automotive', 'TSLA': 'Automotive',
    'CAS.DE': 'Software', 'CRM': 'Software',
    'ADB.DE': 'Software', 'ADBE': 'Software',
    'NFC.DE': 'Entertainment', 'NFLX': 'Entertainment',
    'AMD.DE': 'Semiconductors', 'AMD': 'Semiconductors',
    'INZ.DE': 'Semiconductors', 'INTC': 'Semiconductors',
    'QCI.DE': 'Semiconductors', 'QCOM': 'Semiconductors',
    'ASQ.DE': 'Semiconductors', 'AMAT': 'Semiconductors',
    'MTH.DE': 'Semiconductors', 'MU': 'Semiconductors',
    'TNA.DE': 'Semiconductors', 'TXN': 'Semiconductors',
    'ORC.DE': 'Software', 'ORCL': 'Software',
    'TSFA.DE': 'Semiconductors', 'TSM': 'Semiconductors',
    'KLA.DE': 'Semiconductors', 'KLAC': 'Semiconductors',
    '6N0.DE': 'Software', 'NOW': 'Software',
    '6SN.DE': 'Software', 'SNOW': 'Software',
    '18U.DE': 'Transportation', 'UBER': 'Transportation',
    '2PY.DE': 'Financials', 'PYPL': 'Financials',
    '6SP.DE': 'Entertainment', 'SPOT': 'Entertainment',
    '2H1.DE': 'Ecommerce', 'SHOP': 'Ecommerce',
    '1S2.DE': 'Software', 'FIG': 'Software',
    '3V64.DE': 'Financials', 'V': 'Financials',
    'M9Z.DE': 'Financials', 'MA': 'Financials',
    'CMC.DE': 'Financials', 'JPM': 'Financials',
    'NCB.DE': 'Financials', 'BAC': 'Financials',
    'GOS.DE': 'Financials', 'GS': 'Financials',
    'M9N.DE': 'Financials', 'MS': 'Financials',
    'BRYN.DE': 'Financials', 'BRK-B': 'Financials',
    'AEC.DE': 'Financials', 'AXP': 'Financials',
    'BLA.DE': 'Financials', 'BLK': 'Financials',
    'SAP.DE': 'Software', 'ALV.DE': 'Insurance', 'SIE.DE': 'Industrial',
    'BAYN.DE': 'Healthcare', 'BMW.DE': 'Automotive', 'DTE.DE': 'Telecom',
    'BAS.DE': 'Chemicals', 'MBG.DE': 'Automotive', 'ADS.DE': 'Consumer',
    'MUV2.DE': 'Insurance', 'DBK.DE': 'Financials', 'ENR.DE': 'Energy',
    'IFX.DE': 'Semiconductors', 'VOW3.DE': 'Automotive', 'RWE.DE': 'Utilities',
    'CON.DE': 'Automotive', 'FRE.DE': 'Healthcare', 'VNA.DE': 'Real Estate',
    'HEN3.DE': 'Consumer', 'BEI.DE': 'Consumer', 'ZAL.DE': 'Ecommerce',
    'MTX.DE': 'Industrial', 'NDX1.DE': 'Renewables',
    'ARGX.BR': 'Biotech', 'ARGX.DE': 'Biotech', 'UCB.BR': 'Pharma', 'UCB.DE': 'Pharma',
    'SHL.DE': 'Healthcare', 'COK.DE': 'Technology', 'AIR.DE': 'Industrial',
    'AZN.L': 'Pharma', 'SHELL.AS': 'Energy', 'TTE.PA': 'Energy', 'BP.L': 'Energy',
    'ASML.AS': 'Semiconductors', 'ASML.NA': 'Semiconductors', 'NOV.DE': 'Pharma',
    'NVS': 'Pharma', 'S92G.DE': 'Renewables', 'UNH': 'Healthcare', 'JNJ': 'Healthcare',
    'PFE': 'Healthcare', 'LLY': 'Healthcare', 'ABBV': 'Healthcare', 'MRK': 'Healthcare',
    'AMGN': 'Healthcare', 'GILD': 'Biotech', 'TMO': 'Healthcare', 'BNTX': 'Biotech',
    'VRTX': 'Biotech', 'VRT.DE': 'Biotech',
    'AXSM': 'Biotech', 'AXS.DE': 'Biotech',
    'ATAI': 'Healthcare', 'XOM': 'Energy', 'CVX': 'Energy', 'NEE': 'Utilities',
    'FSLR': 'Renewables', 'GEV': 'Energy', 'GEV.DE': 'Energy',
    'CCJ': 'Energy', 'CJJ.DE': 'Energy',
    'CEG': 'Energy', 'CEG.DE': 'Energy',
    'SMR': 'Energy', 'NUS.DE': 'Energy',
    'OKLO': 'Energy', 'OKL.DE': 'Energy',
    'REP': 'Energy', 'REP.DE': 'Energy',
    'ENB': 'Energy', 'ENB.DE': 'Energy',
    'ENGI': 'Energy', 'EGI.DE': 'Energy',
    'BE': 'Energy', 'BLM.DE': 'Energy',
    'BEP': 'Energy', 'BRP.DE': 'Energy',
    'RIO': 'Mining', 'RIO.DE': 'Mining',
    'ERO': 'Mining', 'ERO.DE': 'Mining',
    'FCX': 'Mining', 'FPM.DE': 'Mining',
    'ALB': 'Mining', 'ALB.DE': 'Mining',
    'MIN': 'Mining', 'MNR.DE': 'Mining',
    'LEU': 'Energy', 'C1E.DE': 'Energy',
    'BA': 'Industrial', 'CAT': 'Industrial', 'LMT': 'Industrial',
    'RTX': 'Industrial', 'GE': 'Industrial', 'HON': 'Industrial',
    'UPS': 'Transportation', 'DE': 'Industrial', 'RHM.DE': 'Industrial',
    'KO': 'Consumer', 'MCD': 'Consumer', 'WMT': 'Consumer', 'HD': 'Consumer',
    'COST': 'Consumer', 'NKE': 'Consumer', 'SBUX': 'Consumer', 'DIS': 'Entertainment',
    'LOW': 'Consumer', 'EUNL.DE': 'ETF', 'VUSA.DE': 'ETF', 'VWCE.DE': 'ETF',
    'EXS1.DE': 'ETF', 'EXXT.DE': 'ETF', 'SPPW.DE': 'ETF', 'IS3N.DE': 'ETF',
    'IUSN.DE': 'ETF', 'XDWD.DE': 'ETF', 'ZPRV.DE': 'ETF', 'DBXD.DE': 'ETF',
}

# The active universe used by the engine (Primary Tickers)
ASSET_UNIVERSE = [
    # --- Tech & Semiconductors ---
    'APC.DE', 'MSF.DE', 'AMZ.DE', 'NVD.DE', 'ABEA.DE', 'FB2A.DE', 'TL0.DE', 
    'SFC.DE', 'ADB.DE', 'NFC.DE', 'AMD.DE', '1IN.DE', 'QCI.DE', 'AP2.DE', 
    'MTU.DE', 'TII.DE', 'ORC.DE', 'TSM.DE', 'KLAC', 'NOW.DE', 'SNW.DE', 
    'UT8.DE', 'PYPL.DE', '639.DE', 'SHOP.DE', 'FIG',
    
    # --- European Blue Chips ---
    'SAP.DE', 'ALV.DE', 'SIE.DE', 'BAYN.DE', 'BMW.DE', 'DTE.DE', 'BAS.DE', 
    'MBG.DE', 'ADS.DE', 'MUV2.DE', 'DBK.DE', 'ENR.DE', 'IFX.DE', 'VOW3.DE', 
    'RWE.DE', 'CON.DE', 'FRE.DE', 'VNA.DE', 'HEN3.DE', 'BEI.DE', 'ZAL.DE', 
    'MTX.DE', 'NDX1.DE', 'ARGX.BR', 'UCB.BR', 'SHL.DE', 
    'COK.DE', 'AIR.DE', 'AZN.L', 'SHELL.AS', 'TTE.PA', 'BP.L', 'ASML.AS', 
    'NOV.DE', 'S92.DE',

    # --- Financials & Consumer ---
    '3V64.DE', 'CMC.DE', 'NCB.DE', 'GOS.DE', 'DWD.DE', 'BRYN.DE', 'AXP.DE', 
    'BLQA.DE', 'KO', 'MCD', 'WMT', 'HD', 'COST', 'NKE', 'SBUX', 'DIS', 'LOW',
    
    # --- Healthcare & Biotech ---
    'UNH', 'JNJ', 'PFE', 'LLY', 'ABBV', 'MRK', 'AMGN', 'GILD', 'TMO', 'BNTX', 
    'VRTX', 'AXSM', 'NVS', 'ATAI',

    # --- Energy, Mining & Industrials ---
    'XOM', 'CVX', 'NEE', 'FSLR', 'GEV', 'CCJ', 'CEG', 'SMR', 'OKLO', 'REP.DE', 
    'ENB.DE', 'EGI.DE', 'BLM.DE', 'BEP', 'RIO', 'ERO', 'FCX', 'ALB', 'MIN', 'C1E.DE',
    'BA', 'CAT', 'LMT', 'RTX', 'GE', 'HON', 'UPS', 'DE', 'RHM.DE'
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
MAX_DAILY_MOVE_ANOMALY = 0.21  # +/- 21%