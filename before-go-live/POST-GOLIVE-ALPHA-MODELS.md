> **STATUS: POST GO-LIVE (BLOCKED BY PHASE 4.1)**
> These are independent Alpha Models for the Black-Litterman optimizer.
> They cannot be built right now because they rely on fundamental data (ROE, Debt, EPS estimates).
> Currently, pulling fundamental data from Yahoo Finance for a SaaS violates their ToS.
> Once Phase 4.1 of the Final Checklist is complete (switching to a paid provider like Polygon.io or EODHD), these models can be immediately built.

# Post Go-Live Alpha Models

This document preserves the mathematical logic for two highly effective Alpha Models that will be added to the portfolio optimizer once a paid fundamental data provider is secured.

---

## 1. Quality Factor Alpha Model
**Concept:** High-quality companies (high Return on Equity, low Debt/Equity, and stable earnings) systematically outperform. This model is explicitly **regime-conditional**: it receives higher weight during Risk-Off regimes.

**Logic:**
```python
quality_score = (0.4 × roe_rank) + (0.4 × low_leverage_rank) + (0.2 × earnings_stability_rank)
```
- `roe_rank` = cross-sectional rank of Return on Equity (within sector)
- `low_leverage_rank` = cross-sectional rank of (1 / debt_to_equity)
- `earnings_stability_rank` = cross-sectional rank of consistency of earnings_growth

**Return Scale:** ±2.5% annualised excess.
**Regime Integration:** 
- Risk-Off: scale return by 1.4x (Quality shines in fear)
- Risk-On: scale return by 0.7x (Quality lags in momentum rallies)

---

## 2. Earnings Revision Momentum
**Concept:** When Wall Street analysts revise their earnings estimates upward, stocks tend to outperform for 3–6 months. Analysts are slow to update their models, creating a persistent drift.

**Logic:**
- Signal: change in `(forward_eps / trailing_eps)` since the reading 4 weeks ago.
- Positive revision (analysts raised estimates) → Buy signal.
- Negative revision (analysts cut estimates) → Sell signal.

**Return Scale:** ±3.5% annualised excess.
**Complementarity:** This captures *pre-announcement* drift, perfectly complementing the existing PEAD model which captures *post-announcement* drift.

---

## Implementation Prerequisites
1. Subscribe to a commercial fundamental data API.
2. Build `engine/data/fundamental_ingestion.py` to fetch this data weekly and write to a new `fundamental_data` table.
3. Build `engine/alpha/quality_factor.py` and `engine/alpha/earnings_revision.py`.
4. Add them to `models` array in `step_alpha_signals()`.
