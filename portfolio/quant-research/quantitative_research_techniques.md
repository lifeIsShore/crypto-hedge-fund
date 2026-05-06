# Quantitative Research Techniques — Implementation Plan

> **Scope:** Six additional signal layers to complement the laggard screen, ETF divergence monitor, and ML prediction notebook. Each technique is standalone but designed to connect into the broader research stack.

---

## Technique 1 — Options Market Signals

### Why This Works

The options market is where informed and institutional traders position before large moves. Buying stock is visible and slow — buying options is faster, cheaper, and harder to detect in real time. By the time a move shows up in the stock price, the options market has often been signaling it for days. This makes options flow one of the most reliable leading indicators available to retail-level researchers.

### Signal Types to Monitor

#### 1.1 Unusual Options Activity (UOA)

**Definition:** Volume on a specific contract exceeds its open interest, or total daily options volume for a ticker is significantly above its 20-day average.

**What it signals:** Someone is making a large directional bet. Not always right, but worth investigating.

**Implementation:**
- Pull daily options chain data per ticker using `yfinance` (basic) or `tradier API` (free tier, more reliable)
- Compute for each ticker daily: `total_call_volume / 20d_avg_call_volume` and same for puts
- Flag any ticker where either ratio exceeds 3.0 (3x normal volume) as a UOA event
- Log: ticker, date, call ratio, put ratio, which strikes were most active, expiry dates

**Interpretation rules:**
- Large call volume + out-of-the-money strikes + near-term expiry = aggressive bullish speculation
- Large put volume + out-of-the-money strikes + near-term expiry = hedging or bearish bet — check if it's a known earnings date first
- Large volume at in-the-money strikes = directional conviction, not speculation

#### 1.2 Implied Volatility vs. Realized Volatility (IV/RV Spread)

**Definition:** Implied volatility (IV) is what the market expects future volatility to be. Realized volatility (RV) is what volatility has actually been. The spread between them is informative.

**Signals:**
- IV significantly above RV (IV/RV > 1.3): market is pricing in fear or an expected event. Selling options is statistically favorable here (but has risk — do not do this without understanding options mechanics)
- IV significantly below RV (IV/RV < 0.8): market is complacent. A move may be coming that options aren't pricing in — watch closely
- IV suddenly spiking on a stock with no news: someone may know something — treat as a research trigger

**Implementation:**
- IV: pull from options chain (use at-the-money 30-day IV for consistency — this is the standard)
- RV: compute as 21-day rolling standard deviation of log returns, annualized: `RV = std(log_returns_21d) × sqrt(252)`
- Compute spread daily: `IV_RV_spread = IV_30d - RV_21d`
- Track trend of this spread over time per ticker — a rising spread (IV expanding faster than RV) is a warning signal

#### 1.3 Put/Call Ratio

**Definition:** Total put volume divided by total call volume for a ticker on a given day.

**Standard interpretation:**
- Ratio > 1.0: more puts than calls — bearish sentiment
- Ratio < 0.7: more calls than puts — bullish sentiment or complacency
- Contrarian interpretation: extremely high put/call ratios sometimes signal capitulation (everyone already bearish = bottom near)

**Implementation:**
- Compute per ticker daily from options chain data
- Track 5-day and 21-day rolling average to smooth noise
- Flag when ratio moves more than 2 standard deviations from its own 90-day average (relative rather than absolute threshold — each stock has its own normal range)

#### 1.4 Options Skew

**Definition:** The difference in implied volatility between out-of-the-money puts and out-of-the-money calls at the same delta (typically 25-delta).

**Formula:** `Skew = IV(25-delta put) - IV(25-delta call)`

**What it signals:**
- High positive skew (puts much more expensive than calls): market is paying heavily for downside protection — fear is elevated
- Low or negative skew (calls more expensive than puts): unusual bullish demand — gamma squeeze risk or strong upside speculation
- Skew compressing (normalizing from high levels): fear subsiding — often precedes a relief rally

**Implementation:**
- Requires options chain with full strike data
- Pull weekly (not daily — skew is a slower signal)
- Compare each ticker's current skew to its own 90-day average skew
- Flag significant deviations

