# Control Tower — Trading System Architecture & Technical Manual
### From Raw Data to Institutional Decision Support — Full Technical Blueprint

> **System Purpose:** Decision Support & Control Tower for Human-Executed Trades  
> **Repository:** `hedge-fund`  
> **Last Updated:** 2026-08-20  

---

## 1. Executive Overview

This system is an **institutional-grade quantitative control tower**. It processes market price data, macroeconomic indicators, technical factors, earnings calendars, and machine learning models every trading day. It derives optimal portfolio allocations using a constrained **Black-Litterman** framework, subjects the portfolio to rigorous risk checks and circuit breakers, and presents actionable recommendations via a high-performance **Flask Web Interface**.

### Core Operational Principles
1. **Decision Support, Not Autopilot:** The algorithm processes data and computes mathematically optimal weights, but human intuition and final execution remain in the loop.
2. **Deterministic & Self-Correcting:** Machine learning models do not place orders; they generate directional views. The Black-Litterman framework scales down model influence when predictive accuracy (Information Coefficient) declines.
3. **No Look-Ahead or Survival Bias:** All signal calculations use Day $T$ close data to prepare Day $T+1$ execution. Historical backtests run walk-forward routines with zero DB pollution.
4. **Dual-Database Isolation:** Real trading state (`engine_data.db`) is strictly separated from paper-trading sandbox state (`sandbox_data.db`).

---

## 2. End-to-End Pipeline Architecture (14-Step Unified Engine)

The core pipeline runs automatically via `engine/scheduler.py` (or manually via `RUN_FUND_TOTAL.bat` / `RUN_SANDBOX.bat`). It follows a strict 14-step assembly line:

```
                  ┌──────────────────────────────────────────┐
                  │ 1. Incremental Ingestion (yfinance/FRED) │
                  └────────────────────┬─────────────────────┘
                                       │
                  ┌────────────────────▼─────────────────────┐
                  │ 2. Feature Store (8 Core + Sector-Relative)│
                  └────────────────────┬─────────────────────┘
                                       │
                  ┌────────────────────▼─────────────────────┐
                  │ 3. Earnings Calendar & Throttle (Finnhub)│
                  └────────────────────┬─────────────────────┘
                                       │
                  ┌────────────────────▼─────────────────────┐
                  │ 4. Multi-Factor Alpha Signal Generation  │
                  │    (Mom, SecMom, RSI, VolTiming, ML, PEAD)│
                  └────────────────────┬─────────────────────┘
                                       │
                  ┌────────────────────▼─────────────────────┐
                  │ 5. Ledoit-Wolf Shrinkage Covariance     │
                  └────────────────────┬─────────────────────┘
                                       │
                  ┌────────────────────▼─────────────────────┐
                  │ 6. Black-Litterman Posterior Returns     │
                  └────────────────────┬─────────────────────┘
                                       │
                  ┌────────────────────▼─────────────────────┐
                  │ 7. Constrained Portfolio Optimization    │
                  │    (Position 15%, Sector 30%, Cluster 25%)│
                  └────────────────────┬─────────────────────┘
                                       │
                  ┌────────────────────▼─────────────────────┐
                  │ 8. Half-Kelly Position Sizing & Filters  │
                  └────────────────────┬─────────────────────┘
                                       │
                  ┌────────────────────▼─────────────────────┐
                  │ 9. Post-Trade Risk & Circuit Breakers    │
                  └────────────────────┬─────────────────────┘
                                       │
                  ┌────────────────────▼─────────────────────┐
                  │ 10. ETF Divergence & Human Labeling      │
                  └────────────────────┬─────────────────────┘
                                       │
                  ┌────────────────────▼─────────────────────┐
                  │ 11. Laggard Sector Screen & Disqualifiers│
                  └────────────────────┬─────────────────────┘
                                       │
                  ┌────────────────────▼─────────────────────┐
                  │ 12. Daily Performance Logging vs EUNL.DE │
                  └────────────────────┬─────────────────────┘
                                       │
                  ┌────────────────────▼─────────────────────┐
                  │ 13. Walk-Forward Backtest & Run Registry │
                  └────────────────────┬─────────────────────┘
                                       │
                  ┌────────────────────▼─────────────────────┐
                  │ 14. Push Signals to Review Queue & Flask  │
                  └──────────────────────────────────────────┘
```

