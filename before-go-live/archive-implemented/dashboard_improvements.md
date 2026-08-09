# Dashboard Improvement Roadmap
### Control Tower — Next-Gen Ops Layer

> Audit of the current 12-tab Flask dashboard. Focused on three pillars:  
> **(1) Human-in-the-Loop**, **(2) Conviction / Highlighted picks tab**, **(3) Short Sell advisory**

---

## Current State — What We Have

| Tab | What it does | Gaps |
|-----|--------------|------|
| OVERVIEW | Portfolio positions, KPIs, freshness | No action prompts, no conviction ranking |
| RISK & STRATEGY | Per-ticker MC, price levels, portfolio VaR | No short signal path, no approval workflow |
| ML RESEARCH | Ensemble verdict, per-ticker signals, PEAD | Signals shown but not actioned |
| MACRO REGIME | US/EU regime history, EW flags | No regime-gated trade filtering |
| PAIRS / STAT ARB | Pairs cointegration screen | Static, no HITL approval |
| REBALANCE | Delta weight suggestions | No override reason capture per decision |
| HOLDINGS | Live positions | No urgency/alert layer |
| TRADES | Trade ledger | Append-only, no tagging |
| ANALYTICS | PnL, performance charts | No attribution by signal source |
| HISTORY | Historical portfolio values | Thin — no signal replay |
| ETF DIVERGENCE | Divergence labelling tool | Manual labelling only |
| PIPELINE HEALTH | Kill switch, provider status | Good — keep as-is |

**Core problem:** The system is an excellent *information display* but almost no *decision workflow*. You read signals, then mentally decide. There is no guided path from signal → review → approve → execute → track.

---

## Improvement 1 — `HIGHLIGHTED` Tab (High-Conviction Picks)

> **The AMD idea:** Surface tickers that have high return potential AND high risk simultaneously — the kind of asymmetric setup where the model has real edge.

### What it shows
A ranked list of the **top 8–12 asymmetric opportunities** from the full ML universe, scored by a composite conviction score.

### Conviction Score formula
```
conviction = (up_proba × auc × (1 + rr_ratio)) × regime_multiplier × pead_boost
```

| Factor | Contribution | Source |
|--------|-------------|--------|
| `up_proba` | Raw ML directional probability | `ml_state.json` |
| `auc` | Model quality gate (≥0.53 = meaningful) | `ml_state.json` |
| `rr_ratio` | Risk/reward ratio (asymmetry) | `price_targets` table |
| `regime_multiplier` | 1.2× if Risk-On, 0.8× if Risk-Off | `regime_state.json` |
| `pead_boost` | 1.15× if ticker has active PEAD setup | `pead_setups` table |
| `vol_score` | Favour moderate vol (15–40% ann.) — not too tame, not reckless | `ml_state.json` |

### Highlighted card layout (per ticker)
```
┌─────────────────────────────────────────────────────────┐
│  NVDA  ·  NVIDIA Corp             ⭐⭐⭐ HIGH CONVICTION  │
│  Conviction: 0.847  |  R:R: 2.4x  |  Win%: 67%         │
│  Up Proba: 73.2%  |  AUC: 0.591  |  Vol: 38% ann       │
│  Current: €112.40  Target: €128  Stop: €101  21D        │
│  Tags: [PEAD ACTIVE] [RISK-ON] [EARNINGS MOMENTUM]      │
│  [⚡ APPROVE FOR REVIEW] [📋 ADD TO WATCHLIST]           │
└─────────────────────────────────────────────────────────┘
```

### Short-side highlighted cards (NEW)
For bearish setups (`up_proba < 0.40`, `AUC ≥ 0.53`), surface a **SHORT CANDIDATE** card instead:
```
┌─────────────────────────────────────────────────────────┐
│  INTC  ·  Intel Corp              🔴 SHORT CANDIDATE     │
│  Bear Proba: 64%  |  R:R (short): 1.9x  |  Vol: 42%   │
│  Entry: ≤ €22.80  Cover: €19.50  Stop: €24.10          │
│  Tags: [WEAK SECTOR] [RISK-OFF REGIME DIVERGENCE]       │
│  [📋 WATCHLIST SHORT] [⚠️ SHORT ADVISORY]               │
└─────────────────────────────────────────────────────────┘
```

### Backend: new API endpoint
```python
# GET /api/highlighted
# Returns top N conviction picks (long + short)
# Scored server-side, cached for 1h
```

### What makes this different from ML RESEARCH tab
- **ML RESEARCH** = all tickers, sorted alphabetically, raw signal display
- **HIGHLIGHTED** = curated, ranked, scored, with regime context + PEAD overlay + a clear "next action" button

