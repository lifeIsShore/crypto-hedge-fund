# Hedge Fund Pipeline — Implementation Roadmap

> Grouped into independent streams. Each can be done in isolation.
> File paths are relative to `hedge-fund/` project root.

---

## ⚠️ START HERE: Stream 0 — Bug Fixes & Foundation (BLOCKING)

> These are runtime crashes and silent logic errors documented in `engine/ENGINE_REVIEW.md`.
> **Nothing in Streams 1–8 will run reliably until these are fixed.**
> Fix these first, in order.

### 0.1 — 🔴 SQLite `INTERVAL` crash in `alpha/base.py`
`compute_rolling_ic()` and `is_live_approved()` both use:
```sql
AND s.date >= CURRENT_DATE - INTERVAL ':days days'
```
SQLite does not support `INTERVAL`. This crashes on every IC computation (every alpha signal, every ticker, every day).

**Fix in `engine/alpha/base.py`:**
```python
# Replace INTERVAL with SQLite date arithmetic
cutoff = (datetime.date.today() - datetime.timedelta(days=days)).isoformat()
# Then use: AND s.date >= :cutoff   with {"cutoff": cutoff}
```

### 0.2 — 🔴 `pd.np` removed in modern pandas — `screens/etf_divergence.py`
```python
etf_pct_ret = (pd.np.exp(etf_log_ret) - 1) if hasattr(pd, 'np') else ...
```
`pd.np` was removed in pandas ≥ 1.0. The fallback re-imports numpy inside the loop on every iteration.

**Fix:** Remove the ternary; use `import numpy as np` at the top of the file and call `np.exp()` directly.

### 0.3 — 🔴 `DISTINCT ON` PostgreSQL-only — `reconciliation/state_reconciler.py`
```sql
SELECT DISTINCT ON (ticker) ticker, ...
FROM positions_history ORDER BY ticker, date DESC
```
`DISTINCT ON` is PostgreSQL-only. On SQLite this throws a syntax error at runtime.

**Fix:**
```sql
SELECT ticker, quantity, price, value_eur, weight
FROM positions_history
WHERE (ticker, date) IN (
    SELECT ticker, MAX(date) FROM positions_history GROUP BY ticker
)
```

### 0.4 — 🔴 Hardcoded `"UNKNOWN"` ticker — `execution/order_manager.py`
All confirmed orders are written to `trades` table with `ticker = "UNKNOWN"`. The dashboard has no mechanism to update this after insert.

**Fix:** Pass `ticker` as a parameter to `confirm_order()`. Update the function signature and all callers.

### 0.5 — 🔴 Wrong columns on `risk_events` insert — `risk/pre_trade.py`
```python
INSERT INTO risk_events (date, metric_name, metric_value) ...
```
`risk_events` has columns `(id, date, event_type, ticker, detail, logged_at)`. `metric_name` and `metric_value` don't exist on this table — they belong to `risk_metrics`. This insert fails silently or raises an error.

**Fix (already correct schema in schema.sql):**
```python
INSERT INTO risk_events (date, event_type, detail)
VALUES (CURRENT_DATE, 'pre_trade_violation', :detail)
```

### 0.6 — 🟡 GBP→EUR FX rate inverted wrong — `data/ingestion.py`
```python
'GBPEUR': ('GBPUSD=X', True),  # inverting GBP/USD does NOT give EUR/GBP
```
Inverting `GBPUSD=X` gives `GBP per USD`, not `EUR per GBP`. All `.L` (LSE) ticker prices are converted with the wrong rate.

**Fix:**
```python
'GBPEUR': ('GBPEUR=X', False),  # direct pair, no inversion needed
```

### 0.7 — 🟡 IC floor hides negative IC — `alpha/base.py`
```python
return max(0.01, ic)
```
When a model has negative IC (actively wrong predictions), flooring to `0.01` lets it keep influencing BL weights instead of being penalised.

