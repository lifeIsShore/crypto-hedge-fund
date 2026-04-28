# Quant Portfolio Management Framework

> A structured reference for building an institutional-grade, systematic portfolio management tool combining correlation intelligence, risk metrics, and multi-model capital allocation.

---

## Overview: The Three Core Pillars

This system is built around three interconnected pillars:

1. **Correlation Intelligence Engine** — understanding relationships between assets
2. **Risk & Performance Metrics** — measuring and validating strategy quality
3. **The Quant Assembly Line** — combining multiple models without conflict

---

## Part 1: Correlation Intelligence Engine

### What It Is

A correlation engine sits at the intersection of risk management and alpha generation. Rather than just calculating a static correlation matrix, the goal is to build a system that identifies *stable, tradable, risk-efficient relationships* between assets.

### The Four Layers

**Layer 1 — Data Engine**

Pull and normalize data across:
- Equities (stocks, sectors, indices)
- FX pairs
- Fixed income

Normalize using log returns and volatility scaling before any correlation work begins.

**Layer 2 — Correlation Intelligence**

Start simple, then evolve:

| Level | Method |
|---|---|
| Basic | Pearson correlation (rolling: 30d, 90d, 180d) |
| Intermediate | Rolling stability scores, regime detection |
| Advanced | DCC-GARCH dynamic correlations, cointegration tests |

Key pitfalls to avoid with raw correlation:
- Correlations **break during stress** — a -0.8 correlation pair can flip in a crisis
- Volatile spread between two assets means a correlated pair may still be unhedgeable
- Spurious correlation is endemic across FX and equities

**Layer 3 — Tradeability Scoring**

For each pair, output a composite score combining:
- Correlation strength
- Stability over time
- Volatility compatibility
- Mean-reversion signal

Example output: *"Pair Score: 8.3 / 10 → Suitable for hedge / stat-arb"*

**Layer 4 — Portfolio Integration**

Connect the correlation engine to portfolio-level decisions:
- Suggest hedges for each open position
- Surface diversification improvements
- Display portfolio correlation heatmap and marginal risk contributions
- Alert on correlation breakdown events

### Advanced Features That Create Real Edge

- **Regime Awareness**: Correlations behave differently in crises vs. bull markets — build regime flags
- **Lead-Lag Detection**: Who moves first? This is alpha, not just hedging
- **Cross-Asset Signals**: FX ↔ equities, rates ↔ sectors
- **ML Layer**: Predict future correlation stability, dynamically cluster assets, detect hidden relationships

---

## Part 2: Risk & Performance Metrics

### The Four Metric Groups

Group metrics by the question they answer:

**A. Performance — What did I earn?**
- Alpha (α)
- Sharpe Ratio
- Sortino Ratio
- Information Ratio (IR)

**B. Risk — What can go wrong?**
- Beta (β)
- Maximum Drawdown (MDD)
- Tracking Error
- Volatility

**C. Statistical Validity — Is this real or luck?**
- t-statistic
- p-value
- R²

> Rule of thumb: t-stat > 2 (p-value < 0.05) gives 95% confidence that alpha is not random noise.

**D. Benchmark Awareness — Am I adding value?**
- Alpha vs. benchmark
- Information Ratio
- Tracking Error

### Advanced Metrics (What Separates Junior from Institutional)

| Metric | Why It Matters |
|---|---|
| VaR / CVaR (Expected Shortfall) | Banks and HFs care deeply about tail risk, not just average loss |
| Factor Exposures (Fama-French) | Separates real alpha from disguised market beta |
| Rolling Sharpe / Beta / Volatility | Detects strategy decay over time |
| Turnover & Transaction Costs | A Sharpe of 2.0 can drop to 0.8 after real-world costs |
| Inter-strategy Correlation | Essential for building diversified multi-strategy portfolios |

### Using Metrics as Controls, Not Just Outputs

Don't display metrics statically. Wire them into decision logic:

- **Strategy filtering**: Only include strategies where Sharpe > 1.5, t-stat > 2, MDD < 20%, p-value < 0.05
- **Capital allocation**: Weight more toward higher IR, lower drawdown, stable alpha strategies
- **Regime classification**: High beta = market-driven; low beta + high alpha = true hedge fund behavior

---

## Part 3: The Quant Assembly Line

### Core Insight

These models do not all do the same job. They belong at different stations on the assembly line. Running them all at the same step creates philosophical conflicts and bad outputs.

```
[ Fama-French ] → [ Black-Litterman ] → [ MPT + Risk Parity ]
   Predict            Adjust                  Allocate
```

---

### Step 1 — Predicting Returns (Fama-French)

**Purpose**: Generate baseline expected return estimates grounded in factor data, not guesswork.

- Identify which assets carry high Value, Size, or Momentum characteristics
- Output: *"Asset A should return 8%; Asset B should return 5%"*

