# ML / Deep Learning Stock Prediction — Jupyter Notebook Strategy

> **Status: TODO — Experimental research notebook. Not a production trading signal.**
> Always be suspicious of results. The goal is structured experimentation, not false confidence.

---

## Guiding Philosophy

- ML on financial data is hard. Expect ~50–55% directional accuracy as a realistic ceiling for most models. That is not useless — but it must be combined with position sizing and risk management to matter.
- A model that is right 53% of the time with good risk/reward is more valuable than one that is right 60% of the time but gives no signal on magnitude.
- The notebook is a **lab**, not an oracle. Every experiment must have a hypothesis, a baseline, and a clear verdict.
- Always be more suspicious when results look too good. Overfitting and data leakage are the two silent killers in financial ML.

---

## Notebook Architecture

### Folder Structure

```
/stock_ml_lab/
│
├── /data/
│   ├── /raw/                   # Never touched after download
│   ├── /processed/             # Cleaned, feature-engineered datasets
│   └── /manual/                # Hand-labeled data (divergence labels, laggard tags, notes)
│
├── /notebooks/
│   ├── 00_data_pipeline.ipynb       # Data fetching and cleaning only
│   ├── 01_eda.ipynb                 # Exploratory data analysis
│   ├── 02_feature_engineering.ipynb # All feature creation logic
│   ├── 03_baseline_models.ipynb     # Baselines — always run first
│   ├── 04_ml_models.ipynb           # Classical ML experiments
│   ├── 05_dl_models.ipynb           # Deep learning experiments
│   ├── 06_scenario_engine.ipynb     # Monte Carlo + scenario generation
│   ├── 07_ensemble.ipynb            # Multi-company ensemble and averaging
│   └── 08_evaluation.ipynb          # Final metrics, verdicts, comparison table
│
├── /models/
│   └── /saved/                 # Versioned saved model files with metadata
│
├── /results/
│   └── experiment_log.csv      # Every experiment logged: date, model, ticker, metrics
│
└── /utils/
    ├── data_loader.py
    ├── feature_builder.py
    ├── evaluator.py
    └── scenario_engine.py
```

**Critical rule:** Raw data is never modified. All transformations happen in code. This means you can always reproduce any result from scratch.

---

## Company Universe Selection

### Why Selection Matters

Averaging predictions across 10 correlated companies (e.g., 10 tech stocks) gives false confidence — their predictions will move together, and ensemble averaging adds no real diversity. The universe must be deliberately diversified.

### Target Universe: 10–12 Companies

Select across these dimensions:

| Dimension | Target |
|---|---|
| Sectors | Minimum 5 different GICS sectors |
| Market cap | Mix of large-cap and mid-cap |
| Geography | Primarily US, optionally 1–2 international ADRs |
| Volatility profile | Mix of high-beta and low-beta stocks |
| Data availability | Minimum 5 years of clean daily history |

### Suggested Starter Universe (Adjust As Needed)

| Ticker | Sector | Rationale |
|---|---|---|
| META | Communication Services | High data volume, well-covered |
| JPM | Financials | Macro sensitivity, rate exposure |
| XOM | Energy | Commodity-driven, different regime behavior |
| UNH | Healthcare | Defensive, low correlation to tech |
| TSLA | Consumer Discretionary | High volatility, sentiment-driven |
| MSFT | Technology | Anchor name, high data quality |
| CAT | Industrials | Cyclical, China/global trade exposure |
| AMZN | Consumer Discretionary / Tech | Dual exposure |
| GLD (ETF) | Commodities proxy | Crisis hedge behavior |
| BRK.B | Diversified | Warren Buffett factor, value anchor |

This gives genuine cross-sector diversity. Each company will get its own model. The ensemble only comes in at notebook 07.

---

## Data Sources and Pipeline

### Price and Volume Data (Auto)

