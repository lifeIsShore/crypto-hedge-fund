# Comprehensive Quantitative Trading Engine Blueprint

> A complete, production-ready plan for building a systematic investment engine on Trade Republic. This document preserves all strategic and mathematical detail from the original concept while organizing it for actual development.

---

## Part 1: Reality Check & Trade Republic Constraints

### 1.1 The Core Limitation: No Official API

**The Reality:**
- Trade Republic does not offer a public API for automated retail trading.
- Unofficial reverse-engineered Python wrappers (like `pytr`) exist on GitHub but violate TR's Terms of Service.
- Using them risks account termination.

**Our Workaround: The "Advisor" Model**
- Your Python engine runs locally on your computer.
- It crunches all the math and outputs clear, actionable instructions: *"Buy 12 shares of AAPL, Sell 5 shares of MSFT."*
- You manually execute these trades in the TR app on your phone.
- This keeps you fully in control and compliant with TR's terms.

### 1.2 Constraint: No Direct Short Selling

**The Reality:**
- Trade Republic restricts retail investors from direct short selling.
- Alternative instruments exist: Knock-Out Certificates, Warrants, Factor ETFs.

**Our Workaround: Long-Only + Defensive Positioning**
- Focus engine on **Long-Only Portfolio Optimization**.
- Use dynamic cash allocation strategies instead of pairs trading.
- Employ trend filters (200-day moving average) to shift weight to cash when markets turn bearish.
- Diversification across uncorrelated assets acts as natural hedging.

### 1.3 Constraint: No Bulk Historical Data from TR

**The Reality:**
- Trade Republic will not provide you bulk historical price data.

**Our Workaround: Yahoo Finance via `yfinance`**
- Use the free `yfinance` Python library to pull 1–5 years of daily historical data.
- TR routes orders through Lang & Schwarz (L&S) Exchange, which closely tracks Xetra (`.DE`).
- Restrict your asset universe to tickers that are liquid and available on TR.
- All prices are in EUR, matching what you see in the TR app.

---

## Part 2: Core System Architecture

### 2.1 Module 1: Data & Universe

**Purpose:** Define which assets to track and reliably fetch their historical data.

**Responsibilities:**
- Maintain a curated list of Trade Republic–available tickers.
- Automatically pull 1–5 years of daily closing prices, dividends, and corporate actions.
- Cache this data locally to avoid redundant API calls.
- Benchmark data: DAX, S&P 500, MSCI World for performance comparison.

**Key Decisions:**
- **Lookback Window:** 2-year rolling window (504 trading days) — long enough for statistical significance, short enough to drop irrelevant old data.
- **Primary Data Source:** Yahoo Finance (`yfinance` library).
- **Asset Universe:** Xetra/Frankfurt tickers (`.DE` suffix for EUR pricing).

### 2.2 Module 2: Statistical & Risk Analysis

**Purpose:** Understand individual asset behavior and how they interact.

#### 2.2.1 Descriptive Statistics (Individual Assets)

**Logarithmic Returns**
- Formula: $R_t = \ln(P_t / P_{t-1})$
- Why logs: Symmetric, time-additive, better for quantitative modeling than simple percentage returns.

**Annualized Volatility (Standard Deviation)**
- Formula: $\sigma_{annual} = \sigma_{daily} \cdot \sqrt{252}$
- Assumes 252 trading days per year.
- Represents baseline risk for each asset.

**Skewness & Kurtosis**
- **Skewness:** Indicates if returns lean toward negative surprises (left-skewed, bad) or positive surprises (right-skewed, good).
- **Kurtosis:** Measures "fat tails"—probability of extreme events like market crashes.
  - Normal distribution: kurtosis = 3
  - Higher kurtosis = higher risk of extreme moves

#### 2.2.2 Bivariate & Multivariate Analysis (Asset Interactions)

**Covariance Matrix**
- A grid showing directional relationships between every pair of assets.
- Raw measurement of how assets move together.

**Pearson Correlation Coefficient (ρ)**
- Formula: $\rho_{x,y} = \frac{Cov(x,y)}{\sigma_x \sigma_y}$
- Range: -1 to 1
  - ρ = 1: Move exactly together (bad for diversification)
  - ρ = -1: Move in opposite directions (ideal hedging)
  - ρ = 0: Uncorrelated (good for diversification)

