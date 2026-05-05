# Technical Deep-Dive & Implementation Guide
### Companion to: Production-Ready Trading System Architecture
### System Purpose: Decision Support & Control Tower — Human-Executed Trades

---

## A Note on System Intent

This system is a **control tower**, not an autopilot.

Every model, every signal, every risk metric exists to answer one question: **"What does the data say, and how confident should I be?"** You make the final call. The system's job is to ensure that call is informed, consistent, and free from cognitive bias.

This changes some design priorities:

- **Explainability** matters more than raw optimization power
- **Visualization** of uncertainty is as important as point estimates
- **Override logging** — when you disagree with the model, that disagreement is recorded and reviewed
- **Latency** is not critical — you do not need millisecond execution infrastructure

---

## Table of Contents

1. The Black-Litterman Model — Full Walkthrough
2. Probabilistic & Regime Detection Techniques
3. Feature Engineering — Detailed Implementation
4. Alpha Model Construction
5. Portfolio Construction — Constraints & Solver
6. Risk Engine — Metrics & Formulas
7. The Dashboard: What Your Control Tower Should Show
8. Implementation TODO — Sequenced Build Plan

---

## 1. The Black-Litterman Model — Full Walkthrough

### 1.1 Why Not Plain Markowitz?

The classic Markowitz mean-variance optimizer has a well-known flaw: it is an **error amplifier**. Small errors in expected return estimates produce wildly unstable portfolio weights. Feed it slightly wrong inputs and it confidently allocates 80% to one asset.

The root cause: Markowitz treats your return estimates as if they are exact. They are not. They are guesses.

Black-Litterman solves this by treating expected returns as a **probability distribution**, not a point estimate.

---

### 1.2 The Conceptual Framework

Black-Litterman starts from a simple idea:

> "If no one had any views about the future, what would the market's implied expected returns be?"

This baseline is called the **equilibrium return** — what returns would have to be for the current market-cap weights to be optimal for the average investor. You derive it by working backwards from observed prices.

Then you **update** this baseline with your own views — expressed as probability distributions, not certainties.

The math is Bayesian inference:

```
Prior:      Equilibrium returns (derived from market)
Likelihood: Your views (from alpha models, analysis)
Posterior:  Blended expected returns used in optimization
```

The degree of blending is controlled by how confident you are in your views relative to how much you trust the prior.

---

### 1.3 Step-by-Step Mathematical Derivation

**Step 1: Define inputs**

```
n       = number of assets
Σ       = n×n covariance matrix of asset returns (from historical data)
w_mkt   = n×1 vector of market-cap weights
δ       = risk aversion coefficient (typically 2.5 for equities)
τ       = scalar uncertainty in the prior (typically 0.025–0.05)
```

**Step 2: Compute equilibrium (implied) returns**

Work backwards from market weights using the CAPM relationship:

```
Π = δ × Σ × w_mkt
```

This gives you `Π`, an n×1 vector of implied excess returns. These are what the market is "pricing in." You are not guessing — you are reading the market's own signal.

**Step 3: Express your views**

Each view is a statement of the form: "I believe portfolio P will return μ over the next period, with uncertainty Ω."

Views are encoded in two matrices:

```
P   = k×n matrix — each row defines a portfolio (your view)
Q   = k×1 vector — your return forecast for each view
Ω   = k×k diagonal matrix — your uncertainty in each view
```

Example views:

| View | P row | Q | Interpretation |
|---|---|---|---|
| Absolute | [0, 0, 1, 0, ...] | 0.05 | Asset 3 will return 5% |
| Relative | [0, 1, -1, 0, ...] | 0.02 | Asset 2 will outperform Asset 3 by 2% |

**Uncertainty Ω** is typically set proportional to variance:

```
Ω = diag(P × (τΣ) × Pᵀ)
```

Higher uncertainty = view has less influence on the posterior.

**Step 4: Compute the posterior expected returns**

This is the BL master formula:

```
μ_BL = [(τΣ)⁻¹ + Pᵀ Ω⁻¹ P]⁻¹ × [(τΣ)⁻¹ Π + Pᵀ Ω⁻¹ Q]
```