- **Source:** `yfinance` Python library (free, reliable for daily OHLCV)
- **Frequency:** Daily OHLCV (Open, High, Low, Close, Volume, Adjusted Close)
- **History:** Minimum 5 years, ideally 10 years for DL models
- **Update cadence:** Weekly refresh, or triggered manually before experiments

### Fundamental Data (Semi-Auto)

- **Source:** `yfinance` has basic fundamentals. For richer data: `financedatabase`, `simfin`, or manual CSV exports from Macrotrends
- **What to pull:** P/E, P/B, EV/EBITDA, revenue growth YoY, gross margin, operating margin, debt/equity, free cash flow
- **Frequency:** Quarterly (aligned to earnings release dates)
- **Note:** Fundamentals must be **point-in-time** — use the value that was *known at the time*, not the restated value. This is a common source of look-ahead bias.

### Technical Indicators (Auto-Computed)

Computed from price data inside `02_feature_engineering.ipynb`. Never pulled from external sources — compute them yourself from raw OHLCV to avoid any timing issues.

### Sentiment / Alternative Data (Manual + Semi-Auto)

- **Earnings call sentiment:** Pull transcripts from `earningscall.biz` or `motley fool`, run basic positive/negative scoring
- **News volume:** Proxy using Google Trends or news article count from NewsAPI (free tier available)
- **Manual labels from your research:** The divergence scenario labels, laggard tags, and analyst notes from your other strategy docs — this is your proprietary signal

### Macro Context Data (Auto)

- **Source:** `pandas_datareader` pulling from FRED (Federal Reserve Economic Data)
- **Variables:** Fed funds rate, 10Y yield, yield curve spread (10Y-2Y), VIX, USD index (DXY), CPI YoY
- **Rationale:** Many stock moves are regime-dependent — a model trained without macro context will fail in different rate environments

---

## Feature Engineering

All features are computed in `02_feature_engineering.ipynb` and saved to `/data/processed/`. They are grouped into families:

### Family 1 — Price Action Features

| Feature | Formula / Method |
|---|---|
| Returns: 1d, 5d, 10d, 21d, 63d | `pct_change(n)` on adjusted close |
| Log returns | `log(close_t / close_t-1)` — preferred for modeling |
| Realized volatility | Rolling std of log returns (21d, 63d windows) |
| Price vs. 50d / 200d MA | `(close - MA_n) / MA_n` — normalized distance |
| 52-week high/low distance | Distance from current price to annual extremes |
| Gap up/down | Overnight gap as % of prior close |

### Family 2 — Volume Features

| Feature | Method |
|---|---|
| Relative volume | `volume / rolling_mean_volume(21d)` |
| Volume trend | `rolling_mean_volume(5d) / rolling_mean_volume(21d)` |
| On-Balance Volume (OBV) | Cumulative volume signed by price direction |
| Volume-price divergence | Price up + volume down flag (and vice versa) |

### Family 3 — Technical Momentum

| Feature | Parameters |
|---|---|
| RSI | 14-period |
| MACD | 12/26/9 standard |
| Bollinger Band position | `(close - lower) / (upper - lower)` |
| ATR (Average True Range) | 14-period, normalized by price |
| Stochastic oscillator | %K 14-period |

Use `ta` or `pandas_ta` library — do not hand-code these unless verifying.

### Family 4 — Fundamental Features

| Feature | Notes |
|---|---|
| P/E ratio | Use trailing, flag if negative |
| P/E vs. sector median | Relative valuation signal |
| Revenue growth (QoQ, YoY) | Acceleration matters more than level |
| Gross margin trend | Expanding vs. compressing |
| FCF yield | FCF / market cap |
| Debt/equity delta | Change over last 2 quarters |

**Important:** Fundamental features must be forward-filled at quarterly cadence and aligned to the exact date they became public (earnings release date, not period end date).

### Family 5 — Macro Context Features