**Beta (β) vs Benchmark**
- Formula: Linear regression of asset returns against benchmark (DAX or MSCI World).
- Interpretation:
  - β = 1.0: Asset moves exactly with the market
  - β = 1.2: Asset is 20% more volatile than the market (aggressive)
  - β = 0.8: Asset is 20% less volatile than the market (defensive)

#### 2.2.3 Risk Metrics (Downside Protection)

**Maximum Drawdown (MDD)**
- Definition: Largest percentage drop from all-time high to lowest trough.
- Your "pain threshold" metric.
- Example: If portfolio hit €100, dropped to €75, then recovered to €90, MDD = -25%.

**Value at Risk (VaR)**
- Definition: Statistical estimate of maximum loss at a confidence level.
- Example: 95% daily VaR of €50 means you're 95% confident you won't lose more than €50 in one day.
- Calculation: Quantile-based (e.g., 5th percentile of daily returns).

**Conditional VaR (Expected Shortfall / CVaR)**
- Definition: If you breach your VaR threshold, what is the *expected* loss beyond that?
- Answers: *"In the 5% of worst days, how much am I actually losing?"*

---

### 2.3 Module 3: The Portfolio Optimizer (The "Brain")

**Purpose:** Calculate optimal asset weights to achieve target return/risk balance.

#### 2.3.1 Modern Portfolio Theory (MPT) Foundation

**Expected Portfolio Return:**
- Formula: $R_p = w^T r$ (weighted sum of expected returns)
- $w$ = vector of asset weights
- $r$ = vector of expected returns

**Portfolio Variance (Risk):**
- Formula: $\sigma_p^2 = w^T \Sigma w$
- $\Sigma$ = covariance matrix
- Key insight: Portfolio risk is NOT the average of individual risks. It heavily depends on correlations.

**Efficient Frontier:**
- The curve of all optimal portfolios.
- Each point on the frontier maximizes return for a given risk level (or minimizes risk for a given return).
- Generated by running thousands of random simulations with different weight combinations.

#### 2.3.2 Optimization Objectives

**Option A: Maximize Sharpe Ratio (Balanced)**
- Formula: $Sharpe = \frac{R_p - R_f}{\sigma_p}$
- $R_p$ = portfolio expected return
- $R_f$ = risk-free rate (2.0% TR cash rate)
- $\sigma_p$ = portfolio standard deviation
- Metric: Return per unit of risk. Industry standard.

**Option B: Minimum Variance (Defensive)**
- Minimize $\sigma_p$ subject to all constraints.
- Produces the portfolio with the lowest possible volatility.
- Best for capital preservation.

**Option C: Maximum Return (Aggressive)**
- Maximize $R_p$ subject to all constraints.
- Pushes limits on highest-momentum assets.
- Best for growth-focused investors.

#### 2.3.3 Constraints for the Optimizer

- **Maximum Single Asset Weight:** 20%-25% (anti-YOLO rule: prevents corner solutions).
- **Minimum Weight:** 0% (can fully exit an asset if math demands).
- **Cash Allocation:** Allow 0%-100% cash to give algorithm defensive flexibility.
- **Total Weights:** Sum to exactly 100%.

---

### 2.4 Module 4: Trading Rules & Signals

**Purpose:** Translate optimization output into executable trade instructions.

#### 2.4.1 Rebalancing Logic: Time + Threshold

**The Problem:**
- Pure time-based (rebalance every Friday) causes excessive fees.
- Pure threshold-based (rebalance if any asset drifts 5%) might never trigger.

**The Solution: Opportunistic Rebalancing**
- **Time Check:** Run the engine on fixed days (e.g., 1st and 3rd Friday of each month).
- **Threshold Check:** Only execute if any asset has drifted more than **5%** from its target weight.
- **Example:**
  - Apple target: 20%
  - Current weight: 23%
  - Drift: 3% → **No action** (below 5% threshold)
  - Current weight: 26%
  - Drift: 6% → **Execute rebalance** (threshold breached)

#### 2.4.2 Stop-Loss Strategy: Trend Filters (Not Hard Stops)

**Why Hard Stops Fail:**
- Traditional stop-loss (e.g., "sell if down 10%") causes whipsawing.
- You exit at the market bottom, then re-enter days later at higher prices.
- Kills long-term strategy profitability.