### Data Sources for Options

| Source | Coverage | Cost |
|---|---|---|
| `yfinance` | Basic options chain (strikes, volume, OI, IV) | Free |
| Tradier API | Better real-time chain data, historical options | Free tier available |
| Unusual Whales | Pre-screened UOA alerts, flow analysis | Paid (~$50/month) |
| Market Chameleon | IV percentile, skew charts, earnings IV | Free basic tier |
| Barchart | Put/call ratios, volume data | Free basic tier |

**Recommended starting point:** `yfinance` for the chain, Market Chameleon for IV percentile context, Barchart for put/call ratios.

### Connection to Existing Research

- UOA event on a ticker already flagged by laggard screen → elevates conviction tier
- IV spike on a ticker in the ETF divergence monitor → potential Scenario 2 or 4 warning
- Low IV/RV spread on a laggard candidate → quiet setup, move may be imminent

### Output Format

For each flagged ticker, log to database:

| Field | Type | Description |
|---|---|---|
| `ticker` | string | Stock symbol |
| `signal_date` | date | Date of signal |
| `signal_type` | enum | UOA / IV_RV_spread / PCR / Skew |
| `signal_value` | float | The computed metric |
| `signal_zscore` | float | How many std devs from normal |
| `direction_implied` | enum | Bullish / Bearish / Neutral / Ambiguous |
| `expiry_focus` | date | Which expiry was most active (for UOA) |
| `notes` | text | Manual observation |
| `outcome_5d` | float | Auto-filled: stock return 5 days later |
| `outcome_21d` | float | Auto-filled: stock return 21 days later |

---

## Technique 2 — Post-Earnings Announcement Drift (PEAD)

### Why This Works

PEAD is one of the most extensively documented anomalies in academic finance. When a company reports earnings that significantly beat or miss expectations, the stock does not fully reprice immediately — it continues drifting in the direction of the surprise for 30–90 days afterward. This happens because:

- Institutional investors take time to adjust positions
- Analyst upgrades and target raises follow earnings, not lead them
- Retail investors react slowly to earnings complexity
- The market systematically underreacts to earnings surprises

This creates a predictable, systematic edge if screened correctly.

### Signal Definition

**Earnings Surprise %:**
```
Surprise = (Reported EPS - Consensus EPS Estimate) / |Consensus EPS Estimate| × 100
```

**PEAD Setup Criteria (all must be met):**
- Surprise > +5% (beat) for bullish drift, or < -5% (miss) for bearish drift
- Post-earnings stock reaction on the day was muted relative to the surprise (i.e., stock moved less than the surprise implied — the market underreacted)
- Volume on earnings day was above average (confirming real interest, not a thin-market reaction)
- No concurrent negative catalyst (guidance cut, management warning) that would offset the beat

### Measuring "Muted Reaction"

This is the key filter — PEAD only works when the initial reaction underprices the surprise.

**Method:**
1. Compute the historical relationship for each stock: for every past quarter, plot earnings surprise % vs. same-day stock move %
2. Fit a simple linear regression: `stock_move = a + b × surprise`
3. For the most recent quarter: if `actual_move < predicted_move` by a meaningful margin (>2%), the stock underreacted → PEAD setup confirmed
4. If actual move was in line with or exceeded predicted move → PEAD setup not present, skip

This per-stock regression is more accurate than using a fixed threshold because different stocks have different historical sensitivity to earnings surprises.

### Implementation Steps

**Step 1: Build Earnings Calendar**
- Source: `yfinance` has basic earnings dates. `Earnings Whispers` (earningswhispers.com) has more precise consensus estimates.
- Alternative: `Alpha Vantage` earnings API (free tier)
- Build a table: ticker, earnings date, reported EPS, consensus EPS, surprise %, same-day stock return

**Step 2: Compute Historical Surprise-Reaction Relationship**
- For each ticker, collect last 8–12 quarters of earnings data
- Run OLS regression: `same_day_return ~ surprise_pct`
- Store the slope coefficient (b) and intercept (a) per ticker
- Rerun quarterly as new data comes in