| Feature | Source |
|---|---|
| VIX level | FRED / yfinance |
| VIX change (5d) | Regime shift indicator |
| Yield curve (10Y-2Y) | Recession signal |
| Fed funds rate | Rate environment |
| DXY (USD index) | Dollar strength effect |
| CPI YoY | Inflation regime |

### Family 6 — Manual / Proprietary Labels

| Feature | Source |
|---|---|
| Divergence scenario label (1–4) | Your human-in-the-loop DB from the divergence doc |
| Laggard flag | Tagged from your laggard screen |
| Analyst conviction tier | From your research notes |
| Checklist answer flags | Structured answers from detection checklist |

These features are your edge. No public dataset has them.

### Feature Engineering Rules

- All features must be computed using only information available **at the time of prediction** — no future data bleeds backward
- Features are normalized/scaled per model type: tree models need no scaling; neural nets require StandardScaler or MinMaxScaler
- Correlation matrix is run at the end of notebook 02 — features with >0.95 correlation to another feature are dropped (redundant noise)
- Missing value strategy: forward-fill fundamentals, drop rows with >20% missing features

---

## Target Variable Definition

This is the most important design decision. What exactly are you predicting?

### Primary Target: Directional Move (Classification)

- **Label:** 1 if `adjusted_close[t+n] > adjusted_close[t]`, else 0
- **Prediction horizons:** 5 days, 21 days, 63 days (run separately — different models for each)
- **Why classification not regression:** Regression on price level or return magnitude is much harder and noisier. Direction first. Magnitude comes in the scenario engine.

### Secondary Target: Magnitude Bucket (Multi-Class)

- **Labels:** Big Down (<-5%), Small Down (-5% to -1%), Flat (-1% to +1%), Small Up (+1% to +5%), Big Up (>+5%)
- **Use:** Feeds the scenario engine for probability-weighted outcome distributions
- **Note:** Class imbalance expected — "Flat" will dominate. Handle with class weights or SMOTE.

### What NOT to Predict

- Exact price target — too noisy, overfit-prone, and creates false precision
- Intraday moves — requires different data entirely (tick data, order flow)
- Options pricing — separate discipline, out of scope

---

## Baseline Models (Notebook 03)

**Always run baselines first. Never skip this step. A model that doesn't beat the baseline is not a model.**

### Baseline 1 — Random Walk (Naive)
- Prediction: Tomorrow's price = today's price (direction = 50/50)
- This is the hardest baseline to beat in finance
- Expected directional accuracy: ~50%

### Baseline 2 — Momentum Naive
- Prediction: If last 5 days were up, predict up. If down, predict down.
- Simple trend-following
- Expected accuracy: 51–53% depending on market regime

### Baseline 3 — Logistic Regression (Single Feature)
- Use only 1-month return as the feature
- Minimal model, interpretable
- Sets a floor for what ML complexity buys you

### Baseline 4 — Buy and Hold
- For evaluation purposes: compare your model's hypothetical return vs. just holding the stock for the same period
- This is the real-world benchmark — beating it risk-adjusted is the actual goal

All baselines are logged in `experiment_log.csv` with the same metrics as ML models.

---

## ML Models (Notebook 04)

### Model 1 — Logistic Regression (Full Features)
- Interpretable, fast, good for understanding feature importance
- L2 regularization, tune C parameter
- Good at: linear relationships, stability
- Weakness: can't capture non-linear interactions

### Model 2 — Random Forest
- Handles non-linearity well, robust to outliers
- Tune: n_estimators (100–500), max_depth (5–15), min_samples_leaf
- Built-in feature importance — use this to understand which features matter
- Good at: mixed feature types (technical + fundamental + macro)

### Model 3 — XGBoost / LightGBM
- Best classical ML model for tabular financial data in practice
- Tune with Optuna (Bayesian hyperparameter optimization) — not grid search
- Good at: capturing complex interactions, handling missing values
- Risk: overfitting without careful regularization and walk-forward validation