**Fix:** Return the raw IC for diagnostics. Only apply the floor inside the BL omega calculation where a zero denominator would break math.

### 0.8 — 🟠 `execution/` and `reconciliation/` modules never called from scheduler
Both modules have never been imported (no `__pycache__`). The full `BL → optimizer → pre-trade → orders → post-trade` loop (`step_portfolio_construction`) exists in `scheduler.py` and is now wired — but double-check that `step_portfolio_construction` is actually registered as step 11 in `run_pipeline()`.

### 0.9 — 🟠 `alpha_signals` table defined but never written to
`alpha_signals` in `schema.sql` has `ic_21d/63d/252d` columns, clearly intended for IC tracking. Nothing writes to it. IC is re-queried from scratch every run.

**Fix (defer to Stream 5):** Either wire IC writes into `base.py` after each compute, or drop the table and use the `signals` table's existing IC columns consistently.

### 0.10 — 🟡 `cash_match` always `TRUE` in reconciliation
Cash reconciliation is not implemented — the log always records `TRUE`. The `cash_history` table exists but is never read here.

**Fix (defer to Stream 8 — Ledger Replay):** Implement actual cash reconciliation in `reconcile()` once ledger import is complete.

---

## Stream 1 — EUR Currency Normalisation (Trade Republic)

### Problem
US tickers (`MSFT`, `NVDA`, etc.) are priced in USD.  
EUR tickers (`APC.DE`, `MSF.DE`, `SAP.DE`) are priced in EUR.  
Black-Litterman and the portfolio optimizer currently mix both, which makes
weight comparisons, expected-return scaling, and € P&L meaningless.

### 1.1 — Add a FX rates table to the database
**File:** `engine/db/schema.py` (or wherever `CREATE TABLE` lives)

```sql
CREATE TABLE IF NOT EXISTS fx_rates (
    date        TEXT NOT NULL,
    pair        TEXT NOT NULL,   -- e.g. 'EURUSD'
    rate        REAL NOT NULL,
    PRIMARY KEY (date, pair)
);
```

### 1.2 — Ingest EUR/USD daily in `data/ingestion.py`
Add a step that fetches `EURUSD=X` from yfinance and writes to `fx_rates`.  
The ingestion already runs daily — just append this to `run_ingestion()`.

```python
# Pseudocode to add to engine/data/ingestion.py
def ingest_fx_rates(session, date):
    import yfinance as yf
    eurusd = yf.download("EURUSD=X", period="5d", progress=False)["Adj Close"]
    rate = float(eurusd.iloc[-1])
    session.execute(text("""
        INSERT INTO fx_rates (date, pair, rate)
        VALUES (:date, 'EURUSD', :rate)
        ON CONFLICT (date, pair) DO UPDATE SET rate = :rate
    """), {"date": date, "rate": rate})
```

### 1.3 — Tag every ticker with its native currency
**File:** `portfolio/src/config.py` (or a new `engine/data/ticker_meta.py`)

```python
# Add a dict alongside ASSET_UNIVERSE
TICKER_CURRENCY = {
    "APC.DE": "EUR", "MSF.DE": "EUR", "SAP.DE": "EUR",
    "EUNL.DE": "EUR", "ALV.DE": "EUR", "SIE.DE": "EUR",
    "NVDA": "USD", "AMZN": "USD", "TSLA": "USD",
    # ... etc
}
BASE_CURRENCY = "EUR"   # Trade Republic account currency
```

### 1.4 — Convert USD prices to EUR in `feature_store.py`
In `load_returns_from_db()`, after fetching prices, multiply USD ticker
prices by the EUR/USD rate fetched the same day.

```python
# After pivot is built in load_returns_from_db():
for ticker in pivot.columns:
    if TICKER_CURRENCY.get(ticker, "USD") == "USD":
        pivot[ticker] = pivot[ticker] / fx_rate_series  # align by date
```

