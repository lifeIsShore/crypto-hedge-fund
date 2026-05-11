# src/data_loader.py

import os
import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime, timedelta
import logging

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

        for _, row in df.iterrows():
            action = str(row['Action']).strip().title()
            ticker = str(row['Ticker']).strip().upper()
            qty    = float(row['Quantity']) if pd.notna(row['Quantity']) else 0.0
            total  = float(row['Total'])    if pd.notna(row['Total'])    else 0.0

            if action == 'Deposit':
                cash += total
            elif action == 'Dividend':
                cash += total
            elif action == 'Fee':
                cash -= total
            elif action == 'Buy':
                cash -= total
                holdings[ticker] = holdings.get(ticker, 0.0) + qty
            elif action == 'Sell':
                cash += total
                holdings[ticker] = holdings.get(ticker, 0.0) - qty
                if holdings[ticker] <= 0.0001:
                    del holdings[ticker]

        logging.info(f"Ledger loaded. Cash: \u20ac{cash:.2f}, Holdings: {len(holdings)} assets.")
        return holdings, cash

    except Exception as e:
        logging.error(f"Error parsing ledger: {e}")
        raise


def validate_data(prices_df, max_daily_move=0.30):
    """
    Sanity Gate: forward-fills gaps and flags large daily moves.

    NON-FATAL: yfinance uses auto_adjust=True so splits are already corrected.
    Moves >30% are almost always real (earnings, crashes, news). We log a
    WARNING but never raise — the engine will continue processing.

    Returns True always (kept for backward compatibility).
    """
    if prices_df.isnull().values.any():
        logging.warning("Missing values detected in price data. Forward-filling gaps.")
        prices_df.ffill(inplace=True)
        prices_df.dropna(inplace=True)

    pct_returns = prices_df.pct_change().dropna()
    max_moves   = pct_returns.abs().max()
    anomalies   = max_moves[max_moves > max_daily_move]

    if not anomalies.empty:
        # WARNING only — do NOT raise. These are legitimate market events.
        logging.warning(
            f"\u26a0\ufe0f  Large moves (>{max_daily_move*100:.0f}%) flagged in "
            f"{list(anomalies.index)} \u2014 engine will continue. "
            "Inspect manually if you suspect an unadjusted split."
        )

    return True


def _drop_dead_columns(prices: pd.DataFrame) -> pd.DataFrame:
    """
    Drops columns that are entirely NaN (delisted / no data tickers).
    If kept, calculate_log_returns' dropna(how='any') wipes every row,
    producing an empty DataFrame that crashes cum_returns.iloc[-1].
    """
    dead = [c for c in prices.columns if prices[c].isna().all()]
    if dead:
        logging.warning(f"\u26a0\ufe0f  Dropping {len(dead)} all-NaN ticker(s): {dead}")
        prices = prices.drop(columns=dead)
    return prices


def fetch_historical(tickers, lookback_days=504, cache_path='data/historical_prices.csv'):
    """
    Fetches adjusted closing prices from yfinance.
    Dead tickers are silently dropped; large moves are warned but allowed.
    """
    end_date   = datetime.today()
    start_date = end_date - timedelta(days=lookback_days + 100)

    os.makedirs(os.path.dirname(cache_path), exist_ok=True)
    logging.info(f"Fetching data for {len(tickers)} assets: {tickers}")
    logging.info(f"Fetching data for {len(tickers)} assets from Yahoo Finance...")

    try:
        # 1. Try bulk download first (fastest)
        data = yf.download(
            tickers,
            start=start_date.strftime('%Y-%m-%d'),
            end=end_date.strftime('%Y-%m-%d'),
            auto_adjust=True,
            progress=False,
        )

        if data.empty or (len(tickers) > 1 and 'Close' not in data.columns):
            logging.warning("Bulk download failed or returned empty. Falling back to individual fetches.")
            prices = pd.DataFrame()
        else:
            prices = pd.DataFrame({tickers[0]: data['Close']}) if len(tickers) == 1 else data['Close']

        # 2. If bulk failed or some tickers are missing, try individual fetches for those missing
        if prices.empty or len(prices.columns) < len(tickers):
            active_cols = list(prices.columns) if not prices.empty else []
            missing = [t for t in tickers if t not in active_cols]
            
            for ticker in missing:
                try:
                    t_data = yf.download(ticker, start=start_date.strftime('%Y-%m-%d'), 
                                         end=end_date.strftime('%Y-%m-%d'), 
                                         auto_adjust=True, progress=False)
                    if not t_data.empty:
                        prices[ticker] = t_data['Close']
                        logging.info(f"  [{ticker}] Fetched individually")
                except Exception as e:
                    logging.warning(f"  [{ticker}] Individual fetch failed: {e}")

        # Reindex to our expected universe (missing tickers become all-NaN)
        prices = prices.reindex(columns=tickers)
        prices = prices.tail(lookback_days)

        # Non-fatal sanity gate (warns only, never raises)
        validate_data(prices)

        # Remove tickers with absolutely no data before caching
        prices = _drop_dead_columns(prices)

        prices.to_csv(cache_path)
        logging.info(
            f"Data cached to {cache_path} "
            f"({len(prices.columns)}/{len(tickers)} active tickers)"
        )
        return prices

    except Exception as e:
        logging.error(f"Failed to fetch market data: {e}")

        if os.path.exists(cache_path):
            logging.info("Falling back to local cache...")
            prices = pd.read_csv(cache_path, index_col=0, parse_dates=True)
            prices = prices.tail(lookback_days)
            # Also clean stale cache — may contain old dead-ticker columns
            prices = _drop_dead_columns(prices)
            return prices
        raise