Breaking this down intuitively:
- `(τΣ)⁻¹ Π` — prior term: equilibrium returns, weighted by confidence in the prior
- `Pᵀ Ω⁻¹ Q` — view term: your forecasts, weighted by confidence in your views
- The formula blends them proportionally

**Step 5: Compute the posterior covariance**

```
M_BL = [(τΣ)⁻¹ + Pᵀ Ω⁻¹ P]⁻¹
```

This is the uncertainty around `μ_BL` — useful for constructing confidence intervals on portfolio weights.

**Step 6: Feed into optimizer**

```
maximize:  μ_BL · w  −  (δ/2) × wᵀ Σ w
subject to: constraints (position limits, sector limits, etc.)
```

---

### 1.4 What Your Alpha Models Actually Do

In your control tower context, your alpha models (momentum score, any ML output, your own qualitative judgment) each become a **view**:

```
"My momentum model rates Asset X in the top quintile.
 I translate this to: expected outperformance of 3% vs. benchmark,
 with confidence proportional to the model's historical IC."
```

The IC (Information Coefficient — correlation between signal and forward return) directly controls the Ω uncertainty:

```
higher IC  →  lower Ω  →  view has more influence on output
lower IC   →  higher Ω →  view is largely ignored, prior dominates
```

This means when your models have been performing well, they influence the portfolio more. When they have been unreliable, the system automatically falls back toward the market equilibrium. This is self-correcting behavior.

---

### 1.5 Practical Parameters

| Parameter | Typical Value | Effect of Increasing |
|---|---|---|
| δ (risk aversion) | 2.5 | Higher → more conservative weights |
| τ (prior uncertainty) | 0.025 | Higher → prior matters less, views dominate |
| View confidence | IC-scaled | Higher → view moves weights more aggressively |

For a control tower system, you can expose δ and τ as **dashboard sliders** — letting you intuitively dial between "trust the market" and "trust my models."

---

## 2. Probabilistic & Regime Detection Techniques

### 2.1 Why Probability Distributions Over Point Estimates

A point estimate says: "The expected return is 8%."

A probability distribution says: "The expected return is 8%, but there is a 30% chance it is negative."

For a decision-support system, the distribution is always more useful than the point. You want to see:
- The central estimate
- The confidence interval around it
- The probability of a bad outcome

This is what separates a control tower from a simple signal generator.

---

### 2.2 Volatility Regime Detection

**The Hidden Markov Model (HMM) approach**

Markets alternate between regimes: low volatility / trend-following, and high volatility / mean-reverting. A two-state HMM can identify which regime you are likely in at any point.

**Inputs:**
- Daily log returns of the portfolio or a benchmark index
- Optionally: VIX level, realized volatility, cross-asset correlations

**Model structure:**

```
State 1 (Low Vol Regime):   returns ~ N(μ₁, σ₁²)   where σ₁ is small
State 2 (High Vol Regime):  returns ~ N(μ₂, σ₂²)   where σ₂ is large

Transition matrix A:
    A[1,1] = probability of staying in State 1
    A[1,2] = probability of switching from 1 to 2
    A[2,1] = probability of switching from 2 to 1
    A[2,2] = probability of staying in State 2
```

**Output:** A probability `P(regime = High Stress | data up to today)` that your dashboard displays as a gauge or heatmap.

**Python implementation (hmmlearn):**

```python
from hmmlearn.hmm import GaussianHMM
import numpy as np

returns = np.array(daily_log_returns).reshape(-1, 1)

model = GaussianHMM(n_components=2, covariance_type="full", n_iter=1000)
model.fit(returns)

# Get state probabilities for today
state_probs = model.predict_proba(returns)
stress_regime_prob = state_probs[-1, high_vol_state_index]
# Returns a float between 0 and 1
```

**Control tower use:** Display `stress_regime_prob` as a gauge on your dashboard. When it exceeds 0.6, the system flags a yellow/red alert and your position size suggestions from the optimizer are automatically scaled down.

---

### 2.3 Volatility Forecasting with GARCH

Historical rolling volatility is a lagging indicator. GARCH (Generalized Autoregressive Conditional Heteroskedasticity) models the fact that **volatility clusters** — high volatility days tend to follow high volatility days.