**Step 3: Flag PEAD Setups**
- After each earnings release, compute: `predicted_move = a + b × surprise`
- Compare to actual same-day move
- If `actual_move < predicted_move - 2%` and surprise > +5%: flag as PEAD bullish setup
- Log to database with timestamp

**Step 4: Define Entry Window**
- Optimal entry: 1–3 days after earnings (let initial volatility settle)
- Do NOT enter on earnings day itself — bid/ask spreads are wide and direction can whipsaw
- Drift window: monitor 21-day and 63-day returns from entry

**Step 5: Exit Rules**
- Take profit at 63 days post-earnings OR when next earnings date approaches (within 2 weeks)
- Exit immediately if a new negative catalyst appears
- Trail stop: if stock gives back >50% of the post-earnings gain, reassess

### PEAD + Revenue Surprise Combination

EPS surprises alone can be engineered (share buybacks, cost cuts). Revenue surprises are harder to fake. The strongest PEAD setups have both:

- EPS surprise > +5% AND
- Revenue surprise > +3% AND
- Gross margin stable or expanding

Setups with EPS beat but revenue miss are lower quality — the beat may not be sustainable.

### Sector Calibration

PEAD magnitude varies significantly by sector:

| Sector | Typical Drift Duration | Drift Magnitude |
|---|---|---|
| Technology | 45–90 days | High |
| Healthcare | 30–60 days | Medium-High |
| Financials | 21–45 days | Medium |
| Consumer Staples | 21–30 days | Low |
| Energy | 14–30 days | Variable (commodity-driven) |
| Industrials | 30–60 days | Medium |

Calibrate your drift window expectations by sector, not universally.

### Database Schema

| Field | Type | Description |
|---|---|---|
| `ticker` | string | Stock symbol |
| `earnings_date` | date | Reporting date |
| `reported_eps` | float | Actual EPS |
| `consensus_eps` | float | Analyst consensus |
| `surprise_pct` | float | Surprise as % |
| `revenue_surprise_pct` | float | Revenue surprise % |
| `same_day_return` | float | Stock return on earnings day |
| `predicted_return` | float | Model-predicted return for this surprise |
| `underreaction_flag` | boolean | actual < predicted - 2% |
| `pead_setup_quality` | enum | High / Medium / Low |
| `entry_date` | date | When position was entered (if acted on) |
| `drift_21d` | float | Auto-filled: return at 21 days |
| `drift_63d` | float | Auto-filled: return at 63 days |
| `outcome_label_correct` | boolean | Did drift occur as expected |

### Connection to Existing Research

- A ticker flagged by the laggard screen that also has a PEAD setup → very high conviction
- PEAD setup in a rising sector → the sector tailwind amplifies the drift
- ML model also bullish on the same ticker and horizon → three independent signals converging

---

## Technique 3 — Insider Transaction Clustering

### Why This Works

Individual insider buys are noisy — executives buy for many reasons and the signal is weak in isolation. But when multiple insiders across multiple companies in the **same sector or sub-industry** buy within a short window, that clustering is a strong sector-level signal. They are not coordinating — they're independently responding to the same improving conditions they see from the inside.

This technique treats insider transactions as a sector sentiment indicator, not just a company-level flag.

### Signal Types

#### 3.1 Individual Insider Buy (Company Level)

**Qualifying criteria (all required):**
- Open market purchase (not option exercise, not DRIP, not automatic plan purchase)
- Transaction size > $100,000 (filters out token purchases)
- Insider role: CEO, CFO, COO, Board Director, or >10% owner (not mid-level management)
- Not within 30 days of an earnings release (reduces noise from earnings-window purchases)
- No corresponding sale within the same insider's history in the past 60 days

**Stronger signal when:**
- Multiple insiders at the same company buy within 30 days of each other
- The purchase is notably large relative to the insider's historical transaction sizes
- The stock has declined 15%+ in the prior 3 months (insiders buying their own dip)

#### 3.2 Sector Clustering Signal (The Core Technique)

**Definition:** 3 or more qualifying insider buys across 3 or more different companies in the same GICS sub-industry within a 30-day rolling window.