---

## Improvement 2 — Short Sell Advisory Layer

> The system is **fully long-only** today. Even the `SELL` signal in the ML tab means "exit / reduce" not "go short". This is a significant missing piece.

### Why short advisory matters
- Bearish signals currently go nowhere — you have `🔴 SELL` in the ML Research tab but no workflow to act on them
- You already have the machinery: `up_proba < 0.40` + good AUC = statistically valid short signal
- In Risk-Off regimes (which your engine detects), short opportunities increase significantly
- PEAD bearish setups (`direction: bearish`) are already identified but not surfaced as actionable shorts

### Two modes of short advisory

#### Mode A — Synthetic Short (Inverse ETF) — Safer, works on Trade Republic
Rather than shorting individual stocks, route bearish signals to inverse ETFs:

| Bearish Signal On | Suggested Instrument | Reason |
|------------------|----------------------|--------|
| US Tech (NVDA, AMD falling) | SQQQ / PSQ | 3× / 1× inverse Nasdaq |
| US Broad Market | SH / SDS | S&P 500 inverse |
| EU Tech / DAX | XSPS.DE / DBX4 | Inverse DAX ETF |
| Individual sector weakness | Sector inverse ETF | Match to sector |

#### Mode B — Direct Short Advisory (informational only, no execution)
For informational purposes (and when using a broker that supports shorting):
- Show short entry price, borrow cost estimate, cover target, stop
- Flag: "This is NOT a Trade Republic supported action — informational only"

### Short Scoring Formula
```
short_score = (1 - up_proba) × auc × (rr_short) × regime_bear_multiplier
```
Where `rr_short = (entry - cover_target) / (stop - entry)` mirrors the long R:R calc.

### New `SHORT ADVISORY` panel in the RISK & STRATEGY tab
Add a second section below the long universe table:

```
┌──────────────────────────────────────────────────────────┐
│  SHORT CANDIDATES / BEARISH ADVISORY            [MODE: ℹ️ INFO ONLY]  │
├────────────┬───────────┬───────────┬───────────┬──────────┤
│ TICKER     │ BEAR PROB │ AUC       │ R:R SHORT │ REGIME  │
│ INTC       │ 64.1%     │ 0.568     │ 1.9x      │ Risk-Off │
│ VOW3.DE    │ 61.3%     │ 0.553     │ 2.1x      │ Slowdown │
└────────────┴───────────┴───────────┴───────────┴──────────┘
  ⚠️ Inverse ETF suggestions: [Show alternatives]
```

### Regime-gated short filter
Shorts are only surfaced when:
- `regime_risk == "Risk-Off"` OR `transition_warning == true`
- OR ticker has a **bearish PEAD setup**
- OR ticker up_proba ≤ 0.38 with AUC ≥ 0.55 (high confidence bear)

This prevents noise — the system won't show short ideas in a strong Risk-On regime.

---

## Improvement 3 — Human-in-the-Loop (HITL) Decision Workflow

> Currently: you look at signals → you do something → no record exists of *why*.  
> Goal: structured approval layer that creates an audit trail of every decision.

### 3.1 — Signal Review Queue (new tab or panel)

Think of it as **an inbox for trade decisions**. Every morning the pipeline produces signals. Instead of just displaying them, route them into a **Review Queue**:

```
┌──────────────────────────────────────────────────────────────┐
│  ⏳ PENDING REVIEW    3 signals awaiting your decision        │
├─────────┬──────────┬──────────┬───────────┬──────────────────┤
│ TICKER  │ SIGNAL   │ CONVICTION│ EXPIRES   │ ACTION           │
│ NVDA    │ 🟢 BUY   │ 0.847    │ 2d 14h    │ [✅ APPROVE] [❌ SKIP] [📝 NOTE] │
│ INTC    │ 🔴 SHORT │ 0.623    │ 2d 14h    │ [✅ APPROVE] [❌ SKIP] [📝 NOTE] │
│ VOW3.DE │ 🟠 LEAN SELL│ 0.441 │ 1d 08h    │ [✅ APPROVE] [❌ SKIP] [📝 NOTE] │
└─────────┴──────────┴──────────┴───────────┴──────────────────┘
```

**Expiry logic:** Signals expire after N days (configurable, default 3 days) — after which the ML re-runs and produces fresh ones. This prevents acting on stale signals.

**Backend table:** `signal_queue` (new)
```sql
CREATE TABLE signal_queue (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    generated_at TEXT,
    ticker       TEXT,
    signal_type  TEXT,   -- BUY, SELL, SHORT, REDUCE
    conviction   REAL,
    expires_at   TEXT,
    status       TEXT DEFAULT 'pending', -- pending | approved | skipped | expired
    reviewed_at  TEXT,
    review_note  TEXT
);
```

