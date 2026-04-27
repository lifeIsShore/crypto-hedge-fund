# System Overview: Trade Republic Quantitative Engine

**Quick Answer:** A Python-based advisory system that analyzes your Trade Republic portfolio, calculates optimal asset allocations using Modern Portfolio Theory, and tells you exactly what trades to make. You keep full control—manual execution only.

---

## What This System Does (In Plain English)

### The Problem You're Solving
- Trade Republic has no API for automated trading.
- Manual portfolio management is emotionally biased.
- Most rebalancing strategies are too complex or require constant tweaking.

### The Solution
1. **Every Friday:** You run a Python script on your computer.
2. **The Script:**
   - Downloads 2 years of historical data for 6 quality assets (Apple, Microsoft, SAP, etc.).
   - Calculates how these assets correlate, their individual risks, and optimal combinations.
   - Compares your *current* portfolio to the *mathematically ideal* portfolio.
   - Checks if rebalancing is needed (and only if the trade is worth the 1 EUR fee).
3. **You Get:**
   - A clear instruction: "Buy €30 of SAP, Sell €20 of Apple" (or "Hold, all good").
   - A beautiful dashboard showing your portfolio health.
4. **You Execute:**
   - Log into Trade Republic app on your phone.
   - Execute the trades exactly as instructed.
   - Update a simple spreadsheet with the trades you made.
5. **Repeat Next Friday.**

---

## The Workflow (Weekly Cycle)

```
Friday Evening (20:00):
  1. Open a terminal on your computer.
  2. Type: python run_engine.py
  3. Streamlit dashboard opens in browser (http://localhost:8501)
  
Dashboard shows:
  • Your portfolio: €X,XXX total, €Y in cash, €Z in each stock
  • Health score: Sharpe Ratio (> 1.0 is good)
  • Action board: "No rebalancing needed" -or- "Sell 10€ of MSFT, buy 10€ of SAP"
  • Charts: Your equity curve vs MSCI World benchmark
  
You execute (Saturday morning):
  1. Log into Trade Republic app
  2. Execute the trades exactly as instructed (e.g., buy 2.5 shares of SAP)
  3. Open ledger.csv on your computer
  4. Add two rows: [Date] [Buy] [SAP.DE] [2.5] [€19.50] [€48.75]
  5. Close the app
  
Next Friday: Engine reads the updated ledger, calculates based on new reality, repeats.
```

---

## Trade Republic Constraints & How We Work Around Them

### Constraint 1: No Official API
- **Reality:** Unofficial API wrappers exist but violate TR's Terms of Service.
- **Our Solution:** Advisory mode. You remain the executor. The Python script just gives instructions.
- **Your Control:** You can reject a signal if market news says otherwise. You're not automated; you're informed.

### Constraint 2: No Direct Short Selling
### Reality Check: Unhedged Currency Risk
- **Reality:** Even though we trade Xetra (`.DE`) tickers priced in Euros, US stocks (Apple, Microsoft) have underlying USD value. 
- **The System:** The engine calculates metrics based strictly on the EUR price. If Apple USD goes up 2% but the Euro strengthens 2% against the Dollar, your `.DE` ticker stays flat. The engine inherently handles this by reacting to the EUR-denominated reality, but you should be aware of why your returns might look different than US financial news.
  

### Constraint 3: No Bulk Historical Data from TR
- **Reality:** TR keeps price data locked up.
- **Our Solution:** Use Yahoo Finance (`yfinance` library). It's free, reliable, and has 20+ years of history.
- **Caveat:** We use Xetra/Frankfurt tickers (`.DE` suffix) so prices match what you see in TR exactly.

### Constraint 4: Flat €1 Transaction Fee
- **Reality:** Every trade costs €1 minimum, regardless of size.
- **Our Solution:** 
  - Set a **€25 minimum trade size** threshold. If the algorithm says "Sell €8 of Apple," we ignore it.
  - **Fee cap:** €25 minimum means fee ≤ 4% per trade. Acceptable for our weekly/monthly rebalancing.
  - Use TR's free **Savings Plans (Sparpläne)** for regular buys (no €1 fee).
- **Scaling rule:** The engine uses a dynamic floor (`MAX(25.00, portfolio_value * 0.005)`). This guarantees minimum trades scale smoothly as your account grows, keeping fee drag strictly capped at ≤ 4% forever.
---

## The Asset Universe

### Universe A: Quality Equities (Your Main Portfolio)

Why these 6?
- **High liquidity:** Can buy/sell instantly on TR without price slippage.
- **Clear economic drivers:** If they drop, you can read the news and understand why.
- **Trade Republic availability:** All available as fractional shares.

