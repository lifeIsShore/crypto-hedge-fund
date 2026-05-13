# PEAD Engine — Post-Earnings Announcement Drift

**Priority 2** of the Quantitative Research Techniques implementation plan.

## What This Does

Screens every earnings event in your universe for **PEAD setups** — situations where the stock's initial reaction underpriced the earnings surprise, creating a statistically predictable drift over the following 21–63 days.

## Why It Works

When a company significantly beats estimates but the stock barely moves on earnings day, institutional investors haven't finished repositioning yet. Analyst upgrades, index rebalancing, and slow retail reaction create continued momentum for 30–90 days. This anomaly has been documented in academic finance since the 1960s and persists today.

## File Structure

```
pead_engine/
├── config.py             # All thresholds — edit only here
├── data_fetcher.py       # Earnings + price data, Xetra→NASDAQ mapping
├── regression_model.py   # Per-ticker surprise→reaction OLS regression
├── screener.py           # Setup screening + quality scoring
├── pead_db.py            # CSV log + JSON state + outcome backfill
├── run_engine.py         # CLI runner
├── requirements.txt
└── data/
    ├── earnings_cache.csv      # Cached earnings history
    ├── pead_prices.csv         # Cached price history
    ├── regression_models.json  # Per-ticker OLS coefficients
    ├── pead_setups.csv         # Append-only setup log
    └── pead_state.json         # Latest state → dashboard
```

## Setup & Running

**Note: This engine is fully integrated into the master pipeline.**
You do not need to run it manually. It executes automatically every weekend via `RUN_FUND_TOTAL.bat` at the project root.

If you need to run it manually for testing:
```bash
cd ml_quant_finance_research/quant_research/pead_engine

# Normal run (screen last 90 days of earnings)
python run_engine.py

# Force refresh all data
python run_engine.py --refresh

# Screen longer history (e.g. last 6 months)
python run_engine.py --lookback 180

# Rebuild regression models from scratch
python run_engine.py --backfill

# Only update drift outcomes for past setups (fast, no new screen)
python run_engine.py --outcomes
```

## Setup Quality Tiers

| Quality | Criteria |
|---------|----------|
| **High** | EPS surprise >5% + underreaction confirmed + (revenue beat OR volume confirmed) |
| **Medium** | EPS surprise >5% + underreaction confirmed |
| **Low** | EPS surprise >5% only — no underreaction data |

Only **High** and **Medium** setups are listed as actionable in `pead_state.json`.

## The Underreaction Test

For each ticker, we fit a regression on historical earnings:
```
same_day_return (%) = a + b × surprise_pct (%)
```

If `actual_move < predicted_move - 2%` → the stock underreacted → PEAD setup confirmed.

This is **per-ticker**, because TSLA's typical reaction to a 10% EPS beat is very different from KO's.

## Output: `pead_state.json`

```json
{
  "active_setups": [
    {
      "ticker": "AMZN",
      "direction": "bullish",
      "quality": "High",
      "surprise_pct": 12.4,
      "entry_date": "2026-05-09",
      "drift_window": 45,
      "underreaction": true,
      "reaction_gap": 4.2
    }
  ],
  "performance": {
    "overall_hit_rate_21d": 0.61,
    "high_avg_drift_21d": 3.8
  }
}
```

## Integration with Regime Engine

The PEAD engine automatically reads `../regime_engine/data/regime_history.csv` and attaches regime labels to every setup. This enables regime-stratified performance analysis:

```
Expansion + Risk-On → 21d hit rate: 68%
Contraction + Risk-Off → 21d hit rate: 41%
```

Run `regime_engine` first. PEAD runs fine without it (regime tagging is non-fatal).

## Entry Rules (from spec)

- **Do NOT enter on earnings day** — spreads are wide, direction can whipsaw
- Enter **2 trading days after** earnings (default, configurable in `config.py`)
- Exit at **63 days** post-earnings OR when next earnings approaches (within 2 weeks)
- Trail stop: if stock gives back **>50%** of post-earnings gain → reassess

## Sector Drift Windows

| Sector | Expected Drift |
|--------|---------------|
| Technology | 45–90 days |
| Healthcare | 30–60 days |
| Financials | 21–45 days |
| Consumer Staples | 21–30 days |
| Industrials | 30–60 days |

## Next: Technique 3 — Options Signals

Once PEAD has been running for at least 2 weeks and logging setups with outcomes, begin `quant-research/options_engine/`.
