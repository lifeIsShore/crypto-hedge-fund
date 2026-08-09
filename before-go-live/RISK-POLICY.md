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
*Document Version: 1.0 | Status: Implemented & Active*
