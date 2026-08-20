============================================================
  HEDGE FUND CONTROL TOWER - UNIFIED SYSTEM RUNNER
============================================================
[1/6] Syncing Market Data (Prices, FX, Fundamentals)...
INFO:__main__:Ingestion starting: 135 tickers, 2026-07-21 → 2026-08-20, polygon=no (yfinance only)
ERROR:yfinance:HTTP Error 404: {"quoteSummary":{"result":null,"error":{"code":"Not Found","description":"Quote not found for symbol: SFC.DE"}}}
ERROR:yfinance:$SFC.DE: possibly delisted; no timezone found
ERROR:yfinance:
1 Failed download:
ERROR:yfinance:['SFC.DE']: possibly delisted; no timezone found
INFO:__main__:Primary SFC.DE failed/empty — trying fallback: CRM
INFO:__main__:Successfully fetched fallback data for SFC.DE via CRM
ERROR:yfinance:HTTP Error 404: {"quoteSummary":{"result":null,"error":{"code":"Not Found","description":"Quote not found for symbol: 1IN.DE"}}}
ERROR:yfinance:$1IN.DE: possibly delisted; no timezone found
ERROR:yfinance:
1 Failed download:
ERROR:yfinance:['1IN.DE']: possibly delisted; no timezone found
INFO:__main__:Primary 1IN.DE failed/empty — trying fallback: INTC
INFO:__main__:Successfully fetched fallback data for 1IN.DE via INTC
ERROR:yfinance:$MTU.DE: possibly delisted; no timezone found
ERROR:yfinance:
1 Failed download:
ERROR:yfinance:['MTU.DE']: possibly delisted; no timezone found
INFO:__main__:Primary MTU.DE failed/empty — trying fallback: MU
INFO:__main__:Successfully fetched fallback data for MTU.DE via MU
ERROR:yfinance:$TSM.DE: possibly delisted; no timezone found
ERROR:yfinance:
1 Failed download:
ERROR:yfinance:['TSM.DE']: possibly delisted; no timezone found
INFO:__main__:Primary TSM.DE failed/empty — trying fallback: TSM
INFO:__main__:Successfully fetched fallback data for TSM.DE via TSM
ERROR:yfinance:$NOW.DE: possibly delisted; no timezone found
ERROR:yfinance:
1 Failed download:
ERROR:yfinance:['NOW.DE']: possibly delisted; no timezone found
INFO:__main__:Primary NOW.DE failed/empty — trying fallback: NOW
INFO:__main__:Successfully fetched fallback data for NOW.DE via NOW
ERROR:yfinance:$PYPL.DE: possibly delisted; no timezone found
ERROR:yfinance:
1 Failed download:
ERROR:yfinance:['PYPL.DE']: possibly delisted; no timezone found
INFO:__main__:Primary PYPL.DE failed/empty — trying fallback: PYPL
INFO:__main__:Successfully fetched fallback data for PYPL.DE via PYPL
ERROR:yfinance:$SHOP.DE: possibly delisted; no timezone found
ERROR:yfinance:
1 Failed download:
ERROR:yfinance:['SHOP.DE']: possibly delisted; no timezone found
INFO:__main__:Primary SHOP.DE failed/empty — trying fallback: SHOP
INFO:__main__:Successfully fetched fallback data for SHOP.DE via SHOP
ERROR:yfinance:$AXP.DE: possibly delisted; no timezone found
ERROR:yfinance:
1 Failed download:
ERROR:yfinance:['AXP.DE']: possibly delisted; no timezone found
INFO:__main__:Primary AXP.DE failed/empty — trying fallback: AXP
INFO:__main__:Successfully fetched fallback data for AXP.DE via AXP
ERROR:yfinance:$BLQA.DE: possibly delisted; no timezone found
ERROR:yfinance:
1 Failed download:
ERROR:yfinance:['BLQA.DE']: possibly delisted; no timezone found
INFO:__main__:Primary BLQA.DE failed/empty — trying fallback: BLK
INFO:__main__:Successfully fetched fallback data for BLQA.DE via BLK
ERROR:yfinance:$ENB.DE: possibly delisted; no price data found  (1d 2026-07-21 -> 2026-08-20)
ERROR:yfinance:
1 Failed download:
ERROR:yfinance:['ENB.DE']: possibly delisted; no price data found  (1d 2026-07-21 -> 2026-08-20)
INFO:__main__:Primary ENB.DE failed/empty — trying fallback: ENB
INFO:__main__:Successfully fetched fallback data for ENB.DE via ENB
ERROR:yfinance:$EGI.DE: possibly delisted; no timezone found
ERROR:yfinance:
1 Failed download:
ERROR:yfinance:['EGI.DE']: possibly delisted; no timezone found
INFO:__main__:Primary EGI.DE failed/empty — trying fallback: ENGIY
INFO:__main__:Successfully fetched fallback data for EGI.DE via ENGIY
ERROR:yfinance:$BLM.DE: possibly delisted; no price data found  (1d 2026-07-21 -> 2026-08-20)
ERROR:yfinance:
1 Failed download:
ERROR:yfinance:['BLM.DE']: possibly delisted; no price data found  (1d 2026-07-21 -> 2026-08-20)
INFO:__main__:Primary BLM.DE failed/empty — trying fallback: BE
INFO:__main__:Successfully fetched fallback data for BLM.DE via BE
ERROR:yfinance:$C1E.DE: possibly delisted; no timezone found
ERROR:yfinance:
1 Failed download:
ERROR:yfinance:['C1E.DE']: possibly delisted; no timezone found
INFO:__main__:Primary C1E.DE failed/empty — trying fallback: LEU
INFO:__main__:Successfully fetched fallback data for C1E.DE via LEU
ERROR:yfinance:$VO51.DE: possibly delisted; no timezone found
ERROR:yfinance:
1 Failed download:
ERROR:yfinance:['VO51.DE']: possibly delisted; no timezone found
INFO:__main__:Primary VO51.DE failed/empty — trying fallback: UUUU
INFO:__main__:Successfully fetched fallback data for VO51.DE via UUUU
INFO:engine.data.validation:Validation complete: 2906 clean rows, 0 rejected
INFO:__main__:FX fetched from yfinance: USDEUR
INFO:__main__:FX fetched from yfinance: GBPEUR
INFO:__main__:FX rates persisted: 44 rows across 2 pairs
WARNING:__main__:persist_prices: dropped 73 rows with NaN close/adj_close
INFO:__main__:Persisted 2833 price rows to DB.
INFO:__main__:Ingestion complete: 2906 rows persisted.
INFO:__main__:✅ Staleness check: all tickers fresh.

Result: 2906 rows, tickers: ['1IN.DE', '1S2.DE', '3V64.DE', '639.DE', 'ABBV', 'ABEA.DE', 'ADB.DE', 'ADS.DE', 'AIR.DE', 'ALB', 'ALV.DE', 'AMD.DE', 'AMGN', 'AMZ.DE', 'AP2.DE', 'APC.DE', 'ARGX.BR', 'ASML.AS', 'ATAI', 'AXP.DE', 'AXSM', 'AZN.L', 'BA', 'BAS.DE', 'BAYN.DE', 'BEI.DE', 'BEP', 'BLM.DE', 'BLQA.DE', 'BMW.DE', 'BNTX', 'BP.L', 'BRYN.DE', 'C1E.DE', 'CAT', 'CCJ', 'CEG', 'CMC.DE', 'COK.DE', 'CON.DE', 'COST', 'CVX', 'DBK.DE', 'DBXD.DE', 'DE', 'DIS', 'DTE.DE', 'DWD.DE', 'EGI.DE', 'ENB.DE', 'ENR.DE', 'ERO', 'EUNL.DE', 'EXS1.DE', 'EXXT.DE', 'FB2A.DE', 'FCX', 'FRE.DE', 'FSLR', 'GE', 'GEV', 'GILD', 'GOS.DE', 'HD', 'HEN3.DE', 'HON', 'IFX.DE', 'IS3N.DE', 'IUSN.DE', 'JNJ', 'KLA.DE', 'KO', 'LLY', 'LMT', 'LOW', 'MBG.DE', 'MCD', 'MIN', 'MRK', 'MSF.DE', 'MTU.DE', 'MTX.DE', 'MUV2.DE', 'NCB.DE', 'NDX1.DE', 'NEE', 'NFC.DE', 'NKE', 'NOV.DE', 'NOW.DE', 'NVD.DE', 'NVS', 'OKLO', 'ORC.DE', 'PFE', 'PPFD.SG', 'PYPL.DE', 'QCI.DE', 'REP.DE', 'RHM.DE', 'RIO', 'RTX', 'RWE.DE', 'S92.DE', 'SAP.DE', 'SBUX', 'SFC.DE', 'SHELL.AS', 'SHL.DE', 'SHOP.DE', 'SIE.DE', 'SMR', 'SNW.DE', 'SPPW.DE', 'TII.DE', 'TL0.DE', 'TMO', 'TSM.DE', 'TTE.PA', 'U6Z.DE', 'UCB.BR', 'UNH', 'UPS', 'UT8.DE', 'VNA.DE', 'VO51.DE', 'VOW3.DE', 'VRTX', 'VUSA.DE', 'VWCE.DE', 'WMT', 'XDWD.DE', 'XOM', 'ZAL.DE', 'ZPRV.DE']
[2/6] Updating Macro Regime Intelligence (Global)...
01:07:43  INFO     ----------------------------------------
01:07:43  INFO       MACRO REGIME ENGINE - US - START
01:07:43  INFO     ----------------------------------------
01:07:44  INFO       Fetched Official FRED API: vix
01:07:44  INFO       Fetched Official FRED API: yield_spread
01:07:45  INFO       Fetched Official FRED API: hy_spread
01:07:46  INFO       Fetched Official FRED API: ig_spread
01:07:46  INFO       Fetched Official FRED API: fed_funds
01:07:47  INFO       Fetched Official FRED API: ism_mfg
01:07:48  INFO     Macro data (US): 447 rows
01:07:48  INFO     Classifying 447 trading days for region: US...
01:07:48  INFO     Latest US regime [2026-08-20]: RiskOn_Neutral_Expansion | EW=False
01:07:48  INFO     Regime history saved: C:\Users\ahmty\Desktop\hedge-fund\shared\state\regime_history.csv (US added, 1034 total rows)
01:07:48  INFO     Regime state (US) written → C:\Users\ahmty\Desktop\hedge-fund\shared\state\regime_state_us.json
01:07:48  INFO     Regime state (canonical) written → C:\Users\ahmty\Desktop\hedge-fund\shared\state\regime_state.json

=======================================================
  MACRO REGIME SNAPSHOT - US - 2026-08-20
=======================================================
  Risk Appetite   : Risk-On
  Rate Environment: Neutral
  Growth Cycle    : Expansion
  Composite       : RiskOn_Neutral_Expansion
  VIX            : 14.89
  Spread (10Y-2Y): 0.46
  HY Spread      : 2.75
  Fed Funds      : 3.63
  Status          : No transition warning (0/4 triggers)
=======================================================

01:07:48  INFO     ----------------------------------------
01:07:48  INFO       MACRO REGIME ENGINE - US - COMPLETE
01:07:48  INFO     ----------------------------------------
01:07:48  INFO     ----------------------------------------
01:07:48  INFO       MACRO REGIME ENGINE - EU - START
01:07:48  INFO     ----------------------------------------
01:07:48  INFO       Fetched Official FRED API: yield_10y
01:07:49  INFO       Fetched Official FRED API: yield_3m
01:07:49  INFO       Fetched Official FRED API: hy_spread
01:07:50  INFO       Fetched Official FRED API: ig_spread
01:07:50  INFO       Fetched Official FRED API: fed_funds
01:07:51  INFO       Fetched Official FRED API: fed_funds_alt
01:07:51  INFO       Fetched Official FRED API: ism_mfg
01:07:51  INFO       Calculated EU yield_spread (10Y - 3M proxy)
01:07:51  WARNING    Missing critical column: vix
01:07:53  ERROR    HTTP Error 404: {"quoteSummary":{"result":null,"error":{"code":"Not Found","description":"Quote not found for symbol: ^V2TX"}}}
01:07:54  ERROR    $^V2TX: possibly delisted; no price data found  (period=2y) (Yahoo error = "No data found, symbol may be delisted")
01:07:54  ERROR
1 Failed download:
01:07:54  ERROR    ['^V2TX']: possibly delisted; no price data found  (period=2y) (Yahoo error = "No data found, symbol may be delisted")
01:07:54  WARNING  VSTOXX failed, falling back to VIX for EU proxy
01:07:56  INFO     Macro data (EU): 447 rows
01:07:56  INFO     Classifying 447 trading days for region: EU...
01:07:56  INFO     Latest EU regime [2026-08-20]: RiskOn_Tightening_Slowdown | EW=False
01:07:56  INFO     Regime history saved: C:\Users\ahmty\Desktop\hedge-fund\shared\state\regime_history.csv (EU added, 1035 total rows)
01:07:56  INFO     Regime state (EU) written → C:\Users\ahmty\Desktop\hedge-fund\shared\state\regime_state_eu.json
01:07:56  INFO     Regime state (canonical) written → C:\Users\ahmty\Desktop\hedge-fund\shared\state\regime_state.json

=======================================================
  MACRO REGIME SNAPSHOT - EU - 2026-08-20
=======================================================
  Risk Appetite   : Risk-On
  Rate Environment: Tightening
  Growth Cycle    : Slowdown
  Composite       : RiskOn_Tightening_Slowdown
  VSTOXX         : 14.89
  Spread (10Y-2Y): 0.631
  HY Spread      : 2.55
  ECB Rate       : 2.25
  Status          : No transition warning (0/4 triggers)
=======================================================

01:07:56  INFO     ----------------------------------------
01:07:56  INFO       MACRO REGIME ENGINE - EU - COMPLETE
01:07:56  INFO     ----------------------------------------
[3/6] Running Earnings (PEAD) Screener...
01:07:59  INFO     ═══════════════════════════════════════
01:07:59  INFO       PEAD ENGINE — START
01:07:59  INFO     ═══════════════════════════════════════
01:07:59  INFO     Step 1/5 — Fetching price history...
01:07:59  INFO     Fetching prices for 71 tickers (756d history)...
01:08:05  INFO     Prices cached: C:\Users\ahmty\Desktop\hedge-fund\ml_quant_finance_research\quant_research\pead_engine\data\pead_prices.csv (577 rows, 71 tickers)
01:08:05  INFO       Prices: 577 rows × 71 tickers
01:08:05  INFO     Step 2/5 — Backfilling drift outcomes...
01:08:05  INFO       DB has 221 total setups after backfill
01:08:05  INFO     Step 3/5 — Fetching earnings history...
01:08:05  INFO     Loading earnings from cache: C:\Users\ahmty\Desktop\hedge-fund\ml_quant_finance_research\quant_research\pead_engine\data\earnings_cache.csv
01:08:05  INFO       Earnings: 252 events across 63 tickers
01:08:05  INFO     Step 4/5 — Fitting surprise→reaction regression models...
01:08:05  INFO       Loaded 54 cached regression models
01:08:05  INFO     Step 5/5 — Screening earnings events (last 90d)...
01:08:05  INFO     Screening 55 earnings events (last 90d)...
01:08:14  INFO     PEAD setups found: 41 total | High=0 Medium=2 Low=39
01:08:14  INFO       Regime labels attached to setups via merge_asof.
01:08:14  INFO     PEAD DB saved: C:\Users\ahmty\Desktop\hedge-fund\ml_quant_finance_research\quant_research\pead_engine\data\pead_setups.csv (221 total setups)
01:08:14  INFO     PEAD state written: C:\Users\ahmty\Desktop\hedge-fund\ml_quant_finance_research\quant_research\pead_engine\data\pead_state.json | 0 active setups

------------------------------------------------------------
  PEAD ENGINE SUMMARY — 2026-08-20 01:08
------------------------------------------------------------

  No active PEAD setups in entry window today.

  [PERFORMANCE] (all-time, 221 setups):
     Overall 21d hit rate : 56.1%
     Overall avg drift 21d: +2.47%
     High quality 21d HR  : 100.0%
     High quality avg 21d : +67.31%
     Slowdown             21d HR: 67.4%
     Expansion            21d HR: 46.2%

------------------------------------------------------------

01:08:14  INFO     ═══════════════════════════════════════
01:08:14  INFO       PEAD ENGINE — COMPLETE
01:08:14  INFO     ═══════════════════════════════════════