**Implementation:**
- Pull all insider transactions daily from SEC Form 4 filings
- Filter to qualifying buys only (per criteria above)
- Tag each transaction with GICS sector and sub-industry
- Run a 30-day rolling window: count qualifying buys per sub-industry
- Flag any sub-industry where count ≥ 3 across ≥ 3 different companies

**Why 3 companies minimum:** Two insiders buying in the same sub-industry could be coincidence. Three is a pattern.

#### 3.3 Insider Sell Cluster (Warning Signal)

Apply the same clustering logic to sales, with inverse interpretation:
- 3+ large insider sales across 3+ companies in the same sub-industry within 30 days
- Flag as a sector deterioration warning
- Cross-reference with ETF divergence monitor — if both signal simultaneously, elevated caution

### Data Sources

| Source | Coverage | Cost |
|---|---|---|
| SEC EDGAR (Form 4) | Official, complete, free | Free |
| OpenInsider.com | Cleaned, filterable, UI-friendly | Free |
| `sec-edgar-downloader` (Python) | Programmatic Form 4 access | Free |
| Finviz Insider | Quick screener view | Free |
| TipRanks | Insider scoring and track records | Paid |

**Recommended approach:** Use OpenInsider for quick screening, `sec-edgar-downloader` for building the automated pipeline.

### Implementation Pipeline

```
Daily:
  1. Pull new Form 4 filings from SEC EDGAR
  2. Parse: ticker, insider name, role, transaction type, shares, price, total value, date
  3. Apply qualifying filters
  4. Tag with GICS sub-industry
  5. Update rolling 30-day cluster counter per sub-industry
  6. Flag clusters ≥ threshold
  7. Log to database, trigger research alert if new cluster detected
```

### Insider Track Record Scoring

Over time, build a per-insider track record:
- For every qualifying buy logged, record the 90-day forward return
- Compute per insider: average 90-day return after their buys, hit rate (% positive)
- Weight cluster signals by the average track record of the insiders involved
- A cluster of high-track-record insiders > a cluster of first-time buyers

### Database Schema

| Field | Type | Description |
|---|---|---|
| `filing_date` | date | SEC Form 4 filing date |
| `transaction_date` | date | Actual transaction date |
| `ticker` | string | |
| `insider_name` | string | |
| `insider_role` | string | CEO / CFO / Director / >10% owner |
| `transaction_type` | enum | Buy / Sell |
| `shares` | integer | |
| `price` | float | |
| `total_value` | float | |
| `gics_sector` | string | |
| `gics_sub_industry` | string | |
| `qualifies` | boolean | Passed all filters |
| `cluster_flag` | boolean | Part of a 30-day cluster |
| `insider_track_record_score` | float | Historical 90d return avg for this insider |
| `outcome_90d` | float | Auto-filled: stock return 90 days later |

---

## Technique 4 — Cross-Asset Correlation Break Detection

### Why This Works

Assets that historically move together reflect a shared underlying driver (e.g., oil stocks and crude oil prices, bank stocks and the yield curve, gold miners and gold). When that correlation breaks — one asset moves but the other doesn't — it signals either a mispricing (opportunity) or a regime change (warning). Detecting these breaks systematically, rather than noticing them by accident, is the edge.

### Core Pairs to Monitor

| Stock / Sector | Correlated Asset | Historical Driver |
|---|---|---|
| Energy stocks (XLE) | Crude oil (WTI) | Revenue directly tied to oil price |
| Bank stocks (XLF) | 10Y-2Y yield spread | Net interest margin driver |
| Gold miners (GDX) | Gold price (GLD) | Revenue tied to gold price |
| Tech hardware | Semiconductor index (SOX) | Supply chain and cycle shared |
| Airlines | Jet fuel / crude oil | Cost base |
| Homebuilders | 30-year mortgage rate | Demand driver |
| EM stocks | DXY (USD index) | Dollar strength = EM headwind |
| Utilities | 10Y Treasury yield | Rate-sensitive income proxy |
| Copper miners | Copper futures | Direct revenue link |
| Consumer discretionary | Consumer confidence index | Spending driver |

