# Portfolio Risk Intelligence: Brainstorming & Audit

This document serves as the master plan for enhancing the portfolio's risk management capabilities. We are moving from basic historical metrics to a robust, multi-engine risk framework that includes Monte Carlo simulations, health checks, and automated validation.

## 1. Current Risk Stack Audit (As-Is)

Currently, the system has a foundational risk layer located in `engine/risk/`:

### A. Post-Trade Metrics (`post_trade.py`)
- **Historical VaR (95%)**: Non-parametric Value at Risk based on past returns.
- **Historical CVaR (95%)**: Conditional VaR (Expected Shortfall).
- **Drawdown Analysis**: Max Drawdown and Current Drawdown tracking.
- **Regime-Based Stress**: A composite score based on volatility and correlation compression.
- **Scenario Shocks**: Hardcoded historical shocks (GFC 2008, Covid 2020, Rate Shock 2022).

### B. Pre-Trade Controls (`pre_trade.py`)
- **Position Limits**: Max 10% per ticker.
- **Sector Exposure**: Max 30% per sector.
- **Leverage Check**: Ensuring total weight $\le$ 1.0.
- **Liquidity Guard**: (Planned/Placeholder) ADV-based order limits.

---

## 2. Identified Gaps & "Health Check" Requirements

To ensure the risk model is "healthy" and accurate, we need to address the following:

### 🚨 Critical Missing Components
1. **Monte Carlo VaR**: Currently, we only use historical simulation. MC VaR is essential for capturing non-linear risks and simulating thousands of potential future paths.
2. **Parametric VaR**: Normal/Log-normal VaR to provide a "baseline" for comparison.
3. **Backtesting Engine**: We calculate VaR, but we don't track if the portfolio "breaks" it more often than expected (e.g., if 95% VaR is breached > 5% of the time, the model is sick).

### 🩺 Health & Validation Checks
- **Data Integrity**: Automated checks for missing price data or "fat-finger" outliers in returns that could skew VaR calculations.
- **Correlation Stability**: Monitoring if correlations between "diversified" assets are spiking (Diversification Melt-down).
- **Concentration Risk**: Identifying if the top 3-5 holdings represent a disproportionate amount of the total VaR.

---

## 3. Proposed Component: Monte Carlo VaR Engine

**Logic Flow:**
1. **Covariance Estimation**: Use the last 252 days of log returns to compute the covariance matrix ($\Sigma$).
2. **Cholesky Decomposition**: Decompose $\Sigma$ into a lower triangular matrix $L$ such that $LL^T = \Sigma$.
3. **Simulation**: 
   - Generate $N$ (e.g., 10,000) vectors of random normal variables.
   - Correlate them using $L$.
   - Project portfolio returns across these $N$ paths.
4. **Result**: The 5th percentile of simulated returns is the 95% MC VaR.

**Improvement Idea**: Use **Student-t distribution** instead of Gaussian to account for "fat tails" (kurtosis) often seen in stock markets.

---

## 4. Proposed Component: VaR Health Check (Backtesting)

We need a script to perform a **Kupiec's Proportion of Failures (POF) Test**:
- **Input**: Last 252 days of actual returns vs. Predicted 95% VaR.
- **Metric**: Number of violations ($x$).
- **Health Signal**:
    - **Green**: $x \approx 12$ (Expected 5% of 252).
    - **Yellow**: $x > 18$ (Model might be underestimating risk).
    - **Red**: $x > 25$ (Model is broken; recalibrate lookback or distribution).

---

## 5. Roadmap: Risk Engine Evolution

- [ ] **Phase 1**: Implement the **Ensemble VaR Engine** (Gaussian, Student-t, GARCH).
- [ ] **Phase 2**: Build the **VaR Health Backtester** (Kupiec Test) to monitor model accuracy.
- [ ] **Phase 3**: Integrate **Marginal VaR (MVaR)** to identify specific risk-contributing tickers.
- [ ] **Phase 4**: Automated **Data Integrity Guard** (detecting outliers/NaNs in price feeds).

---

## 6. Implementation Task: Ensemble VaR Engine

**Objective**: Create a robust risk engine that computes a "Spectrum of VaR" using Gaussian, Student-t, and GARCH-filtered Monte Carlo simulations.

### Step 1: Data Preparation & Statistical Analysis
- **Requirement**: Fetch the last 252–504 days of log returns for all active portfolio holdings.
- **Computation**: 
    - Compute the **Covariance Matrix** ($\Sigma$).
    - Compute **Kurtosis** and **Skewness** for each asset to determine the appropriate "degrees of freedom" for the Student-t distribution.
    - Check for **Correlation Stability**: If the average correlation has spiked by >20% recently, flag it.