**GARCH(1,1) — the standard model:**

```
σ²_t = ω + α × ε²_(t-1) + β × σ²_(t-1)
```

Where:
- `σ²_t` = forecast variance for tomorrow
- `ε²_(t-1)` = yesterday's squared return shock (surprise)
- `σ²_(t-1)` = yesterday's variance forecast
- `ω, α, β` = fitted parameters (α + β < 1 for stationarity)

**Intuition:**
- High `α` → volatility reacts quickly to new shocks
- High `β` → volatility is persistent, slow to mean-revert
- `α + β` close to 1 → volatility is very persistent (common in equities)

**Python implementation (arch library):**

```python
from arch import arch_model
import pandas as pd

returns = pd.Series(daily_pct_returns) * 100  # GARCH works better on scaled returns

model = arch_model(returns, vol='Garch', p=1, q=1, dist='normal')
result = model.fit(disp='off')

# Forecast next-day volatility
forecast = result.forecast(horizon=1)
next_day_vol = np.sqrt(forecast.variance.values[-1, 0]) / 100  # back to decimal
```

**Control tower use:** Display GARCH-forecasted volatility alongside realized volatility. When GARCH vol diverges sharply upward from realized vol, the market is pricing in an upcoming stress event — worth your attention before placing any trades.

---

### 2.4 Value at Risk (VaR) and Expected Shortfall (CVaR)

**VaR** answers: "What is the most I can lose in a day, at 95% confidence?"

```
VaR_95 = μ_portfolio − 1.645 × σ_portfolio   (parametric, assuming normality)
```

**The problem with VaR:** It tells you nothing about what happens in the 5% of cases beyond the threshold. Two portfolios can have identical VaR but very different tail behavior.

**CVaR (Conditional VaR / Expected Shortfall)** answers: "Given that I am having a bad day beyond the VaR threshold, what is my expected loss?"

```
CVaR_95 = E[loss | loss > VaR_95]
```

For a normal distribution:

```python
from scipy import stats
import numpy as np

def portfolio_cvar(returns, confidence=0.95):
    mu = np.mean(returns)
    sigma = np.std(returns)
    
    var = stats.norm.ppf(1 - confidence, mu, sigma)
    cvar = mu - sigma * stats.norm.pdf(stats.norm.ppf(1 - confidence)) / (1 - confidence)
    
    return var, cvar  # Both as decimal returns (negative = loss)
```

**For non-normal returns (recommended):** Use historical simulation — sort actual returns and take the average of the worst 5%:

```python
def historical_cvar(returns, confidence=0.95):
    sorted_returns = np.sort(returns)
    cutoff_index = int((1 - confidence) * len(sorted_returns))
    cvar = sorted_returns[:cutoff_index].mean()
    return cvar
```

**Control tower use:** Show both VaR and CVaR on the dashboard. The gap between them indicates tail risk — a large gap means your portfolio has fat-tail exposure that VaR alone would understate.

---

### 2.5 Drawdown Analysis

Drawdown is more intuitive than VaR for most decision-makers. Three metrics matter:

```python
def drawdown_analysis(equity_curve):
    rolling_max = equity_curve.cummax()
    drawdown = (equity_curve - rolling_max) / rolling_max
    
    max_drawdown = drawdown.min()
    current_drawdown = drawdown.iloc[-1]
    
    # Time underwater: consecutive days below previous peak
    underwater = (drawdown < 0).astype(int)
    # ... calculate max consecutive run
    
    return {
        "max_drawdown": max_drawdown,          # worst peak-to-trough
        "current_drawdown": current_drawdown,  # where you are now
        "time_to_recovery": ...,               # average days to new high
    }
```

**Control tower use:** Display current drawdown vs. historical drawdown distribution. If current drawdown is at the 90th percentile of historical drawdowns, the system flags it — not as an automatic stop, but as a prompt for your review.

---

### 2.6 Bayesian Updating of Model Confidence

As you use the system over time, you can track whether each alpha model's predictions are actually coming true. Bayesian updating lets the system adjust model weights based on live performance:

```
Prior: model has IC of 0.05 (from backtest)
Observation: over last 60 days, model's actual IC is 0.08
Posterior: updated belief that model's true IC is higher than initially thought
→ increase model's view weight in BL framework
```