**The 6 Assets:**
1. **Apple** → `APC.DE` (Tech growth)
2. **Microsoft** → `MSF.DE` (Tech/Cloud)
3. **SAP** → `SAP.DE` (European software)
4. **Allianz** → `ALV.DE` (Insurance/financials)
5. **LVMH** → `MOH.DE` (Luxury consumer)
6. **MSCI World ETF (iShares Core)** → `EUNL.DE` (Global diversification anchor)

**Lookback:**
- 2 years of daily closing prices (504 trading days).
- Long enough to see multiple market regimes (bull, sideways, bear).
- Short enough to forget old crises (preventing outdated constraints).

---

## What the Engine Actually Calculates

### Layer 1: Understanding Each Asset (Descriptive Statistics)
- **Daily Returns:** How much did Apple's price change today? (In log return form)
- **Volatility:** Apple swings ±2% daily = high risk. Allianz swings ±1% = lower risk.
- **Skewness:** Do Apple's big moves tend to be up-days (good) or down-days (bad)?

### Layer 2: Understanding Asset Interactions (Correlation)
- **Correlation Matrix:** When Apple drops, does Microsoft also drop? Are they moving together?
  - Corr = 1.0: Move exactly together (bad for diversification)
  - Corr = -1.0: Move oppositely (good for hedging)
  - Corr = 0.0: Uncorrelated (good for diversification)
- **Example:** In normal times, tech stocks (Apple, Microsoft, SAP) might corr = 0.7. In a crash, everything corr = 0.9 (you lose diversification).

### Layer 3: The Optimizer (Modern Portfolio Theory)
- **Objective:** Find the best mix of all 6 assets that maximizes Sharpe Ratio.
- **Sharpe Ratio:** Return ÷ Risk. *"How much money am I making per unit of stress?"*
- **Constraints:**
  - No single asset > 25% (prevents "YOLO into Apple" corner solutions)
  - Can hold up to 100% cash (for defensive positioning)
  - Must total 100%

### Layer 4: Risk Metrics (Downside Protection)
- **Maximum Drawdown:** "In the worst period ever, my portfolio fell 35%. That's my pain threshold."
- **Value at Risk (95% VaR):** "95% of the time, my daily loss doesn't exceed €5."

### Layer 5: Rebalancing Decision
- **Comparison:** Is your *current* SAP holding (15%) too high vs *optimal* SAP (18%)?
  - Drift = 3%. This is < 5% buy threshold, so **DON'T TRADE** (save the fee).
- **Trend Filter:** Is SAP above its 200-day moving average? 
  - Yes → Keep it open to buying.
  - No → Optimizer sets target to 0% (defensive positioning).
- **Fee Check:** Is the required trade (e.g., "Sell 5€ of SAP") ≥ €25?
  - Yes → Execute.
  - No → Swallow the signal (too expensive relative to trade size).

---

## Dashboard: What You See Every Week

### Screen 1: The "Command Center" (Action-Focused)

**Top Row: 3 Big Scorecards**
- **Card 1:** "€105 portfolio value, €25 cash" (is your capital intact?)
- **Card 2:** "+€5 profit (+5%)" (are you winning?)
- **Card 3:** "Sharpe Ratio: 1.23 ✅ GOOD" (is your risk worth it?)

**Center: The Action Board (Highlighted)**
- **Green box** with huge text: 
  - Either: "✅ No action required this week. All assets within safe range."
  - Or: "⚠️ Rebalance: Sell €30 of Apple, Buy €30 of SAP"

**Why the change?** 
- (Tooltip): *"Apple grew too much (23% of portfolio > 20% target). We're locking in gains."*

**Bottom: 2 Charts**
- **Left:** Donut showing current allocation (Apple 23%, MSFT 18%, SAP 15%, Cash 20%, etc.)
- **Right:** Line chart: Your black line (equity curve) vs blue line (MSCI World). Are you beating it?

### Screen 2: The "Ledger" (Input & Verification)

**Top Left: Log a Trade**
- Dropdown: Action (Buy / Sell / Deposit / Dividend)
- Dropdown: Ticker (APC.DE, MSF.DE, SAP.DE, etc.)
- Input: Shares, Price
- Button: Submit
- *For syncing:* After you trade on TR, log it here so the engine knows your current reality.

**Right: Current Holdings Table**
| Asset | Qty | Avg Buy | Current | Unrealized PnL | Trend |
|-------|-----|---------|---------|---|---|
| AAPL | 2.5 | €150 | €155 | +€12.50 | ✅ UP |
| MSFT | 1.8 | €300 | €295 | -€9 | ⚠️ UP (close to 200-day MA) |
| ... | ... | ... | ... | ... | ... |