This list covers the most reliable and economically sensible pairs. Do not add pairs without a clear fundamental reason for the correlation — spurious correlations are everywhere in financial data.

### Correlation Break Detection Method

**Step 1: Establish Rolling Correlation Baseline**
- For each pair, compute 252-day (1 year) rolling Pearson correlation
- This becomes the "normal" correlation for that pair
- Also compute 63-day rolling correlation to capture recent relationship

**Step 2: Detect Breaks**
- Break condition: `|corr_63d - corr_252d| > 0.25`
- This means the 3-month correlation has diverged significantly from the 1-year baseline
- Also flag: `corr_63d < 0.3` for pairs that historically correlate above 0.7

**Step 3: Classify the Break**

When a correlation break is detected, determine which direction:

- **Type A — Asset leads, stock lags:** The correlated asset (e.g., oil) has moved significantly but the stock (e.g., energy companies) has not followed yet → potential laggard opportunity. Investigate why the stock hasn't moved.
- **Type B — Stock leads, asset lags:** The stock has moved but the underlying driver hasn't confirmed it yet → potential false move or early signal of a shift in the underlying asset.
- **Type C — Diverging entirely:** Both assets moving in opposite directions — rare, but signals a fundamental regime change or a stock-specific factor overwhelming the macro driver.

**Step 4: Quantify the Dislocation**

For Type A (most actionable):
- Compute the expected stock price based on the historical relationship: `expected_stock = intercept + slope × current_asset_price`
- Compute the dislocation: `dislocation = (actual_stock - expected_stock) / expected_stock × 100`
- Threshold for action: dislocation > 8% (stock meaningfully below where its correlated asset says it should be)

### Implementation Pipeline

```
Weekly:
  1. Pull price data for all pairs (stocks + assets)
  2. Compute 63d and 252d rolling correlations for each pair
  3. Flag break conditions
  4. For Type A breaks: compute expected vs. actual stock price
  5. Rank by dislocation magnitude
  6. Top 3 dislocations → add to research watchlist
  7. Log to database
```

### Interpreting Breaks: Not Always Opportunity

A correlation break is a **research trigger**, not a signal to trade. Possible explanations:

| Explanation | Action |
|---|---|
| Temporary lag — stock will follow asset shortly | Research the fundamentals — if clean, opportunity |
| Hedging offsetting asset exposure at company level | Read 10-K/10-Q for hedging disclosures — may reduce opportunity |
| Company-specific issue decoupling it from asset | Cross with disqualifier checklist — may be a trap |
| Regime change — the correlation is genuinely breaking down | Investigate macro environment — update the pair model |
| Tax-loss selling or technical factor | Usually resolves quickly — shorter-term opportunity |

### Database Schema

| Field | Type | Description |
|---|---|---|
| `pair_id` | string | e.g., "XLE_WTI" |
| `detection_date` | date | |
| `corr_252d` | float | Long-term rolling correlation |
| `corr_63d` | float | Short-term rolling correlation |
| `break_magnitude` | float | Difference between the two |
| `break_type` | enum | A / B / C |
| `dislocation_pct` | float | Stock vs. expected price (Type A only) |
| `research_triggered` | boolean | Did you investigate this one |
| `explanation_assigned` | string | Which explanation category |
| `outcome_30d_stock` | float | Auto-filled: stock return 30 days later |
| `outcome_30d_asset` | float | Auto-filled: correlated asset return 30 days later |
| `correlation_restored` | boolean | Did correlation return to normal within 60 days |

---

## Technique 5 — Short Interest Dynamics

### Why This Works

Short interest alone is a weak signal. But **changes** in short interest, especially when combined with other signals, are much more informative. Two specific setups are worth monitoring systematically: short squeeze conditions and rising short interest as a warning flag in seemingly healthy stocks.

### Signal Type 5.1 — Short Squeeze Setup

**Definition:** A stock with high short interest begins trending upward with improving fundamentals, creating conditions where short sellers must buy back shares to cover losses — amplifying the upside move.

**Quantitative criteria (all must be met):**

