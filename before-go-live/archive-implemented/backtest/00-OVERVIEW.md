> **STATUS: IMPLEMENTED ✅** — 2026-08-20 (session 11). All four modules built, syntax-checked, imports verified.
> `walk_forward.py` · `alpha_eval.py` · `metrics.py` · `templates/backtests.html` · Flask routes — all live.

# Walk-Forward Backtest — Overview

Three separate modules, each buildable independently.
Read this doc first, then the three numbered docs below.

```
backtest/
  00-OVERVIEW.md              ← you are here
  01-engine.md                ← core walk-forward loop + data pipeline
  02-alpha-ic-evaluation.md   ← per-model alpha IC / factor analysis
  03-portfolio-metrics.md     ← full portfolio metrics + benchmark comparison
```

---

## The problem with naive backtesting of this system

This is a **BL optimizer + 6 trained alpha models + regime gating**. Each component
introduces a potential bias:

| Component | Bias risk | Mitigation |
|---|---|---|
| ML alpha (`ml_alpha.py`) | Trained on full history → future leakage if features include post-event data | Walk-forward: ML only sees data up to `t_train` |
| Momentum features | `mom_12m` uses 252d lookback — first valid date is ~2023-01 with 2022-01 start | Min warmup = 273 trading days (252 + 21 skip) |
| Ledoit-Wolf covariance | Trained on same window as optimizer inputs — no leakage concern (purely backward-looking) | N/A |
| BL priors (`market_weights`) | Equal-weight priors → same at every step, no leakage | N/A |
| Regime state | Macro regime uses VIX/yield curve snapshots — purely backward-looking | N/A |

**Critical rule: at each backtest date `t`, only data with `date < t` is visible.**
No forward fill, no future price references, no future ML labels.

---

## Data available

You have prices from 2022-01-01 in `engine_data.db`. After the momentum
warmup of 273 trading days, the backtest starts on approximately **2023-01-20**.
That gives ~600 backtest trading days (≈2.4 years) ending today.

**Benchmark**: `EUNL.DE` (iShares Core MSCI World) — already in DB, already
used by `step_performance_log()` in the scheduler.

---

## What we are NOT building

- No intraday simulation — EOD only, same as the live system
- No short selling — long-only, same as the live system
- No transaction cost model beyond what `optimize_with_bl()` already uses
  (SLIPPAGE_PCT=0.05%, TURNOVER_PENALTY=0.2%) — reuse those constants directly
- No parameter optimisation on the backtest window — that's curve-fitting.
  The live parameters stay fixed throughout.
- No ML retraining inside the loop (doc 01 explains why and what to do instead)

---

## Build order

1. `01-engine.md` first — the loop that produces a `backtest_equity` Series
2. `02-alpha-ic-evaluation.md` — can be built in parallel with 01, reads the same prices table
3. `03-portfolio-metrics.md` — depends on the equity Series from 01

Estimated total build time: **2–3 days** after a clean pipeline run.