This creates a **self-improving system** where models that have been performing well get more influence and models that have been underperforming are automatically downweighted — without you having to manually intervene.

---

## 3. Feature Engineering — Detailed Implementation

### 3.1 Momentum Factors

Cross-sectional momentum: rank assets by their past return, go long top quintile, avoid or underweight bottom quintile.

```python
import pandas as pd

def momentum_score(prices, lookback_days=252, skip_days=21):
    """
    Standard momentum: 12-month return, skipping last month.
    Skip_days avoids short-term reversal contamination.
    """
    momentum = prices.shift(skip_days) / prices.shift(lookback_days) - 1
    # Cross-sectional rank (0 to 1)
    ranked = momentum.rank(axis=1, pct=True)
    return ranked

def momentum_score_3m(prices):
    return (prices / prices.shift(63) - 1).rank(axis=1, pct=True)
```

**Why cross-sectional ranking matters:** Raw return values are not comparable across market regimes. A 5% return means something very different in 2020 vs. 2022. Ranking normalizes this — you always know an asset's score relative to its peers, not in absolute terms.

### 3.2 Volatility Metrics

```python
def realized_volatility(returns, window=21):
    """Annualized realized volatility over rolling window."""
    return returns.rolling(window).std() * np.sqrt(252)

def volatility_of_volatility(returns, short=21, long=63):
    """
    High vol-of-vol = unstable regime.
    Useful as a risk-off signal input.
    """
    short_vol = realized_volatility(returns, short)
    long_vol = realized_volatility(returns, long)
    return (short_vol - long_vol) / long_vol  # relative vol spike
```

### 3.3 RSI (Relative Strength Index)

```python
def rsi(prices, period=14):
    delta = prices.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    
    avg_gain = gain.ewm(alpha=1/period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/period, adjust=False).mean()
    
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

# Interpretation for your dashboard:
# RSI > 70: potentially overbought — flag for review before adding exposure
# RSI < 30: potentially oversold — flag as potential entry
# RSI crossings of 50: momentum signal
```

### 3.4 Feature Store Schema

```sql
CREATE TABLE feature_store (
    date          DATE        NOT NULL,
    asset_id      VARCHAR(20) NOT NULL,
    feature_name  VARCHAR(50) NOT NULL,
    feature_value FLOAT       NOT NULL,
    computed_at   TIMESTAMP   DEFAULT NOW(),
    PRIMARY KEY (date, asset_id, feature_name)
);

-- Example query: get all features for today
SELECT asset_id, feature_name, feature_value
FROM feature_store
WHERE date = CURRENT_DATE
ORDER BY asset_id, feature_name;
```

---

## 4. Alpha Model Construction

### 4.1 The Information Coefficient (IC)

IC is the Pearson correlation between your model's signal today and the actual return over the next period:

```python
from scipy.stats import pearsonr

def information_coefficient(signals_t, returns_t_plus_1):
    """
    signals_t: cross-sectional signal values (e.g., momentum rank) at time t
    returns_t_plus_1: actual forward returns realized at t+1
    """
    ic, p_value = pearsonr(signals_t, returns_t_plus_1)
    return ic, p_value

# Rolling IC over time: gives you model performance history
rolling_ic = []
for i in range(lookback, len(dates)):
    ic, _ = information_coefficient(signals[i-1], returns[i])
    rolling_ic.append(ic)
```

**Interpreting IC:**
- IC of 0.05 is considered good in professional asset management
- IC of 0.10+ is exceptional
- Negative IC means the model is predicting backwards — still useful if you flip the sign

**IC Decay:** Track IC over rolling 21D, 63D, 252D windows. If the 21D IC drops sharply while 252D IC remains stable, it's a temporary noise blip. If all three are declining, the model is genuinely degrading.

### 4.2 Translating IC to BL View Confidence

```python
def ic_to_view_uncertainty(ic, base_variance):
    """
    Higher IC → lower uncertainty → view has more influence in BL.
    Maps IC [0, 1] to an uncertainty scalar.
    """
    confidence = max(0.01, abs(ic))  # floor at 1% to avoid division by zero
    return base_variance / confidence
```