> **Why this matters:** BL expected returns, optimizer weights, and order
> sizing in € will then all be consistent. A USD-denominated signal that
> says "+4% return" will correctly translate to the EUR-denominated return
> after FX drift.

### 1.5 — Show EUR-adjusted prices on the dashboard
Add a `currency` column to the positions table display so Trade Republic
users see their actual € values without mental conversion.

---

## Stream 2 — ML Universe Expansion

### Problem
Current `UNIVERSE` in `data_loader.py` has only 10 tickers (US-heavy).
Signals from 10 tickers give a noisy, US-biased ensemble verdict.

### 2.1 — Expand `data_loader.py` UNIVERSE dict
Target: ~50 tickers across sectors and geographies.

```python
UNIVERSE = {
    # ── US Mega-Cap Tech ───────────────────────────────────────────────────
    "MSFT": "Technology",  "AAPL": "Technology",  "NVDA": "Technology",
    "GOOGL": "Technology", "META": "Communication","AMZN": "Consumer Disc",
    "ADBE": "Technology",  "CRM": "Technology",   "NOW": "Technology",
    "ORCL": "Technology",

    # ── US Semis ───────────────────────────────────────────────────────────
    "AMD": "Semiconductors", "INTC": "Semiconductors", "QCOM": "Semiconductors",
    "AMAT": "Semiconductors","MU": "Semiconductors",   "TXN": "Semiconductors",

    # ── US Financials ──────────────────────────────────────────────────────
    "JPM": "Financials", "GS": "Financials", "MS": "Financials",
    "BRK-B": "Diversified", "V": "Financials", "MA": "Financials",

    # ── US Healthcare ──────────────────────────────────────────────────────
    "UNH": "Healthcare", "LLY": "Healthcare", "ABBV": "Healthcare",
    "PFE": "Healthcare", "MRK": "Healthcare", "AMGN": "Healthcare",

    # ── US Consumer/Staples ────────────────────────────────────────────────
    "TSLA": "Consumer Disc", "KO": "Consumer Staples",
    "WMT": "Consumer Staples","HD": "Consumer Disc",

    # ── US Industrials/Energy ──────────────────────────────────────────────
    "CAT": "Industrials", "XOM": "Energy", "CVX": "Energy",
    "BA": "Industrials",  "LMT": "Industrials",

    # ── European Blue-Chips (EUR-denominated, Trade Republic) ───────────────
    "SAP.DE": "Technology",   "SIE.DE": "Industrials",  "ALV.DE": "Financials",
    "BMW.DE": "Consumer Disc","MBG.DE": "Consumer Disc","VOW3.DE": "Consumer Disc",
    "DTE.DE": "Comm Services","IFX.DE": "Semis",        "BAS.DE": "Chemicals",
    "AIR.DE": "Aerospace",    "APC.DE": "Technology",   "MSF.DE": "Technology",
    "ASML.AS": "Semis",       "MC.PA": "Luxury",        "TTE.PA": "Energy",
    "NOV.DE": "Healthcare",   "EUNL.DE": "ETF",

    # ── Commodities / Macro proxies ────────────────────────────────────────
    "GLD": "Commodities", "SLV": "Commodities", "USO": "Energy",
    "TLT": "Fixed Income", "HYG": "Fixed Income",
}
```

### 2.2 — Add EUR ticker handling in `fetch_price_data()`
yfinance handles `.DE` tickers natively. Just ensure they are fetched with
`auto_adjust=False` (same as US). No change needed to the fetch logic —
just add them to UNIVERSE.

> **Training effect:** Going from 10 → 50 tickers gives the walk-forward
> evaluator ~5× more fold instances, making AUC and Sharpe estimates
> significantly more robust.

### 2.3 — Handle EUR tickers missing `Adj Close`
Some European yfinance feeds return `Close` without `Adj Close`. The
existing fallback in `run_ml_pipeline.py` already handles this — no change needed.

