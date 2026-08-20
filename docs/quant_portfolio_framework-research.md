# Quant Portfolio Management Framework — Research & System Architecture Reference

> A structured reference for the institutional portfolio management framework implemented in the Hedge Fund Control Tower.

---

## The Three Pillar Architecture

### 1. Correlation Intelligence Engine
- **Data Standardization:** Log return transformations and volatility scaling.
- **Ledoit-Wolf Shrinkage:** Reduces sample covariance estimation noise.
- **Hierarchical Clustering:** Automatically groups co-moving assets into correlation clusters to enforce $25\%$ group caps in optimization (`engine/portfolio/optimizer.py`).
- **Pairs & Stat-Arb Scanner:** Cointegration and spread mean-reversion scanner available on `/pairs`.

### 2. Risk & Performance Metrics Engine
- **Performance Attributions:** CAGR, Total Return, Sharpe Ratio, Sortino Ratio, Calmar Ratio, Information Ratio.
- **Relative Risk Metrics:** Beta, Tracking Error, Daily Hit Rate, Annual Excess Returns vs MSCI World (`EUNL.DE`).
- **Tail Risk:** Rolling 95% Parametric VaR, Historical CVaR (Expected Shortfall), Max Drawdown tracking.
- **Circuit Breakers:** Pre-trade auto-zeroing of position weights if stock drawdown $>15\%$ or ETF drawdown $>12\%$.

### 3. The Quant Assembly Line
```
[ Alpha Models ]  ───►  [ Black-Litterman ]  ───►  [ Constrained Solver ]  ───►  [ Control Tower ]
 (Mom, RSI, ML,          Equilibrium + Views         SLSQP Optimizer +           Flask UI for
  PEAD, VolTiming)       weighted by IC             Caps & Penalties             Approval/Override
```

1. **Prediction:** Independent alpha models output directional expected returns and confidence.
2. **Blending:** Black-Litterman combines CAPM market equilibrium returns with model views.
3. **Allocation:** SLSQP optimizer computes target weights under position, sector, cluster, and cost constraints.
4. **Execution Decision:** Output rendered on `/rebalance` for human-in-the-loop approval.
