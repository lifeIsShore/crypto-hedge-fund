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

    # --- Financials & Consumer (Converted) ---
    'CCC3.DE': 'KO',     # Coca-Cola
    'MDO.DE':  'MCD',    # McDonald's
    'WMT.DE':  'WMT',    # Walmart
    'HDI.DE':  'HD',     # Home Depot
    'CTO.DE':  'COST',   # Costco
    'NKE.DE':  'NKE',    # Nike
    'SRB.DE':  'SBUX',   # Starbucks
    'WDP.DE':  'DIS',    # Disney
    'LWE.DE':  'LOW',    # Lowe's

    # --- Healthcare & Biotech (Converted) ---
    'UNH.DE':  'UNH',    # UnitedHealth
    'JNJ.DE':  'JNJ',    # Johnson & Johnson
    'PFE.DE':  'PFE',    # Pfizer
    'LLY.DE':  'LLY',    # Eli Lilly
    '4AB.DE':  'ABBV',   # AbbVie
    '6MK.DE':  'MRK',    # Merck
    'AMG.DE':  'AMGN',   # Amgen
    'GIS.DE':  'GILD',   # Gilead
    'TMO.DE':  'TMO',    # Thermo Fisher
    '22UA.DE': 'BNTX',   # BioNTech
    '4YC.DE':  'ATAI',   # ATAI Life Sciences
    
    # --- Industrials (Converted) ---
    'BCO.DE':  'BA',     # Boeing
    'CAT1.DE': 'CAT',    # Caterpillar
    'LOM.DE':  'LMT',    # Lockheed Martin
    'RTX.DE':  'RTX',    # RTX Corp
    'GEC.DE':  'GE',     # General Electric
    'HON.DE':  'HON',    # Honeywell
    'UPB.DE':  'UPS',    # UPS
    'DCO.DE':  'DE',     # Deere

    # --- European Blue Chips (Converted to .DE for EUR) ---
    'ASME.DE': 'ASML',   # ASML
    'R6C0.DE': 'SHEL',   # Shell
    'TOTB.DE': 'TTE',    # TotalEnergies
    'BPE5.DE': 'BP',     # BP
    'ZEGB.DE': 'AZN',    # AstraZeneca
    'ARGX.DE': 'ARGX',   # argenx
    'UCB.DE':  'UCBJF',  # UCB
    'NOV.DE':  'NVS',    # Novartis

    # --- New Energy & Mining (US fallback) ---
    'XONA.DE': 'XOM',    # Exxon Mobil
    'CHV.DE':  'CVX',    # Chevron
    'NPL.DE':  'NEE',    # NextEra
    'F3A.DE':  'FSLR',   # First Solar
    'GEV.DE':  'GEV',    # GE Vernova
    'CJJ.DE':  'CCJ',    # Cameco
    'CEG.DE':  'CEG',    # Constellation
    'NUS.DE':  'SMR',    # NuScale
    'OKL.DE':  'OKLO',   # Oklo
    'REP.DE':  'REPYY',  # Repsol
    'ENB.DE':  'ENB',    # Enbridge
    'EGI.DE':  'ENGIY',  # Engie
    'BLM.DE':  'BE',     # Bloom Energy
    'BRP.DE':  'BEP',    # Brookfield
    'RIO.DE':  'RIO',    # Rio Tinto
    'ERO.DE':  'ERO',    # Ero Copper
    'FPM.DE':  'FCX',    # Freeport
    'ALB.DE':  'ALB',    # Albemarle
    'MNR.DE':  'MIN',    # Mineral Resources
    'C1E.DE':  'LEU',    # Centrus Energy
    'VO51.DE': 'UUUU',   # Energy Fuels
    'U6Z.DE':  'UEC',    # Uranium Energy
    'VRT.DE':  'VRTX',   # Vertex
    'AXS.DE':  'AXSM',   # Axsome
    'PPFD.SG': 'SLV',    # Silver
}

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
    'ARGX.DE': 'argenx SE', 'ARGX': 'argenx SE',
    'UCB.DE': 'UCB S.A.', 'UCBJF': 'UCB S.A.',
    'SHL.DE': 'Siemens Healthineers AG', 'COK.DE': 'CANCOM SE', 'AIR.DE': 'Airbus SE',
    'ZEGB.DE': 'AstraZeneca PLC', 'AZN': 'AstraZeneca PLC', 
    'R6C0.DE': 'Shell PLC', 'SHEL': 'Shell PLC', 
    'TOTB.DE': 'TotalEnergies SE', 'TTE': 'TotalEnergies SE',
    'BPE5.DE': 'BP p.l.c.', 'BP': 'BP p.l.c.', 
    'ASME.DE': 'ASML Holding N.V.', 'ASML': 'ASML Holding N.V.',
    'NOV.DE': 'Novartis AG', 'NVS': 'Novartis AG', 'S92.DE': 'SMA Solar Technology AG',
    'UNH.DE': 'UnitedHealth Group', 'UNH': 'UnitedHealth Group', 
    'JNJ.DE': 'Johnson & Johnson', 'JNJ': 'Johnson & Johnson',
    'PFE.DE': 'Pfizer Inc.', 'PFE': 'Pfizer Inc.', 
    'LLY.DE': 'Eli Lilly', 'LLY': 'Eli Lilly', 
    '4AB.DE': 'AbbVie Inc.', 'ABBV': 'AbbVie Inc.',
    '6MK.DE': 'Merck & Co.', 'MRK': 'Merck & Co.', 
    'AMG.DE': 'Amgen Inc.', 'AMGN': 'Amgen Inc.', 
    'GIS.DE': 'Gilead Sciences', 'GILD': 'Gilead Sciences',
    'TMO.DE': 'Thermo Fisher', 'TMO': 'Thermo Fisher', 
    '22UA.DE': 'BioNTech SE', 'BNTX': 'BioNTech SE',
    'VRTX': 'Vertex Pharmaceuticals', 'VRT.DE': 'Vertex Pharmaceuticals',
    'AXSM': 'Axsome Therapeutics', 'AXS.DE': 'Axsome Therapeutics',
    '4YC.DE': 'ATAI Life Sciences', 'ATAI': 'ATAI Life Sciences',
    'XONA.DE': 'Exxon Mobil', 'XOM': 'Exxon Mobil', 
    'CHV.DE': 'Chevron', 'CVX': 'Chevron',
    'NPL.DE': 'NextEra Energy', 'NEE': 'NextEra Energy', 
    'F3A.DE': 'First Solar', 'FSLR': 'First Solar',
    'GEV': 'GE Vernova Inc.', 'GEV.DE': 'GE Vernova Inc.',
    'CCJ': 'Cameco Corporation', 'CJJ.DE': 'Cameco Corporation',
    'CEG': 'Constellation Energy Corporation', 'CEG.DE': 'Constellation Energy Corporation',
    'SMR': 'NuScale Power Corporation', 'NUS.DE': 'NuScale Power Corporation',
    'OKLO': 'Oklo Inc.', 'OKL.DE': 'Oklo Inc.',
    'REP': 'Repsol S.A.', 'REP.DE': 'Repsol S.A.',
    'ENB': 'Enbridge Inc.', 'ENB.DE': 'Enbridge Inc.',
    'ENGI': 'ENGIE S.A.', 'EGI.DE': 'ENGIE S.A.',
    'BE': 'Bloom Energy Corporation', 'BLM.DE': 'Bloom Energy Corporation',
    'BRP.DE': 'Brookfield Renewable', 'BEP': 'Brookfield Renewable',
    'RIO.DE': 'Rio Tinto Group', 'RIO': 'Rio Tinto Group',
    'ERO.DE': 'Ero Copper Corp.', 'ERO': 'Ero Copper Corp.',
    'FPM.DE': 'Freeport-McMoRan', 'FCX': 'Freeport-McMoRan',
    'ALB.DE': 'Albemarle', 'ALB': 'Albemarle',
    'MNR.DE': 'Mineral Resources', 'MIN': 'Mineral Resources',
    'LEU': 'Centrus Energy Corp.', 'C1E.DE': 'Centrus Energy Corp.',
    'VO51.DE': 'Energy Fuels Inc.', 'UUUU': 'Energy Fuels Inc.',
    'U6Z.DE': 'Uranium Energy Corp.', 'UEC': 'Uranium Energy Corp.',
    'BCO.DE': 'The Boeing Company', 'BA': 'The Boeing Company', 
    'CAT1.DE': 'Caterpillar Inc.', 'CAT': 'Caterpillar Inc.',
    'LOM.DE': 'Lockheed Martin', 'LMT': 'Lockheed Martin', 
    'RTX.DE': 'RTX Corporation', 'RTX': 'RTX Corporation',
    'GEC.DE': 'General Electric', 'GE': 'General Electric', 
    'HON.DE': 'Honeywell', 'HON': 'Honeywell',
    'UPB.DE': 'United Parcel Service', 'UPS': 'United Parcel Service', 
    'DCO.DE': 'Deere & Company', 'DE': 'Deere & Company',
    'RHM.DE': 'Rheinmetall AG', 
    'CCC3.DE': 'The Coca-Cola Company', 'KO': 'The Coca-Cola Company',
    'MDO.DE': 'McDonald\'s Corporation', 'MCD': 'McDonald\'s Corporation', 
    'WMT.DE': 'Walmart Inc.', 'WMT': 'Walmart Inc.',
    'HDI.DE': 'The Home Depot', 'HD': 'The Home Depot', 
    'CTO.DE': 'Costco Wholesale', 'COST': 'Costco Wholesale',
    'NKE.DE': 'NIKE, Inc.', 'NKE': 'NIKE, Inc.', 
    'SRB.DE': 'Starbucks', 'SBUX': 'Starbucks',
    'WDP.DE': 'The Walt Disney Company', 'DIS': 'The Walt Disney Company', 
    'LWE.DE': 'Lowe\'s Companies', 'LOW': 'Lowe\'s Companies',
    'EUNL.DE': 'iShares Core MSCI World', 'VUSA.DE': 'Vanguard S&P 500',
    'VWCE.DE': 'Vanguard FTSE All-World', 'EXS1.DE': 'iShares Core DAX',
    'EXXT.DE': 'iShares Nasdaq-100', 'SPPW.DE': 'SPDR MSCI World',
    'IS3N.DE': 'iShares Core EM IMI', 'IUSN.DE': 'iShares MSCI World Small Cap',
    'XDWD.DE': 'Xtrackers MSCI World Swap', 'ZPRV.DE': 'SPDR MSCI USA Small Cap Value',
    'DBXD.DE': 'Xtrackers DAX', 'IS04.DE': 'iShares MSCI World', 'EGLN.DE': 'iShares Physical Gold',
    'PPFD.SG': 'iShares Physical Silver ETC', 'SLV': 'iShares Silver Trust',
}

