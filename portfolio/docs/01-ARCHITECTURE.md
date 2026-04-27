# System Architecture & Codebase Directory

**Document Purpose:** This file maps out the directory structure, file responsibilities, and data flow of the Trade Republic Quantitative Engine.

---

## 1. Directory Tree

```
portfolio/
│
├── README.md                   # Master documentation map (START HERE)
│
├── docs/                       # System Documentation
│   ├── 00-SYSTEM-OVERVIEW.md   # What does this do? (plain English)
│   ├── 01-ARCHITECTURE.md      # How is it structured? (this file)
│   ├── 02-STRATEGY-RULES.md    # What are the exact rules & math?
│   ├── 03-TUNING-LOG.md        # Maintenance & change history
│   └── REFERENCE-FORMULAS.md   # Quick math reference
│
├── src/                        # Python Source Code (empty during planning)
│   ├── __init__.py             # Package marker
│   ├── config.py               # Constants (Tickers, Risk-Free Rate, Minimum Trade Size)
│   ├── data_loader.py          # Functions to read ledger.csv and fetch yfinance data
│   ├── math_optimizer.py       # Core Quant Engine (Covariance, Volatility, MPT)
│   ├── rules_engine.py         # Applies the asymmetric drift and dynamic minimum trade constraints.
│   ├── performance.py          # KPI calculations (Sharpe, Calmar, etc)
│   └── app.py                  # Streamlit Frontend (The Visual Dashboard)
│
├── data/                       # Local data storage
│   ├── ledger.csv              # USER INPUT: Manual log of Trade Republic transactions
│   ├── historical_prices.csv   # CACHE: Downloaded yfinance data to minimize API calls
│   └── engine_state.json       # CACHE: Last calculated target weights and KPIs
│
├── notebooks/                  # Jupyter Notebooks (exploratory analysis)
│   ├── 01_data_exploration.ipynb
│   ├── 02_correlation_analysis.ipynb
│   └── 03_backtest_simulation.ipynb
│
├── reports/                    # Generated outputs
│   ├── efficient_frontier.csv  # Scatter plot of simulated portfolios
│   └── monthly_summary.txt     # Human-readable report
│
├── requirements.txt            # Python dependencies (pandas, numpy, etc)
├── run_engine.bat/.sh          # One-click launcher script
└── .gitignore                  # Git exclusions
```

---

## 2. Component Descriptions

### The `data/` Directory (Local Storage)

**`ledger.csv`** — The single source of truth for your actual portfolio state.
- You manually update this file after executing trades on Trade Republic.
- Columns: `Date`, `Action`, `Ticker`, `Quantity`, `Price`, `Total`, `Notes`
- Engine reads this to calculate:
  - Current holdings (how many shares of each asset)
  - Cash balance (capital not yet invested)
  - Cost basis (for profit/loss calculation)

**`historical_prices.csv`** — Local cache of daily closing prices.
- Downloaded from Yahoo Finance via `yfinance` library.
- Updated daily to prevent rate-limiting.
- Format: Dates as rows, tickers as columns (one row per trading day).
- Covers 2-year rolling window (504 trading days).
- Sourced from Xetra/Frankfurt to match TR prices exactly (`.DE` suffixes).

