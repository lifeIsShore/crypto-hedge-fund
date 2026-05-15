# Macro Regime Detection Engine

**Priority 1** of the Quantitative Research Techniques implementation plan.

## What This Does

Classifies every trading day across **three independent axes** for both **US and European (EU)** markets:

| Axis | Labels |
|------|--------|
| **Risk Appetite** | Risk-On / Neutral / Risk-Off |
| **Rate Environment** | Easing / Neutral / Tightening |
| **Growth Cycle** | Expansion / Slowdown / Contraction / Recovery |

Combined into a **composite label** (e.g., `RiskOn_Easing_Expansion`) that tags every signal in the research stack. This allows the system to filter for "regime-aware" signals.

## Multi-Region Support

The engine now distinguishes between US and EU regimes, using distinct regional thresholds for metrics like:
- **US:** VIX, 10Y-2Y Yield Spread, Fed Funds Rate, ISM PMI.
- **EU:** VSTOXX, STOXX-DAX Spread, ECB Main Refinancing Rate, Eurozone PMI.

## File Structure

```
regime_engine/
├── config.py          # Regional thresholds & FRED IDs
├── data_fetcher.py    # FRED + yfinance data, 4-tier fallback logic
├── classifier.py      # Rules-based classification (Regional aware)
├── regime_db.py       # CSV history + JSON state writer
├── run_engine.py      # Main runner (CLI entry point)
├── requirements.txt   # Dependencies
└── data/              # Auto-created on first run
    ├── fred_cache.csv       # Cached macro data
    ├── regime_history.csv   # Append-only daily regime log (US)
    ├── regime_history_eu.csv # Append-only daily regime log (EU)
    └── regime_state.json    # Latest snapshot → dashboard
```

## API Resilience: The 4-Tier Fallback

To ensure the "Go-Live" dashboard never displays empty data, the `data_fetcher` implements:
1. **Primary:** FRED Official API (via `.env` key).
2. **Secondary:** `yfinance` proxy (for VIX, Spreads, and some Rates).
3. **Tertiary:** Local Cache (`fred_cache.csv`) for recent values.
4. **Final Fallback:** Persistence of the last known valid regime state.

## Setup & Running

**Note: This engine is fully integrated into the master pipeline.**

If you need to run it manually:
```bash
cd ml_quant_finance_research/quant_research/regime_engine

# Normal daily run
python run_engine.py

# Force FRED data refresh (ignores cache TTL)
python run_engine.py --refresh

# Full backfill — rebuilds US and EU history from scratch
python run_engine.py --backfill
```

## Output: `regime_state.json`

```json
{
  "us": {
    "regime_risk": "Neutral",
    "regime_rates": "Tightening",
    "regime_growth": "Expansion",
    "composite": "Neutral_Tightening_Expansion"
  },
  "eu": {
    "regime_risk": "Risk-On",
    "regime_rates": "Neutral",
    "regime_growth": "Recovery",
    "composite": "RiskOn_Neutral_Recovery"
  },
  "early_warning_flags": 1,
  "as_of_date": "2026-05-15"
}
```

## Early Warning System

Fires when **2+ of these** trigger in a region:
- **Volatility Spike:** VIX/VSTOXX rising >20% in 14 days.
- **Inversion:** Yield curve (10Y-2Y) flipping negative.
- **Credit Stress:** Spreads widening >50bps in 21 days.
- **Rate Shock:** Sudden central bank repricing >50bps.

## Integration

Every other engine (PEAD, ML, Pairs) uses regional tagging to answer: *"Does this signal work in the current EU environment, or only in US Expansion?"*

---
**Next: Technique 2 — PEAD Screen**
Once `regime_history.csv` is populated, the PEAD engine will automatically stratify its hit rates by these regimes.
