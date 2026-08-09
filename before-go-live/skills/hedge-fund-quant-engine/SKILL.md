---
name: hedge-fund-quant-engine
description: >
  Deep context for the Control Tower hedge-fund quant engine codebase.
  Use when working on the Python pipeline (engine/scheduler.py), alpha models,
  database schema, Flask backend (flask_app.py), or any bug-fix / feature work
  in this project. Provides architecture, conventions, known gotchas, and roadmap
  priority so the agent doesn't repeat solved problems or break working invariants.
---

# Hedge Fund Quant Engine — Skill

## Project location
`C:\Users\ahmty\Desktop\hedge-fund\`  
Entry points: `RUN_FUND_TOTAL.bat` (full pipeline), `DASHBOARD_ONLY.bat` (Flask UI only).

---

## Architecture overview

```
engine/
  scheduler.py          ← 14-step canonical pipeline (run_pipeline())
  alpha/                ← ML models: ensemble, LSTM, PEAD, pairs
  db/db.py              ← SQLAlchemy session factory → engine_data.db (SQLite)
  execution/
    order_manager.py    ← BL-weight → order queue (verify end-to-end before live use)
flask_app.py            ← Flask dashboard, ~3 100 lines, all DB reads via _q()/_exec()
engine_data.db          ← Single SQLite file, all state lives here
shared/state_paths.py   ← Canonical path constants (ML_STATE_PATH, REGIME_STATE_PATH…)
```

**Not in scope:** `portfolio/recalculate_engine.py` — deprecated, writes to legacy JSON cache no longer read by the UI. Header says so. Don't call it.

---

## Pipeline: 14 steps in run_pipeline()

| # | Step function | What it does |
|---|---|---|
| 1 | step_ingest | Download OHLCV via yfinance, persist to `prices` table |
| 2 | step_fx | Fetch EUR/USD FX rate → `fx_rates` table |
| 3 | step_features | Compute 24 technical features → `feature_store` (EWM, RSI, BBands, vol, momentum) |
| 4 | step_ml_train | Ensemble ML (LightGBM/RF/LogReg) → `ml_state.json` (AUC, up_proba per ticker) |
| 5 | step_regime | Macro regime classification → `regime_history_new` + `regime_state.json` |
| 6 | step_pead | Post-earnings drift detection → `pead_setups` table |
| 7 | step_pairs | Pairs cointegration screen → results in DB |
| 8 | step_alpha_signals | Ensemble alpha → `signals` + `alpha_signals` tables |
| 9 | step_bl_views | Black-Litterman views from alpha signals |
| 10 | step_risk | Monte Carlo VaR/CVaR → `risk_metrics` table |
| 11 | step_portfolio_construction | BL portfolio weights → `model_outputs` table |
| 12 | step_price_targets | 1σ price targets, Kelly sizing → `price_targets` table |
| 13 | step_performance_log | Daily portfolio value snapshot → `performance_history` |
| 14 | step_push_signals_to_queue | Auto-populates `signal_queue` with high-conviction signals for HITL review |

Weekly-only (Mondays): step_lstm_train (walk-forward LSTM re-train).

---

## Database — key tables and row counts (as of 2026-08-04)

### User-owned (exported by export_data.py)
| Table | ~Rows | Purpose |
|---|---|---|
| trades | 26 | Trade ledger (BUY/SELL, price, qty, fee) |
| positions_history | 104 | Daily position snapshots |
| cash_history | 42 | Cash balance events |
| signal_queue | live | HITL review inbox — pending/approved/skipped/expired |
| watchlist | live | Tickers under surveillance before queuing |
| divergence_labels | 48 | ETF-divergence human labels with outcomes |
| saved_portfolios | 1 | Portfolio Lab saved scenarios |
| performance_history | 54 | Daily portfolio value + benchmark |
| override_log | 0 | Human override audit trail (structured capture) |

### Pipeline-derived (not exported — re-computed on next run)
`prices` (198k rows), `feature_store` (229k rows), `signals` (2.9k), `model_outputs`, `price_targets`, `pead_setups` (134), `regime_history`, `fx_rates`, `risk_metrics`

---

## Conviction scoring formula (used in Highlighted tab + HITL queue)

```python
conviction = up_proba × auc × (1 + rr_ratio) × regime_mult × pead_boost × vol_score
```

- `regime_mult`: 1.2 if Risk-On, 0.8 if Risk-Off, else 1.0
- `pead_boost`: 1.15/1.08/1.03 for HIGH/MEDIUM/LOW quality PEAD setup
- `vol_score`: 1.1 if 15% ≤ vol_ann ≤ 40%, 0.8 if vol_ann > 60%, else 1.0
- AUC gate: skip ticker if AUC < 0.53
- Thresholds: ≥ 0.70 = HIGH, 0.55–0.70 = MEDIUM, < 0.55 = LOW, AUC < 0.53 = GATED

Short conviction:
```python
short_score = bear_proba × auc × rr_short × regime_mult_short × pead_boost
```
Only surface shorts when: Risk-Off regime OR transition_warning OR up_proba ≤ 0.38 OR bearish PEAD.

---

## Fixed bugs — do NOT re-introduce these

| Bug | Fix |
|---|---|
| Raw `.cov()` on covariance matrix | Ledoit-Wolf shrinkage via `sklearn.covariance.LedoitWolf` |
| MC seeds hardcoded to 0 | Seeds now drawn from `np.random.SeedSequence` |
| FX fallback hardcoded | DB-sourced from `fx_rates` table |
| `step_lstm_train()` defined twice | Duplicate removed — single definition remains |
| Rebalance no tolerance band | 2% band added — drift < 2pp doesn't trigger trade |
| Ticker key mismatches ASSET_UNIVERSE vs TICKER_SECTORS | Aligned at config level |
| Split-brain scheduler | `flask_app.py` weekly_refresh calls `engine.scheduler.run_pipeline()` directly; `recalculate_engine.py` deprecated |
| `signal_queue` never auto-populated | `step_push_signals_to_queue()` added as step 14 |

---

## Security / hard blockers status

| Item | Status |
|---|---|
| Plaintext API keys in `.env` | `.env.example` created; **Ahmet still needs to rotate all 4 keys + audit git history** |
| No Flask auth | `DASHBOARD_SECRET` env var now required; basic-auth gate added |
| `debug=True` in prod | Now gated on `FLASK_DEBUG=1` env var |
| Stray `fee_debug.log` write | Removed |
| `check_staleness()` never wired | Now called in ingestion step |
| Alerting | Code is correct; **Slack/SMTP credentials + Task Scheduler setup still needs Ahmet manually** |

---

## Known open items / gotchas

- **`order_manager.py` / execution layer never verified end-to-end** — no `__pycache__` evidence of ever being run. Do a dry-run/sandbox pass (I4: paper trading) before using with real capital.
- **Missing ADV liquidity gating** — no check that trade value < 5% of asset's average daily volume before entering order queue. Worth adding to `order_manager.py`.
- **yfinance ToS** — commercial/SaaS use of yfinance is against ToS. For hosted instances, budget for Polygon.io, Alpaca Data, or Financial Modeling Prep.
- **`SOS-button.md` is empty** — panic-sell/liquidate concept, no spec. Don't build without Ahmet's direction.
- **`how-desktop.md` — DO NOT IMPLEMENT** — PyInstaller/Inno Setup desktop packaging. Architecture is hosted containers, not desktop.

---

## Conventions

- All DB access in `flask_app.py` goes through `_q(sql, params)` (read) and `_exec(sql, params)` (write). Never bypass these.
- JSON state files (`ml_state.json`, `regime_state.json`) are read-only from Flask; written exclusively by the pipeline. Treat as eventual-consistent cache.
- The `_ensure_*_table()` pattern in `flask_app.py` means user tables (`signal_queue`, `watchlist`) are created lazily on first request — this is intentional.
- `engine/db/db.py:get_session()` returns a SQLAlchemy session. Always close in a `try/finally`. The pipeline uses this; Flask uses raw sqlite3 via `_q()`.

---

## Post-launch improvements (I1–I5) — pending

| # | Feature | File | Status |
|---|---|---|---|
| I1 | Light/cream theme | `I1-light-theme.md` | Not started |
| I2 | Signal explainability (proportional, not SHAP) | `I2-signal-explainability.md` | Not started |
| I3 | Circuit breakers / hard stop-loss per position | `I3-circuit-breakers.md` | Not started |
| I4 | Paper trading sandbox | `I4-paper-trading-sandbox.md` | Not started |
| I5 | Benchmark tracking overlay | `I5-benchmark-tracking.md` | Not started |

All spec files live in `before-go-live/`.

---

## Export/import
`export_data.py` — standalone CLI tool.  
`python export_data.py export` / `python export_data.py import <file>`  
Schema version: `1.0`. Exports 9 user-owned tables, skips 14 pipeline-derived tables.
