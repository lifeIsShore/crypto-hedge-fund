# Macro Regime Detection Engine

**Priority 1** of the Quantitative Research Techniques implementation plan.

## What This Does

Classifies every trading day across **three independent axes**:

| Axis | Labels |
|------|--------|
| Risk Appetite | Risk-On / Neutral / Risk-Off |
| Rate Environment | Easing / Neutral / Tightening |
| Growth Cycle | Expansion / Slowdown / Contraction / Recovery |

Combined into a **composite label** e.g. `RiskOn_Easing_Expansion` that tags every other signal in the research stack, so you know *when* each technique is reliable.

## File Structure

```
regime_engine/
├── config.py          # All thresholds — edit only here
├── data_fetcher.py    # FRED + yfinance data, caching
├── classifier.py      # Rules-based classification logic
├── regime_db.py       # CSV history + JSON state writer
├── run_engine.py      # Main runner (CLI entry point)
├── requirements.txt   # Dependencies
└── data/              # Auto-created on first run
    ├── fred_cache.csv       # Cached FRED macro data
    ├── regime_history.csv   # Append-only daily regime log
    └── regime_state.json    # Latest snapshot → dashboard
```

## Setup

```bash
cd quant-research/regime_engine
pip install -r requirements.txt
```

## Running

```bash
# Normal daily run
python run_engine.py

# Force FRED data refresh (ignores cache TTL)
python run_engine.py --refresh

# Full backfill — clears history and rebuilds from scratch
python run_engine.py --backfill
```

## Output: `regime_state.json`

The dashboard reads this file. Key fields:

```json
{
  "as_of_date": "2026-05-07",
  "regime_risk": "Neutral",
  "regime_rates": "Easing",
  "regime_growth": "Slowdown",
  "regime_composite": "Neutral_Easing_Slowdown",
  "transition_warning": false,
  "ew_active_count": 1,
  "current_streak_days": 14,
  "macro_snapshot": { "vix": 19.4, "yield_spread": 0.21, ... }
}
```

## Early Warning System

Fires when **2+ of these** trigger simultaneously:

- VIX rising from calm (<18) to stress (>22) within 14 days
- Yield curve flattening >20bps in 28 days
- HY credit spreads widening >50bps in 21 days
- Fed funds repricing >50bps in 28 days

## Signal Guidance Table (from spec)

| Growth | Risk | Laggard | PEAD | Short Squeeze | Corr Break |
|--------|------|---------|------|---------------|------------|
| Expansion | Risk-On | ✅ HIGH | ✅ HIGH | ✅ HIGH | ✅ HIGH |
| Slowdown | Neutral | 🟡 MOD | 🟡 MOD | 🟡 MOD | ❌ AVOID |
| Contraction | Risk-Off | ❌ AVOID | 🔴 LOW | ❌ AVOID | ❌ AVOID |
| Recovery | Risk-On | ✅ HIGH | 🟡 MOD | ✅ HIGH | ✅ HIGH |

## Integration with Other Techniques

Every other engine (PEAD, Options, Short Interest, etc.) will call:

```python
from regime_db import load_regime_history, stratify_by_regime

regime = load_regime_history()
results = stratify_by_regime(signal_df, regime, outcome_col="drift_21d")
```

This lets you answer: *"Was my PEAD signal actually accurate, or only during Expansion?"*

## Next: Technique 2 — PEAD Screen

Once this engine has been running for at least one week and `regime_history.csv` is populated, begin implementing the PEAD screen in `quant-research/pead_engine/`.
