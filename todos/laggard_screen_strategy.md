> **STATUS (2026-08-13, implemented by Claude): WIRED IN.** `engine/screens/laggard_screen.py` implements Phases 1, 3, 4, and 5. Changes from the original stub:
> - **Wired into `engine/scheduler.py`** as step W2, weekly (Monday), right after the PEAD refresh.
> - **Phase 4 disqualifiers are now real for 2 of 8 checks** (elevated debt/equity — gated on J6's `fundamental_data` table existing, which it doesn't yet; elevated vol-of-vol as a distress proxy). The remaining 5 checks (sanctions/legal, governance, earnings quality, structural decline, insider selling) are surfaced as explicit "manual required" reminders on the dashboard rather than silently passed. A real automated flag now downgrades a candidate's conviction to WATCH instead of removing it from the list — the original placeholder's `if disq: continue` would, once any check was implemented, have silently dropped every single candidate (the always-present manual reminders alone made that condition true 100% of the time). Fixed as part of this wiring.
> - **Deviation from Phase 1 as written:** `SECTOR_ETF_MAP` only has 3 broad regional/market proxies (Nasdaq-100, DAX, MSCI World), not true per-sector ETFs (XLK/XLE/XLF/...), while `TICKER_SECTORS` classifies tickers into ~20 granular sectors. There's no honest way to match those vocabularies 1:1 with the ETF data this system actually ingests, so `detect_rising_sectors` is used as a coarse "is the broad market in an uptrend" gate rather than a per-sector filter — see the comment in `scheduler.py`'s `step_laggard_screen()` for the full reasoning. True sector-level gating would need real sector ETF price data this system doesn't have.
> - **New dashboard route `/laggards` + `templates/laggards.html`** exist, following the `/divergence` pattern, with hard flags (🚫) and manual-required reminders (⚠) rendered as visually distinct badges per this doc's own emphasis on not conflating the two.
> - `laggard_screen_results` table (schema.sql) extended with `peer_median_return`, `disqualifiers`, `reviewed` columns — migration handled via `ensure_laggard_schema()` for pre-existing DBs.
> - **Not yet verified end-to-end**: the weekly step has never actually fired in a real pipeline run (requires a Monday run with a rising broad-market signal). Check `laggard_screen_results` for real rows after the next Monday run before trusting this fully.

# Laggard Stock Screen — Research Strategy Plan

## Core Concept

When a sector or industry trends upward and lifts most of its peers, the stocks that **did not move proportionally** represent a high-probability opportunity — assuming no fundamental reason explains the underperformance. This plan formalizes that intuition into a repeatable research workflow.

---

## Mental Model: Why This Works

- Markets are inefficient in the short-to-mid term at the **individual stock level**, even when efficient at the **sector level**
- Institutional rotation often hits the largest/most liquid names first — smaller or less-covered peers lag by days, weeks, or months
- Once the sector narrative strengthens, capital eventually flows into the overlooked names
- The edge is in **identifying the lag before the catch-up**, then validating it's not a value trap

---

## Phase 1 — Sector-Level Signal Detection

### Step 1.1: Identify a Rising Sector

- Track sector ETFs (e.g., XLK, XLE, XLV, XLF, etc.) for sustained upward momentum
- Define "rising" as: **+8–25% over 1–6 months** (mid-term frame), with the trend intact (not a spike-and-crash)
- Flag sectors that are outperforming the broader index (S&P 500 / MSCI World) meaningfully

### Step 1.2: Confirm the Sector Narrative

Before drilling down, ask: *Why is this sector moving?*
- Macro tailwinds (rate changes, commodity cycles, regulation shifts)?
- Earnings beats across multiple players?
- New technology adoption cycle?
- Geopolitical shifts driving demand?