**`engine_state.json`** — Snapshot of the last optimization run.
- Saves the output of the mathematical optimizer so dashboard loads instantly.
- Contains: optimal weights, current KPIs, rebalance recommendations, next rebalance date.
- Updated weekly when engine runs.
- Allows dashboard to work offline (doesn't recalculate 2 years of data on every refresh).

### The `src/` Directory (Core Logic)

**`config.py`** — The control panel. Hard-coded constants.

Contains:
- `ASSET_UNIVERSE`: List of tickers (APC.DE, MSF.DE, SAP.DE, etc.)
- `LOOKBACK_DAYS`: 504 (2-year rolling window)
- `MAX_WEIGHT`: 0.25 (25% maximum per asset)
- `MIN_TRADE_EUR_FLOOR`: 25.00 (Hard floor for minimum trade)
- `FEE_DRAG_TARGET`: 0.005 (0.5% dynamic scaling factor for min trades)
- `RISK_FREE_RATE`: 0.02 (2% TR cash yield)
- `REBALANCE_FREQUENCY`: [1, 3] (1st and 3rd Friday of month)
- `DRIFT_THRESHOLD_BUY`: 0.05 (5% drift tolerance for buying)
- `DRIFT_THRESHOLD_SELL`: 0.07 (7% drift tolerance for selling to defer taxes)
- `TREND_FILTER_MA_PERIODS`: 200 (200-day moving average)

**Any parameter change must be logged in `TUNING-LOG.md` with mathematical rationale.**

---

**`data_loader.py`** — All I/O operations and data assembly.

Responsibilities:
- **Read ledger:** Parse `ledger.csv` to calculate current holdings + cash balance.
- **Fetch data:** Pull missing historical daily prices from Yahoo Finance (strictly using `Adj Close`).
- **Validate (The Sanity Gate):** Check for data gaps, NaN values, and flag any daily price moves > ±15% to prevent stock-split panic selling.

Key Functions:
- `load_ledger(filepath)` → Current portfolio state (holdings dict, cash float)
- `fetch_historical(tickers, lookback_days)` → Raw price data from yfinance
- `calculate_log_returns(prices)` → Time series of daily log returns
- `validate_data(df)` → Check for gaps, NaN, missing dates

---

**`math_optimizer.py`** — The heaviest file. Core quantitative engine.

Responsibilities:
- **Descriptive stats:** Volatility, skewness, kurtosis per asset.
- **Interaction:** Correlation matrix, covariance matrix, beta.
- **Portfolio metrics:** Expected return, portfolio variance.
- **Optimization:** Find efficient frontier, maximize Sharpe ratio with constraints.
- **Risk metrics:** Maximum drawdown, VaR, CVaR, Ulcer Index.

Key Functions:
- `calculate_returns(prices)` → Log returns
- `calculate_correlation_matrix(returns)` → Pearson correlation
- `calculate_volatility(returns)` → Annualized standard deviation
- `calculate_beta(asset_returns, benchmark_returns)` → Beta vs benchmark
- `optimize_portfolio(expected_returns, cov_matrix, constraints)` → Optimal weights
- `calculate_efficient_frontier(expected_returns, cov_matrix, n_simulations=10000)` → Scatter plot data

---

**`rules_engine.py`** — The referee applying constraints.

Responsibilities:
- Take optimal weights from `math_optimizer.py`.
- Compare to current portfolio from `data_loader.py`.
- Apply constraints:
  - Asymmetric drift threshold (trade if drift < -5% to buy, or > +7% to sell)
  - Dynamic minimum trade size (ignore trades below MAX(€25, 0.5% of portfolio))
  - 200-day MA trend filter (set weight to 0% if price < 200-day MA)
- Output actionable signals: "Buy €30 of SAP, Sell €20 of AAPL" or "Hold, no action required."

Key Functions:
- `calculate_current_weights(holdings, total_value)` → Current portfolio allocation
- `calculate_drift(current_weights, target_weights)` → Absolute drift per asset
- `apply_trend_filter(prices, target_weights)` → Zero out assets below 200-day MA
- `generate_trade_signals(current_weights, optimal_weights, account_value)` → Exact buy/sell amounts in EUR
- `filter_by_minimum_trade_size(signals, min_trade)` → Remove trades < €25

---

**`performance.py`** — Calculate all KPIs for dashboard display.

Responsibilities:
- **Risk-adjusted returns:** Sharpe ratio, Sortino ratio, Calmar ratio.
- **Active management:** Information ratio vs benchmark.
- **Trade health:** Profit factor, win rate, risk/reward ratio.
- **Drawdown analysis:** Maximum drawdown, Ulcer Index.

Key Functions:
- `calculate_sharpe_ratio(returns, risk_free_rate)` → Sharpe ratio
- `calculate_calmar_ratio(returns, max_drawdown)` → Calmar ratio
- `calculate_information_ratio(portfolio_returns, benchmark_returns)` → IR vs benchmark
- `calculate_profit_factor(trade_pnl)` → Sum wins / Sum losses
- `calculate_max_drawdown(cumulative_returns)` → MDD metric
- `calculate_ulcer_index(cumulative_returns)` → Duration-weighted drawdown

---

**`app.py`** — Streamlit frontend. Presentation layer.

Responsibilities:
- Load `engine_state.json` for latest data.
- Build interactive dashboard with 2 screens:
  - **Command Center:** Scorecards, action board, charts
  - **Ledger:** Transaction entry form, holdings table
- Apply Ligne Claire aesthetic:
  - Thick black outlines around data cards
  - Flat, vivid colors (no gradients)
  - Off-white background with subtle dotted texture
- Render charts using Plotly:
  - Donut chart (current weights)
  - Line chart (equity vs benchmark)
  - Underwater plot (drawdown area)
  - Correlation heatmap
  - Efficient frontier scatter
- **Input Validation:** Enforce strict checks on the Ledger Entry form:
  - Block selling more shares than currently owned.
  - Block buying if total cost exceeds logged cash balance.
  - Include an "Undo Last Entry" button to easily fix manual typos without editing the CSV.

---

## 3. Data Flow: Execution Cycle

When the user runs the application (`python run_engine.py`), the system executes in this order:

### Step 1: Initialization
```
app.py starts
→ Streamlit renders dashboard shell
→ Triggers backend engine execution
```

### Step 2: State Assembly
```
data_loader.py reads ledger.csv
→ Calculates "Current Reality": 
   - How many shares of each asset do I own?
   - How much cash is uninvested?
   - What is my total portfolio value?
→ Returns: holdings_dict = {AAPL: 2.5, MSFT: 1.8, ...}, cash = €25
```

### Step 3: Market Data Update
```
data_loader.py checks historical_prices.csv
→ If outdated or missing data:
   → Fetch latest prices from yfinance for AAPL.DE, MSFT.DE, etc.
   → Validate no gaps
   → Write to historical_prices.csv
→ Calculate log returns from cached prices
```

### Step 4: Statistical Calculation
```
math_optimizer.py processes price history
→ Calculate correlation matrix (6×6 grid showing asset relationships)
→ Calculate volatility per asset
→ Calculate expected returns (historical average)
→ Result: mean_returns vector, cov_matrix
```

### Step 5: Optimization
```
math_optimizer.py runs scipy.optimize.minimize
→ Objective: Maximize Sharpe Ratio
→ Constraints: sum(w)=1, 0≤w_i≤0.25
→ Result: optimal_weights = [0.18, 0.20, 0.15, 0.12, 0.10, 0.25]
→ Also calculate: 3 scenarios (Max Sharpe, Min Variance, Max Return)
```

### Step 6: Reconciliation & Signal Generation
```text
rules_engine.py compares "Current Reality" to "Mathematical Ideal"
→ Current weights: [22%, 18%, 14%, 11%, 9%, 26%]
→ Optimal weights: [18%, 20%, 15%, 12%, 10%, 25%]
→ Drift per asset: [+4%, -2%, -1%, -1%, -1%, +1%]
→ Apply Asymmetric Thresholds: 
  - AAPL drift is +4% (Target is 18%). Sell threshold is +7%. → Ignore.
  - MSFT drift is -2% (Target is 20%). Buy threshold is -5%. → Ignore.
→ Apply trend filter: Check if AAPL is above 200-day MA? Yes → keep
→ Generate signal: "Hold. All drifts below asymmetric thresholds (5% Buy / 7% Sell)."
→ Save to engine_state.json
```

### Step 7: Visualization
```
app.py reads engine_state.json
→ Renders scoreboard cards:
   - Total value: €105.32
   - PnL: +€5.32 (+5%)
   - Sharpe: 1.23 ✅
→ Renders action board: "No action required"
→ Renders charts:
   - Donut (current weights)
   - Line (equity vs benchmark)
   - Underwater plot (drawdown history)
→ Renders holdings table from holdings_dict
→ User sees dashboard live
```

---

## 4. Data Schemas

### `ledger.csv` (Your Manual Input)

```
Date,Action,Ticker,Quantity,Price,Total,Notes
2026-03-01,Deposit,CASH,100.00,1.00,100.00,Initial deposit
2026-03-15,Buy,APC.DE,2.5,155.20,388.00,AAPL purchase
2026-03-15,Buy,SAP.DE,5.0,95.50,477.50,SAP purchase
2026-03-22,Sell,APC.DE,1.0,157.50,157.50,Rebalance
2026-03-22,Buy,EUNL.DE,3.0,50.20,150.60,MSCI World top-up
```

---

### `historical_prices.csv` (Cached Market Data)

```
Date,APC.DE,MSF.DE,SAP.DE,ALV.DE,MOH.DE,EUNL.DE
2024-03-25,150.32,410.15,95.20,92.30,750.50,48.20
2024-03-26,151.10,411.20,95.80,92.50,751.20,48.35
2024-03-27,150.85,410.80,95.50,92.10,750.80,48.10
...
2026-03-25,155.40,415.60,96.20,93.80,758.30,50.50
```

---

### `engine_state.json` (Last Optimization Output)

```json
{
  "last_run": "2026-03-25T20:15:30",
  "next_rebalance": "2026-04-07",
  "current_values": {
    "total_portfolio": 105.32,
    "cash": 15.00,
    "holdings": {
      "APC.DE": 23.50,
      "MSF.DE": 18.20,
      "SAP.DE": 17.50,
      "ALV.DE": 12.80,
      "MOH.DE": 10.20,
      "EUNL.DE": 8.10
    }
  },
  "optimal_weights": {
    "APC.DE": 0.18,
    "MSF.DE": 0.20,
    "SAP.DE": 0.15,
    "ALV.DE": 0.12,
    "MOH.DE": 0.10,
    "EUNL.DE": 0.25
  },
  "current_weights": {
    "APC.DE": 0.223,
    "MSF.DE": 0.173,
    "SAP.DE": 0.166,
    "ALV.DE": 0.122,
    "MOH.DE": 0.097,
    "EUNL.DE": 0.077,
    "CASH": 0.142
  },
  "kpis": {
    "sharpe_ratio": 1.23,
    "calmar_ratio": 0.85,
    "max_drawdown": -0.142,
    "information_ratio": 0.32,
    "profit_factor": 1.62
  },
  "action_signal": "No action required this week. All assets within asymmetric drift thresholds (5% Buy / 7% Sell).",
  "reason": "AAPL drift +4% (below 7% sell threshold); all other assets within tolerance."
}
```

---

## 5. Weekly Execution Checklist

**Friday 8 PM (Automation):**
- [ ] Run `python run_engine.py`
- [ ] Backend executes full pipeline automatically
- [ ] Dashboard opens in browser

**Friday 8:15 PM (Observation):**
- [ ] Check "Command Center" screen
- [ ] Read action board: "Hold" or "Rebalance required"
- [ ] Review KPI scorecards
- [ ] If changes needed, note the exact trades

**Saturday Morning (Manual Execution):**
- [ ] Open Trade Republic app
- [ ] Execute trades exactly as instructed (buy/sell amounts)
- [ ] Record exact execution prices

**Saturday Noon (Ledger Update):**
- [ ] Open `ledger.csv`
- [ ] Add rows for each trade executed
- [ ] Save file
- [ ] Close app

**Next Friday:**
- [ ] Repeat

---

> **The architecture ensures that all mathematical complexity is hidden behind a simple weekly workflow. Data flows in one direction: Current Reality → Math → Signals → Visualization. No backtracking without reason.**