[4/6] ML INTELLIGENCE UPDATE
Do you want to run FULL ML training? (Takes ~10-45 mins) (y/n): y
[ACTION] Training ML Models...
01:09:01 [INFO] ============================================================
01:09:01 [INFO]  ML PIPELINE — START
01:09:01 [INFO] ============================================================
01:09:01 [INFO] Step 1/5 — Loading price data from parquets…
01:09:03 [INFO] [APC.DE] Fetching 2014-01-01 → 2026-08-20
01:09:05 [INFO] [APC.DE] 3207 rows saved
01:09:05 [INFO] [MSF.DE] Fetching 2014-01-01 → 2026-08-20
01:09:06 [INFO] [MSF.DE] 3207 rows saved
01:09:06 [INFO] [AMZ.DE] Fetching 2014-01-01 → 2026-08-20
01:09:06 [INFO] [AMZ.DE] 3207 rows saved
01:09:06 [INFO] [NVD.DE] Fetching 2014-01-01 → 2026-08-20
01:09:07 [INFO] [NVD.DE] 3207 rows saved
01:09:07 [INFO] [ABEA.DE] Fetching 2014-01-01 → 2026-08-20
01:09:08 [INFO] [ABEA.DE] 3207 rows saved
01:09:08 [INFO] [FB2A.DE] Fetching 2014-01-01 → 2026-08-20
01:09:08 [INFO] [FB2A.DE] 3207 rows saved
01:09:08 [INFO] [TL0.DE] Fetching 2014-01-01 → 2026-08-20
01:09:09 [INFO] [TL0.DE] 3207 rows saved
01:09:09 [INFO] [SFC.DE] Fetching 2014-01-01 → 2026-08-20
01:09:11 [ERROR] HTTP Error 404: {"quoteSummary":{"result":null,"error":{"code":"Not Found","description":"Quote not found for symbol: SFC.DE"}}}
01:09:11 [ERROR] $SFC.DE: possibly delisted; no timezone found
01:09:11 [ERROR]
1 Failed download:
01:09:11 [ERROR] ['SFC.DE']: possibly delisted; no timezone found
01:09:11 [INFO] [SFC.DE] Primary failed — trying fallback: CRM
01:09:12 [INFO] [SFC.DE] 3176 rows saved
01:09:12 [INFO] [ADB.DE] Fetching 2014-01-01 → 2026-08-20
01:09:13 [INFO] [ADB.DE] 3207 rows saved
01:09:13 [INFO] [NFC.DE] Fetching 2014-01-01 → 2026-08-20
01:09:14 [INFO] [NFC.DE] 3207 rows saved
01:09:14 [INFO] [AMD.DE] Fetching 2014-01-01 → 2026-08-20
01:09:16 [INFO] [AMD.DE] 3207 rows saved
01:09:16 [INFO] [1IN.DE] Fetching 2014-01-01 → 2026-08-20
01:09:19 [ERROR] HTTP Error 404: {"quoteSummary":{"result":null,"error":{"code":"Not Found","description":"Quote not found for symbol: 1IN.DE"}}}
01:09:19 [ERROR] $1IN.DE: possibly delisted; no timezone found
01:09:19 [ERROR]
1 Failed download:
01:09:19 [ERROR] ['1IN.DE']: possibly delisted; no timezone found
01:09:19 [INFO] [1IN.DE] Primary failed — trying fallback: INTC
01:09:20 [INFO] [1IN.DE] 3176 rows saved
01:09:20 [INFO] [QCI.DE] Fetching 2014-01-01 → 2026-08-20
01:09:20 [INFO] [QCI.DE] 3207 rows saved
01:09:20 [INFO] [AP2.DE] Fetching 2014-01-01 → 2026-08-20
01:09:21 [INFO] [AP2.DE] 3207 rows saved
01:09:21 [INFO] [MTU.DE] Fetching 2014-01-01 → 2026-08-20
01:09:22 [ERROR] $MTU.DE: possibly delisted; no timezone found
01:09:22 [ERROR]
1 Failed download:
01:09:22 [ERROR] ['MTU.DE']: possibly delisted; no timezone found
01:09:22 [INFO] [MTU.DE] Primary failed — trying fallback: MU
01:09:22 [INFO] [MTU.DE] 3176 rows saved
01:09:22 [INFO] [TII.DE] Fetching 2014-01-01 → 2026-08-20
01:09:23 [INFO] [TII.DE] 3207 rows saved
01:09:23 [INFO] [ORC.DE] Fetching 2014-01-01 → 2026-08-20
01:09:24 [INFO] [ORC.DE] 3207 rows saved
01:09:24 [INFO] [TSM.DE] Fetching 2014-01-01 → 2026-08-20
01:09:25 [ERROR] $TSM.DE: possibly delisted; no timezone found
01:09:25 [ERROR]
1 Failed download:
01:09:25 [ERROR] ['TSM.DE']: possibly delisted; no timezone found
01:09:25 [INFO] [TSM.DE] Primary failed — trying fallback: TSM
01:09:25 [INFO] [TSM.DE] 3176 rows saved
01:09:25 [INFO] [KLA.DE] Fetching 2014-01-01 → 2026-08-20
01:09:26 [INFO] [KLA.DE] 3207 rows saved
01:09:26 [INFO] [NOW.DE] Fetching 2014-01-01 → 2026-08-20
01:09:27 [ERROR] $NOW.DE: possibly delisted; no timezone found
01:09:27 [ERROR]
1 Failed download:
01:09:27 [ERROR] ['NOW.DE']: possibly delisted; no timezone found
01:09:27 [INFO] [NOW.DE] Primary failed — trying fallback: NOW
01:09:27 [INFO] [NOW.DE] 3176 rows saved
01:09:27 [INFO] [SNW.DE] Fetching 2014-01-01 → 2026-08-20
01:09:28 [INFO] [SNW.DE] 3207 rows saved
01:09:28 [INFO] [UT8.DE] Fetching 2014-01-01 → 2026-08-20
01:09:29 [INFO] [UT8.DE] 1832 rows saved
01:09:29 [INFO] [PYPL.DE] Fetching 2014-01-01 → 2026-08-20
01:09:30 [ERROR] $PYPL.DE: possibly delisted; no timezone found
01:09:30 [ERROR]
1 Failed download:
01:09:30 [ERROR] ['PYPL.DE']: possibly delisted; no timezone found
01:09:30 [INFO] [PYPL.DE] Primary failed — trying fallback: PYPL
01:09:30 [INFO] [PYPL.DE] 2798 rows saved
01:09:30 [INFO] [639.DE] Fetching 2014-01-01 → 2026-08-20
01:09:31 [INFO] [639.DE] 617 rows saved
01:09:31 [INFO] [SHOP.DE] Fetching 2014-01-01 → 2026-08-20
01:09:32 [ERROR] $SHOP.DE: possibly delisted; no timezone found
01:09:32 [ERROR]
1 Failed download:
01:09:32 [ERROR] ['SHOP.DE']: possibly delisted; no timezone found
01:09:32 [INFO] [SHOP.DE] Primary failed — trying fallback: SHOP
01:09:32 [INFO] [SHOP.DE] 2829 rows saved
01:09:32 [INFO] [1S2.DE] Fetching 2014-01-01 → 2026-08-20
01:09:33 [INFO] [1S2.DE] 53 rows saved
01:09:33 [INFO] [SAP.DE] Fetching 2014-01-01 → 2026-08-20
01:09:34 [INFO] [SAP.DE] 3207 rows saved
01:09:34 [INFO] [ALV.DE] Fetching 2014-01-01 → 2026-08-20
01:09:35 [INFO] [ALV.DE] 3207 rows saved
01:09:35 [INFO] [SIE.DE] Fetching 2014-01-01 → 2026-08-20
01:09:36 [INFO] [SIE.DE] 3207 rows saved
01:09:36 [INFO] [BAYN.DE] Fetching 2014-01-01 → 2026-08-20
01:09:36 [INFO] [BAYN.DE] 3207 rows saved
01:09:36 [INFO] [BMW.DE] Fetching 2014-01-01 → 2026-08-20
01:09:37 [INFO] [BMW.DE] 3207 rows saved
01:09:37 [INFO] [DTE.DE] Fetching 2014-01-01 → 2026-08-20
01:09:38 [INFO] [DTE.DE] 3207 rows saved
01:09:38 [INFO] [BAS.DE] Fetching 2014-01-01 → 2026-08-20
01:09:39 [INFO] [BAS.DE] 3207 rows saved
01:09:39 [INFO] [MBG.DE] Fetching 2014-01-01 → 2026-08-20
01:09:39 [INFO] [MBG.DE] 3207 rows saved
01:09:39 [INFO] [ADS.DE] Fetching 2014-01-01 → 2026-08-20
01:09:41 [INFO] [ADS.DE] 3207 rows saved
01:09:41 [INFO] [MUV2.DE] Fetching 2014-01-01 → 2026-08-20
01:09:41 [INFO] [MUV2.DE] 3207 rows saved
01:09:41 [INFO] [DBK.DE] Fetching 2014-01-01 → 2026-08-20
01:09:43 [INFO] [DBK.DE] 3207 rows saved
01:09:43 [INFO] [ENR.DE] Fetching 2014-01-01 → 2026-08-20
01:09:44 [INFO] [ENR.DE] 1499 rows saved
01:09:44 [INFO] [IFX.DE] Fetching 2014-01-01 → 2026-08-20
01:09:45 [INFO] [IFX.DE] 3207 rows saved
01:09:45 [INFO] [VOW3.DE] Fetching 2014-01-01 → 2026-08-20
01:09:45 [INFO] [VOW3.DE] 3207 rows saved
01:09:45 [INFO] [RWE.DE] Fetching 2014-01-01 → 2026-08-20
01:09:46 [INFO] [RWE.DE] 3207 rows saved
01:09:46 [INFO] [CON.DE] Fetching 2014-01-01 → 2026-08-20
01:09:46 [INFO] [CON.DE] 3207 rows saved
01:09:46 [INFO] [FRE.DE] Fetching 2014-01-01 → 2026-08-20
01:09:47 [INFO] [FRE.DE] 3207 rows saved
01:09:47 [INFO] [VNA.DE] Fetching 2014-01-01 → 2026-08-20
01:09:48 [INFO] [VNA.DE] 3207 rows saved
01:09:48 [INFO] [HEN3.DE] Fetching 2014-01-01 → 2026-08-20
01:09:48 [INFO] [HEN3.DE] 3207 rows saved
01:09:48 [INFO] [BEI.DE] Fetching 2014-01-01 → 2026-08-20
01:09:50 [INFO] [BEI.DE] 3207 rows saved
01:09:50 [INFO] [ZAL.DE] Fetching 2014-01-01 → 2026-08-20
01:09:50 [INFO] [ZAL.DE] 3016 rows saved
01:09:50 [INFO] [MTX.DE] Fetching 2014-01-01 → 2026-08-20
01:09:51 [INFO] [MTX.DE] 3207 rows saved
01:09:51 [INFO] [NDX1.DE] Fetching 2014-01-01 → 2026-08-20
01:09:52 [INFO] [NDX1.DE] 3207 rows saved
01:09:52 [INFO] [ARGX.BR] Fetching 2014-01-01 → 2026-08-20
01:09:52 [INFO] [ARGX.BR] 3098 rows saved
01:09:52 [INFO] [UCB.BR] Fetching 2014-01-01 → 2026-08-20
01:09:53 [INFO] [UCB.BR] 3230 rows saved
01:09:53 [INFO] [SHL.DE] Fetching 2014-01-01 → 2026-08-20
01:09:54 [INFO] [SHL.DE] 2121 rows saved
01:09:54 [INFO] [COK.DE] Fetching 2014-01-01 → 2026-08-20
01:09:55 [INFO] [COK.DE] 3207 rows saved
01:09:55 [INFO] [AIR.DE] Fetching 2014-01-01 → 2026-08-20
01:09:55 [INFO] [AIR.DE] 3207 rows saved
01:09:55 [INFO] [AZN.L] Fetching 2014-01-01 → 2026-08-20
01:09:56 [INFO] [AZN.L] 3192 rows saved
01:09:56 [INFO] [SHELL.AS] Fetching 2014-01-01 → 2026-08-20
01:09:57 [INFO] [SHELL.AS] 3230 rows saved
01:09:57 [INFO] [TTE.PA] Fetching 2014-01-01 → 2026-08-20
01:09:57 [INFO] [TTE.PA] 3232 rows saved
01:09:57 [INFO] [BP.L] Fetching 2014-01-01 → 2026-08-20
01:09:58 [INFO] [BP.L] 3191 rows saved
01:09:58 [INFO] [ASML.AS] Fetching 2014-01-01 → 2026-08-20
01:09:59 [INFO] [ASML.AS] 3230 rows saved
01:09:59 [INFO] [NOV.DE] Fetching 2014-01-01 → 2026-08-20
01:10:00 [INFO] [NOV.DE] 3207 rows saved
01:10:00 [INFO] [S92.DE] Fetching 2014-01-01 → 2026-08-20
01:10:00 [INFO] [S92.DE] 3207 rows saved
01:10:00 [INFO] [3V64.DE] Fetching 2014-01-01 → 2026-08-20
01:10:01 [INFO] [3V64.DE] 3207 rows saved
01:10:01 [INFO] [CMC.DE] Fetching 2014-01-01 → 2026-08-20
01:10:02 [INFO] [CMC.DE] 3207 rows saved
01:10:02 [INFO] [NCB.DE] Fetching 2014-01-01 → 2026-08-20
01:10:03 [INFO] [NCB.DE] 3207 rows saved
01:10:03 [INFO] [GOS.DE] Fetching 2014-01-01 → 2026-08-20
01:10:04 [INFO] [GOS.DE] 3207 rows saved
01:10:04 [INFO] [DWD.DE] Fetching 2014-01-01 → 2026-08-20
01:10:04 [INFO] [DWD.DE] 3207 rows saved
01:10:04 [INFO] [BRYN.DE] Fetching 2014-01-01 → 2026-08-20
01:10:05 [INFO] [BRYN.DE] 3207 rows saved
01:10:05 [INFO] [AXP.DE] Fetching 2014-01-01 → 2026-08-20
01:10:06 [ERROR] $AXP.DE: possibly delisted; no timezone found
01:10:06 [ERROR]
1 Failed download:
01:10:06 [ERROR] ['AXP.DE']: possibly delisted; no timezone found
01:10:06 [INFO] [AXP.DE] Primary failed — trying fallback: AXP
01:10:06 [INFO] [AXP.DE] 3176 rows saved
01:10:06 [INFO] [BLQA.DE] Fetching 2014-01-01 → 2026-08-20
01:10:07 [ERROR] $BLQA.DE: possibly delisted; no timezone found
01:10:07 [ERROR]
1 Failed download:
01:10:07 [ERROR] ['BLQA.DE']: possibly delisted; no timezone found
01:10:07 [INFO] [BLQA.DE] Primary failed — trying fallback: BLK
01:10:08 [INFO] [BLQA.DE] 3176 rows saved
01:10:08 [INFO] [KO] Fetching 2014-01-01 → 2026-08-20
01:10:09 [INFO] [KO] 3176 rows saved
01:10:09 [INFO] [MCD] Fetching 2014-01-01 → 2026-08-20
01:10:09 [INFO] [MCD] 3176 rows saved
01:10:09 [INFO] [WMT] Fetching 2014-01-01 → 2026-08-20
01:10:10 [INFO] [WMT] 3176 rows saved
01:10:10 [INFO] [HD] Fetching 2014-01-01 → 2026-08-20
01:10:11 [INFO] [HD] 3176 rows saved
01:10:11 [INFO] [COST] Fetching 2014-01-01 → 2026-08-20
01:10:12 [INFO] [COST] 3176 rows saved
01:10:12 [INFO] [NKE] Fetching 2014-01-01 → 2026-08-20
01:10:12 [INFO] [NKE] 3176 rows saved
01:10:12 [INFO] [SBUX] Fetching 2014-01-01 → 2026-08-20
01:10:13 [INFO] [SBUX] 3176 rows saved
01:10:13 [INFO] [DIS] Fetching 2014-01-01 → 2026-08-20
01:10:14 [INFO] [DIS] 3176 rows saved
01:10:14 [INFO] [LOW] Fetching 2014-01-01 → 2026-08-20
01:10:15 [INFO] [LOW] 3176 rows saved
01:10:15 [INFO] [UNH] Fetching 2014-01-01 → 2026-08-20
01:10:16 [INFO] [UNH] 3176 rows saved
01:10:16 [INFO] [JNJ] Fetching 2014-01-01 → 2026-08-20
01:10:16 [INFO] [JNJ] 3176 rows saved
01:10:16 [INFO] [PFE] Fetching 2014-01-01 → 2026-08-20
01:10:17 [INFO] [PFE] 3176 rows saved
01:10:17 [INFO] [LLY] Fetching 2014-01-01 → 2026-08-20
01:10:19 [INFO] [LLY] 3176 rows saved
01:10:19 [INFO] [ABBV] Fetching 2014-01-01 → 2026-08-20
01:10:19 [INFO] [ABBV] 3175 rows saved
01:10:19 [INFO] [MRK] Fetching 2014-01-01 → 2026-08-20
01:10:20 [INFO] [MRK] 3176 rows saved
01:10:20 [INFO] [AMGN] Fetching 2014-01-01 → 2026-08-20
01:10:22 [INFO] [AMGN] 3176 rows saved
01:10:22 [INFO] [GILD] Fetching 2014-01-01 → 2026-08-20
01:10:22 [INFO] [GILD] 3176 rows saved
01:10:22 [INFO] [TMO] Fetching 2014-01-01 → 2026-08-20
01:10:23 [INFO] [TMO] 3176 rows saved
01:10:23 [INFO] [BNTX] Fetching 2014-01-01 → 2026-08-20
01:10:24 [INFO] [BNTX] 1722 rows saved
01:10:24 [INFO] [VRTX] Fetching 2014-01-01 → 2026-08-20
01:10:25 [INFO] [VRTX] 3176 rows saved
01:10:25 [INFO] [AXSM] Fetching 2014-01-01 → 2026-08-20
01:10:25 [INFO] [AXSM] 2700 rows saved
01:10:25 [INFO] [NVS] Fetching 2014-01-01 → 2026-08-20
01:10:26 [INFO] [NVS] 3176 rows saved
01:10:26 [INFO] [ATAI] Fetching 2014-01-01 → 2026-08-20
01:10:26 [INFO] [ATAI] 1298 rows saved
01:10:26 [INFO] [XOM] Fetching 2014-01-01 → 2026-08-20
01:10:27 [INFO] [XOM] 3176 rows saved
01:10:27 [INFO] [CVX] Fetching 2014-01-01 → 2026-08-20
01:10:28 [INFO] [CVX] 3176 rows saved
01:10:28 [INFO] [NEE] Fetching 2014-01-01 → 2026-08-20
01:10:28 [INFO] [NEE] 3176 rows saved
01:10:28 [INFO] [FSLR] Fetching 2014-01-01 → 2026-08-20
01:10:29 [INFO] [FSLR] 3176 rows saved
01:10:29 [INFO] [GEV] Fetching 2014-01-01 → 2026-08-20
01:10:31 [INFO] [GEV] 601 rows saved
01:10:31 [INFO] [CCJ] Fetching 2014-01-01 → 2026-08-20
01:10:31 [INFO] [CCJ] 3176 rows saved
01:10:31 [INFO] [CEG] Fetching 2014-01-01 → 2026-08-20
01:10:32 [INFO] [CEG] 1150 rows saved
01:10:32 [INFO] [SMR] Fetching 2014-01-01 → 2026-08-20
01:10:32 [INFO] [SMR] 1122 rows saved
01:10:32 [INFO] [OKLO] Fetching 2014-01-01 → 2026-08-20
01:10:33 [INFO] [OKLO] 1285 rows saved
01:10:33 [INFO] [REP.DE] Fetching 2014-01-01 → 2026-08-20
01:10:33 [INFO] [REP.DE] 3207 rows saved
01:10:33 [INFO] [ENB.DE] Fetching 2014-01-01 → 2026-08-20
01:10:34 [ERROR] $ENB.DE: possibly delisted; no price data found  (1d 2014-01-01 -> 2026-08-20)
01:10:34 [ERROR]
1 Failed download:
01:10:34 [ERROR] ['ENB.DE']: possibly delisted; no price data found  (1d 2014-01-01 -> 2026-08-20)
01:10:34 [INFO] [ENB.DE] Primary failed — trying fallback: ENB
01:10:35 [INFO] [ENB.DE] 3176 rows saved
01:10:35 [INFO] [EGI.DE] Fetching 2014-01-01 → 2026-08-20
01:10:36 [ERROR] $EGI.DE: possibly delisted; no timezone found
01:10:36 [ERROR]
1 Failed download:
01:10:36 [ERROR] ['EGI.DE']: possibly delisted; no timezone found
01:10:36 [INFO] [EGI.DE] Primary failed — trying fallback: ENGIY
01:10:36 [INFO] [EGI.DE] 3176 rows saved
01:10:36 [INFO] [BLM.DE] Fetching 2014-01-01 → 2026-08-20
01:10:37 [ERROR] $BLM.DE: possibly delisted; no price data found  (1d 2014-01-01 -> 2026-08-20)
01:10:37 [ERROR]
1 Failed download:
01:10:37 [ERROR] ['BLM.DE']: possibly delisted; no price data found  (1d 2014-01-01 -> 2026-08-20)
01:10:37 [INFO] [BLM.DE] Primary failed — trying fallback: BE
01:10:37 [INFO] [BLM.DE] 2028 rows saved
01:10:37 [INFO] [BEP] Fetching 2014-01-01 → 2026-08-20
01:10:38 [INFO] [BEP] 3176 rows saved
01:10:38 [INFO] [RIO] Fetching 2014-01-01 → 2026-08-20
01:10:39 [INFO] [RIO] 3176 rows saved
01:10:39 [INFO] [ERO] Fetching 2014-01-01 → 2026-08-20
01:10:41 [INFO] [ERO] 2218 rows saved
01:10:41 [INFO] [FCX] Fetching 2014-01-01 → 2026-08-20
01:10:42 [INFO] [FCX] 3176 rows saved
01:10:42 [INFO] [ALB] Fetching 2014-01-01 → 2026-08-20
01:10:43 [INFO] [ALB] 3176 rows saved
01:10:43 [INFO] [MIN] Fetching 2014-01-01 → 2026-08-20
01:10:44 [INFO] [MIN] 3176 rows saved
01:10:44 [INFO] [C1E.DE] Fetching 2014-01-01 → 2026-08-20
01:10:45 [ERROR] $C1E.DE: possibly delisted; no timezone found
01:10:45 [ERROR]
1 Failed download:
01:10:45 [ERROR] ['C1E.DE']: possibly delisted; no timezone found
01:10:45 [INFO] [C1E.DE] Primary failed — trying fallback: LEU
01:10:46 [INFO] [C1E.DE] 3176 rows saved
01:10:46 [INFO] [VO51.DE] Fetching 2014-01-01 → 2026-08-20
01:10:47 [ERROR] $VO51.DE: possibly delisted; no timezone found
01:10:47 [ERROR]
1 Failed download:
01:10:47 [ERROR] ['VO51.DE']: possibly delisted; no timezone found
01:10:47 [INFO] [VO51.DE] Primary failed — trying fallback: UUUU
01:10:48 [INFO] [VO51.DE] 3176 rows saved
01:10:48 [INFO] [U6Z.DE] Fetching 2014-01-01 → 2026-08-20
01:10:48 [INFO] [U6Z.DE] 3207 rows saved
01:10:48 [INFO] [BA] Fetching 2014-01-01 → 2026-08-20
01:10:49 [INFO] [BA] 3176 rows saved
01:10:49 [INFO] [CAT] Fetching 2014-01-01 → 2026-08-20
01:10:50 [INFO] [CAT] 3176 rows saved
01:10:50 [INFO] [LMT] Fetching 2014-01-01 → 2026-08-20
01:10:50 [INFO] [LMT] 3176 rows saved
01:10:50 [INFO] [RTX] Fetching 2014-01-01 → 2026-08-20
01:10:51 [INFO] [RTX] 3176 rows saved
01:10:51 [INFO] [GE] Fetching 2014-01-01 → 2026-08-20
01:10:53 [INFO] [GE] 3176 rows saved
01:10:53 [INFO] [HON] Fetching 2014-01-01 → 2026-08-20
01:10:53 [INFO] [HON] 3176 rows saved
01:10:53 [INFO] [UPS] Fetching 2014-01-01 → 2026-08-20
01:10:54 [INFO] [UPS] 3176 rows saved
01:10:54 [INFO] [DE] Fetching 2014-01-01 → 2026-08-20
01:10:55 [INFO] [DE] 3176 rows saved
01:10:55 [INFO] [RHM.DE] Fetching 2014-01-01 → 2026-08-20
01:10:56 [INFO] [RHM.DE] 3207 rows saved
01:10:56 [INFO] [EUNL.DE] Fetching 2014-01-01 → 2026-08-20
01:10:57 [INFO] [EUNL.DE] 3206 rows saved
01:10:57 [INFO] [VUSA.DE] Fetching 2014-01-01 → 2026-08-20
01:10:57 [INFO] [VUSA.DE] 2235 rows saved
01:10:57 [INFO] [VWCE.DE] Fetching 2014-01-01 → 2026-08-20
01:10:58 [INFO] [VWCE.DE] 1794 rows saved
01:10:58 [INFO] [EXS1.DE] Fetching 2014-01-01 → 2026-08-20
01:10:58 [INFO] [EXS1.DE] 3205 rows saved
01:10:58 [INFO] [EXXT.DE] Fetching 2014-01-01 → 2026-08-20
01:11:01 [INFO] [EXXT.DE] 3206 rows saved
01:11:01 [INFO] [SPPW.DE] Fetching 2014-01-01 → 2026-08-20
01:11:02 [INFO] [SPPW.DE] 1899 rows saved
01:11:02 [INFO] [IS3N.DE] Fetching 2014-01-01 → 2026-08-20
01:11:02 [INFO] [IS3N.DE] 3094 rows saved
01:11:02 [INFO] [IUSN.DE] Fetching 2014-01-01 → 2026-08-20
01:11:03 [INFO] [IUSN.DE] 2110 rows saved
01:11:03 [INFO] [XDWD.DE] Fetching 2014-01-01 → 2026-08-20
01:11:04 [INFO] [XDWD.DE] 3046 rows saved
01:11:04 [INFO] [ZPRV.DE] Fetching 2014-01-01 → 2026-08-20
01:11:05 [INFO] [ZPRV.DE] 2920 rows saved
01:11:05 [INFO] [DBXD.DE] Fetching 2014-01-01 → 2026-08-20
01:11:06 [INFO] [DBXD.DE] 3206 rows saved
01:11:06 [INFO] [PPFD.SG] Fetching 2014-01-01 → 2026-08-20
01:11:06 [INFO] [PPFD.SG] 452 rows saved
01:11:06 [INFO] fetch_price_data complete: 135/135 tickers loaded
01:11:06 [INFO]   Loaded 135 tickers: ['APC.DE', 'MSF.DE', 'AMZ.DE', 'NVD.DE', 'ABEA.DE', 'FB2A.DE', 'TL0.DE', 'SFC.DE', 'ADB.DE', 'NFC.DE', 'AMD.DE', '1IN.DE', 'QCI.DE', 'AP2.DE', 'MTU.DE', 'TII.DE', 'ORC.DE', 'TSM.DE', 'KLA.DE', 'NOW.DE', 'SNW.DE', 'UT8.DE', 'PYPL.DE', '639.DE', 'SHOP.DE', '1S2.DE', 'SAP.DE', 'ALV.DE', 'SIE.DE', 'BAYN.DE', 'BMW.DE', 'DTE.DE', 'BAS.DE', 'MBG.DE', 'ADS.DE', 'MUV2.DE', 'DBK.DE', 'ENR.DE', 'IFX.DE', 'VOW3.DE', 'RWE.DE', 'CON.DE', 'FRE.DE', 'VNA.DE', 'HEN3.DE', 'BEI.DE', 'ZAL.DE', 'MTX.DE', 'NDX1.DE', 'ARGX.BR', 'UCB.BR', 'SHL.DE', 'COK.DE', 'AIR.DE', 'AZN.L', 'SHELL.AS', 'TTE.PA', 'BP.L', 'ASML.AS', 'NOV.DE', 'S92.DE', '3V64.DE', 'CMC.DE', 'NCB.DE', 'GOS.DE', 'DWD.DE', 'BRYN.DE', 'AXP.DE', 'BLQA.DE', 'KO', 'MCD', 'WMT', 'HD', 'COST', 'NKE', 'SBUX', 'DIS', 'LOW', 'UNH', 'JNJ', 'PFE', 'LLY', 'ABBV', 'MRK', 'AMGN', 'GILD', 'TMO', 'BNTX', 'VRTX', 'AXSM', 'NVS', 'ATAI', 'XOM', 'CVX', 'NEE', 'FSLR', 'GEV', 'CCJ', 'CEG', 'SMR', 'OKLO', 'REP.DE', 'ENB.DE', 'EGI.DE', 'BLM.DE', 'BEP', 'RIO', 'ERO', 'FCX', 'ALB', 'MIN', 'C1E.DE', 'VO51.DE', 'U6Z.DE', 'BA', 'CAT', 'LMT', 'RTX', 'GE', 'HON', 'UPS', 'DE', 'RHM.DE', 'EUNL.DE', 'VUSA.DE', 'VWCE.DE', 'EXS1.DE', 'EXXT.DE', 'SPPW.DE', 'IS3N.DE', 'IUSN.DE', 'XDWD.DE', 'ZPRV.DE', 'DBXD.DE', 'PPFD.SG']
01:11:06 [INFO] Step 1b — Loading macro data…
01:11:07 [INFO]   Macro shape: (4509, 8)
01:11:07 [INFO] Step 1c — Loading fundamentals…
01:11:10 [INFO] Step 1d — Fetching options & short interest (free via yfinance)…
01:11:11 [INFO] Fetching options features for 22/135 US tickers...
01:11:11 [INFO]   Options data: 22 tickers covered
01:11:11 [INFO] Step 2/5 — Training models (walk-forward)…
01:11:11 [INFO]   ── APC.DE ──
01:11:11 [INFO]   [APC.DE] Building features…
01:11:11 [INFO] Feature selection — Stage 1 (variance): 40 → 25 features
01:11:11 [INFO] Feature selection — Stage 2 (correlation): → 24 features (dropped 1 correlated)
01:11:11 [INFO] Feature selection complete: 40 → 24 features selected
01:11:11 [INFO]   [APC.DE] After variance/corr selection: 24 features
01:11:11 [INFO]   [APC.DE] 2742 rows · 15 WF splits · 24 features
01:11:16 [INFO] Logged: 1766826d | APC.DE | Baseline_Random | acc=0.5032 | auc=0.5241 | purge=7d
01:11:16 [INFO] Logged: a68e60a7 | APC.DE | Baseline_Momentum | acc=0.637 | auc=0.5 | purge=7d
01:11:19 [INFO] Logged: a41a5518 | APC.DE | LogisticRegression | acc=0.5698 | auc=0.5906 | purge=7d
01:11:23 [INFO] Feature selection — Stage 1 (variance): 24 → 24 features
01:11:23 [INFO] Feature selection — Stage 2 (correlation): → 24 features (dropped 0 correlated)
01:11:23 [INFO] Feature selection — Stage 3 (importance): → 17 features (dropped 7 low-importance)
01:11:23 [INFO] Feature selection complete: 24 → 17 features selected
01:11:23 [INFO]   [APC.DE] After importance gate: 17 features
01:11:42 [INFO] Logged: dd84b68b | APC.DE | RandomForest | acc=0.5534 | auc=0.4875 | purge=7d
01:12:03 [INFO] Logged: e5de8390 | APC.DE | XGBoost | acc=0.5392 | auc=0.535 | purge=7d
01:12:03 [INFO]   [APC.DE] OK
01:12:03 [INFO]   ── MSF.DE ──
01:12:03 [INFO]   [MSF.DE] Building features…
01:12:04 [INFO] Feature selection — Stage 1 (variance): 40 → 22 features
01:12:04 [INFO] Feature selection — Stage 2 (correlation): → 21 features (dropped 1 correlated)
01:12:04 [INFO] Feature selection complete: 40 → 21 features selected
01:12:04 [INFO]   [MSF.DE] After variance/corr selection: 21 features
01:12:04 [INFO]   [MSF.DE] 2742 rows · 15 WF splits · 21 features
01:12:04 [INFO] Logged: a290c6e8 | MSF.DE | Baseline_Random | acc=0.5079 | auc=0.5122 | purge=7d
01:12:04 [INFO] Logged: 8a4bab90 | MSF.DE | Baseline_Momentum | acc=0.6016 | auc=0.5 | purge=7d
01:12:06 [INFO] Logged: a825f8c5 | MSF.DE | LogisticRegression | acc=0.5778 | auc=0.6107 | purge=7d
01:12:07 [INFO] Feature selection — Stage 1 (variance): 21 → 21 features
01:12:07 [INFO] Feature selection — Stage 2 (correlation): → 21 features (dropped 0 correlated)
01:12:07 [INFO] Feature selection — Stage 3 (importance): → 17 features (dropped 4 low-importance)
01:12:07 [INFO] Feature selection complete: 21 → 17 features selected
01:12:07 [INFO]   [MSF.DE] After importance gate: 17 features
01:12:28 [INFO] Logged: 471c42b6 | MSF.DE | RandomForest | acc=0.5481 | auc=0.6508 | purge=7d
01:12:48 [INFO] Logged: 74bb72bd | MSF.DE | XGBoost | acc=0.5492 | auc=0.6596 | purge=7d
01:12:48 [INFO]   [MSF.DE] OK
01:12:48 [INFO]   ── AMZ.DE ──
01:12:48 [INFO]   [AMZ.DE] Building features…
01:12:49 [INFO] Feature selection — Stage 1 (variance): 40 → 26 features
01:12:49 [INFO] Feature selection — Stage 2 (correlation): → 25 features (dropped 1 correlated)
01:12:49 [INFO] Feature selection complete: 40 → 25 features selected
01:12:49 [INFO]   [AMZ.DE] After variance/corr selection: 25 features
01:12:49 [INFO]   [AMZ.DE] 2742 rows · 15 WF splits · 25 features
01:12:49 [INFO] Logged: 19e1bc82 | AMZ.DE | Baseline_Random | acc=0.5185 | auc=0.5246 | purge=7d
01:12:49 [INFO] Logged: 6d24ff6c | AMZ.DE | Baseline_Momentum | acc=0.6048 | auc=0.5 | purge=7d
01:12:51 [INFO] Logged: 72e19d93 | AMZ.DE | LogisticRegression | acc=0.5513 | auc=0.6452 | purge=7d
01:12:53 [INFO] Feature selection — Stage 1 (variance): 25 → 25 features
01:12:53 [INFO] Feature selection — Stage 2 (correlation): → 25 features (dropped 0 correlated)
01:12:53 [INFO] Feature selection — Stage 3 (importance): → 18 features (dropped 7 low-importance)
01:12:53 [INFO] Feature selection complete: 25 → 18 features selected
01:12:53 [INFO]   [AMZ.DE] After importance gate: 18 features
01:13:13 [INFO] Logged: 58667fd5 | AMZ.DE | RandomForest | acc=0.5825 | auc=0.6341 | purge=7d
01:13:35 [INFO] Logged: 8c165918 | AMZ.DE | XGBoost | acc=0.5683 | auc=0.5925 | purge=7d
01:13:35 [INFO]   [AMZ.DE] OK
01:13:35 [INFO]   ── NVD.DE ──
01:13:35 [INFO]   [NVD.DE] Building features…
01:13:36 [INFO] Feature selection — Stage 1 (variance): 40 → 27 features
01:13:36 [INFO] Feature selection — Stage 2 (correlation): → 26 features (dropped 1 correlated)
01:13:36 [INFO] Feature selection complete: 40 → 26 features selected
01:13:36 [INFO]   [NVD.DE] After variance/corr selection: 26 features
01:13:36 [INFO]   [NVD.DE] 2200 rows · 11 WF splits · 26 features
01:13:36 [INFO] Logged: ba4f13fb | NVD.DE | Baseline_Random | acc=0.5115 | auc=0.5198 | purge=7d
01:13:36 [INFO] Logged: c94299af | NVD.DE | Baseline_Momentum | acc=0.6176 | auc=0.5 | purge=7d
01:13:37 [INFO] Logged: 7d9e16f4 | NVD.DE | LogisticRegression | acc=0.5029 | auc=0.5576 | purge=7d
01:13:39 [INFO] Feature selection — Stage 1 (variance): 26 → 26 features
01:13:39 [INFO] Feature selection — Stage 2 (correlation): → 26 features (dropped 0 correlated)
01:13:39 [INFO] Feature selection — Stage 3 (importance): → 18 features (dropped 8 low-importance)
01:13:39 [INFO] Feature selection complete: 26 → 18 features selected
01:13:39 [INFO]   [NVD.DE] After importance gate: 18 features
01:13:52 [INFO] Logged: be587a40 | NVD.DE | RandomForest | acc=0.5606 | auc=0.5863 | purge=7d
01:14:07 [INFO] Logged: c98378ee | NVD.DE | XGBoost | acc=0.5216 | auc=0.5627 | purge=7d
01:14:07 [INFO]   [NVD.DE] OK
01:14:07 [INFO]   ── ABEA.DE ──
01:14:07 [INFO]   [ABEA.DE] Building features…
01:14:07 [INFO] Feature selection — Stage 1 (variance): 40 → 24 features
01:14:07 [INFO] Feature selection — Stage 2 (correlation): → 23 features (dropped 1 correlated)
01:14:07 [INFO] Feature selection complete: 40 → 23 features selected
01:14:07 [INFO]   [ABEA.DE] After variance/corr selection: 23 features
01:14:07 [INFO]   [ABEA.DE] 2721 rows · 15 WF splits · 23 features
01:14:07 [INFO] Logged: 52ac3207 | ABEA.DE | Baseline_Random | acc=0.5058 | auc=0.4818 | purge=7d
01:14:07 [INFO] Logged: 16471e58 | ABEA.DE | Baseline_Momentum | acc=0.6302 | auc=0.5 | purge=7d
01:14:09 [INFO] Logged: 40369280 | ABEA.DE | LogisticRegression | acc=0.5455 | auc=0.6571 | purge=7d
01:14:11 [INFO] Feature selection — Stage 1 (variance): 23 → 23 features
01:14:11 [INFO] Feature selection — Stage 2 (correlation): → 23 features (dropped 0 correlated)
01:14:11 [INFO] Feature selection — Stage 3 (importance): → 16 features (dropped 7 low-importance)
01:14:11 [INFO] Feature selection complete: 23 → 16 features selected
01:14:11 [INFO]   [ABEA.DE] After importance gate: 16 features
01:14:29 [INFO] Logged: 622a1b07 | ABEA.DE | RandomForest | acc=0.4693 | auc=0.6551 | purge=7d
01:14:51 [INFO] Logged: d209cd13 | ABEA.DE | XGBoost | acc=0.4857 | auc=0.6639 | purge=7d
01:14:51 [INFO]   [ABEA.DE] OK
01:14:51 [INFO]   ── FB2A.DE ──
01:14:51 [INFO]   [FB2A.DE] Building features…
01:14:51 [INFO] Feature selection — Stage 1 (variance): 40 → 26 features
01:14:51 [INFO] Feature selection — Stage 2 (correlation): → 25 features (dropped 1 correlated)
01:14:51 [INFO] Feature selection complete: 40 → 25 features selected
01:14:51 [INFO]   [FB2A.DE] After variance/corr selection: 25 features
01:14:51 [INFO]   [FB2A.DE] 2783 rows · 16 WF splits · 25 features
01:14:51 [INFO] Logged: f66d5c14 | FB2A.DE | Baseline_Random | acc=0.5273 | auc=0.5006 | purge=7d
01:14:51 [INFO] Logged: 94ae150c | FB2A.DE | Baseline_Momentum | acc=0.6096 | auc=0.5 | purge=7d
01:14:53 [INFO] Logged: 7a5eea40 | FB2A.DE | LogisticRegression | acc=0.5124 | auc=0.6548 | purge=7d
01:14:55 [INFO] Feature selection — Stage 1 (variance): 25 → 25 features
01:14:55 [INFO] Feature selection — Stage 2 (correlation): → 25 features (dropped 0 correlated)
01:14:55 [INFO] Feature selection — Stage 3 (importance): → 14 features (dropped 11 low-importance)
01:14:55 [INFO] Feature selection complete: 25 → 14 features selected
01:14:55 [INFO]   [FB2A.DE] After importance gate: 14 features
01:15:14 [INFO] Logged: fcaac96c | FB2A.DE | RandomForest | acc=0.5729 | auc=0.5319 | purge=7d
01:15:34 [INFO] Logged: fe490cc6 | FB2A.DE | XGBoost | acc=0.5089 | auc=0.5629 | purge=7d
01:15:34 [INFO]   [FB2A.DE] OK
01:15:34 [INFO]   ── TL0.DE ──
01:15:34 [INFO]   [TL0.DE] Building features…
01:15:34 [INFO] Feature selection — Stage 1 (variance): 40 → 28 features
01:15:34 [INFO] Feature selection — Stage 2 (correlation): → 27 features (dropped 1 correlated)
01:15:34 [INFO] Feature selection complete: 40 → 27 features selected
01:15:34 [INFO]   [TL0.DE] After variance/corr selection: 27 features
01:15:34 [INFO]   [TL0.DE] 2783 rows · 16 WF splits · 27 features
01:15:34 [INFO] Logged: 6a98130a | TL0.DE | Baseline_Random | acc=0.5188 | auc=0.4916 | purge=7d
01:15:34 [INFO] Logged: 8f270536 | TL0.DE | Baseline_Momentum | acc=0.5456 | auc=0.5 | purge=7d
01:15:35 [INFO] Logged: 01c967d0 | TL0.DE | LogisticRegression | acc=0.5625 | auc=0.5849 | purge=7d
01:15:35 [INFO] Feature selection — Stage 1 (variance): 27 → 27 features
01:15:35 [INFO] Feature selection — Stage 2 (correlation): → 27 features (dropped 0 correlated)
01:15:35 [INFO] Feature selection — Stage 3 (importance): → 17 features (dropped 10 low-importance)
01:15:35 [INFO] Feature selection complete: 27 → 17 features selected
01:15:35 [INFO]   [TL0.DE] After importance gate: 17 features
01:15:56 [INFO] Logged: 2b27cea9 | TL0.DE | RandomForest | acc=0.4931 | auc=0.609 | purge=7d
01:16:16 [INFO] Logged: 5b2ee617 | TL0.DE | XGBoost | acc=0.4598 | auc=0.5485 | purge=7d
01:16:16 [INFO]   [TL0.DE] OK
01:16:16 [INFO]   ── SFC.DE ──
01:16:16 [INFO]   [SFC.DE] Building features…
01:16:16 [WARNING]   [SFC.DE] Too few clean rows; skipping
01:16:16 [INFO]   [SFC.DE] SKIPPED
01:16:16 [INFO]   ── ADB.DE ──
01:16:16 [INFO]   [ADB.DE] Building features…
01:16:17 [INFO] Feature selection — Stage 1 (variance): 40 → 26 features
01:16:17 [INFO] Feature selection — Stage 2 (correlation): → 25 features (dropped 1 correlated)
01:16:17 [INFO] Feature selection complete: 40 → 25 features selected
01:16:17 [INFO]   [ADB.DE] After variance/corr selection: 25 features
01:16:17 [INFO]   [ADB.DE] 1645 rows · 7 WF splits · 25 features
01:16:17 [INFO] Logged: caa62d4c | ADB.DE | Baseline_Random | acc=0.4841 | auc=0.5121 | purge=7d
01:16:17 [INFO] Logged: 14b9485e | ADB.DE | Baseline_Momentum | acc=0.4603 | auc=0.5 | purge=7d
01:16:18 [INFO] Logged: f07f75cc | ADB.DE | LogisticRegression | acc=0.5329 | auc=0.6116 | purge=7d
01:16:19 [INFO] Feature selection — Stage 1 (variance): 25 → 25 features
01:16:19 [INFO] Feature selection — Stage 2 (correlation): → 25 features (dropped 0 correlated)
01:16:19 [INFO] Feature selection — Stage 3 (importance): → 18 features (dropped 7 low-importance)
01:16:19 [INFO] Feature selection complete: 25 → 18 features selected
01:16:19 [INFO]   [ADB.DE] After importance gate: 18 features
01:16:28 [INFO] Logged: bf210d51 | ADB.DE | RandomForest | acc=0.4365 | auc=0.6149 | purge=7d
01:16:34 [INFO] Logged: 6a996d27 | ADB.DE | XGBoost | acc=0.5136 | auc=0.6005 | purge=7d
01:16:34 [INFO]   [ADB.DE] OK
01:16:34 [INFO]   ── NFC.DE ──
01:16:34 [INFO]   [NFC.DE] Building features…
01:16:34 [INFO] Feature selection — Stage 1 (variance): 40 → 27 features
01:16:34 [INFO] Feature selection — Stage 2 (correlation): → 26 features (dropped 1 correlated)
01:16:34 [INFO] Feature selection complete: 40 → 26 features selected
01:16:34 [INFO]   [NFC.DE] After variance/corr selection: 26 features
01:16:34 [INFO]   [NFC.DE] 2726 rows · 15 WF splits · 26 features
01:16:35 [INFO] Logged: edc02063 | NFC.DE | Baseline_Random | acc=0.4894 | auc=0.5 | purge=7d
01:16:35 [INFO] Logged: 27a12ae3 | NFC.DE | Baseline_Momentum | acc=0.5725 | auc=0.5 | purge=7d
01:16:36 [INFO] Logged: 5157c3a6 | NFC.DE | LogisticRegression | acc=0.5069 | auc=0.5854 | purge=7d
01:16:37 [INFO] Feature selection — Stage 1 (variance): 26 → 26 features
01:16:37 [INFO] Feature selection — Stage 2 (correlation): → 26 features (dropped 0 correlated)
01:16:37 [INFO] Feature selection — Stage 3 (importance): → 19 features (dropped 7 low-importance)
01:16:37 [INFO] Feature selection complete: 26 → 19 features selected
01:16:37 [INFO]   [NFC.DE] After importance gate: 19 features
01:16:51 [INFO] Logged: 3b7b2abe | NFC.DE | RandomForest | acc=0.5222 | auc=0.5613 | purge=7d
01:17:15 [INFO] Logged: 14890e20 | NFC.DE | XGBoost | acc=0.5302 | auc=0.585 | purge=7d
01:17:15 [INFO]   [NFC.DE] OK
01:17:15 [INFO]   ── AMD.DE ──
01:17:15 [INFO]   [AMD.DE] Building features…
01:17:15 [INFO] Feature selection — Stage 1 (variance): 40 → 28 features
01:17:15 [INFO] Feature selection — Stage 2 (correlation): → 27 features (dropped 1 correlated)
01:17:15 [INFO] Feature selection complete: 40 → 27 features selected
01:17:15 [INFO]   [AMD.DE] After variance/corr selection: 27 features
01:17:15 [INFO]   [AMD.DE] 2637 rows · 14 WF splits · 27 features
01:17:15 [INFO] Logged: e898779d | AMD.DE | Baseline_Random | acc=0.5079 | auc=0.4869 | purge=7d
01:17:15 [INFO] Logged: a652e5b3 | AMD.DE | Baseline_Momentum | acc=0.5476 | auc=0.5 | purge=7d
01:17:17 [INFO] Logged: 088a2c9d | AMD.DE | LogisticRegression | acc=0.5147 | auc=0.6543 | purge=7d
01:17:19 [INFO] Feature selection — Stage 1 (variance): 27 → 27 features
01:17:19 [INFO] Feature selection — Stage 2 (correlation): → 27 features (dropped 0 correlated)
01:17:19 [INFO] Feature selection — Stage 3 (importance): → 17 features (dropped 10 low-importance)
01:17:19 [INFO] Feature selection complete: 27 → 17 features selected
01:17:19 [INFO]   [AMD.DE] After importance gate: 17 features
01:17:39 [INFO] Logged: 442bb5d6 | AMD.DE | RandomForest | acc=0.445 | auc=0.6012 | purge=7d
01:18:03 [INFO] Logged: 9e14850e | AMD.DE | XGBoost | acc=0.4807 | auc=0.6406 | purge=7d
01:18:03 [INFO]   [AMD.DE] OK
01:18:03 [INFO]   ── 1IN.DE ──
01:18:03 [INFO]   [1IN.DE] Building features…
01:18:03 [WARNING]   [1IN.DE] Too few clean rows; skipping
01:18:03 [INFO]   [1IN.DE] SKIPPED
01:18:03 [INFO]   ── QCI.DE ──
01:18:03 [INFO]   [QCI.DE] Building features…
01:18:03 [INFO] Feature selection — Stage 1 (variance): 40 → 27 features
01:18:03 [INFO] Feature selection — Stage 2 (correlation): → 26 features (dropped 1 correlated)
01:18:03 [INFO] Feature selection complete: 40 → 26 features selected
01:18:03 [INFO]   [QCI.DE] After variance/corr selection: 26 features
01:18:03 [INFO]   [QCI.DE] 2537 rows · 14 WF splits · 26 features
01:18:03 [INFO] Logged: 0e9104b5 | QCI.DE | Baseline_Random | acc=0.5136 | auc=0.5186 | purge=7d
01:18:04 [INFO] Logged: 543f05b1 | QCI.DE | Baseline_Momentum | acc=0.5522 | auc=0.5 | purge=7d
01:18:05 [INFO] Logged: 07a5936b | QCI.DE | LogisticRegression | acc=0.4637 | auc=0.5683 | purge=7d
01:18:07 [INFO] Feature selection — Stage 1 (variance): 26 → 26 features
01:18:07 [INFO] Feature selection — Stage 2 (correlation): → 26 features (dropped 0 correlated)
01:18:07 [INFO] Feature selection — Stage 3 (importance): → 18 features (dropped 8 low-importance)
01:18:07 [INFO] Feature selection complete: 26 → 18 features selected
01:18:07 [INFO]   [QCI.DE] After importance gate: 18 features
01:18:27 [INFO] Logged: e590ff68 | QCI.DE | RandomForest | acc=0.4722 | auc=0.6077 | purge=7d
01:18:49 [INFO] Logged: 4d53d8a8 | QCI.DE | XGBoost | acc=0.4983 | auc=0.6332 | purge=7d
01:18:49 [INFO]   [QCI.DE] OK
01:18:49 [INFO]   ── AP2.DE ──
01:18:49 [INFO]   [AP2.DE] Building features…
01:18:49 [INFO] Feature selection — Stage 1 (variance): 40 → 27 features
01:18:49 [INFO] Feature selection — Stage 2 (correlation): → 26 features (dropped 1 correlated)
01:18:49 [INFO] Feature selection complete: 40 → 26 features selected
01:18:49 [INFO]   [AP2.DE] After variance/corr selection: 26 features
01:18:49 [INFO]   [AP2.DE] 1787 rows · 8 WF splits · 26 features
01:18:49 [INFO] Logged: 929c6d7b | AP2.DE | Baseline_Random | acc=0.5119 | auc=0.4996 | purge=7d
01:18:49 [INFO] Logged: 356f078e | AP2.DE | Baseline_Momentum | acc=0.5813 | auc=0.5 | purge=7d
01:18:50 [INFO] Logged: 01c36714 | AP2.DE | LogisticRegression | acc=0.497 | auc=0.52 | purge=7d
01:18:52 [INFO] Feature selection — Stage 1 (variance): 26 → 26 features
01:18:52 [INFO] Feature selection — Stage 2 (correlation): → 26 features (dropped 0 correlated)
01:18:52 [INFO] Feature selection — Stage 3 (importance): → 18 features (dropped 8 low-importance)
01:18:52 [INFO] Feature selection complete: 26 → 18 features selected
01:18:52 [INFO]   [AP2.DE] After importance gate: 18 features
01:19:03 [INFO] Logged: e6981d9d | AP2.DE | RandomForest | acc=0.4901 | auc=0.5147 | purge=7d
01:19:17 [INFO] Logged: 9fb42367 | AP2.DE | XGBoost | acc=0.4683 | auc=0.5451 | purge=7d
01:19:17 [INFO]   [AP2.DE] OK
01:19:17 [INFO]   ── MTU.DE ──
01:19:17 [INFO]   [MTU.DE] Building features…
01:19:17 [WARNING]   [MTU.DE] Too few clean rows; skipping
01:19:17 [INFO]   [MTU.DE] SKIPPED
01:19:17 [INFO]   ── TII.DE ──
01:19:17 [INFO]   [TII.DE] Building features…
01:19:17 [INFO] Feature selection — Stage 1 (variance): 40 → 26 features
01:19:17 [INFO] Feature selection — Stage 2 (correlation): → 26 features (dropped 0 correlated)
01:19:17 [INFO] Feature selection complete: 40 → 26 features selected
01:19:17 [INFO]   [TII.DE] After variance/corr selection: 26 features
01:19:17 [INFO]   [TII.DE] 947 rows · 1 WF splits · 26 features
01:19:17 [INFO] Logged: f74158b8 | TII.DE | Baseline_Random | acc=0.5714 | auc=0.5292 | purge=7d
01:19:17 [INFO] Logged: a8dd585f | TII.DE | Baseline_Momentum | acc=0.627 | auc=0.5 | purge=7d
01:19:18 [INFO] Logged: 2b0ca366 | TII.DE | LogisticRegression | acc=0.3413 | auc=0.4368 | purge=7d
01:19:19 [INFO] Feature selection — Stage 1 (variance): 26 → 26 features
01:19:19 [INFO] Feature selection — Stage 2 (correlation): → 26 features (dropped 0 correlated)
01:19:19 [INFO] Feature selection — Stage 3 (importance): → 21 features (dropped 5 low-importance)
01:19:19 [INFO] Feature selection complete: 26 → 21 features selected
01:19:19 [INFO]   [TII.DE] After importance gate: 21 features
01:19:20 [INFO] Logged: 5dff65fe | TII.DE | RandomForest | acc=0.3413 | auc=0.5093 | purge=7d
01:19:21 [INFO] Logged: 597c77dc | TII.DE | XGBoost | acc=0.5317 | auc=0.488 | purge=7d
01:19:21 [INFO]   [TII.DE] OK
01:19:21 [INFO]   ── ORC.DE ──
01:19:21 [INFO]   [ORC.DE] Building features…
01:19:22 [INFO] Feature selection — Stage 1 (variance): 40 → 26 features
01:19:22 [INFO] Feature selection — Stage 2 (correlation): → 24 features (dropped 2 correlated)
01:19:22 [INFO] Feature selection complete: 40 → 24 features selected
01:19:22 [INFO]   [ORC.DE] After variance/corr selection: 24 features
01:19:22 [INFO]   [ORC.DE] 2171 rows · 11 WF splits · 24 features
01:19:22 [INFO] Logged: ac50d465 | ORC.DE | Baseline_Random | acc=0.5058 | auc=0.4922 | purge=7d
01:19:22 [INFO] Logged: b01205c9 | ORC.DE | Baseline_Momentum | acc=0.5671 | auc=0.5 | purge=7d
01:19:23 [INFO] Logged: a4b235cd | ORC.DE | LogisticRegression | acc=0.575 | auc=0.6803 | purge=7d
01:19:25 [INFO] Feature selection — Stage 1 (variance): 24 → 24 features
01:19:25 [INFO] Feature selection — Stage 2 (correlation): → 24 features (dropped 0 correlated)
01:19:25 [INFO] Feature selection — Stage 3 (importance): → 16 features (dropped 8 low-importance)
01:19:25 [INFO] Feature selection complete: 24 → 16 features selected
01:19:25 [INFO]   [ORC.DE] After importance gate: 16 features
01:19:40 [INFO] Logged: a8e6cbca | ORC.DE | RandomForest | acc=0.5173 | auc=0.7027 | purge=7d
01:19:54 [INFO] Logged: 3e6e2471 | ORC.DE | XGBoost | acc=0.5368 | auc=0.709 | purge=7d
01:19:54 [INFO]   [ORC.DE] OK
01:19:54 [INFO]   ── TSM.DE ──
01:19:54 [INFO]   [TSM.DE] Building features…
01:19:54 [WARNING]   [TSM.DE] Too few clean rows; skipping
01:19:54 [INFO]   [TSM.DE] SKIPPED
01:19:54 [INFO]   ── KLA.DE ──
01:19:54 [INFO]   [KLA.DE] Building features…
01:19:54 [INFO] Feature selection — Stage 1 (variance): 40 → 26 features
01:19:54 [INFO] Feature selection — Stage 2 (correlation): → 26 features (dropped 0 correlated)
01:19:54 [INFO] Feature selection complete: 40 → 26 features selected
01:19:54 [INFO]   [KLA.DE] After variance/corr selection: 26 features
01:19:54 [WARNING] walk_forward_splits: only 389 rows — insufficient for train=756 + buffer=7 + val=126. Returning 0 splits.
01:19:54 [WARNING]   [KLA.DE] Not enough data for walk-forward splits
01:19:54 [INFO]   [KLA.DE] SKIPPED
01:19:54 [INFO]   ── NOW.DE ──
01:19:54 [INFO]   [NOW.DE] Building features…
01:19:54 [WARNING]   [NOW.DE] Too few clean rows; skipping
01:19:54 [INFO]   [NOW.DE] SKIPPED
01:19:54 [INFO]   ── SNW.DE ──
01:19:54 [INFO]   [SNW.DE] Building features…
01:19:54 [INFO] Feature selection — Stage 1 (variance): 40 → 23 features
01:19:54 [INFO] Feature selection — Stage 2 (correlation): → 22 features (dropped 1 correlated)
01:19:54 [INFO] Feature selection complete: 40 → 22 features selected
01:19:54 [INFO]   [SNW.DE] After variance/corr selection: 22 features
01:19:54 [INFO]   [SNW.DE] 2742 rows · 15 WF splits · 22 features
01:19:55 [INFO] Logged: 9a15baa6 | SNW.DE | Baseline_Random | acc=0.4989 | auc=0.5005 | purge=7d
01:19:55 [INFO] Logged: c582d353 | SNW.DE | Baseline_Momentum | acc=0.5757 | auc=0.5 | purge=7d
01:19:57 [INFO] Logged: de86378c | SNW.DE | LogisticRegression | acc=0.5624 | auc=0.6596 | purge=7d
01:19:58 [INFO] Feature selection — Stage 1 (variance): 22 → 22 features
01:19:58 [INFO] Feature selection — Stage 2 (correlation): → 22 features (dropped 0 correlated)
01:19:58 [INFO] Feature selection — Stage 3 (importance): → 16 features (dropped 6 low-importance)
01:19:58 [INFO] Feature selection complete: 22 → 16 features selected
01:19:58 [INFO]   [SNW.DE] After importance gate: 16 features
01:20:18 [INFO] Logged: 9d506c9e | SNW.DE | RandomForest | acc=0.5884 | auc=0.6555 | purge=7d
01:20:36 [INFO] Logged: cdf02c4b | SNW.DE | XGBoost | acc=0.5841 | auc=0.6665 | purge=7d
01:20:36 [INFO]   [SNW.DE] OK
01:20:36 [INFO]   ── UT8.DE ──
01:20:36 [INFO]   [UT8.DE] Building features…
01:20:36 [INFO] Feature selection — Stage 1 (variance): 40 → 27 features
01:20:36 [INFO] Feature selection — Stage 2 (correlation): → 26 features (dropped 1 correlated)
01:20:36 [INFO] Feature selection complete: 40 → 26 features selected
01:20:36 [INFO]   [UT8.DE] After variance/corr selection: 26 features
01:20:36 [INFO]   [UT8.DE] 1491 rows · 5 WF splits · 26 features
01:20:36 [INFO] Logged: 33e8565c | UT8.DE | Baseline_Random | acc=0.5254 | auc=0.5189 | purge=7d
01:20:36 [INFO] Logged: 0085dc5e | UT8.DE | Baseline_Momentum | acc=0.5492 | auc=0.5 | purge=7d
01:20:37 [INFO] Logged: bd0c2cc8 | UT8.DE | LogisticRegression | acc=0.5698 | auc=0.5942 | purge=7d
01:20:39 [INFO] Feature selection — Stage 1 (variance): 26 → 26 features
01:20:39 [INFO] Feature selection — Stage 2 (correlation): → 26 features (dropped 0 correlated)
01:20:39 [INFO] Feature selection — Stage 3 (importance): → 19 features (dropped 7 low-importance)
01:20:39 [INFO] Feature selection complete: 26 → 19 features selected
01:20:39 [INFO]   [UT8.DE] After importance gate: 19 features
01:20:45 [INFO] Logged: 6cc79e86 | UT8.DE | RandomForest | acc=0.5381 | auc=0.4739 | purge=7d
01:20:51 [INFO] Logged: e892417f | UT8.DE | XGBoost | acc=0.5429 | auc=0.4681 | purge=7d
01:20:51 [INFO]   [UT8.DE] OK
01:20:51 [INFO]   ── PYPL.DE ──
01:20:51 [INFO]   [PYPL.DE] Building features…
01:20:51 [WARNING]   [PYPL.DE] Too few clean rows; skipping
01:20:51 [INFO]   [PYPL.DE] SKIPPED
01:20:51 [INFO]   ── 639.DE ──
01:20:51 [INFO]   [639.DE] Building features…
01:20:52 [WARNING]   [639.DE] Too few clean rows; skipping
01:20:52 [INFO]   [639.DE] SKIPPED
01:20:52 [INFO]   ── SHOP.DE ──
01:20:52 [INFO]   [SHOP.DE] Building features…
01:20:52 [WARNING]   [SHOP.DE] Too few clean rows; skipping
01:20:52 [INFO]   [SHOP.DE] SKIPPED
01:20:52 [INFO]   ── 1S2.DE ──
01:20:52 [INFO]   [1S2.DE] Building features…
01:20:52 [WARNING]   [1S2.DE] Too few rows (0); skipping
01:20:52 [INFO]   [1S2.DE] SKIPPED
01:20:52 [INFO]   ── SAP.DE ──
01:20:52 [INFO]   [SAP.DE] Building features…
01:20:52 [INFO] Feature selection — Stage 1 (variance): 40 → 25 features
01:20:52 [INFO] Feature selection — Stage 2 (correlation): → 24 features (dropped 1 correlated)
01:20:52 [INFO] Feature selection complete: 40 → 24 features selected
01:20:52 [INFO]   [SAP.DE] After variance/corr selection: 24 features
01:20:52 [INFO]   [SAP.DE] 2783 rows · 16 WF splits · 24 features
01:20:53 [INFO] Logged: 8b1a04b7 | SAP.DE | Baseline_Random | acc=0.5104 | auc=0.5098 | purge=7d
01:20:53 [INFO] Logged: cd9db44d | SAP.DE | Baseline_Momentum | acc=0.5769 | auc=0.5 | purge=7d
01:20:56 [INFO] Logged: 14d3750a | SAP.DE | LogisticRegression | acc=0.5719 | auc=0.6428 | purge=7d
01:20:58 [INFO] Feature selection — Stage 1 (variance): 24 → 24 features
01:20:58 [INFO] Feature selection — Stage 2 (correlation): → 24 features (dropped 0 correlated)
01:20:58 [INFO] Feature selection — Stage 3 (importance): → 14 features (dropped 10 low-importance)
01:20:58 [INFO] Feature selection complete: 24 → 14 features selected
01:20:58 [INFO]   [SAP.DE] After importance gate: 14 features
01:21:18 [INFO] Logged: 0e30f39b | SAP.DE | RandomForest | acc=0.5466 | auc=0.5546 | purge=7d
01:21:40 [INFO] Logged: bc79c361 | SAP.DE | XGBoost | acc=0.5407 | auc=0.5995 | purge=7d
01:21:40 [INFO]   [SAP.DE] OK
01:21:40 [INFO]   ── ALV.DE ──
01:21:40 [INFO]   [ALV.DE] Building features…
01:21:41 [INFO] Feature selection — Stage 1 (variance): 40 → 24 features
01:21:41 [INFO] Feature selection — Stage 2 (correlation): → 23 features (dropped 1 correlated)
01:21:41 [INFO] Feature selection complete: 40 → 23 features selected
01:21:41 [INFO]   [ALV.DE] After variance/corr selection: 23 features
01:21:41 [INFO]   [ALV.DE] 2783 rows · 16 WF splits · 23 features
01:21:42 [INFO] Logged: 89541f14 | ALV.DE | Baseline_Random | acc=0.5129 | auc=0.496 | purge=7d
01:21:42 [INFO] Logged: 0bac5a1b | ALV.DE | Baseline_Momentum | acc=0.6101 | auc=0.5 | purge=7d
01:21:44 [INFO] Logged: 95ef2ae0 | ALV.DE | LogisticRegression | acc=0.5799 | auc=0.6631 | purge=7d
01:21:46 [INFO] Feature selection — Stage 1 (variance): 23 → 23 features
01:21:46 [INFO] Feature selection — Stage 2 (correlation): → 23 features (dropped 0 correlated)
01:21:46 [INFO] Feature selection — Stage 3 (importance): → 17 features (dropped 6 low-importance)
01:21:46 [INFO] Feature selection complete: 23 → 17 features selected
01:21:46 [INFO]   [ALV.DE] After importance gate: 17 features
01:22:10 [INFO] Logged: 2cf4bb89 | ALV.DE | RandomForest | acc=0.5258 | auc=0.6872 | purge=7d
01:22:29 [INFO] Logged: 4ecd10de | ALV.DE | XGBoost | acc=0.5342 | auc=0.6747 | purge=7d
01:22:29 [INFO]   [ALV.DE] OK
01:22:29 [INFO]   ── SIE.DE ──
01:22:29 [INFO]   [SIE.DE] Building features…
01:22:29 [INFO] Feature selection — Stage 1 (variance): 40 → 25 features
01:22:29 [INFO] Feature selection — Stage 2 (correlation): → 24 features (dropped 1 correlated)
01:22:29 [INFO] Feature selection complete: 40 → 24 features selected
01:22:29 [INFO]   [SIE.DE] After variance/corr selection: 24 features
01:22:29 [INFO]   [SIE.DE] 2783 rows · 16 WF splits · 24 features
01:22:30 [INFO] Logged: 4176eec4 | SIE.DE | Baseline_Random | acc=0.5025 | auc=0.5093 | purge=7d
01:22:30 [INFO] Logged: 48e2d70f | SIE.DE | Baseline_Momentum | acc=0.5809 | auc=0.5 | purge=7d
01:22:32 [INFO] Logged: 9beae75b | SIE.DE | LogisticRegression | acc=0.5377 | auc=0.6494 | purge=7d
01:22:33 [INFO] Feature selection — Stage 1 (variance): 24 → 24 features
01:22:33 [INFO] Feature selection — Stage 2 (correlation): → 24 features (dropped 0 correlated)
01:22:33 [INFO] Feature selection — Stage 3 (importance): → 17 features (dropped 7 low-importance)
01:22:33 [INFO] Feature selection complete: 24 → 17 features selected
01:22:33 [INFO]   [SIE.DE] After importance gate: 17 features
01:22:53 [INFO] Logged: cb025b79 | SIE.DE | RandomForest | acc=0.5288 | auc=0.5749 | purge=7d
01:23:13 [INFO] Logged: 26737727 | SIE.DE | XGBoost | acc=0.5188 | auc=0.6459 | purge=7d
01:23:13 [INFO]   [SIE.DE] OK
01:23:13 [INFO]   ── BAYN.DE ──
01:23:13 [INFO]   [BAYN.DE] Building features…
01:23:13 [WARNING]   [BAYN.DE] Too few clean rows; skipping
01:23:13 [INFO]   [BAYN.DE] SKIPPED
01:23:13 [INFO]   ── BMW.DE ──
01:23:13 [INFO]   [BMW.DE] Building features…
01:23:13 [INFO] Feature selection — Stage 1 (variance): 40 → 25 features
01:23:13 [INFO] Feature selection — Stage 2 (correlation): → 24 features (dropped 1 correlated)
01:23:13 [INFO] Feature selection complete: 40 → 24 features selected
01:23:13 [INFO]   [BMW.DE] After variance/corr selection: 24 features
01:23:13 [INFO]   [BMW.DE] 2783 rows · 16 WF splits · 24 features
01:23:13 [INFO] Logged: 62d153b7 | BMW.DE | Baseline_Random | acc=0.496 | auc=0.4971 | purge=7d
01:23:14 [INFO] Logged: 9dba1124 | BMW.DE | Baseline_Momentum | acc=0.5198 | auc=0.5 | purge=7d
01:23:15 [INFO] Logged: 66ce9ee9 | BMW.DE | LogisticRegression | acc=0.4886 | auc=0.5704 | purge=7d
01:23:17 [INFO] Feature selection — Stage 1 (variance): 24 → 24 features
01:23:17 [INFO] Feature selection — Stage 2 (correlation): → 24 features (dropped 0 correlated)
01:23:17 [INFO] Feature selection — Stage 3 (importance): → 19 features (dropped 5 low-importance)
01:23:17 [INFO] Feature selection complete: 24 → 19 features selected
01:23:17 [INFO]   [BMW.DE] After importance gate: 19 features
01:23:38 [INFO] Logged: c8ce2d07 | BMW.DE | RandomForest | acc=0.4603 | auc=0.5756 | purge=7d
01:23:59 [INFO] Logged: 8ac3c313 | BMW.DE | XGBoost | acc=0.4911 | auc=0.5595 | purge=7d
01:23:59 [INFO]   [BMW.DE] OK
01:23:59 [INFO]   ── DTE.DE ──
01:23:59 [INFO]   [DTE.DE] Building features…
01:23:59 [INFO] Feature selection — Stage 1 (variance): 40 → 23 features
01:23:59 [INFO] Feature selection — Stage 2 (correlation): → 22 features (dropped 1 correlated)
01:23:59 [INFO] Feature selection complete: 40 → 22 features selected
01:23:59 [INFO]   [DTE.DE] After variance/corr selection: 22 features
01:23:59 [INFO]   [DTE.DE] 2762 rows · 15 WF splits · 22 features
01:23:59 [INFO] Logged: a9ff17f2 | DTE.DE | Baseline_Random | acc=0.5116 | auc=0.5207 | purge=7d
01:23:59 [INFO] Logged: 5b8856df | DTE.DE | Baseline_Momentum | acc=0.5989 | auc=0.5 | purge=7d
01:24:01 [INFO] Logged: ec216fa1 | DTE.DE | LogisticRegression | acc=0.5656 | auc=0.606 | purge=7d
01:24:03 [INFO] Feature selection — Stage 1 (variance): 22 → 22 features
01:24:03 [INFO] Feature selection — Stage 2 (correlation): → 22 features (dropped 0 correlated)
01:24:03 [INFO] Feature selection — Stage 3 (importance): → 13 features (dropped 9 low-importance)
01:24:03 [INFO] Feature selection complete: 22 → 13 features selected
01:24:03 [INFO]   [DTE.DE] After importance gate: 13 features
01:24:23 [INFO] Logged: 85443a65 | DTE.DE | RandomForest | acc=0.5344 | auc=0.6684 | purge=7d
01:24:42 [INFO] Logged: 9f299e37 | DTE.DE | XGBoost | acc=0.5243 | auc=0.6622 | purge=7d
01:24:42 [INFO]   [DTE.DE] OK
01:24:42 [INFO]   ── BAS.DE ──
01:24:42 [INFO]   [BAS.DE] Building features…
01:24:42 [INFO] Feature selection — Stage 1 (variance): 40 → 25 features
01:24:42 [INFO] Feature selection — Stage 2 (correlation): → 24 features (dropped 1 correlated)
01:24:42 [INFO] Feature selection complete: 40 → 24 features selected
01:24:42 [INFO]   [BAS.DE] After variance/corr selection: 24 features
01:24:42 [INFO]   [BAS.DE] 2783 rows · 16 WF splits · 24 features
01:24:43 [INFO] Logged: b7301c58 | BAS.DE | Baseline_Random | acc=0.494 | auc=0.5091 | purge=7d
01:24:43 [INFO] Logged: b525b983 | BAS.DE | Baseline_Momentum | acc=0.506 | auc=0.5 | purge=7d
01:24:44 [INFO] Logged: c56ae089 | BAS.DE | LogisticRegression | acc=0.5288 | auc=0.5621 | purge=7d
01:24:46 [INFO] Feature selection — Stage 1 (variance): 24 → 24 features
01:24:46 [INFO] Feature selection — Stage 2 (correlation): → 24 features (dropped 0 correlated)
01:24:46 [INFO] Feature selection — Stage 3 (importance): → 17 features (dropped 7 low-importance)
01:24:46 [INFO] Feature selection complete: 24 → 17 features selected
01:24:46 [INFO]   [BAS.DE] After importance gate: 17 features
01:25:06 [INFO] Logged: 8956204f | BAS.DE | RandomForest | acc=0.5035 | auc=0.6048 | purge=7d
01:25:29 [INFO] Logged: 91b85684 | BAS.DE | XGBoost | acc=0.4985 | auc=0.6666 | purge=7d
01:25:29 [INFO]   [BAS.DE] OK
01:25:29 [INFO]   ── MBG.DE ──
01:25:29 [INFO]   [MBG.DE] Building features…
01:25:29 [INFO] Feature selection — Stage 1 (variance): 40 → 26 features
01:25:29 [INFO] Feature selection — Stage 2 (correlation): → 25 features (dropped 1 correlated)
01:25:29 [INFO] Feature selection complete: 40 → 25 features selected
01:25:29 [INFO]   [MBG.DE] After variance/corr selection: 25 features
01:25:29 [INFO]   [MBG.DE] 2783 rows · 16 WF splits · 25 features
01:25:29 [INFO] Logged: 69b70233 | MBG.DE | Baseline_Random | acc=0.501 | auc=0.5023 | purge=7d
01:25:30 [INFO] Logged: 0ba23638 | MBG.DE | Baseline_Momentum | acc=0.5337 | auc=0.5 | purge=7d
01:25:32 [INFO] Logged: 7a04e53e | MBG.DE | LogisticRegression | acc=0.434 | auc=0.5147 | purge=7d
01:25:33 [INFO] Feature selection — Stage 1 (variance): 25 → 25 features
01:25:33 [INFO] Feature selection — Stage 2 (correlation): → 25 features (dropped 0 correlated)
01:25:33 [INFO] Feature selection — Stage 3 (importance): → 17 features (dropped 8 low-importance)
01:25:33 [INFO] Feature selection complete: 25 → 17 features selected
01:25:33 [INFO]   [MBG.DE] After importance gate: 17 features
01:25:55 [INFO] Logged: 4596bc54 | MBG.DE | RandomForest | acc=0.5074 | auc=0.6101 | purge=7d
01:26:14 [INFO] Logged: 69287e5f | MBG.DE | XGBoost | acc=0.4668 | auc=0.6114 | purge=7d
01:26:14 [INFO]   [MBG.DE] OK
01:26:14 [INFO]   ── ADS.DE ──
01:26:14 [INFO]   [ADS.DE] Building features…
01:26:15 [WARNING]   [ADS.DE] Too few clean rows; skipping
01:26:15 [INFO]   [ADS.DE] SKIPPED
01:26:15 [INFO]   ── MUV2.DE ──
01:26:15 [INFO]   [MUV2.DE] Building features…
01:26:15 [WARNING]   [MUV2.DE] Too few clean rows; skipping
01:26:15 [INFO]   [MUV2.DE] SKIPPED
01:26:15 [INFO]   ── DBK.DE ──
01:26:15 [INFO]   [DBK.DE] Building features…
01:26:15 [WARNING]   [DBK.DE] Too few clean rows; skipping
01:26:15 [INFO]   [DBK.DE] SKIPPED
01:26:15 [INFO]   ── ENR.DE ──
01:26:15 [INFO]   [ENR.DE] Building features…
01:26:15 [INFO] Feature selection — Stage 1 (variance): 40 → 27 features
01:26:15 [INFO] Feature selection — Stage 2 (correlation): → 27 features (dropped 0 correlated)
01:26:15 [INFO] Feature selection complete: 40 → 27 features selected
01:26:15 [INFO]   [ENR.DE] After variance/corr selection: 27 features
01:26:15 [INFO]   [ENR.DE] 1179 rows · 3 WF splits · 27 features
01:26:15 [INFO] Logged: 66b055d3 | ENR.DE | Baseline_Random | acc=0.5317 | auc=0.4826 | purge=7d
01:26:15 [INFO] Logged: 71e96ba8 | ENR.DE | Baseline_Momentum | acc=0.7989 | auc=0.5 | purge=7d
01:26:16 [INFO] Logged: 07d658fb | ENR.DE | LogisticRegression | acc=0.6111 | auc=0.4645 | purge=7d
01:26:17 [INFO] Feature selection — Stage 1 (variance): 27 → 27 features
01:26:17 [INFO] Feature selection — Stage 2 (correlation): → 27 features (dropped 0 correlated)
01:26:17 [INFO] Feature selection — Stage 3 (importance): → 17 features (dropped 10 low-importance)
01:26:17 [INFO] Feature selection complete: 27 → 17 features selected
01:26:17 [INFO]   [ENR.DE] After importance gate: 17 features
01:26:20 [INFO] Logged: f67f2f55 | ENR.DE | RandomForest | acc=0.6402 | auc=0.3979 | purge=7d
01:26:23 [INFO] Logged: 3ef89799 | ENR.DE | XGBoost | acc=0.6005 | auc=0.4904 | purge=7d
01:26:23 [INFO]   [ENR.DE] OK
01:26:23 [INFO]   ── IFX.DE ──
01:26:23 [INFO]   [IFX.DE] Building features…
01:26:23 [WARNING]   [IFX.DE] Too few clean rows; skipping
01:26:23 [INFO]   [IFX.DE] SKIPPED
01:26:23 [INFO]   ── VOW3.DE ──
01:26:23 [INFO]   [VOW3.DE] Building features…
01:26:23 [INFO] Feature selection — Stage 1 (variance): 40 → 26 features
01:26:23 [INFO] Feature selection — Stage 2 (correlation): → 25 features (dropped 1 correlated)
01:26:23 [INFO] Feature selection complete: 40 → 25 features selected
01:26:23 [INFO]   [VOW3.DE] After variance/corr selection: 25 features
01:26:23 [INFO]   [VOW3.DE] 2783 rows · 16 WF splits · 25 features
01:26:24 [INFO] Logged: 201a248f | VOW3.DE | Baseline_Random | acc=0.505 | auc=0.5044 | purge=7d
01:26:24 [INFO] Logged: ed97e79a | VOW3.DE | Baseline_Momentum | acc=0.5079 | auc=0.5 | purge=7d
01:26:25 [INFO] Logged: 90316ab4 | VOW3.DE | LogisticRegression | acc=0.496 | auc=0.6216 | purge=7d
01:26:26 [INFO] Feature selection — Stage 1 (variance): 25 → 25 features
01:26:26 [INFO] Feature selection — Stage 2 (correlation): → 25 features (dropped 0 correlated)
01:26:26 [INFO] Feature selection — Stage 3 (importance): → 16 features (dropped 9 low-importance)
01:26:26 [INFO] Feature selection complete: 25 → 16 features selected
01:26:26 [INFO]   [VOW3.DE] After importance gate: 16 features
01:26:46 [INFO] Logged: f8472c62 | VOW3.DE | RandomForest | acc=0.4876 | auc=0.6338 | purge=7d
01:27:05 [INFO] Logged: 9893f6d6 | VOW3.DE | XGBoost | acc=0.5089 | auc=0.6543 | purge=7d
01:27:05 [INFO]   [VOW3.DE] OK
01:27:05 [INFO]   ── RWE.DE ──
01:27:05 [INFO]   [RWE.DE] Building features…
01:27:05 [INFO] Feature selection — Stage 1 (variance): 40 → 26 features
01:27:05 [INFO] Feature selection — Stage 2 (correlation): → 25 features (dropped 1 correlated)
01:27:05 [INFO] Feature selection complete: 40 → 25 features selected
01:27:05 [INFO]   [RWE.DE] After variance/corr selection: 25 features
01:27:05 [INFO]   [RWE.DE] 2783 rows · 16 WF splits · 25 features
01:27:05 [INFO] Logged: 7ba75927 | RWE.DE | Baseline_Random | acc=0.5169 | auc=0.511 | purge=7d
01:27:05 [INFO] Logged: dba52f44 | RWE.DE | Baseline_Momentum | acc=0.5883 | auc=0.5 | purge=7d
01:27:07 [INFO] Logged: ee344cf8 | RWE.DE | LogisticRegression | acc=0.5119 | auc=0.6127 | purge=7d
01:27:08 [INFO] Feature selection — Stage 1 (variance): 25 → 25 features
01:27:08 [INFO] Feature selection — Stage 2 (correlation): → 25 features (dropped 0 correlated)
01:27:08 [INFO] Feature selection — Stage 3 (importance): → 16 features (dropped 9 low-importance)
01:27:08 [INFO] Feature selection complete: 25 → 16 features selected
01:27:08 [INFO]   [RWE.DE] After importance gate: 16 features
01:27:29 [INFO] Logged: c93fdfb8 | RWE.DE | RandomForest | acc=0.5496 | auc=0.6934 | purge=7d
01:27:50 [INFO] Logged: 06137e3f | RWE.DE | XGBoost | acc=0.5377 | auc=0.6156 | purge=7d
01:27:50 [INFO]   [RWE.DE] OK
01:27:50 [INFO]   ── CON.DE ──
01:27:50 [INFO]   [CON.DE] Building features…
01:27:50 [WARNING]   [CON.DE] Too few clean rows; skipping
01:27:50 [INFO]   [CON.DE] SKIPPED
01:27:50 [INFO]   ── FRE.DE ──
01:27:50 [INFO]   [FRE.DE] Building features…
01:27:51 [INFO] Feature selection — Stage 1 (variance): 40 → 25 features
01:27:51 [INFO] Feature selection — Stage 2 (correlation): → 24 features (dropped 1 correlated)
01:27:51 [INFO] Feature selection complete: 40 → 24 features selected
01:27:51 [INFO]   [FRE.DE] After variance/corr selection: 24 features
01:27:51 [INFO]   [FRE.DE] 2783 rows · 16 WF splits · 24 features
01:27:51 [INFO] Logged: c221df7d | FRE.DE | Baseline_Random | acc=0.5119 | auc=0.5164 | purge=7d
01:27:51 [INFO] Logged: ac6d8096 | FRE.DE | Baseline_Momentum | acc=0.5317 | auc=0.5 | purge=7d
01:27:53 [INFO] Logged: e60df361 | FRE.DE | LogisticRegression | acc=0.5536 | auc=0.5982 | purge=7d
01:27:54 [INFO] Feature selection — Stage 1 (variance): 24 → 24 features
01:27:54 [INFO] Feature selection — Stage 2 (correlation): → 24 features (dropped 0 correlated)
01:27:54 [INFO] Feature selection — Stage 3 (importance): → 19 features (dropped 5 low-importance)
01:27:54 [INFO] Feature selection complete: 24 → 19 features selected
01:27:54 [INFO]   [FRE.DE] After importance gate: 19 features
01:28:14 [INFO] Logged: 2f0b9909 | FRE.DE | RandomForest | acc=0.5094 | auc=0.6264 | purge=7d
01:28:34 [INFO] Logged: b819a495 | FRE.DE | XGBoost | acc=0.4911 | auc=0.597 | purge=7d
01:28:34 [INFO]   [FRE.DE] OK
01:28:34 [INFO]   ── VNA.DE ──
01:28:34 [INFO]   [VNA.DE] Building features…
01:28:34 [INFO] Feature selection — Stage 1 (variance): 40 → 25 features
01:28:34 [INFO] Feature selection — Stage 2 (correlation): → 24 features (dropped 1 correlated)
01:28:34 [INFO] Feature selection complete: 40 → 24 features selected
01:28:34 [INFO]   [VNA.DE] After variance/corr selection: 24 features
01:28:34 [INFO]   [VNA.DE] 2762 rows · 15 WF splits · 24 features
01:28:34 [INFO] Logged: 152afc8d | VNA.DE | Baseline_Random | acc=0.5169 | auc=0.5183 | purge=7d
01:28:34 [INFO] Logged: 9e39c262 | VNA.DE | Baseline_Momentum | acc=0.5312 | auc=0.5 | purge=7d
01:28:36 [INFO] Logged: 481b3f6a | VNA.DE | LogisticRegression | acc=0.5577 | auc=0.6814 | purge=7d
01:28:37 [INFO] Feature selection — Stage 1 (variance): 24 → 24 features
01:28:37 [INFO] Feature selection — Stage 2 (correlation): → 24 features (dropped 0 correlated)
01:28:37 [INFO] Feature selection — Stage 3 (importance): → 19 features (dropped 5 low-importance)
01:28:37 [INFO] Feature selection complete: 24 → 19 features selected
01:28:37 [INFO]   [VNA.DE] After importance gate: 19 features
01:28:56 [INFO] Logged: 11c7cb9e | VNA.DE | RandomForest | acc=0.5397 | auc=0.6833 | purge=7d
01:29:16 [INFO] Logged: 01456936 | VNA.DE | XGBoost | acc=0.5598 | auc=0.6623 | purge=7d
01:29:16 [INFO]   [VNA.DE] OK
01:29:16 [INFO]   ── HEN3.DE ──
01:29:16 [INFO]   [HEN3.DE] Building features…
01:29:17 [INFO] Feature selection — Stage 1 (variance): 40 → 23 features
01:29:17 [INFO] Feature selection — Stage 2 (correlation): → 22 features (dropped 1 correlated)
01:29:17 [INFO] Feature selection complete: 40 → 22 features selected
01:29:17 [INFO]   [HEN3.DE] After variance/corr selection: 22 features
01:29:17 [INFO]   [HEN3.DE] 2778 rows · 16 WF splits · 22 features
01:29:17 [INFO] Logged: 87291aaf | HEN3.DE | Baseline_Random | acc=0.4851 | auc=0.5186 | purge=7d
01:29:17 [INFO] Logged: 27c37ca5 | HEN3.DE | Baseline_Momentum | acc=0.505 | auc=0.5 | purge=7d
01:29:19 [INFO] Logged: 857d359a | HEN3.DE | LogisticRegression | acc=0.4965 | auc=0.5845 | purge=7d
01:29:20 [INFO] Feature selection — Stage 1 (variance): 22 → 22 features
01:29:20 [INFO] Feature selection — Stage 2 (correlation): → 22 features (dropped 0 correlated)
01:29:20 [INFO] Feature selection — Stage 3 (importance): → 16 features (dropped 6 low-importance)
01:29:20 [INFO] Feature selection complete: 22 → 16 features selected
01:29:20 [INFO]   [HEN3.DE] After importance gate: 16 features
01:29:38 [INFO] Logged: 469a7c9c | HEN3.DE | RandomForest | acc=0.4906 | auc=0.6701 | purge=7d
01:29:58 [INFO] Logged: d9934fcb | HEN3.DE | XGBoost | acc=0.4712 | auc=0.6571 | purge=7d
01:29:58 [INFO]   [HEN3.DE] OK
01:29:58 [INFO]   ── BEI.DE ──
01:29:58 [INFO]   [BEI.DE] Building features…
01:29:59 [INFO] Feature selection — Stage 1 (variance): 40 → 23 features
01:29:59 [INFO] Feature selection — Stage 2 (correlation): → 22 features (dropped 1 correlated)
01:29:59 [INFO] Feature selection complete: 40 → 22 features selected
01:29:59 [INFO]   [BEI.DE] After variance/corr selection: 22 features
01:29:59 [INFO]   [BEI.DE] 2783 rows · 16 WF splits · 22 features
01:29:59 [INFO] Logged: 046520e8 | BEI.DE | Baseline_Random | acc=0.5203 | auc=0.5129 | purge=7d
01:29:59 [INFO] Logged: 3fd4f5e3 | BEI.DE | Baseline_Momentum | acc=0.5273 | auc=0.5 | purge=7d
01:30:01 [INFO] Logged: 2516faad | BEI.DE | LogisticRegression | acc=0.5501 | auc=0.6152 | purge=7d
01:30:02 [INFO] Feature selection — Stage 1 (variance): 22 → 22 features
01:30:02 [INFO] Feature selection — Stage 2 (correlation): → 22 features (dropped 0 correlated)
01:30:02 [INFO] Feature selection — Stage 3 (importance): → 14 features (dropped 8 low-importance)
01:30:02 [INFO] Feature selection complete: 22 → 14 features selected
01:30:02 [INFO]   [BEI.DE] After importance gate: 14 features
01:30:22 [INFO] Logged: c412e1cb | BEI.DE | RandomForest | acc=0.5233 | auc=0.5893 | purge=7d
01:30:43 [INFO] Logged: a7a74d80 | BEI.DE | XGBoost | acc=0.5288 | auc=0.631 | purge=7d
01:30:43 [INFO]   [BEI.DE] OK
01:30:43 [INFO]   ── ZAL.DE ──
01:30:43 [INFO]   [ZAL.DE] Building features…
01:30:43 [INFO] Feature selection — Stage 1 (variance): 40 → 27 features
01:30:43 [INFO] Feature selection — Stage 2 (correlation): → 26 features (dropped 1 correlated)
01:30:43 [INFO] Feature selection complete: 40 → 26 features selected
01:30:43 [INFO]   [ZAL.DE] After variance/corr selection: 26 features
01:30:43 [INFO]   [ZAL.DE] 2592 rows · 14 WF splits · 26 features
01:30:43 [INFO] Logged: 09313f33 | ZAL.DE | Baseline_Random | acc=0.5057 | auc=0.4797 | purge=7d
01:30:43 [INFO] Logged: 18696944 | ZAL.DE | Baseline_Momentum | acc=0.4943 | auc=0.5 | purge=7d
01:30:44 [INFO] Logged: 07bb263a | ZAL.DE | LogisticRegression | acc=0.4762 | auc=0.5269 | purge=7d
01:30:46 [INFO] Feature selection — Stage 1 (variance): 26 → 26 features
01:30:46 [INFO] Feature selection — Stage 2 (correlation): → 26 features (dropped 0 correlated)
01:30:46 [INFO] Feature selection — Stage 3 (importance): → 17 features (dropped 9 low-importance)
01:30:46 [INFO] Feature selection complete: 26 → 17 features selected
01:30:46 [INFO]   [ZAL.DE] After importance gate: 17 features
01:31:04 [INFO] Logged: e3b09f9a | ZAL.DE | RandomForest | acc=0.479 | auc=0.6244 | purge=7d
01:31:21 [INFO] Logged: 0e6d226e | ZAL.DE | XGBoost | acc=0.4745 | auc=0.6326 | purge=7d
01:31:21 [INFO]   [ZAL.DE] OK
01:31:21 [INFO]   ── MTX.DE ──
01:31:21 [INFO]   [MTX.DE] Building features…
01:31:21 [WARNING]   [MTX.DE] Too few clean rows; skipping
01:31:21 [INFO]   [MTX.DE] SKIPPED
01:31:21 [INFO]   ── NDX1.DE ──
01:31:21 [INFO]   [NDX1.DE] Building features…
01:31:21 [INFO] Feature selection — Stage 1 (variance): 40 → 27 features
01:31:21 [INFO] Feature selection — Stage 2 (correlation): → 26 features (dropped 1 correlated)
01:31:21 [INFO] Feature selection complete: 40 → 26 features selected
01:31:21 [INFO]   [NDX1.DE] After variance/corr selection: 26 features
01:31:21 [INFO]   [NDX1.DE] 2783 rows · 16 WF splits · 26 features
01:31:22 [INFO] Logged: 51ebc7c8 | NDX1.DE | Baseline_Random | acc=0.4936 | auc=0.5101 | purge=7d
01:31:22 [INFO] Logged: fb0795e7 | NDX1.DE | Baseline_Momentum | acc=0.5531 | auc=0.5 | purge=7d
01:31:24 [INFO] Logged: cfed3282 | NDX1.DE | LogisticRegression | acc=0.4469 | auc=0.4554 | purge=7d
01:31:25 [INFO] Feature selection — Stage 1 (variance): 26 → 26 features
01:31:25 [INFO] Feature selection — Stage 2 (correlation): → 26 features (dropped 0 correlated)
01:31:25 [INFO] Feature selection — Stage 3 (importance): → 18 features (dropped 8 low-importance)
01:31:25 [INFO] Feature selection complete: 26 → 18 features selected
01:31:25 [INFO]   [NDX1.DE] After importance gate: 18 features
01:31:45 [INFO] Logged: a0bd6ab0 | NDX1.DE | RandomForest | acc=0.5466 | auc=0.5421 | purge=7d
01:32:06 [INFO] Logged: b9596d3b | NDX1.DE | XGBoost | acc=0.5203 | auc=0.5672 | purge=7d
01:32:06 [INFO]   [NDX1.DE] OK
01:32:06 [INFO]   ── ARGX.BR ──
01:32:06 [INFO]   [ARGX.BR] Building features…
01:32:06 [WARNING]   [ARGX.BR] Too few clean rows; skipping
01:32:06 [INFO]   [ARGX.BR] SKIPPED
01:32:06 [INFO]   ── UCB.BR ──
01:32:06 [INFO]   [UCB.BR] Building features…
01:32:06 [INFO] Feature selection — Stage 1 (variance): 40 → 25 features
01:32:06 [INFO] Feature selection — Stage 2 (correlation): → 24 features (dropped 1 correlated)
01:32:06 [INFO] Feature selection complete: 40 → 24 features selected
01:32:06 [INFO]   [UCB.BR] After variance/corr selection: 24 features
01:32:06 [INFO]   [UCB.BR] 2910 rows · 17 WF splits · 24 features
01:32:06 [INFO] Logged: 354d79fc | UCB.BR | Baseline_Random | acc=0.5099 | auc=0.4703 | purge=7d
01:32:06 [INFO] Logged: 5f8ec9e9 | UCB.BR | Baseline_Momentum | acc=0.5808 | auc=0.5 | purge=7d
01:32:08 [INFO] Logged: 0e42180f | UCB.BR | LogisticRegression | acc=0.4496 | auc=0.5686 | purge=7d
01:32:09 [INFO] Feature selection — Stage 1 (variance): 24 → 24 features
01:32:09 [INFO] Feature selection — Stage 2 (correlation): → 24 features (dropped 0 correlated)
01:32:09 [INFO] Feature selection — Stage 3 (importance): → 17 features (dropped 7 low-importance)
01:32:09 [INFO] Feature selection complete: 24 → 17 features selected
01:32:09 [INFO]   [UCB.BR] After importance gate: 17 features
01:32:30 [INFO] Logged: a9b4594c | UCB.BR | RandomForest | acc=0.4804 | auc=0.5326 | purge=7d
01:32:50 [INFO] Logged: c3bcf443 | UCB.BR | XGBoost | acc=0.4608 | auc=0.5449 | purge=7d
01:32:50 [INFO]   [UCB.BR] OK
01:32:50 [INFO]   ── SHL.DE ──
01:32:50 [INFO]   [SHL.DE] Building features…
01:32:51 [INFO] Feature selection — Stage 1 (variance): 40 → 24 features
01:32:51 [INFO] Feature selection — Stage 2 (correlation): → 23 features (dropped 1 correlated)
01:32:51 [INFO] Feature selection complete: 40 → 23 features selected
01:32:51 [INFO]   [SHL.DE] After variance/corr selection: 23 features
01:32:51 [INFO]   [SHL.DE] 1801 rows · 8 WF splits · 23 features
01:32:51 [INFO] Logged: 897dd815 | SHL.DE | Baseline_Random | acc=0.5169 | auc=0.4897 | purge=7d
01:32:51 [INFO] Logged: fcc0a207 | SHL.DE | Baseline_Momentum | acc=0.4931 | auc=0.5 | purge=7d
01:32:52 [INFO] Logged: 0dc169f0 | SHL.DE | LogisticRegression | acc=0.4544 | auc=0.5822 | purge=7d
01:32:53 [INFO] Feature selection — Stage 1 (variance): 23 → 23 features
01:32:53 [INFO] Feature selection — Stage 2 (correlation): → 23 features (dropped 0 correlated)
01:32:53 [INFO] Feature selection — Stage 3 (importance): → 16 features (dropped 7 low-importance)
01:32:53 [INFO] Feature selection complete: 23 → 16 features selected
01:32:53 [INFO]   [SHL.DE] After importance gate: 16 features
01:33:02 [INFO] Logged: 67151a5d | SHL.DE | RandomForest | acc=0.4742 | auc=0.6909 | purge=7d
01:33:12 [INFO] Logged: b433b139 | SHL.DE | XGBoost | acc=0.5089 | auc=0.6907 | purge=7d
01:33:12 [INFO]   [SHL.DE] OK
01:33:12 [INFO]   ── COK.DE ──
01:33:12 [INFO]   [COK.DE] Building features…
01:33:12 [INFO] Feature selection — Stage 1 (variance): 40 → 26 features
01:33:12 [INFO] Feature selection — Stage 2 (correlation): → 25 features (dropped 1 correlated)
01:33:12 [INFO] Feature selection complete: 40 → 25 features selected
01:33:12 [INFO]   [COK.DE] After variance/corr selection: 25 features
01:33:12 [INFO]   [COK.DE] 2783 rows · 16 WF splits · 25 features
01:33:12 [INFO] Logged: 8b5a1ab0 | COK.DE | Baseline_Random | acc=0.5045 | auc=0.4972 | purge=7d
01:33:13 [INFO] Logged: 6d18ffed | COK.DE | Baseline_Momentum | acc=0.5104 | auc=0.5 | purge=7d
01:33:14 [INFO] Logged: a7f49ac2 | COK.DE | LogisticRegression | acc=0.5015 | auc=0.6041 | purge=7d
01:33:16 [INFO] Feature selection — Stage 1 (variance): 25 → 25 features
01:33:16 [INFO] Feature selection — Stage 2 (correlation): → 25 features (dropped 0 correlated)
01:33:16 [INFO] Feature selection — Stage 3 (importance): → 18 features (dropped 7 low-importance)
01:33:16 [INFO] Feature selection complete: 25 → 18 features selected
01:33:16 [INFO]   [COK.DE] After importance gate: 18 features
01:33:35 [INFO] Logged: 7806717e | COK.DE | RandomForest | acc=0.4747 | auc=0.6198 | purge=7d
01:33:55 [INFO] Logged: b8925140 | COK.DE | XGBoost | acc=0.4782 | auc=0.6444 | purge=7d
01:33:55 [INFO]   [COK.DE] OK
01:33:55 [INFO]   ── AIR.DE ──
01:33:55 [INFO]   [AIR.DE] Building features…
01:33:55 [INFO] Feature selection — Stage 1 (variance): 40 → 26 features
01:33:55 [INFO] Feature selection — Stage 2 (correlation): → 25 features (dropped 1 correlated)
01:33:55 [INFO] Feature selection complete: 40 → 25 features selected
01:33:55 [INFO]   [AIR.DE] After variance/corr selection: 25 features
01:33:55 [INFO]   [AIR.DE] 2783 rows · 16 WF splits · 25 features
01:33:56 [INFO] Logged: 2c17e02e | AIR.DE | Baseline_Random | acc=0.505 | auc=0.5143 | purge=7d
01:33:56 [INFO] Logged: edbbe7b6 | AIR.DE | Baseline_Momentum | acc=0.5694 | auc=0.5 | purge=7d
01:33:58 [INFO] Logged: 24b4edc6 | AIR.DE | LogisticRegression | acc=0.5491 | auc=0.5571 | purge=7d
01:34:00 [INFO] Feature selection — Stage 1 (variance): 25 → 25 features
01:34:00 [INFO] Feature selection — Stage 2 (correlation): → 25 features (dropped 0 correlated)
01:34:00 [INFO] Feature selection — Stage 3 (importance): → 15 features (dropped 10 low-importance)
01:34:00 [INFO] Feature selection complete: 25 → 15 features selected
01:34:00 [INFO]   [AIR.DE] After importance gate: 15 features
01:34:21 [INFO] Logged: 26faffa4 | AIR.DE | RandomForest | acc=0.4802 | auc=0.5744 | purge=7d
01:34:43 [INFO] Logged: 45cceacf | AIR.DE | XGBoost | acc=0.4454 | auc=0.5869 | purge=7d
01:34:43 [INFO]   [AIR.DE] OK
01:34:43 [INFO]   ── AZN.L ──
01:34:43 [INFO]   [AZN.L] Building features…
01:34:43 [INFO] Feature selection — Stage 1 (variance): 40 → 22 features
01:34:43 [INFO] Feature selection — Stage 2 (correlation): → 21 features (dropped 1 correlated)
01:34:43 [INFO] Feature selection complete: 40 → 21 features selected
01:34:43 [INFO]   [AZN.L] After variance/corr selection: 21 features
01:34:43 [INFO]   [AZN.L] 2851 rows · 16 WF splits · 21 features
01:34:43 [INFO] Logged: a978c1ae | AZN.L | Baseline_Random | acc=0.505 | auc=0.4981 | purge=7d
01:34:43 [INFO] Logged: 7508cd24 | AZN.L | Baseline_Momentum | acc=0.5774 | auc=0.5 | purge=7d
01:34:45 [INFO] Logged: 7450e4c2 | AZN.L | LogisticRegression | acc=0.5342 | auc=0.6416 | purge=7d
01:34:47 [INFO] Feature selection — Stage 1 (variance): 21 → 21 features
01:34:47 [INFO] Feature selection — Stage 2 (correlation): → 21 features (dropped 0 correlated)
01:34:47 [INFO] Feature selection — Stage 3 (importance): → 17 features (dropped 4 low-importance)
01:34:47 [INFO] Feature selection complete: 21 → 17 features selected
01:34:47 [INFO]   [AZN.L] After importance gate: 17 features
01:35:11 [INFO] Logged: 748cf7b8 | AZN.L | RandomForest | acc=0.5491 | auc=0.6776 | purge=7d
01:35:33 [INFO] Logged: 44696a19 | AZN.L | XGBoost | acc=0.5213 | auc=0.6537 | purge=7d
01:35:33 [INFO]   [AZN.L] OK
01:35:33 [INFO]   ── SHELL.AS ──
01:35:33 [INFO]   [SHELL.AS] Building features…
01:35:33 [INFO] Feature selection — Stage 1 (variance): 40 → 25 features
01:35:34 [INFO] Feature selection — Stage 2 (correlation): → 24 features (dropped 1 correlated)
01:35:34 [INFO] Feature selection complete: 40 → 24 features selected
01:35:34 [INFO]   [SHELL.AS] After variance/corr selection: 24 features
01:35:34 [INFO]   [SHELL.AS] 2910 rows · 17 WF splits · 24 features
01:35:34 [INFO] Logged: 9d123aa5 | SHELL.AS | Baseline_Random | acc=0.5005 | auc=0.5021 | purge=7d
01:35:34 [INFO] Logged: b567734a | SHELL.AS | Baseline_Momentum | acc=0.57 | auc=0.5 | purge=7d
01:35:36 [INFO] Logged: ef886dbe | SHELL.AS | LogisticRegression | acc=0.5093 | auc=0.5941 | purge=7d
01:35:38 [INFO] Feature selection — Stage 1 (variance): 24 → 24 features
01:35:38 [INFO] Feature selection — Stage 2 (correlation): → 24 features (dropped 0 correlated)
01:35:38 [INFO] Feature selection — Stage 3 (importance): → 18 features (dropped 6 low-importance)
01:35:38 [INFO] Feature selection complete: 24 → 18 features selected
01:35:38 [INFO]   [SHELL.AS] After importance gate: 18 features
01:36:03 [INFO] Logged: 30dfd4d2 | SHELL.AS | RandomForest | acc=0.5089 | auc=0.6437 | purge=7d
01:36:27 [INFO] Logged: 032e90f7 | SHELL.AS | XGBoost | acc=0.5387 | auc=0.6351 | purge=7d
01:36:27 [INFO]   [SHELL.AS] OK
01:36:27 [INFO]   ── TTE.PA ──
01:36:27 [INFO]   [TTE.PA] Building features…
01:36:27 [INFO] Feature selection — Stage 1 (variance): 40 → 25 features
01:36:27 [INFO] Feature selection — Stage 2 (correlation): → 24 features (dropped 1 correlated)
01:36:27 [INFO] Feature selection complete: 40 → 24 features selected
01:36:27 [INFO]   [TTE.PA] After variance/corr selection: 24 features
01:36:27 [INFO]   [TTE.PA] 2869 rows · 16 WF splits · 24 features
01:36:28 [INFO] Logged: 57118181 | TTE.PA | Baseline_Random | acc=0.5005 | auc=0.4987 | purge=7d
01:36:28 [INFO] Logged: fdc5352b | TTE.PA | Baseline_Momentum | acc=0.559 | auc=0.5 | purge=7d
01:36:30 [INFO] Logged: de35bb34 | TTE.PA | LogisticRegression | acc=0.5342 | auc=0.6335 | purge=7d
01:36:31 [INFO] Feature selection — Stage 1 (variance): 24 → 24 features
01:36:31 [INFO] Feature selection — Stage 2 (correlation): → 24 features (dropped 0 correlated)
01:36:31 [INFO] Feature selection — Stage 3 (importance): → 20 features (dropped 4 low-importance)
01:36:31 [INFO] Feature selection complete: 24 → 20 features selected
01:36:31 [INFO]   [TTE.PA] After importance gate: 20 features
01:36:55 [INFO] Logged: f8d3152c | TTE.PA | RandomForest | acc=0.4836 | auc=0.5926 | purge=7d
01:37:18 [INFO] Logged: 3eb575d5 | TTE.PA | XGBoost | acc=0.505 | auc=0.5764 | purge=7d
01:37:18 [INFO]   [TTE.PA] OK
01:37:18 [INFO]   ── BP.L ──
01:37:18 [INFO]   [BP.L] Building features…
01:37:18 [INFO] Feature selection — Stage 1 (variance): 40 → 25 features
01:37:18 [INFO] Feature selection — Stage 2 (correlation): → 24 features (dropped 1 correlated)
01:37:18 [INFO] Feature selection complete: 40 → 24 features selected
01:37:18 [INFO]   [BP.L] After variance/corr selection: 24 features
01:37:18 [INFO]   [BP.L] 2871 rows · 16 WF splits · 24 features
01:37:18 [INFO] Logged: 54949aef | BP.L | Baseline_Random | acc=0.504 | auc=0.5164 | purge=7d
01:37:19 [INFO] Logged: 4d9661ee | BP.L | Baseline_Momentum | acc=0.498 | auc=0.5 | purge=7d
01:37:20 [INFO] Logged: a87fb362 | BP.L | LogisticRegression | acc=0.4851 | auc=0.5895 | purge=7d
01:37:21 [INFO] Feature selection — Stage 1 (variance): 24 → 24 features
01:37:21 [INFO] Feature selection — Stage 2 (correlation): → 24 features (dropped 0 correlated)
01:37:21 [INFO] Feature selection — Stage 3 (importance): → 18 features (dropped 6 low-importance)
01:37:21 [INFO] Feature selection complete: 24 → 18 features selected
01:37:21 [INFO]   [BP.L] After importance gate: 18 features
01:37:43 [INFO] Logged: 75bfcc7a | BP.L | RandomForest | acc=0.495 | auc=0.6128 | purge=7d
01:38:05 [INFO] Logged: d068d2bd | BP.L | XGBoost | acc=0.5417 | auc=0.6465 | purge=7d
01:38:05 [INFO]   [BP.L] OK
01:38:05 [INFO]   ── ASML.AS ──
01:38:05 [INFO]   [ASML.AS] Building features…
01:38:05 [INFO] Feature selection — Stage 1 (variance): 40 → 26 features
01:38:05 [INFO] Feature selection — Stage 2 (correlation): → 25 features (dropped 1 correlated)
01:38:05 [INFO] Feature selection complete: 40 → 25 features selected
01:38:05 [INFO]   [ASML.AS] After variance/corr selection: 25 features
01:38:05 [INFO]   [ASML.AS] 2910 rows · 17 WF splits · 25 features
01:38:05 [INFO] Logged: d385dc64 | ASML.AS | Baseline_Random | acc=0.5126 | auc=0.4917 | purge=7d
01:38:05 [INFO] Logged: bf0249e4 | ASML.AS | Baseline_Momentum | acc=0.6027 | auc=0.5 | purge=7d
01:38:07 [INFO] Logged: bbd0c867 | ASML.AS | LogisticRegression | acc=0.5308 | auc=0.5331 | purge=7d
01:38:09 [INFO] Feature selection — Stage 1 (variance): 25 → 25 features
01:38:09 [INFO] Feature selection — Stage 2 (correlation): → 25 features (dropped 0 correlated)
01:38:09 [INFO] Feature selection — Stage 3 (importance): → 16 features (dropped 9 low-importance)
01:38:09 [INFO] Feature selection complete: 25 → 16 features selected
01:38:09 [INFO]   [ASML.AS] After importance gate: 16 features
01:38:31 [INFO] Logged: 1e03e658 | ASML.AS | RandomForest | acc=0.5331 | auc=0.5833 | purge=7d
01:38:52 [INFO] Logged: 9ccf3acf | ASML.AS | XGBoost | acc=0.5187 | auc=0.6323 | purge=7d
01:38:52 [INFO]   [ASML.AS] OK
01:38:52 [INFO]   ── NOV.DE ──
01:38:52 [INFO]   [NOV.DE] Building features…
01:38:52 [INFO] Feature selection — Stage 1 (variance): 40 → 26 features
01:38:52 [INFO] Feature selection — Stage 2 (correlation): → 25 features (dropped 1 correlated)
01:38:52 [INFO] Feature selection complete: 40 → 25 features selected
01:38:52 [INFO]   [NOV.DE] After variance/corr selection: 25 features
01:38:52 [INFO]   [NOV.DE] 2783 rows · 16 WF splits · 25 features
01:38:52 [INFO] Logged: 22322559 | NOV.DE | Baseline_Random | acc=0.5223 | auc=0.4836 | purge=7d
01:38:52 [INFO] Logged: 8d371871 | NOV.DE | Baseline_Momentum | acc=0.6424 | auc=0.5 | purge=7d
01:38:53 [INFO] Logged: e390d3e4 | NOV.DE | LogisticRegression | acc=0.6022 | auc=0.5749 | purge=7d
01:38:54 [INFO] Feature selection — Stage 1 (variance): 25 → 25 features
01:38:54 [INFO] Feature selection — Stage 2 (correlation): → 25 features (dropped 0 correlated)
01:38:54 [INFO] Feature selection — Stage 3 (importance): → 15 features (dropped 10 low-importance)
01:38:54 [INFO] Feature selection complete: 25 → 15 features selected
01:38:54 [INFO]   [NOV.DE] After importance gate: 15 features
01:39:15 [INFO] Logged: 169b04b9 | NOV.DE | RandomForest | acc=0.5997 | auc=0.6387 | purge=7d
01:39:37 [INFO] Logged: aa8f6704 | NOV.DE | XGBoost | acc=0.5615 | auc=0.6404 | purge=7d
01:39:37 [INFO]   [NOV.DE] OK
01:39:37 [INFO]   ── S92.DE ──
01:39:37 [INFO]   [S92.DE] Building features…
01:39:37 [WARNING]   [S92.DE] Too few clean rows; skipping
01:39:37 [INFO]   [S92.DE] SKIPPED
01:39:37 [INFO]   ── 3V64.DE ──
01:39:37 [INFO]   [3V64.DE] Building features…
01:39:37 [INFO] Feature selection — Stage 1 (variance): 40 → 23 features
01:39:37 [INFO] Feature selection — Stage 2 (correlation): → 22 features (dropped 1 correlated)
01:39:37 [INFO] Feature selection complete: 40 → 22 features selected
01:39:37 [INFO]   [3V64.DE] After variance/corr selection: 22 features
01:39:37 [INFO]   [3V64.DE] 2704 rows · 15 WF splits · 22 features
01:39:37 [INFO] Logged: dfd98360 | 3V64.DE | Baseline_Random | acc=0.5048 | auc=0.5099 | purge=7d
01:39:37 [INFO] Logged: ec5e1d71 | 3V64.DE | Baseline_Momentum | acc=0.5751 | auc=0.5 | purge=7d
01:39:39 [INFO] Logged: 10053f65 | 3V64.DE | LogisticRegression | acc=0.5661 | auc=0.7369 | purge=7d
01:39:41 [INFO] Feature selection — Stage 1 (variance): 22 → 22 features
01:39:41 [INFO] Feature selection — Stage 2 (correlation): → 22 features (dropped 0 correlated)
01:39:41 [INFO] Feature selection — Stage 3 (importance): → 17 features (dropped 5 low-importance)
01:39:41 [INFO] Feature selection complete: 22 → 17 features selected
01:39:41 [INFO]   [3V64.DE] After importance gate: 17 features
01:39:59 [INFO] Logged: 6f4fcd13 | 3V64.DE | RandomForest | acc=0.5646 | auc=0.6402 | purge=7d
01:40:11 [INFO] Logged: bf205200 | 3V64.DE | XGBoost | acc=0.5582 | auc=0.6101 | purge=7d
01:40:11 [INFO]   [3V64.DE] OK
01:40:11 [INFO]   ── CMC.DE ──
01:40:11 [INFO]   [CMC.DE] Building features…
01:40:11 [WARNING]   [CMC.DE] Too few clean rows; skipping
01:40:11 [INFO]   [CMC.DE] SKIPPED
01:40:11 [INFO]   ── NCB.DE ──
01:40:11 [INFO]   [NCB.DE] Building features…
01:40:11 [WARNING]   [NCB.DE] Too few clean rows; skipping
01:40:11 [INFO]   [NCB.DE] SKIPPED
01:40:11 [INFO]   ── GOS.DE ──
01:40:11 [INFO]   [GOS.DE] Building features…
01:40:12 [WARNING]   [GOS.DE] Too few clean rows; skipping
01:40:12 [INFO]   [GOS.DE] SKIPPED
01:40:12 [INFO]   ── DWD.DE ──
01:40:12 [INFO]   [DWD.DE] Building features…
01:40:12 [WARNING]   [DWD.DE] Too few clean rows; skipping
01:40:12 [INFO]   [DWD.DE] SKIPPED
01:40:12 [INFO]   ── BRYN.DE ──
01:40:12 [INFO]   [BRYN.DE] Building features…
01:40:12 [INFO] Feature selection — Stage 1 (variance): 40 → 22 features
01:40:12 [INFO] Feature selection — Stage 2 (correlation): → 21 features (dropped 1 correlated)
01:40:12 [INFO] Feature selection complete: 40 → 21 features selected
01:40:12 [INFO]   [BRYN.DE] After variance/corr selection: 21 features
01:40:12 [INFO]   [BRYN.DE] 2498 rows · 13 WF splits · 21 features
01:40:12 [INFO] Logged: 6b6453bf | BRYN.DE | Baseline_Random | acc=0.5183 | auc=0.5011 | purge=7d
01:40:12 [INFO] Logged: 843d3a7f | BRYN.DE | Baseline_Momentum | acc=0.6606 | auc=0.5 | purge=7d
01:40:13 [INFO] Logged: 4a77f66e | BRYN.DE | LogisticRegression | acc=0.6239 | auc=0.6406 | purge=7d
01:40:13 [INFO] Feature selection — Stage 1 (variance): 21 → 21 features
01:40:13 [INFO] Feature selection — Stage 2 (correlation): → 21 features (dropped 0 correlated)
01:40:13 [INFO] Feature selection — Stage 3 (importance): → 15 features (dropped 6 low-importance)
01:40:13 [INFO] Feature selection complete: 21 → 15 features selected
01:40:13 [INFO]   [BRYN.DE] After importance gate: 15 features
01:40:30 [INFO] Logged: 9fd4af58 | BRYN.DE | RandomForest | acc=0.5842 | auc=0.6422 | purge=7d
01:40:46 [INFO] Logged: e0fd30fb | BRYN.DE | XGBoost | acc=0.5647 | auc=0.6539 | purge=7d
01:40:46 [INFO]   [BRYN.DE] OK
01:40:46 [INFO]   ── AXP.DE ──
01:40:46 [INFO]   [AXP.DE] Building features…
01:40:46 [WARNING]   [AXP.DE] Too few clean rows; skipping
01:40:46 [INFO]   [AXP.DE] SKIPPED
01:40:46 [INFO]   ── BLQA.DE ──
01:40:46 [INFO]   [BLQA.DE] Building features…
01:40:46 [WARNING]   [BLQA.DE] Too few clean rows; skipping
01:40:46 [INFO]   [BLQA.DE] SKIPPED
01:40:46 [INFO]   ── KO ──
01:40:46 [INFO]   [KO] Building features…
01:40:47 [INFO] Feature selection — Stage 1 (variance): 48 → 21 features
01:40:47 [INFO] Feature selection — Stage 2 (correlation): → 20 features (dropped 1 correlated)
01:40:47 [INFO] Feature selection complete: 48 → 20 features selected
01:40:47 [INFO]   [KO] After variance/corr selection: 20 features
01:40:47 [INFO]   [KO] 2858 rows · 16 WF splits · 20 features
01:40:47 [INFO] Logged: 58140ac3 | KO | Baseline_Random | acc=0.503 | auc=0.5078 | purge=7d
01:40:47 [INFO] Logged: 8b4e04cd | KO | Baseline_Momentum | acc=0.6121 | auc=0.5 | purge=7d
01:40:49 [INFO] Logged: c3ba307e | KO | LogisticRegression | acc=0.563 | auc=0.5905 | purge=7d
01:40:51 [INFO] Feature selection — Stage 1 (variance): 20 → 20 features
01:40:51 [INFO] Feature selection — Stage 2 (correlation): → 20 features (dropped 0 correlated)
01:40:51 [INFO] Feature selection — Stage 3 (importance): → 15 features (dropped 5 low-importance)
01:40:51 [INFO] Feature selection complete: 20 → 15 features selected
01:40:51 [INFO]   [KO] After importance gate: 15 features
01:41:11 [INFO] Logged: d6308e7b | KO | RandomForest | acc=0.558 | auc=0.6415 | purge=7d
01:41:31 [INFO] Logged: 6aba4055 | KO | XGBoost | acc=0.5729 | auc=0.6458 | purge=7d
01:41:31 [INFO]   [KO] OK
01:41:31 [INFO]   ── MCD ──
01:41:31 [INFO]   [MCD] Building features…
01:41:31 [WARNING]   [MCD] Too few clean rows; skipping
01:41:31 [INFO]   [MCD] SKIPPED
01:41:31 [INFO]   ── WMT ──
01:41:31 [INFO]   [WMT] Building features…
01:41:31 [INFO] Feature selection — Stage 1 (variance): 48 → 24 features
01:41:31 [INFO] Feature selection — Stage 2 (correlation): → 23 features (dropped 1 correlated)
01:41:31 [INFO] Feature selection complete: 48 → 23 features selected
01:41:31 [INFO]   [WMT] After variance/corr selection: 23 features
01:41:31 [INFO]   [WMT] 2858 rows · 16 WF splits · 23 features
01:41:31 [INFO] Logged: f2a31c6b | WMT | Baseline_Random | acc=0.4936 | auc=0.4906 | purge=7d
01:41:32 [INFO] Logged: 17b2225b | WMT | Baseline_Momentum | acc=0.6265 | auc=0.5 | purge=7d
01:41:34 [INFO] Logged: 9d6bffb4 | WMT | LogisticRegression | acc=0.5536 | auc=0.5741 | purge=7d
01:41:36 [INFO] Feature selection — Stage 1 (variance): 23 → 23 features
01:41:36 [INFO] Feature selection — Stage 2 (correlation): → 23 features (dropped 0 correlated)
01:41:36 [INFO] Feature selection — Stage 3 (importance): → 14 features (dropped 9 low-importance)
01:41:36 [INFO] Feature selection complete: 23 → 14 features selected
01:41:36 [INFO]   [WMT] After importance gate: 14 features
01:42:00 [INFO] Logged: 0d810137 | WMT | RandomForest | acc=0.5561 | auc=0.6217 | purge=7d
01:42:17 [INFO] Logged: eada6221 | WMT | XGBoost | acc=0.5476 | auc=0.6509 | purge=7d
01:42:17 [INFO]   [WMT] OK
01:42:17 [INFO]   ── HD ──
01:42:17 [INFO]   [HD] Building features…
01:42:17 [INFO] Feature selection — Stage 1 (variance): 48 → 24 features
01:42:17 [INFO] Feature selection — Stage 2 (correlation): → 23 features (dropped 1 correlated)
01:42:17 [INFO] Feature selection complete: 48 → 23 features selected
01:42:17 [INFO]   [HD] After variance/corr selection: 23 features
01:42:17 [INFO]   [HD] 2858 rows · 16 WF splits · 23 features
01:42:17 [INFO] Logged: 1559f779 | HD | Baseline_Random | acc=0.5149 | auc=0.5172 | purge=7d
01:42:17 [INFO] Logged: df2b0a54 | HD | Baseline_Momentum | acc=0.5774 | auc=0.5 | purge=7d
01:42:17 [INFO] Logged: 638748e4 | HD | LogisticRegression | acc=0.5645 | auc=0.6499 | purge=7d
01:42:18 [INFO] Feature selection — Stage 1 (variance): 23 → 23 features
01:42:18 [INFO] Feature selection — Stage 2 (correlation): → 23 features (dropped 0 correlated)
01:42:18 [INFO] Feature selection — Stage 3 (importance): → 17 features (dropped 6 low-importance)
01:42:18 [INFO] Feature selection complete: 23 → 17 features selected
01:42:18 [INFO]   [HD] After importance gate: 17 features
01:42:33 [INFO] Logged: 853809d0 | HD | RandomForest | acc=0.5312 | auc=0.612 | purge=7d
01:42:41 [INFO] Logged: f6a35068 | HD | XGBoost | acc=0.5456 | auc=0.6406 | purge=7d
01:42:41 [INFO]   [HD] OK
01:42:41 [INFO]   ── COST ──
01:42:41 [INFO]   [COST] Building features…
01:42:41 [INFO] Feature selection — Stage 1 (variance): 48 → 22 features
01:42:41 [INFO] Feature selection — Stage 2 (correlation): → 21 features (dropped 1 correlated)
01:42:41 [INFO] Feature selection complete: 48 → 21 features selected
01:42:41 [INFO]   [COST] After variance/corr selection: 21 features
01:42:41 [INFO]   [COST] 2858 rows · 16 WF splits · 21 features
01:42:41 [INFO] Logged: 68906bd5 | COST | Baseline_Random | acc=0.5015 | auc=0.4965 | purge=7d
01:42:42 [INFO] Logged: 5dbf4703 | COST | Baseline_Momentum | acc=0.6414 | auc=0.5 | purge=7d
01:42:42 [INFO] Logged: c727c361 | COST | LogisticRegression | acc=0.6081 | auc=0.6598 | purge=7d
01:42:43 [INFO] Feature selection — Stage 1 (variance): 21 → 21 features
01:42:43 [INFO] Feature selection — Stage 2 (correlation): → 21 features (dropped 0 correlated)
01:42:43 [INFO] Feature selection — Stage 3 (importance): → 16 features (dropped 5 low-importance)
01:42:43 [INFO] Feature selection complete: 21 → 16 features selected
01:42:43 [INFO]   [COST] After importance gate: 16 features
01:42:58 [INFO] Logged: b6446de3 | COST | RandomForest | acc=0.6076 | auc=0.6491 | purge=7d
01:43:06 [INFO] Logged: 6f4d4e6d | COST | XGBoost | acc=0.6007 | auc=0.6538 | purge=7d
01:43:06 [INFO]   [COST] OK
01:43:06 [INFO]   ── NKE ──
01:43:06 [INFO]   [NKE] Building features…
01:43:06 [INFO] Feature selection — Stage 1 (variance): 48 → 26 features
01:43:06 [INFO] Feature selection — Stage 2 (correlation): → 25 features (dropped 1 correlated)
01:43:06 [INFO] Feature selection complete: 48 → 25 features selected
01:43:06 [INFO]   [NKE] After variance/corr selection: 25 features
01:43:06 [INFO]   [NKE] 2858 rows · 16 WF splits · 25 features
01:43:06 [INFO] Logged: 2853b1f5 | NKE | Baseline_Random | acc=0.5064 | auc=0.5021 | purge=7d
01:43:06 [INFO] Logged: b8b4b77b | NKE | Baseline_Momentum | acc=0.5402 | auc=0.5 | purge=7d
01:43:07 [INFO] Logged: a3ff31fe | NKE | LogisticRegression | acc=0.5456 | auc=0.5122 | purge=7d
01:43:08 [INFO] Feature selection — Stage 1 (variance): 25 → 25 features
01:43:08 [INFO] Feature selection — Stage 2 (correlation): → 25 features (dropped 0 correlated)
01:43:08 [INFO] Feature selection — Stage 3 (importance): → 18 features (dropped 7 low-importance)
01:43:08 [INFO] Feature selection complete: 25 → 18 features selected
01:43:08 [INFO]   [NKE] After importance gate: 18 features
01:43:25 [INFO] Logged: fb32e2e3 | NKE | RandomForest | acc=0.5223 | auc=0.5962 | purge=7d
01:43:46 [INFO] Logged: 1dda25ad | NKE | XGBoost | acc=0.5551 | auc=0.6274 | purge=7d
01:43:46 [INFO]   [NKE] OK
01:43:46 [INFO]   ── SBUX ──
01:43:46 [INFO]   [SBUX] Building features…
01:43:46 [WARNING]   [SBUX] Too few clean rows; skipping
01:43:46 [INFO]   [SBUX] SKIPPED
01:43:46 [INFO]   ── DIS ──
01:43:46 [INFO]   [DIS] Building features…
01:43:46 [INFO] Feature selection — Stage 1 (variance): 40 → 26 features
01:43:46 [INFO] Feature selection — Stage 2 (correlation): → 25 features (dropped 1 correlated)
01:43:46 [INFO] Feature selection complete: 40 → 25 features selected
01:43:46 [INFO]   [DIS] After variance/corr selection: 25 features
01:43:46 [INFO]   [DIS] 2858 rows · 16 WF splits · 25 features
01:43:46 [INFO] Logged: 5d42a508 | DIS | Baseline_Random | acc=0.497 | auc=0.4877 | purge=7d
01:43:46 [INFO] Logged: aeb1c3e2 | DIS | Baseline_Momentum | acc=0.4732 | auc=0.5 | purge=7d
01:43:49 [INFO] Logged: 0f3b3640 | DIS | LogisticRegression | acc=0.5208 | auc=0.5645 | purge=7d
01:43:50 [INFO] Feature selection — Stage 1 (variance): 25 → 25 features
01:43:50 [INFO] Feature selection — Stage 2 (correlation): → 25 features (dropped 0 correlated)
01:43:50 [INFO] Feature selection — Stage 3 (importance): → 18 features (dropped 7 low-importance)
01:43:50 [INFO] Feature selection complete: 25 → 18 features selected
01:43:50 [INFO]   [DIS] After importance gate: 18 features
01:44:11 [INFO] Logged: 9b1d5105 | DIS | RandomForest | acc=0.5015 | auc=0.5612 | purge=7d
01:44:33 [INFO] Logged: b19a1cff | DIS | XGBoost | acc=0.4836 | auc=0.5786 | purge=7d
01:44:33 [INFO]   [DIS] OK
01:44:33 [INFO]   ── LOW ──
01:44:33 [INFO]   [LOW] Building features…
01:44:33 [WARNING]   [LOW] Too few clean rows; skipping
01:44:33 [INFO]   [LOW] SKIPPED
01:44:33 [INFO]   ── UNH ──
01:44:33 [INFO]   [UNH] Building features…
01:44:33 [INFO] Feature selection — Stage 1 (variance): 48 → 25 features
01:44:33 [INFO] Feature selection — Stage 2 (correlation): → 24 features (dropped 1 correlated)
01:44:33 [INFO] Feature selection complete: 48 → 24 features selected
01:44:33 [INFO]   [UNH] After variance/corr selection: 24 features
01:44:33 [INFO]   [UNH] 2858 rows · 16 WF splits · 24 features
01:44:33 [INFO] Logged: 0407b74c | UNH | Baseline_Random | acc=0.4931 | auc=0.5064 | purge=7d
01:44:34 [INFO] Logged: 300ef36c | UNH | Baseline_Momentum | acc=0.5694 | auc=0.5 | purge=7d
01:44:35 [INFO] Logged: 7ec1c14d | UNH | LogisticRegression | acc=0.558 | auc=0.5908 | purge=7d
01:44:37 [INFO] Feature selection — Stage 1 (variance): 24 → 24 features
01:44:37 [INFO] Feature selection — Stage 2 (correlation): → 24 features (dropped 0 correlated)
01:44:37 [INFO] Feature selection — Stage 3 (importance): → 18 features (dropped 6 low-importance)
01:44:37 [INFO] Feature selection complete: 24 → 18 features selected
01:44:37 [INFO]   [UNH] After importance gate: 18 features
01:44:59 [INFO] Logged: 81f55c4d | UNH | RandomForest | acc=0.5868 | auc=0.6562 | purge=7d
01:45:22 [INFO] Logged: 86d44fd2 | UNH | XGBoost | acc=0.5848 | auc=0.6435 | purge=7d
01:45:22 [INFO]   [UNH] OK
01:45:22 [INFO]   ── JNJ ──
01:45:22 [INFO]   [JNJ] Building features…
01:45:23 [INFO] Feature selection — Stage 1 (variance): 48 → 22 features
01:45:23 [INFO] Feature selection — Stage 2 (correlation): → 21 features (dropped 1 correlated)
01:45:23 [INFO] Feature selection complete: 48 → 21 features selected
01:45:23 [INFO]   [JNJ] After variance/corr selection: 21 features
01:45:23 [INFO]   [JNJ] 2858 rows · 16 WF splits · 21 features
01:45:23 [INFO] Logged: 30bbc13e | JNJ | Baseline_Random | acc=0.5045 | auc=0.5106 | purge=7d
01:45:23 [INFO] Logged: bfe98bcb | JNJ | Baseline_Momentum | acc=0.562 | auc=0.5 | purge=7d
01:45:25 [INFO] Logged: 82607ee4 | JNJ | LogisticRegression | acc=0.501 | auc=0.6081 | purge=7d
01:45:27 [INFO] Feature selection — Stage 1 (variance): 21 → 21 features
01:45:27 [INFO] Feature selection — Stage 2 (correlation): → 21 features (dropped 0 correlated)
01:45:27 [INFO] Feature selection — Stage 3 (importance): → 16 features (dropped 5 low-importance)
01:45:27 [INFO] Feature selection complete: 21 → 16 features selected
01:45:27 [INFO]   [JNJ] After importance gate: 16 features
01:45:50 [INFO] Logged: ab6ec7a5 | JNJ | RandomForest | acc=0.5079 | auc=0.6445 | purge=7d
01:46:10 [INFO] Logged: e20d02b5 | JNJ | XGBoost | acc=0.5278 | auc=0.6378 | purge=7d
01:46:10 [INFO]   [JNJ] OK
01:46:10 [INFO]   ── PFE ──
01:46:10 [INFO]   [PFE] Building features…
01:46:10 [INFO] Feature selection — Stage 1 (variance): 48 → 24 features
01:46:10 [INFO] Feature selection — Stage 2 (correlation): → 23 features (dropped 1 correlated)
01:46:10 [INFO] Feature selection complete: 48 → 23 features selected
01:46:10 [INFO]   [PFE] After variance/corr selection: 23 features
01:46:10 [INFO]   [PFE] 2858 rows · 16 WF splits · 23 features
01:46:10 [INFO] Logged: aaafdc78 | PFE | Baseline_Random | acc=0.4945 | auc=0.5136 | purge=7d
01:46:10 [INFO] Logged: be85892f | PFE | Baseline_Momentum | acc=0.5035 | auc=0.5 | purge=7d
01:46:12 [INFO] Logged: d4e9ad34 | PFE | LogisticRegression | acc=0.5174 | auc=0.6545 | purge=7d
01:46:14 [INFO] Feature selection — Stage 1 (variance): 23 → 23 features
01:46:14 [INFO] Feature selection — Stage 2 (correlation): → 23 features (dropped 0 correlated)
01:46:14 [INFO] Feature selection — Stage 3 (importance): → 17 features (dropped 6 low-importance)
01:46:14 [INFO] Feature selection complete: 23 → 17 features selected
01:46:14 [INFO]   [PFE] After importance gate: 17 features
01:46:33 [INFO] Logged: 9b60766a | PFE | RandomForest | acc=0.5789 | auc=0.6534 | purge=7d
01:46:51 [INFO] Logged: b9b50704 | PFE | XGBoost | acc=0.5888 | auc=0.6642 | purge=7d
01:46:51 [INFO]   [PFE] OK
01:46:51 [INFO]   ── LLY ──
01:46:51 [INFO]   [LLY] Building features…
01:46:52 [INFO] Feature selection — Stage 1 (variance): 48 → 24 features
01:46:52 [INFO] Feature selection — Stage 2 (correlation): → 23 features (dropped 1 correlated)
01:46:52 [INFO] Feature selection complete: 48 → 23 features selected
01:46:52 [INFO]   [LLY] After variance/corr selection: 23 features
01:46:52 [INFO]   [LLY] 2858 rows · 16 WF splits · 23 features
01:46:52 [INFO] Logged: d205961a | LLY | Baseline_Random | acc=0.505 | auc=0.4907 | purge=7d
01:46:52 [INFO] Logged: ed59bc06 | LLY | Baseline_Momentum | acc=0.629 | auc=0.5 | purge=7d
01:46:54 [INFO] Logged: eac4f2b6 | LLY | LogisticRegression | acc=0.5511 | auc=0.579 | purge=7d
01:46:55 [INFO] Feature selection — Stage 1 (variance): 23 → 23 features
01:46:55 [INFO] Feature selection — Stage 2 (correlation): → 23 features (dropped 0 correlated)
01:46:55 [INFO] Feature selection — Stage 3 (importance): → 18 features (dropped 5 low-importance)
01:46:55 [INFO] Feature selection complete: 23 → 18 features selected
01:46:55 [INFO]   [LLY] After importance gate: 18 features
01:47:16 [INFO] Logged: 7a20bdc9 | LLY | RandomForest | acc=0.5387 | auc=0.5094 | purge=7d
01:47:39 [INFO] Logged: 611a72e4 | LLY | XGBoost | acc=0.5035 | auc=0.5397 | purge=7d
01:47:39 [INFO]   [LLY] OK
01:47:39 [INFO]   ── ABBV ──
01:47:39 [INFO]   [ABBV] Building features…
01:47:39 [WARNING]   [ABBV] Too few clean rows; skipping
01:47:39 [INFO]   [ABBV] SKIPPED
01:47:39 [INFO]   ── MRK ──
01:47:39 [INFO]   [MRK] Building features…
01:47:39 [INFO] Feature selection — Stage 1 (variance): 48 → 23 features
01:47:39 [INFO] Feature selection — Stage 2 (correlation): → 22 features (dropped 1 correlated)
01:47:39 [INFO] Feature selection complete: 48 → 22 features selected
01:47:39 [INFO]   [MRK] After variance/corr selection: 22 features
01:47:39 [INFO]   [MRK] 2858 rows · 16 WF splits · 22 features
01:47:40 [INFO] Logged: fffc4820 | MRK | Baseline_Random | acc=0.496 | auc=0.511 | purge=7d
01:47:40 [INFO] Logged: 4146ed0a | MRK | Baseline_Momentum | acc=0.5833 | auc=0.5 | purge=7d
01:47:42 [INFO] Logged: 5e9c813b | MRK | LogisticRegression | acc=0.5015 | auc=0.5842 | purge=7d
01:47:43 [INFO] Feature selection — Stage 1 (variance): 22 → 22 features
01:47:43 [INFO] Feature selection — Stage 2 (correlation): → 22 features (dropped 0 correlated)
01:47:43 [INFO] Feature selection — Stage 3 (importance): → 16 features (dropped 6 low-importance)
01:47:43 [INFO] Feature selection complete: 22 → 16 features selected
01:47:43 [INFO]   [MRK] After importance gate: 16 features
01:48:03 [INFO] Logged: 9eab2b40 | MRK | RandomForest | acc=0.5342 | auc=0.5754 | purge=7d
01:48:26 [INFO] Logged: 662531b6 | MRK | XGBoost | acc=0.5451 | auc=0.5831 | purge=7d
01:48:26 [INFO]   [MRK] OK
01:48:26 [INFO]   ── AMGN ──
01:48:26 [INFO]   [AMGN] Building features…
01:48:26 [INFO] Feature selection — Stage 1 (variance): 48 → 23 features
01:48:26 [INFO] Feature selection — Stage 2 (correlation): → 22 features (dropped 1 correlated)
01:48:26 [INFO] Feature selection complete: 48 → 22 features selected
01:48:26 [INFO]   [AMGN] After variance/corr selection: 22 features
01:48:26 [INFO]   [AMGN] 2858 rows · 16 WF splits · 22 features
01:48:26 [INFO] Logged: ee8331e4 | AMGN | Baseline_Random | acc=0.4985 | auc=0.5242 | purge=7d
01:48:26 [INFO] Logged: ce90a902 | AMGN | Baseline_Momentum | acc=0.5312 | auc=0.5 | purge=7d
01:48:28 [INFO] Logged: 7492f66a | AMGN | LogisticRegression | acc=0.5293 | auc=0.7156 | purge=7d
01:48:30 [INFO] Feature selection — Stage 1 (variance): 22 → 22 features
01:48:30 [INFO] Feature selection — Stage 2 (correlation): → 22 features (dropped 0 correlated)
01:48:30 [INFO] Feature selection — Stage 3 (importance): → 14 features (dropped 8 low-importance)
01:48:30 [INFO] Feature selection complete: 22 → 14 features selected
01:48:30 [INFO]   [AMGN] After importance gate: 14 features
01:48:51 [INFO] Logged: ac169e71 | AMGN | RandomForest | acc=0.5461 | auc=0.6829 | purge=7d
01:49:11 [INFO] Logged: 67a622c0 | AMGN | XGBoost | acc=0.5263 | auc=0.6706 | purge=7d
01:49:11 [INFO]   [AMGN] OK
01:49:11 [INFO]   ── GILD ──
01:49:11 [INFO]   [GILD] Building features…
01:49:11 [INFO] Feature selection — Stage 1 (variance): 48 → 24 features
01:49:11 [INFO] Feature selection — Stage 2 (correlation): → 23 features (dropped 1 correlated)
01:49:11 [INFO] Feature selection complete: 48 → 23 features selected
01:49:11 [INFO]   [GILD] After variance/corr selection: 23 features
01:49:11 [INFO]   [GILD] 2858 rows · 16 WF splits · 23 features
01:49:11 [INFO] Logged: 499fe1b0 | GILD | Baseline_Random | acc=0.496 | auc=0.5252 | purge=7d
01:49:11 [INFO] Logged: 83a14ddf | GILD | Baseline_Momentum | acc=0.5437 | auc=0.5 | purge=7d
01:49:13 [INFO] Logged: cf6af50a | GILD | LogisticRegression | acc=0.4871 | auc=0.6146 | purge=7d
01:49:15 [INFO] Feature selection — Stage 1 (variance): 23 → 23 features
01:49:15 [INFO] Feature selection — Stage 2 (correlation): → 23 features (dropped 0 correlated)
01:49:15 [INFO] Feature selection — Stage 3 (importance): → 18 features (dropped 5 low-importance)
01:49:15 [INFO] Feature selection complete: 23 → 18 features selected
01:49:15 [INFO]   [GILD] After importance gate: 18 features
01:49:35 [INFO] Logged: bc18a4f8 | GILD | RandomForest | acc=0.5238 | auc=0.6124 | purge=7d
01:49:57 [INFO] Logged: ad32aab6 | GILD | XGBoost | acc=0.4891 | auc=0.5909 | purge=7d
01:49:57 [INFO]   [GILD] OK
01:49:57 [INFO]   ── TMO ──
01:49:57 [INFO]   [TMO] Building features…
01:49:57 [INFO] Feature selection — Stage 1 (variance): 40 → 24 features
01:49:57 [INFO] Feature selection — Stage 2 (correlation): → 23 features (dropped 1 correlated)
01:49:57 [INFO] Feature selection complete: 40 → 23 features selected
01:49:57 [INFO]   [TMO] After variance/corr selection: 23 features
01:49:58 [INFO]   [TMO] 2858 rows · 16 WF splits · 23 features
01:49:58 [INFO] Logged: 56ea14d2 | TMO | Baseline_Random | acc=0.5005 | auc=0.518 | purge=7d
01:49:58 [INFO] Logged: 87b042a8 | TMO | Baseline_Momentum | acc=0.5888 | auc=0.5 | purge=7d
01:50:00 [INFO] Logged: c374a5b5 | TMO | LogisticRegression | acc=0.563 | auc=0.7171 | purge=7d
01:50:02 [INFO] Feature selection — Stage 1 (variance): 23 → 23 features
01:50:02 [INFO] Feature selection — Stage 2 (correlation): → 23 features (dropped 0 correlated)
01:50:02 [INFO] Feature selection — Stage 3 (importance): → 16 features (dropped 7 low-importance)
01:50:02 [INFO] Feature selection complete: 23 → 16 features selected
01:50:02 [INFO]   [TMO] After importance gate: 16 features
01:50:23 [INFO] Logged: 7cb426dd | TMO | RandomForest | acc=0.561 | auc=0.6843 | purge=7d
01:50:44 [INFO] Logged: df6d3fff | TMO | XGBoost | acc=0.5491 | auc=0.6791 | purge=7d
01:50:44 [INFO]   [TMO] OK
01:50:44 [INFO]   ── BNTX ──
01:50:44 [INFO]   [BNTX] Building features…
01:50:44 [WARNING]   [BNTX] Too few clean rows; skipping
01:50:44 [INFO]   [BNTX] SKIPPED
01:50:44 [INFO]   ── VRTX ──
01:50:44 [INFO]   [VRTX] Building features…
01:50:45 [INFO] Feature selection — Stage 1 (variance): 40 → 25 features
01:50:45 [INFO] Feature selection — Stage 2 (correlation): → 24 features (dropped 1 correlated)
01:50:45 [INFO] Feature selection complete: 40 → 24 features selected
01:50:45 [INFO]   [VRTX] After variance/corr selection: 24 features
01:50:45 [INFO]   [VRTX] 2858 rows · 16 WF splits · 24 features
01:50:45 [INFO] Logged: a11ebe3c | VRTX | Baseline_Random | acc=0.503 | auc=0.5291 | purge=7d
01:50:45 [INFO] Logged: 2d6556a6 | VRTX | Baseline_Momentum | acc=0.5754 | auc=0.5 | purge=7d
01:50:47 [INFO] Logged: 0109832a | VRTX | LogisticRegression | acc=0.5228 | auc=0.5893 | purge=7d
01:50:48 [INFO] Feature selection — Stage 1 (variance): 24 → 24 features
01:50:48 [INFO] Feature selection — Stage 2 (correlation): → 24 features (dropped 0 correlated)
01:50:48 [INFO] Feature selection — Stage 3 (importance): → 18 features (dropped 6 low-importance)
01:50:48 [INFO] Feature selection complete: 24 → 18 features selected
01:50:48 [INFO]   [VRTX] After importance gate: 18 features
01:50:59 [INFO] Logged: 07dcdbf4 | VRTX | RandomForest | acc=0.568 | auc=0.5814 | purge=7d
01:51:07 [INFO] Logged: 574d1cdb | VRTX | XGBoost | acc=0.5332 | auc=0.5713 | purge=7d
01:51:07 [INFO]   [VRTX] OK
01:51:07 [INFO]   ── AXSM ──
01:51:07 [INFO]   [AXSM] Building features…
01:51:07 [WARNING]   [AXSM] Too few clean rows; skipping
01:51:07 [INFO]   [AXSM] SKIPPED
01:51:07 [INFO]   ── NVS ──
01:51:07 [INFO]   [NVS] Building features…
01:51:07 [INFO] Feature selection — Stage 1 (variance): 40 → 21 features
01:51:07 [INFO] Feature selection — Stage 2 (correlation): → 20 features (dropped 1 correlated)
01:51:07 [INFO] Feature selection complete: 40 → 20 features selected
01:51:07 [INFO]   [NVS] After variance/corr selection: 20 features
01:51:07 [INFO]   [NVS] 2858 rows · 16 WF splits · 20 features
01:51:07 [INFO] Logged: bedd4e60 | NVS | Baseline_Random | acc=0.5 | auc=0.5352 | purge=7d
01:51:07 [INFO] Logged: 7ea95ffb | NVS | Baseline_Momentum | acc=0.5744 | auc=0.5 | purge=7d
01:51:08 [INFO] Logged: 2d81bb1f | NVS | LogisticRegression | acc=0.4688 | auc=0.5332 | purge=7d
01:51:09 [INFO] Feature selection — Stage 1 (variance): 20 → 20 features
01:51:09 [INFO] Feature selection — Stage 2 (correlation): → 20 features (dropped 0 correlated)
01:51:09 [INFO] Feature selection — Stage 3 (importance): → 14 features (dropped 6 low-importance)
01:51:09 [INFO] Feature selection complete: 20 → 14 features selected
01:51:09 [INFO]   [NVS] After importance gate: 14 features
01:51:22 [INFO] Logged: 9c0f3e99 | NVS | RandomForest | acc=0.5198 | auc=0.6277 | purge=7d
01:51:30 [INFO] Logged: b6ae2ec4 | NVS | XGBoost | acc=0.5104 | auc=0.6309 | purge=7d
01:51:30 [INFO]   [NVS] OK
01:51:30 [INFO]   ── ATAI ──
01:51:30 [INFO]   [ATAI] Building features…
01:51:30 [WARNING]   [ATAI] Too few clean rows; skipping
01:51:30 [INFO]   [ATAI] SKIPPED
01:51:30 [INFO]   ── XOM ──
01:51:30 [INFO]   [XOM] Building features…
01:51:30 [INFO] Feature selection — Stage 1 (variance): 48 → 25 features
01:51:30 [INFO] Feature selection — Stage 2 (correlation): → 24 features (dropped 1 correlated)
01:51:30 [INFO] Feature selection complete: 48 → 24 features selected
01:51:30 [INFO]   [XOM] After variance/corr selection: 24 features
01:51:30 [INFO]   [XOM] 2858 rows · 16 WF splits · 24 features
01:51:30 [INFO] Logged: b29710ba | XOM | Baseline_Random | acc=0.4886 | auc=0.5061 | purge=7d
01:51:30 [INFO] Logged: 39c4062b | XOM | Baseline_Momentum | acc=0.5699 | auc=0.5 | purge=7d
01:51:31 [INFO] Logged: ba76f08d | XOM | LogisticRegression | acc=0.4955 | auc=0.6148 | purge=7d
01:51:32 [INFO] Feature selection — Stage 1 (variance): 24 → 24 features
01:51:32 [INFO] Feature selection — Stage 2 (correlation): → 24 features (dropped 0 correlated)
01:51:32 [INFO] Feature selection — Stage 3 (importance): → 17 features (dropped 7 low-importance)
01:51:32 [INFO] Feature selection complete: 24 → 17 features selected
01:51:32 [INFO]   [XOM] After importance gate: 17 features
01:51:45 [INFO] Logged: a1633f49 | XOM | RandomForest | acc=0.5288 | auc=0.6468 | purge=7d
01:51:52 [INFO] Logged: b216a961 | XOM | XGBoost | acc=0.5069 | auc=0.6092 | purge=7d
01:51:52 [INFO]   [XOM] OK
01:51:52 [INFO]   ── CVX ──
01:51:52 [INFO]   [CVX] Building features…
01:51:52 [INFO] Feature selection — Stage 1 (variance): 40 → 25 features
01:51:52 [INFO] Feature selection — Stage 2 (correlation): → 24 features (dropped 1 correlated)
01:51:52 [INFO] Feature selection complete: 40 → 24 features selected
01:51:52 [INFO]   [CVX] After variance/corr selection: 24 features
01:51:52 [INFO]   [CVX] 2858 rows · 16 WF splits · 24 features
01:51:52 [INFO] Logged: 5cedb71f | CVX | Baseline_Random | acc=0.4891 | auc=0.5057 | purge=7d
01:51:53 [INFO] Logged: 8d9de458 | CVX | Baseline_Momentum | acc=0.5694 | auc=0.5 | purge=7d
01:51:53 [INFO] Logged: 709a65f3 | CVX | LogisticRegression | acc=0.496 | auc=0.5947 | purge=7d
01:51:54 [INFO] Feature selection — Stage 1 (variance): 24 → 24 features
01:51:54 [INFO] Feature selection — Stage 2 (correlation): → 24 features (dropped 0 correlated)
01:51:54 [INFO] Feature selection — Stage 3 (importance): → 15 features (dropped 9 low-importance)
01:51:54 [INFO] Feature selection complete: 24 → 15 features selected
01:51:54 [INFO]   [CVX] After importance gate: 15 features
01:52:08 [INFO] Logged: a5f828a9 | CVX | RandomForest | acc=0.5511 | auc=0.7018 | purge=7d
01:52:20 [INFO] Logged: 0a27c1a0 | CVX | XGBoost | acc=0.5243 | auc=0.6836 | purge=7d
01:52:20 [INFO]   [CVX] OK
01:52:20 [INFO]   ── NEE ──
01:52:20 [INFO]   [NEE] Building features…
01:52:21 [INFO] Feature selection — Stage 1 (variance): 40 → 24 features
01:52:21 [INFO] Feature selection — Stage 2 (correlation): → 23 features (dropped 1 correlated)
01:52:21 [INFO] Feature selection complete: 40 → 23 features selected
01:52:21 [INFO]   [NEE] After variance/corr selection: 23 features
01:52:21 [INFO]   [NEE] 2858 rows · 16 WF splits · 23 features
01:52:21 [INFO] Logged: 84ee435e | NEE | Baseline_Random | acc=0.5099 | auc=0.4972 | purge=7d
01:52:21 [INFO] Logged: 6c856b12 | NEE | Baseline_Momentum | acc=0.6062 | auc=0.5 | purge=7d
01:52:23 [INFO] Logged: d3d897e5 | NEE | LogisticRegression | acc=0.5828 | auc=0.6952 | purge=7d
01:52:24 [INFO] Feature selection — Stage 1 (variance): 23 → 23 features
01:52:24 [INFO] Feature selection — Stage 2 (correlation): → 23 features (dropped 0 correlated)
01:52:24 [INFO] Feature selection — Stage 3 (importance): → 15 features (dropped 8 low-importance)
01:52:24 [INFO] Feature selection complete: 23 → 15 features selected
01:52:24 [INFO]   [NEE] After importance gate: 15 features
01:52:42 [INFO] Logged: 83a95353 | NEE | RandomForest | acc=0.5615 | auc=0.769 | purge=7d
01:53:05 [INFO] Logged: 95645bbd | NEE | XGBoost | acc=0.5947 | auc=0.746 | purge=7d
01:53:05 [INFO]   [NEE] OK
01:53:05 [INFO]   ── FSLR ──
01:53:05 [INFO]   [FSLR] Building features…
01:53:05 [INFO] Feature selection — Stage 1 (variance): 40 → 28 features
01:53:05 [INFO] Feature selection — Stage 2 (correlation): → 27 features (dropped 1 correlated)
01:53:05 [INFO] Feature selection complete: 40 → 27 features selected
01:53:05 [INFO]   [FSLR] After variance/corr selection: 27 features
01:53:05 [INFO]   [FSLR] 2858 rows · 16 WF splits · 27 features
01:53:05 [INFO] Logged: c86d31ae | FSLR | Baseline_Random | acc=0.4931 | auc=0.5051 | purge=7d
01:53:05 [INFO] Logged: b95f7ade | FSLR | Baseline_Momentum | acc=0.5397 | auc=0.5 | purge=7d
01:53:07 [INFO] Logged: abfc60a2 | FSLR | LogisticRegression | acc=0.5412 | auc=0.6709 | purge=7d
01:53:08 [INFO] Feature selection — Stage 1 (variance): 27 → 27 features
01:53:08 [INFO] Feature selection — Stage 2 (correlation): → 27 features (dropped 0 correlated)
01:53:08 [INFO] Feature selection — Stage 3 (importance): → 16 features (dropped 11 low-importance)
01:53:08 [INFO] Feature selection complete: 27 → 16 features selected
01:53:08 [INFO]   [FSLR] After importance gate: 16 features
01:53:28 [INFO] Logged: fe4ed310 | FSLR | RandomForest | acc=0.5184 | auc=0.579 | purge=7d
01:53:46 [INFO] Logged: 4f8ad3f8 | FSLR | XGBoost | acc=0.5005 | auc=0.5613 | purge=7d
01:53:46 [INFO]   [FSLR] OK
01:53:46 [INFO]   ── GEV ──
01:53:46 [INFO]   [GEV] Building features…
01:53:46 [WARNING]   [GEV] Too few clean rows; skipping
01:53:46 [INFO]   [GEV] SKIPPED
01:53:46 [INFO]   ── CCJ ──
01:53:46 [INFO]   [CCJ] Building features…
01:53:46 [INFO] Feature selection — Stage 1 (variance): 40 → 27 features
01:53:46 [INFO] Feature selection — Stage 2 (correlation): → 26 features (dropped 1 correlated)
01:53:46 [INFO] Feature selection complete: 40 → 26 features selected
01:53:46 [INFO]   [CCJ] After variance/corr selection: 26 features
01:53:46 [INFO]   [CCJ] 2858 rows · 16 WF splits · 26 features
01:53:46 [INFO] Logged: c2959897 | CCJ | Baseline_Random | acc=0.4896 | auc=0.4917 | purge=7d
01:53:46 [INFO] Logged: 1c8b6481 | CCJ | Baseline_Momentum | acc=0.565 | auc=0.5 | purge=7d
01:53:47 [INFO] Logged: aad995c7 | CCJ | LogisticRegression | acc=0.5362 | auc=0.6404 | purge=7d
01:53:48 [INFO] Feature selection — Stage 1 (variance): 26 → 26 features
01:53:48 [INFO] Feature selection — Stage 2 (correlation): → 26 features (dropped 0 correlated)
01:53:48 [INFO] Feature selection — Stage 3 (importance): → 16 features (dropped 10 low-importance)
01:53:48 [INFO] Feature selection complete: 26 → 16 features selected
01:53:48 [INFO]   [CCJ] After importance gate: 16 features
01:54:01 [INFO] Logged: 3bb8664b | CCJ | RandomForest | acc=0.5322 | auc=0.6332 | purge=7d
01:54:08 [INFO] Logged: 6df4fdf7 | CCJ | XGBoost | acc=0.5466 | auc=0.6005 | purge=7d
01:54:08 [INFO]   [CCJ] OK
01:54:08 [INFO]   ── CEG ──
01:54:08 [INFO]   [CEG] Building features…
01:54:08 [INFO] Feature selection — Stage 1 (variance): 40 → 27 features
01:54:08 [INFO] Feature selection — Stage 2 (correlation): → 27 features (dropped 0 correlated)
01:54:08 [INFO] Feature selection complete: 40 → 27 features selected
01:54:08 [INFO]   [CEG] After variance/corr selection: 27 features
01:54:08 [WARNING] walk_forward_splits: only 832 rows — insufficient for train=756 + buffer=7 + val=126. Returning 0 splits.
01:54:08 [WARNING]   [CEG] Not enough data for walk-forward splits
01:54:08 [INFO]   [CEG] SKIPPED
01:54:08 [INFO]   ── SMR ──
01:54:08 [INFO]   [SMR] Building features…
01:54:08 [WARNING]   [SMR] Too few clean rows; skipping
01:54:08 [INFO]   [SMR] SKIPPED
01:54:08 [INFO]   ── OKLO ──
01:54:08 [INFO]   [OKLO] Building features…
01:54:08 [WARNING]   [OKLO] Too few clean rows; skipping
01:54:08 [INFO]   [OKLO] SKIPPED
01:54:08 [INFO]   ── REP.DE ──
01:54:08 [INFO]   [REP.DE] Building features…
01:54:08 [INFO] Feature selection — Stage 1 (variance): 40 → 26 features
01:54:08 [INFO] Feature selection — Stage 2 (correlation): → 25 features (dropped 1 correlated)
01:54:08 [INFO] Feature selection complete: 40 → 25 features selected
01:54:08 [INFO]   [REP.DE] After variance/corr selection: 25 features
01:54:08 [INFO]   [REP.DE] 2534 rows · 14 WF splits · 25 features
01:54:08 [INFO] Logged: 2c07e5c0 | REP.DE | Baseline_Random | acc=0.5017 | auc=0.4776 | purge=7d
01:54:08 [INFO] Logged: fa17a2ba | REP.DE | Baseline_Momentum | acc=0.5731 | auc=0.5 | purge=7d
01:54:09 [INFO] Logged: 81bc92b3 | REP.DE | LogisticRegression | acc=0.449 | auc=0.5221 | purge=7d
01:54:10 [INFO] Feature selection — Stage 1 (variance): 25 → 25 features
01:54:10 [INFO] Feature selection — Stage 2 (correlation): → 25 features (dropped 0 correlated)
01:54:10 [INFO] Feature selection — Stage 3 (importance): → 19 features (dropped 6 low-importance)
01:54:10 [INFO] Feature selection complete: 25 → 19 features selected
01:54:10 [INFO]   [REP.DE] After importance gate: 19 features
01:54:21 [INFO] Logged: 593fec08 | REP.DE | RandomForest | acc=0.4433 | auc=0.6262 | purge=7d
01:54:39 [INFO] Logged: 161e19c8 | REP.DE | XGBoost | acc=0.4994 | auc=0.607 | purge=7d
01:54:39 [INFO]   [REP.DE] OK
01:54:39 [INFO]   ── ENB.DE ──
01:54:39 [INFO]   [ENB.DE] Building features…
01:54:40 [WARNING]   [ENB.DE] Too few clean rows; skipping
01:54:40 [INFO]   [ENB.DE] SKIPPED
01:54:40 [INFO]   ── EGI.DE ──
01:54:40 [INFO]   [EGI.DE] Building features…
01:54:40 [WARNING]   [EGI.DE] Too few clean rows; skipping
01:54:40 [INFO]   [EGI.DE] SKIPPED
01:54:40 [INFO]   ── BLM.DE ──
01:54:40 [INFO]   [BLM.DE] Building features…
01:54:40 [WARNING]   [BLM.DE] Too few clean rows; skipping
01:54:40 [INFO]   [BLM.DE] SKIPPED
01:54:40 [INFO]   ── BEP ──
01:54:40 [INFO]   [BEP] Building features…
01:54:40 [WARNING]   [BEP] Too few clean rows; skipping
01:54:40 [INFO]   [BEP] SKIPPED
01:54:40 [INFO]   ── RIO ──
01:54:40 [INFO]   [RIO] Building features…
01:54:40 [INFO] Feature selection — Stage 1 (variance): 40 → 26 features
01:54:40 [INFO] Feature selection — Stage 2 (correlation): → 25 features (dropped 1 correlated)
01:54:40 [INFO] Feature selection complete: 40 → 25 features selected
01:54:40 [INFO]   [RIO] After variance/corr selection: 25 features
01:54:40 [INFO]   [RIO] 2858 rows · 16 WF splits · 25 features
01:54:40 [INFO] Logged: dce0db82 | RIO | Baseline_Random | acc=0.502 | auc=0.5183 | purge=7d
01:54:41 [INFO] Logged: 9aa01ed2 | RIO | Baseline_Momentum | acc=0.5804 | auc=0.5 | purge=7d
01:54:43 [INFO] Logged: fe669fe9 | RIO | LogisticRegression | acc=0.4901 | auc=0.5407 | purge=7d
01:54:44 [INFO] Feature selection — Stage 1 (variance): 25 → 25 features
01:54:44 [INFO] Feature selection — Stage 2 (correlation): → 25 features (dropped 0 correlated)
01:54:44 [INFO] Feature selection — Stage 3 (importance): → 20 features (dropped 5 low-importance)
01:54:44 [INFO] Feature selection complete: 25 → 20 features selected
01:54:44 [INFO]   [RIO] After importance gate: 20 features
01:55:00 [INFO] Logged: 8ca42206 | RIO | RandomForest | acc=0.5025 | auc=0.5531 | purge=7d
01:55:21 [INFO] Logged: cf982827 | RIO | XGBoost | acc=0.4757 | auc=0.57 | purge=7d
01:55:21 [INFO]   [RIO] OK
01:55:21 [INFO]   ── ERO ──
01:55:21 [INFO]   [ERO] Building features…
01:55:22 [INFO] Feature selection — Stage 1 (variance): 40 → 28 features
01:55:22 [INFO] Feature selection — Stage 2 (correlation): → 28 features (dropped 0 correlated)
01:55:22 [INFO] Feature selection complete: 40 → 28 features selected
01:55:22 [INFO]   [ERO] After variance/corr selection: 28 features
01:55:22 [INFO]   [ERO] 1345 rows · 4 WF splits · 28 features
01:55:22 [INFO] Logged: 6769b2b1 | ERO | Baseline_Random | acc=0.5119 | auc=0.4906 | purge=7d
01:55:22 [INFO] Logged: deca4115 | ERO | Baseline_Momentum | acc=0.5952 | auc=0.5 | purge=7d
01:55:22 [INFO] Logged: cb92b617 | ERO | LogisticRegression | acc=0.4385 | auc=0.5914 | purge=7d
01:55:24 [INFO] Feature selection — Stage 1 (variance): 28 → 28 features
01:55:24 [INFO] Feature selection — Stage 2 (correlation): → 28 features (dropped 0 correlated)
01:55:24 [INFO] Feature selection — Stage 3 (importance): → 19 features (dropped 9 low-importance)
01:55:24 [INFO] Feature selection complete: 28 → 19 features selected
01:55:24 [INFO]   [ERO] After importance gate: 19 features
01:55:28 [INFO] Logged: 6efcc79e | ERO | RandomForest | acc=0.4345 | auc=0.5481 | purge=7d
01:55:33 [INFO] Logged: 9b1446dc | ERO | XGBoost | acc=0.4405 | auc=0.5169 | purge=7d
01:55:33 [INFO]   [ERO] OK
01:55:33 [INFO]   ── FCX ──
01:55:33 [INFO]   [FCX] Building features…
01:55:33 [INFO] Feature selection — Stage 1 (variance): 40 → 28 features
01:55:33 [INFO] Feature selection — Stage 2 (correlation): → 27 features (dropped 1 correlated)
01:55:33 [INFO] Feature selection complete: 40 → 27 features selected
01:55:33 [INFO]   [FCX] After variance/corr selection: 27 features
01:55:33 [INFO]   [FCX] 2858 rows · 16 WF splits · 27 features
01:55:34 [INFO] Logged: cdbbdcdd | FCX | Baseline_Random | acc=0.5005 | auc=0.5072 | purge=7d
01:55:34 [INFO] Logged: 85f9b03e | FCX | Baseline_Momentum | acc=0.5303 | auc=0.5 | purge=7d
01:55:36 [INFO] Logged: ab99666f | FCX | LogisticRegression | acc=0.5069 | auc=0.6245 | purge=7d
01:55:37 [INFO] Feature selection — Stage 1 (variance): 27 → 27 features
01:55:37 [INFO] Feature selection — Stage 2 (correlation): → 27 features (dropped 0 correlated)
01:55:37 [INFO] Feature selection — Stage 3 (importance): → 15 features (dropped 12 low-importance)
01:55:37 [INFO] Feature selection complete: 27 → 15 features selected
01:55:37 [INFO]   [FCX] After importance gate: 15 features
01:56:00 [INFO] Logged: 6cdd9ab1 | FCX | RandomForest | acc=0.4965 | auc=0.6089 | purge=7d
01:56:19 [INFO] Logged: 1ccf75fe | FCX | XGBoost | acc=0.4846 | auc=0.6131 | purge=7d
01:56:19 [INFO]   [FCX] OK
01:56:19 [INFO]   ── ALB ──
01:56:19 [INFO]   [ALB] Building features…
01:56:19 [WARNING]   [ALB] Too few clean rows; skipping
01:56:19 [INFO]   [ALB] SKIPPED
01:56:19 [INFO]   ── MIN ──
01:56:19 [INFO]   [MIN] Building features…
01:56:19 [WARNING]   [MIN] Too few clean rows; skipping
01:56:19 [INFO]   [MIN] SKIPPED
01:56:19 [INFO]   ── C1E.DE ──
01:56:19 [INFO]   [C1E.DE] Building features…
01:56:19 [WARNING]   [C1E.DE] Too few clean rows; skipping
01:56:19 [INFO]   [C1E.DE] SKIPPED
01:56:19 [INFO]   ── VO51.DE ──
01:56:19 [INFO]   [VO51.DE] Building features…
01:56:20 [WARNING]   [VO51.DE] Too few clean rows; skipping
01:56:20 [INFO]   [VO51.DE] SKIPPED
01:56:20 [INFO]   ── U6Z.DE ──
01:56:20 [INFO]   [U6Z.DE] Building features…
01:56:20 [WARNING]   [U6Z.DE] Too few clean rows; skipping
01:56:20 [INFO]   [U6Z.DE] SKIPPED
01:56:20 [INFO]   ── BA ──
01:56:20 [INFO]   [BA] Building features…
01:56:20 [INFO] Feature selection — Stage 1 (variance): 48 → 27 features
01:56:20 [INFO] Feature selection — Stage 2 (correlation): → 26 features (dropped 1 correlated)
01:56:20 [INFO] Feature selection complete: 48 → 26 features selected
01:56:20 [INFO]   [BA] After variance/corr selection: 26 features
01:56:20 [INFO]   [BA] 2858 rows · 16 WF splits · 26 features
01:56:20 [INFO] Logged: a8b07e54 | BA | Baseline_Random | acc=0.496 | auc=0.532 | purge=7d
01:56:20 [INFO] Logged: 26d15c98 | BA | Baseline_Momentum | acc=0.4871 | auc=0.5 | purge=7d
01:56:23 [INFO] Logged: 71f9e8bd | BA | LogisticRegression | acc=0.5456 | auc=0.6038 | purge=7d
01:56:24 [INFO] Feature selection — Stage 1 (variance): 26 → 26 features
01:56:24 [INFO] Feature selection — Stage 2 (correlation): → 26 features (dropped 0 correlated)
01:56:24 [INFO] Feature selection — Stage 3 (importance): → 18 features (dropped 8 low-importance)
01:56:24 [INFO] Feature selection complete: 26 → 18 features selected
01:56:24 [INFO]   [BA] After importance gate: 18 features
01:56:47 [INFO] Logged: b8e2dc78 | BA | RandomForest | acc=0.5476 | auc=0.6469 | purge=7d
01:57:05 [INFO] Logged: e5dc9dd4 | BA | XGBoost | acc=0.5372 | auc=0.6124 | purge=7d
01:57:05 [INFO]   [BA] OK
01:57:05 [INFO]   ── CAT ──
01:57:05 [INFO]   [CAT] Building features…
01:57:05 [INFO] Feature selection — Stage 1 (variance): 48 → 26 features
01:57:05 [INFO] Feature selection — Stage 2 (correlation): → 25 features (dropped 1 correlated)
01:57:05 [INFO] Feature selection complete: 48 → 25 features selected
01:57:05 [INFO]   [CAT] After variance/corr selection: 25 features
01:57:05 [INFO]   [CAT] 2858 rows · 16 WF splits · 25 features
01:57:05 [INFO] Logged: 1365796c | CAT | Baseline_Random | acc=0.5042 | auc=0.5278 | purge=7d
01:57:06 [INFO] Logged: a9a89ae6 | CAT | Baseline_Momentum | acc=0.6071 | auc=0.5 | purge=7d
01:57:06 [INFO] Logged: a9933a4e | CAT | LogisticRegression | acc=0.5114 | auc=0.5743 | purge=7d
01:57:07 [INFO] Feature selection — Stage 1 (variance): 25 → 25 features
01:57:07 [INFO] Feature selection — Stage 2 (correlation): → 25 features (dropped 0 correlated)
01:57:07 [INFO] Feature selection — Stage 3 (importance): → 14 features (dropped 11 low-importance)
01:57:07 [INFO] Feature selection complete: 25 → 14 features selected
01:57:07 [INFO]   [CAT] After importance gate: 14 features
01:57:22 [INFO] Logged: 696ca9ee | CAT | RandomForest | acc=0.5144 | auc=0.5957 | purge=7d
01:57:30 [INFO] Logged: e4a935de | CAT | XGBoost | acc=0.4926 | auc=0.5838 | purge=7d
01:57:30 [INFO]   [CAT] OK
01:57:30 [INFO]   ── LMT ──
01:57:30 [INFO]   [LMT] Building features…
01:57:30 [INFO] Feature selection — Stage 1 (variance): 48 → 24 features
01:57:30 [INFO] Feature selection — Stage 2 (correlation): → 23 features (dropped 1 correlated)
01:57:30 [INFO] Feature selection complete: 48 → 23 features selected
01:57:30 [INFO]   [LMT] After variance/corr selection: 23 features
01:57:30 [INFO]   [LMT] 2858 rows · 16 WF splits · 23 features
01:57:30 [INFO] Logged: 11d3942e | LMT | Baseline_Random | acc=0.5119 | auc=0.4807 | purge=7d
01:57:30 [INFO] Logged: 3fa285bd | LMT | Baseline_Momentum | acc=0.5536 | auc=0.5 | purge=7d
01:57:31 [INFO] Logged: 398868dd | LMT | LogisticRegression | acc=0.4623 | auc=0.5466 | purge=7d
01:57:32 [INFO] Feature selection — Stage 1 (variance): 23 → 23 features
01:57:32 [INFO] Feature selection — Stage 2 (correlation): → 23 features (dropped 0 correlated)
01:57:32 [INFO] Feature selection — Stage 3 (importance): → 18 features (dropped 5 low-importance)
01:57:32 [INFO] Feature selection complete: 23 → 18 features selected
01:57:32 [INFO]   [LMT] After importance gate: 18 features
01:57:48 [INFO] Logged: d0406a29 | LMT | RandomForest | acc=0.5203 | auc=0.5641 | purge=7d
01:57:56 [INFO] Logged: 6bd81efa | LMT | XGBoost | acc=0.5055 | auc=0.611 | purge=7d
01:57:56 [INFO]   [LMT] OK
01:57:56 [INFO]   ── RTX ──
01:57:56 [INFO]   [RTX] Building features…
01:57:56 [INFO] Feature selection — Stage 1 (variance): 48 → 25 features
01:57:56 [INFO] Feature selection — Stage 2 (correlation): → 24 features (dropped 1 correlated)
01:57:56 [INFO] Feature selection complete: 48 → 24 features selected
01:57:56 [INFO]   [RTX] After variance/corr selection: 24 features
01:57:56 [INFO]   [RTX] 2858 rows · 16 WF splits · 24 features
01:57:56 [INFO] Logged: a23590dc | RTX | Baseline_Random | acc=0.494 | auc=0.5067 | purge=7d
01:57:56 [INFO] Logged: 1fc045d5 | RTX | Baseline_Momentum | acc=0.6002 | auc=0.5 | purge=7d
01:57:58 [INFO] Logged: 79f5869d | RTX | LogisticRegression | acc=0.5675 | auc=0.53 | purge=7d
01:57:59 [INFO] Feature selection — Stage 1 (variance): 24 → 24 features
01:57:59 [INFO] Feature selection — Stage 2 (correlation): → 24 features (dropped 0 correlated)
01:57:59 [INFO] Feature selection — Stage 3 (importance): → 18 features (dropped 6 low-importance)
01:57:59 [INFO] Feature selection complete: 24 → 18 features selected
01:57:59 [INFO]   [RTX] After importance gate: 18 features
01:58:14 [INFO] Logged: 8b336ada | RTX | RandomForest | acc=0.5074 | auc=0.5702 | purge=7d
01:58:21 [INFO] Logged: 7eb1bbaa | RTX | XGBoost | acc=0.5293 | auc=0.6073 | purge=7d
01:58:21 [INFO]   [RTX] OK
01:58:21 [INFO]   ── GE ──
01:58:21 [INFO]   [GE] Building features…
01:58:22 [INFO] Feature selection — Stage 1 (variance): 48 → 26 features
01:58:22 [INFO] Feature selection — Stage 2 (correlation): → 25 features (dropped 1 correlated)
01:58:22 [INFO] Feature selection complete: 48 → 25 features selected
01:58:22 [INFO]   [GE] After variance/corr selection: 25 features
01:58:22 [INFO]   [GE] 2858 rows · 16 WF splits · 25 features
01:58:22 [INFO] Logged: 5e770724 | GE | Baseline_Random | acc=0.4931 | auc=0.5189 | purge=7d
01:58:22 [INFO] Logged: d37a9d3b | GE | Baseline_Momentum | acc=0.5769 | auc=0.5 | purge=7d
01:58:23 [INFO] Logged: f5396c38 | GE | LogisticRegression | acc=0.5565 | auc=0.5582 | purge=7d
01:58:24 [INFO] Feature selection — Stage 1 (variance): 25 → 25 features
01:58:24 [INFO] Feature selection — Stage 2 (correlation): → 25 features (dropped 0 correlated)
01:58:24 [INFO] Feature selection — Stage 3 (importance): → 18 features (dropped 7 low-importance)
01:58:24 [INFO] Feature selection complete: 25 → 18 features selected
01:58:24 [INFO]   [GE] After importance gate: 18 features
01:58:40 [INFO] Logged: 2b4d1c55 | GE | RandomForest | acc=0.5074 | auc=0.5473 | purge=7d
01:58:53 [INFO] Logged: 38c81b47 | GE | XGBoost | acc=0.5407 | auc=0.5519 | purge=7d
01:58:53 [INFO]   [GE] OK
01:58:53 [INFO]   ── HON ──
01:58:53 [INFO]   [HON] Building features…
01:58:53 [INFO] Feature selection — Stage 1 (variance): 48 → 23 features
01:58:53 [INFO] Feature selection — Stage 2 (correlation): → 22 features (dropped 1 correlated)
01:58:53 [INFO] Feature selection complete: 48 → 22 features selected
01:58:53 [INFO]   [HON] After variance/corr selection: 22 features
01:58:53 [INFO]   [HON] 2858 rows · 16 WF splits · 22 features
01:58:54 [INFO] Logged: 97ed47b0 | HON | Baseline_Random | acc=0.4866 | auc=0.4831 | purge=7d
01:58:54 [INFO] Logged: 119d3ae1 | HON | Baseline_Momentum | acc=0.5432 | auc=0.5 | purge=7d
01:58:56 [INFO] Logged: 49d8e179 | HON | LogisticRegression | acc=0.5565 | auc=0.6195 | purge=7d
01:58:57 [INFO] Feature selection — Stage 1 (variance): 22 → 22 features
01:58:58 [INFO] Feature selection — Stage 2 (correlation): → 22 features (dropped 0 correlated)
01:58:58 [INFO] Feature selection — Stage 3 (importance): → 17 features (dropped 5 low-importance)
01:58:58 [INFO] Feature selection complete: 22 → 17 features selected
01:58:58 [INFO]   [HON] After importance gate: 17 features
01:59:20 [INFO] Logged: 00fcd034 | HON | RandomForest | acc=0.4846 | auc=0.6232 | purge=7d
01:59:43 [INFO] Logged: 6315b2bf | HON | XGBoost | acc=0.5184 | auc=0.604 | purge=7d
01:59:43 [INFO]   [HON] OK
01:59:43 [INFO]   ── UPS ──
01:59:43 [INFO]   [UPS] Building features…
01:59:43 [INFO] Feature selection — Stage 1 (variance): 40 → 25 features
01:59:44 [INFO] Feature selection — Stage 2 (correlation): → 24 features (dropped 1 correlated)
01:59:44 [INFO] Feature selection complete: 40 → 24 features selected
01:59:44 [INFO]   [UPS] After variance/corr selection: 24 features
01:59:44 [INFO]   [UPS] 2858 rows · 16 WF splits · 24 features
01:59:44 [INFO] Logged: 29f26aee | UPS | Baseline_Random | acc=0.497 | auc=0.5101 | purge=7d
01:59:44 [INFO] Logged: 13662052 | UPS | Baseline_Momentum | acc=0.5347 | auc=0.5 | purge=7d
01:59:46 [INFO] Logged: d12add77 | UPS | LogisticRegression | acc=0.5451 | auc=0.6947 | purge=7d
01:59:47 [INFO] Feature selection — Stage 1 (variance): 24 → 24 features
01:59:47 [INFO] Feature selection — Stage 2 (correlation): → 24 features (dropped 0 correlated)
01:59:47 [INFO] Feature selection — Stage 3 (importance): → 14 features (dropped 10 low-importance)
01:59:47 [INFO] Feature selection complete: 24 → 14 features selected
01:59:47 [INFO]   [UPS] After importance gate: 14 features
02:00:10 [INFO] Logged: 46628056 | UPS | RandomForest | acc=0.5188 | auc=0.6904 | purge=7d
02:00:32 [INFO] Logged: abcf5c60 | UPS | XGBoost | acc=0.4936 | auc=0.6975 | purge=7d
02:00:32 [INFO]   [UPS] OK
02:00:32 [INFO]   ── DE ──
02:00:32 [INFO]   [DE] Building features…
02:00:32 [INFO] Feature selection — Stage 1 (variance): 40 → 24 features
02:00:32 [INFO] Feature selection — Stage 2 (correlation): → 23 features (dropped 1 correlated)
02:00:32 [INFO] Feature selection complete: 40 → 23 features selected
02:00:32 [INFO]   [DE] After variance/corr selection: 23 features
02:00:32 [INFO]   [DE] 2858 rows · 16 WF splits · 23 features
02:00:32 [INFO] Logged: 84c6dd7f | DE | Baseline_Random | acc=0.4995 | auc=0.508 | purge=7d
02:00:33 [INFO] Logged: aa32252d | DE | Baseline_Momentum | acc=0.5441 | auc=0.5 | purge=7d
02:00:35 [INFO] Logged: 226db2bb | DE | LogisticRegression | acc=0.5193 | auc=0.5736 | purge=7d
02:00:36 [INFO] Feature selection — Stage 1 (variance): 23 → 23 features
02:00:36 [INFO] Feature selection — Stage 2 (correlation): → 23 features (dropped 0 correlated)
02:00:36 [INFO] Feature selection — Stage 3 (importance): → 17 features (dropped 6 low-importance)
02:00:36 [INFO] Feature selection complete: 23 → 17 features selected
02:00:36 [INFO]   [DE] After importance gate: 17 features
02:00:59 [INFO] Logged: 8dbfb6e7 | DE | RandomForest | acc=0.5084 | auc=0.6217 | purge=7d
02:01:21 [INFO] Logged: b684a7a0 | DE | XGBoost | acc=0.4831 | auc=0.6192 | purge=7d
02:01:21 [INFO]   [DE] OK
02:01:21 [INFO]   ── RHM.DE ──
02:01:21 [INFO]   [RHM.DE] Building features…
02:01:21 [INFO] Feature selection — Stage 1 (variance): 40 → 27 features
02:01:21 [INFO] Feature selection — Stage 2 (correlation): → 26 features (dropped 1 correlated)
02:01:21 [INFO] Feature selection complete: 40 → 26 features selected
02:01:21 [INFO]   [RHM.DE] After variance/corr selection: 26 features
02:01:21 [INFO]   [RHM.DE] 2783 rows · 16 WF splits · 26 features
02:01:21 [INFO] Logged: c6a34189 | RHM.DE | Baseline_Random | acc=0.5084 | auc=0.4759 | purge=7d
02:01:21 [INFO] Logged: 5b836957 | RHM.DE | Baseline_Momentum | acc=0.5749 | auc=0.5 | purge=7d
02:01:23 [INFO] Logged: f3f2cd82 | RHM.DE | LogisticRegression | acc=0.5278 | auc=0.5336 | purge=7d
02:01:25 [INFO] Feature selection — Stage 1 (variance): 26 → 26 features
02:01:25 [INFO] Feature selection — Stage 2 (correlation): → 26 features (dropped 0 correlated)
02:01:25 [INFO] Feature selection — Stage 3 (importance): → 18 features (dropped 8 low-importance)
02:01:25 [INFO] Feature selection complete: 26 → 18 features selected
02:01:25 [INFO]   [RHM.DE] After importance gate: 18 features
02:01:48 [INFO] Logged: 489bbb95 | RHM.DE | RandomForest | acc=0.5213 | auc=0.5914 | purge=7d
02:01:55 [INFO] Logged: eae706cc | RHM.DE | XGBoost | acc=0.4921 | auc=0.6577 | purge=7d
02:01:55 [INFO]   [RHM.DE] OK
02:01:55 [INFO]   ── EUNL.DE ──
02:01:55 [INFO]   [EUNL.DE] Building features…
02:01:55 [WARNING]   [EUNL.DE] Too few clean rows; skipping
02:01:55 [INFO]   [EUNL.DE] SKIPPED
02:01:55 [INFO]   ── VUSA.DE ──
02:01:55 [INFO]   [VUSA.DE] Building features…
02:01:55 [WARNING]   [VUSA.DE] Too few clean rows; skipping
02:01:55 [INFO]   [VUSA.DE] SKIPPED
02:01:55 [INFO]   ── VWCE.DE ──
02:01:55 [INFO]   [VWCE.DE] Building features…
02:01:55 [WARNING]   [VWCE.DE] Too few clean rows; skipping
02:01:55 [INFO]   [VWCE.DE] SKIPPED
02:01:55 [INFO]   ── EXS1.DE ──
02:01:55 [INFO]   [EXS1.DE] Building features…
02:01:55 [WARNING]   [EXS1.DE] Too few clean rows; skipping
02:01:55 [INFO]   [EXS1.DE] SKIPPED
02:01:55 [INFO]   ── EXXT.DE ──
02:01:55 [INFO]   [EXXT.DE] Building features…
02:01:56 [WARNING]   [EXXT.DE] Too few clean rows; skipping
02:01:56 [INFO]   [EXXT.DE] SKIPPED
02:01:56 [INFO]   ── SPPW.DE ──
02:01:56 [INFO]   [SPPW.DE] Building features…
02:01:56 [WARNING]   [SPPW.DE] Too few clean rows; skipping
02:01:56 [INFO]   [SPPW.DE] SKIPPED
02:01:56 [INFO]   ── IS3N.DE ──
02:01:56 [INFO]   [IS3N.DE] Building features…
02:01:56 [WARNING]   [IS3N.DE] Too few clean rows; skipping
02:01:56 [INFO]   [IS3N.DE] SKIPPED
02:01:56 [INFO]   ── IUSN.DE ──
02:01:56 [INFO]   [IUSN.DE] Building features…
02:01:56 [WARNING]   [IUSN.DE] Too few clean rows; skipping
02:01:56 [INFO]   [IUSN.DE] SKIPPED
02:01:56 [INFO]   ── XDWD.DE ──
02:01:56 [INFO]   [XDWD.DE] Building features…
02:01:56 [WARNING]   [XDWD.DE] Too few clean rows; skipping
02:01:56 [INFO]   [XDWD.DE] SKIPPED
02:01:56 [INFO]   ── ZPRV.DE ──
02:01:56 [INFO]   [ZPRV.DE] Building features…
02:01:56 [WARNING]   [ZPRV.DE] Too few clean rows; skipping
02:01:56 [INFO]   [ZPRV.DE] SKIPPED
02:01:56 [INFO]   ── DBXD.DE ──
02:01:56 [INFO]   [DBXD.DE] Building features…
02:01:56 [WARNING]   [DBXD.DE] Too few clean rows; skipping
02:01:56 [INFO]   [DBXD.DE] SKIPPED
02:01:56 [INFO]   ── PPFD.SG ──
02:01:56 [INFO]   [PPFD.SG] Building features…
02:01:56 [WARNING]   [PPFD.SG] Too few rows (0); skipping
02:01:56 [INFO]   [PPFD.SG] SKIPPED
02:01:56 [INFO] Step 2 done. 78/135 tickers succeeded.
02:01:56 [INFO] Step 3/5 — Building ml_state payload…
02:01:56 [INFO] Step 4/5 — Writing to C:\Users\ahmty\Desktop\hedge-fund\shared\state\ml_state.json…
02:01:56 [INFO]   Written (primary):  C:\Users\ahmty\Desktop\hedge-fund\shared\state\ml_state.json
02:01:56 [INFO]   Versioned feature matrix → feature_matrix_20260820_0201.parquet
02:01:56 [INFO]   Written (legacy):   C:\Users\ahmty\Desktop\hedge-fund\portfolio\data\ml_state.json
02:01:56 [INFO] Step 5/5 — Summary:
02:01:56 [INFO]   Ensemble verdict : MIXED
02:01:56 [INFO]   Weighted score   : 0.4943
02:01:56 [INFO]   Tickers covered  : 78
02:01:56 [INFO]   Best model       : XGBoost  AUC=0.6149  Sharpe=0.0
02:01:56 [INFO]   Beats baseline   : 100% of models
02:01:56 [INFO] ============================================================
02:01:56 [INFO]  DONE — refresh the ML RESEARCH tab in the dashboard
02:01:56 [INFO] ============================================================
[5/6] Mirroring Research to Production & Rebalancing...
2026-08-20 02:02:09,673 INFO [scheduler] ============================================================
  Pipeline: 2026-08-20 (weekday=3)
  Tickers: 135
