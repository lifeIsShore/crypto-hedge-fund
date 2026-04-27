#!/usr/bin/env python3
"""
Script to add Amazon and Tesla stock prices in EUR to the historical prices CSV
"""

import pandas as pd
import yfinance as yf
from datetime import datetime
import sys

def add_amzn_tsla_to_csv():
    """Fetch AMZN and TSLA data and add to historical_prices.csv"""
    
    # Read existing CSV
    df = pd.read_csv('data/historical_prices.csv')
    
    # Get date range from existing data
    df['Date'] = pd.to_datetime(df['Date'])
    start_date = df['Date'].min()
    end_date = df['Date'].max()
    
    print(f"Fetching AMZN and TSLA data from {start_date.date()} to {end_date.date()}...")
    
    # Fetch AMZN data (USD)
    print("  Fetching AMZN...")
    amzn_data = yf.download('AMZN', start=start_date, end=end_date, progress=False)
    amzn_usd = amzn_data[('Close', 'AMZN')].squeeze() if isinstance(amzn_data.columns, pd.MultiIndex) else amzn_data['Close'].squeeze()
    
    # Fetch TSLA data (USD)
    print("  Fetching TSLA...")
    tsla_data = yf.download('TSLA', start=start_date, end=end_date, progress=False)
    tsla_usd = tsla_data[('Close', 'TSLA')].squeeze() if isinstance(tsla_data.columns, pd.MultiIndex) else tsla_data['Close'].squeeze()
    
    # Fetch EUR/USD exchange rate data
    print("  Fetching EUR/USD exchange rate...")
    eurusd_data = yf.download('EURUSD=X', start=start_date, end=end_date, progress=False)
    eurusd = eurusd_data[('Close', 'EURUSD=X')].squeeze() if isinstance(eurusd_data.columns, pd.MultiIndex) else eurusd_data['Close'].squeeze()
    
    print("Converting USD prices to EUR...")
    
    # Convert to EUR by dividing by exchange rate
    amzn_eur = (amzn_usd / eurusd).reset_index(drop=True)
    tsla_eur = (tsla_usd / eurusd).reset_index(drop=True)
    
    # Reset df index to align properly
    df = df.reset_index(drop=True)
    
    # Add AMZN and TSLA columns
    df['AMZN'] = amzn_eur
    df['TSLA'] = tsla_eur
    
    # Forward fill any NaN values
    df['AMZN'] = df['AMZN'].fillna(method='ffill')
    df['TSLA'] = df['TSLA'].fillna(method='ffill')
    
    # Save back to CSV
    df.to_csv('data/historical_prices.csv', index=False)
    print(f"✓ Successfully added AMZN and TSLA columns to historical_prices.csv")
    print(f"  Total rows: {len(df)}")
    print(f"  Columns: {', '.join(df.columns)}")

if __name__ == '__main__':
    try:
        add_amzn_tsla_to_csv()
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