**Better: Regime Filter (200-Day Moving Average)**
- Calculate the 200-day simple moving average for each asset.
- If current price < 200-day MA: Asset in "Bear Regime" → set target weight to 0%.
- If current price > 200-day MA: Asset in "Bull Regime" → use normal optimization.
- Systematic, emotionless, avoids daily noise.

#### 2.4.3 Capital Allocation & Position Sizing

**Sharpe-Based Allocation:**
- Use the optimized weights directly as dollar amounts.
- Example: If optimization says Apple should be 20% of €100 → buy €20 of Apple.

**Kelly Criterion (Half-Kelly / Quarter-Kelly):**
- Formula tells you exactly what % of capital to allocate based on your win rate and payoff ratio.
- Full Kelly is often too aggressive → use Half-Kelly or Quarter-Kelly for safety.
- Implementation: Calculate separately for each asset based on historical trade-by-trade performance.

---

## Part 3: Advanced KPIs for Practical Management

### 3.1 Risk-Adjusted Return Metrics

**Sharpe Ratio** (Industry Standard)
- Formula: $S = \frac{E[R_p] - R_f}{\sigma_p}$
- Interpretation: How much excess return per unit of total risk?
- Benchmark: > 1.0 is considered good.

**Sortino Ratio** (Downside-Focused)
- Like Sharpe, but only penalizes downside volatility (ignores upside swings as positive).
- More practical for real investors who care more about losses than gains.

**Calmar Ratio** (Return per Pain)
- Formula: $Calmar = \frac{\text{Annualized Return}}{\text{Maximum Drawdown}}$
- Practical for retail investors asking: *"How much gain per unit of worst-case pain?"*
- Example: 12% annualized return / 30% max drawdown = Calmar ratio of 0.4.

**Information Ratio (Beating the Benchmark)**
- Formula: $IR = \frac{R_p - R_b}{\sigma_{Active}}$
- $R_p$ = your portfolio return
- $R_b$ = benchmark return (e.g., MSCI World)
- $\sigma_{Active}$ = tracking error
- Interpretation: How much excess return per unit of active risk taken?

### 3.2 Strategy Health & Execution KPIs

**Profit Factor** (Ultimate "Bullshit Filter")
- Formula: $Profit\ Factor = \frac{\sum \text{Gross Profits}}{\sum |\text{Gross Losses}|}$
- Rule of thumb: < 1.5 = strategy too fragile to trade.
- Filters out false positives in backtest.

**Win Rate vs Risk/Reward Ratio**
- 40% win rate is fine if average winners are +15% and average losers are -5%.
- Calculated dynamically: engine must ensure current stop-loss and take-profit rules maintain this ratio.

**Ulcer Index** (Depth + Duration of Pain)
- Measures not just *how deep* a drawdown is, but *how long* you stay underwater.
- More psychologically relevant than maximum drawdown alone.
- Prevents panic-selling during protracted bear markets.

### 3.3 Dynamic Regimes & Momentum

**Rolling Correlation (Dynamic, Not Static)**
- Recalculate correlation matrix every 30–60 days instead of once per year.
- In normal times: correlations may be 0.3–0.5.
- In market crashes: correlations spike to 0.8–1.0 (everything falls together).
- Engine uses this to detect loss of diversification and shift to defensive mode.

**MACD (Moving Average Convergence Divergence)**
- Not for day-trading, but as an **entry filter**.
- Used to avoid buying stocks at overbought peaks.
- Example rule: Don't execute a buy signal for SAP if MACD is at a 3-month high.

**RSI (Relative Strength Index, 14-day)**
- Another momentum indicator for entry filtering.
- RSI > 80 = overbought (consider reducing new buy orders).
- RSI < 20 = oversold (consider adding to positions).

### 3.4 What We Intentionally Skip (Anti-Ridiculousness)

**Black-Scholes Options Pricing**
- You're not writing complex derivatives contracts.
- Overkill for a long-only equity portfolio.

**High-Frequency Slippage Models**
- TR manual execution = no microsecond-level precision needed.
- Simple spread estimates suffice.

**GARCH Volatility Forecasting**
- Computationally heavy and overkill for weekly/monthly rebalancing.
- Simple rolling standard deviation captures what we need.

---

## Part 4: Visualization & Dashboard Architecture

