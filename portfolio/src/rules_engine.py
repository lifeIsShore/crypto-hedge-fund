# src/rules_engine.py

import logging
import pandas as pd
from src.config import (
    DRIFT_THRESHOLD_BUY, DRIFT_THRESHOLD_SELL,
    MIN_TRADE_EUR_FLOOR, FEE_DRAG_TARGET,
    TREND_FILTER_MA_PERIODS
)

def apply_trend_filter(historical_prices_df, optimal_weights):
    """
    The Regime Filter: Checks if assets are above their 200-day Simple Moving Average.
    If an asset is in a Bear Regime (below SMA), its target weight is set to 0.0
    and the capital is reallocated to CASH for defensive positioning.
    """
    latest_prices = historical_prices_df.iloc[-1]
    
    # Calculate the moving average (default 200 days)
    sma = historical_prices_df.tail(TREND_FILTER_MA_PERIODS).mean()
    
    adjusted_weights = optimal_weights.copy()
    cash_allocation = adjusted_weights.get('CASH', 0.0)
    
    for ticker in list(adjusted_weights.keys()):
        if ticker == 'CASH':
            continue
        
        try:
            # Ensure we get scalar values, not Series
            current_price = float(latest_prices[ticker])
            ma_price = float(sma[ticker])
            
            if current_price < ma_price:
                logging.info(f"📉 BEAR REGIME: {ticker} (Price: €{current_price:.2f} < 200MA: €{ma_price:.2f}). Shifting to Cash.")
                cash_allocation += adjusted_weights[ticker]
                adjusted_weights[ticker] = 0.0
        except (KeyError, TypeError, ValueError) as e:
            logging.warning(f"⚠️ Skipping {ticker}: {e}")
            continue
            
    adjusted_weights['CASH'] = cash_allocation
    return adjusted_weights

def generate_trade_signals(current_holdings, current_cash, latest_prices, optimal_weights):
    """
    Compares current reality to the mathematical ideal. 
    Applies asymmetric drift thresholds and dynamic fee logic to output precise trades.
    """
    # 1. Calculate Total Portfolio Reality
    current_values = {}
    total_equity = 0.0
    
    for ticker, qty in current_holdings.items():
        if ticker in latest_prices.index:
            try:
                price = float(latest_prices[ticker])
                value = float(qty) * price
                current_values[ticker] = value
                total_equity += value
            except (ValueError, TypeError, KeyError) as e:
                logging.warning(f"⚠️ Skipping {ticker} in holdings: {e}")
                continue
            
    total_portfolio_value = total_equity + float(current_cash)
    
    # Calculate Dynamic Minimum Trade Size (Max of €25 or 0.5% of portfolio)
    dynamic_min_trade = max(MIN_TRADE_EUR_FLOOR, total_portfolio_value * FEE_DRAG_TARGET)
    
    signals = []
    reasons = []
    
    # 2. Iterate through targets and check for rebalance triggers
    for ticker, target_weight in optimal_weights.items():
        if ticker == 'CASH':
            continue
            
        target_euro = target_weight * total_portfolio_value
        current_euro = current_values.get(ticker, 0.0)
        
        current_weight = current_euro / total_portfolio_value if total_portfolio_value > 0 else 0.0
        drift_pct = current_weight - target_weight
        
        trade_euro = target_euro - current_euro
        abs_trade_euro = abs(trade_euro)
        
        # Suppress tiny trades immediately (Fee Drag check)
        if abs_trade_euro < dynamic_min_trade:
            reasons.append(f"{ticker} trade of €{abs_trade_euro:.2f} is below dynamic floor (€{dynamic_min_trade:.2f}). Ignored.")
            continue
            
        # Apply Asymmetric Thresholds
        if drift_pct >= DRIFT_THRESHOLD_SELL:
            # Sell condition triggered (e.g. drift is +8%, which is > +7%)
            signals.append(f"SELL €{abs_trade_euro:.2f} of {ticker}")
            reasons.append(f"{ticker} drift +{drift_pct*100:.1f}% breached {DRIFT_THRESHOLD_SELL*100}% sell limit. Locking profits.")
            
        elif drift_pct <= DRIFT_THRESHOLD_BUY:
            # Buy condition triggered (e.g. drift is -6%, which is < -5%)
            
            # Tax-Aware / Cash Flow First check
            if current_cash >= abs_trade_euro:
                signals.append(f"BUY €{abs_trade_euro:.2f} of {ticker} (Using Cash)")
                reasons.append(f"{ticker} drift {drift_pct*100:.1f}% breached {DRIFT_THRESHOLD_BUY*100}% buy limit. Deployed idle cash.")
                current_cash -= abs_trade_euro # Deduct from available cash pool
            else:
                signals.append(f"BUY €{abs_trade_euro:.2f} of {ticker}")
                reasons.append(f"{ticker} drift {drift_pct*100:.1f}% breached buy limit. Rebalance required.")
        else:
            reasons.append(f"{ticker} drift ({drift_pct*100:.1f}%) within safe asymmetric bounds.")

    # 3. Format the final output
    if not signals:
        action_signal = "✅ No action required this week. All assets within asymmetric drift thresholds."
    else:
        action_signal = "⚠️ REBALANCE REQUIRED:\n" + "\n".join([f" - {sig}" for sig in signals])
        
    return action_signal, reasons, current_values, total_portfolio_value