# --- ASSET SECTORS ---
TICKER_SECTORS = {
    'APC.DE': 'Technology', 'AAPL': 'Technology',
    'MSF.DE': 'Technology', 'MSFT': 'Technology',
    'AMZ.DE': 'Ecommerce', 'AMZN': 'Ecommerce',
    'NVD.DE': 'Semiconductors', 'NVDA': 'Semiconductors',
    'ABEA.DE': 'Technology', 'GOOGL': 'Technology',
    'FB2A.DE': 'Technology', 'META': 'Technology',
    'TL0.DE': 'Automotive', 'TSLA': 'Automotive',
    'SFC.DE': 'Software', 'CRM': 'Software',
    'ADB.DE': 'Software', 'ADBE': 'Software',
    'NFC.DE': 'Entertainment', 'NFLX': 'Entertainment',
    'AMD.DE': 'Semiconductors', 'AMD': 'Semiconductors',
    '1IN.DE': 'Semiconductors', 'INTC': 'Semiconductors',
    'QCI.DE': 'Semiconductors', 'QCOM': 'Semiconductors',
    'AP2.DE': 'Semiconductors', 'AMAT': 'Semiconductors',
    'MTU.DE': 'Semiconductors', 'MU': 'Semiconductors',
    'TII.DE': 'Semiconductors', 'TXN': 'Semiconductors',
    'ORC.DE': 'Software', 'ORCL': 'Software',
    'TSM.DE': 'Semiconductors', 'TSM': 'Semiconductors',
    'KLA.DE': 'Semiconductors', 'KLAC': 'Semiconductors',
    'NOW.DE': 'Software', 'NOW': 'Software',
    'SNW.DE': 'Software', 'SNOW': 'Software',
    'UT8.DE': 'Transportation', 'UBER': 'Transportation',
    'PYPL.DE': 'Financials', 'PYPL': 'Financials',
    '639.DE': 'Entertainment', 'SPOT': 'Entertainment',
    'SHOP.DE': 'Ecommerce', 'SHOP': 'Ecommerce',
    '1S2.DE': 'Software', 'FIG': 'Software',
    '3V64.DE': 'Financials', 'V': 'Financials',
    'M9Z.DE': 'Financials', 'MA': 'Financials',
    'CMC.DE': 'Financials', 'JPM': 'Financials',
    'NCB.DE': 'Financials', 'BAC': 'Financials',
    'GOS.DE': 'Financials', 'GS': 'Financials',
    'DWD.DE': 'Financials', 'MS': 'Financials',
    'BRYN.DE': 'Financials', 'BRK-B': 'Financials',
    'AXP.DE': 'Financials', 'AXP': 'Financials',
    'BLQA.DE': 'Financials', 'BLK': 'Financials',
    
    # European Blue Chips
    'SAP.DE': 'Software', 'ALV.DE': 'Insurance', 'SIE.DE': 'Industrial',
    'BAYN.DE': 'Healthcare', 'BMW.DE': 'Automotive', 'DTE.DE': 'Telecom',
    'BAS.DE': 'Chemicals', 'MBG.DE': 'Automotive', 'ADS.DE': 'Consumer',
    'MUV2.DE': 'Insurance', 'DBK.DE': 'Financials', 'ENR.DE': 'Energy',
    'IFX.DE': 'Semiconductors', 'VOW3.DE': 'Automotive', 'RWE.DE': 'Utilities',
    'CON.DE': 'Automotive', 'FRE.DE': 'Healthcare', 'VNA.DE': 'Real Estate',
    'HEN3.DE': 'Consumer', 'BEI.DE': 'Consumer', 'ZAL.DE': 'Ecommerce',
    'MTX.DE': 'Industrial', 'NDX1.DE': 'Renewables',
    'ARGX.DE': 'Biotech', 'ARGX': 'Biotech', 
    'UCB.DE': 'Pharma', 'UCBJF': 'Pharma',
    'SHL.DE': 'Healthcare', 'COK.DE': 'Technology', 'AIR.DE': 'Industrial',
    'ZEGB.DE': 'Pharma', 'AZN': 'Pharma', 
    'R6C0.DE': 'Energy', 'SHEL': 'Energy', 
    'TOTB.DE': 'Energy', 'TTE': 'Energy', 
    'BPE5.DE': 'Energy', 'BP': 'Energy',
    'ASME.DE': 'Semiconductors', 'ASML': 'Semiconductors', 
    'NOV.DE': 'Pharma', 'NVS': 'Pharma', 
    'S92.DE': 'Renewables',

    # Healthcare
    'UNH.DE': 'Healthcare', 'UNH': 'Healthcare', 
    'JNJ.DE': 'Healthcare', 'JNJ': 'Healthcare',
    'PFE.DE': 'Healthcare', 'PFE': 'Healthcare', 
    'LLY.DE': 'Healthcare', 'LLY': 'Healthcare', 
    '4AB.DE': 'Healthcare', 'ABBV': 'Healthcare', 
    '6MK.DE': 'Healthcare', 'MRK': 'Healthcare',
    'AMG.DE': 'Healthcare', 'AMGN': 'Healthcare', 
    'GIS.DE': 'Biotech', 'GILD': 'Biotech', 
    'TMO.DE': 'Healthcare', 'TMO': 'Healthcare', 
    '22UA.DE': 'Biotech', 'BNTX': 'Biotech',
    'VRTX': 'Biotech', 'VRT.DE': 'Biotech',
    'AXSM': 'Biotech', 'AXS.DE': 'Biotech',
    '4YC.DE': 'Healthcare', 'ATAI': 'Healthcare', 
    
    # Energy & Industrials
    'XONA.DE': 'Energy', 'XOM': 'Energy', 
    'CHV.DE': 'Energy', 'CVX': 'Energy', 
    'NPL.DE': 'Utilities', 'NEE': 'Utilities',
    'F3A.DE': 'Renewables', 'FSLR': 'Renewables', 
    'GEV': 'Energy', 'GEV.DE': 'Energy',
    'CCJ': 'Energy', 'CJJ.DE': 'Energy',
    'CEG': 'Energy', 'CEG.DE': 'Energy',
    'SMR': 'Energy', 'NUS.DE': 'Energy',
    'OKLO': 'Energy', 'OKL.DE': 'Energy',
    'REP': 'Energy', 'REP.DE': 'Energy',
    'ENB': 'Energy', 'ENB.DE': 'Energy',
    'ENGI': 'Energy', 'EGI.DE': 'Energy',
    'BE': 'Energy', 'BLM.DE': 'Energy',
    'BRP.DE': 'Energy', 'BEP': 'Energy',
    'RIO.DE': 'Mining', 'RIO': 'Mining',
    'ERO.DE': 'Mining', 'ERO': 'Mining',
    'FPM.DE': 'Mining', 'FCX': 'Mining',
    'ALB.DE': 'Mining', 'ALB': 'Mining',
    'MNR.DE': 'Mining', 'MIN': 'Mining',
    'LEU': 'Energy', 'C1E.DE': 'Energy',
    'VO51.DE': 'Energy', 'UUUU': 'Energy',
    'U6Z.DE': 'Energy', 'UEC': 'Energy',
    'BCO.DE': 'Industrial', 'BA': 'Industrial', 
    'CAT1.DE': 'Industrial', 'CAT': 'Industrial', 
    'LOM.DE': 'Industrial', 'LMT': 'Industrial',
    'RTX.DE': 'Industrial', 'RTX': 'Industrial', 
    'GEC.DE': 'Industrial', 'GE': 'Industrial', 
    'HON.DE': 'Industrial', 'HON': 'Industrial',
    'UPB.DE': 'Transportation', 'UPS': 'Transportation', 
    'DCO.DE': 'Industrial', 'DE': 'Industrial', 
    'RHM.DE': 'Industrial',
    
    # Consumer
    'CCC3.DE': 'Consumer', 'KO': 'Consumer', 
    'MDO.DE': 'Consumer', 'MCD': 'Consumer', 
    'WMT.DE': 'Consumer', 'WMT': 'Consumer', 
    'HDI.DE': 'Consumer', 'HD': 'Consumer',
    'CTO.DE': 'Consumer', 'COST': 'Consumer', 
    'NKE.DE': 'Consumer', 'NKE': 'Consumer', 
    'SRB.DE': 'Consumer', 'SBUX': 'Consumer', 
    'WDP.DE': 'Entertainment', 'DIS': 'Entertainment',
    'LWE.DE': 'Consumer', 'LOW': 'Consumer', 
    
    # ETFs
    'EUNL.DE': 'ETF', 'VUSA.DE': 'ETF', 'VWCE.DE': 'ETF',
    'EXS1.DE': 'ETF', 'EXXT.DE': 'ETF', 'SPPW.DE': 'ETF', 'IS3N.DE': 'ETF',
    'IUSN.DE': 'ETF', 'XDWD.DE': 'ETF', 'ZPRV.DE': 'ETF', 'DBXD.DE': 'ETF',
    'PPFD.SG': 'ETF', 'SLV': 'ETF',
}

