import sqlite3
import yfinance as yf
import pandas as pd
from datetime import datetime, date, timedelta
import time
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")

def populate_earnings_and_pead():
    conn = sqlite3.connect('engine_data.db')
    
    # 1. Get the list of tickers in our universe
    prices_tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='prices'").fetchall()
    if not prices_tables:
        logging.error("Prices table not found. Cannot determine universe.")
        return
        
    df_tickers = pd.read_sql("SELECT DISTINCT ticker FROM prices", conn)
    universe = df_tickers['ticker'].tolist()
    logging.info(f"Loaded {len(universe)} tickers from the database.")
    
    # Track stats
    total_calendar = 0
    total_pead = 0
    
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    for ticker in universe:
        logging.info(f"Fetching earnings data for {ticker} via yfinance...")
        try:
            t = yf.Ticker(ticker)
            earnings = t.earnings_dates
            
            if earnings is None or earnings.empty:
                logging.warning(f"  [{ticker}] No earnings data available.")
                continue
                
            # yfinance returns index as dates (with timezone)
            earnings.index = pd.to_datetime(earnings.index).tz_localize(None)
            
            for edate, row in earnings.iterrows():
                eps_est = row.get('EPS Estimate', None)
                eps_rep = row.get('Reported EPS', None)
                eps_surprise = row.get('Surprise(%)', None)
                
                edate_str = edate.strftime('%Y-%m-%d')
                
                # If the earnings date is in the future, it goes to earnings_calendar
                if edate.date() >= date.today():
                    conn.execute("""
                        INSERT INTO earnings_calendar (ticker, report_date, eps_estimate, fetched_at)
                        VALUES (?, ?, ?, ?)
                    """, (ticker, edate_str, eps_est if not pd.isna(eps_est) else None, now_str))
                    total_calendar += 1
                
                # If it's in the past and has an actual reported EPS, it's a historical PEAD setup
                elif edate.date() < date.today() and not pd.isna(eps_rep):
                    # In a real setup we'd calculate returns around earnings, but to populate the DB
                    # we insert the basic surprise data so the ML pipeline features don't crash on NaN.
                    conn.execute("""
                        INSERT INTO pead_setups (ticker, earnings_date, surprise_pct, created_at)
                        VALUES (?, ?, ?, ?)
                    """, (ticker, edate_str, eps_surprise if not pd.isna(eps_surprise) else None, now_str))
                    total_pead += 1
                    
            conn.commit()
            
        except Exception as e:
            logging.error(f"  [{ticker}] Failed: {e}")
            
        # Rate limiting to avoid yfinance bans
        time.sleep(1)
        
    logging.info(f"Done! Inserted {total_calendar} future earnings and {total_pead} historical PEAD setups.")

if __name__ == "__main__":
    populate_earnings_and_pead()
