# Trade Republic Systematic Portfolio: Strategy Rules & Mathematical Parameters

**Document Purpose:** This file defines the strict mathematical, logical, and execution rules for the Python-based quantitative trading engine. Reference this while coding `rules_engine.py` and `config.py`.

---

## 1. Core Identity & Objectives

* **Target Platform:** Trade Republic (Lang & Schwarz Exchange routing)
* **Base Currency:** EUR (€)
* **Time Horizon:** Medium-term (weekly/monthly rebalancing, not day trading)
* **Execution Model:** Manual advisory (Python computes signals; you execute on TR app)

### Primary Objective Function
Maximize the Sharpe Ratio (risk-adjusted return):

$$S = \frac{E[R_p] - R_f}{\sigma_p}$$

Where:
- $R_p$ = Portfolio expected return (or historical average)
- $R_f$ = Risk-free rate (2.00% TR cash yield)
- $\sigma_p$ = Portfolio standard deviation

### Secondary Objectives (Display Alternative Scenarios)
The engine also calculates and displays:
1. **Minimum Variance Portfolio** (defensive, capital preservation focus)
2. **Maximum Return Portfolio** (aggressive, growth focus)

User chooses which scenario to execute based on current macroeconomic conditions.

### Dividend Pooling & Cash Management
Dividends are strictly pooled as cash. When an asset (e.g., Allianz) pays a dividend, it is logged in `ledger.csv` as a cash addition. 
* **Rule:** Dividends are not automatically DRIP'd (Dividend Reinvestment Plan) into the asset that paid them. 
* **Mechanic:** They sit in the cash pile earning the 2.0% TR yield until the next Friday engine run, where the optimizer will naturally allocate that cash to whichever asset is mathematically most underweight.

---

## 2. Asset Universe: Sub-Portfolio A (Quality Equities)

All tickers sourced using **Xetra/Frankfurt (`.DE`) suffixes** to ensure EUR pricing matches Trade Republic exactly.

### The 6 Core Assets

| Ticker | Company | Sector | Why Included |
|--------|---------|--------|--------------|
| `APC.DE` | Apple Inc. | Technology | Global tech leader, high liquidity |
| `MSF.DE` | Microsoft Corp. | Technology/Cloud | Enterprise software, recurring revenue |
| `SAP.DE` | SAP SE | Software (German) | European champion, B2B focus |
| `ALV.DE` | Allianz SE | Insurance/Financials | Dividend yield, defensive |
| `MOH.DE` | LVMH | Luxury Consumer | Growth, different sector correlations |
| `EUNL.DE` | iShares Core MSCI World ETF | Diversified Global | Anchor asset for broad exposure |

### Additional Assets (Optional Future Universes)

**Universe B: Crypto Satellites** (max 10% allocation)
- Bitcoin, Ethereum, Solana
- Optimized separately due to extreme volatility
- Uncorrelated tail hedge

**Universe C: Macro / Safe Haven** (max 15% allocation)
- Gold ETCs (Xetra-Gold)
- Government Bond ETFs
- Shift to during bear market regimes

**Cash:** Uninvested euros held at TR (earning 2.00% p.a.)

---

## 3. The Mathematical Engine: Core Parameters

### Historical Data & Lookback