---

## 3. Layer-by-Layer System Specification

### Layer 1: Data Ingestion & Validation
- **Incremental Data Ingestion (`engine/data/ingestion.py`):** Queries `MAX(date)` from the `prices` table and pulls only missing days (plus a 5-day overlap window to capture adjusted close revisions).
- **Multi-Source Resilience:** Uses `yfinance` for core price series, FRED REST API for risk-free rates ($10\text{Y}$ US Treasuries / EUR rates), and Finnhub for corporate earnings dates.
- **Staleness & Anomaly Checks:** Automatic alerts trigger if data feeds miss $>24\text{ hours}$ or if single-day price moves exceed $25\%$ without earnings news.

### Layer 2: Feature Store (`engine/features/feature_store.py`)
Computes normalized features across the universe:
- **Momentum Factors:** $1\text{M}, 3\text{M}, 6\text{M}, 12\text{M}$ returns (skipping the most recent month to avoid short-term reversal bias).
- **Sector-Relative Momentum:** Intra-sector percentile ranking of 12-month returns against sector peers.
- **Volatility Metrics:** $21\text{-day}$ and $63\text{-day}$ realized volatility and volatility-of-volatility.
- **Technical Indicators:** $14\text{-day}$ RSI, ATR, and Bollinger Band stretch.

### Layer 3: Alpha Models & Signal Generation
The engine combines six independent alpha sources:
1. **Cross-Sectional Momentum:** Rank-ordered momentum score mapped to expected return.
2. **Sector Relative Momentum:** Overweights top performers within rising sector themes.
3. **Mean Reversion / Technicals:** Volatility-adjusted RSI mean reversion ($50 - \text{RSI})/50$.
4. **Volatility Timing:** Penalizes high-volatility assets to capture the low-volatility anomaly.
5. **PEAD (Post-Earnings Announcement Drift):** Tracks earnings surprises and drift momentum.
6. **Machine Learning Stack (`ml_quant_finance_research/`):** XGBoost + LightGBM models outputting $21\text{-day}$ forward return probabilities (`up_proba`). Gated by AUC threshold ($\ge 0.53$).

### Layer 4: Black-Litterman Portfolio Construction
- **Implied Equilibrium Returns ($\Pi$):** Derived via reverse optimization from market-cap weights:
  $$\Pi = \delta \Sigma w_{\text{mkt}}$$
- **Ledoit-Wolf Covariance ($\Sigma$):** Shrinkage covariance matrix calculation to eliminate sample noise.
- **View Integration:** Alpha predictions are injected as absolute views ($P \mu = Q$) with view uncertainty diagonal ($\Omega$) inversely proportional to the model's rolling Information Coefficient (IC).
- **Constrained Optimizer (`engine/portfolio/optimizer.py`):** Solves via SLSQP:
  $$\max_{w} \left[ w^T \mu_{\text{BL}} - \frac{\delta}{2} w^T \Sigma w - \kappa \|w - w_{\text{prev}}\|_1 - \text{TaxDrag}(w) \right]$$
  Subject to:
  - Max Position Limit: $15\%$
  - Max Sector Limit: $30\%$
  - Max Hierarchical Correlation Cluster Limit: $25\%$
  - Long-only constraint: $w_i \ge 0, \sum w_i = 1.0$

