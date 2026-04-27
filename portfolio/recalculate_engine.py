# recalculate_engine.py
# Minimal engine recalculation (no Streamlit launch)

import os
import json
import logging
import pandas as pd
import numpy as np
from datetime import datetime

from src.config import ASSET_UNIVERSE, LOOKBACK_DAYS, BENCHMARK_TICKER, RISK_FREE_RATE
from src.data_loader import load_ledger, fetch_historical, calculate_log_returns
from src.math_optimizer import run_all_scenarios
from src.rules_engine import apply_trend_filter, generate_trade_signals
from src.performance import generate_kpi_report

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

def calculate_current_weights(current_values, current_cash, total_portfolio_value):
    """Helper to calculate current percentage allocation."""
    if total_portfolio_value == 0:
        return {}
    weights = {ticker: value / total_portfolio_value for ticker, value in current_values.items()}
    weights['CASH'] = current_cash / total_portfolio_value
    return weights

def calculate_historical_portfolio_returns(log_returns, current_weights):
    """Approximates historical portfolio returns based on today's weights."""
    port_returns = pd.Series(0.0, index=log_returns.index)
    for ticker in log_returns.columns:
        weight = current_weights.get(ticker, 0.0)
        port_returns += log_returns[ticker] * weight
    return port_returns

def calculate_ledger_stats(ledger_path='data/ledger.csv'):
    """Calculate total deposits and fees from ledger."""
    total_deposits = 0.0
    total_fees = 0.0
    
    if not os.path.exists(ledger_path):
        return total_deposits, total_fees
    
    try:
        df = pd.read_csv(ledger_path, comment='#')
        for index, row in df.iterrows():
            action = str(row['Action']).strip().title()
            total = float(row['Total']) if pd.notna(row['Total']) else 0.0
            
            if action == 'Deposit':
                total_deposits += total
            elif action == 'Fee':
                total_fees += total
        
        logging.info(f"Ledger stats: Deposits: €{total_deposits:.2f}, Fees: €{total_fees:.2f}")
    except Exception as e:
        logging.warning(f"Could not calculate ledger stats: {e}")
    
    return total_deposits, total_fees

def recalculate():
    """Recalculate engine state and save to engine_state.json"""
    logging.info("📊 Recalculating engine state from ledger...")
    
    # 1. Load Current Reality
    current_holdings, current_cash = load_ledger('data/ledger.csv')
    
    # 2. Fetch Market Data
    prices_df = fetch_historical(ASSET_UNIVERSE, LOOKBACK_DAYS, 'data/historical_prices.csv')
    log_returns = calculate_log_returns(prices_df)
    latest_prices = prices_df.iloc[-1]
    
    # 3. Calculate current portfolio value
    current_values = {ticker: qty * latest_prices[ticker] for ticker, qty in current_holdings.items()}
    total_portfolio_value = sum(current_values.values()) + current_cash
    
    # 4. Run optimization
    all_results = run_all_scenarios(log_returns)
    optimal_weights = all_results['max_sharpe']
    
    # 5. Apply trend filter
    adjusted_weights = apply_trend_filter(prices_df, optimal_weights)
    
    # 6. Generate trade signals (returns 4 values)
    action_signal, reasons, signal_current_values, signal_total_value = generate_trade_signals(current_holdings, current_cash, latest_prices, adjusted_weights)
    
    # Update with values from signal generation
    current_values = signal_current_values
    total_portfolio_value = signal_total_value
    
    # 7. Calculate KPIs
    current_weights = calculate_current_weights(current_values, current_cash, total_portfolio_value)
    portfolio_returns = calculate_historical_portfolio_returns(log_returns, current_weights)
    
    # Calculate benchmark returns (EUNL.DE = MSCI World ETF)
    benchmark_returns = log_returns.get(BENCHMARK_TICKER, log_returns.iloc[:, 0])
    
    # Calculate portfolio performance metrics
    total_deposits, total_fees = calculate_ledger_stats('data/ledger.csv')
    
    kpis = generate_kpi_report(portfolio_returns, benchmark_returns, total_portfolio_value, total_deposits, total_fees, RISK_FREE_RATE)
    
    # 8. Save state
    engine_state = {
        "last_run": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "next_rebalance": "2026-04-11",
        "current_values": {
            "total_portfolio": total_portfolio_value,
            "cash": current_cash,
            "holdings": current_values
        },
        "optimal_weights": adjusted_weights,
        "current_weights": current_weights,
        "kpis": kpis,
        "latest_prices": {ticker: float(price) for ticker, price in latest_prices.items()},
        "action_signal": action_signal,
        "reasons": reasons
    }
    
    os.makedirs('data', exist_ok=True)
    with open('data/engine_state.json', 'w') as f:
        json.dump(engine_state, f, indent=4)
    
    logging.info("✅ Engine state updated successfully!")
    return True

if __name__ == "__main__":
    try:
        recalculate()
    except Exception as e:
        logging.error(f"❌ Engine recalculation failed: {e}")
        exit(1)