---

## 5. Portfolio Construction — Constraints & Solver

### 5.1 The Full Optimization Problem in Code

```python
import numpy as np
from scipy.optimize import minimize

def optimize_portfolio(mu_bl, sigma, current_weights, 
                        max_position=0.10, turnover_penalty=0.002,
                        transaction_cost=0.0005):
    n = len(mu_bl)
    
    def objective(w):
        # Expected return (negative because we minimize)
        ret = -np.dot(mu_bl, w)
        # Portfolio variance
        risk = 0.5 * 2.5 * np.dot(w, sigma @ w)
        # Turnover penalty
        turnover = turnover_penalty * np.sum(np.abs(w - current_weights))
        # Transaction costs
        costs = transaction_cost * np.sum(np.abs(w - current_weights))
        return ret + risk + turnover + costs
    
    constraints = [
        {'type': 'eq', 'fun': lambda w: np.sum(w) - 1},  # fully invested
    ]
    
    bounds = [(0, max_position)] * n  # long only, max 10% per asset
    
    result = minimize(
        objective,
        x0=current_weights,
        method='SLSQP',
        bounds=bounds,
        constraints=constraints
    )
    
    return result.x  # optimal weights
```

### 5.2 Adding Sector Constraints

```python
def sector_constraints(sector_map, max_sector_weight=0.30):
    """
    sector_map: dict mapping asset_index → sector_name
    Returns list of constraint dicts for scipy.optimize
    """
    sectors = set(sector_map.values())
    constraints = []
    
    for sector in sectors:
        sector_assets = [i for i, s in sector_map.items() if s == sector]
        constraints.append({
            'type': 'ineq',
            'fun': lambda w, idx=sector_assets: max_sector_weight - np.sum(w[idx])
        })
    
    return constraints
```

### 5.3 What to Show on the Dashboard

After optimization runs, your control tower should display:

- **Suggested weights** vs. **current weights** — a bar chart showing what the model recommends
- **Delta (trades required)** — sorted by size, showing which assets to buy/sell and by how much
- **Expected portfolio metrics** at the suggested weights: return, vol, Sharpe, max drawdown estimate
- **Sensitivity analysis** — "what happens to weights if I change δ from 2.5 to 3.0?"

You review this output and decide what to act on.

---

## 6. Risk Engine — Metrics & Formulas

### 6.1 Portfolio Beta

```python
def portfolio_beta(portfolio_returns, benchmark_returns, window=63):
    """Rolling beta vs. benchmark."""
    cov = portfolio_returns.rolling(window).cov(benchmark_returns)
    var = benchmark_returns.rolling(window).var()
    return cov / var
```

**Control tower use:** Display rolling beta. When beta drifts significantly from your target (e.g., target 0.8, current 1.2), flag it as a prompt to review sector or factor exposures.

### 6.2 Factor Exposure

If you have factor data (e.g., from Fama-French), you can decompose portfolio returns:

```python
from sklearn.linear_model import LinearRegression

def factor_attribution(portfolio_returns, factor_returns):
    """
    factor_returns: DataFrame with columns [MKT, SMB, HML, MOM, ...]
    Returns factor loadings (betas) and residual alpha
    """
    model = LinearRegression()
    model.fit(factor_returns, portfolio_returns)
    
    loadings = dict(zip(factor_returns.columns, model.coef_))
    alpha = model.intercept_
    r_squared = model.score(factor_returns, portfolio_returns)
    
    return loadings, alpha, r_squared
```

### 6.3 Stress Testing

Rather than relying only on statistical models, define a set of named scenarios and compute portfolio impact:

```python
scenarios = {
    "2008 GFC":       {"equities": -0.45, "bonds": +0.08, "gold": +0.05},
    "2020 COVID":     {"equities": -0.34, "bonds": +0.06, "gold": +0.08},
    "2022 Rate Shock":{"equities": -0.20, "bonds": -0.15, "gold": -0.02},
    "Mild Correction":{"equities": -0.10, "bonds": +0.02, "gold": +0.01},
}

def stress_test(weights, asset_to_class_map, scenarios):
    results = {}
    for scenario_name, shocks in scenarios.items():
        portfolio_shock = sum(
            weights[i] * shocks.get(asset_to_class_map[i], 0)
            for i in range(len(weights))
        )
        results[scenario_name] = portfolio_shock
    return results
```

