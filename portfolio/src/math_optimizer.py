# src/math_optimizer.py

import numpy as np
import pandas as pd
from scipy.optimize import minimize
import logging

# Import constraints from config
from src.config import MAX_WEIGHT, RISK_FREE_RATE
def calculate_portfolio_performance(weights, mean_returns, cov_matrix, risk_free_rate=RISK_FREE_RATE):
    """
    Calculates the expected annualized return, annualized volatility, and Sharpe Ratio 
    of a given portfolio weight combination.
    """
    returns = np.sum(mean_returns * weights)
    std_dev = np.sqrt(np.dot(weights.T, np.dot(cov_matrix, weights)))
    
    # Handle edge case where std_dev is mathematically 0 to avoid division by zero
    if std_dev == 0:
        sharpe_ratio = 0
    else:
        sharpe_ratio = (returns - risk_free_rate) / std_dev
        
    return returns, std_dev, sharpe_ratio

def negative_sharpe_ratio(weights, mean_returns, cov_matrix, risk_free_rate=RISK_FREE_RATE):
    """
    Objective function for the optimizer. Scipy minimizes functions, so we minimize 
    the *negative* Sharpe ratio to find the maximum Sharpe ratio.
    """
    return -calculate_portfolio_performance(weights, mean_returns, cov_matrix, risk_free_rate)[2]

def portfolio_variance(weights, mean_returns, cov_matrix):
    """
    Objective function for the Minimum Variance portfolio.
    """
    return calculate_portfolio_performance(weights, mean_returns, cov_matrix)[1] ** 2

def negative_returns(weights, mean_returns, cov_matrix):
    """
    Objective function for the Maximum Return portfolio.
    """
    return -calculate_portfolio_performance(weights, mean_returns, cov_matrix)[0]

def optimize_portfolio(mean_returns, cov_matrix, objective='max_sharpe'):
    """
    Runs the scipy optimization to find optimal asset weights.
    Objective can be: 'max_sharpe', 'min_variance', or 'max_return'.
    """
    num_assets = len(mean_returns)
    
    # Give the optimizer a neutral starting point (equal weight)
    initial_guess = num_assets * [1. / num_assets,]
    
    # Constraint 1: Weights must sum to 1 (100% of capital allocated)
    constraints = ({'type': 'eq', 'fun': lambda x: np.sum(x) - 1})
    
    # Constraint 2: No short selling (0 min), Anti-YOLO rule (MAX_WEIGHT max)
    bounds = tuple((0.0, MAX_WEIGHT) for asset in range(num_assets))
    
    # Select the objective function based on user choice
    if objective == 'max_sharpe':
        opt_func = negative_sharpe_ratio
    elif objective == 'min_variance':
        opt_func = portfolio_variance
    elif objective == 'max_return':
        opt_func = negative_returns
    else:
        raise ValueError("Invalid objective. Use 'max_sharpe', 'min_variance', or 'max_return'.")

    # Run the SLSQP (Sequential Least Squares Programming) optimizer
    result = minimize(opt_func, initial_guess, args=(mean_returns, cov_matrix),
                      method='SLSQP', bounds=bounds, constraints=constraints)
    
    if not result.success:
        logging.warning(f"Optimizer failed to converge for {objective}. Check data.")
        
    return np.round(result.x, 4)

def run_all_scenarios(log_returns):
    """
    Takes the daily log returns, calculates necessary stats, and generates 
    the three required target portfolios.
    """
    # Annualize mean returns (252 trading days)
    mean_returns = log_returns.mean() * 252
    
    # Annualize covariance matrix
    cov_matrix = log_returns.cov() * 252
    
    # 1. Maximum Sharpe Ratio (The Default)
    weights_sharpe = optimize_portfolio(mean_returns, cov_matrix, 'max_sharpe')
    
    # 2. Minimum Variance (The Defensive Play)
    weights_min_var = optimize_portfolio(mean_returns, cov_matrix, 'min_variance')
    
    # 3. Maximum Return (The Aggressive Play)
    weights_max_ret = optimize_portfolio(mean_returns, cov_matrix, 'max_return')
    
    # Package the results nicely into a dictionary mapping tickers to weights
    tickers = log_returns.columns
    
    scenarios = {
        'max_sharpe': dict(zip(tickers, weights_sharpe)),
        'min_variance': dict(zip(tickers, weights_min_var)),
        'max_return': dict(zip(tickers, weights_max_ret))
    }
    
    logging.info("Mathematical optimization complete across all 3 scenarios.")
    return scenarios