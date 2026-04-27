# Algorithm Tuning & Maintenance Log

**Document Purpose:** Quantitative strategies fail when they are tweaked emotionally or impulsively. This log serves as the strict, permanent record for every change made to the engine. Before modifying any parameter in `config.py` or `rules_engine.py`, you must document the change here with mathematical reasoning.

**The Golden Rule:** No parameter changes without explaining "Why?" in this log. "The market looks bad today" is NOT a valid rationale.

---

## Log Entry Template

Use this template for every parameter change:

```
---
**Date:** [YYYY-MM-DD]  
**Initiated By:** [Your name]  
**Component Changed:** [e.g., Lookback Period, Ticker Added, Min Trade Size]  
**Previous Value:** [e.g., 504 days]  
**New Value:** [e.g., 252 days]  
**Reason Category:** [Mathematical | Operational | Risk Management | Market Regime]  
**Mathematical / Logical Rationale:** [2-3 sentences explaining exactly why this change was necessary. Cite portfolio performance metrics, TR policy changes, or fundamental shifts.]  
**Data Supporting Decision:** [Specific numbers: e.g., "Correlation between Apple and MSFT rose from 0.4 to 0.8 due to tech sector selloff; concentration risk increased 35%"]  
**Approval:** [Self-approval for non-critical changes; requires review if major]  
**Reversal Condition:** [When/if would you undo this? E.g., "If correlation returns below 0.6"]  
```

---

## Maintenance History

### Entry 1: Initial System Deployment (V1.0 Live)

---
**Date:** 2026-03-25  
**Initiated By:** Portfolio Builder  
**Component Changed:** Initial System Architecture Lock  
**Previous Value:** N/A (Inception; system did not exist)  
**New Value:** V1.0 System Live with all baseline parameters  
**Reason Category:** Operational / Deployment  
**Mathematical / Logical Rationale:**  
Deployed the quantitative engine in advisory mode for Trade Republic. Initial parameters are based on 18 months of theoretical optimization and institutional best practices for mid-cap ETF rebalancing. Capital starting at €100 (test phase). All rules locked unless empirical data contradicts optimization.

**Data Supporting Decision:**  
- 6-asset universe selected for maximum diversification (correlation matrix shows ~0.4 avg correlation)
- 25% max weight constraint prevents single-stock concentration (empirical: unconstrained 2-year optimization was pushing 68% into one asset)
- 5% drift threshold balances transaction costs (€1/trade on €100 = severe) vs rebalancing accuracy
- €25 minimum trade size caps fee drag at 4% per execution

**Approval:** Self-approved (first deployment)  
**Reversal Condition:** Major market structure change or TR policy shift (e.g., fees).

---

### Entry 2: [Future Entry Template]

---
**Date:** [YYYY-MM-DD]  
**Initiated By:** [Your name]  
**Component Changed:** [What changed?]  
**Previous Value:** [Old parameter]  
**New Value:** [New parameter]  
**Reason Category:** [Mathematical | Operational | Risk Management | Market Regime]  
**Mathematical / Logical Rationale:**  
[Explain why...]

**Data Supporting Decision:**  
[Numbers...]

**Approval:** [Approved by whom?]  
**Reversal Condition:** [When would you undo this?]

---

## Parameter Change Checklist

Before submitting a change, verify:

- [ ] Change is NOT emotional ("market looks sad today")
- [ ] Change is based on empirical data or fundamental shift
- [ ] Mathematical rationale is documented above
- [ ] Previous value is recorded (for reversal if needed)
- [ ] Reversal condition is specified (how to undo)
- [ ] Change does not conflict with other rules
- [ ] TUNING-LOG.md entry is written before code is modified
- [ ] Code change (config.py) reflects this log entry exactly
- [ ] System tested after change (verify dashboards still work)

---

## Running Metric Monitors (Check Monthly)

These metrics help you identify if the engine needs tuning:

### Portfolio Health
- Sharpe Ratio: Should stay 0.8-1.5 (below 0.5 = investigate)
- Max Drawdown: Should stay < -40% (above -60% = mode failure)
- Win Rate: Should stay > 40% (below 30% = investigate)

### Rebalancing Efficiency
- Average days between rebalances: Should be ~14 days (1st & 3rd Friday)
- Average trade size when executed: Should be €25-€100 (< €25 = suppressed by rule)
- Profit Factor: Should stay > 1.4 (below 1.5 = strategy fragile)

### System Integrity
- Data gaps in historical_prices.csv: Should be zero (daily close is required)
- Correlation matrix stability: Should change < 10% day-to-day (if > 20% jump, alert)
- Drift threshold compliance: 100% of rebalanced trades should have drift > 5%