============================================================
2026-08-20 02:02:09,680 INFO [scheduler] [mirror] pead_state.json → shared/state/
2026-08-20 02:02:09,689 INFO [scheduler] [mirror] pead_setups.csv → shared/state/
2026-08-20 02:02:09,690 INFO [scheduler] [mirror] 2 copied, 2 already fresh, 0 sources not found
2026-08-20 02:02:09,785 INFO [scheduler] ▶ 0.  Ledger import
2026-08-20 02:02:09,873 INFO [engine.reconciliation.ledger_importer] [ledger] Replay complete: 9 positions, cash=€404.01
2026-08-20 02:02:10,593 INFO [engine.reconciliation.ledger_importer] [ledger] Synced 9 positions + cash=€404.01 (total portfolio ≈ €1252.69) for 2026-08-20
2026-08-20 02:02:10,608 INFO [engine.reconciliation.ledger_importer]
[ledger] Trade Advisor Summary:
2026-08-20 02:02:10,611 INFO [engine.reconciliation.ledger_importer]   SELL AMZ.DE       -0.5743 shares  €-128.97  (currently 17.9% → target 7.6%)
2026-08-20 02:02:10,612 INFO [engine.reconciliation.ledger_importer]   BUY  APC.DE       +0.0000 shares  €+118.27  (currently 0.0% → target 9.4%)
2026-08-20 02:02:10,612 INFO [engine.reconciliation.ledger_importer]   SELL PPFD.SG      -1.7216 shares  €-90.15  (currently 8.3% → target 1.1%)
2026-08-20 02:02:10,613 INFO [engine.reconciliation.ledger_importer]   SELL VO51.DE      -4.9877 shares  €-74.07  (currently 7.1% → target 1.2%)
2026-08-20 02:02:10,613 INFO [engine.reconciliation.ledger_importer]   BUY  MIN          +0.0000 shares  €+55.49  (currently 0.0% → target 4.4%)
2026-08-20 02:02:10,613 INFO [engine.reconciliation.ledger_importer]   BUY  CAT          +0.0000 shares  €+51.74  (currently 0.0% → target 4.1%)
2026-08-20 02:02:10,614 INFO [engine.reconciliation.ledger_importer]   SELL NEE          -0.6459 shares  €-47.92  (currently 11.8% → target 8.0%)
2026-08-20 02:02:10,615 INFO [engine.reconciliation.ledger_importer]   BUY  BAS.DE       +0.0000 shares  €+45.22  (currently 0.0% → target 3.6%)
2026-08-20 02:02:10,615 INFO [engine.reconciliation.ledger_importer]   SELL FIG          -2.0000 shares  €-41.75  (currently 3.3% → target 0.0%)
2026-08-20 02:02:10,615 INFO [engine.reconciliation.ledger_importer]   BUY  MTU.DE       +0.0000 shares  €+36.33  (currently 0.0% → target 2.9%)
2026-08-20 02:02:10,617 INFO [engine.reconciliation.ledger_importer]   BUY  ENB.DE       +0.0000 shares  €+29.06  (currently 0.0% → target 2.3%)
2026-08-20 02:02:10,618 INFO [engine.reconciliation.ledger_importer]   BUY  BRYN.DE      +0.0000 shares  €+29.06  (currently 0.0% → target 2.3%)
2026-08-20 02:02:10,619 INFO [engine.reconciliation.ledger_importer]   BUY  HEN3.DE      +0.0000 shares  €+28.94  (currently 0.0% → target 2.3%)
2026-08-20 02:02:10,619 INFO [engine.reconciliation.ledger_importer]   BUY  BMW.DE       +0.0000 shares  €+28.31  (currently 0.0% → target 2.3%)
2026-08-20 02:02:10,620 INFO [engine.reconciliation.ledger_importer]   BUY  MTX.DE       +0.0000 shares  €+26.18  (currently 0.0% → target 2.1%)
2026-08-20 02:02:10,620 INFO [engine.reconciliation.ledger_importer]   BUY  TTE.PA       +0.0000 shares  €+24.55  (currently 0.0% → target 2.0%)
2026-08-20 02:02:10,621 INFO [engine.reconciliation.ledger_importer]   SELL TL0.DE       -0.0789 shares  €-22.97  (currently 1.8% → target 0.0%)
2026-08-20 02:02:10,621 INFO [engine.reconciliation.ledger_importer]   BUY  1IN.DE       +0.0000 shares  €+21.92  (currently 0.0% → target 1.8%)
2026-08-20 02:02:10,621 INFO [engine.reconciliation.ledger_importer]   BUY  NDX1.DE      +0.0000 shares  €+21.42  (currently 0.0% → target 1.7%)
2026-08-20 02:02:10,622 INFO [engine.reconciliation.ledger_importer]   BUY  TMO          +0.0000 shares  €+20.79  (currently 0.0% → target 1.7%)
2026-08-20 02:02:10,622 INFO [engine.reconciliation.ledger_importer]   BUY  NOV.DE       +0.0000 shares  €+18.67  (currently 0.0% → target 1.5%)
2026-08-20 02:02:10,623 INFO [engine.reconciliation.ledger_importer]   BUY  ADS.DE       +0.0000 shares  €+18.54  (currently 0.0% → target 1.5%)
2026-08-20 02:02:10,624 INFO [engine.reconciliation.ledger_importer]   BUY  ORC.DE       +0.0000 shares  €+18.54  (currently 0.0% → target 1.5%)
2026-08-20 02:02:10,624 INFO [engine.reconciliation.ledger_importer]   BUY  AXP.DE       +0.0000 shares  €+18.29  (currently 0.0% → target 1.5%)
2026-08-20 02:02:10,624 INFO [engine.reconciliation.ledger_importer]   BUY  ABBV         +0.0000 shares  €+15.66  (currently 0.0% → target 1.2%)
2026-08-20 02:02:10,625 INFO [engine.reconciliation.ledger_importer]   BUY  CEG          +0.0000 shares  €+15.41  (currently 0.0% → target 1.2%)
2026-08-20 02:02:10,625 INFO [engine.reconciliation.ledger_importer]   BUY  AMGN         +0.0000 shares  €+13.65  (currently 0.0% → target 1.1%)
2026-08-20 02:02:10,626 INFO [engine.reconciliation.ledger_importer]   BUY  RTX          +0.0000 shares  €+12.90  (currently 0.0% → target 1.0%)
2026-08-20 02:02:10,626 INFO [engine.reconciliation.ledger_importer]   BUY  MBG.DE       +0.0000 shares  €+12.65  (currently 0.0% → target 1.0%)
2026-08-20 02:02:10,627 INFO [engine.reconciliation.ledger_importer]   BUY  BEI.DE       +0.0000 shares  €+11.90  (currently 0.0% → target 0.9%)
2026-08-20 02:02:10,627 INFO [engine.reconciliation.ledger_importer]   BUY  NKE          +0.0000 shares  €+11.90  (currently 0.0% → target 0.9%)
2026-08-20 02:02:10,627 INFO [engine.reconciliation.ledger_importer]   BUY  OKLO         +0.0000 shares  €+11.40  (currently 0.0% → target 0.9%)
2026-08-20 02:02:10,628 INFO [engine.reconciliation.ledger_importer]   BUY  FRE.DE       +0.0000 shares  €+10.77  (currently 0.0% → target 0.9%)
2026-08-20 02:02:10,628 INFO [engine.reconciliation.ledger_importer]   BUY  XOM          +0.0000 shares  €+9.27  (currently 0.0% → target 0.7%)
2026-08-20 02:02:10,628 INFO [engine.reconciliation.ledger_importer]   BUY  FCX          +0.0000 shares  €+9.27  (currently 0.0% → target 0.7%)
2026-08-20 02:02:10,629 INFO [engine.reconciliation.ledger_importer]   BUY  UT8.DE       +0.0000 shares  €+9.02  (currently 0.0% → target 0.7%)
2026-08-20 02:02:10,629 INFO [engine.reconciliation.ledger_importer]   BUY  BLQA.DE      +0.0000 shares  €+8.64  (currently 0.0% → target 0.7%)
2026-08-20 02:02:10,630 INFO [engine.reconciliation.ledger_importer]   BUY  SHOP.DE      +0.0000 shares  €+8.02  (currently 0.0% → target 0.6%)
2026-08-20 02:02:10,631 INFO [engine.reconciliation.ledger_importer]   BUY  NOW.DE       +0.0000 shares  €+8.02  (currently 0.0% → target 0.6%)
2026-08-20 02:02:10,632 INFO [engine.reconciliation.ledger_importer]   BUY  DE           +0.0000 shares  €+7.52  (currently 0.0% → target 0.6%)
2026-08-20 02:02:10,633 INFO [engine.reconciliation.ledger_importer]   BUY  DTE.DE       +0.0000 shares  €+6.26  (currently 0.0% → target 0.5%)
2026-08-20 02:02:10,634 INFO [engine.reconciliation.ledger_importer]   BUY  UNH          +0.0000 shares  €+6.26  (currently 0.0% → target 0.5%)
2026-08-20 02:02:10,634 INFO [scheduler] [ledger] 9 positions, cash=€404.01
2026-08-20 02:02:10,635 INFO [scheduler] [ledger] Trade advisor: 42 orders suggested
2026-08-20 02:02:10,636 INFO [scheduler] ✅ 0.  Ledger import (0.8s)
2026-08-20 02:02:10,648 INFO [scheduler] ▶ 1.  Data ingestion
2026-08-20 02:02:13,202 INFO [scheduler] [ingest] Fetching from 2026-08-14 (incremental, overlap=5d)
2026-08-20 02:02:13,202 INFO [engine.data.ingestion] Ingestion starting: 135 tickers, 2026-08-14 → 2026-08-20, polygon=no (yfinance only)
2026-08-20 02:02:20,320 ERROR [yfinance] HTTP Error 404: {"quoteSummary":{"result":null,"error":{"code":"Not Found","description":"Quote not found for symbol: SFC.DE"}}}
2026-08-20 02:02:20,731 ERROR [yfinance] $SFC.DE: possibly delisted; no timezone found
2026-08-20 02:02:20,735 ERROR [yfinance]
1 Failed download:
2026-08-20 02:02:20,735 ERROR [yfinance] ['SFC.DE']: possibly delisted; no timezone found
2026-08-20 02:02:20,739 INFO [engine.data.ingestion] Primary SFC.DE failed/empty — trying fallback: CRM
2026-08-20 02:02:21,070 INFO [engine.data.ingestion] Successfully fetched fallback data for SFC.DE via CRM
2026-08-20 02:02:23,905 ERROR [yfinance] HTTP Error 404: {"quoteSummary":{"result":null,"error":{"code":"Not Found","description":"Quote not found for symbol: 1IN.DE"}}}
2026-08-20 02:02:24,519 ERROR [yfinance] $1IN.DE: possibly delisted; no timezone found
2026-08-20 02:02:24,524 ERROR [yfinance]
1 Failed download:
2026-08-20 02:02:24,524 ERROR [yfinance] ['1IN.DE']: possibly delisted; no timezone found
2026-08-20 02:02:24,527 INFO [engine.data.ingestion] Primary 1IN.DE failed/empty — trying fallback: INTC
2026-08-20 02:02:26,092 INFO [engine.data.ingestion] Successfully fetched fallback data for 1IN.DE via INTC
2026-08-20 02:02:28,249 ERROR [yfinance] $MTU.DE: possibly delisted; no timezone found
2026-08-20 02:02:28,256 ERROR [yfinance]
1 Failed download:
2026-08-20 02:02:28,256 ERROR [yfinance] ['MTU.DE']: possibly delisted; no timezone found
2026-08-20 02:02:28,259 INFO [engine.data.ingestion] Primary MTU.DE failed/empty — trying fallback: MU
2026-08-20 02:02:28,848 INFO [engine.data.ingestion] Successfully fetched fallback data for MTU.DE via MU
2026-08-20 02:02:31,011 ERROR [yfinance] $TSM.DE: possibly delisted; no timezone found
2026-08-20 02:02:31,020 ERROR [yfinance]
1 Failed download:
2026-08-20 02:02:31,020 ERROR [yfinance] ['TSM.DE']: possibly delisted; no timezone found
2026-08-20 02:02:31,026 INFO [engine.data.ingestion] Primary TSM.DE failed/empty — trying fallback: TSM
2026-08-20 02:02:31,464 INFO [engine.data.ingestion] Successfully fetched fallback data for TSM.DE via TSM
2026-08-20 02:02:33,036 ERROR [yfinance] $NOW.DE: possibly delisted; no timezone found
2026-08-20 02:02:33,040 ERROR [yfinance]
1 Failed download:
2026-08-20 02:02:33,040 ERROR [yfinance] ['NOW.DE']: possibly delisted; no timezone found
2026-08-20 02:02:33,050 INFO [engine.data.ingestion] Primary NOW.DE failed/empty — trying fallback: NOW
2026-08-20 02:02:33,397 INFO [engine.data.ingestion] Successfully fetched fallback data for NOW.DE via NOW
2026-08-20 02:02:36,280 ERROR [yfinance] $PYPL.DE: possibly delisted; no timezone found
2026-08-20 02:02:36,290 ERROR [yfinance]
1 Failed download:
2026-08-20 02:02:36,290 ERROR [yfinance] ['PYPL.DE']: possibly delisted; no timezone found
2026-08-20 02:02:36,294 INFO [engine.data.ingestion] Primary PYPL.DE failed/empty — trying fallback: PYPL
2026-08-20 02:02:36,654 INFO [engine.data.ingestion] Successfully fetched fallback data for PYPL.DE via PYPL
2026-08-20 02:02:37,880 ERROR [yfinance] $SHOP.DE: possibly delisted; no timezone found
2026-08-20 02:02:37,890 ERROR [yfinance]
1 Failed download:
2026-08-20 02:02:37,890 ERROR [yfinance] ['SHOP.DE']: possibly delisted; no timezone found
2026-08-20 02:02:37,893 INFO [engine.data.ingestion] Primary SHOP.DE failed/empty — trying fallback: SHOP
2026-08-20 02:02:38,264 INFO [engine.data.ingestion] Successfully fetched fallback data for SHOP.DE via SHOP
2026-08-20 02:03:10,017 ERROR [yfinance] $AXP.DE: possibly delisted; no timezone found
2026-08-20 02:03:10,020 ERROR [yfinance]
1 Failed download:
2026-08-20 02:03:10,021 ERROR [yfinance] ['AXP.DE']: possibly delisted; no timezone found
2026-08-20 02:03:10,025 INFO [engine.data.ingestion] Primary AXP.DE failed/empty — trying fallback: AXP
2026-08-20 02:03:10,560 INFO [engine.data.ingestion] Successfully fetched fallback data for AXP.DE via AXP
2026-08-20 02:03:11,262 ERROR [yfinance] $BLQA.DE: possibly delisted; no timezone found
2026-08-20 02:03:11,262 ERROR [yfinance]
1 Failed download:
2026-08-20 02:03:11,264 ERROR [yfinance] ['BLQA.DE']: possibly delisted; no timezone found
2026-08-20 02:03:11,268 INFO [engine.data.ingestion] Primary BLQA.DE failed/empty — trying fallback: BLK
2026-08-20 02:03:11,663 INFO [engine.data.ingestion] Successfully fetched fallback data for BLQA.DE via BLK
2026-08-20 02:03:28,140 ERROR [yfinance] $ENB.DE: possibly delisted; no price data found  (1d 2026-08-14 -> 2026-08-20)
2026-08-20 02:03:28,148 ERROR [yfinance]
1 Failed download:
2026-08-20 02:03:28,148 ERROR [yfinance] ['ENB.DE']: possibly delisted; no price data found  (1d 2026-08-14 -> 2026-08-20)
2026-08-20 02:03:28,153 INFO [engine.data.ingestion] Primary ENB.DE failed/empty — trying fallback: ENB
2026-08-20 02:03:28,660 INFO [engine.data.ingestion] Successfully fetched fallback data for ENB.DE via ENB
2026-08-20 02:03:30,263 ERROR [yfinance] $EGI.DE: possibly delisted; no timezone found
2026-08-20 02:03:30,265 ERROR [yfinance]
1 Failed download:
2026-08-20 02:03:30,265 ERROR [yfinance] ['EGI.DE']: possibly delisted; no timezone found
2026-08-20 02:03:30,271 INFO [engine.data.ingestion] Primary EGI.DE failed/empty — trying fallback: ENGIY
2026-08-20 02:03:30,651 INFO [engine.data.ingestion] Successfully fetched fallback data for EGI.DE via ENGIY
2026-08-20 02:03:30,961 ERROR [yfinance] $BLM.DE: possibly delisted; no price data found  (1d 2026-08-14 -> 2026-08-20)
2026-08-20 02:03:30,967 ERROR [yfinance]
1 Failed download:
2026-08-20 02:03:30,967 ERROR [yfinance] ['BLM.DE']: possibly delisted; no price data found  (1d 2026-08-14 -> 2026-08-20)
2026-08-20 02:03:30,974 INFO [engine.data.ingestion] Primary BLM.DE failed/empty — trying fallback: BE
2026-08-20 02:03:31,344 INFO [engine.data.ingestion] Successfully fetched fallback data for BLM.DE via BE
2026-08-20 02:03:37,165 ERROR [yfinance] $C1E.DE: possibly delisted; no timezone found
2026-08-20 02:03:37,165 ERROR [yfinance]
1 Failed download:
2026-08-20 02:03:37,166 ERROR [yfinance] ['C1E.DE']: possibly delisted; no timezone found
2026-08-20 02:03:37,170 INFO [engine.data.ingestion] Primary C1E.DE failed/empty — trying fallback: LEU
2026-08-20 02:03:37,524 INFO [engine.data.ingestion] Successfully fetched fallback data for C1E.DE via LEU
2026-08-20 02:03:39,706 ERROR [yfinance] $VO51.DE: possibly delisted; no timezone found
2026-08-20 02:03:39,712 ERROR [yfinance]
1 Failed download:
2026-08-20 02:03:39,712 ERROR [yfinance] ['VO51.DE']: possibly delisted; no timezone found
2026-08-20 02:03:39,715 INFO [engine.data.ingestion] Primary VO51.DE failed/empty — trying fallback: UUUU
2026-08-20 02:03:40,216 INFO [engine.data.ingestion] Successfully fetched fallback data for VO51.DE via UUUU
2026-08-20 02:03:50,639 INFO [engine.data.validation] Validation complete: 539 clean rows, 0 rejected
2026-08-20 02:03:51,013 INFO [engine.data.ingestion] FX fetched from yfinance: USDEUR
2026-08-20 02:03:51,380 INFO [engine.data.ingestion] FX fetched from yfinance: GBPEUR
2026-08-20 02:03:51,383 INFO [engine.data.ingestion] FX rates persisted: 8 rows across 2 pairs
2026-08-20 02:03:51,461 WARNING [engine.data.ingestion] persist_prices: dropped 73 rows with NaN close/adj_close
2026-08-20 02:03:51,568 INFO [engine.data.ingestion] Persisted 466 price rows to DB.
2026-08-20 02:03:51,569 INFO [engine.data.ingestion] Ingestion complete: 539 rows persisted.
2026-08-20 02:03:51,756 INFO [engine.data.ingestion] ✅ Staleness check: all tickers fresh.
2026-08-20 02:03:51,756 INFO [scheduler] ✅ 1.  Data ingestion (101.1s)
2026-08-20 02:03:51,762 INFO [scheduler] ▶ 2.  Macro regime refresh
2026-08-20 02:03:58,902 INFO [scheduler] [regime] regime_state.json updated
2026-08-20 02:03:58,905 INFO [scheduler] [mirror] 0 copied, 4 already fresh, 0 sources not found
2026-08-20 02:03:58,913 INFO [scheduler] ✅ 2.  Macro regime refresh (7.2s)
2026-08-20 02:03:58,919 INFO [scheduler] ▶ 3.  Feature pipeline
2026-08-20 02:03:58,945 INFO [engine.features.feature_store] Feature pipeline starting: 2026-08-20, 135 tickers
2026-08-20 02:04:00,150 INFO [engine.features.feature_store] Momentum features: 4 cols, 135 tickers
2026-08-20 02:04:00,169 INFO [engine.features.feature_store] Sector-relative momentum features: 4 cols
2026-08-20 02:04:00,188 INFO [engine.features.feature_store] Volatility features: 3 cols
2026-08-20 02:04:00,377 INFO [engine.features.feature_store] Technical features: 1 cols
2026-08-20 02:04:00,631 INFO [engine.features.feature_store] Feature store: persisted 1613 values for 2026-08-20
2026-08-20 02:04:01,563 INFO [ml_quant_finance_research.general_research.src.regime] Correlation compression computed: 495 observations (window=30d)
2026-08-20 02:04:01,573 INFO [ml_quant_finance_research.general_research.src.regime] Composite regime: 495 observations | Current: low_stress (stress=0.144)
2026-08-20 02:04:01,575 INFO [engine.features.feature_store] Statistical regime: {'stress_score': 0.1439, 'vol_component': 0.0, 'corr_component': 0.35963073832812076, 'regime_low': 1.0, 'regime_medium': 0.0, 'regime_high': 0.0}
2026-08-20 02:04:01,576 INFO [engine.features.feature_store] [feature_store] Macro regime loaded: Risk-On / Tightening / Slowdown | EW=False | streak=1d
2026-08-20 02:04:01,576 INFO [engine.features.feature_store] Macro regime: risk_on=1.0, growth_expansion=0.0, ew=0.0
2026-08-20 02:04:01,606 INFO [engine.features.feature_store] Feature store: persisted 22 values for 2026-08-20
2026-08-20 02:04:01,607 INFO [engine.features.feature_store] Feature pipeline complete: 2026-08-20, 135 tickers, 12 per-ticker features, 22 portfolio features
2026-08-20 02:04:01,609 INFO [scheduler] ✅ 3.  Feature pipeline (2.7s)
2026-08-20 02:04:01,623 INFO [scheduler] ▶ 3b. Earnings calendar
2026-08-20 02:04:02,313 INFO [engine.data.earnings_calendar] [earnings_calendar] 7 earnings dates persisted (of 524 fetched)
2026-08-20 02:04:02,314 INFO [scheduler] [earnings_calendar] 7 rows persisted for 2026-08-20
2026-08-20 02:04:02,315 INFO [scheduler] ✅ 3b. Earnings calendar (0.7s)
2026-08-20 02:04:02,333 INFO [scheduler] ▶ 4.  Alpha: momentum
2026-08-20 02:04:04,440 INFO [engine.alpha.momentum] [momentum] 134 signals, IC=0.0284, date=2026-08-20
2026-08-20 02:04:04,490 INFO [engine.alpha.base] [momentum] Persisted 134 signals for 2026-08-20
2026-08-20 02:04:04,491 INFO [scheduler] [momentum] 134 signals persisted
2026-08-20 02:04:04,491 INFO [scheduler] ✅ 4.  Alpha: momentum (2.2s)
2026-08-20 02:04:04,498 INFO [scheduler] ▶ 4b. Alpha: sector momentum
2026-08-20 02:04:04,513 INFO [engine.alpha.sector_momentum] [sector_momentum] 134 signals, IC=-0.1158, date=2026-08-20
2026-08-20 02:04:04,582 INFO [engine.alpha.base] [sector_momentum] Persisted 134 signals for 2026-08-20
2026-08-20 02:04:04,583 INFO [scheduler] [sector_momentum] 134 signals persisted
2026-08-20 02:04:04,584 INFO [scheduler] ✅ 4b. Alpha: sector momentum (0.1s)
2026-08-20 02:04:04,596 INFO [scheduler] ▶ 5.  Alpha: mean reversion
2026-08-20 02:04:04,619 INFO [engine.alpha.mean_reversion] [mean_reversion] 135 signals, IC=-0.0775, date=2026-08-20
2026-08-20 02:04:04,706 INFO [engine.alpha.base] [mean_reversion] Persisted 135 signals for 2026-08-20
2026-08-20 02:04:04,707 INFO [scheduler] [mean_reversion] 135 signals persisted
2026-08-20 02:04:04,708 INFO [scheduler] ✅ 5.  Alpha: mean reversion (0.1s)
2026-08-20 02:04:04,723 INFO [scheduler] ▶ 6.  Alpha: vol timing
2026-08-20 02:04:04,767 INFO [engine.alpha.vol_timing] [vol_timing] 135 signals, IC=-0.0200, date=2026-08-20
2026-08-20 02:04:04,869 INFO [engine.alpha.base] [vol_timing] Persisted 135 signals for 2026-08-20
2026-08-20 02:04:04,870 INFO [scheduler] [vol_timing] 135 signals persisted
2026-08-20 02:04:04,871 INFO [scheduler] ✅ 6.  Alpha: vol timing (0.1s)
2026-08-20 02:04:04,885 INFO [scheduler] ▶ 7.  Alpha: PEAD signals
2026-08-20 02:04:04,936 INFO [engine.alpha.pead_alpha] [pead] No active High/Medium quality setups for 2026-08-20
2026-08-20 02:04:04,937 INFO [scheduler] [pead] No signals generated
2026-08-20 02:04:04,938 INFO [scheduler] ✅ 7.  Alpha: PEAD signals (0.1s)
2026-08-20 02:04:04,950 INFO [scheduler] ▶ 8.  Alpha: ML signals
2026-08-20 02:04:04,962 INFO [engine.alpha.ml_alpha] [ml] 76 signals generated (of 78 in state), date=2026-08-20
2026-08-20 02:04:05,033 INFO [engine.alpha.base] [ml_model] Persisted 76 signals for 2026-08-20
2026-08-20 02:04:05,034 INFO [scheduler] [ml_model] 76 signals persisted
2026-08-20 02:04:05,034 INFO [scheduler] ✅ 8.  Alpha: ML signals (0.1s)
2026-08-20 02:04:05,137 INFO [scheduler] ▶ 9.  ETF divergence scan
2026-08-20 02:04:05,409 INFO [engine.screens.etf_divergence] ETF divergence scan: 2 events detected for 2026-08-20
2026-08-20 02:04:05,427 INFO [engine.screens.etf_divergence] Saved 2 new divergence events to DB
2026-08-20 02:04:05,427 INFO [scheduler] ETF divergence scan: 2 events found
2026-08-20 02:04:05,428 INFO [scheduler] ✅ 9.  ETF divergence scan (0.3s)
2026-08-20 02:04:05,440 INFO [scheduler] ▶ 10. Outcome fill
2026-08-20 02:04:05,466 INFO [scheduler] ✅ 10. Outcome fill (0.0s)
2026-08-20 02:04:05,477 INFO [scheduler] ▶ 11. Portfolio construction
2026-08-20 02:04:07,890 WARNING [scheduler] [portfolio] Insufficient data for Ledoit-Wolf — using raw covariance
2026-08-20 02:04:07,896 INFO [scheduler] [portfolio] Regime: low_stress | RiskOn_Tightening_Slowdown
2026-08-20 02:04:12,903 INFO [ml_quant_finance_research.general_research.src.factor_model] Regime view: low_stress → benchmark Q=0.0257, omega=0.001
2026-08-20 02:04:12,904 INFO [engine.portfolio.black_litterman] BL: 614 alpha views + 1 regime view
2026-08-20 02:04:13,399 INFO [ml_quant_finance_research.general_research.src.factor_model] BL posterior returns computed for 135 assets with 615 views.
2026-08-20 02:04:16,749 INFO [engine.portfolio.optimizer] Model outputs persisted: 2026-08-20, 135 tickers
2026-08-20 02:04:16,751 CRITICAL [engine.risk.circuit_breaker] 🚨 CIRCUIT BREAKER: PPFD.SG down -14.9% from entry (entry=€61.50, current=€52.37) — FORCED SELL
2026-08-20 02:04:16,758 CRITICAL [scheduler] [circuit_breaker] Forced weights to 0 for: ['PPFD.SG']
2026-08-20 02:04:16,758 CRITICAL [engine.alerting.digest] 🚨 ALERT [CRITICAL]: 🚨 CIRCUIT BREAKER activated for: PPFD.SG
2026-08-20 02:04:16,759 INFO [engine.risk.pre_trade] Pre-trade checks: ALL PASSED
2026-08-20 02:04:16,776 INFO [engine.execution.order_manager] [Kelly Sizing] MTU.DE: €34 -> €34 (kelly=1.00, regime=1.00)
2026-08-20 02:04:16,777 INFO [engine.execution.order_manager] [Kelly Sizing] ORC.DE: €26 -> €26 (kelly=1.00, regime=1.00)
2026-08-20 02:04:16,778 INFO [engine.execution.order_manager] [Kelly Sizing] BAS.DE: €59 -> €59 (kelly=1.00, regime=1.00)
2026-08-20 02:04:16,780 INFO [engine.execution.order_manager] [Kelly Sizing] ADS.DE: €30 -> €30 (kelly=1.00, regime=1.00)
2026-08-20 02:04:16,781 INFO [engine.execution.order_manager] [Kelly Sizing] MTX.DE: €33 -> €33 (kelly=1.00, regime=1.00)
2026-08-20 02:04:16,783 INFO [engine.execution.order_manager] [Kelly Sizing] MIN: €31 -> €31 (kelly=1.00, regime=1.00)
2026-08-20 02:04:16,784 INFO [engine.execution.order_manager] [Kelly Sizing] CAT: €60 -> €60 (kelly=1.00, regime=1.00)
2026-08-20 02:04:16,784 INFO [engine.execution.order_manager] Order queue: 11 orders generated (tolerance bands, ADV gating, Kelly sizing, earnings throttle applied)
2026-08-20 02:04:16,785 INFO [scheduler] [portfolio] 11 orders (portfolio=€1,312)
2026-08-20 02:04:16,785 INFO [scheduler]   SELL AMZ.DE       €  123.77
2026-08-20 02:04:16,785 INFO [scheduler]   SELL PPFD.SG      €  108.58
2026-08-20 02:04:16,786 INFO [scheduler]   BUY  CAT          €   59.56
2026-08-20 02:04:16,786 INFO [scheduler]   BUY  BAS.DE       €   59.29
2026-08-20 02:04:16,786 INFO [scheduler]   SELL NEE          €   58.71
2026-08-20 02:04:16,786 INFO [scheduler]   SELL VO51.DE      €   56.31
2026-08-20 02:04:16,786 INFO [scheduler]   BUY  MTU.DE       €   34.24
2026-08-20 02:04:16,787 INFO [scheduler]   BUY  MTX.DE       €   32.53
2026-08-20 02:04:16,787 INFO [scheduler]   BUY  MIN          €   31.48
2026-08-20 02:04:16,787 INFO [scheduler]   BUY  ADS.DE       €   29.52
2026-08-20 02:04:16,787 INFO [scheduler]   BUY  ORC.DE       €   25.71
2026-08-20 02:04:18,948 INFO [ml_quant_finance_research.general_research.src.regime] Correlation compression computed: 474 observations (window=30d)
2026-08-20 02:04:18,955 INFO [ml_quant_finance_research.general_research.src.regime] Composite regime: 474 observations | Current: low_stress (stress=0.144)
2026-08-20 02:04:18,975 INFO [engine.risk.post_trade] Post-trade risk: VaR=-0.36%, CVaR=-0.90%, Regime=low_stress
2026-08-20 02:04:18,977 INFO [scheduler] ✅ 11. Portfolio construction (13.5s)
2026-08-20 02:04:18,990 INFO [scheduler] ▶ 12. Price targets
2026-08-20 02:04:19,049 INFO [engine.analysis.price_targets] [price_targets] Starting for 2026-08-20, 135 tickers
2026-08-20 02:04:21,937 INFO [engine.analysis.price_targets] [price_targets] Computed 135 targets, 0 skipped (no data), date=2026-08-20
2026-08-20 02:04:21,992 INFO [engine.analysis.price_targets] [price_targets] Persisted 135 price targets for 2026-08-20
2026-08-20 02:04:22,003 INFO [engine.analysis.price_targets] [price_targets] JSON written to C:\Users\ahmty\Desktop\hedge-fund\shared\state\price_targets.json
2026-08-20 02:04:22,003 INFO [scheduler] [price_targets] 135 targets computed
2026-08-20 02:04:22,004 INFO [scheduler] ✅ 12. Price targets (3.0s)
2026-08-20 02:04:22,014 INFO [scheduler] ▶ 13. Performance logging
2026-08-20 02:04:22,029 INFO [scheduler] [performance] Logged: €1,311.80 | Return: +0.11%
2026-08-20 02:04:22,029 INFO [scheduler] ✅ 13. Performance logging (0.0s)
2026-08-20 02:04:22,038 INFO [scheduler] ▶ 14. Signal queue push
2026-08-20 02:04:22,194 INFO [scheduler] [signal_push] Pushed 9 long / 3 short / 0 PEAD signals — 31 already pending (skipped)
2026-08-20 02:04:22,195 INFO [scheduler] ✅ 14. Signal queue push (0.2s)
2026-08-20 02:04:22,203 INFO [scheduler] ============================================================
  Pipeline complete: 2026-08-20