### Model 4 — Support Vector Machine (SVM)
- Works well in high-dimensional feature spaces
- Use RBF kernel
- Slower to train but sometimes finds patterns tree models miss
- Normalize features before using SVM

### Implementation Rules for All Classical ML Models

- **Walk-Forward Validation only** (see Validation section — this is critical)
- Feature importance plots for every model
- Calibrated probabilities (use `CalibratedClassifierCV`) — raw probabilities from tree models are not well-calibrated
- Log every experiment run: date, model, ticker, hyperparams, all metrics

---

## Deep Learning Models (Notebook 05)

### When to Use DL vs. Classical ML

Use DL when:
- You have 3+ years of daily data (minimum ~750 rows per ticker)
- You want to capture sequential / temporal patterns
- You are predicting at 21d+ horizons

Do not use DL when:
- Data is limited
- You need interpretability
- Predicting 1–5 day horizons (classical ML usually wins here)

### Model 5 — LSTM (Long Short-Term Memory)

Best for: capturing temporal dependencies in price sequences

Architecture:
```
Input: sequence of 60 days, each day = feature vector of all features
→ LSTM layer (64–128 units)
→ Dropout (0.2–0.3) — critical for regularization
→ LSTM layer (32–64 units, optional second layer)
→ Dropout (0.2)
→ Dense (16 units, ReLU)
→ Output: sigmoid (binary) or softmax (multi-class)
```

Sequence construction: sliding window of 60 trading days (~3 months) as input, predict next 5/21/63 days

Key hyperparameters to tune:
- Sequence length (30, 45, 60 days)
- Number of LSTM units
- Dropout rate
- Learning rate (start at 0.001, use ReduceLROnPlateau callback)
- Batch size (32 or 64)

### Model 6 — Transformer / Attention Model

Best for: capturing non-sequential long-range dependencies in features

Note: Transformers need more data than LSTMs. Only apply if you have 5+ years of history.

Architecture:
```
Input: same sequence format as LSTM
→ Positional Encoding
→ Multi-Head Attention (4–8 heads)
→ Feed-Forward layers
→ Global Average Pooling
→ Dense output
```

Libraries: Use `keras` with TensorFlow backend, or `pytorch` if preferred.

### Model 7 — Temporal Fusion Transformer (TFT)

Best for: multi-horizon forecasting with interpretable attention weights

This is the most sophisticated model in the stack. Only run after simpler models are validated. Use the `pytorch-forecasting` library.

