# src/performance.py

import numpy as np
import pandas as pd
import logging

def calculate_max_drawdown(cumulative_returns):
    """
    Calculates the maximum peak-to-trough drop in portfolio value.
    Your 'Pain Threshold' metric.
    """
    peak = cumulative_returns.cummax()
    drawdown = (cumulative_returns - peak) / peak
    max_dd = drawdown.min()
    return max_dd

def calculate_sharpe_ratio(returns, risk_free_rate=0.02):
    """
    Calculates annualized Sharpe Ratio.
    (Return per unit of total risk). Target > 1.0.
    """
    if returns.std() == 0:
        return 0.0
    
    # Convert annual RF rate to a daily rate for accurate subtraction
    daily_rf = (1 + risk_free_rate) ** (1/252) - 1
    excess_returns = returns - daily_rf
    
    # Annualize the ratio
    return np.sqrt(252) * excess_returns.mean() / excess_returns.std()

def calculate_calmar_ratio(returns, max_drawdown):
    """
    Calculates Calmar Ratio (Annualized Return / Absolute Max Drawdown).
    (Return per unit of worst-case pain). Target > 0.5.
    """
    if max_drawdown == 0:
        return 0.0
    
    ann_return = returns.mean() * 252
    return ann_return / abs(max_drawdown)

def calculate_information_ratio(portfolio_returns, benchmark_returns):
    """
    Calculates Information Ratio vs a benchmark (e.g., MSCI World).
    Proves if active rebalancing is actually beating a simple buy-and-hold.
    Target > 0.2.
    """
    # Align the two series by date to ensure accurate daily subtraction
    aligned = pd.concat([portfolio_returns, benchmark_returns], axis=1).dropna()
    aligned.columns = ['Portfolio', 'Benchmark']
    
    active_return = aligned['Portfolio'] - aligned['Benchmark']
    
    if active_return.std() == 0:
        return 0.0
        
    return np.sqrt(252) * active_return.mean() / active_return.std()

def calculate_profit_factor(trade_pnls):
    """
    Calculates Profit Factor: Sum of Gross Profits / Absolute Sum of Gross Losses.
    trade_pnls: A list of realized PnL values from closed trades.
    Target > 1.5.
    """
    if not trade_pnls:
        return 0.0
        
    gross_profits = sum(p for p in trade_pnls if p > 0)
    gross_losses = abs(sum(p for p in trade_pnls if p < 0))
    
    if gross_losses == 0:
        return float('inf') if gross_profits > 0 else 0.0
        
    return gross_profits / gross_losses
    
def generate_kpi_report(portfolio_returns, benchmark_returns, current_value, initial_investment, total_fees, risk_free_rate=0.02, trade_pnls=None):
    """
    Aggregates all KPIs into a single dictionary to be exported to engine_state.json
    for the Streamlit dashboard to render.
    """
    # Convert daily log returns to cumulative simple returns for drawdown math
    cum_returns = (1 + portfolio_returns).cumprod()
    
    max_dd = calculate_max_drawdown(cum_returns)
    sharpe = calculate_sharpe_ratio(portfolio_returns, risk_free_rate)
    calmar = calculate_calmar_ratio(portfolio_returns, max_dd)
    info_ratio = calculate_information_ratio(portfolio_returns, benchmark_returns)
    
    profit_factor = 0.0
    if trade_pnls:
        profit_factor = calculate_profit_factor(trade_pnls)
    
    # Calculate portfolio performance metrics
    portfolio_return_pct = ((cum_returns.iloc[-1] - 1) * 100) if len(cum_returns) > 0 else 0.0
    
    # Calculate unrealized/realized P&L
    # Gross P&L: What portfolio would be worth WITHOUT fees (add back fees to current value)
    gross_pnl = current_value + total_fees - initial_investment
    # Net P&L: Actual portfolio value minus what was invested
    net_pnl = current_value - initial_investment
    
    kpis = {
        "sharpe_ratio": round(sharpe, 2),
        "calmar_ratio": round(calmar, 2),
        "max_drawdown": round(max_dd, 4),  # Keeping extra precision for percentages
        "information_ratio": round(info_ratio, 2),
        "profit_factor": round(profit_factor, 2),
        "portfolio_return_pct": round(portfolio_return_pct, 2),
        "current_value": round(current_value, 2),
        "initial_investment": round(initial_investment, 2),
        "total_fees": round(total_fees, 2),
        "gross_pnl": round(gross_pnl, 2),
        "net_pnl": round(net_pnl, 2)
    }
    
    logging.info(f"KPIs Calculated - Sharpe: {kpis['sharpe_ratio']}, Max DD: {kpis['max_drawdown']*100:.1f}%")
    return kpis