* **Lookback Horizon:** 2 Years (504 Trading Days)
  * Long enough for statistical significance (covariance matrix needs ≥2 years)
  * Short enough to forget outdated market regimes (2008 crash doesn't paralyze 2026 decisions)
  * Industry standard for mid-term quantitative portfolio management

### Returns Calculation

* **Log Returns:** $R_t = \ln(P_t / P_{t-1})$
  * Why logs? Time-additive, symmetric, better for quantitative modeling than simple percentage returns
  * Calculated daily, all analysis flows from daily log returns

### Risk-Free Rate

* **Hard-Coded:** `risk_free_rate = 0.02` (2.00% per annum)
* **Source:** Trade Republic's current rate on uninvested cash (ECB deposit facility rate pass-through)
* **Recalculated:** Annually (or if TR policy changes; log in TUNING-LOG.md)

### Volatility Annualization

* **Formula:** $\sigma_{annual} = \sigma_{daily} \times \sqrt{252}$
* **Assumption:** 252 trading days per year (industry standard)

---

## 4. Constraints & Risk Management

### Hard Constraints (Never Relaxed Without Written Rationale)

**Maximum Asset Weight**
* No single equity or ETF may exceed **25% of total portfolio**
* **Why:** Prevents "corner solutions" where optimizer dumps 90% into best-performing asset
* **Effect:** Forces diversification, reduces concentrated risk

**Minimum Asset Weight**
* 0% allowed (can fully exit an asset)
* **Why:** Allows defensive positioning (e.g., exit Apple if it breaks trend)
* **Caveat:** No short selling (Trade Republic restriction)

**Portfolio Composition**
* Must sum to exactly 100% (all capital allocated, 0 unallocated)
* Cash is a valid asset class (up to 100% cash for defensive positioning)

### The Regime Filter: 200-Day Moving Average (Trend Detection)

**Logic:** Binary trend classification using the 200-day Simple Moving Average (SMA)

**Rule:**
- If `Current Price > 200-day SMA` → Asset in **BULL REGIME** (usable in optimization)
- If `Current Price ≤ 200-day SMA` → Asset in **BEAR REGIME** (optimizer sets weight to 0%)

**Effect:**
- Avoids holding assets in downtrends
- Shift capital to cash or defensive assets when trends turn negative
- Systematic alternative to emotional "stop losses"

**Why 200-day?**
- Industry standard for medium-term trend identification
- Avoids whipsawing on daily noise
- Approximately 10 months of trading data (meaningful price history)

**Implementation Caveat:**
- When asset enters BEAR regime at 10:00 AM, don't immediately panic-sell
- Regime filter applies at next rebalancing cycle (1st or 3rd Friday)
- Prevents emotional mid-week tilts

### Data Reliability: The 15% Sanity Gate

**The Rule:** If any asset's daily adjusted closing price moves more than **±15%** in a single day, the engine triggers a "Data Anomaly Halt".
**Why:** Free data sources (`yfinance`) occasionally fail to instantly adjust for stock splits or special dividends. A 4-for-1 split looks like a 75% crash to a naive algorithm, causing it to panic-sell based on a broken 200-day moving average.
**Effect:** When tripped, the dashboard flashes a `⚠️ DATA ANOMALY DETECTED` warning and refuses to output trade signals until the user manually verifies the price action. Always use `Adj Close` to minimize these occurrences.

---

## 5. Rebalancing Logic: Opportunistic Execution

### Time-Based Checking (Systematic Schedule)

**Trigger Dates:** 1st and 3rd Friday of each month
- Automatic, non-negotiable schedule
- Prevents emotional "I feel bad today, let me rebalance" tweaks
- Gives predictable rhythm (every ~2 weeks)

### Threshold-Based Execution (Asymmetric Drift)

**The Asymmetric Thresholds:**
To minimize the German tax drag (*Abgeltungsteuer*) on realized capital gains, the engine uses asymmetric drift thresholds:
* **Buy Threshold (5%):** An asset must drift 5% below its optimal weight to trigger a "Buy" signal.
* **Sell Threshold (7%):** An asset must drift 7% above its optimal weight to trigger a "Sell" signal.

**Why Asymmetric?**
Selling winners triggers immediate capital gains tax (~26.375%), bleeding capital out of the compounding system. By giving winners more room to run (7%), we defer taxes. We are stricter on buying losers (5%) to quickly scoop up value.

**Cash Flow First (Tax-Aware Rebalancing):**
Before generating a "Sell" signal, the engine attempts to rebalance via Cash Flow. If Apple is 6% overweight, but you have unallocated cash (from dividends or Sparpläne deposits), the engine will instruct you to buy the underweight assets *first* to dilute Apple's percentage back to normal, avoiding the taxable sell event entirely.

### Combined: Opportunistic Rebalancing

1. **Check on schedule:** 1st and 3rd Friday
2. **Measure drift:** Calculate current vs optimal for each asset
3. **Apply threshold:** Only trade if asymmetric drift thresholds are breached (5% buy / 7% sell)
4. **Generate signal:** "Rebalance required" (if threshold breached) OR "Hold" (if not)

---

## 6. Transaction Friction & Capital Scaling Caveats

### The €1 Trade Republic Fee Model

Trade Republic charges **€1 per transaction** (manual buy or sell order), regardless of trade size.

**Impact on €100 Portfolio:**
- €1 fee = 1% of capital per trade (severe drag)
- If you trade weekly, fees alone are 50% per year (unsustainable)

### Mitigation Strategy 1: Minimum Trade Size Rule

**Hard Rule:**
- Even if the 5% drift threshold is breached, suppress the signal if the required trade size is < **€25**
- **Why:** €1 fee on €25 trade = 4% cost (manageable, but acknowledged)
- **Rule:** €1 fee on €8 trade = 12.5% cost (unacceptable)

**Effect:**
- Forces discipline on only trading meaningful rebalancing amounts
- Caps fee drag at 4% per execution (much better than 12%)

### Mitigation Strategy 2: Savings Plan Loophole

Use Trade Republic's free **Sparpläne (Savings Plans)** for regular monthly buys:
- Sparpläne are free (€0 fee)
- No minimum amount required
- Perfect for dollar-cost averaging into positions

**Recommendation in Dashboard:**
- "Consider using Sparplan to deposit €50/month to SAP.DE (saves €1 fee)"

### Mitigation Strategy 3: Capital Scaling Critical Path

**Scaling Rule (Smooth Curve):**
To avoid a jarring logic break at exactly €5,000, the engine uses a dynamic `MAX` function to determine minimum trade size:
`MIN_TRADE_EUR = max(25.00, portfolio_value * 0.005)`

* At €100: Min trade is €25 (hard floor).
* At €5,000: Min trade is €25.
* At €10,000: Min trade smoothly scales to €50.
This keeps fee drag permanently capped at ≤ 4% without requiring you to manually edit the config file as you cross arbitrary thresholds.

---

## 7. Rebalancing Triggers: The Three Scenarios

The portfolio optimizer calculates and displays **three distinct model portfolios**:

### Scenario 1: Maximum Sharpe (The Balanced Benchmark)
- **Objective:** Maximize risk-adjusted return
- **Result:** The "default" portfolio unless market conditions warrant otherwise
- **When to use:** Normal market conditions, no major geopolitical events
- **Risk profile:** Moderate

### Scenario 2: Minimum Variance (The Defensive Play)
- **Objective:** Minimize volatility (capital preservation priority)
- **Result:** Heavy on low-volatility assets, high cash allocation
- **When to use:** Market stress, rising recession fears, geopolitical crises
- **Risk profile:** Low (but also low return potential)

### Scenario 3: Maximum Return (The Aggressive Play)
- **Objective:** Maximize expected return (growth priority)
- **Result:** Pushes limits on best-performing assets, minimal cash
- **When to use:** Strong bull market, low recession risk, personal high risk tolerance
- **Risk profile:** High (but higher return potential)

**How You Use This:**
- Friday dashboard shows all three scenarios
- You (as CEO) choose which one to execute based on your macro view
- Engine is advisory team; you are the decision-maker
- Never force the engine to pick; you always have the final say

---

## 8. UI / Dashboard Aesthetic Guidelines

To prevent "dashboard fatigue" and maintain clarity, the Streamlit frontend adheres to strict visual hierarchy:

### Design Aesthetic: Ligne Claire (Clear Line) Principles
- **Inspiration:** European illustration tradition (Hergé's Tintin, ligne claire comics)
- **Applied to UI:** Strong, continuous black outlines of equal width around key elements
- **Effect:** Crisp, high-contrast information hierarchy

### Visual Architecture
- **Colors:** Flat, vividly saturated colors (no heavy shading, no gradients)
  - Vivid teal for growth indicators (up trends, wins)
  - Vivid crimson for risk indicators (drawdowns, losses)
  - Flat mustard yellow for neutral/cash elements
  - Stark white or off-white backgrounds
- **Typography:** Sans-serif, high contrast, readable from across room
- **Texture:** Very subtle dotted/Risograph-style background to add character without glare
- **Density:** Spacious; never pack data tightly

### Specific Component Design

**Scorecards (Top Row):**
- Thick black borders (2-3px)
- Flat, distinct background color per card
- Large, bold numbers
- Subtext in grey

**Action Board (Center):**
- Vivid accent color border (yellow or green)
- Translate all mathematical complexity into plain English
- Single, clear sentence: "No action required" OR "Buy €30 SAP, Sell €20 AAPL"

**Charts (Bottom):**
- Plotly interactive visualizations
- Flat colors matching the palette
- No unnecessary 3D effects or shadows

---

## 9. Operational Rules: What Never Changes Without Rationale

| Rule | Value | Can Be Changed? | Process |
|------|-------|-----------------|---------|
| Lookback window | 2 years | Very rarely | Document in TUNING-LOG.md with statistical analysis |
| Risk-free rate | 2.0% | Yearly or if TR changes | Update config.py, log in TUNING-LOG.md |
| Max weight | 25% | Rarely | Explain in TUNING-LOG.md why corner solutions were risk |
| Min trade size | Dynamic (Max of €25 or 0.5%) | Scaling only | Auto-trigger at €5K threshold, log change |
| Drift threshold | Asymmetric (5% Buy / 7% Sell) | Rarely | Analysis needed on fee efficiency vs accuracy |
| Rebalance frequency | 1st & 3rd Friday | Rarely | Explain why systematic was changing to emotional schedule |
| Trend filter | 200-day MA | Very rarely | Explain statistical basis if modifying |

**Golden Rule:** No parameter changes without logging mathematical, logical, or systemic rationale in `TUNING-LOG.md`.

---

## 10. Risk Metrics: What "Good" Looks Like

These are the Key Performance Indicators tracked on the dashboard:

| Metric | Goal | Target | Warning |
|--------|------|--------|---------|
| Sharpe Ratio | Return per unit risk | > 1.0 | < 0.5 = investigate |
| Calmar Ratio | Return per unit pain | > 0.5 | < 0.3 = strategy weak |
| Max Drawdown | Worst-case loss | < -30% | > -50% = reassess risk |
| Information Ratio | Beat benchmark | > 0.2 | < 0 = underperforming MSCI |
| Profit Factor | Trade system health | > 1.5 | < 1.5 = too fragile |
| Win Rate | Trade success | > 40% | < 30% = investigate |

---

## 11. Final Checkpoint Before Implementation

Before coding `rules_engine.py` and `config.py`, verify:

- [ ] All 6 tickers locked: APC.DE, MSF.DE, SAP.DE, ALV.DE, MOH.DE, EUNL.DE
- [ ] Max weight 25% ← confirmed
- [ ] Minimum trade size dynamic floor ← confirmed
- [ ] Rebalance frequency 1st & 3rd Friday ← confirmed
- [ ] Drift threshold Asymmetric (5%/7%) ← confirmed
- [ ] Risk-free rate 2.0% ← confirmed
- [ ] Lookback window 2 years ← confirmed
- [ ] Trend filter 200-day MA ← confirmed
- [ ] Three scenarios (Max Sharpe, Min Variance, Max Return) ← will display all

**Status:** Ready to code implementation.

---

> **These rules are frozen. They do not change on impulse or emotional market reaction. Any future change must be logged with mathematical rationale in TUNING-LOG.md. This prevents strategy drift and maintains system integrity.**
