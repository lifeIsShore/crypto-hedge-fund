# Production-Ready Trading System Architecture
### From Backtester to Institutional-Grade Multi-Strategy Platform

---

## Executive Summary

This document defines the complete architectural roadmap to transition a portfolio engine from a backtesting framework into a robust, live-trading system. The goal is to eliminate every simulated assumption, replace prototype-grade components with production-grade equivalents, and build a modular platform that can support multiple alpha sources, institutional-quality risk management, and full operational observability.

Live trading is unforgiving. Every design decision in this architecture is made with that in mind.

---

## System Architecture Overview

The system follows a strict separation of responsibilities across a linear pipeline:

```
Raw Data
   │
   ▼
Data Infrastructure Layer
(ingestion, validation, adjustment, redundancy)
   │
   ▼
Feature Engineering Layer
(momentum, volatility, technicals, macro)
   │
   ▼
Alpha Modeling Layer
(multiple independent models → expected returns + confidence)
   │
   ▼
Portfolio Construction Layer
(Black-Litterman + constraints + cost modeling)
   │
   ▼
Risk Management Engine
(pre-trade controls + post-trade monitoring + regime detection)
   │
   ▼
Execution Engine
(order state machine + execution strategies + slippage model)
   │
   ▼
State Reconciliation
(broker as source of truth at every rebalance)
   │
   ▼
Persistence Layer
(PostgreSQL: positions, trades, features, signals, model outputs)
   │
   ▼
Monitoring & Observability
(PnL, drawdown, model decay, alerts)
   │
   ▼
Control Layer
(adaptive kill switches, volatility targeting, drawdown scaling)
```

Each component operates independently and communicates through well-defined interfaces. Failure in any single component must not cascade into system-wide failure.

---

## Phase 1 — Backtest Integrity: Eliminating Bias

Before allocating real capital, the backtesting engine must perfectly mirror real-world execution friction. A backtest that overstates returns due to simulation shortcuts is worse than no backtest at all.

### 1.1 Execution Timing

**The problem:** Most naive backtests compute a signal using Day T closing prices and immediately assume execution at those same prices. In reality, the market is closed when the signal fires.

**The fix:**
- Compute signals using **Day T close prices**
- Execute all resulting trades at **Day T+1 market open**
- This single change eliminates look-ahead bias and reflects real trading constraints

### 1.2 Position Sizing Constraints

Verify whether the target broker supports **fractional shares** for the asset universe you trade.

If fractional shares are **not** supported:
- Implement `math.floor()` lot sizing on all position calculations
- Accept residual cash as a natural part of portfolio dynamics
- Model this residual accurately in the backtest — it compounds over time and affects performance metrics

### 1.3 Transaction Cost Modeling

**Baseline:** Apply a flat **0.05% slippage penalty** to every trade to simulate the bid-ask spread. A strategy that does not survive this drag is not robust.

**Upgrade path:** Replace the flat model with a dynamic slippage model:
- Function of realized volatility at time of execution
- Function of asset liquidity (average daily volume relative to order size)
- Function of trade size as a percentage of ADV (Average Daily Volume)

If the strategy survives dynamic slippage modeling at realistic assumptions, it is deployable.

---

## Phase 2 — Data Infrastructure

Prototype data sources such as `yfinance` are excellent for research but are not suitable for live capital deployment. They are subject to rate limiting, missing trading days, unadjusted corporate actions, and unpredictable API availability.

### 2.1 Market Data Feed

Replace prototype data sources with a broker or institutional-grade API:
- **Interactive Brokers** — deep asset coverage, professional-grade historical data
- **Alpaca** — REST API with good US equity coverage, well-suited for automation
- **Polygon.io** — institutional-quality EOD and real-time data with clean split/dividend adjustment

All data must be:
- **Split-adjusted** — price continuity across corporate actions
- **Dividend-adjusted** — total return series where relevant
- **Timestamp-consistent** — no missing trading days, no duplicated records

### 2.2 Corporate Actions Handling

Maintain an explicit pipeline for corporate actions:
- **Stock splits** — retroactive price and share count adjustment
- **Dividends** — adjust historical prices or model reinvestment explicitly
- Do not rely on the data vendor to handle this silently — validate adjustments independently

### 2.3 Data Validation Layer