### Step 2: Build the Monte Carlo Core (`engine/risk/monte_carlo.py`)
- **Simulate Correlated Returns**: Use Cholesky decomposition ($L$) of the covariance matrix to correlate random variables.
- **Engine A (Gaussian)**: Use `np.random.standard_normal`.
- **Engine B (Student-t)**: Use `np.random.standard_t` with $df$ based on asset kurtosis. This is the "Tail Risk" model.
- **Engine C (GARCH-Filtered)**: 
    - Fit a GARCH(1,1) model to the portfolio's aggregate return stream.
    - Extract the "Conditional Volatility" ($\sigma_{t+1}$).
    - Scale the simulated returns by the ratio of $(\sigma_{t+1} / \sigma_{historical})$. This makes the VaR reactive to current market spikes.

### Step 3: Aggregation & Consensus Logic
- Compute the 95% and 99% VaR for all three engines.
- **Logic**:
    - `var_baseline`: Gaussian.
    - `var_conservative`: Student-t.
    - `var_tactical`: GARCH-filtered.
- **Consensus Signal**: If `var_tactical` is >1.5x `var_baseline`, trigger a **"Vol-Clustering Alert"** in the dashboard.

### Step 4: Integration & Persistence
- Update `engine/risk/post_trade.py` to call this new ensemble.
- Persist results to the `risk_metrics` table with new metric names: `var_95_mc_gaussian`, `var_95_mc_student_t`, `var_95_mc_garch`.

### Step 5: Dashboard Visualization
- Create a "Risk Spectrum" chart showing the three VaR levels.
- Add a "Health Status" badge based on the Backtesting Engine (Kupiec Test).

---

## ✅ Success Criteria
1. The engine produces three distinct VaR values.
2. The Student-t VaR is consistently more conservative (larger loss) than the Gaussian VaR in backtests.
3. The GARCH VaR spikes immediately following a high-volatility day (e.g., a -2% market drop).

---

## 7. Phase 5: UI Coherence & Professional Layout

**Goal**: Organize the Risk Tab into a clean, "Nerve Center" hierarchy that prevents information overload and provides actionable health signals.

### A. The "Nerve Center" (Top View)
- **Triple-VaR KPIs**: Three cards side-by-side:
    - `Gaussian (Baseline)`
    - `Student-t (Tail Risk)`
    - `GARCH (Tactical)`
- **System Health Badge**: A prominent status indicator (Green/Yellow/Red) derived from the **Kupiec Backtest**.
- **Consensus Message**: A dynamic text block (e.g., "Risk is within normal historical bounds" or "⚠ GARCH Divergence Detected: Volatility is clustering").

### B. The "Diagnostic Core" (Side-by-Side Panels)
- **Panel Left (Visual)**: **VaR Spectrum Chart**. A Bar/Line chart showing the spread between the 3 models.
- **Panel Right (Tabular)**: **Stress Scenarios & Shocks**. A table showing the projected EUR loss for historical events (e.g., GFC -50%, Covid -33%).

### C. The "Deep Dive" (Bottom Fold)
- **Upgraded Asset Breakdown**:
    - Add **Marginal VaR (MVaR)**: Shows how much risk each stock adds to the *total* portfolio.
    - Add **Liquidity Score**: "Days to Liquidate" based on position size / 30-day ADV.
- **Correlation Stress Matrix**: Highlight cells where correlations have increased by >0.20 in the last 10 days.

### D. Stability & Anti-Crash Guards
- **Null Guards**: All JS charts must use a `.filter(v => v !== null)` to prevent broken lines if one asset has missing data.
- **Unit Normalization**: Ensure all VaR numbers are stored and displayed as percentages (%) to avoid confusion with raw EUR values.

---

## 8. Cross-Project Context & Historical Integration

To ensure this risk framework aligns with previous development phases, the following requirements must be met:

### A. EUR Currency Normalization
- **Requirement**: All absolute risk values (e.g., Stress Scenario losses) must be computed in **EUR**. 
- **Context**: The fund operates in EUR (Trade Republic Local), and previous tasks established EUR as the base currency for all position values and ledger tracking.

### B. ML Signal Integration
- **Signal Overlay**: The "Risk Consensus" should incorporate the **ML Ensemble Score** from your research pipeline.
- **Logic**: If the ML signal is bearish AND the GARCH VaR is spiking, the "Consensus Status" should immediately move to **CRITICAL**.

### C. Relative Risk (Benchmarking)
- **Component**: Add **Relative VaR**. 
- **Metric**: Compare the Portfolio VaR against the Benchmark VaR (e.g., SPY or MSCI World). This answers the question: "Am I riskier than the market, or just following it?"

### D. Data Freshness Guard
- **Dependency**: Risk calculations must check the timestamp of `regime_state.json`. 
- **Alert**: If the regime data is >24h old, the dashboard should display a "Stale Risk Data" warning, as the volatility/correlation inputs may no longer reflect the current market regime.

### E. Drift Correlation
- **Metric**: Track the correlation between **Portfolio Drift** (unintended weight changes) and **VaR Increase**. 
- **Insight**: Identify if the portfolio is becoming riskier simply because you haven't rebalanced (Drift Risk).
