# Backtest History & Strategy Registry — TODO

## The Problem We're Solving

Every time `walk_forward.py` runs, it silently overwrites:
- `backtest_results.csv`
- `backtest_metrics.csv`
- `alpha_ic_results.csv`

So yesterday's run is gone. If market conditions change and the current strategy
underperforms, we have no quick way to say "let me go back to the June 2026 run —
what alphas did I use and what were the metrics?" This TODO addresses exactly that.

---

## Core Ideas

### 1. Timestamped CSV Outputs (Quick Win)
Every backtest run should produce **immutable, dated artifacts**. Instead of
overwriting flat files, emit:

```
backtests/runs/
  20260820_152600/
    backtest_results.csv
    backtest_metrics.csv
    alpha_ic_results.csv
    strategy_config.json     ← NEW: captures what alphas were active
    run_meta.json            ← NEW: timing, git hash, data range
```

Changes needed:
- [ ] `walk_forward.py`: accept optional `--run-id` arg; default = `YYYYMMDD_HHMMSS`
- [ ] `walk_forward.py`: write all outputs into `backtests/runs/<run_id>/` folder
- [ ] `metrics.py`: also write into the same run folder when called from `walk_forward.py`
- [ ] `alpha_eval.py`: same — output into run folder
- [ ] Keep the top-level flat CSVs as symlinks/copies of the **latest** run (backward compat)

### 2. Strategy Config Snapshot (`strategy_config.json`)
At the moment of the run, capture *exactly* which alpha generators were used and with
what parameters. This is the "what I used to build this strategy" memory.

Fields to capture:
```json
{
  "run_id": "20260820_152600",
  "run_timestamp": "2026-08-20T15:26:00Z",
  "backtest_start": "2023-06-01",
  "backtest_end": "2026-08-20",
  "git_commit": "abc1234",
  "initial_capital": 10000.0,
  "benchmark": "EUNL.DE",
  "alphas_active": [
    {"name": "momentum",       "confidence": 0.05, "return_scale": 0.04},
    {"name": "sector_momentum","confidence": 0.04, "return_scale": 0.03},
    {"name": "mean_reversion", "confidence": 0.03, "return_scale": 0.02},
    {"name": "vol_timing",     "confidence": 0.03, "return_scale": 0.02},
    {"name": "ml_alpha",       "confidence": 0.05, "return_scale": "dynamic"}
  ],
  "optimizer_params": {
    "max_position": 0.15,
    "turnover_penalty": 0.002,
    "slippage_pct": 0.001,
    "tau": 0.05,
    "risk_aversion": 2.5
  },
  "warmup_days": 273,
  "rebal_weekday": 0,
  "risk_free_rate": 0.04
}
```

Changes needed:
- [ ] Extract all constants from `walk_forward.py` and `metrics.py` into this snapshot
- [ ] Write `strategy_config.json` at the **start** of every run
- [ ] Add helper `backtests/registry.py` with `list_runs()`, `load_run(run_id)` functions

### 3. Run Registry / Index (`runs_index.csv`)
A lightweight CSV at `backtests/runs/runs_index.csv` that gets a new row appended after
each run — making it easy to scan history without reading every folder:

```
run_id,timestamp,start_date,end_date,sharpe_port,cagr_port,mdd_port,alphas,notes
20260820_152600,2026-08-20T15:26:00Z,2023-06-01,2026-08-20,1.42,+18.3%,-12.1%,mom+sec+mr+vt+ml,""
20260715_093000,2026-07-15T09:30:00Z,2023-06-01,2026-07-15,1.31,+16.1%,-14.2%,mom+sec+mr+vt,""
```

Changes needed:
- [ ] `walk_forward.py`: after saving metrics, append row to `runs_index.csv`
- [ ] Include key metrics: Sharpe, CAGR, MDD, alpha combo, backtest date range
- [ ] Include a free-text `notes` field (passable via `--note "disabled ml_alpha"`)

