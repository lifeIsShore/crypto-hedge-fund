# Hedge Fund Capability Brainstorm
# What You Have, What You're Missing, What to Build Next

---

## Honest Assessment: Can This Run a Hedge Fund?

Short answer: **Not yet, but it's closer than most retail quant setups.**

Here is the precise gap between what you have and what a real fund needs.

---

## What you have (and it's genuinely good)

| Layer | What exists | Quality |
|-------|-------------|---------|
| Data | yfinance + 3 backup APIs, FX conversion, validation | ✅ Solid |
| Features | Momentum (1/3/6/12m), RSI, Vol 21/63d, Vol-of-Vol | ⚠️ Thin |
| Alpha models | Momentum, Mean Reversion, Vol Timing, PEAD, ML ensemble, LSTM | ✅ Good range |
| Signal gating | IC gate (MIN_IC=0.05, 21-day sustained), AUC gate (0.53) | ✅ Correct |
| Portfolio construction | Black-Litterman + IC-scaled Omega + Constrained optimizer | ✅ Institutional |
| Risk | Pre/post trade, VaR/CVaR, stress tests, regime detection | ✅ Solid |
| Execution | Manual order queue, confirmation loop, ledger reconciliation | ✅ Appropriate |
| Observability | Pipeline logs, health page, alerting digest structure | ⚠️ Unconfigured |
| Dashboard | Flask, live reconstruction, 12 pages of analytics | ✅ Strong |

---

## The Honest Gap List

These are NOT sci-fi. These are things real funds use that you don't have yet.
Ordered from highest to lowest impact on your actual returns.

---

### GAP 1 — Feature Starvation (Biggest Gap)

You have 8 features per ticker. Professional funds use 50–200.
Your BL views are built on: momentum ranks, RSI, and vol ratio.
That's a thin foundation for 130 tickers across 12 sectors.

**What's missing:**