---

## Stream 3 — Price Target & Resistance Levels (€)

### 3.1 — New module: `engine/analysis/price_targets.py`

This module takes as input:
- `current_price_eur` (EUR-adjusted)
- `up_proba_21d` from `ml_state.json`
- `vol_ann` from `ml_state.json`
- OHLCV history from DB

And outputs:

| Output | Method |
|--------|--------|
| **Expected price (21d)** | `current * exp(up_proba edge * vol * sqrt(21/252))` |
| **Upside target (+1σ)** | Lognormal 84th percentile at t=21d |
| **Stop-loss (-1σ)** | Lognormal 16th percentile at t=21d |
| **MA resistance** | 50d MA, 200d MA |
| **Bollinger upper/lower** | ±2σ 20d band |
| **52-week high/low** | Static level from DB |
| **VWAP** | Volume-weighted avg over 20d |
| **Round number levels** | Nearest 5% round numbers above/below |

```python
def compute_price_targets(ticker, current_price_eur, up_proba, vol_ann,
                          prices_df) -> dict:
    horizon = 21
    t = horizon / 252
    edge = (up_proba - 0.5) * 2
    drift = edge * vol_ann * t
    sigma = vol_ann * np.sqrt(t)

    expected = current_price_eur * np.exp(drift)
    target_up = current_price_eur * np.exp(drift + sigma)
    stop_loss = current_price_eur * np.exp(drift - sigma)
    stop_tight = current_price_eur * np.exp(drift - 0.5*sigma)

    ma50  = prices_df["Close"].rolling(50).mean().iloc[-1]
    ma200 = prices_df["Close"].rolling(200).mean().iloc[-1]
    bb_upper = prices_df["Close"].rolling(20).mean().iloc[-1] + \
               2 * prices_df["Close"].rolling(20).std().iloc[-1]
    bb_lower = prices_df["Close"].rolling(20).mean().iloc[-1] - \
               2 * prices_df["Close"].rolling(20).std().iloc[-1]

    return {
        "expected_21d_eur":  round(expected, 2),
        "target_1sigma_eur": round(target_up, 2),
        "stop_1sigma_eur":   round(stop_loss, 2),
        "stop_tight_eur":    round(stop_tight, 2),
        "resistance_ma50":   round(ma50, 2),
        "resistance_ma200":  round(ma200, 2),
        "resistance_bb_upper": round(bb_upper, 2),
        "support_bb_lower":    round(bb_lower, 2),
        "risk_reward_ratio": round((target_up - current_price_eur) /
                                   (current_price_eur - stop_loss + 1e-9), 2),
    }
```

### 3.2 — Persist to a new `price_targets` table in SQLite
```sql
CREATE TABLE IF NOT EXISTS price_targets (
    date              TEXT NOT NULL,
    ticker            TEXT NOT NULL,
    current_price_eur REAL,
    expected_21d_eur  REAL,
    target_1sigma_eur REAL,
    stop_1sigma_eur   REAL,
    stop_tight_eur    REAL,
    resistance_ma50   REAL,
    resistance_ma200  REAL,
    resistance_bb_upper REAL,
    support_bb_lower    REAL,
    risk_reward_ratio   REAL,
    computed_at       TEXT,
    PRIMARY KEY (date, ticker)
);
```

### 3.3 — Wire into `scheduler.py` as a daily step after portfolio construction

```python
_run_step('12. Price targets', step_price_targets, dry_run)
```

### 3.4 — Surface in the dashboard
Per-ticker: `Expected 21d: €142.50 (+4.2%) | Target: €148 | Stop: €132 | R:R 1.8`

---

## Stream 4 — Risk/Strategy HTML Page (Probability View)

### 4.1 — New dynamic dashboard: `dashboard/risk_strategy.html`

A single, high-performance HTML dashboard featuring a **Global Ticker Selector** (dropdown). Selecting a ticker instantly re-calculates and re-renders the following sections.

