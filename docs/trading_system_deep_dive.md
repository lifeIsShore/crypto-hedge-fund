# Technical Deep-Dive & Mathematical Reference
### Companion Guide to the Hedge Fund Control Tower Architecture

> **Purpose:** Detailed mathematical derivations, algorithms, and parameter formulas for Black-Litterman optimization, covariance shrinkage, risk metrics, and alpha evaluation.

---

## 1. Black-Litterman Mathematical Derivation

### 1.1 The Equilibrium Prior ($\Pi$)
Rather than using noisy historical sample means, Black-Litterman starts from the market equilibrium return vector $\Pi$, calculated by reversing Markowitz optimization on market-cap weights $w_{\text{mkt}}$:

$$\Pi = \delta \Sigma w_{\text{mkt}}$$

Where:
- $\delta$: Risk aversion coefficient (default $= 2.5$).
- $\Sigma$: $N \times N$ covariance matrix of asset returns.
- $w_{\text{mkt}}$: Vector of market equilibrium weights.

### 1.2 Incorporating Views ($Q$, $P$, $\Omega$)
Views are expressed in matrix form:
$$P \cdot \mu \sim \mathcal{N}(Q, \Omega)$$

- $P$: $K \times N$ matrix picking assets involved in each of the $K$ views.
- $Q$: $K \times 1$ vector of view expected returns.
- $\Omega$: $K \times K$ diagonal matrix of view uncertainty variances:
  $$\Omega = \text{diag}\left( P (\tau \Sigma) P^T \right) / \text{Confidence}$$

Where:
- $\tau$: Scalar indicating uncertainty of the prior (default $= 0.05$).
- $\text{Confidence}$: Derived from the rolling Information Coefficient ($\text{IC}$) of the generating alpha model.

### 1.3 Posterior Distribution Master Formula
The blended posterior expected return vector $\mu_{\text{BL}}$ and posterior covariance matrix $M_{\text{BL}}$ are:

$$\mu_{\text{BL}} = \left[ (\tau \Sigma)^{-1} + P^T \Omega^{-1} P \right]^{-1} \left[ (\tau \Sigma)^{-1} \Pi + P^T \Omega^{-1} Q \right]$$

$$M_{\text{BL}} = \Sigma + \left[ (\tau \Sigma)^{-1} + P^T \Omega^{-1} P \right]^{-1}$$

---

## 2. Ledoit-Wolf Shrinkage Covariance Matrix

Sample covariance matrices estimated from $N$ assets over $T$ days suffer from high estimation error when $N \approx T$. We use **Ledoit-Wolf shrinkage** to blend the sample covariance $S$ with a structured target matrix $F$ (single-index constant correlation model):

$$\Sigma_{\text{LW}} = (1 - \alpha) S + \alpha F$$

Where $\alpha \in [0, 1]$ is the optimal shrinkage intensity computed analytically to minimize mean-squared error. Annualized by multiplying by 252.

---

## 3. Constrained Portfolio Optimization Solver

The optimizer (`engine/portfolio/optimizer.py`) minimizes the penalized negative utility:

$$\min_{w} \left[ -w^T \mu_{\text{BL}} + \frac{\delta}{2} w^T \Sigma w + \kappa \sum_{i=1}^N |w_i - w_{i, \text{prev}}| + \text{TaxPenalty}(w) \right]$$

Subject to:
1. **Fully Invested / Long Only:** $\sum_{i=1}^N w_i = 1.0, \quad w_i \ge 0$
2. **Max Position Limit:** $w_i \le 0.15 \quad \forall i$
3. **Max Sector Limit:** $\sum_{i \in \text{Sector}_j} w_i \le 0.30 \quad \forall j$
4. **Hierarchical Cluster Limit:** $\sum_{i \in \text{Cluster}_k} w_i \le 0.25 \quad \forall k$

---

## 4. Risk Engine Metrics & Formulas

### 4.1 Value at Risk (VaR) & Conditional VaR (CVaR)
- **Parametric VaR ($95\%$):**
  $$\text{VaR}_{0.95} = - (\mu_p - 1.645 \cdot \sigma_p)$$
- **Historical CVaR / Expected Shortfall ($95\%$):**
  $$\text{CVaR}_{0.95} = -\mathbb{E}[R_p \mid R_p \le \text{VaR}_{0.95}]$$
  Calculated by taking the average of the worst $5\%$ realized portfolio returns.

### 4.2 Alpha Model Information Coefficient (IC) & ICIR
For signal vector $s_t$ and realized forward return vector $r_{t+1}$:

$$\text{IC}_t = \text{SpearmanCorr}(s_t, r_{t+1})$$

$$\text{ICIR} = \frac{\mathbb{E}[\text{IC}_t]}{\text{Std}(\text{IC}_t)}$$

Models are evaluated across 5-day, 21-day, and 63-day horizons. An $\text{ICIR} > 0.5$ indicates strong predictive consistency.

### 4.3 Half-Kelly Sizing Formula
For an asset with win probability $p = \text{up\_proba}$ from the ML model and win/loss ratio $b$:

$$f^* = \frac{p(b+1) - 1}{b}$$

Half-Kelly fraction $f_{\text{half}} = 0.5 \cdot f^*$ is clipped to $[0.1, 1.0]$ and applied as a multiplicative scalar to buy orders.

---

## 5. Walk-Forward Backtesting Framework

The walk-forward suite (`backtests/walk_forward.py`) executes an expanding-window simulation:

1. **Warmup Cutoff:** 273 days ($252\text{d} + 21\text{d}$) minimum historical buffer.
2. **Rebalance Cadence:** Mondays only (matching live trading schedule).
3. **Information Barrier:** Price slice for step $t$ includes only dates $\le t$. Returns calculated using $t+1$ close prices.
4. **Artifact Emissions:** Each run outputs dated files in `backtests/runs/<run_id>/` and updates `runs_index.csv`.