Implement automated quality checks before any data enters the feature pipeline:
- **Price change thresholds** — flag any single-day move beyond a defined percentage (e.g., ±25%) for manual review or automatic rejection
- **Missing observations** — detect gaps in time series and either auto-fill (forward-fill or interpolation) or reject the affected asset from that rebalance
- **Stale data detection** — flag assets where the latest timestamp does not match the expected trading day

Corrupted or suspicious data must never reach the portfolio construction layer.

### 2.4 Redundancy

Production data infrastructure requires a **primary provider** and a **fallback provider**. If the primary fails:
- The system automatically switches to the fallback
- Alerts are raised for the outage
- Trading continues without interruption

### 2.5 Data Ingestion Mechanics

- Use **asynchronous fetching** (e.g., Python's `asyncio`) when pulling data for large asset universes — sequential fetching for 100+ assets is too slow and hits rate limits
- Implement robust **retry mechanics** (e.g., the `Tenacity` library) with exponential backoff for network failures, rate limit responses, and API timeouts

---

## Phase 3 — Feature Engineering Layer

Feature engineering must be fully decoupled from trading logic. The feature pipeline runs independently, writes outputs to a structured store, and serves as the sole input to all alpha models.

### 3.1 Feature Categories

| Category | Examples |
|---|---|
| Momentum | 1M, 3M, 6M, 12M return; cross-sectional rank |
| Volatility | Realized vol (21D, 63D); vol of vol; GARCH estimates |
| Technical | RSI, MACD, Bollinger Band position, ATR |
| Macro | Interest rates, yield curve slope, FX rates, commodity prices |
| Sentiment (future) | News sentiment scores, analyst revision momentum |

### 3.2 Storage

Features are persisted daily to a structured database table: `feature_store`

- Schema: `(date, asset_id, feature_name, feature_value)`
- No flat files (CSV) in production — they do not support atomic writes or concurrent access
- The feature store is append-only; historical features are never overwritten

### 3.3 Output Interface

The feature store serves as the standardized input interface to all alpha models. A consistent schema ensures any model can be plugged in or swapped out without modifying upstream logic.

---

## Phase 4 — Alpha Modeling Layer

The system supports multiple independent alpha sources. This is the key architectural upgrade from a single-strategy system to a multi-strategy platform.

### 4.1 Alpha Model Examples

| Model | Signal Type |
|---|---|
| Momentum | Cross-sectional return rank |
| Mean Reversion | Deviation from fair value or moving average |
| Volatility Timing | Risk-adjusted expected return adjustment |
| Machine Learning | Predicted forward return from supervised model |

### 4.2 Output Structure

Each model produces a standardized output:

```
expected_return_i   →  forward return prediction for asset i
confidence_i        →  model confidence / signal strength (used as BL view weight)
```

This standardized interface is what allows the portfolio construction layer to treat all models uniformly.

### 4.3 Black-Litterman Integration

The portfolio construction layer uses the **Black-Litterman model** as its core framework. Alpha model outputs feed directly into BL as **views**:

- Each alpha model produces a view: "Asset X will return Y% over the next period"
- Confidence scores control how much the view tilts the posterior distribution away from the market equilibrium
- The BL posterior expected returns are then passed to the optimizer

**Critical design rule:** Machine learning models do not execute trades. They output views. The optimizer decides weights.

### 4.4 Fault Isolation

If any single alpha model fails (data unavailable, model crash, stale predictions):
- That model's views are excluded from the BL input
- The system continues with the remaining active models
- An alert is raised but trading is not halted
- No single alpha source creates a system dependency

---

## Phase 5 — Portfolio Construction Layer

Portfolio optimization must incorporate real-world constraints. Plain mean-variance optimization produces portfolios that are theoretically optimal but practically unimplementable.

### 5.1 Core Framework

**Black-Litterman** replaces raw historical mean returns as the expected return estimate. This provides:
- More stable portfolio weights (less sensitivity to estimation error)
- A principled way to incorporate alpha model views
- Better out-of-sample performance characteristics

### 5.2 Objective Function

The optimization problem is:

```
maximize:
    Expected Return
  − λ × Portfolio Variance
  − Transaction Costs
  − κ × Turnover Penalty

subject to:
    Σ weights = 1
    weight_i ≤ max_position_size
    sector_exposure_j ≤ max_sector_limit
    leverage ≤ max_leverage
```

This formulation produces **stable, implementable portfolios** — which is where most retail-grade systems fail.

### 5.3 Constraint Framework

| Constraint | Purpose |
|---|---|
| Maximum position size | Prevents concentration risk |
| Sector exposure limits | Controls systematic factor exposure |
| Turnover penalty | Reduces unnecessary trading costs |
| Transaction cost model | Ensures optimized portfolios are net-of-cost positive |
| Leverage constraint | Capital preservation under stress |

---

## Phase 6 — Risk Management Engine

The risk engine operates **independently** from portfolio construction. It acts as a separate layer of oversight that can override, scale, or halt the portfolio construction output.

### 6.1 Pre-Trade Risk Controls

Checks performed **before** any order is submitted:

- Maximum position size per asset (hard limit)
- Maximum sector or asset class exposure
- Maximum portfolio leverage
- Liquidity screen — no trades in assets with ADV below threshold relative to order size

If any pre-trade check fails, the offending order is blocked and an alert is raised.

### 6.2 Post-Trade Risk Monitoring

Continuous monitoring after execution:

- **Rolling Value-at-Risk (VaR)** — parametric and historical, at 95% and 99% confidence
- **Expected Shortfall (CVaR)** — captures tail risk beyond VaR
- **Drawdown tracking** — peak-to-trough across multiple lookback windows
- **Volatility regime detection** — identifies when realized volatility has shifted regime

### 6.3 Regime Detection

Replace hard threshold rules such as "if VIX > 35, go to cash" with a **probabilistic regime model**:

- Inputs: implied volatility (VIX), realized volatility, cross-asset correlations
- Output: probability of being in a low / medium / high stress regime
- Response: **continuous** scaling of risk exposure based on regime probability, not binary switches

This approach avoids the problem of being whipsawed in and out of the market at precisely the wrong moments.

---

## Phase 7 — Execution Engine

Execution is where theory meets reality. The execution engine must handle the full complexity of real market mechanics.

### 7.1 Order State Machine

Every order follows a defined lifecycle:

```
CREATED
   │
   ▼
SUBMITTED  ──────────────────────────────────► FAILED
   │                                           (rejected, error)
   ▼
PARTIALLY_FILLED
   │
   ▼
FILLED
```

The system must handle every state transition explicitly. There is no "assume it filled."

### 7.2 Execution Strategies

| Strategy | Use Case |
|---|---|
| Market-on-Open (MOO) | Standard rebalance execution — high fill certainty |
| Limit orders with tolerance bands | Reduce slippage on larger orders |
| VWAP-style execution | Large orders — minimize market impact over session |

The default for daily rebalancing is MOO. VWAP is reserved for scaling in/out of larger positions.

### 7.3 Execution Queue

All orders are placed into a **queue** before submission to the broker:
- Orders are validated (pre-trade risk checks) before entering the queue
- The queue handles partial fills, rejections, retries, and cancellations
- A partially filled order is tracked until completion or explicit cancellation

### 7.4 Dynamic Slippage Model

The static 0.05% slippage from the backtest phase is upgraded to a dynamic model:
- **Volatility component** — higher volatility widens spreads
- **Liquidity component** — lower ADV increases market impact
- **Size component** — larger orders relative to ADV incur more slippage

This model is also used in portfolio construction to accurately predict execution costs before trading.

---

## Phase 8 — State Reconciliation

This is a non-negotiable control mechanism. It is the single most important operational safeguard in a live trading system.

**The golden rule:** The system never trusts its own internal database for live balances.

At every rebalance cycle, before any calculation begins:

```python
positions = broker_api.get_positions()
cash      = broker_api.get_cash_balance()
open_orders = broker_api.get_open_orders()
```

The internal database is a **log and cache only** — not a source of truth. Any discrepancy between the internal state and the broker state is treated as an error requiring investigation before proceeding.

Failure to reconcile state is one of the most common causes of live trading disasters — the system thinks it owns something it sold, or doesn't own something it bought.

---

## Phase 9 — Persistence Layer

All flat files (`ledger.csv`, `engine_state.json`, `alpha_scores.csv`) must be replaced with a transactional database.

### 9.1 Recommended Database

- **PostgreSQL** — preferred for production; full ACID compliance, excellent performance, strong ecosystem
- **SQLite** — acceptable for single-machine deployments or development environments

### 9.2 Core Schema

| Table | Contents |
|---|---|
| `positions_history` | All historical portfolio positions with timestamps |
| `trades` | Complete trade log with execution details and costs |
| `feature_store` | Daily feature values per asset |
| `signals` | Raw alpha model outputs before portfolio construction |
| `model_outputs` | Final optimizer outputs: weights, expected returns, risk estimates |
| `risk_events` | Log of all pre-trade rejections and post-trade risk breaches |
| `reconciliation_log` | Record of every state reconciliation with any discrepancies noted |

### 9.3 Requirements

- **ACID compliance** — atomicity guarantees that a partial rebalance write does not leave the database in an inconsistent state
- **Recovery** — the system can restart after any interruption and reconstruct current state from the database alone
- **Audit trail** — every state change is logged with a timestamp; nothing is overwritten, only appended

---

## Phase 10 — Monitoring & Observability

A production system that cannot be observed cannot be trusted. Full transparency into system behavior is required at all times.

### 10.1 Performance Tracking

- Daily and cumulative PnL (gross and net of costs)
- Rolling Sharpe ratio (21D, 63D, 252D)
- Drawdown chart — current drawdown vs. historical distribution
- Exposure breakdown by asset, sector, and factor

### 10.2 Model Monitoring

For each alpha model independently:
- Rolling performance attribution — how much of PnL is explained by each model's views
- **Model decay detection** — flag when a model's information coefficient (IC) has degraded below a threshold over a rolling window
- Signal correlation monitoring — detect when models that should be independent start correlating (regime compression)

### 10.3 Alerting

Automated alerts for:

| Event | Severity |
|---|---|
| Trade execution failure | High |
| Missing or corrupted data | High |
| State reconciliation discrepancy | Critical |
| Drawdown breaching warning threshold | High |
| Alpha model IC below decay threshold | Medium |
| Abnormal PnL swing (>2σ daily move) | High |
| Data provider failover triggered | Medium |

Alerts must go to a durable channel (email, Slack, PagerDuty) — not just log files.

---

## Phase 11 — Control Layer

Hard kill switches must evolve into **adaptive, policy-based controls**. Binary on/off rules create dangerous discontinuities — moving 100% to cash at a single threshold is itself a risk.

### 11.1 Adaptive Controls

Replace hard rules with continuous scaling mechanisms:

| Rule-Based (Avoid) | Policy-Based (Use) |
|---|---|
| If drawdown > 10%, halt trading | Reduce gross exposure linearly from 100% to 20% as drawdown moves from 5% to 15% |
| If VIX > 35, go to cash | Scale risk exposure inversely to regime stress probability |
| If model crashes, shut down | Exclude failed model; continue with remaining models |

### 11.2 Volatility Targeting

Dynamically adjust portfolio leverage to maintain a **target realized volatility**:

```
target_vol = 10% annualized
current_realized_vol = (rolling 21D)

leverage_scalar = target_vol / current_realized_vol
portfolio_exposure = base_exposure × leverage_scalar
```

This automatically reduces risk in volatile regimes and allows fuller deployment in calm regimes.

### 11.3 Capital Allocation Adjustment

Allocate capital across alpha models dynamically based on rolling performance attribution. Models with decaying ICs receive reduced weight; models with improving ICs receive increased weight. This is a **meta-layer** above portfolio construction.

---

## Implementation Sequence

The phases above define the architecture. The recommended build sequence prioritizes risk reduction and capital preservation:

| Priority | Phase | Rationale |
|---|---|---|
| 1 | Backtest Integrity | Fix simulation before trusting any results |
| 2 | Data Infrastructure | No production system on prototype data |
| 3 | State Reconciliation | Non-negotiable before live trading |
| 4 | Persistence Layer | Required for state reconciliation to work |
| 5 | Execution Engine | Core live trading mechanics |
| 6 | Risk Management Engine | Protect capital before optimizing returns |
| 7 | Feature Engineering Layer | Foundation for alpha expansion |
| 8 | Portfolio Construction | Upgrade from Markowitz to Black-Litterman |
| 9 | Alpha Modeling Layer | Multi-strategy expansion |
| 10 | Monitoring & Observability | Operational transparency |
| 11 | Control Layer | Adaptive governance |

---

## Final Positioning

This architecture transforms the system from a single-strategy backtester into a **modular, multi-strategy investment platform** that is:

- Robust to data failures through redundancy and validation
- Resilient to execution failures through state machines and reconciliation
- Adaptable to new alpha sources through standardized model interfaces
- Aligned with institutional portfolio construction and risk management practices
- Observable and auditable at every layer

The system can be extended, stress-tested, and defended in a professional environment — a quantitative hedge fund, an asset management team, or an advanced research setting.

---

*Document version 1.0 — Architecture Roadmap*