**Control tower use:** Display a stress test table on the dashboard — every time weights change, you instantly see the estimated P&L impact of historical crisis scenarios. This is one of the most valuable pieces of information for a human decision-maker.

---

## 7. The Dashboard: What Your Control Tower Should Show

Since you are executing trades manually, the dashboard is the product. Everything above serves this interface.

### 7.1 Recommended Layout

```
┌─────────────────────────────────────────────────────────────────┐
│  PORTFOLIO OVERVIEW                          DATE: 2024-01-15   │
│  NAV: €485,230    Daily P&L: +€1,240    YTD: +8.4%             │
├──────────────────┬──────────────────────┬───────────────────────┤
│  REGIME GAUGE    │  RISK METRICS        │  MODEL HEALTH         │
│                  │                      │                       │
│  [●●●●○○○○○○]   │  VaR (95%): -1.2%   │  Momentum IC: 0.07   │
│  Stress: 38%     │  CVaR (95%): -1.9%  │  Mean Rev IC: 0.04   │
│  Low-Med Regime  │  Beta: 0.82          │  Vol IC: 0.03         │
│                  │  Max DD: -8.3%       │  Decay alerts: None  │
├──────────────────┴──────────────────────┴───────────────────────┤
│  SUGGESTED REBALANCE                                            │
│                                                                 │
│  Asset    Current%  Suggested%   Δ       Action                │
│  AAPL     8.2%      9.5%        +1.3%   BUY  ~€6,300          │
│  MSFT     7.1%      6.0%        -1.1%   SELL ~€5,340          │
│  CASH     12.0%     8.0%        -4.0%   DEPLOY                │
│  ...                                                            │
│                                                [ACCEPT] [SKIP]  │
├─────────────────────────────────────────────────────────────────┤
│  STRESS TEST           │  DRAWDOWN CHART                        │
│  GFC 2008:   -18.4%   │  [equity curve with drawdown shading]  │
│  COVID 2020: -11.2%   │                                        │
│  Rate 2022:  -9.8%    │                                        │
└─────────────────────────────────────────────────────────────────┤
│  ALERTS                                                         │
│  ⚠ AAPL momentum IC below 30D avg — confirm before overweight  │
│  ✓ All data feeds healthy                                       │
│  ✓ State reconciled                                             │
└─────────────────────────────────────────────────────────────────┘
```

### 7.2 The Override Log

Every time you deviate from the model's suggestion, log it:

```sql
CREATE TABLE override_log (
    date            DATE,
    asset_id        VARCHAR(20),
    model_suggestion FLOAT,     -- what the model said to do
    action_taken     FLOAT,     -- what you actually did
    reason           TEXT,      -- free text: why you overrode
    outcome_30d      FLOAT      -- filled in later: was the override right?
);
```

Over time, this becomes a **feedback loop**: you can analyze whether your overrides add or subtract value from the model's baseline. Most systematic traders find this humbling — and instructive.

---

## 8. Implementation TODO — Sequenced Build Plan

### Phase 1 — Foundation (Weeks 1–3)

**Goal:** A working data pipeline with clean, validated, stored data.

- [ ] Set up PostgreSQL database locally (Docker recommended)
- [ ] Create `feature_store`, `prices`, `returns` tables
- [ ] Implement data ingestion from chosen provider (Alpaca or Polygon.io recommended for start)
- [ ] Write data validation layer:
  - [ ] Price change threshold checker (flag > ±20% daily)
  - [ ] Missing day detector
  - [ ] Split-adjustment validator
- [ ] Implement corporate actions adjustment pipeline
- [ ] Write daily ingestion script (scheduled via cron or Airflow)
- [ ] Test: run 2 years of history through pipeline, check for anomalies

---

### Phase 2 — Feature Engineering (Weeks 4–5)

**Goal:** Feature store populated daily with all required signals.