### 4. Backtest UI — Date Picker & Run Browser
In `flask_app.py`, add a new `/backtest` UI section (or extend the existing one) that:

#### 4a. Run Selector
- [ ] Dropdown / table of all runs from `runs_index.csv`
- [ ] Show timestamp, date range, Sharpe, CAGR, MDD, active alphas at a glance
- [ ] Clicking a run loads its full metrics + equity curve

#### 4b. Side-by-Side Comparison
- [ ] Select **two runs** and display their metrics in a diff-style table
- [ ] Highlight which metric is better in green
- [ ] Key for quickly comparing "current strategy vs 3-months-ago strategy"

#### 4c. Equity Curve Overlay
- [ ] Chart multiple runs' portfolio_value curves on the same graph (normalised to 100)
- [ ] Toggle individual runs on/off
- [ ] Show benchmark once (not per-run)

#### 4d. Alpha IC Viewer
- [ ] For the selected run, display `alpha_ic_results.csv` as a table
- [ ] Show IC mean / ICIR / hit rate per alpha model per horizon
- [ ] Color-code by ICIR: green > 0.3, yellow 0.1–0.3, red < 0.1
- [ ] Easy to see "in this run, ml_alpha was the main driver; in the previous run momentum dominated"

#### 4e. Search by Date
- [ ] Date-range filter: show only runs that covered a specific market period
- [ ] E.g., "show me all backtests that include 2024-Q3 so I can compare how each strategy handled that drawdown"

#### 4f. Notes & Tags
- [ ] Editable `notes` column directly in the UI (PATCH to update `runs_index.csv`)
- [ ] Tag runs (e.g., "no_ml", "tight_turnover", "v2_optimizer") for quick filtering

---

## Implementation Order (Priority)

| # | Item | Effort | Value |
|---|------|--------|-------|
| 1 | Timestamped run folders + `run_meta.json` | S | High — never lose a run again |
| 2 | `strategy_config.json` snapshot | S | High — answers "what was active?" |
| 3 | `runs_index.csv` append | S | High — enables all UI features |
| 4 | `registry.py` helper module | S | Medium — shared loader for UI |
| 5 | Flask UI: run browser table | M | High — main UI value |
| 6 | Flask UI: equity curve overlay | M | High — visual comparison |
| 7 | Flask UI: side-by-side metrics diff | M | Medium |
| 8 | Flask UI: alpha IC viewer per run | M | High — strategy memory |
| 9 | Flask UI: date search | S | Medium |
| 10 | Flask UI: notes/tags editable | S | Low-medium |

S = Small (< 1h), M = Medium (2-4h)

---

## File Layout After Implementation

```
backtests/
  registry.py                ← NEW: load_run(), list_runs(), append_index()
  runs/
    runs_index.csv           ← NEW: one row per run, key metrics
    20260820_152600/
      backtest_results.csv
      backtest_metrics.csv
      alpha_ic_results.csv
      strategy_config.json   ← NEW
      run_meta.json          ← NEW
    20260715_093000/
      ...
  walk_forward.py            ← MODIFIED: writes to runs/<run_id>/
  metrics.py                 ← MODIFIED: accepts output_dir param
  alpha_eval.py              ← MODIFIED: accepts output_dir param
```

---

## Open Design Questions

1. **Backward compat**: keep `backtest_results.csv` at root level as a copy of the
   latest run? Yes — `RUN_BACKTEST.bat` and any external scripts should not break.

2. **Git hash**: capture `git rev-parse HEAD` at run time so we can trace back
   to the exact code version. Fail gracefully if not in a git repo.

3. **Flask route**: new dedicated `/backtest/history` route, or integrate into
   the existing backtest section? Lean toward a new tab in the existing backtest page.

4. **Storage**: runs can accumulate. Add a `--keep N` flag to `walk_forward.py` that
   prunes runs older than the N most recent? Or leave cleanup manual?

5. **Alpha config editable via UI**: longer term, could we let the user toggle alphas
   on/off in the UI and trigger a new run? That's a bigger feature (Phase 2).
