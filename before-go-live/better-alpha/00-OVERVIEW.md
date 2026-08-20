> **STATUS: PLANNING ONLY. Do not touch any ML code until Gate 1 is passed.**
> Hard prerequisite: `backtest/02-alpha-ic-evaluation.md` must run first to establish baseline.

# Better Alpha — Master Planning Document

## What this folder is

A controlled roadmap for improving the ML alpha model without breaking what already works.
Three docs. Three phases. Each phase has explicit acceptance gates that must pass
before the next phase starts. The gates are not optional.

```
better-alpha/
  00-OVERVIEW.md          ← you are here (concerns, framework, gates)
  01-feature-additions.md ← Phase 1A/B/C: DB bridging + cross-sectional + technical
  02-target-refinement.md ← Phase 1D: Target Refinement (Predicting Alpha)
  03-panel-model.md       ← Phase 2: panel architecture (post-backtest decision)
```

---

## Current state of the ML system

**File:** `ml_quant_finance_research/ml_research/stock_ml_lab/run_ml_pipeline.py`
**Architecture:** One model per ticker, trained on ~1,000 rows of that ticker's own history.
**Models:** LogisticRegression, RandomForest, XGBoost (walk-forward, 3 folds).
**Features (46–48 total, 7 families):**

| Family | Features | Count |
|---|---|---|
| Price | ret_1/5/10/21/63d, log_ret_1d, vol_21/63d, price_vs_ma50/200, dist_52w_high/low, gap_pct | 13 |
| Volume | rel_volume, volume_trend, obv_zscore, vol_price_div_up/down | 5 |
| Technical | rsi_14, macd_hist, macd_signal, bb_position, atr_norm, stoch_k | 6 |
| Fundamental | fund_pe, fund_pb, fund_ev_ebitda, fund_rev_growth, fund_gross_margin, fund_op_margin, fund_de, fund_fcf | 8 |
| Macro | macro_fed_funds, macro_cpi, macro_yield_curve, macro_dxy + others from parquet | ~6–8 |
| Options | opt_iv_atm, opt_iv_rv_spread, opt_iv_skew, opt_iv_change_5d, opt_pc_ratio | 5 |
| Short Interest | opt_short_pct, opt_short_ratio, opt_short_change | 3 |

**Feature selection (already live):**
- Stage 1: Variance threshold — drop features with var < 0.005
- Stage 2: Correlation dedup — drop one of any pair with |r| > 0.95 (keep higher variance)
- Stage 3: Importance gate — drop features with RF importance < 0.40/n_features (if ≥ 10 survive)

**Acceptance gate:** AUC < 0.53 → signal excluded from BL (in `ml_alpha.py`, line 32–33).

---

## The two concerns — fully articulated

### Concern 1: Overfitting

Stock ML data has an exceptionally low signal-to-noise ratio. A 21-day directional
prediction in equities is essentially a hard classification problem with ~52–54% theoretical
accuracy ceiling for good models on most stocks. This means:

- Small apparent improvements in AUC (0.53 → 0.57) can be entirely explained by
  chance, particularly with only ~1,000 training rows per ticker.
- The walk-forward already in the pipeline is the correct framework, but it does NOT
  protect against every form of overfitting. Specifically:

**Risk A — Temporal clustering of regime features**

Macro/regime features (`macro_risk_off`, `stress_score`, `macro_vix`) are identical
for all tickers on the same date. This violates a key assumption of cross-validation:
that validation observations are independent of training observations.

Example of the failure mode:
- Training period: 2022–2024 (contains bear + bull)
- Validation fold: 2024–2025 (bull)
- The model learns: "when macro_risk_on=1 → stocks go up" with high AUC in validation
- In 2026 bear market: macro_risk_on=0 but the model never learned what happens then
  because ALL its validation folds were in a bull regime
- Live performance collapses; you can't diagnose why because the signal came from
  a regime feature that looked powerful historically