Key factors:
- **Market** (CAPM baseline)
- **Size** (small-cap premium)
- **Value** (cheap vs. expensive)
- **Momentum** (trend persistence)

---

### Step 2 — Adjusting Expectations (Black-Litterman)

**Purpose**: Blend model-based predictions with subjective views or external signals (e.g., a Markov Chain regime-switching model predicting recession).

- Input: Fama-French baseline returns
- Inject views: *"My regime model says bear market is 80% likely → downgrade equities by 2%"*
- Output: Smoothed, stable expected returns that won't cause the optimizer to produce extreme weights

Black-Litterman solves MPT's core problem: tiny input changes causing wild, unrealistic allocations (e.g., 90% into one asset).

---

### Step 3 — Allocating Capital (MPT + Risk Parity)

**Purpose**: Turn expected returns into actual portfolio weights, with a volatility guardrail.

- **MPT**: Finds the allocation that maximizes return per unit of risk (the Efficient Frontier)
- **Risk Parity constraint**: Ensures no single asset class contributes more than X% of total portfolio volatility

Example rule: *"Maximize Sharpe, but cap any asset's volatility contribution at 20% of total portfolio risk."*

This hybrid is called **Risk Budgeting** — it avoids the pure Risk Parity trap (see below).

---

### Where Models Clash: Traps to Avoid

**Trap 1 — Black-Litterman vs. Pure Risk Parity**

Pure Risk Parity ignores expected returns entirely — it assumes humans cannot predict the future, so it builds portfolios from volatility and correlations alone. If you run pure Risk Parity, all your Fama-French and Black-Litterman work gets deleted from the math. The solution is the **Risk Budgeting hybrid**: use BL returns, but constrain the optimizer with risk contribution limits.

**Trap 2 — Overfitting**

Using Fama-French to find past trends, then Monte Carlo to simulate them, then t-statistics to "validate" — all on the same historical dataset — is just slicing the same data three ways to confirm your own bias. A model that perfectly predicts the past often blows up in the future. Mitigations:
- Out-of-sample testing on held-out periods
- Walk-forward validation (rolling train/test windows)
- Regime sensitivity analysis

---

## Part 4: Probabilistic Tools

### Value at Risk (VaR) and CVaR

- **VaR**: Maximum expected loss over a timeframe at a confidence level (e.g., 1-day 99% VaR = $1M → 1% chance of losing more than $1M in a day)
- **CVaR / Expected Shortfall**: Average loss *beyond* the VaR threshold — preferred by regulators and sophisticated risk desks because it captures tail severity, not just tail probability

### Monte Carlo Simulation

- Generate tens of thousands of randomized price paths based on historical volatility and return distributions
- Analyze the resulting outcome cloud to produce probability ranges: *"85% probability the portfolio returns between 6-9% over the next decade"*
- Useful for stress testing and scenario analysis, not just point estimates

### Markov Chain Regime Models

- Model market states (e.g., State 1: Low-Volatility Bull; State 2: High-Volatility Bear)
- Calculate transition probabilities between states
- Feed regime probabilities into Black-Litterman as views
- Applications beyond equities: credit rating transitions in fixed income

---

## Architecture Summary

```
DATA LAYER
  └── Equities, FX, Fixed Income
  └── Log returns, volatility normalization

CORRELATION ENGINE
  └── Rolling Pearson (30/90/180d)
  └── Regime detection
  └── DCC-GARCH (advanced)
  └── Cointegration tests
  └── Tradeability scoring

RETURN PREDICTION
  └── Fama-French factor model
  └── Markov regime-switching input

EXPECTATION ADJUSTMENT
  └── Black-Litterman (BL mixes baseline + views)

PORTFOLIO OPTIMIZATION
  └── MPT (Efficient Frontier)
  └── Risk Budgeting constraint (hybrid Risk Parity)

METRICS & VALIDATION
  └── Performance: Sharpe, Sortino, Alpha, IR
  └── Risk: Beta, MDD, VaR, CVaR
  └── Statistical: t-stat, p-value, R²
  └── Rolling versions of all the above

DASHBOARD / DECISION ENGINE
  └── Correlation heatmap (live)
  └── Best hedge pairs panel
  └── Strategy filtering & scoring
  └── Allocation recommendations
  └── Alerts (correlation breakdown, regime shift)
```

---

## Key Conceptual Distinctions

| Concept | Common Mistake | Correct Framing |
|---|---|---|
| Correlation | "Find negative correlation" | "Find stable, tradable, risk-efficient relationships" |
| Metrics | Display statically as outputs | Use as controls for allocation and filtering decisions |
| Risk Parity | Run it purely, ignoring returns | Use as a risk budgeting constraint alongside BL returns |
| Backtesting | Validate on same data used to build model | Walk-forward, out-of-sample, regime-split testing |
| Alpha | High t-stat means it's real | High t-stat on in-sample data; need OOS confirmation |

---

*Last updated: work in progress — brainstorm / reference document*