# The active universe used by the engine (Primary Tickers)
ASSET_UNIVERSE = [
    # --- Tech & Semiconductors ---
    'APC.DE', 'MSF.DE', 'AMZ.DE', 'NVD.DE', 'ABEA.DE', 'FB2A.DE', 'TL0.DE', 
    'SFC.DE', 'ADB.DE', 'NFC.DE', 'AMD.DE', '1IN.DE', 'QCI.DE', 'AP2.DE', 
    'MTU.DE', 'TII.DE', 'ORC.DE', 'TSM.DE', 'KLA.DE', 'NOW.DE', 'SNW.DE', 
    'UT8.DE', 'PYPL.DE', '639.DE', 'SHOP.DE', '1S2.DE',
    
    # --- European Blue Chips ---
    'SAP.DE', 'ALV.DE', 'SIE.DE', 'BAYN.DE', 'BMW.DE', 'DTE.DE', 'BAS.DE', 
    'MBG.DE', 'ADS.DE', 'MUV2.DE', 'DBK.DE', 'ENR.DE', 'IFX.DE', 'VOW3.DE', 
    'RWE.DE', 'CON.DE', 'FRE.DE', 'VNA.DE', 'HEN3.DE', 'BEI.DE', 'ZAL.DE', 
    'MTX.DE', 'NDX1.DE', 'ARGX.DE', 'UCB.DE', 'SHL.DE', 
    'COK.DE', 'AIR.DE', 'ZEGB.DE', 'R6C0.DE', 'TOTB.DE', 'BPE5.DE', 'ASME.DE', 
    'S92.DE',

    # --- Financials & Consumer ---
    '3V64.DE', 'CMC.DE', 'NCB.DE', 'GOS.DE', 'DWD.DE', 'BRYN.DE', 'AXP.DE', 
    'BLQA.DE', 'CCC3.DE', 'MDO.DE', 'WMT.DE', 'HDI.DE', 'CTO.DE', 'NKE.DE', 
    'SRB.DE', 'WDP.DE', 'LWE.DE',
    
    # --- Healthcare & Biotech ---
    'UNH.DE', 'JNJ.DE', 'PFE.DE', 'LLY.DE', '4AB.DE', '6MK.DE', 'AMG.DE', 
    'GIS.DE', 'TMO.DE', '22UA.DE', 'VRT.DE', 'AXS.DE', 'NOV.DE', '4YC.DE',

    # --- Energy, Mining & Industrials ---
    'XONA.DE', 'CHV.DE', 'NPL.DE', 'F3A.DE', 'GEV.DE', 'CJJ.DE', 'CEG.DE', 
    'NUS.DE', 'OKL.DE', 'REP.DE', 'ENB.DE', 'EGI.DE', 'BLM.DE', 'BRP.DE', 
    'RIO.DE', 'ERO.DE', 'FPM.DE', 'ALB.DE', 'MNR.DE', 'C1E.DE', 'VO51.DE', 'U6Z.DE',
    'BCO.DE', 'CAT1.DE', 'LOM.DE', 'RTX.DE', 'GEC.DE', 'HON.DE', 'UPB.DE', 
    'DCO.DE', 'RHM.DE'
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
    'PPFD.SG',  # iShares Physical Silver ETC
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

# Sanity check: benchmark must be in the universe for beta computation
assert BENCHMARK_TICKER in ASSET_UNIVERSE, (
    f"BENCHMARK_TICKER '{BENCHMARK_TICKER}' is not in ASSET_UNIVERSE. "
    f"Beta computation will fail. Add it to ETF_TICKERS."
)