### 4.1 The "Glance" View (Overall Performance)

**Cumulative Equity Curve (Logarithmic Scale)**
- Line chart showing portfolio growth over time.
- Logarithmic scale: €10→€20 jump visually equals €100→€200 jump (both 100% growth).
- Overlay benchmark (MSCI World, DAX) for direct comparison.
- Color code: portfolio line in black, benchmark in blue.

**Monthly Returns Heatmap**
- Calendar-style grid: rows = years, columns = months.
- Green cells = positive months, Red cells = negative months.
- Instantly visualize seasonality and consistency.
- Identify patterns (e.g., "always strong in November").

### 4.2 The "Sanity Check" View (Risk & Drawdown)

**Underwater Plot (Drawdown Area Chart)**
- Top line: zero (all-time portfolio high).
- Red shaded area below: how far underwater you are at each point.
- Visual representation of psychological "pain."
- Shows duration of drawdowns (not just depth).

**Rolling Volatility Line Chart**
- 30-day or 60-day rolling standard deviation.
- Spikes indicate market turmoil.
- Alert trigger: if rolling vol spikes 50%, consider shifting to cash.

**Asset Correlation Heatmap**
- Grid: rows = assets, columns = assets.
- Dark blue = high positive correlation (move together).
- Dark red = negative correlation (move oppositely).
- Warning: if entire board turns blue, you've lost diversification.

### 4.3 The "Engine" View (System Mechanics)

**Efficient Frontier Scatter Plot**
- X-axis: Portfolio Standard Deviation (Risk)
- Y-axis: Expected Return
- Grey dots: thousands of random portfolio combinations.
- Curved line bounding the top: the Efficient Frontier.
- Bright star: your current chosen portfolio.

**Dynamic Asset Allocation (Stacked Area Chart)**
- Y-axis: 100% of capital.
- Colored bands for each asset (Apple = teal, SAP = mustard, Cash = grey).
- Over time: see how algorithm rebalances and shifts to cash in downturns.

**Current Weights (Donut Chart)**
- Clean breakdown of today's exact allocation.
- Pull this chart up before opening TR app to execute trades.

### 4.4 KPI Scorecards (Dashboard Top)

**Big, Bold Numbers:**
- **Total Portfolio Value:** €X,XXX (updated daily).
- **Total Profit/Loss:** €X,XXX (+XX%).
- **Sharpe Ratio:** X.XX (health score; color-coded: green if > 1.0, red if < 0.5).
- **Maximum Drawdown:** -XX%.
- **Win Rate:** XX%.
- **Next Rebalance Date:** DD/MM/YYYY.

---

## Part 5: User Interface & Interaction Design

### 5.1 Design Philosophy

**Aesthetic:**
- Light mode (white/off-white backgrounds).
- Strong, continuous black outlines around data cards (Ligne Claire inspired).
- Flat, vivid colors (no gradients): crimson, teal, mustard yellow.
- Subtle dotted/grainy background texture for character without sacrificing readability.

**Goal:** Clean, functional, instantly readable. Anyone peeking over your shoulder understands it at a glance.

### 5.2 Screen 1: The "Command Center" (Dashboard)

**Top Row: Scoreboard Cards (3 Cards)**
- Card 1: Portfolio Value + Cash Balance
- Card 2: Total PnL (€ and %)
- Card 3: Sharpe Ratio + Health Status
- Each with a `?` tooltip explaining the metric in plain English.

**Center: The Action Board (Prominent Card)**
- Bordered prominently; vivid background color (yellow or green).
- **Output Text:** Either "No action required this week. All assets within 5% drift threshold." OR "Rebalance Required: Sell €30 of AAPL, Buy €30 of SAP."
- **Why Explanation Tooltip:** "Apple grew too fast and now makes up 28% of your portfolio, breaching the 25% safety limit. We're locking in profits."

**Bottom: Charts Section**
- **Left:** Current Weights Donut Chart.
- **Right:** Equity vs. Benchmark Line Chart (black = your portfolio, blue = MSCI World ETF).
- Below both: Underwater Plot (Drawdown Area Chart).