Mitigation: require that each walk-forward fold spans at least one regime transition
(a period where the dominant regime state changes). Check this explicitly when
evaluating regime features. Also: regime features should be evaluated on IC
(cross-sectional rank correlation) not just AUC — if the regime feature is the same
for all tickers on a given day, it contributes zero IC by construction.

**Risk B — Multiple comparisons / data mining bias**

Testing 20 new features, selecting 8 that survive the importance gate, and reporting
the AUC of those 8 is a data mining procedure. The surviving features won a selection
lottery, not a skill competition. The AUC improvement is partially (sometimes entirely)
illusory.

This risk scales with the number of features tested. Adding families one at a time
and measuring IC *before* looking at AUC reduces this dramatically.

Example: you add 12 cross-sectional features. The importance gate keeps 4. You report
AUC = 0.581. Is this real? Maybe. But you also implicitly "tested" 12 features and
selected the winners. The true OOS AUC might be 0.555.

Mitigation: **a locked holdout set**. The last 6 months of price history
(approx 2026-02-01 to today) is never used during feature development. Feature
selection, importance gating, AUC measurement — none of it touches this window.
Only when the full feature set is finalised do you evaluate on the holdout *once*.
If AUC on holdout matches the walk-forward AUC within 0.01, the features are real.
If it drops more than 0.01, revert everything.

**Risk C — Cross-sectional rank look-ahead (survivorship bias)**

If you compute `cs_ret_21d_rank` using the full current universe (all 130 tickers),
but some of those tickers were only added to the universe *after* 2022, then the
2022 ranks include "future knowledge" — you're ranking against companies you didn't
know about yet in 2022.

In practice this is mild (your universe is stable) but it exists. When computing
cross-sectional ranks for historical periods, only include tickers that had price
data on that date with fewer than 5 consecutive NaN days.

**Risk D — Label contamination between horizons**

You train on `target_dir_21d` (21-day forward return). But the feature `ret_21d`
(21-day backward return) shares a 0-day overlap at the boundary — the last day of
the backward window is the first day of the forward window. This is a feature/label
correlation, not strictly a leak, but it inflates apparent momentum-model AUC.
It's already in your system and it's fine — just be aware that adding more backward-
overlapping features will keep inflating momentum AUC specifically.

---

### Concern 2: Overengineering

**The failure mode:**
1. You add 3 new feature families over 6 weeks
2. AUC improves: 0.558 → 0.591 (measured on walk-forward, before holdout)
3. System goes live with new features
4. Live IC drops from 0.045 to 0.021 over 8 weeks
5. You can't diagnose: is it the regime features? The cross-sectional features?
   The old features? A regime change in the market? The BL mixing parameters?
6. Each Saturday retraining overwrites the model weights — the old model is gone
7. You can't revert cleanly because you don't know which feature caused the regression

**Why this is real:**
The current pipeline doesn't version the exact feature set used per run.
It saves feature *importances* in the parquet but not the exact feature *names* used.
If you add 12 new features and some are dropped by the importance gate and some aren't,
the parquet doesn't tell you which 8 survived on which run.

**Structural mitigations (to be implemented before any feature additions):**

1. **Baseline freeze** — before touching `feature_builder.py`, run `02-alpha-ic-evaluation.md`
   and write the output to `alpha_ic_results_baseline_v1.csv`. This is the ground truth.
   Never overwrite this file.

2. **Feature set versioning** — add a `features_used` field to `ml_state.json` that records
   the exact list of feature column names used in the final training run. This costs 2 lines
   of code and makes debugging possible.

3. **Modular addition** — each new feature family is a self-contained function
   (e.g., `add_crosssectional_features()`, `add_db_regime_features()`). Each function
   has a single boolean flag in the pipeline config to enable/disable it. Disabling =
   commenting out one line. Not a refactor.

4. **No simultaneous addition** — one feature family at a time. Never add two families
   in the same pipeline version. If both families look good independently, add the
   better one first, measure for 2 weeks of Saturday runs, then consider the second.

5. **Panel model is a separate script** — it never replaces `run_ml_pipeline.py`.
   It runs in parallel as `run_ml_pipeline_panel.py` and writes to
   `ml_state_panel.json`. The live engine stays on the per-ticker pipeline until
   the panel model has 4 weeks of IC evidence showing it's better.

