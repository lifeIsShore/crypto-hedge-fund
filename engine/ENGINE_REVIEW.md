# Engine Code Review — Issues & Missing Implementations

> **Scope:** `engine/` directory only  
> **Date:** 2026-05-10  
> **Severity levels:** 🔴 Bug / will break at runtime · 🟡 Logic error / wrong result silently · 🟠 Missing implementation · ⚪ Minor / style

---

## 1. `alpha/base.py` — `compute_rolling_ic()`

### 🔴 SQLite-incompatible `INTERVAL` syntax
```python
AND s.date >= CURRENT_DATE - INTERVAL ':days days'
```
SQLite does not support `INTERVAL`. This query will **throw a runtime error** every time IC is computed (i.e., for every alpha signal on every ticker every day).

**Fix:** Use SQLite date arithmetic:
```sql
AND s.date >= date('now', '-63 days')
```
Or pass the cutoff date as a Python string parameter.

---

### 🟡 `is_live_approved()` uses `confidence` as a proxy for IC — but it is not IC
The query averages `confidence` from the `signals` table. `confidence` is set differently by each model (AUC for ML, rolling IC for others). For models that write AUC as confidence, the live-approval gate is checking AUC ≥ 0.05, not IC ≥ 0.05 — a completely different threshold with a different semantic. The gate will pass models that have poor IC but high AUC, or reject models that have good IC but modest AUC.

**Fix:** Either store IC separately (the schema already has `ic_21d` / `ic_63d` columns on the `signals` table but they are never written), or make `is_live_approved()` call `compute_rolling_ic()` directly.

---

### 🟡 `is_live_approved()` same `INTERVAL` bug
Same SQLite incompatibility as above — `INTERVAL '90 days'` will fail.

---

## 2. `alpha/base.py` — `compute_rolling_ic()`

### 🟡 IC floor `max(0.01, ic)` hides negative IC
When a model has negative IC (signal is actively wrong), the floor returns `0.01` instead of a negative value. This means a model that consistently predicts the opposite of what happens will still get positive confidence weight in Black-Litterman, rather than being penalised or excluded. The comment says "never return 0 (breaks BL omega)" but the fix should be to clamp to a small positive only for the omega calculation, not to hide the diagnostic value.

---

## 3. `screens/etf_divergence.py` — `detect_divergences()`

### 🔴 `pd.np` is removed in pandas ≥ 1.0
```python
etf_pct_ret = (pd.np.exp(etf_log_ret) - 1) if hasattr(pd, 'np') else (
    __import__('numpy').exp(etf_log_ret) - 1
)
```
The `hasattr(pd, 'np')` fallback will always take the `__import__('numpy')` branch on any modern pandas, but the pattern is fragile and ugly. More critically, `numpy` is already imported at the top of the function via `import numpy as np` inside the loop — which means `np` is being re-imported inside every iteration of the `components` loop.

**Fix:** Move `import numpy as np` to the top of the file and use it directly:
```python
etf_pct_ret = np.exp(etf_log_ret) - 1
```

---

## 4. `portfolio/black_litterman.py` — `compute_view_omegas()`

### 🟠 Function defined but never called
`compute_view_omegas()` is defined and correct in isolation, but `build_bl_views_calibrated()` reimplements the omega calculation inline (differently) and never calls `compute_view_omegas()`. There are now two divergent omega computation paths in the same file.

**Fix:** Either delete `compute_view_omegas()` or refactor `build_bl_views_calibrated()` to use it.

---

## 5. `portfolio/black_litterman.py` — `build_bl_views_calibrated()`

### 🟡 `Sigma` is computed but never used for the approved-model path
```python
Sigma = cov_matrix.loc[tickers, tickers].values
ic = max(0.01, float(row["confidence"]))
...
base = float((P_row @ (tau * Sigma) @ P_row.T)[0, 0])
omega = base / (ic ** 2)
```
`Sigma` is computed every loop iteration (an n×n matrix slice each time) even though only `P_row @ (tau * Sigma) @ P_row.T` is needed — a scalar. For 50 tickers this is fine; for 200+ tickers this becomes expensive. Not a correctness issue, but worth noting.

---

## 6. `execution/order_manager.py` — `confirm_order()`