**Sections:**

#### A. Global Ticker Selector & Core Stats
- Dropdown containing the expanded universe.
- Summary bar: Current Price (€), 21d Forecast (%), and Macro Regime alignment.

#### B. Probability Distribution of Risk
- Interactive Chart: Visualizes the return distribution (from Monte Carlo sims).
- VaR: Clear markers for 1% and 5% worst-case loss thresholds.
- Probabilistic Targets: P(Profit > 0), P(Profit > 5%), and P(Max Drawdown > 10%).

#### C. The "Stick-To-It" Strategy Card
- **Buy-In Zone:** Statistical "Fair Value" range based on recent volatility.
- **Target Exit (€):** Probabilistic profit-taking level.
- **Hard Stop-Loss (€):** The "Statistical Limit Loss" price.
- **Resistance/Support Points:** 50d/200d MA and Bollinger levels in €.
- **Risk Probability Score:** 1–100 score of how likely the trade hits target before stop.

#### D. Risk/Reward Summary Table
| Ticker | Price € | Expected 21d € | Target € | Stop € | R:R | Win Prob | Kelly % |

**Kelly fraction:** `f = (p * b - q) / b` where `p=up_proba`, `q=1-p`, `b = target/current - 1`.

#### E. Portfolio-Level Risk Distribution
- Aggregated P&L distribution across all positions (Monte Carlo, weighted by current weights)
- VaR (5th percentile), CVaR (average of bottom 5%)
- Current vs optimal position sizing (Kelly vs actual)

### 4.2 — Data source
- `shared/state/ml_state.json` → `model_signals` for up_proba per ticker
- `shared/state/regime_state.json` → current regime
- `shared/state/price_targets.json` OR from SQLite via Flask endpoint `/api/price_targets`

### 4.3 — Flask endpoint
```python
@app.route('/api/price_targets')
def api_price_targets():
    session = get_session()
    rows = session.execute(text("""
        SELECT ticker, current_price_eur, expected_21d_eur, target_1sigma_eur,
               stop_1sigma_eur, stop_tight_eur, resistance_ma50, resistance_ma200,
               risk_reward_ratio
        FROM price_targets
        WHERE date = (SELECT MAX(date) FROM price_targets)
    """)).fetchall()
    session.close()
    return jsonify([dict(r._mapping) for r in rows])
```

---

## Stream 5 — SQLite Storage Migration

### Guiding principle
> **SQLite** = anything you'd want to query by date/ticker, JOIN with other tables, or aggregate over time.  
> **JSON** = anything that is a rich nested object read/written atomically and never partially queried.

### What to keep as JSON ✅
| File | Reason |
|------|--------|
| `shared/state/ml_state.json` | Deep nested tree: ensemble, model_comparison, scenarios, feature_importance. |
| `shared/state/factor_state.json` | BL factor outputs, matrices. Always read whole. |
| `shared/state/correlation_state.json` | Correlation matrix. Always read whole. |
| `shared/state/pead_state.json` | Dashboard-ready summary. Small. Read atomically. |
| `shared/state/regime_state.json` | Latest snapshot only. Read atomically. |

### What to migrate to SQLite 🔄

#### 5.1 — `regime_history.csv` → `regime_history` table
```sql
CREATE TABLE IF NOT EXISTS regime_history (
    date              TEXT PRIMARY KEY,
    regime_risk       TEXT,
    regime_rates      TEXT,
    regime_growth     TEXT,
    regime_composite  TEXT,
    transition_warning INTEGER,
    ew_active_count   INTEGER,
    vix               REAL,
    yield_spread      REAL,
    hy_spread         REAL,
    fed_funds         REAL,
    computed_at       TEXT
);
```
**Action:** Update `regime_db.py` → `save_regime_history()` to write to this table. Keep CSV as lightweight backup.