---

## The 5 acceptance gates — hard rules

These gates are ordered. Gate N must pass before Gate N+1 work begins.

---

### Gate 0 — Baseline Establishment (prerequisite, ~1 hour)

**What:** Run `backtest/02-alpha-ic-evaluation.md` (the IC evaluation script).
**Output:** `backtests/alpha_ic_results_baseline_v1.csv`

Record for each model at 21d horizon:
- `mean_ic`, `std_ic`, `icir`, `hit_rate`, `n_obs`

Also record per-ticker AUC from `ml_state.json` → compute mean and std across tickers.
Write to `better-alpha/baseline_v1_auc.txt` (simple text file, format below):

```
# Baseline v1 — recorded YYYY-MM-DD before any feature additions
mean_auc_xgb=0.572
std_auc_xgb=0.031
mean_auc_rf=0.563
mean_ic_momentum_21d=0.048
mean_ic_ml_alpha_21d=0.061
icir_ml_alpha_21d=0.72
```

**Pass condition:** this file exists. It cannot fail — it's a measurement step.
**Do NOT proceed to Phase 1 until this file exists.**

---

### Gate 1 — Holdout Lock (prerequisite, ~5 minutes)

**What:** Identify and document the holdout period. No code change needed — just a
documented rule.

**Holdout period:** The 126 most recent trading days in the prices table
(approximately 6 calendar months). Compute the exact cutoff date:

```python
from engine.db.db import get_session
from sqlalchemy import text
session = get_session()
dates = session.execute(text(
    "SELECT DISTINCT date FROM prices ORDER BY date DESC LIMIT 127"
)).fetchall()
HOLDOUT_START = dates[-1][0]  # 127th most recent date = start of holdout
session.close()
print(f"HOLDOUT_START = {HOLDOUT_START}")
```

Write `HOLDOUT_START` to `better-alpha/holdout_config.txt`.

**The rule:** `feature_builder.py`, `run_ml_pipeline.py`, and all IC evaluation
code must filter training data to `date < HOLDOUT_START`. The holdout period is
evaluated *once* at Gate 4. Never before.

**Pass condition:** `holdout_config.txt` exists with the exact date.

---

### Gate 2 — Feature Addition IC Test (per feature family)

**What:** For each new feature family:
1. Add the `add_*_features()` function to `feature_builder.py`
2. Enable it with a flag: `ENABLE_FAMILY_X = True`
3. Run `02-alpha-ic-evaluation.md` on the walk-forward window (pre-holdout only)
4. Compare IC results to baseline_v1

**Pass conditions (ALL must be met):**
- `mean_ic` at 21d horizon improves by **> +0.003** vs baseline_v1
  (example: baseline IC=0.048 → new IC must be > 0.051)
- `icir` does not decrease by more than 0.05 (stability must not worsen)
- Mean AUC across tickers improves by **> +0.003** vs baseline_v1
- The feature family, when disabled (`ENABLE_FAMILY_X = False`), exactly reproduces
  baseline_v1 AUC (confirming the addition is clean and reversible)

**Fail conditions — immediate rollback:**
- Mean IC *decreases* by any amount vs baseline_v1
- AUC variance across tickers *increases* by > 0.01 (model becomes less consistent)
- Any individual ticker AUC drops below 0.50 that was previously above 0.53
  (the feature is actively hurting some tickers)

**Record:** Update `better-alpha/gate2_results.csv` with one row per family tested:
```
family,mean_ic_before,mean_ic_after,delta_ic,icir_before,icir_after,auc_before,auc_after,result
```

---

### Gate 3 — Two-Week Saturday Live IC Observation

**What:** After a feature family passes Gate 2, run the live Saturday pipeline
(with the new feature enabled) for two consecutive Saturdays. Measure live IC
using `02-alpha-ic-evaluation.md` on the most recent 21-day forward return window.

**Why:** Gate 2 is on historical walk-forward. Live IC is on real future data.
They should agree. If they diverge, the feature is overfitted.

