
from portfolio.src.config import ASSET_UNIVERSE

loaded_tickers = ['1IN.DE', '3V64.DE', '639.DE', 'ABBV', 'ABEA.DE', 'ADB.DE', 'ADS.DE', 'AIR.DE', 'ALB', 'ALV.DE', 'AMD.DE', 'AMGN', 'AMZ.DE', 'AP2.DE', 'APC.DE', 'ARGX.BR', 'ASML.AS', 'ATAI', 'AXP.DE', 'AXSM', 'AZN.L', 'BA', 'BAS.DE', 'BAYN.DE', 'BE', 'BEI.DE', 'BEP', 'BLQA.DE', 'BMW.DE', 'BNTX', 'BP.L', 'BRYN.DE', 'C1E.DE', 'CAT', 'CCJ', 'CEG', 'CMC.DE', 'COK.DE', 'CON.DE', 'COST', 'CVX', 'DBK.DE', 'DBXD.DE', 'DE', 'DIS', 'DTE.DE', 'DWD.DE', 'ENB', 'ENR.DE', 'ERO', 'EUNL.DE', 'EXS1.DE', 'EXXT.DE', 'FB2A.DE', 'FCX', 'FIG', 'FRE.DE', 'FSLR', 'GE', 'GEV', 'GILD', 'GOS.DE', 'HD', 'HEN3.DE', 'HON', 'IFX.DE', 'IS3N.DE', 'IUSN.DE', 'JNJ', 'KLAC', 'KO', 'LLY', 'LMT', 'LOW', 'MBG.DE', 'MCD', 'MIN', 'MRK', 'MSF.DE', 'MTU.DE', 'MTX.DE', 'MUV2.DE', 'NCB.DE', 'NDX1.DE', 'NEE', 'NFC.DE', 'NKE', 'NOV.DE', 'NOW.DE', 'NVD.DE', 'NVS', 'OKLO', 'ORC.DE', 'PFE', 'PYPL.DE', 'QCI.DE', 'RHM.DE', 'RIO', 'RTX', 'RWE.DE', 'S92.DE', 'SAP.DE', 'SBUX', 'SFC.DE', 'SHELL.AS', 'SHL.DE', 'SHOP.DE', 'SIE.DE', 'SMR', 'SNW.DE', 'SPPW.DE', 'TII.DE', 'TL0.DE', 'TMO', 'TSM.DE', 'TTE.PA', 'UCB.BR', 'UNH', 'UPS', 'UT8.DE', 'VNA.DE', 'VOW3.DE', 'VRTX', 'VUSA.DE', 'VWCE.DE', 'WMT', 'XDWD.DE', 'XOM', 'ZAL.DE', 'ZPRV.DE']

missing = [t for t in ASSET_UNIVERSE if t not in loaded_tickers]
print(f"Total Universe: {len(ASSET_UNIVERSE)}")
print(f"Loaded Tickers: {len(loaded_tickers)}")
print(f"Missing Tickers ({len(missing)}):")
for t in missing:
    print(f" - {t}")