*UP/DOWN badge shows: Is this asset above or below its 200-day moving average?*

---

## Rebalancing Logic: When Do You Actually Trade?

### Time-Based Check
- Engine runs **1st and 3rd Friday** of every month.
- You're not constantly checking. Two decision points per month. Systematic, not emotional.

### Threshold-Based Execution
- **Example:**
  - Apple target: 20%
  - Current: 24% (drift = +4%)
  - → No signal (below the 7% Sell threshold, tax deferred!)
  - ---
  - Current: 28% (drift = +8%)
  - → Signal: "Sell €X of Apple" (7% threshold breached)

### Fee Logic
- Must be ≥ €25 trade size (else €1 fee = too expensive).
- If math says "Sell €8 of Apple" but account is €100 total → Engine suppresses (output "HOLD").

---

## Key Parameters (Locked Unless You Change Them With Reason)

| Parameter | Value | Why |
|-----------|-------|-----|
| **Lookback** | 2 years (504 days) | Enough history, not stale |
| **Risk-Free Rate** | 2.0% p.a. | TR cash yield |
| **Max Weight Per Asset** | 25% | Anti-YOLO rule |
| **Rebalance Frequency** | 1st & 3rd Friday | Systematic, not emotional |
| **Drift Threshold** | Asymmetric (5% Buy / 7% Sell) | Balance accuracy, defer taxes |
| **Minimum Trade Size** | Dynamic Floor (Max of €25 or 0.5%) | Fee cap at ≤ 4% forever |
| **Trend Filter** | 200-day SMA | Avoid holding losers |

**Important:** These don't change on a whim. Any change must be logged with mathematical rationale in `TUNING-LOG.md`.

---

## Your Weekly Time Commitment

- **Friday 8 PM:** Run script (5 min)
- **Saturday morning:** Check dashboard, execute trades on TR (10 min)
- **Saturday noon:** Log trades in ledger.csv (2 min)
- **Total:** ~17 minutes per week

---

## Success Metrics (What "Good" Looks Like)

### Month 1–2
- ✅ Engine running without crashes
- ✅ Dashboard displaying live data
- ✅ You've executed your first manual rebalance based on engine output

### Month 3–6
- ✅ Your portfolio hasn't suffered major losses (within reasonable drawdown)
- ✅ Your Information Ratio > 0 (you're beating the MSCI World ETF)
- ✅ You trust the engine enough to stick to its signals even when you disagree

### Month 12
- ✅ €100 has grown to €120+ (or understood reasons for lower if market crashed)
- ✅ You're ready to scale capital up (go from €100 → €1,000 → €5,000)
- ✅ You've never tweaked the algorithm emotionally or "just because markets look bad today"

---

## What Could Go Wrong (And How We Prevent It)

| Risk | Mitigation |
|------|-----------|
| **Too many tiny trades** | €25 minimum trade size caps fee drag |
| **Over-concentration** | 25% max weight per asset |
| **Holding losers** | 200-day MA trend filter exits automatically |
| **Emotional tweaking** | All changes logged in TUNING-LOG.md with rationale |
| **Stale data** | Engine fetches latest yfinance prices daily |
| **Fee bleed at scale** | Scaling rule: 2% min trade when portfolio > €5,000 |
| **Losing diversification** | Rolling correlation check alerts if all assets correlate |

---

## Not This Project (What We Intentionally Skip)

- ❌ Day-trading or high-frequency strategies (TR execution is manual)
- ❌ Options strategies or derivatives (only long equity + cash)
- ❌ Pair trading / short selling (TR doesn't allow it)
- ❌ Real-time algorithmic execution (you're the algorithm executor)
- ❌ Minute-level GARCH volatility models (overkill for weekly rebalancing)
- ❌ Emotional storytelling (decisions are mathematical, not narrative)

---

## Ready to Start?

1. ✅ **You understand the big picture** (this document)
2. **Next:** Read [ARCHITECTURE.md](./ARCHITECTURE.md) to see how it's built
3. **Then:** Read [STRATEGY-RULES.md](./STRATEGY-RULES.md) to understand exact rules
4. **Finally:** Start Phase 1 implementation (create src/config.py with tickers)

---

> **This is not a get-rich-quick scheme. This is a systematic, mathematically grounded framework for holding a diversified portfolio and rebalancing it intelligently. It requires discipline and consistency. If you can commit to checking once per week and executing trades when instructed, you'll have a robust, professional-grade investment system.**