### 🔴 Hardcoded `"UNKNOWN"` ticker
```python
session.execute(text("""
    INSERT INTO trades (date, ticker, action, ...)
    VALUES (CURRENT_DATE, :ticker, :action, ...)
"""), {
    "ticker": "UNKNOWN",   # replaced by dashboard with actual ticker
    ...
})
```
The ticker is hardcoded as `"UNKNOWN"`. The comment says "replaced by dashboard" but the dashboard has no mechanism to update this after insert — it would need to DELETE and re-INSERT or UPDATE. This means all confirmed orders are written to the `trades` table with `ticker = 'UNKNOWN'` until a dashboard UPDATE path is implemented (which does not exist in this codebase).

**Fix:** Pass `order_id` and `ticker` as parameters to `confirm_order()`.

---

## 7. `reconciliation/state_reconciler.py` — `get_db_positions()`

### 🔴 `DISTINCT ON` is PostgreSQL-only; not supported by SQLite
```sql
SELECT DISTINCT ON (ticker) ticker, quantity, price, value_eur, weight
FROM positions_history
ORDER BY ticker, date DESC
```
`DISTINCT ON` is a PostgreSQL extension. On SQLite (the current default DB), this will throw a syntax error at runtime.

**Fix for SQLite:**
```sql
SELECT ticker, quantity, price, value_eur, weight
FROM positions_history
WHERE (ticker, date) IN (
    SELECT ticker, MAX(date) FROM positions_history GROUP BY ticker
)
```

---

## 8. `reconciliation/state_reconciler.py` — `reconcile()`

### 🟡 `cash_match` hardcoded to `TRUE`
```python
session.execute(text("""
    INSERT INTO reconciliation_log (positions_match, cash_match, discrepancies, action_taken)
    VALUES (:pos_match, TRUE, :disc, :action)
"""), ...)
```
Cash reconciliation is not implemented — it always writes `TRUE`. The schema has a `cash_history` table but it is never read here.

---

## 9. `risk/pre_trade.py` — `risk_events` schema mismatch

### 🟡 Inserting into wrong columns
```python
session.execute(text("""
    INSERT INTO risk_events (date, metric_name, metric_value)
    VALUES (CURRENT_DATE, :name, 1)
"""), {"name": f"pre_trade_violation: {v[:60]}"})
```
The `risk_events` schema (from `schema.sql`) defines columns: `(id, date, event_type, ticker, detail, logged_at)`. There are no columns `metric_name` or `metric_value` on `risk_events`. This insert will fail silently or raise an error depending on SQLite's strict mode.

The columns `metric_name` / `metric_value` exist on `risk_metrics`, not `risk_events`.

**Fix:** Use the correct table/columns:
```python
INSERT INTO risk_events (date, event_type, detail)
VALUES (CURRENT_DATE, 'pre_trade_violation', :detail)
```

---

## 10. `data/ingestion.py` — FX inversion for GBP

### 🟡 `GBPUSD=X` inverted gives USD/GBP, not EUR/GBP
```python
'GBPEUR': ('GBPUSD=X', True),   # GBP/USD also inverted to get EUR/GBP
```
Inverting `GBPUSD=X` gives `USD per GBP` inverted = `GBP per USD`, which is neither EUR/GBP nor GBP/EUR. To get GBP→EUR you need either `GBPEUR=X` directly from yfinance, or derive it as `GBPUSD / EURUSD`. The current code applies a wrong multiplier to all `.L` tickers.

**Fix:**
```python
'GBPEUR': ('GBPEUR=X', False),   # direct, no inversion needed
```

---

## 11. `features/feature_store.py` — `load_prices_from_db()`

### 🟡 Reconstructed prices are relative, not absolute
```python
prices = np.exp(log_returns.cumsum())
```
This reconstructs a relative price index starting at 1.0, not the actual EUR prices. Momentum features use `prices.shift(skip) / prices.shift(lookback + skip) - 1` — this ratio is correct regardless of the price level. RSI also uses `series.diff()` which is level-dependent: on a price index starting at 1.0, `diff()` values are very small (e.g. 0.001 instead of 1.50 EUR), which affects the EWM smoothing convergence slightly but not the RSI ratio. Technically fine for RSI, but the function is misleadingly named and documented.