| Metric | Threshold | Rationale |
|---|---|---|
| Short Interest as % of Float | > 15% | Enough shorts to create squeeze fuel |
| Days to Cover (Short Ratio) | > 5 days | Short sellers can't exit quickly without moving price |
| Price trend (21d) | Positive | Shorts are already under pressure |
| Fundamental trend | Stable or improving | Squeeze needs a reason to sustain |
| Institutional ownership trend | Stable or increasing | Smart money not abandoning it |

**Days to Cover formula:**
```
Days to Cover = Short Interest (shares) / Average Daily Volume (30d)
```

**The squeeze trigger:** When a stock meeting all five criteria above also receives a positive catalyst (earnings beat, analyst upgrade, sector momentum), the forced buying by short sellers can amplify the move significantly beyond what fundamentals alone would justify. This is a short-window, high-magnitude opportunity.

**Important caution:** Short squeeze setups can be violent in both directions. A squeeze that fails (catalyst doesn't materialize) can reverse sharply. Position size carefully and define the exit before entering.

### Signal Type 5.2 — Rising Short Interest Warning

**Definition:** Short interest in a stock has been rising consistently for 2+ months even as the stock price holds steady or rises.

**Why it matters:** Short sellers are not always right, but when sophisticated institutional short sellers are building a position persistently, they typically have a thesis. This doesn't mean you sell immediately, but it means your disqualifier checklist (from the laggard strategy) must be run rigorously before acting on any bullish signal on that ticker.

**Threshold:** Short interest rising >25% over 8 weeks while price is flat or up → elevated caution flag

**Investigation steps when flagged:**
1. Search for any known short-seller research reports on the ticker (Hindenburg, Citron, etc.)
2. Check recent 10-Q for any unusual accounting disclosures
3. Review revenue recognition notes
4. Check if management has been selling while short interest builds
5. If no explanation found → watch but don't ignore

### Signal Type 5.3 — Short Interest Collapse (Capitulation)

**Definition:** Short interest drops sharply (>20% decline in short shares over 4 weeks) after a sustained high-short-interest period.

**What it signals:** Short sellers are giving up and covering. This often coincides with a price floor being established. If the underlying business is intact, this can mark the end of a pressure period and the beginning of recovery.

**Action:** Not immediately bullish — wait for price confirmation (21-day uptrend) before acting. Use as a filter to add laggard or PEAD candidates to the watchlist.

### Data Sources for Short Interest

| Source | Update Frequency | Cost |
|---|---|---|
| FINRA (official) | Twice monthly | Free |
| Finviz | Bi-weekly (from FINRA) | Free |
| Fintel | Daily estimated short interest | Paid (~$35/month) |
| Ortex | Real-time estimated short interest | Paid (~$99/month) |
| iborrowdesk.com | Daily borrow rates (proxy for short demand) | Free |

**Recommended:** Finviz for screening, iborrowdesk for monitoring borrow rate trends on flagged tickers (rising borrow rate = demand to short is increasing, even before FINRA data updates).

### Implementation Pipeline

```
Bi-weekly (aligned with FINRA release):
  1. Pull updated short interest data for all tickers in universe
  2. Compute: SI % of float, days to cover, 8-week change in SI
  3. Flag squeeze setups (all 5 criteria met)
  4. Flag rising short interest warnings (>25% increase, 8 weeks)
  5. Flag capitulation events (>20% drop in SI from high)
  6. Cross-reference all flags with laggard screen and PEAD pipeline
  7. Log to database
```

### Database Schema

| Field | Type | Description |
|---|---|---|
| `ticker` | string | |
| `report_date` | date | FINRA report date |
| `short_interest_shares` | integer | |
| `float_shares` | integer | |
| `si_pct_float` | float | Short interest as % of float |
| `avg_daily_volume_30d` | integer | |
| `days_to_cover` | float | |
| `si_change_8w_pct` | float | % change in SI over 8 weeks |
| `signal_type` | enum | Squeeze / Warning / Capitulation / None |
| `borrow_rate` | float | From iborrowdesk if available |
| `outcome_30d` | float | Auto-filled |
| `squeeze_occurred` | boolean | Did a squeeze materialize within 30 days |

---

## Technique 6 — Macro Regime Detection

### Why This Works

A signal that works in a risk-on, low-rate expansion environment may fail entirely in a risk-off, high-rate contraction. Most backtests fail to account for this because they train on all market history mixed together. Regime detection solves this by tagging every signal, prediction, and trade with the active macro regime — so you know not just *what* a signal says, but *when* it is likely to be reliable.

This technique is foundational infrastructure, not a standalone signal. It makes every other technique in this document more honest and more useful.

### Regime Dimensions

Define the regime across three independent axes:

**Axis 1 — Risk Appetite**
| Regime | Definition |
|---|---|
| Risk-On | VIX < 20 and trending down, credit spreads tight, equities in uptrend |
| Neutral | VIX 20–28, no clear directional trend in spreads |
| Risk-Off | VIX > 28 or spiking, credit spreads widening, equities declining |

**Axis 2 — Rate Environment**
| Regime | Definition |
|---|---|
| Easing | Fed funds rate declining or market pricing in cuts (Fed futures) |
| Neutral | Rates stable, no strong cut/hike expectation |
| Tightening | Fed funds rate rising or market pricing in hikes |

**Axis 3 — Growth Cycle**
| Regime | Definition |
|---|---|
| Expansion | ISM Manufacturing > 50 and rising, yield curve positive, earnings estimates rising |
| Slowdown | ISM declining toward 50, yield curve flattening |
| Contraction | ISM < 50, yield curve inverted, earnings estimates being cut |
| Recovery | ISM turning up from below 50, credit spreads tightening |

The combination of these three axes defines the full regime. Example: Risk-On + Easing + Expansion is the best possible environment for equities. Risk-Off + Tightening + Contraction is the worst.

### Regime Classification Method

**Option A — Rules-Based (Start Here)**

Define hard thresholds for each indicator as above. Assign regime label daily. Simple, interpretable, easy to implement.

Variables needed (all free from FRED via `pandas_datareader`):
- VIX: `VIXCLS`
- 10Y-2Y yield spread: `T10Y2Y`
- ISM Manufacturing (monthly): `MANEMP` (proxy) or pull directly from ISM website
- IG Credit spread (investment grade): `BAMLC0A0CMEY`
- HY Credit spread (high yield): `BAMLH0A0HYM2`
- Fed funds rate: `FEDFUNDS`
- Fed funds futures (for forward-looking rate expectations): pull from CME FedWatch or Quandl

**Option B — Statistical (Add Later)**

Use a Hidden Markov Model (HMM) with 3–4 states on a multivariate input of the above variables. The HMM learns the regimes from the data rather than hard-coding thresholds. More robust, less interpretable. Use the `hmmlearn` Python library.

Recommended: implement rules-based first, validate that regimes make intuitive sense (2008 = Risk-Off + Tightening + Contraction, 2021 = Risk-On + Easing + Expansion), then add HMM as a second opinion.

### Regime Tagging Implementation

Once regime labels are generated daily, they are joined to every other dataset by date:

```python
# Pseudocode
experiment_log['regime_risk'] = experiment_log['date'].map(regime_risk_lookup)
experiment_log['regime_rates'] = experiment_log['date'].map(regime_rates_lookup)
experiment_log['regime_growth'] = experiment_log['date'].map(regime_growth_lookup)
```

This allows every analysis to be stratified by regime:

```
"XGBoost directional accuracy on META, 21d horizon:"
  Overall: 54%
  During Expansion + Risk-On: 61%
  During Contraction + Risk-Off: 47%
  During Tightening: 49%
```

That stratification is far more useful than the overall number.

### Regime-Conditional Signal Performance

For each technique (laggard screen, PEAD, options signals, etc.), track signal performance by regime:

| Technique | Expansion | Slowdown | Contraction | Recovery |
|---|---|---|---|---|
| Laggard Screen | ✓ High hit rate | ✓ Moderate | ✗ Avoid | ✓ High |
| PEAD Bullish | ✓ High | ✓ Moderate | ✗ Low | ✓ Moderate |
| Short Squeeze | ✓ High | ✓ Moderate | ✗ Violent reversals | ✓ High |
| Correlation Break (Type A) | ✓ | ✗ May not resolve | ✗ May not resolve | ✓ |

This table will be populated empirically from your logged outcomes over time. Start with hypotheses, update with real data.

### Regime Change Detection (Early Warning)

The most valuable insight is detecting a **regime transition** before it is obvious. Early warning indicators:

- VIX rising from below 18 toward 22 over 2 weeks (not yet Risk-Off, but trending)
- Yield curve flattening more than 20bps in 4 weeks
- ISM PMI dropping below 52 for 2 consecutive months
- HY credit spreads widening >50bps in 3 weeks
- Fed funds futures repricing more than 2 rate changes in 4 weeks

When 2+ of these early warning indicators trigger simultaneously: flag as "Regime Transition Risk" and reduce conviction on all bullish signals until regime stabilizes.

### Database Schema

| Field | Type | Description |
|---|---|---|
| `date` | date | Daily |
| `vix` | float | |
| `vix_21d_change` | float | |
| `yield_spread_10y2y` | float | |
| `hy_credit_spread` | float | |
| `ig_credit_spread` | float | |
| `ism_manufacturing` | float | Monthly, forward-filled |
| `fed_funds_rate` | float | |
| `regime_risk` | enum | Risk-On / Neutral / Risk-Off |
| `regime_rates` | enum | Easing / Neutral / Tightening |
| `regime_growth` | enum | Expansion / Slowdown / Contraction / Recovery |
| `transition_warning` | boolean | 2+ early warning indicators active |
| `regime_composite` | string | Combined label, e.g. "RiskOn_Easing_Expansion" |

---

## Integration Map — How All Techniques Connect

```
MACRO REGIME (Technique 6)
        │
        ▼ tags everything below with regime context
        │
┌───────┴──────────────────────────────────────────────┐
│                                                        │
▼                                                        ▼
LAGGARD SCREEN ──────────────────► PEAD SCREEN
(sector rising, peer left behind)   (earnings beat, drift setup)
        │                                    │
        ▼                                    ▼
CROSS-ASSET CORRELATION         OPTIONS SIGNALS
BREAK (Technique 4)             (Technique 1)
        │                                    │
        └──────────────┬─────────────────────┘
                       │
                       ▼
              INSIDER CLUSTERING
              (Technique 3)
                       │
                       ▼
              SHORT INTEREST
              DYNAMICS (Technique 5)
                       │
                       ▼
              ML PREDICTION NOTEBOOK
              (scenario engine, ensemble)
                       │
                       ▼
              SIGNAL CONVERGENCE SCORE
              (how many independent signals agree?)
                       │
                       ▼
              CONVICTION TIER → POSITION SIZING DECISION
```

### Signal Convergence Scoring

For each ticker under consideration, count how many independent signals are aligned:

| Score | Signals Aligned | Action |
|---|---|---|
| 5–6 | Laggard + PEAD + Options bullish + Insider buy + No short warning + Positive regime | Maximum conviction — full position |
| 3–4 | Most signals aligned, 1–2 neutral | Standard position |
| 2 | Mixed signals | Reduced position or watchlist only |
| 0–1 | Signals conflicting | Do not act — research only |

This scoring framework is the final output layer that sits above all six techniques. A ticker needs to earn its conviction tier through multiple independent signals, not just one strong one.

---

## Implementation Priority Order

| Priority | Technique | Reason |
|---|---|---|
| 1 | Macro Regime Detection | Tags all other signals — implement first |
| 2 | PEAD Screen | High-quality academic edge, clear implementation |
| 3 | Options Signals (UOA + IV/RV) | Strongest leading indicator, free data available |
| 4 | Cross-Asset Correlation Breaks | Connects naturally to laggard screen |
| 5 | Short Interest Dynamics | Bi-weekly data cadence, simpler pipeline |
| 6 | Insider Clustering | Slowest signal, most manual — implement last |

Each technique should be fully implemented, validated, and producing logged outcomes before the next one begins. Do not run all six in parallel — the logging and outcome tracking will become unmanageable.
