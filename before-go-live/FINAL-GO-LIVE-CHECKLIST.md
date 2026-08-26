# FINAL GO-LIVE CHECKLIST
# The Master Sequence to Production

This document serves as the absolute final order of operations before accepting real user capital or switching from paper trading to live broker execution. 

The steps are ordered strictly by **dependency** and **risk mitigation**. Do not jump to Phase 4 (Commercialization) until Phase 1 (Quant Validation) proves the system actually makes money out-of-sample.

---

## PHASE 1: Quant Validation (Proving the Edge)
*You cannot trade real money or sell this as a SaaS without proving the historical walk-forward performance.*

- [x] **1.1 Build the Backtest Engine (`before-go-live/archive-implemented/backtest/01-engine.md`)**
  - Extract the Black-Litterman logic to run over historical price slices without touching the live SQL database.
- [x] **1.2 Build the Alpha Evaluator (`before-go-live/archive-implemented/backtest/02-alpha-ic-evaluation.md`)**
  - Implement the Information Coefficient (IC) math to strictly measure if the ML model is predicting noise or signal.
- [x] **1.3 Build Portfolio Metrics & Dashboard (`before-go-live/archive-implemented/backtest/03-portfolio-metrics.md` & `04-dashboard.md`)**
  - Compute Sharpe, Calmar, and Drawdowns, and render them in the non-technical UI dashboard.
- [x] **1.4 Establish ML Baseline (`better-alpha/00-OVERVIEW.md` - Gate 0)**
  - ✅ Done 2026-08-21. Coverage bug fixed (126/135 tickers, up from 78). Baseline recorded in `better-alpha/baseline_v1_auc.txt`: mean_auc=0.6331, n_tickers=126. Gate 1 locked: `HOLDOUT_START=2026-02-23`.
- [x] **1.5 Target Refinement (`better-alpha/02-target-refinement.md`)**
  - Change the ML target from predicting Absolute Return to predicting **Alpha** (Excess Return vs. Benchmark). 
  - Run Gate 2 evaluation: Ensure IC improves by `> 0.003`. (FAILED Gate 2 - remains False).
- [x] **1.6 Feature Addition (`better-alpha/01-feature-additions.md` - Phase 1A/B/C)**
  - Slowly bridge the production regime signals (Stress score, VIX) and PEAD data into the ML pipeline, gating each addition strictly. (FAILED Gate 2 - remains False).

---

## PHASE 2: Engine & Risk Finalization (Tying up loose ends)
*These are components that were half-built or drafted, but never fully wired into the live scheduler or UI.*

- [x] **2.1 Ticker Liquidity Tiering (`before-go-live/NEW-ticker-liquidity-tiering.md`)**
  - Implement `engine/data/liquidity_classifier.py` and wire it into the `scheduler.py` weekly pipeline.
  - Implement the liquidity filter to prevent the engine from firing BUY signals on highly illiquid or stale `.DE` cross-listings.
- [x] **2.2 USD Display Toggle (`before-go-live/NEW-usd-display-toggle.md`)**
  - Add the UI toggle allowing non-EU users to view portfolio values and trades in USD alongside EUR.
- [ ] **2.3 Wire the Laggard Screen (J7)**
  - The logic exists in `engine/screens/laggard_screen.py`. It needs to be called in `scheduler.py` and displayed in the dashboard UI.
- [ ] **2.4 Wire PEAD Calendar Trigger (`before-go-live/NEW-pead-calendar-trigger.md`)**
  - Connect `pead_alpha.py` / the PEAD engine to `get_recently_reported()` from the Earnings Calendar module, so it triggers on calendar dates, not just price anomalies.
- [ ] **2.5 Missing UI Badges (`before-go-live/NEW-ui-badges.md`)**
  - Surface the "Upcoming Earnings" flag (from J4) and the Sector Relative rank (from J5) on the Ticker Detail pages and live portfolio view.
- [ ] **2.6 Implement Portfolio Drawdown Protocol**
  - Review section 2b of `RISK-POLICY.md`. Decide if you want auto-halts at -15% or -20% portfolio drawdowns, and implement the circuit breaker.
- [ ] **2.7 Decide on the SOS Button (`SOS-button.md`)**
  - Choose between "Halt Only" or "Liquidate" for the emergency kill-switch, and build the UI button.

---

## PHASE 3: Sandbox End-to-End Verification
*The paper trading environment must run flawlessly for 2 weeks before real capital is injected.*

- [ ] **3.1 Run a clean `RUN_SANDBOX.bat` execution**
  - Monitor the console output to ensure Step 11 (Portfolio Construction) and Step 14 (Paper Orders) complete without Python crashes.
- [ ] **3.2 Verify Constraints in Paper Trades**
  - Look at `sandbox_data.db`. Verify that paper orders were correctly scaled down by the Kelly Scalar (J3) and the Earnings Throttle (J4).
- [ ] **3.3 Reconcile Cash Double-Count**
  - Run `FIX_SANDBOX_CASH.bat` to fix the historical database bug where cash was deducted twice for paper buys.

---

## PHASE 4: Commercialization & Legal (SaaS Prep)
*If you are managing your own money, you can skip this. If you are selling this software to others, these are hard blockers.*

- [ ] **4.1 Migrate off `yfinance`**
  - Yahoo Finance ToS forbids commercial use. Select and integrate a paid provider (e.g., Polygon.io, EODHD, Financial Modeling Prep) for real-time prices.
- [ ] **4.2 Resolve Regulatory Risk**
  - Consult legal counsel regarding BaFin/SEC laws around "Investment Advice." Generating personalized target weights for paying customers carries high legal risk. You may need to abstract the output (e.g., selling "model scores" rather than "portfolio allocations").
- [ ] **4.3 Legal Documents Preparation**
  - Bring `LEGAL-DOCS-CHECKLIST.md` to a lawyer to draft the actual ToS, Privacy Policy, and Financial Disclaimers.
- [ ] **4.4 Database Architecture Decision**
  - Review `SAAS-MONETIZATION-AND-SCALE-ARCHITECTURE.md`. Decide if you will stick with SQLite (1 container per user) or migrate to a shared Postgres database before onboarding the first 100 users.
