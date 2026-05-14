import os
import sys
import pandas as pd
import numpy as np
import logging
from datetime import datetime, timedelta

# Ensure root is in path
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.normpath(os.path.join(_HERE, '..', '..'))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from engine.features.feature_store import (
    load_returns_from_db, load_prices_from_db,
    compute_momentum_features, compute_volatility_features,
    compute_technical_features, persist_features
)
from portfolio.src.config import ASSET_UNIVERSE

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('backfill_features')

def run_backfill(days=252):
    tickers = ASSET_UNIVERSE
    logger.info(f"Starting feature backfill for {len(tickers)} tickers over {days} days")

    # Load 2 years of data to ensure enough history for all indicators (even at start of backfill)
    full_returns = load_returns_from_db(tickers, lookback_days=days + 504)
    full_prices  = load_prices_from_db(tickers, lookback_days=days + 504)

    if full_returns.empty:
        logger.error("No price data available in DB for backfill")
        return

    logger.info(f"Loaded returns for {len(full_returns.columns)} tickers")
    logger.info(f"Example tickers: {full_returns.columns[:10].tolist()}")

    # All dates in the returns series
    all_dates = full_returns.index.tolist()
    
    # We want to fill the last 'days' dates
    target_dates = all_dates[-days:]
    logger.info(f"Backfilling from {target_dates[0].date()} to {target_dates[-1].date()}")

    for i, target_date in enumerate(target_dates):
        date_str = str(target_date.date())
        
        # Slice history up to this date
        hist_returns = full_returns.loc[:target_date]
        hist_prices  = full_prices.loc[:target_date]
        
        # Compute features using existing logic
        # Note: compute_* functions take the latest row from the provided DF
        mom_features = compute_momentum_features(hist_prices)
        vol_features = compute_volatility_features(hist_returns)
        tech_features = compute_technical_features(hist_prices)
        
        frames = []
        if not mom_features.empty: frames.append(mom_features)
        if not vol_features.empty: frames.append(vol_features)
        if not tech_features.empty: frames.append(tech_features)
        
        if not frames:
            continue
            
        all_features = frames[0]
        for frame in frames[1:]:
            all_features = all_features.join(frame, how='outer')
            
        # Persist to DB
        persist_features(date_str, all_features)
        
        if i % 10 == 0:
            logger.info(f"Progress: {i}/{len(target_dates)} dates processed")

    logger.info("Backfill complete.")

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--days', type=int, default=252)
    args = parser.parse_args()
    
    run_backfill(days=args.days)
