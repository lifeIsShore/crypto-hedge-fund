# Risk Engine Implementation Blueprint: Advanced Quantitative Framework

This document outlines the technical architecture and implementation steps for the next-generation Risk Engine, integrating Ensemble Monte Carlo, advanced risk attribution, and correlation-based trading signals.

---

## 1. Core Data Infrastructure: The Dynamic Covariance Engine
All advanced risk metrics (VaR, MVaR, Tracking Error) depend on a high-fidelity Covariance Matrix ($\\Sigma$).

### EWMA Covariance Matrix (`engine/risk/covariance.py`)
Moving beyond simple rolling windows to Exponentially Weighted Moving Average (EWMA) to prioritize recent volatility.
- **Math**: $\\sigma_{i,j,t} = (1 - \\lambda) r_{i,t-1} r_{j,t-1} + \\lambda \\sigma_{i,j,t-1}$
- **Parameter**: Set $\\lambda = 0.94$ (industry standard for daily returns).
- **Output**: Generates both the Covariance Matrix ($\\Sigma$) and the Correlation Matrix ($P$).

---

## 2. Priority 1: Ensemble Monte Carlo VaR (`engine/risk/monte_carlo.py`)
Moving from a single Gaussian model to a multi-model ensemble to capture fat-tail risks.

### Implementation Logic:
1.  **Student-t Model**: 
    - Set degrees of freedom ($\\nu$) between 3 and 5.
    - Captures the leptokurtic nature of financial returns (higher probability of extreme moves).
2.  **GARCH-Filtered Model**:
    - Use GARCH(1,1) to forecast volatility ($\\sigma_{t+1}$).
    - Rescale historical residuals by predicted volatility before running the Monte Carlo simulation.
3.  **Ensemble Execution**:
    - Draw $N$ paths using **Cholesky Decomposition** ($L \\cdot Z$) where $LL^T = \\Sigma$.
    - Run paths for both Gaussian and Student-t distributions.
    - **Final VaR**: Result = $\\max(\\text{Gaussian VaR}, \\text{Student-t VaR}, \\text{GARCH-VaR})$.

---

## 3. Priority 2 & 4: Risk Health & Attribution

### Kupiec POF Backtest (`engine/risk/backtest.py`)
A statistical "truth test" for the VaR model.
- **Logic**: Perform a Likelihood Ratio (LR) test on the number of VaR breaches ($x$) over $N$ days.
- **Thresholds**: 
    - **Green (Healthy)**: Breaches $\\approx 12/252$ (at 95% confidence).
    - **Red (Failing)**: Breaches $> 20/252$.
- **Integration**: Output results to a JSON feed for the `health.html` dashboard badge.

### Marginal VaR (MVaR) (`engine/risk/attribution.py`)
Determines the risk contribution of each specific position.
- **Math**: $MVaR_i = \\frac{VaR}{Portfolio Value} \\times \\beta_i$
- **Implementation**: Bolt this onto the Priority 1 engine. Since the covariance matrix is already computed, $\\beta$ is derived as $\\frac{Cov(r_i, r_p)}{\\sigma^2_p}$.

---

## 4. Priority 3 & 5: Execution Controls & Early Warning

### Pre-Trade Liquidity Polish (`engine/risk/pre_trade.py`)
- **Metric**: Days to Liquidate (DTL).
- **Implementation**: 
    - Query `prices` table for 20-day Average Daily Volume (ADV).
    - Hard Constraint: If $\\frac{\\text{Position Size}}{\\text{ADV} \\times 0.01} > 1$, flag as illiquid.
    - Wire `check_adv_liquidity()` directly into the execution order flow.

### Correlation Stability Monitoring
- **Concept**: Detect "Diversification Meltdown" (when all assets begin moving together).
- **Z-Score Logic**: 
    - Calculate rolling 20-day average pairwise correlation.
    - Compare current correlation to 1-year mean.
    - Alert: If Z-score $> 2.0$, flag as "High Correlation Regime."

---

## 5. Secondary Refinements & Alpha Signals

### Tracking Error VaR (Relative Risk)
- Instead of absolute VaR, compute the VaR of the **Spread Series**: $R_{port} - R_{benchmark}$.
- Essential for identifying risk relative to a target index (e.g., S&P 500).

### Correlation Breakdown (Pair Trading Opportunity)
- Use the `correlation_state.json` to monitor pairs (e.g., Asset A vs Asset B).
- **Signal**: If historical correlation is 0.8 but current 10-day correlation drops below 0.3 without fundamental divergence, flag as a **Mean Reversion / Pair Trade** opportunity.

### Consensus Messaging (ML + GARCH)
- **Logic**: Only trigger critical alerts when both signals align.
- **Rule**: `IF ML_Signal == "Bearish" AND GARCH_Tactical_Vol > 1.5 * Baseline_Vol THEN ALERT_CRITICAL`.
- **Pre-requisite**: Must be backtested to ensure the threshold isn't too restrictive.

---

## 6. Implementation Timeline

| Phase | Component | File Path |
| :--- | :--- | :--- |
| **Week 1** | Ensemble VaR (Cholesky + Student-t) | `engine/risk/monte_carlo.py` |
| **Week 2** | Backtesting (Kupiec POF) & Dashboard | `engine/risk/backtest.py` |
| **Week 3** | Liquidity & MVaR Integration | `engine/risk/pre_trade.py` |
| **Week 4** | Correlation Alpha Signals | `engine/alpha/pair_monitor.py` |