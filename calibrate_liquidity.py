import os
import sys
import pandas as pd

# Add project root to sys.path
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from engine.db.db import get_session
from sqlalchemy import text
from engine.data.liquidity_classifier import classify_ticker
from portfolio.src.config import ASSET_UNIVERSE

def run_calibration():
    session = get_session()
    
    # Use the max date in the database as "today" for the calibration 
    # (so we don't penalize for staleness just because the DB is a week old)
    max_date_row = session.execute(text("SELECT MAX(date) FROM prices")).fetchone()
    as_of_date = max_date_row[0][:10] if max_date_row and max_date_row[0] else None
    print(f"Using as_of_date: {as_of_date}")
    
    results = []
    
    print("Classifying {} tickers...".format(len(ASSET_UNIVERSE)))
    for t in ASSET_UNIVERSE:
        rec = classify_ticker(t, session, as_of_date=as_of_date)
        results.append(rec)
    session.close()
    
    df = pd.DataFrame(results)
    print("\n--- TIER DISTRIBUTION ---")
    print(df['tier'].value_counts())
    
    print("\n--- UNRELIABLE TICKERS ---")
    unreliable = df[df['tier'] == 'unreliable'][['ticker', 'trading_days_90d', 'history_days', 'days_since_update']]
    print(unreliable)
    
    print("\n--- THIN TICKERS ---")
    thin = df[df['tier'] == 'thin'][['ticker', 'trading_days_90d', 'history_days', 'days_since_update', 'avg_range_pct']]
    print(thin.head(15))
    
if __name__ == "__main__":
    run_calibration()