============================================================
2026-08-20 02:04:22,207 INFO [engine.alerting.digest]
📊 *Pipeline Summary — 2026-08-20*
──────────────────────────────────────────
  ✅ 0.  Ledger import                (0.8s)
  ✅ 1.  Data ingestion               (101.1s)
  ✅ 2.  Macro regime refresh         (7.2s)
  ✅ 3.  Feature pipeline             (2.7s)
  ✅ 3b. Earnings calendar            (0.7s)
  ✅ 4.  Alpha: momentum              (2.2s)
  ✅ 4b. Alpha: sector momentum       (0.1s)
  ✅ 5.  Alpha: mean reversion        (0.1s)
  ✅ 6.  Alpha: vol timing            (0.1s)
  ✅ 7.  Alpha: PEAD signals          (0.1s)
  ✅ 8.  Alpha: ML signals            (0.1s)
  ✅ 9.  ETF divergence scan          (0.3s)
  ✅ 10. Outcome fill                 (0.0s)
  ✅ 11. Portfolio construction       (13.5s)
  ✅ 12. Price targets                (3.0s)
  ✅ 13. Performance logging          (0.0s)
  ✅ 14. Signal queue push            (0.2s)
──────────────────────────────────────────
  Orders blocked:       ✅ No
  Pre-trade violations: 0
  Portfolio VaR (95%):  -0.36%
  Regime:               low_stress
  Portfolio value:      €1,312
