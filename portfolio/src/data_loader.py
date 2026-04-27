# src/data_loader.py

import os
import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime, timedelta
import logging

# Set up simple logging to track the engine's background work
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

def load_ledger(filepath='data/ledger.csv'):
    """
    Reads the manual ledger to calculate current holdings and uninvested cash.
    Assumes columns: Date, Action, Ticker, Quantity, Price, Total, Notes
    Actions allowed: 'Buy', 'Sell', 'Deposit', 'Dividend', 'Fee'
    """
    holdings = {}
    cash = 0.0

    if not os.path.exists(filepath):
        logging.warning(f"No ledger found at {filepath}. Returning empty portfolio.")
        return holdings, cash

    try:
        df = pd.read_csv(filepath, comment='#')
        
        for index, row in df.iterrows():
            action = str(row['Action']).strip().title()
            ticker = str(row['Ticker']).strip().upper()
            qty = float(row['Quantity']) if pd.notna(row['Quantity']) else 0.0
            total = float(row['Total']) if pd.notna(row['Total']) else 0.0

            if action == 'Deposit':
                cash += total
            elif action == 'Dividend':
                # Dividends go straight to the cash pile
                cash += total
            elif action == 'Fee':
                cash -= total
            elif action == 'Buy':
                cash -= total
                holdings[ticker] = holdings.get(ticker, 0.0) + qty
            elif action == 'Sell':
                cash += total
                holdings[ticker] = holdings.get(ticker, 0.0) - qty
                
                # Clean up if we completely exited a position
                if holdings[ticker] <= 0.0001:  # Account for floating point math
                    del holdings[ticker]

        logging.info(f"Ledger loaded. Cash: €{cash:.2f}, Holdings: {len(holdings)} assets.")
        return holdings, cash

    except Exception as e:
        logging.error(f"Error parsing ledger: {e}")
        raise

def validate_data(prices_df, max_daily_move=0.30):
    """
    The Sanity Gate: Checks for data gaps and unrealistic daily moves.
    Returns True if data is safe, raises ValueError if anomaly detected.
    """
    if prices_df.isnull().values.any():
        logging.warning("Missing values detected in price data. Forward-filling gaps.")
        prices_df.ffill(inplace=True)  # <-- This fixes the Pandas deprecation warning
        # Drop any remaining NaNs at the very beginning
        prices_df.dropna(inplace=True)

    # Calculate daily percentage returns (not log returns yet, just for the sanity check)
    pct_returns = prices_df.pct_change().dropna()
    
    # Check for moves > threshold (could indicate an unadjusted stock split)
    max_moves = pct_returns.abs().max()
    anomalies = max_moves[max_moves > max_daily_move]
    
    if not anomalies.empty:
        error_msg = f"⚠️ DATA ANOMALY DETECTED: Moves > {max_daily_move*100}% found in: {list(anomalies.index)}."
        logging.error(error_msg)
        raise ValueError(error_msg + " Please check yfinance data for unadjusted splits.")
        
    return True


def fetch_historical(tickers, lookback_days=504, cache_path='data/historical_prices.csv'):
    """
    Fetches adjusted closing prices from yfinance. Uses local cache if fresh.
    """
    end_date = datetime.today()
    start_date = end_date - timedelta(days=lookback_days + 100) # Buffer for weekends/holidays

    # Create data directory if it doesn't exist
    os.makedirs(os.path.dirname(cache_path), exist_ok=True)

    # Note: For production, you could add logic here to check if the cache is 
    # from today and skip the download. For now, we download fresh to be safe.
    logging.info(f"Fetching data for {len(tickers)} assets from Yahoo Finance...")
    
    try:
        # Download data, group by ticker, auto-adjust for splits/dividends
        data = yf.download(tickers, start=start_date.strftime('%Y-%m-%d'), 
                           end=end_date.strftime('%Y-%m-%d'), 
                           auto_adjust=True, progress=False)
        
        # We only care about the Close price (which is adjusted because of auto_adjust=True)
        if len(tickers) == 1:
            prices = pd.DataFrame({tickers[0]: data['Close']})
        else:
            prices = data['Close']
            
        # Ensure we only have the columns we asked for
        prices = prices[tickers]
        
        # Keep exactly the number of trading days requested
        prices = prices.tail(lookback_days)
        
        # Run through the Sanity Gate
        validate_data(prices)
        
        # Cache it locally
        prices.to_csv(cache_path)
        logging.info(f"Data validated and cached successfully to {cache_path}")
        
        return prices
        
    except Exception as e:
        logging.error(f"Failed to fetch market data: {e}")
        
        # Fallback to cache if download fails
        if os.path.exists(cache_path):
            logging.info("Falling back to local cache...")
            prices = pd.read_csv(cache_path, index_col=0, parse_dates=True)
            return prices.tail(lookback_days)
        else:
            raise

def calculate_log_returns(prices_df):
    """
    Converts raw prices into time-additive log returns.
    """
    # log(P_t / P_{t-1})
    log_returns = np.log(prices_df / prices_df.shift(1)).dropna()
    return log_returns