---

## 12. `alpha/ml_alpha.py` — AUC confidence scaling

### ⚪ AUC rescaling ceiling is too low for good models
```python
confidence = min(max((auc - 0.5) * 4, 0.01), 1.0)
```
An AUC of 0.75 (genuinely excellent for equity ML) maps to `(0.75 - 0.5) * 4 = 1.0`. An AUC of 0.65 maps to `0.60`. In practice, AUC above 0.65 is rare in equity returns — so the effective range used is `[0.01, 0.60]`, with `1.0` essentially unreachable. This is fine numerically but the scaling comment (`[0.5, 0.75] → [0, 1]`) should be in the code so the intent is clear.

---

## 13. Missing: No `__init__.py` wiring for `execution/` and `reconciliation/`

### 🟠 Both subdirectories have `__init__.py` but no pycache
`execution/` and `reconciliation/` have no `__pycache__` directories, meaning they have never been imported / run. The `scheduler.py` never calls either module. There is no step in the pipeline that:
- Generates and logs the order queue to the DB
- Runs reconciliation

These modules exist but are disconnected from the pipeline entirely.

---

## 14. `db/schema.sql` — `alpha_signals` table never used

### 🟠 Dead table
The `alpha_signals` table is defined in the schema and has `ic_21d`, `ic_63d`, `ic_252d` columns — clearly intended for IC tracking. But nothing in the codebase writes to it. The `signals` table is used instead, but its IC columns (`ic_21d`, `ic_63d`, `ic_252d`) are also never written. Rolling IC is computed on the fly each time from `raw_score` vs forward returns — meaning every IC calculation re-runs the full lookback query from scratch.

---

## 15. `scheduler.py` — No BL / optimizer step in the daily pipeline

### 🟠 The core portfolio construction loop is absent
The scheduler runs: ingest → features → alpha signals → screens. It never calls:
- `run_black_litterman()` 
- `optimize_with_bl()`
- `run_pre_trade_checks()`
- `generate_order_queue()`
- `run_post_trade_risk()`

The full signal → weights → orders → risk loop is implemented in `portfolio/` and `risk/` but is never wired into the scheduler. The pipeline produces signals but never produces a portfolio.

---

## Summary Table

| # | File | Severity | Issue |
|---|------|----------|-------|
| 1 | `alpha/base.py` | 🔴 | `INTERVAL` syntax crashes SQLite in `compute_rolling_ic()` |
| 2 | `alpha/base.py` | 🟡 | `is_live_approved()` uses `confidence` (AUC) instead of IC |
| 3 | `alpha/base.py` | 🔴 | Same `INTERVAL` bug in `is_live_approved()` |
| 4 | `alpha/base.py` | 🟡 | IC floor hides negative IC, masks bad models |
| 5 | `screens/etf_divergence.py` | 🔴 | `pd.np` removed in modern pandas; numpy re-imported in loop |
| 6 | `portfolio/black_litterman.py` | 🟠 | `compute_view_omegas()` defined but never called |
| 7 | `execution/order_manager.py` | 🔴 | `ticker = "UNKNOWN"` hardcoded in all trade inserts |
| 8 | `reconciliation/state_reconciler.py` | 🔴 | `DISTINCT ON` is PostgreSQL-only, breaks SQLite |
| 9 | `reconciliation/state_reconciler.py` | 🟡 | `cash_match` always hardcoded `TRUE` |
| 10 | `risk/pre_trade.py` | 🟡 | `metric_name`/`metric_value` don't exist on `risk_events` table |
| 11 | `data/ingestion.py` | 🟡 | `GBPUSD=X` inverted ≠ GBP→EUR rate |
| 12 | `features/feature_store.py` | 🟡 | `load_prices_from_db()` returns relative index, not actual prices |
| 13 | `alpha/ml_alpha.py` | ⚪ | AUC ceiling comment missing; effective range unclear |
| 14 | `execution/`, `reconciliation/` | 🟠 | Both modules never called from scheduler |
| 15 | `db/schema.sql` | 🟠 | `alpha_signals` table defined but never written to |
| 16 | `scheduler.py` | 🟠 | BL → optimizer → pre-trade → orders → post-trade loop entirely absent |