#### 5.2 — `pead_setups.csv` → `pead_setups` table
```sql
CREATE TABLE IF NOT EXISTS pead_setups (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker           TEXT NOT NULL,
    earnings_date    TEXT NOT NULL,
    entry_date       TEXT,
    direction        TEXT,
    pead_setup_quality TEXT,
    surprise_pct     REAL,
    underreaction_flag INTEGER,
    reaction_gap     REAL,
    drift_21d        REAL,
    drift_63d        REAL,
    outcome_label_correct INTEGER,
    regime_risk      TEXT,
    regime_growth    TEXT,
    regime_composite TEXT,
    sector           TEXT,
    created_at       TEXT,
    UNIQUE(ticker, earnings_date)
);
```

#### 5.3 — `price_targets` table (from Stream 3)
#### 5.4 — `fx_rates` table (from Stream 1)

### Migration order
1. Add new tables to `engine/db/schema.sql`
2. Update writers first (regime_db.py, pead_db.py)
3. Update readers to prefer SQL but fall back to CSV if table is empty
4. After one week of confirmed SQL writes, remove CSV dependency

---

## Stream 6 — Frontend Consolidation (Bye-bye Streamlit)

> **STATUS (2026-08-09, verified by Claude): DONE.** Checked all 3 `.bat` files (`RUN_FUND_TOTAL.bat`, `RUN_SANDBOX.bat`, `DASHBOARD_ONLY.bat`) and `.env.example` — zero Streamlit references anywhere in the live run path. Flask (`flask_app.py`) is the sole dashboard entry point, confirmed by the unified routing already in place (`/`, `/rebalance`, `/divergence`, etc. all live in `flask_app.py`). The old Streamlit code sits retired in `_archive/dashboard/`, `_archive/.streamlit/`, `_archive/portfolio_pages/` — correctly out of the live path. Nothing left to do here.

### 6.1 — Migrate ML Research & Quant Results to HTML
Convert existing Streamlit components (charts, tables, parameter sliders) into pure HTML/CSS/JS components within the main Flask dashboard.

- **Charts:** Use `Chart.js` for lightweight line charts and `Plotly.js` for complex probability distributions.
- **Tables:** Standardize on a single, searchable HTML table component (DataTables.net style).
- **Communication:** Main app fetches data from `/api/ml_results` and `/api/quant_results` instead of reading files directly in Python.

### 6.2 — Unified Routing
The Flask app becomes the single entry point:
- `/` — Main Portfolio Overview
- `/risk` — New Probabilistic Strategy Page (Stream 4)
- `/research` — Consolidated ML/Quant findings (formerly Streamlit)
- `/rebalance` — Trade execution and drift management

---

## Stream 7 — ML Integrity & Validation (Scaling Safely)

> **STATUS (2026-08-09, verified by Claude): DONE.** Both sub-items confirmed directly in code:
> - **7.1 (purge buffer):** `evaluator.py`'s `walk_forward_splits()` implements a 7-day embargo between train/val folds (`PURGE_BUFFER_DAYS = 7`), explicitly citing Lopez de Prado's embargo method. There's also a `get_walk_forward_report()` diagnostic function showing exact train/purge/val date ranges per fold — built beyond what this doc asked for.
> - **7.2 (correlation dedup):** `feature_builder.py` has a two-stage feature selection pipeline; Stage 2 drops one of any feature pair with |r| > 0.95, keeping the higher-variance one. Also confirmed.
> - **Not done:** the "Stratification" sub-bullet (separate Regime Expert weights trained per macro regime) — this was a minor aside in the original doc, not a numbered sub-item, and is a much bigger feature (essentially N separate model variants) than the rest of this stream. Worth its own doc if you want it, not a quick add-on.