**Pass condition:**
- Live IC at 21d is within ±0.008 of the walk-forward IC from Gate 2
- Live AUC is within ±0.010 of walk-forward AUC from Gate 2

**Fail condition — rollback:**
- Live IC diverges by > 0.008 (feature is not generalising)
- Any ticker's AUC in `ml_state.json` drops below 0.50

---

### Gate 4 — Holdout Validation (once, at the end of all Phase 1 additions)

**What:** After all Phase 1 feature families that passed Gates 2 and 3 are combined,
run `02-alpha-ic-evaluation.md` on the holdout period only (`date >= HOLDOUT_START`).

**This evaluation runs exactly once. The holdout set is consumed by this evaluation
and cannot be reused.**

**Pass conditions:**
- Holdout IC is within -0.005 of walk-forward IC (small degradation is expected and OK)
- Holdout AUC is within -0.010 of walk-forward AUC

**Fail condition — revert ALL Phase 1 changes:**
- Holdout IC drops more than 0.010 below walk-forward IC
- Holdout AUC drops more than 0.010 below walk-forward AUC

If Gate 4 fails, ALL feature families added in Phase 1 are reverted simultaneously
by setting all `ENABLE_FAMILY_X = False`. The system returns to `baseline_v1`.
A post-mortem must identify which family caused the holdout degradation before
any feature additions are attempted again.

---

### Gate 5 — Panel Model Prerequisite (Phase 2 entry condition)

The panel model does NOT start until:

1. Gate 4 passes (Phase 1 features are validated on holdout)
2. The Phase 1 feature set has been running live for **at least 4 Saturdays**
3. `02-alpha-ic-evaluation.md` shows live IC ≥ baseline_v1 IC over those 4 weeks
4. `backtest/02-alpha-ic-evaluation.md` on the full history shows mean AUC ≥ 0.55 
   for the per-ticker models (if average AUC is still only 0.53–0.54, the per-ticker
   architecture may be the bottleneck and the panel model becomes higher priority)

**If condition 4 is not met:** proceed to Phase 2 (panel model) sooner.
**If condition 4 is met:** consider whether Phase 2 is worth the rewrite risk.

---

## Diagram: what happens if something goes wrong at each gate

```
Gate 0 fails → Impossible (measurement only)
Gate 1 fails → Impossible (documentation only)

Gate 2 fails for Family X:
  → Set ENABLE_FAMILY_X = False
  → Document failure in gate2_results.csv
  → Move to next family (or stop if no more candidates)
  → DO NOT touch baseline_v1

Gate 3 fails for Family X:
  → Set ENABLE_FAMILY_X = False immediately
  → Do not wait for next Saturday
  → Remove from candidate list
  → Investigate: is it noise, or a real regime shift?

Gate 4 fails:
  → Set ALL ENABLE_FAMILY_X = False
  → Return to baseline_v1 exactly
  → Run Gate 2 individually on each family to identify which one caused holdout failure
  → That family is permanently removed from candidacy
  → Remaining families may be re-tested in isolation

Gate 5 preconditions not met:
  → Panel model work does not start
  → No exception — this is a hard rule
```

---

## Phase overview

| Phase | What | Docs | Prerequisite |
|---|---|---|---|
| Phase 1A | Bridge DB signals to ML (regime, PEAD, earnings) | `01-feature-additions.md` §A | Gates 0, 1 |
| Phase 1B | Cross-sectional features + price acceleration | `01-feature-additions.md` §B | Phase 1A Gate 2+3 passed |
| Phase 1C | Richer technical features | `01-feature-additions.md` §C | Phase 1B Gate 2+3 passed |
| Phase 1D | Target Refinement (Predicting Alpha) | `02-target-refinement.md` | Phase 1C Gate 2+3 passed |
| Phase 2 | Panel model (architectural rewrite) | `03-panel-model.md` | Gate 5 |

Each phase within Phase 1 goes through its own Gate 2 and Gate 3 before the next
phase starts. Only at the end of all Phase 1 additions does Gate 4 (holdout) run.