### Layer 5: Pre & Post-Trade Risk Engine
- **Half-Kelly Position Sizing (`engine/execution/order_manager.py`):** Scales target weights based on half-Kelly fraction derived from ML win probability and volatility.
- **Earnings Throttle:** Halves buy sizes within $3\text{ days}$ of an earnings release.
- **Circuit Breakers (`engine/risk/circuit_breaker.py`):** Auto-forces target weight to $0.0$ if a stock drops $>15\%$ or an ETF drops $>12\%$ from average cost basis.
- **Macro Regime Filter:** Computes regime stress score (Low / Medium / High). Automatically scales down portfolio risk allocation during High Stress regimes.

---

## 4. Backtesting & Registry System (`backtests/`)

Every backtest run generates **immutable, non-overwriting artifacts**:

```
backtests/runs/
  20260820_152600/
    backtest_results.csv     ← daily equity curve & benchmark
    backtest_metrics.csv      ← Sharpe, CAGR, MDD, Alpha, Beta, etc.
    alpha_ic_results.csv      ← IC, ICIR, hit rate per model & horizon
    strategy_config.json      ← complete snapshot of active parameters
    run_meta.json             ← git commit, execution time, notes
  runs_index.csv              ← central master index (one row per run)
```

- **Registry Module (`backtests/registry.py`):** Central API for querying runs (`list_runs()`), fetching run details (`load_run()`), and updating notes (`update_note()`).
- **Batch Automation (`RUN_BACKTEST.bat`):** Passes a unified `RUN_ID` across `walk_forward.py`, `alpha_eval.py`, and `metrics.py`.

---

## 5. Web Interface & Control Tower (`flask_app.py`)

The web UI is a high-performance Flask application running on `http://localhost:5000`.

### Main Navigation Structure
- **Overview (`/`):** Real-time portfolio NAV, holdings, cash, trade advisor, and pipeline health.
- **BT History (`/backtest/history`):** Complete backtest run browser, date-range filter, side-by-side metric comparison with green/red winner highlights, equity curve overlay chart (normalised to 100%), alpha IC viewer, and inline note editor.
- **Risk & Strategy (`/risk`):** Monte Carlo portfolio VaR/CVaR, price targets, 1-sigma stop losses, and regime indicators.
- **Rebalance (`/rebalance`):** Target weight deltas, trade sizing in EUR, override logger, and trade execution controls.
- **ML Research (`/research`):** Rolling IC metrics, AUC health, model decay alerts, and walk-forward reports.
- **Macro Regime (`/regime`):** Probabilistic stress scores, yield curve slope, and trend filter state.
- **ETF Divergence (`/divergence`):** Human-in-the-loop scenario labeling for ETF-stock divergence signals.
- **Laggard Screen (`/laggards`):** Sector rotation laggards with disqualifier checks and conviction ratings.
- **Pipeline Health (`/health`):** Structured log viewer, API connectivity probes, and kill switch status.

---

## 6. Database Schema Summary (`engine_data.db` / `sandbox_data.db`)

Key tables in SQLite:
- `prices`: Daily OHLCV data, adjusted close, currency, source.
- `feature_store`: Daily engineered features per asset.
- `signals`: Raw expected returns and confidence from each alpha model.
- `price_targets`: ML win probability, 21-day price targets, 1-sigma stops, Kelly fraction.
- `model_outputs`: Final Black-Litterman posterior returns, current vs suggested weights, deltas.
- `trades`: Reconciled trade log (BUY/SELL, shares, price EUR, fee, notes).
- `positions_history`: Historical holdings snapshot per date.
- `cash_history`: Cash ledger tracking deposits, withdrawals, and trade debits/credits.
- `pipeline_runs`: Execution logs, step durations, and status per pipeline run.
- `risk_events`: Logged circuit breaker triggers, drawdown alerts, and data staleness warnings.
- `divergence_labels`: Human analyst scenario labels for ETF divergence events.
- `laggard_screen_results`: Weekly laggard screen outputs and disqualifiers.
