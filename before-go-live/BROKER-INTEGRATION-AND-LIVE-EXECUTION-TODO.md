# Brokerage Integration & Automated Execution — Future Go-Live TODO

> **Category:** Phase 3/4 Optional - Automated Broker Execution
> **Current Status:** Inactive (System currently operates as a Human-in-the-Loop Control Tower where trades are approved/logged via web dashboard).
> **Purpose:** This document tracks the remaining tasks if you ever decide to connect direct automated broker APIs (e.g. Interactive Brokers, Alpaca) for execution.

---

## 1. Data Feed Upgrade (Institutional Feed)
- [ ] Replace or supplement `yfinance` with an institutional broker API (Interactive Brokers, Alpaca, or Polygon.io).
- [ ] Add asynchronous fetching (`asyncio` or `Tenacity` retry logic) to prevent rate limits across 100+ tickers.
- [ ] Build automated corporate action adjustment validation (splits and dividend adjustments).

## 2. Live Broker State Reconciliation
- [ ] Implement live API reconciliation loop before rebalance:
  ```python
  positions = broker_api.get_positions()
  cash      = broker_api.get_cash_balance()
  ```
- [ ] Ensure DB acts strictly as a cache/log while the broker API remains the single source of truth for holdings.

## 3. Order Execution State Machine
- [ ] Upgrade manual trade log into an automated order state machine:
  `CREATED → SUBMITTED → PARTIALLY_FILLED → FILLED / FAILED`
- [ ] Handle partial fills, limit order tolerance bands, and order cancellation retries automatically.

## 4. Automated Execution Kill Switches
- [ ] Add API-level execution kill switch: halt API trading if portfolio drawdown exceeds 15% in a rolling 7-day window.
- [ ] Add API-level VIX override: scale API trade sizes down proportionally during high-volatility regimes.