- [ ] Implement momentum factors (1M, 3M, 6M, 12M, cross-sectional rank)
- [ ] Implement realized volatility (21D, 63D)
- [ ] Implement GARCH(1,1) volatility forecast per asset
- [ ] Implement RSI (14-day)
- [ ] Implement MACD
- [ ] Write feature persistence to `feature_store` table
- [ ] Test: pull features for a given date, verify values manually against known prices

---

### Phase 3 — Alpha Models (Weeks 6–7)

**Goal:** Each model produces standardized `(expected_return, confidence)` output.

- [ ] Implement momentum alpha model (rank → expected return mapping)
- [ ] Implement IC calculation and rolling IC tracker
- [ ] Store model outputs to `signals` table with model name, date, asset, value
- [ ] Implement IC-to-BL-confidence converter
- [ ] Test: run models over historical period, compute IC, verify it is positive

---

### Phase 4 — Black-Litterman Optimizer (Weeks 8–10)

**Goal:** Given signals, produce suggested portfolio weights.

- [ ] Implement equilibrium return calculation (Π = δΣw_mkt)
- [ ] Implement view construction from alpha model outputs
- [ ] Implement BL posterior formula
- [ ] Implement constrained optimizer (scipy SLSQP or cvxpy recommended)
- [ ] Add sector constraint framework
- [ ] Add turnover penalty and transaction cost modeling
- [ ] Store outputs to `model_outputs` table
- [ ] Test: compare suggested weights to current weights, verify constraints are satisfied

---

### Phase 5 — Risk Engine (Weeks 11–12)

**Goal:** Full risk metrics computed daily and stored.

- [ ] Implement rolling VaR (parametric and historical)
- [ ] Implement CVaR / Expected Shortfall
- [ ] Implement drawdown tracker
- [ ] Implement GARCH-based vol forecast for risk module
- [ ] Implement HMM regime detector (2-state)
- [ ] Implement stress test framework with named scenarios
- [ ] Implement factor attribution (beta, optional Fama-French)
- [ ] Store all metrics to `risk_metrics` table (date, metric_name, value)

---

### Phase 6 — State & Persistence (Week 13)

**Goal:** System state is always consistent and recoverable.

- [ ] Implement positions table with full history
- [ ] Implement manual trade entry form (you enter what you executed)
- [ ] Implement state reconciliation: compare DB positions vs. broker statement
- [ ] Build reconciliation log
- [ ] Build override log

---

### Phase 7 — Dashboard (Weeks 14–18)

**Goal:** The control tower interface that makes everything usable.

- [ ] Choose framework: Streamlit (fast), Dash (more control), or custom React (best UX)
- [ ] Build portfolio overview panel (NAV, P&L, YTD)
- [ ] Build regime gauge (HMM stress probability)
- [ ] Build risk metrics panel (VaR, CVaR, drawdown)
- [ ] Build model health panel (rolling IC per model)
- [ ] Build rebalance suggestion table (current vs. suggested, with trade sizes)
- [ ] Build stress test table (auto-updates when weights change)
- [ ] Build drawdown chart with equity curve
- [ ] Build alerts panel
- [ ] Build override log entry form
- [ ] Test: full end-to-end run — data → features → signals → weights → dashboard display

---

### Phase 8 — Monitoring & Iteration (Ongoing)

- [ ] Set up automated daily run (cron or scheduler)
- [ ] Set up alert delivery (email or Slack)
- [ ] Review override log monthly — are your overrides adding value?
- [ ] Review model IC quarterly — is any model decaying?
- [ ] Extend universe or add new alpha models as needed

---

## Technology Stack Recommendation

| Component | Recommended Tool | Alternative |
|---|---|---|
| Database | PostgreSQL (Docker) | SQLite |
| Data ingestion | Polygon.io API | Alpaca, IB |
| Async fetching | Python asyncio + aiohttp | Tenacity |
| Optimization | cvxpy | scipy.optimize |
| HMM Regime | hmmlearn | pomegranate |
| GARCH | arch (Python) | statsmodels |
| Scheduling | APScheduler or cron | Airflow (overkill for solo) |
| Dashboard | Streamlit | Dash, React |
| Notifications | smtplib (email) | Slack webhooks |

---

*Technical Deep-Dive v1.0 — Companion to Architecture Roadmap*
*System Design: Decision Support & Control Tower*