### 7.1 — Strict Walk-Forward Isolation
As the universe expands, we must ensure the `evaluator.py` maintains absolute time-series separation.
- **Rule:** No data point from the "Testing" fold can ever exist in the "Training" fold.
- **Buffer Zones:** Implement a 7-day "purge" between training and testing to account for lagged features (like 5-day RSI).

### 7.2 — Feature Correlation Deduplication
Prevent "Model Overlap" by pruning the feature set.
- **Automatic Pruning:** If two features (e.g., RSI_14 and Stoch_K) have correlation > 0.95, automatically drop one.
- **Stratification:** Train separate "Regime Expert" weights (e.g., weights that perform better in Risk-Off).

---

## Stream 8 — Portfolio Vision (Ledger Replay)

### 8.1 — Transaction-to-Holding Module
Instead of a static list, the Engine will "replay" your `portfolio/data/ledger.csv` to reconstruct current state.
- **Tool:** `engine/reconciliation/ledger_importer.py`
- **Logic:** Iterates through all `Buy` and `Sell` actions to find current `Quantity` per ticker. Sums `Deposit`, `Dividend`, `Fee`, and trade `Total` values to find exact `CASH` balance.
- **SQLite Sync:** The resulting "Snapshot" is saved to `positions_history` and `cash_history` tables.

### 8.2 — Automated Drift & Order Generation
Compare your CSV holdings against the "Optimal Weight" suggested by the ML/Quant models.
- **The "Trade Advisor":** Generates a specific advice card: *"You own 14 shares of ATAI; Model target is 20 shares. Action: Buy 6 shares."*

### 8.3 — Sync Verification in `.bat`
The `refresh_engine.bat` ensures that your `ledger.csv` is parsed before any portfolio optimization, so you are always trading based on your real-world account balance.

---

not now
## Stream 9 — Alerting & Observability (NEW)

> **Problem:** The pipeline runs silently. If the Saturday ML refresh crashes or
> the pre-trade checks block orders, you only find out by tailing logs. For a
> system managing real money, you need a simple health layer.

### 9.1 — Daily pipeline digest (email or Slack)
After `run_pipeline()` completes, send a summary:
```
📊 Pipeline Summary — 2026-05-10
✅  1. Data ingestion         (12.3s)
✅  2. Regime refresh          (8.1s)
✅  3. Feature pipeline        (4.7s)
⚠️  8. Alpha: ML signals      (SLOW — 94.2s, threshold 60s)
✅ 11. Portfolio construction  (5.2s)
---
Orders blocked: NO
Pre-trade violations: 0
Portfolio VaR (95%): -2.3%
Regime: Expansion + RiskOn
```

**Implementation:** Add `send_digest()` at the end of `run_pipeline()`. Reuse existing `send_alert()` Slack webhook. Add optional email via `smtplib` (env var `SMTP_*`).

### 9.2 — Pipeline health page in dashboard
A simple `/health` route in Flask showing:
- Last run date + time per step
- Status (success / failed / skipped) for the last 7 days (from `pipeline_runs` table — already being written!)
- Any open `risk_events` from the last 24h

### 9.3 — Slow-step warnings
In `_run_step()`, add a threshold check:
```python
STEP_THRESHOLDS = {
    '1. Data ingestion': 120,   # seconds
    'WE1. ML pipeline refresh': 1800,
}
if elapsed > STEP_THRESHOLDS.get(name, 300):
    send_alert(f"⚠️ {name} took {elapsed}s — above threshold")
```

### 9.4 — Heartbeat check
A simple daily cron job (or Windows Task Scheduler entry) that:
1. Reads the latest `run_date` from `pipeline_runs`
2. If it's more than 2 trading days old, sends an alert: "Pipeline hasn't run since {date}"

This catches the silent failure case: the `.bat` doesn't run because of a Windows update reboot or a login screen.

---

## Recommended Implementation Order

