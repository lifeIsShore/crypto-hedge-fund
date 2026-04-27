# src/performance.py

import numpy as np
import pandas as pd
import logging

# Note: portfolio_returns passed to these functions are LOG returns (from calculate_log_returns).
# Cumulative conversion: cumsum().apply(np.exp)  — NOT (1+r).cumprod()

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
    for the dashboard to render.

    Returns
    -------
    kpis : dict
    portfolio_returns : pd.Series   — the daily log-return series (last 252 days)
    """
    # FIX: Log returns must be converted via cumsum().exp(), NOT (1+r).cumprod()
    # Guard: if the return series is empty (all NaN after dropna) return safe defaults.
    portfolio_returns = portfolio_returns.dropna()
    if portfolio_returns.empty:
        logging.warning("portfolio_returns is empty — returning zero KPIs. Check data pipeline.")
        empty_kpis = {
            k: 0.0 for k in [
                "sharpe_ratio", "calmar_ratio", "max_drawdown", "information_ratio",
                "profit_factor", "real_return_pct", "portfolio_return_pct",
                "backtest_return_pct", "current_value", "initial_investment",
                "total_fees", "gross_pnl", "net_pnl",
                "ann_volatility_pct", "var95_daily_pct", "var99_daily_pct",
                "cvar95_daily_pct", "skewness", "excess_kurtosis",
            ]
        }
        empty_kpis["current_value"]      = round(current_value, 2)
        empty_kpis["initial_investment"] = round(initial_investment, 2)
        empty_kpis["total_fees"]         = round(total_fees, 2)
        return empty_kpis, portfolio_returns

    cum_returns = portfolio_returns.cumsum().apply(np.exp)

    max_dd = calculate_max_drawdown(cum_returns)
    sharpe = calculate_sharpe_ratio(portfolio_returns, risk_free_rate)
    calmar = calculate_calmar_ratio(portfolio_returns, max_dd)
    info_ratio = calculate_information_ratio(portfolio_returns, benchmark_returns)

    profit_factor = 0.0
    if trade_pnls:
        profit_factor = calculate_profit_factor(trade_pnls)

    # backtest_return_pct: Theoretical backtest using today's static weights.
    backtest_return_pct = float((cum_returns.iloc[-1] - 1) * 100) if len(cum_returns) > 0 else 0.0

    # Real P&L from the actual ledger
    gross_pnl = current_value + total_fees - initial_investment
    net_pnl = current_value - initial_investment
    real_return_pct = (net_pnl / initial_investment * 100) if initial_investment > 0 else 0.0

    # Annualised volatility of the portfolio return series
    ann_volatility = float(portfolio_returns.std() * np.sqrt(252) * 100)
    # Daily VaR 95% (historical, from the return series)
    sorted_r = sorted(portfolio_returns.dropna().tolist())
    n = len(sorted_r)
    var95_daily = float(sorted_r[int(0.05 * n)] * 100) if n > 0 else 0.0
    var99_daily = float(sorted_r[int(0.01 * n)] * 100) if n > 0 else 0.0
    tail95 = sorted_r[:max(1, int(0.05 * n))]
    cvar95_daily = float(sum(tail95) / len(tail95) * 100) if tail95 else 0.0
    skewness = float(portfolio_returns.skew())
    excess_kurtosis = float(portfolio_returns.kurtosis())  # pandas returns excess kurtosis

    kpis = {
        "sharpe_ratio":       round(sharpe, 2),
        "calmar_ratio":       round(calmar, 2),
        "max_drawdown":       round(max_dd, 4),
        "information_ratio":  round(info_ratio, 2),
        "profit_factor":      round(profit_factor, 2),
        # Honest % gain/loss on deposited capital (after fees)
        "real_return_pct":    round(real_return_pct, 2),
        # Theoretical 504-day backtest (not your actual gain)
        "portfolio_return_pct":  round(backtest_return_pct, 2),
        "backtest_return_pct":   round(backtest_return_pct, 2),
        "current_value":      round(current_value, 2),
        "initial_investment": round(initial_investment, 2),
        "total_fees":         round(total_fees, 2),
        "gross_pnl":          round(gross_pnl, 2),
        "net_pnl":            round(net_pnl, 2),
        # Risk metrics derived from the real return series
        "ann_volatility_pct": round(ann_volatility, 2),
        "var95_daily_pct":    round(var95_daily, 3),
        "var99_daily_pct":    round(var99_daily, 3),
        "cvar95_daily_pct":   round(cvar95_daily, 3),
        "skewness":           round(skewness, 3),
        "excess_kurtosis":    round(excess_kurtosis, 3),
    }

    logging.info(f"KPIs — Sharpe: {kpis['sharpe_ratio']}, Max DD: {kpis['max_drawdown']*100:.1f}%, "
                 f"Ann.Vol: {ann_volatility:.1f}%, VaR95: {var95_daily:.2f}%")
    return kpis, portfolio_returns


def compute_asset_stats(log_returns, current_weights):
    """
    Computes per-asset annualised return (mu) and volatility (sigma) from
    historical log returns, filtered to only held tickers.
    Returns a dict: { ticker: {mu_ann_pct, sigma_ann_pct} }
    """
    stats = {}
    for ticker in log_returns.columns:
        w = current_weights.get(ticker, 0.0)
        if w == 0.0:
            continue
        r = log_returns[ticker].dropna()
        if len(r) < 20:
            continue
        mu_ann  = float(r.mean() * 252 * 100)
        sig_ann = float(r.std()  * np.sqrt(252) * 100)
        stats[ticker] = {
            "mu_ann_pct":    round(mu_ann, 2),
            "sigma_ann_pct": round(sig_ann, 2),
        }
    return stats