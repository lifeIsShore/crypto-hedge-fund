# Fund Risk Policy & Governance Document

This document outlines the strict risk management protocols, trading bounds, and governance rules mathematically enforced by the engine. These rules are hardcoded into the pipeline and cannot be bypassed during normal execution, ensuring portfolio safety, compliance, and alignment with our risk mandate.

## 1. Liquidity & Execution Constraints (Order Manager)
To prevent slippage and market impact, the engine will never generate an order that represents an oversized portion of an asset's daily trading volume.
* **Volume Cap (Liquidity Gating):** No single order will exceed **5%** of the asset's 21-day Average Daily Volume (ADV) measured in EUR.
* **Enforcement:** If a generated target allocation requires a trade larger than this cap, the order size is strictly truncated down to the 5% ADV limit before it reaches the execution queue.
* **Tolerance Bands:** To prevent noise-trading and excessive broker fees, target weights must drift by a minimum configurable threshold before a rebalancing trade is triggered.

## 2. Stop-Loss & Circuit Breakers (Risk Engine)
The system enforces hard, per-position stop-loss floors. These overrides supersede all predictive alpha models and portfolio optimizers.
* **Individual Equities:** If an individual stock drops **-15%** from its weighted-average entry price (cost basis), the circuit breaker triggers.
* **Broad-Market ETFs:** ETFs (e.g., VWCE.DE, EUNL.DE) are subject to a tighter **-12%** circuit breaker due to their inherently lower volatility.
* **Enforcement Action:** When a threshold is breached:
  1. The asset's target weight is immediately forced to **0%**.
  2. A `CRITICAL` alert is broadcast via the notification digest.
  3. A permanent, auditable log is written to the `risk_events` ledger.
  4. The engine initiates a forced liquidation (sell-to-close) in the execution queue.

## 2b. Portfolio-Level Drawdown Protocol

Section 2 above covers **per-position** circuit breakers. This section covers
**portfolio-level** drawdown — what happens as total fund value falls from
its high-water mark, independent of any single position. This was flagged
as an open gap in `BRAINSTORM-new-features-and-gaps.md` ("Operational Gap
#2") and had no coded behavior anywhere in the engine as of this writing.

**Decision needed from Ahmet before this becomes enforceable** — the tiers
below are a starting proposal, not yet wired into `scheduler.py`. This
section exists so the decision is made in writing, in advance, rather than
during an actual drawdown (per the BRAINSTORM doc's own reasoning: "During a
drawdown is the worst time to decide").

| Drawdown from high-water mark | Proposed action | Status |
|---|---|---|
| **-10%** | Alert-only. CRITICAL digest entry, no automatic trading change. | Proposed — not built |
| **-15%** | Reduce gross exposure: scale all new BUY orders by 0.5× (reuse the same scalar mechanism as J3's Kelly sizing / J4's earnings throttle in `order_manager.py`, so it composes with them rather than adding a fourth ad-hoc sizing path). | Proposed — not built |
| **-20%** | Pause the pipeline: `step_portfolio_construction()` continues to run (so risk metrics and the dashboard stay current) but `generate_order_queue()` returns no new BUY orders — SELLs and circuit-breaker-forced exits still execute, since risk-reducing trades should never be paused. | Proposed — not built |

**Open questions for Ahmet to resolve before implementation:**
- High-water mark basis: since first deposit, or trailing 12 months? (Affects
  how quickly the tiers reset after a recovery.)
- Should the -20% pause require manual un-pause (a dashboard button), or
  auto-resume once drawdown recovers above -15%?
- Do the three tiers interact with the existing per-position circuit breakers
  (Section 2) or run entirely independently? Recommendation: independently
  — a portfolio-wide drawdown can occur with no single position breaching
  -15%/-12%, and conflating the two triggers would make each harder to
  reason about in isolation.

## 3. Position Sizing & Concentration
Position sizing is dynamically determined by the Black-Litterman optimizer, which balances conviction (Alpha signal strength) against market equilibrium and volatility.
* **Diversification Mandate:** The optimizer heavily penalizes excess concentration, ensuring capital is distributed across the asset universe rather than isolated into binary bets.
* **Regime Adaptation:** During periods of high macroeconomic stress (detected via VIX, credit spreads, and yield curves in the `Regime Engine`), the optimizer aggressively compresses total exposure, deleveraging the portfolio into cash/safe-havens.

## 4. Human-in-the-Loop (HITL) Override Protocols
While the engine executes autonomously, human portfolio managers retain ultimate oversight.
* **Signal Queue Interception:** Analysts can review proposed alpha signals and reject them before they enter the Black-Litterman optimizer.
* **Manual Trades:** Managers can execute manual trades via the dashboard. These are recorded with `source='manual'` in the trade ledger to isolate them from algorithmic performance metrics.
* **Emergency Halt (SOS Protocol):** Under extreme, unforeseen market dysfunction, the pipeline can be manually halted, blocking all API execution routes until the environment stabilizes.

---
*Document Version: 1.1 | Status: Sections 1, 2, 3, 4 Implemented & Active. Section 2b (Portfolio Drawdown Protocol) is a proposal pending Ahmet's sign-off — not yet coded.*