| Order | Stream | Why |
|-------|--------|-----|
| **1st** | Stream 0 — Bug Fixes | Unblocks everything. Pipeline crashes without this. |
| **2nd** | Stream 1 — FX Normalisation | Makes all EUR P&L correct. High correctness impact. |
| **3rd** | Stream 2 — Universe Expansion | Easy win. Just add tickers. Better ML signal immediately. |
| **4th** | Stream 3 — Price Targets | Actionable trade levels. Needed for Stream 4. |
| **5th** | Stream 4 — Risk Dashboard | User-visible value. Depends on Stream 3. |
| **6th** | Stream 8 — Ledger Replay | Real portfolio grounding. Fixes cash_match hardcoding (0.10). |
| **7th** | Stream 9 — Alerting | Operational maturity. Can build in parallel with 3–4. |
| **8th** | Stream 5 — SQLite Migration | Cleanup. Low urgency but improves queryability. |
| **9th** | Stream 6 — Frontend | Drop Streamlit. Parallel with 5. |
| **10th** | Stream 7 — ML Integrity | Scaling safety. Do after universe is expanded. |

---

## Quick Reference — Impact vs Effort

| Stream | Impact | Effort | Do First? |
|--------|--------|--------|-----------|
| Stream 0: Bug Fixes | 🔴 Critical — pipeline crashes without this | Low | **YES — before anything** |
| Stream 1: FX | 🔴 High — makes all EUR P&L correct | Medium | Yes |
| Stream 2: Universe | 🟠 Medium-High — better ensemble signal | Low (just add tickers) | Yes, easy win |
| Stream 3: Price Targets | 🟠 Medium-High — actionable trade levels | Medium | After FX |
| Stream 4: Risk Dashboard | 🔵 High user value | High | Parallel with 3 |
| Stream 8: Ledger Replay | 🟠 Medium — real portfolio grounding | Medium | After dashboard |
| Stream 9: Alerting | 🟢 Operational maturity | Low | Anytime |
| Stream 5: SQLite Migration | 🟢 Low urgency but clean | Medium | Last |
| Stream 6: Frontend | 🔵 Recommended — Unified premium UX | High | Parallel with 5 |
| Stream 7: ML Integrity | 🟢 Scaling safety | Medium | After universe expansion |

---

## Design Principles: The Coherence Manifesto

To ensure the application remains stable and trustworthy as it grows, we follow these 3 rules:

### 1. Single Source of Truth (SSOT)
- **Data:** All raw data enters through `ingestion.py`. No other module fetches raw yfinance data directly.
- **Currency:** All internal values are stored and transmitted in **EUR**. Currency conversion happens at the edge (ingestion) and nowhere else.
- **State:** `shared/state/` remains the only place where inter-process artifacts live.

### 2. Logic Centralization (DRY)
- **Alpha Models:** All alpha calculation logic lives in `engine/alpha/`. The Frontend only displays these values; it never calculates its own "Expected Return."
- **Price Targets:** The logic for 1σ stops and targets lives in a single utility module used by both the daily scheduler and the Flask API.

### 3. Component Reusability
- **UI Consistency:** Any new HTML/JS component must be written as a reusable template.
- **Dropdown Synchronisation:** The Ticker Selector should be a global component. Selecting "NVDA" on the research tab should persist when switching to the risk tab.

---

## Notes & Caveats

- **ML on European stocks:** `.DE` tickers via yfinance often have less options data (no CBOE coverage). The `options_scraper` will silently fail for these — that's fine, options features will be `NaN` and the model will still train on the other 6 feature families.

- **Kelly sizing is a guide, not a rule.** On a real Trade Republic account, never use raw Kelly — use half-Kelly as a maximum per-ticker allocation.

- **Price targets are probabilistic, not guaranteed.** The expected price is the median of a lognormal distribution — it will be wrong roughly 50% of the time. The value is in having an explicit exit plan, not in precision.

- **Resistance levels from technical analysis** are useful anchors but should be combined with the ML signal. A resistance level only matters if the model also shows high AUC (edge > random).