──────────────────────────────────────────
  ✅ Pipeline completed cleanly
[6/6] Launching Flask Control Tower...
Dashboard will be available locally at http://localhost:5000
Dashboard will be available on LAN at http://192.168.1.11:5000
2026-08-20 02:04:33,798 [INFO] Adding job tentatively -- it will be properly scheduled when the scheduler starts
2026-08-20 02:04:33,799 [INFO] Added job "_run_scheduled_rebalance" to job store "default"
2026-08-20 02:04:33,800 [INFO] Scheduler started
2026-08-20 02:04:33,800 [INFO] ⏱️  Scheduler active: Weekly refresh set for Monday 17:00 CET
2026-08-20 02:04:33,801 [INFO] Control Tower (Flask) starting — http://localhost:5000 and http://0.0.0.0:5000 (LAN) (debug=False)
 * Serving Flask app 'flask_app'
 * Debug mode: off
2026-08-20 02:04:33,839 [INFO] WARNING: This is a development server. Do not use it in a production deployment. Use a production WSGI server instead.
 * Running on all addresses (0.0.0.0)
 * Running on http://127.0.0.1:5000
 * Running on http://192.168.1.11:5000
2026-08-20 02:04:33,839 [INFO] Press CTRL+C to quit
2026-08-20 02:04:34,604 [INFO] 127.0.0.1 - - [20/Aug/2026 02:04:34] "GET / HTTP/1.1" 200 -
2026-08-20 02:04:34,807 [INFO] 127.0.0.1 - - [20/Aug/2026 02:04:34] "GET /api/freshness HTTP/1.1" 200 -
2026-08-20 02:04:34,826 [INFO] 127.0.0.1 - - [20/Aug/2026 02:04:34] "GET /api/watchlist/count HTTP/1.1" 200 -
2026-08-20 02:04:35,116 [INFO] 127.0.0.1 - - [20/Aug/2026 02:04:35] "GET /api/signal_queue/count HTTP/1.1" 200 -
2026-08-20 02:04:35,357 [INFO] 127.0.0.1 - - [20/Aug/2026 02:04:35] "GET /api/cash HTTP/1.1" 200 -
2026-08-20 02:04:35,366 [INFO] 127.0.0.1 - - [20/Aug/2026 02:04:35] "GET /api/ml HTTP/1.1" 200 -
2026-08-20 02:04:35,398 [INFO] 127.0.0.1 - - [20/Aug/2026 02:04:35] "GET /api/rebalance HTTP/1.1" 200 -
2026-08-20 02:04:35,404 [INFO] 127.0.0.1 - - [20/Aug/2026 02:04:35] "GET /api/regime HTTP/1.1" 200 -
2026-08-20 02:04:35,427 [INFO] 127.0.0.1 - - [20/Aug/2026 02:04:35] "GET /api/positions HTTP/1.1" 200 -
2026-08-20 02:04:35,439 [INFO] 127.0.0.1 - - [20/Aug/2026 02:04:35] "GET /api/trades HTTP/1.1" 200 -
2026-08-20 02:04:35,678 [INFO] 127.0.0.1 - - [20/Aug/2026 02:04:35] "GET /api/price_targets HTTP/1.1" 200 -
2026-08-20 02:04:35,697 [INFO] 127.0.0.1 - - [20/Aug/2026 02:04:35] "GET /api/portfolio_mc HTTP/1.1" 200 -
2026-08-20 02:04:35,736 [INFO] 127.0.0.1 - - [20/Aug/2026 02:04:35] "GET /api/circuit_breakers HTTP/1.1" 200 -
2026-08-20 02:04:35,746 [INFO] 127.0.0.1 - - [20/Aug/2026 02:04:35] "GET /favicon.ico HTTP/1.1" 404 -
2026-08-20 02:04:35,758 [INFO] 127.0.0.1 - - [20/Aug/2026 02:04:35] "GET /api/institutional_mc HTTP/1.1" 200 -
2026-08-20 02:04:47,194 [INFO] 127.0.0.1 - - [20/Aug/2026 02:04:47] "GET /health HTTP/1.1" 200 -
2026-08-20 02:04:47,412 [INFO] 127.0.0.1 - - [20/Aug/2026 02:04:47] "GET /api/freshness HTTP/1.1" 200 -
2026-08-20 02:04:47,426 [INFO] 127.0.0.1 - - [20/Aug/2026 02:04:47] "GET /api/watchlist/count HTTP/1.1" 200 -
2026-08-20 02:04:47,558 [INFO] 127.0.0.1 - - [20/Aug/2026 02:04:47] "GET /api/pipeline HTTP/1.1" 200 -
2026-08-20 02:04:47,683 [INFO] 127.0.0.1 - - [20/Aug/2026 02:04:47] "GET /api/risk_events HTTP/1.1" 200 -
2026-08-20 02:04:47,685 [INFO] 127.0.0.1 - - [20/Aug/2026 02:04:47] "GET /api/signal_queue/count HTTP/1.1" 200 -
2026-08-20 02:04:47,724 [INFO] 127.0.0.1 - - [20/Aug/2026 02:04:47] "GET /api/pipeline_logs?limit=100 HTTP/1.1" 200 -
2026-08-20 02:04:47,745 [INFO] 127.0.0.1 - - [20/Aug/2026 02:04:47] "GET /api/freshness HTTP/1.1" 200 -
2026-08-20 02:04:48,910 [INFO] 127.0.0.1 - - [20/Aug/2026 02:04:48] "GET /api/kill_switch_status HTTP/1.1" 200 -