### 3.2 — Override Capture (upgrade existing)

The `override_log` table already exists but the UI for it is minimal. Upgrade it:

**Current:** "Action taken" field  
**New:** Structured form with:
- `reason_category`: `MACRO_VIEW` / `EARNINGS_RISK` / `POSITION_SIZE_TOO_LARGE` / `ALREADY_HOLDING` / `REGULATORY` / `OTHER`
- `conviction_override`: slider (do you agree with the model's confidence 0–100%)
- `notes`: free text
- `follow_up_date`: when to revisit this decision

This turns overrides into **learning data** — you can later analyse which override categories led to better/worse outcomes.

### 3.3 — Decision Journal (new panel in ANALYTICS)

A timeline of every human decision:
```
2026-06-01  NVDA  [APPROVED BUY]  Conviction 0.847  Note: "Strong earnings momentum"
2026-05-28  INTC  [SKIPPED SELL]  Reason: MACRO_VIEW  Note: "Expecting Fed pivot"
2026-05-21  AMD   [OVERRIDDEN → BUY]  Model said NEUTRAL  Note: "AMD-like setup"
```

This is the **audit trail** that makes your system defensible and learnable.

### 3.4 — Regime-Gated Trade Approval

Add a **pre-approval check** that warns before approving any BUY in Risk-Off regime:

```
⚠️ REGIME WARNING
You are about to approve a LONG position in a Risk-Off regime.
Macro indicators suggest elevated market stress.
Conviction adjusted: 0.847 → 0.678 (regime-discounted)
[Proceed anyway] [Cancel]
```

---

## Improvement 4 — Conviction Scoring as First-Class Citizen

> Currently conviction is implicit (up_proba + AUC separately). Make it explicit everywhere.

### Add `conviction_score` column to all signal tables
- Compute server-side in `price_targets` step
- Display on OVERVIEW, ML RESEARCH, RISK tabs
- Sort HIGHLIGHTED tab by this score by default
- Store historical conviction scores → track model calibration over time

### Conviction traffic light
```
🟢 HIGH   ≥ 0.70  — Strong edge, regime-aligned
🟡 MEDIUM  0.55–0.70  — Model signal present, proceed with normal sizing
🔴 LOW    < 0.55  — Marginal, reduce size or skip
⚫ GATED  AUC < 0.53  — Do not act on this signal
```

---

## Improvement 5 — PEAD → HITL Workflow Integration

PEAD setups are currently displayed but disconnected from the approval workflow.

### Connect PEAD to the Review Queue
When a new PEAD setup fires (`active_setups` has new entries after a pipeline run):
1. Auto-create a `signal_queue` entry tagged `source: PEAD`
2. Include the earnings surprise magnitude, direction, quality score
3. Show in the HITL Review Queue with pre-filled conviction = `pead_setup_quality × up_proba`

This means **every PEAD setup requires a conscious human approval** before any trade consideration.

### PEAD Outcome Tracking
When a PEAD setup expires (21d window closes):
- Auto-flag for outcome review: "Was the direction correct? Y/N"
- Store outcome → feeds back into PEAD quality scoring over time
- Show PEAD hit rate per regime type: "PEAD works 71% in Risk-On Expansion, 44% in Risk-Off"

---

## Improvement 6 — Short PEAD (Bearish Earnings Drift)

The PEAD engine today only surfaces *underreaction* for follow-up. Extend it for shorts:

| Scenario | Current | New |
|----------|---------|-----|
| Big positive surprise, stock didn't rally | → PEAD BULL setup | Same |
| Big negative surprise, stock didn't fall | → **PEAD BEAR setup** | Add short advisory |
| Huge drop on earnings | → Not tracked | Track as "overreaction" short opportunity (mean reversion) |

**Short PEAD signal:** `surprise_pct < -5%` AND `stock_3d_reaction < -2%` AND `underreaction_flag == True` → **Bearish PEAD** short advisory entry.

---

## Improvement 7 — Watchlist / Stalker Screen

> "Watch AMD-like setups" — before committing, just track.

New concept: **Watchlist** — a lightweight staging area between "I find it interesting" and "I'm putting it in the queue."

```
[+ ADD TO WATCHLIST] button on every signal row (ML Research, HIGHLIGHTED, Risk tabs)
```

**Watchlist panel** (new section on OVERVIEW or dedicated tab):
```
┌────────────────────────────────────────────────────────────┐
│  👁️ WATCHLIST  (4 tickers tracking)                         │
├──────────┬───────────┬───────────┬────────────┬────────────┤
│ TICKER   │ ADDED     │ UP PROBA  │ CONVICTION │ TREND      │
│ AMD      │ 3 days ago│ 61.2% → 68.5% ↑       │ 0.612 ↑   │ IMPROVING  │
│ ASML.AS  │ 1 week ago│ 57.3% ↓   │ 0.533 ↓   │ WEAKENING  │
└──────────┴───────────┴───────────┴────────────┴────────────┘
```

Shows conviction trend (is the model getting stronger or weaker on this ticker over time?). When conviction crosses 0.70 while on the watchlist → **auto-promote to Review Queue** with alert.

---

## Improvement 8 — Position Sizing Advisory

Today: Kelly% is shown as a number but there's no sizing *workflow*.

### Add to HIGHLIGHTED and HITL Queue:
```
NVDA  ·  BUY
Kelly (half): 4.2%  ≈  €420 on €10,000 portfolio
Current position: €180 (1.8%)  →  Model suggests adding: €240
Trade Republic lot at €113: BUY 2 shares (€226)  → oversize by €0.74
```

This bridges the gap between a percentage signal and an **actionable Trade Republic order**.

For short advisory:
```
INTC  ·  SHORT (Inverse ETF alternative: PSQ)
Bear Kelly: 2.1%  ≈  €210 on €10,000 portfolio
Suggested: Buy €210 of PSQ (Inverse Nasdaq)
```

---

## Improvement 9 — Signal Decay & Freshness Warnings

Signals have **timestamps** but no freshness decay logic in the UI. Add:

- ML signal older than 7 days → yellow warning on that ticker row
- ML signal older than 14 days → red, greyed out, "STALE — do not act"
- Regime state older than 24h → already handled (kill switch)
- PEAD setup past its 21d window → auto-archive, show "EXPIRED" tag

---

## Improvement 10 — Analytics Attribution

The ANALYTICS tab today shows PnL but not **which signals were responsible**.

### Add signal attribution layer:
When a trade is approved via the HITL queue, link it to the signal:
```sql
ALTER TABLE trades ADD COLUMN signal_queue_id INTEGER;  -- FK to signal_queue
ALTER TABLE trades ADD COLUMN conviction_at_entry REAL; -- what was the conviction when you bought
```

Then in ANALYTICS:
- **PnL by signal source:** PEAD vs ML Ensemble vs Pairs vs Manual
- **Conviction calibration chart:** "When conviction was 0.8+, average 21d return was +X%"
- **Override performance:** "Signals you skipped would have returned +Y% on average"

This is how you build a feedback loop that actually improves your decision-making over time.

---

## Implementation Priority

| # | Feature | Impact | Effort | Do First? |
|---|---------|--------|--------|-----------|
| 1 | **HIGHLIGHTED tab** with conviction scoring | 🔴 High | Medium | **Yes** |
| 2 | **Short sell advisory panel** in RISK tab | 🔴 High | Low | **Yes** |
| 3 | **Signal Review Queue** (HITL) | 🔴 High | Medium | **Yes** |
| 4 | Watchlist / Stalker screen | 🟠 Medium | Low | After 1–3 |
| 5 | Bearish PEAD (short PEAD) | 🟠 Medium | Medium | After PEAD fixes |
| 6 | Position sizing advisory | 🟠 Medium | Low | Easy win |
| 7 | Signal decay / freshness warnings | 🟡 Low | Low | Anytime |
| 8 | HITL override capture (structured) | 🟠 Medium | Low | After queue |
| 9 | Signal attribution in ANALYTICS | 🟡 Low | High | Last — needs data history |
| 10 | Regime-gated trade approval | 🟡 Low | Low | Easy win |

---

## What NOT to add right now

- ❌ Full automated trade execution → You are single-person, manual approval is the right model
- ❌ Telegram / email alerts → useful later, but not before the queue workflow exists
- ❌ Options/derivatives → complexity explosion, not justified yet
- ❌ Live broker API integration → Phase 2 / 3 territory (see `later-implementations.md`)

---

## Quick Win — Implement this week

The single highest ROI improvement is **adding short candidates to the existing RISK & STRATEGY tab's universe table**, which requires:

1. Add `short_score` computed column to `/api/price_targets` (3 lines of Python)
2. Add a visual indicator (🔴 SHORT CANDIDATE) in the universe table for `up_proba < 0.40` and `AUC ≥ 0.53`
3. Add inverse ETF suggestion column (lookup dict, hardcoded initially)

This gives you a **short advisory** without building any new infrastructure.

---

*Generated from audit of: 12 dashboard tabs, flask_app.py (2252 lines), todos/, regime_engine/, ml_quant_finance_research/*