If the reason is **durable and broad** (not just one company's earnings), proceed. If it's a single-name story dragging the sector, be cautious.

---

## Phase 2 — Sub-Industry Drill-Down

### Step 2.1: Break the Sector into Sub-Industries

Example — Energy sector → Upstream (E&P), Midstream, Downstream, Oilfield Services, Renewables

- Use GICS classification (Sector → Industry Group → Industry → Sub-Industry)
- Identify **which sub-industries are leading** the sector move
- Identify **which sub-industries are lagging or flat** despite the sector trend

### Step 2.2: Confirm the Sub-Industry is Legitimately Exposed

A sub-industry lagging is only interesting if it *should* benefit from the same macro theme. Verify:
- Do these companies share the same revenue drivers?
- Are they exposed to the same end markets?
- Is the thesis applicable to their business model?

---

## Phase 3 — Peer Comparison Within Sub-Industry

### Step 3.1: Build a Comparable Peer Group

Criteria for "same size or near same size":
- Market cap within **±50%** of each other (flexible — use buckets: small, mid, large)
- Similar revenue scale
- Same primary geography of operations
- Same business model type (pure-play vs. diversified)

### Step 3.2: Measure Relative Performance

For each peer group, calculate over the **mid-term window** (default: 3–6 months):
- Absolute price return (%)
- Return relative to the sector ETF
- Return relative to the peer group median

**Sort by relative underperformance.** Stocks in the bottom quartile of the peer group are your laggard candidates.

### Step 3.3: Spot the Short-Term Exceptions

Run a separate, parallel screen for **1–4 week** laggards where:
- The peer group moved sharply in a short window
- One or two stocks barely moved or pulled back
- These are higher-risk, higher-speed opportunities — flag separately and apply stricter filters before acting

---

## Phase 4 — Laggard Validation (Eliminating Value Traps)

This is the most critical phase. A laggard is only an opportunity if there is **no fundamental reason** explaining the underperformance.

### Step 4.1: Negative Catalyst Check (Disqualifiers)

Go through this checklist for each laggard candidate. **Any confirmed item = remove from list.**

| Check | What to Look For |
|---|---|
| Sanctions / Legal | Active sanctions, DOJ/SEC investigations, major pending litigation |
| Governance | Insider fraud allegations, recent management exodus without explanation |
| Balance Sheet | Debt/Equity significantly higher than peers, covenant risk, upcoming debt maturity |
| Liquidity | Cash runway concern, negative free cash flow without clear path to profitability |
| Earnings Quality | Revenue recognition issues, declining gross margins, repeated guidance cuts |
| Structural Decline | Is this company losing market share *within* the growing industry? |
| Insider Selling | Unusual volume of insider selling during the sector rally |
| Short Interest | Abnormally high short interest — check *why* before dismissing |

### Step 4.2: Positive Thesis Confirmation

After clearing the disqualifiers, confirm the upside:
- Revenue and earnings trajectory in line with peers (or better)
- Comparable or better gross/operating margins
- Management has communicated the same exposure to the macro theme
- Analyst coverage hasn't recently downgraded with a sector-specific concern

### Step 4.3: Assign a Confidence Tier

| Tier | Criteria |
|---|---|
| **High Conviction** | Passed all disqualifier checks, strong fundamentals, clear peer parity expected |
| **Medium Conviction** | Minor concern (e.g., slightly elevated debt) but thesis still intact |
| **Watch List** | Interesting lag but one unresolved uncertainty — monitor, don't act yet |

---

## Phase 5 — Entry & Sizing Decision

### Step 5.1: Determine Position Sizing by Tier

- High Conviction laggards → standard or slightly above-average position size
- Medium Conviction → reduced size, wider stop
- Short-term laggards (exception cases) → small, defined-risk position only

### Step 5.2: Define the Catch-Up Target

- What is the gap between this stock's return and the peer median?
- Set a **realistic catch-up target** (e.g., "peers are up 18%, this is up 4% — targeting the gap to close to within 5%")
- This gives a rough price target and a basis for exit planning

### Step 5.3: Set an Invalidation Condition

Define upfront when the thesis is *wrong*:
- Peer group pulls back broadly (sector reversal — exit all)
- A new negative catalyst is confirmed (exit immediately)
- After X weeks, no catch-up movement despite sector holding (reassess)

---

## Data Sources Needed (For Implementation Phase)

| Need | Suggested Source |
|---|---|
| Sector/ETF performance | Yahoo Finance, TradingView, Finviz |
| Peer group price returns | Finviz stock screener, Koyfin, Macrotrends |
| GICS classification | MSCI GICS, Bloomberg, Finviz filters |
| Fundamentals (balance sheet, margins) | Macrotrends, Wisesheets, SEC EDGAR |
| Short interest | Finviz, Fintel, Ortex |
| Insider transactions | OpenInsider, SEC Form 4 filings |
| News / negative catalyst check | Seeking Alpha, Reuters, company IR page |

---

## Summary Workflow (Quick Reference)

```
1. Sector rising (mid-term, broad narrative) → confirmed ✓
2. Break into sub-industries → identify lagging sub-industries
3. Build peer group (similar size, same sub-industry) → rank by relative return
4. Flag bottom quartile performers → laggard candidates
5. Run disqualifier checklist → remove value traps
6. Confirm positive thesis → assign conviction tier
7. Decide position size + set catch-up target + set invalidation rule
8. (Parallel track) Short-term laggards → same process, stricter filter, smaller size
```

---

## Notes & Principles

- **The screen generates candidates, not decisions.** Every laggard still needs deep-dive research before capital is committed.
- **Peer group quality matters more than quantity.** A tight peer group of 4–6 truly comparable companies beats a loose group of 20.
- **Mid-term is the primary frame (3–6 months).** Short-term exceptions are satellite positions, not core positions.
- **Re-run the screen periodically** — a laggard that doesn't catch up in 4–6 weeks while the sector holds is a signal to reassess, not add.
