# Backtest History & Strategy Registry — TODO (COMPLETED & ARCHIVED)

> **Status**: ✅ **100% IMPLEMENTED** (Archived on 2026-08-20)

## The Problem We Solved

Every time `walk_forward.py` ran, it silently overwritten `backtest_results.csv`, `backtest_metrics.csv`, and `alpha_ic_results.csv`.
Now every backtest run generates an immutable, timestamped record in `backtests/runs/<run_id>/`, complete with full strategy parameter snapshots, git commit hash, and performance metadata.

---

## Core Ideas & Status

### 1. Timestamped CSV Outputs (Quick Win) — ✅ COMPLETED
Every backtest run produces **immutable, dated artifacts**:
```
backtests/runs/
  20260820_152600/
    backtest_results.csv
    backtest_metrics.csv
    alpha_ic_results.csv
    strategy_config.json     ← captures active alphas & params
    run_meta.json            ← timing, git hash, data range
```

Changes made:
- [x] `walk_forward.py`: accepts `--run-id` arg; defaults to `YYYYMMDD_HHMMSS`
- [x] `walk_forward.py`: writes all outputs into `backtests/runs/<run_id>/` folder
- [x] `metrics.py`: saves metrics to run folder when called from `walk_forward.py`
- [x] `alpha_eval.py`: accepts `--run-id` arg to output into run folder
- [x] Top-level flat CSVs kept as copies of latest run for backward compatibility

### 2. Strategy Config Snapshot (`strategy_config.json`) — ✅ COMPLETED
At the moment of the run, captures *exactly* which alpha generators were used and with what parameters.

Changes made:
- [x] Extracted all constants into `strategy_config.json` snapshot
- [x] Writes `strategy_config.json` at the start of every run
- [x] Created `backtests/registry.py` helper with `list_runs()`, `load_run(run_id)`, `append_index()`, `update_note()`

### 3. Run Registry / Index (`runs_index.csv`) — ✅ COMPLETED
A lightweight CSV at `backtests/runs/runs_index.csv` that gets a new row appended after each run.

Changes made:
- [x] `walk_forward.py`: appends row to `runs_index.csv` after saving metrics
- [x] Includes Sharpe, CAGR, MDD, alpha combo, date ranges
- [x] Includes free-text `notes` field (passable via `--note "disabled ml_alpha"`)

### 4. Backtest UI — Date Picker & Run Browser — ✅ COMPLETED
Added `/backtest/history` route in `flask_app.py` and `backtest_history.html` template.

#### 4a. Run Selector — ✅ COMPLETED
- [x] Table of all runs from `runs_index.csv`
- [x] Shows timestamp, date range, Sharpe, CAGR, MDD, active alphas
- [x] Clicking a run opens the drawer with full metrics + equity curve + IC table

#### 4b. Side-by-Side Comparison — ✅ COMPLETED
- [x] Select **two runs** and display metrics in a diff-style table
- [x] Highlights superior metric in green

#### 4c. Equity Curve Overlay — ✅ COMPLETED
- [x] Charts multiple runs' equity curves on the same graph (normalised to 100)
- [x] Toggle individual runs on/off
- [x] Benchmark shown once (dashed)

#### 4d. Alpha IC Viewer — ✅ COMPLETED
- [x] Displays `alpha_ic_results.csv` table for selected run (21d horizon)
- [x] Color-codes by ICIR: green > 0.5, yellow 0.3–0.5, red < 0.3

#### 4e. Search by Date — ✅ COMPLETED
- [x] Date-range filter: filter runs by `From` and `To` market period dates

#### 4f. Notes & Tags — ✅ COMPLETED
- [x] Editable `notes` column directly in the UI (PATCH endpoint `/api/backtest/run/<run_id>/note`)

---

## File Layout Implemented

```
backtests/
  registry.py                ← NEW: load_run(), list_runs(), append_index(), update_note()
  runs/
    runs_index.csv           ← NEW: one row per run, key metrics
    20260820_152600/
      backtest_results.csv
      backtest_metrics.csv
      alpha_ic_results.csv
      strategy_config.json   ← NEW
      run_meta.json          ← NEW
  walk_forward.py            ← MODIFIED: writes to runs/<run_id>/
  metrics.py                 ← MODIFIED: output into run folder
  alpha_eval.py              ← MODIFIED: accepts --run-id arg
```