---

## Known Issues & Watchlist

### Issue 1: Fee Drag on Small Portfolio
**Status:** Acknowledged (baseline parameter)  
**Impact:** Every €1 trade = 1% on €100 portfolio  
**Mitigation:** €25 minimum trade size (caps at 4%); use Sparpläne for regular buys  
**Resolution:** Scale capital to €5,000+; then adjust MIN_TRADE_SIZE to 2% of portfolio value

**Related Entry:** Entry 1 (Initial Deployment)

---

### Issue 2: Correlation Regime Breaks
**Status:** Monitor  
**Warning Signs:** Correlation matrix suddenly shifts (all assets correlating > 0.9)  
**Cause:** Market crashes or sector rotation  
**Response Protocol:**  
1. Check 200-day MA filter — are assets falling below?
2. If yes, optimizer will automatically zero-out those assets
3. If no, but correlation spiked, check if another structural change occurred
4. If truly concerned, manually override to "Minimum Variance" portfolio scenario

**Current Fix:** None needed (200-day MA handles most cases)

---

### Issue 3: Spillover from Universe B/C (Crypto, Macro)
**Status:** Planned (not yet implemented)  
**Description:** Universe A (equities) has separate optimizers from Universe B (crypto) and Universe C (safe haven)  
**Risk:** If crypto highly volatile, don't let it affect equity weights  
**When to Address:** After V1.0 scales successfully to €5,000

---

## Audit Trail: Parameter Snapshots

### Current Production Parameters (2026-03-25)

```python
# From config.py
ASSET_UNIVERSE = ['APC.DE', 'MSF.DE', 'SAP.DE', 'ALV.DE', 'MOH.DE', 'EUNL.DE']
LOOKBACK_DAYS = 504  # 2 years
MAX_WEIGHT = 0.25  # 25%
MIN_TRADE_EUR = 25.00
RISK_FREE_RATE = 0.02  # 2%
REBALANCE_FREQUENCY = [1, 3]  # 1st & 3rd Friday
DRIFT_THRESHOLD = 0.05  # 5%
TREND_FILTER_MA_PERIODS = 200  # 200-day SMA
THREE_SCENARIOS = True  # Display Max Sharpe, Min Var, Max Return
```

---

## Decision Tree: When to Tune What

```
Is portfolio underperforming MSCI World? (Information Ratio < 0)
├─ YES → Check:
│  ├─ Are correlations too high? (> 0.8 avg)
│  │  └─ If YES: Add non-correlated asset (temporarily add gold)
│  ├─ Is risk too high? (Sharpe < 0.5)
│  │  └─ If YES: Lower lookback to 1 year to catch recent market shifts
│  └─ Are fees too high? (# of trades > 1 per week)
│     └─ If YES: Increase drift threshold from 5% to 7%
│
└─ NO → No change needed; engine working as designed

---

Is Sharpe Ratio declining? (was 1.2, now 0.8)
├─ YES → It's likely:
│  ├─ High volatility period (check rolling vol)
│  ├─ Or assets entered bear regime (check 200-day MA filter)
│  └─ Wait 2 weeks; if persists, check correlations
│
└─ NO → No change needed

---

Portfolio value crossed €5,000 threshold?
├─ YES → MANDATORY ACTION:
│  ├─ Update config.py: MIN_TRADE_EUR = portfolio_value * 0.02
│  ├─ Log change in TUNING-LOG.md (Entry #X)
│  ├─ Restart engine
│  └─ Test dashboard loads
│
└─ NO → Continue monitoring
```

---

## Communication Protocol

If you make a parameter change:

1. **Write the TUNING-LOG.md entry FIRST** (before touching code)
2. **Update config.py** (code reflects log)
3. **Test the system** (verify dashboards work)
4. **Document in README.md** (if major change affects user experience)

Example workflow:
```
Step 1: Edit this file (TUNING-LOG.md)
        Add Entry #X with rationale and data

Step 2: Run tests
        python -m pytest  # If you set up tests

Step 3: Edit config.py
        Change MIN_TRADE_EUR = 25 → MIN_TRADE_EUR = 500  # (example on €25k portfolio)

Step 4: Restart engine
        python run_engine.py
        Verify dashboard loads, no crashes

Step 5: Document if needed
        Edit docs/02-STRATEGY-RULES.md if the rule itself changed
```

---

> **This log is the chain of custody for every decision made. It prevents drift, ensures reproducibility, and creates accountability. A healthy quantitative system has a thick tuning log—evidence of thoughtful iteration, not emotional tweaking.**