**Price-based (all computable from your existing `prices` table):**
- `mom_1w` — 5-day momentum (captures very short reversals that 1-month misses)
- `mom_9m` — fills the gap between 6m and 12m
- `beta_rolling` — 63-day beta vs benchmark (you compute this in stress tests but don't store it as a feature)
- `rsi_21` — medium-term RSI complements 14-day
- `bb_width` — Bollinger Band width = `(upper - lower) / mid`. Compression before breakout.
- `price_to_52w_high` — distance from 52-week high (documented return predictor)
- `atr_14` — Average True Range, normalised by price. Better risk measure than vol alone.
- `vol_skew` — asymmetry of return distribution (negative skew stocks underperform)
- `realized_to_implied_vol_ratio` — when options imply more vol than realised, mean reversion tends to follow (requires options data — skip for now)

**Fundamental (requires separate data source — see Gap 2):**
- `pe_ratio`, `pb_ratio`, `ps_ratio`
- `earnings_surprise_pct` (you have this in PEAD but not in the main feature store)
- `revenue_growth_yoy`
- `free_cash_flow_yield`

**Macro (you have regime labels but not raw macro features per ticker):**
- `ticker_vs_sector_momentum` — relative momentum within sector (not vs whole universe)
- `sector_momentum_rank` — which sectors are leading, which are lagging

All price-based features above can be added to `engine/features/feature_store.py`
in a single session. Document in `FEATURE-ROADMAP.md`.

---

### GAP 2 — No Fundamental Data

Every alpha model you have is purely technical/quantitative — price and volume only.
This is a significant blind spot. A company with terrible momentum but great
fundamentals is a genuine opportunity your system cannot see.

**What you need:** A free or cheap fundamental data source.
Options ranked by data quality vs cost:

1. **yfinance `.info` dict** — free, already in your stack. Gives P/E, P/B, EPS,
   revenue, market cap, debt/equity for most tickers. Unreliable on European stocks.
   No API limit. Start here.

2. **FRED (you already have the key)** — macro fundamentals only (not per-ticker),
   but excellent for: 10Y yield, HY spread, VIX, PMI, CPI. You use some of these
   in regime detection but they're not in the per-ticker feature store.

3. **Financial Modeling Prep (FMP)** — €15/month for 250 tickers. Best quality
   per-ticker fundamental data available at this price point. Has European stocks.
   Gives: EPS surprise, free cash flow, revenue growth, debt ratios.

4. **Twelve Data** — you already have a key. Add fundamental endpoints.

Without fundamentals, your system will systematically miss value plays and
will be blindsided by earnings disasters it could have avoided with a quick
debt/equity check.

---

### GAP 3 — No Earnings Calendar Integration

Your PEAD engine reacts to earnings after they happen. But a real edge is
knowing WHEN earnings are coming so you can:
1. Reduce position size before earnings (to avoid unhedged binary risk)
2. Prepare the PEAD setup trade the moment numbers drop

**What's missing:**
An earnings calendar feed that writes upcoming earnings dates to a DB table.

```sql
CREATE TABLE earnings_calendar (
    ticker          TEXT NOT NULL,
    report_date     TEXT NOT NULL,
    report_time     TEXT,    -- 'BMO' (before market open) or 'AMC' (after close)
    eps_estimate    REAL,
    revenue_estimate REAL,
    PRIMARY KEY (ticker, report_date)
);
```

Free source: yfinance `ticker.calendar` dict. Unreliable but free.
Better: Finnhub `/calendar/earnings` endpoint (you have the key).

This feeds three things:
1. Pre-earnings position sizing (reduce by 30% 3 days before report)
2. PEAD engine trigger (automatic, not manual)
3. Risk event logging ("NVDA reports in 2 days — reduce exposure")

---

### GAP 4 — No Sector-Relative Signals

Your momentum model ranks ALL tickers together — NVD.DE competes with RWE.DE.
This means a semiconductor in a general market downturn looks terrible on
momentum rank even if it's the best semiconductor stock.

**What's missing:** Intra-sector ranking.
`sector_relative_momentum` = ticker's rank within its sector, not the whole universe.

This is a 30-line addition to `feature_store.py` that would significantly
improve the quality of your momentum and mean-reversion signals, especially
in sector-rotation regimes.

---

### GAP 5 — No Position Sizing Model Beyond Kelly

You have Half-Kelly in the schema (`kelly_half` in `price_targets`) but it's
not used for order sizing in `order_manager.py`. The order manager uses
`delta_weight * portfolio_value` as order size — which is optimizer-output only.

A proper sizing model layers Kelly on top of the optimizer:
`final_size = optimizer_weight * kelly_scalar * regime_scalar`

Where:
- `kelly_scalar` = Half-Kelly fraction based on historical win rate of the signal
- `regime_scalar` = 0.6 in Risk-Off regimes, 1.0 in Risk-On (you have this data)

This is the difference between a system that "suggests good trades" and one
that "sizes positions correctly for risk."

---

### GAP 6 — Correlation Risk Not Managed

You have a correlation heatmap on the pairs page. But the optimizer doesn't
penalise you for holding highly correlated positions.

Example: Holding NVD.DE + AMD.DE + QCI.DE + TSM.DE is four semiconductor
positions that will all drop 15% together if there's a chip export restriction.
The sector cap (30%) helps, but four positions at 7% each = 28% in semis,
all correlated at 0.85+.

**What's missing:** Concentration-within-correlation-cluster penalty.
Run k-means or hierarchical clustering on the correlation matrix.
Limit any single cluster to 25% regardless of sector labels.

This is a 50-line addition to `optimizer.py`.

---

### GAP 7 — No Trade Journal / Decision Log

You have an `override_log` table. But it only captures the numbers
(what weight the model suggested, what weight you chose). It doesn't
capture the reasoning in a structured way.

A proper trading journal links:
- The specific override decision
- The macro context at the time (VIX, regime, yield spread)
- The model's IC trend at the moment of override
- Your stated reason (macro event, technical resistance, earnings risk)
- The outcome 30 and 90 days later

Your `override_log` has `outcome_30d` and `outcome_90d` columns — they're
never populated. The backfill logic doesn't exist yet.

**Why this matters:** In 12 months you'll have 50+ override decisions.
Without outcome tracking, you can't learn whether your overrides add value.
If your overrides are systematically wrong, you're paying yourself to hurt
your returns. If they're right, you know where your genuine edge is.

---

## New Alpha Models to Build (Not Sci-Fi, All Implementable)

### Alpha 6 — Earnings Revision Momentum
**Concept:** When analysts revise their EPS estimates upward, stocks tend
to outperform for 3-6 months. This is one of the most robust documented
anomalies in academic finance.
**Source:** yfinance `ticker.info['earningsGrowth']` or FMP EPS revision endpoint.
**Signal:** `eps_revision_3m` = change in consensus EPS estimate over 3 months.
**Strength:** Largely uncorrelated with price momentum — adds genuine diversification.

---

### Alpha 7 — Insider Transaction Signal
**Concept:** Corporate insiders (CEO, CFO, board members) must file
transactions publicly. Clusters of insider buying (multiple insiders,
not just one) strongly predict positive 6-month returns.
**Source:** SEC EDGAR Form 4 filings (US stocks only). Free.
OpenInsider.com has a free JSON API.
**Signal:** `insider_net_buy_3m` = net insider buy/sell value over 3 months,
normalised by market cap.
**Strength:** Forward-looking signal not captured by any price-based model.
Works on US stocks (which is ~40% of your universe).

---

### Alpha 8 — Short Interest Signal  
**Concept:** High short interest + price strength = potential short squeeze.
Low short interest = no crowd bearishness = lower return variance.
**Source:** FINRA reports short interest twice monthly for US stocks.
yfinance `ticker.info['shortRatio']` and `shortPercentOfFloat`.
**Signal:** `short_ratio_change` = change in short ratio over 1 month.
Increasing shorts on a rising stock = contrarian buy signal (squeeze setup).
Decreasing shorts on a falling stock = capitulation signal.

---

### Alpha 9 — Options Flow Asymmetry (Simple Version)
**Concept:** When call volume significantly exceeds put volume (unusual options
activity), it often precedes positive price moves. Not because options predict
the future — but because institutional players use options to hedge or speculate
BEFORE their large equity trades.
**Source:** yfinance `ticker.option_chain()` for near-term expiries.
**Signal:** `put_call_ratio` = put volume / call volume (inverted = bullish when low).
**Cost:** Free via yfinance. Works best for US large-caps.
**Note:** This is a sentiment/flow signal, not price prediction. Use as a
secondary confirmer, not a primary signal.

---

### Alpha 10 — Quality Factor (Low Leverage, High ROE)
**Concept:** The "Quality" factor is one of the five Fama-French factors.
High Return on Equity + Low Debt/Equity = quality company that tends to
outperform in Risk-Off regimes and preserve capital in crashes.
**Source:** yfinance `.info` dict has `returnOnEquity`, `debtToEquity`.
**Signal:**
```
quality_score = (roe_rank * 0.5) + (low_leverage_rank * 0.5)
```
where ranks are cross-sectional within sector.
**Why now:** In Risk-Off regimes (which your regime engine detects),
rotate toward high-quality stocks. This is directly actionable via
your existing regime-conditional BL views.

---

## What Makes a Fund a Fund (Operational Gaps)

These are not code features. They're operational requirements.

### 1 — Risk Policy Document
Before going live, you need one document that answers:
- What is the maximum loss I will accept before stopping trading? (e.g., -20% drawdown)
- What is my rebalance frequency and why?
- Under what conditions do I override the model? (written rules, not instinct)
- What is the maximum position size? (currently coded as 10% — is this deliberate?)
- What is my benchmark and time horizon?

This doesn't need to be long. One page. But having it written forces
clarity and prevents emotional decisions during drawdowns.

### 2 — Drawdown Protocol
Your system has no drawdown-triggered behaviour. At -10%, -15%, -20%
portfolio drawdown, what changes? Options:
- Reduce gross exposure (sell some positions to cash)
- Increase cash buffer
- Pause the pipeline (stop generating new orders)
- Alert only (monitor more closely)

Decide this in advance. During a drawdown is the worst time to decide.

### 3 — Liquidity Check Before Each Trade
For each trade in the order queue, verify:
`trade_value_eur / (avg_daily_volume * price_eur) < 0.05`

If your order is more than 5% of the average daily volume, you will move
the price against yourself. This matters at portfolio sizes above ~€50,000
in less liquid positions (small-cap European stocks, mining stocks).

### 4 — Tax-Aware Selling (Abgeltungsteuer)
Since you're using Trade Republic in Germany:
- Capital gains tax is 25% + solidarity surcharge = ~26.4%
- Selling a position held < 12 months triggers full tax
- Selling a position held > 12 months still triggers the same tax
  (Germany has no long-term capital gains exemption unlike the UK/US)

This means: your optimizer should penalise selling positions that have
unrealised gains, because the tax drag reduces the actual realised alpha.
The simplest implementation: add a `tax_penalty` column to `override_log`
that estimates the after-tax cost of each suggested sell.

---

## Priority Order for New Features

| Priority | Feature | Time | Alpha Impact |
|----------|---------|------|-------------|
| 1 | Add 8 more price features to feature_store | 1 day | High — better signals immediately |
| 2 | Earnings calendar integration (Finnhub) | 1 day | High — pre-earnings risk management |
| 3 | Sector-relative momentum ranking | 2 hours | Medium-High — cleaner signals |
| 4 | Populate outcome_30d/90d in override_log | 1 day | Medium — learning from decisions |
| 5 | Quality factor alpha (yfinance .info) | 1 day | Medium — uncorrelated signal |
| 6 | Drawdown protocol (coded rules) | 2 hours | High — capital protection |
| 7 | Correlation cluster constraint in optimizer | 3 hours | Medium — risk reduction |
| 8 | Insider transaction signal (US stocks) | 2 days | Medium — uncorrelated |
| 9 | Fundamental data (FMP or yfinance .info) | 2 days | Medium — new dimension |
| 10 | EPS revision momentum | 2 days | Medium — robust anomaly |

---

## The Realistic 3-Month Roadmap

**Month 1 (After blocker fixes):**
- Feature expansion (8 → 20 features)
- Earnings calendar wired in
- Sector-relative signals
- Drawdown protocol written and coded
- Override outcome tracking working

**Month 2:**
- Quality factor alpha
- Fundamental data integration
- Correlation cluster constraint
- Tax-aware selling penalty
- Full paper-trading sandbox running

**Month 3:**
- Insider signal (US stocks)
- EPS revision momentum
- Review sandbox results vs benchmark
- Go live with documented risk policy

At the end of month 3, you have a genuine quant fund setup. Not a hedge fund
in the regulatory sense — but a systematic, evidence-based, risk-managed
investment process that most retail investors and many small family offices
would not be able to replicate.