def calculate_log_returns(prices_df):
    """
    Converts raw prices into time-additive log returns.
    Drops rows where ALL values are NaN first (belt-and-braces),
    then any remaining row with a single NaN.
    """
    log_returns = np.log(prices_df / prices_df.shift(1))
    log_returns = log_returns.dropna(how='all')
    log_returns = log_returns.dropna(how='any')
    return log_returns


def fetch_fx_rate(from_currency='USD', to_currency='EUR'):
    """
    Fetches the live spot FX rate from Yahoo Finance.
    Falls back to 0.92 (ECB approximation) on any failure.
    """
    FALLBACK_RATE = 0.92
    pair = f"{from_currency}{to_currency}=X"
    try:
        data = yf.download(pair, period='2d', auto_adjust=True, progress=False)
        if data.empty or 'Close' not in data.columns:
            raise ValueError(f"Empty data for {pair}")
        close = data['Close'].dropna()
        rate  = float(close.iloc[-1])   # .iloc[-1] avoids FutureWarning from float(Series)
        logging.info(f"FX Rate fetched: 1 {from_currency} = {rate:.4f} {to_currency}")
        return rate
    except Exception as e:
        logging.warning(
            f"FX fetch failed ({e}). "
            f"Using fallback rate {FALLBACK_RATE} {to_currency}/{from_currency}."
        )
        return FALLBACK_RATE


def convert_usd_prices_to_eur(prices_df, usd_eur_rate):
    """
    Multiplies non-EUR tickers by the USD\u2192EUR rate.

    Recognised EUR-denominated suffixes (already priced in EUR):
      .DE  \u2014 Xetra / Frankfurt
      .AS  \u2014 Amsterdam (Euronext)
      .PA  \u2014 Paris (Euronext)

    Everything else (no suffix, .L, etc.) is treated as USD and converted.
    """
    EUR_SUFFIXES = ('.DE', '.AS', '.PA')

    converted   = prices_df.copy()
    n_converted = 0
    for col in converted.columns:
        if not any(col.endswith(s) for s in EUR_SUFFIXES):
            converted[col] = converted[col] * usd_eur_rate
            logging.info(f"  Converted {col}: USD \u2192 EUR @ {usd_eur_rate:.4f}")
            n_converted += 1
    logging.info(f"Currency conversion applied to {n_converted} non-EUR tickers.")
    return converted


def calculate_ledger_stats(filepath='data/ledger.csv'):
    """
    Computes total deposited capital and total fees from the ledger.
    Returns (total_deposits, total_fees).
    """
    total_deposits = 0.0
    total_fees     = 0.0

    if not os.path.exists(filepath):
        return total_deposits, total_fees

    try:
        df = pd.read_csv(filepath, comment='#')
        for _, row in df.iterrows():
            action = str(row['Action']).strip().title()
            total  = float(row['Total']) if pd.notna(row['Total']) else 0.0
            if action == 'Deposit':
                total_deposits += total
            elif action == 'Fee':
                total_fees += total
    except Exception as e:
        logging.error(f"Error reading ledger stats: {e}")

    return total_deposits, total_fees