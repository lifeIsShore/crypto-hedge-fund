# ETF vs. Component Divergence Signal — Strategy Plan

> **Status: TODO — Implement after laggard screen is live**

---

## Core Concept

When a broad index or thematic ETF (S&P 500, Magnificent 7, XLK, etc.) is **rising** while one of its major components is **falling or significantly underperforming**, a divergence signal exists. The ETF masks the individual stock's weakness — or alternatively, the stock's weakness is temporary and the ETF is telling you the broader thesis is intact.

The entire edge here is correctly diagnosing **which of those two realities is true.**

---

## The Four Scenarios (And How to React to Each)

### Scenario 1 — Temporary Rotation
*The ETF rises because capital rotates into other components. The lagging stock's fundamentals are unchanged.*

**Signal characteristics:**
- No negative news on the stock
- Other components in the ETF are unusually strong (picking up the weight)
- Volume on the lagging stock is normal or below average — no distribution
- Institutional holdings relatively stable

**Reaction:** Treat as a laggard screen opportunity (see laggard strategy doc). The ETF is your confirmation that the macro/sector thesis is intact. The individual stock is temporarily out of rotation. Research the fundamentals — if clean, this is a buy candidate.

---

### Scenario 2 — Stock-Specific Bad News
*The stock dropped for a real reason. The ETF doesn't reflect it because the other components compensate.*

**Signal characteristics:**
- Identifiable negative catalyst (earnings miss, regulatory action, guidance cut, leadership change)
- High volume on the down move
- Analyst downgrades or target cuts
- Peers in the same sub-industry also weak (even if ETF hides it)

**Reaction:** Do NOT buy the dip reflexively. The ETF rising is misleading here — it is not confirming the stock's thesis. Put the stock on a **watch list**, define what a "recovery confirmation" looks like (e.g., one clean earnings beat, regulatory resolution), and wait. This is a future opportunity, not a current one.

---

### Scenario 3 — Valuation Compression / Mean Reversion
*The stock ran significantly ahead of peers, now pulling back to fair value while others catch up. The ETF rises because the rest of the basket is re-rating.*

**Signal characteristics:**
- The stock had a large prior run (e.g., +60–80% in prior 6 months) before the divergence
- P/E or EV/EBITDA significantly above historical average and above peers
- No bad news — just normalization
- Other ETF components are re-rating upward toward the lagging stock's prior level

**Reaction:** Neutral — wait. The compression may not be finished. There is no urgency. Set a price alert at a valuation level that looks historically fair (e.g., stock hits its 3-year average P/E), then reassess. Do not fight the mean reversion.

---

### Scenario 4 — True Divergence / Thesis Break
*The market is pricing in something structural about this specific company that the ETF smooths over. This is the most dangerous case.*

**Signal characteristics:**
- Divergence is sustained over weeks, not days
- Insider selling during the divergence period
- Short interest rising meaningfully
- Peers in the same sub-industry also quietly weakening (even if ETF holds)
- Fundamental deterioration visible in recent filings (margin compression, revenue deceleration)

**Reaction:** Avoid. If already holding, treat as an exit signal — the ETF is masking a real problem. The broader index rising gives a false sense of security. This is exactly the scenario where people hold too long because "the market is fine."

---

## Detection Checklist (Run Before Categorizing)

When you spot an ETF-stock divergence, answer these questions in order:

1. **Is there identifiable negative news?**
   - Yes → likely Scenario 2 or 4
   - No → likely Scenario 1 or 3

2. **Did the stock have a large prior run before the divergence?**
   - Yes → likely Scenario 3
   - No → lean toward Scenario 1 or 4

3. **Is the divergence recent (days) or sustained (weeks/months)?**
   - Recent → Scenario 1 or 2
   - Sustained → Scenario 3 or 4

4. **Are peers in the same sub-industry also quietly weak?**
   - Yes → Scenario 2 or 4 (something real is happening)
   - No (peers are fine) → Scenario 1 or 3

5. **Is short interest rising? Is there insider selling?**
   - Yes → Scenario 4 (exit or avoid)
   - No → Scenario 1 or 3 (opportunity side)

---

## Data Sources Needed

| Need | Suggested Source |
|---|---|
| ETF vs. component performance comparison | TradingView, Koyfin, ETF.com holdings view |
| Component weighting within ETF | ETF.com, issuer website (iShares, Vanguard, etc.) |
| Volume and distribution analysis | TradingView, Finviz |
| Short interest trend | Fintel, Ortex, Finviz |
| Insider transactions | OpenInsider, SEC Form 4 |
| Peer sub-industry performance | Finviz, Koyfin |
| Valuation vs. historical average | Macrotrends, Koyfin |

---

## Key Principle

> The ETF rising is **not** a buy signal for the diverging component — it is a **context signal** that helps you categorize the situation. The trade direction depends entirely on which scenario you are in.

The instinct to buy a falling stock "because the index is fine" is the most common mistake this divergence creates. The checklist above exists to prevent that reflex from bypassing the research.

---

## Implementation Notes (For When This Becomes Active)

- Build this as a **separate screen** that runs alongside the laggard screen — different logic, different reaction framework
- Prioritize large-cap components of major ETFs first (Mag 7, S&P top 50) — these are where the divergence signal is clearest and most liquid
- Define a minimum divergence threshold before triggering the checklist (e.g., stock down 5%+ while ETF up 3%+ over same 4-week window)
- Short-term divergences (under 1 week) are noise unless accompanied by very high volume — filter those out initially