Why TFT specifically: it handles static covariates (company fundamentals that don't change daily), time-varying known inputs (macro data), and time-varying unknown inputs (price/volume) in a unified architecture. It also produces quantile forecasts natively — useful for scenario generation.

### DL Training Rules

- Use GPU if available (Google Colab Pro or local)
- Early stopping with patience=15 epochs on validation loss
- Save best model checkpoint, not final epoch
- Learning rate scheduler: ReduceLROnPlateau or cosine annealing
- Always use walk-forward validation, not random train/test split
- Batch normalization between dense layers
- L2 regularization on dense layers

---

## Validation Framework

### Walk-Forward Validation (Mandatory for All Models)

**Never use random train/test split on time series data. It will leak future information into training and inflate all metrics.**

Walk-forward structure:
```
Training window: 3 years rolling
Validation window: 6 months (out of sample)
Step: Retrain every 6 months, advance the window

Example for 10 years of data:
  Fold 1: Train 2014–2016, Validate 2017 H1
  Fold 2: Train 2014–2017, Validate 2017 H2
  Fold 3: Train 2014–2017 H2, Validate 2018 H1
  ... continue to present
```

Average metrics across all folds. A model that works in 7 out of 10 folds but fails in 3 is telling you something important about regime sensitivity.

### Purged Cross-Validation

For overlapping prediction horizons (e.g., 21-day returns), add a **purge gap** between training and validation equal to the prediction horizon. This prevents label leakage when returns overlap across the boundary.

---

## Evaluation Metrics

Log all of these for every model, every ticker, every fold:

### Classification Metrics

| Metric | Why It Matters |
|---|---|
| Directional Accuracy | Basic: % of directions predicted correctly |
| Precision (Up class) | Of all "up" predictions, how many were right |
| Recall (Up class) | Of all actual ups, how many did you catch |
| F1 Score | Balance of precision and recall |
| AUC-ROC | Overall discrimination ability |
| Brier Score | Calibration of probabilities — lower is better |

### Financial Metrics (More Important Than Statistical Metrics)

| Metric | Why It Matters |
|---|---|
| Hypothetical return | If you acted on every signal, what return? |
| Sharpe Ratio (hypothetical) | Return per unit of risk |
| Max Drawdown | Worst peak-to-trough loss following signals |
| Win rate vs. baseline | How often model beats buy-and-hold |
| Signal frequency | How often does the model actually generate a signal? |

**Rule:** A model with 52% accuracy and 1.2 Sharpe is better than one with 58% accuracy and 0.6 Sharpe.

---

## Scenario Engine (Notebook 06)

This is where single-point predictions become actionable scenario plans.

### Method: Monte Carlo Simulation + Model Quantiles

For each ticker and prediction horizon, generate 1,000+ simulated price paths using:

1. **Model-informed drift:** Use the ML model's probability output (e.g., 62% probability of upward move) as the directional bias
2. **Historical volatility:** Use realized volatility (21d rolling) as the diffusion term
3. **Fat tails:** Use a Student-t distribution instead of normal — financial returns have fat tails and the model must reflect that

### Scenario Output Format

For each ticker, produce three named scenarios:

**Bull Scenario (Top 25th percentile of simulations)**
- Expected return range
- Key conditions that would validate this path (e.g., earnings beat, macro tailwinds)
- Probability estimate
- Suggested action

**Base Scenario (25th–75th percentile — median path)**
- Expected return range
- Most likely outcome given current signals
- Probability estimate
- Suggested action

**Bear Scenario (Bottom 25th percentile)**
- Expected return range
- Key conditions that would push toward this path
- Probability estimate
- Suggested action / risk management trigger

### Scenario Labeling in the UI / Notebook

Each scenario output includes:
- Price range at t+21 and t+63 days
- Probability (from simulation distribution)
- 3–5 bullet conditions that would confirm or invalidate the scenario
- Suggested action: Buy / Watch / Avoid / Exit
- Invalidation trigger: the specific event or price level that would flip the scenario

### If/Then Action Rules (Per Scenario)

For each scenario, define explicit conditional logic:

```
IF [Bull Scenario conditions hold]:
  → Action: Enter position / Add to position
  → Target: [price or return target]
  → Stop: [invalidation price]
  → Horizon: [21d / 63d]

IF [Base Scenario holds]:
  → Action: Hold / Wait for confirmation
  → Monitor: [specific indicators to watch]

IF [Bear Scenario materializes]:
  → Action: Avoid / Reduce / Exit
  → Trigger: [specific price or event]
```

This turns the probability output into a decision tree, not just a number.

---

## Multi-Company Ensemble (Notebook 07)

### Purpose

Aggregate signals across the 10–12 company universe to produce general market insights and reduce single-stock noise.

### Ensemble Construction

- Each company's model produces a directional probability (0–1) for each horizon
- Weight each company's signal by: model confidence (AUC from validation) × inverse of recent prediction error
- Do NOT weight by market cap — that introduces correlation bias (big tech is correlated)

### Ensemble Outputs

**Cross-Sector Sentiment Score**
- Average of all directional probabilities across the universe
- Score >0.60 → broadly bullish signal
- Score <0.40 → broadly bearish signal
- Score 0.40–0.60 → mixed / no clear edge

**Sector Divergence Signal**
- Compare sentiment scores within each sector
- Large spread between sectors = rotation signal (connects back to laggard screen)

**Consensus vs. Dissent Map**
- Table showing which companies all models agree on (high conviction) vs. disagree on (low conviction / skip)

### Statistical Averaging Rules

- Report median prediction, not mean — more robust to outliers
- Report 25th/75th percentile spread — wider spread = less consensus = lower position sizing
- Never report ensemble output without the per-company breakdown alongside it — the aggregate hides the important variance

---

## Overfitting Prevention Checklist

Run this checklist before trusting any result:

- [ ] Walk-forward validation used (not random split)?
- [ ] Purge gap applied for overlapping return horizons?
- [ ] Model performance on out-of-sample folds is consistent (not just one good fold)?
- [ ] Feature importance shows economically sensible features at the top (not random noise features)?
- [ ] Training accuracy is NOT dramatically higher than validation accuracy (>10% gap = overfit)?
- [ ] Model was NOT retrained on the test set after seeing results?
- [ ] Hyperparameters were tuned on validation, not test set?
- [ ] Results replicated on at least 3 different tickers before trusting?
- [ ] Financial metrics (Sharpe, drawdown) computed, not just accuracy?

If any box is unchecked, the result is not trustworthy.

---

## Experiment Logging (experiment_log.csv)

Every model run logged automatically. Schema:

| Column | Description |
|---|---|
| `run_id` | UUID |
| `run_date` | Timestamp |
| `ticker` | Company |
| `model_type` | e.g., XGBoost, LSTM, RandomForest |
| `prediction_horizon` | 5d / 21d / 63d |
| `feature_set` | Which families were used |
| `train_period` | Date range |
| `val_period` | Date range |
| `directional_accuracy` | % |
| `auc_roc` | Float |
| `brier_score` | Float |
| `hypothetical_sharpe` | Float |
| `max_drawdown` | Float |
| `beats_baseline` | Boolean |
| `notes` | Free text — what was different about this run |

This log is your experiment history. Without it you will repeat the same experiments and lose track of what worked.

---

## Known Risks and Limitations

| Risk | Mitigation |
|---|---|
| Look-ahead bias | Strict point-in-time feature construction, purged CV |
| Overfitting | Walk-forward validation, regularization, checklist above |
| Regime change | Models trained pre-2020 may not generalize post-2022. Retrain periodically. |
| Survivorship bias | Include some companies that struggled, not just current S&P winners |
| Spurious correlations | Feature importance review, economic intuition check |
| Over-reliance on model output | Scenarios are inputs to decisions, not decisions themselves |
| Data quality issues | Raw data layer is immutable; log any anomalies found during EDA |

---

## Implementation Order

Execute in this sequence — do not skip phases:

```
1. Build data pipeline (notebook 00) — get all tickers loading cleanly
2. Run EDA (notebook 01) — understand distributions, missing data, outliers
3. Build feature set (notebook 02) — all 6 feature families
4. Baselines (notebook 03) — establish the floor
5. Classical ML (notebook 04) — XGBoost should be your first serious model
6. Evaluate and log — do not proceed to DL until classical ML results are understood
7. Deep learning (notebook 05) — LSTM first, Transformer only after LSTM validated
8. Scenario engine (notebook 06) — connect model outputs to Monte Carlo paths
9. Ensemble (notebook 07) — only after individual models are validated
10. Final evaluation (notebook 08) — full comparison table, verdicts per model per ticker
```

---

## Success Criteria (What "Working" Looks Like)

The notebook is considered producing useful output when:

- At least one model beats all 4 baselines on at least 7 of 12 tickers in walk-forward validation
- Scenario engine produces three distinct, non-overlapping outcome ranges with economically sensible conditions
- Ensemble cross-sector sentiment score shows some correlation with subsequent 21d index returns (even weak correlation is useful)
- Experiment log has at least 50 runs with clear trend of improving metrics over iterations
- You can explain *why* the model works based on feature importance (not just that it does)

A model that cannot be explained should not be trusted, even if its metrics look good.