**Secondary Deep Dive Tab:**
- Correlation Heatmap (doesn't need to be on main dashboard).
- Efficient Frontier Scatter Plot.
- Rolling Volatility Chart.
- Detailed performance metrics.

### 5.3 Screen 2: The "Ledger" (Input & Portfolio Management)

**Top Left: Transaction Entry Form**
- Dropdowns: `Action` (Deposit, Buy, Sell, Dividend).
- Dropdowns: `Ticker` (from curated universe).
- Input: `Shares`, `Price per Share`.
- Button: Submit (flat color, prominent).
- Tooltip: "Log every trade you make in the TR app here to keep the engine synced."

**Right/Center: Current Holdings Table**
- Columns: Asset Name, Quantity, Avg Buy Price, Current Price, Unrealized PnL (€ and %), Trend Badge (UP/DOWN based on 200-day MA).
- Alternating row colors (white and light grey) to prevent eye skipping.
- Sortable columns for quick reference.

**Top: Sub-Portfolio Toggle**
- Chunky tabs: "Quality Equities," "Crypto Satellite," "Safe Havens."
- Allows you to view each universe independently without data clutter.

### 5.4 Educational "Dictionary" Panel (Sidebar)

**Purpose:** Always-visible definitions of quant terms.

**Examples:**
- *Volatility:* Measures how wildly a stock's price swings. Higher = riskier.
- *Maximum Drawdown:* The worst peak-to-trough loss your portfolio has experienced.
- *Efficient Frontier:* The set of portfolios offering the highest return for each level of risk.
- *Rebalancing:* Buying/selling to return your portfolio to its target weights.
- *Trend Filter:* A rule using the 200-day moving average to avoid holding losing assets.

---

## Part 6: How the Math Maps to the Visual Interface

### 6.1 Scoreboard Card 1 → Portfolio Variance Calculations

- Raw KPI: Portfolio variance $\sigma_p^2 = w^T \Sigma w$ calculated from covariance matrix.
- Visual Simplification: "Your portfolio is €X,XXX with €Y in cash."
- Hidden complexity: Diversification benefit is already baked into the target weights.

### 6.2 Scoreboard Card 3 → Sharpe Ratio + Color Coding

- Raw KPI: Sharpe ratio $\frac{R_p - R_f}{\sigma_p}$.
- Visual output: "Sharpe Ratio: 1.23" displayed in green (> 1.0 = good).
- If volatility spikes without return increase → Sharpe drops → card turns red warning sign.

### 6.3 Action Board → MPT Optimizer + Rebalancing Logic

- Raw computation: Efficient Frontier calculation, comparison of current weights to optimal weights, threshold check (5% drift), fee logic check (€25 minimum trade).
- Visual output: Single instruction sentence.
- Entirely hides complexity while preserving decision clarity.

### 6.4 Current Weights Donut → Dynamic Asset Allocation

- Raw KPI: Dynamic portfolio weights from optimization.
- Visual: Each asset colored distinctly; size is its current weight.
- Alerts: If one asset dominates (> 25%), its color brightens or badge appears.

### 6.5 Equity vs Benchmark Line → Information Ratio

- Raw KPI: Cumulative log returns of your portfolio vs benchmark; tracking error $\sigma_{Active}$.
- Visual: Two lines over time; if your line (black) stays above benchmark (blue), your active management is working.

---

## Part 7: Data Pipeline & Ledger Architecture

### 7.1 The Transaction Ledger (Your Input)

**Format:** CSV or Excel (`transactions.xlsx`)

**Columns:**
- `Date` (YYYY-MM-DD)
- `Action` (Deposit | Buy | Sell | Dividend | Fee)
- `Ticker` (e.g., APC.DE, SAP.DE)
- `Quantity` (number of shares; can be fractional for TR)
- `Price per Share` (€)
- `Total Value` (€)
- `Notes` (optional; e.g., "Using Sparplan")

**What This Does:**
- You log every manual trade from TR app.
- Engine reads this file to calculate your current holdings and cost basis.
- Cost basis used for PnL tracking.

### 7.2 The Backend Data Pipeline

**Steps (Run Weekly):**
1. Read `transactions.xlsx` to determine current positions.
2. Fetch latest market prices from `yfinance` for all tickers.
3. Calculate log returns, volatility, correlation matrix (2-year rolling window).
4. Run MPT optimization (3 scenarios: max Sharpe, min variance, max return).
5. Compare optimal weights to current weights; check 5% threshold.
6. Apply fee logic: if trade size < €25, suppress signal.
7. Output CSV/JSON with latest metrics, recommended actions, and all KPIs.
8. Streamlit frontend reads this output and renders dashboard.

### 7.3 Output Files (Produced by Backend)

**File: `portfolio_metrics.json`**
- Current holdings, unrealized PnL, portfolio value.
- Latest Sharpe, Calmar, Information Ratio.
- Maximum Drawdown, rolling volatility, correlation matrix snapshot.

**File: `rebalance_action.json`**
- Recommended trades (if any).
- Reasoning for each trade.
- Next rebalance date.

**File: `efficient_frontier.csv`**
- Scatter of thousands of simulated portfolios (Risk, Return pairs).
- Your current portfolio coordinates.
- The three optimal scenarios (max Sharpe, min variance, max return).

---

## Part 8: Operational Workflow

### Weekly/Monthly Cycle (Every 1st & 3rd Friday)

1. **You:** Log into your computer Friday evening.
2. **You:** Run the Python backend: `python main.py`
3. **Backend:** Fetches latest market data, calculates all metrics, checks rebalance conditions.
4. **Dashboard:** Updates with new charts, KPIs, and trade instructions.
5. **You:** Look at the "Action Board" card.
   - If it says "No action required," close the app.
   - If it says "Sell €30 of AAPL, buy €30 of SAP," note the instruction.
6. **You:** Open Trade Republic app on your phone.
7. **You:** Execute the trades exactly as instructed.
8. **You:** Open `transactions.xlsx` and log the trades (Date, Action, Ticker, Quantity, Price).
9. **Next Week:** Backend reads the updated ledger; everything stays synced.

### Quarterly Deep Dive (Every 3 Months)

- Review rolling correlation heatmap: has diversification held up?
- Check Information Ratio: are you actually beating the MSCI World ETF?
- Review profit factor and win rate of the algo's trade signals.
- Adjust universe if any asset becomes illiquid on TR.

---

## Part 9: The Asset Universe

### Universe A: High-Quality Equities (Primary Portfolio)

**Purpose:** Core holdings for long-term growth. Highly liquid, mission-critical (if they drop, you understand why from financial news).

**Tickers (.DE for EUR pricing):**
- **Apple:** `APC.DE`
- **Microsoft:** `MSF.DE`
- **SAP:** `SAP.DE`
- **Allianz:** `ALV.DE`
- **LVMH:** `MOH.DE`
- **MSCI World ETF (iShares Core):** `EUNL.DE` (anchor asset for broad diversification)

**Optimizer:** Single mean-variance optimizer across all 6 assets.
**Max Weight:** 25% per asset (except EUNL.DE can be 35% as anchor).

### Universe B: Crypto Satellite (Small Allocation)

**Assets:** Bitcoin, Ethereum, Solana.
**Allocation:** Max 10% of total portfolio.
**Reason:** Separate optimizer because crypto volatility overwhelms equity optimization. Treat as uncorrelated tail hedge.
**Rebalancing:** Monthly, independent of Universe A timing.

### Universe C: Macro / Safe Haven

**Assets:** Gold ETCs (Xetra-Gold), Government Bond ETFs.
**Allocation:** Max 15% of total portfolio.
**Purpose:** Defensive allocation when equity regimes turn bearish.
**Trigger:** Shifts to this universe when 200-day MA filters trigger "Bear Regime."

---

## Part 10: Risk & Fee Model

### 10.1 Trade Republic Fee Drag on a €100 Portfolio

**The Reality:**
- TR charges €1 per transaction (market/limit order).
- On a €100 portfolio, a €1 fee is 1% of capital.
- On an €8 trade, a €1 fee is 12.5% cost.

**Our Mitigation Strategies:**

**Strategy 1: Minimum Trade Size**
- Hard rule: Do NOT execute a trade unless it's worth ≥ €25.
- If optimizer says "Sell €8 of Apple," engine swallows signal and outputs "HOLD."
- When portfolio exceeds €5,000, adjust minimum trade size to 2% of account value.

**Strategy 2: Savings Plans (Sparpläne)**
- TR offers free recurring investments through Sparpläne.
- Recommend this for regular monthly deposits (0% fee).
- Manual rebalancing uses paid transactions only when drift threshold is breached.

**Strategy 3: Documentation & Scaling Caveat**
- In the Streamlit app, include a "Capital Scaling" documentation tab.
- Clear warning: *"This engine is designed for €100–€5,000 portfolios with €25 minimum trades. When equity exceeds €5,000, adjust the Minimum Trade Size variable from €25 to 2% of total account value to maintain mathematical soundness. Failure to scale will result in excessive fee drag and strategy degradation."*
- Use stark black outlines and vivid red warning boxes to make it impossible to miss.

### 10.2 Risk-Free Rate (TR Cash Rate)

- Current TR rate: **2.00% p.a.** (calculated daily, paid monthly).
- This rate is hard-coded as `risk_free_rate = 0.02` in the optimizer.
- Impact: When calculating Sharpe Ratio, optimizer knows cash is *guaranteed* 2%. If equities are extremely volatile and only offer 2.5% expected return, optimizer allocates more to cash.

---

## Part 11: Suggested File Structure

```
portfolio/
├── README.md (Project overview)
├── data/
│   ├── historical_prices.csv (cached yfinance data)
│   ├── transactions.xlsx (YOUR INPUT: manual trade log)
│   └── portfolio_metrics.json (generated by backend)
├── src/
│   ├── __init__.py
│   ├── main.py (entry point; orchestrates entire workflow)
│   ├── universe.py (defines asset universe, tickers, constraints)
│   ├── data.py (yfinance integration, caching, data validation)
│   ├── metrics.py (volatility, correlation, skewness, kurtosis, beta)
│   ├── optimizer.py (MPT efficient frontier, weight optimization)
│   ├── signals.py (rebalancing logic, trend filters, trade generation)
│   ├── performance.py (Sharpe, Calmar, Information Ratio, profit factor)
│   ├── portfolio.py (ledger reading, current holdings, PnL calculation)
│   └── config.py (constants: min trade size, max weight, lookback window, risk-free rate)
├── app/
│   ├── streamlit_dashboard.py (main Streamlit app)
│   ├── components/
│   │   ├── scoreboard.py
│   │   ├── action_board.py
│   │   ├── charts.py
│   │   └── ledger_entry.py
│   └── styles.css (custom Streamlit styling)
├── notebooks/
│   ├── 01_exploratory_analysis.ipynb (test correlation, volatility)
│   ├── 02_optimization_testing.ipynb (test efficient frontier)
│   └── 03_backtest.ipynb (historical performance if desired)
├── reports/
│   ├── efficient_frontier.csv (exported scatter plot data)
│   └── monthly_summary.txt (generated reports)
└── requirements.txt (pandas, numpy, scipy, yfinance, streamlit, plotly)
```

---

## Part 12: MVP Implementation Roadmap

### Phase 1: Core Data Pipeline
1. Implement `universe.py`: Define tickers, constraints.
2. Implement `data.py`: Fetch from yfinance, cache locally.
3. Test: Pull 2 years of data for the 6 equities; verify no gaps.

### Phase 2: Statistical Foundation
1. Implement `metrics.py`: Log returns, volatility, correlation matrix, skewness, kurtosis, beta.
2. Test: Generate correlation heatmap for visual inspection; validate against Bloomberg/Yahoo directly.

### Phase 3: Optimization Engine
1. Implement `optimizer.py`: Efficient frontier (random search or scipy.optimize).
2. Generate 3 scenarios: max Sharpe, min variance, max return.
3. Test: Verify weights sum to 100%, respect max 25% constraint, always have cash.

### Phase 4: Trading Rules
1. Implement `signals.py`: Compare current weights to optimized, check 5% threshold, apply €25 minimum trade rule.
2. Test: Manually feed some portfolio scenarios; verify correct trade decisions.

### Phase 5: Performance KPIs
1. Implement `performance.py`: Sharpe, Calmar, Information Ratio, profit factor, win rate, Ulcer Index.
2. Test: Calculate on historical data; verify against known reference implementations.

### Phase 6: User Interface (Streamlit)
1. Build basic 2-screen dashboard (Command Center + Ledger).
2. Integrate all backend outputs into Streamlit widgets.
3. Add styling (light mode, black outlines, vivid colors).
4. Test: Walk through a complete weekly cycle.

### Phase 7: Polish & Documentation
1. Add tooltips and "Dictionary" panel.
2. Implement Capital Scaling warning.
3. Write user manual.
4. Identify and fix edge cases.

---

## Part 13: Technical Decisions & Justifications

### Why Python?
- Mature data science ecosystem (pandas, numpy, scipy, scikit-learn).
- Streamlit for rapid web app prototyping without deep web dev knowledge.
- Plotly for interactive, publication-quality charts.
- Easy to extend and debug.

### Why Streamlit Over Flask/Django?
- Minimal boilerplate; focus on logic, not infrastructure.
- Hot reloading: change code, refresh browser, see results immediately.
- Built-in state management for form inputs.
- Native Plotly integration.

### Why MongoDB/SQLite Over Excel?
- Durability and concurrent access (though you're the only user).
- Scalability: easily add more universes or metrics.
- Transactions integrity: safer than file locking issues with Excel.
- Can be queried programmatically.

### Why 2-Year Lookback Window?
- Short enough to forget old market regimes (2008 crash, COVID crash aren't dragging current calc).
- Long enough to see at least 2–3 complete market cycles (bull, sideways, bear).
- Statistical sweet spot for covariance matrix: enough data to be significant, not so much that we overfit to historical patterns.

---

## Part 14: What Success Looks Like

### Month 1 (Setup Phase)
- [x] Backend running without errors.
- [x] Streamlit dashboard displaying live data.
- [x] Execute first manual rebalance based on engine output.

### Month 3 (Operational)
- [x] Weekly workflow automated and repeatable.
- [x] Transaction ledger accurate and synced with backend.
- [x] Action Board generating sensible trade instructions.

### Month 6 (Validation)
- [x] Engine has survived at least one market setback without major losses.
- [x] Your Information Ratio positive (beating MSCI World ETF).
- [x] Win Rate > 40%; Profit Factor > 1.5.

### Month 12 (Mature)
- [x] €100 has grown (or shrunk, but for *understood* reasons).
- [x] Portfolio volatility contained and predictable.
- [x] Scalable: confidence to allocate more capital.

---

## Part 15: Knowledge Base & References

### Key Formulas Quick Reference

| Metric | Formula | Purpose |
|--------|---------|---------|
| Log Return | $R_t = \ln(P_t / P_{t-1})$ | Time-additive, symmetric return |
| Annualized Vol | $\sigma = \sigma_{daily} \times \sqrt{252}$ | Risk measurement |
| Correlation | $\rho = \frac{Cov(x,y)}{\sigma_x \sigma_y}$ | Asset relationship |
| Portfolio Return | $R_p = w^T r$ | Weighted expected return |
| Portfolio Variance | $\sigma_p^2 = w^T \Sigma w$ | Diversification effect |
| Sharpe Ratio | $\frac{R_p - R_f}{\sigma_p}$ | Return per unit risk |
| Calmar Ratio | $\frac{R_p}{MDD}$ | Return per unit of pain |
| Information Ratio | $\frac{R_p - R_b}{\sigma_{Active}}$ | Active alpha per unit of active risk |
| Profit Factor | $\frac{\sum Profits}{\|\sum Losses\|}$ | Trade system robustness |

### Python Libraries Needed

- **Data:** `pandas`, `numpy`
- **Fetching:** `yfinance`
- **Optimization:** `scipy.optimize`
- **Stats:** `scipy.stats`
- **Visualization:** `plotly`, `matplotlib`
- **Web App:** `streamlit`
- **Utility:** `python-dotenv`, `requests`

---

## Part 16: Final Checklist Before Build

- [ ] Asset universe locked (6 equities + benchmarks defined)
- [ ] Minimum trade size agreed (€25 for €100 portfolio)
- [ ] Max single-asset weight agreed (25%)
- [ ] Rebalancing frequency agreed (1st & 3rd Friday)
- [ ] Drift threshold agreed (5%)
- [ ] Risk-free rate set (2.00%)
- [ ] Lookback window set (2 years)
- [ ] UI aesthetic agreed (light mode, black outlines, vivid colors)
- [ ] Trade execution workflow documented (manual app entry)
- [ ] Ledger format finalized (`transactions.xlsx` columns)
- [ ] File structure created locally
- [ ] First PR draft reviewed

**Status:** Ready to begin Phase 1 implementation.

---

> This document is the complete, production-ready blueprint. It covers all mathematical detail, practical constraints, user experience, and technical architecture. Use this to guide development week by week.
