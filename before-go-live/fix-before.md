Listed directory hedge-fund
Viewed missing-parts.md:1-55
Viewed improvements.md:1-135
Viewed ingestion.py:1-480
Viewed validation.py:1-143
Viewed flask_app.py:1-800
Ran command: `sqlite3 engine_data.db ".schema"`
Edited check_db_schema.py
Ran command: `python scratch/check_db_schema.py`
Viewed recalculate_engine.py:1-192
Viewed RUN_FUND_TOTAL.bat:1-59
Viewed scheduler.py:1-666
Viewed system_bootstrap.py:1-345

I have completed a comprehensive system check-up of the **Hedge Fund Control Tower**. Below is a detailed diagnosis of the current state, identified bugs, and technical debt, followed by brainstormed solutions.

### 1. Architectural Conflict & Technical Debt
**The Problem:** There is a fundamental "split-brain" issue between the legacy system and the new production-grade infrastructure.
*   **The Conflict:** `flask_app.py` has a background scheduler that triggers `portfolio/recalculate_engine.py`. This legacy script operates on `ledger.csv` and `historical_prices.csv`, saving results to `engine_state.json`.
*   **The Modern Path:** The unified pipeline (`RUN_FUND_TOTAL.bat` and `engine/scheduler.py`) uses `engine_data.db` (SQL) and is much more robust.
*   **The Bug:** The dashboard primarily reads from SQL tables (`trades`, `positions_history`), but the background job refreshes a JSON state file that is largely ignored by the new frontend, leading to potential data mismatches and wasted compute.

### 2. Data Ingestion & Integrity
**The Problem:** Blind trust in third-party data providers (`yfinance`).
*   **Undetected Staleness:** `engine/data/validation.py` has a `check_staleness` function, but it is **not called** during the main `run_ingestion` flow. If a ticker stops updating, the engine will proceed with stale data without alerting the user.
*   **Opaque Substitution:** When a primary ticker (e.g., Xetra) fails, the system falls back to a US ticker. While good for availability, this "Substitution Event" is not surfaced prominently on the dashboard.
*   **FX Fallback Dependency:** Ingestion uses fallback FX rates (`0.92`, `1.17`) if APIs fail. If these are not updated, the entire portfolio valuation for US/UK stocks could be off by several percentage points.

### 3. Missing Observability (The "Silent Killer")
**The Problem:** The pipeline runs via `.bat` files which fail silently unless a user manually inspects the terminal.
*   **Hidden Crashes:** If `yfinance` blocks an IP or the database locks, the `pipeline_runs` table will simply stop updating, but the user won't get a "Heartbeat" alert.
*   **Digest Config:** `engine/scheduler.py` has hooks for `send_digest`, but the `engine/alerting/digest.py` module (referenced but not viewed) needs to be verified for correct SMTP/Slack configuration to prevent "alert fatigue" or silent failures.

### 4. Portfolio & Risk Modeling Gaps
**The Problem:** The current Black-Litterman optimizer and Risk Engine are "Retail-Grade" rather than "Institutional-Grade."
*   **Covariance Noise:** Standard historical covariance (used in `scheduler.py` line 350) is prone to noise. It lacks **Ledoit-Wolf Shrinkage**, which would stabilize the weights.
*   **Transaction Costs:** The optimizer assumes trades are free. It doesn't account for **slippage** or **bid-ask spreads**, which leads to "Portfolio Churn" (unnecessary trades for tiny theoretical gains).
*   **Static Seeds:** MC simulations in `flask_app.py` (line 280) use `seed=0`. This makes the "Risk" view identical every time, which is good for debugging but hides the probabilistic nature of the risks from the user.

### 5. UI & Dashboard Deficiencies
**The Problem:** Certain critical data streams are either missing or hard to interpret.
*   **PEAD Table Emptiness:** Previous logs mention the "ACTIVE ENTRY WINDOWS" being empty. The logic in `flask_app.py` has a complex fallback between SQL and CSV, suggesting a potential synchronization bug between the `pead_engine` and the production database.
*   **Explainability:** The trade suggestions (Delta Weights) are presented as raw numbers. There is no "Why" (e.g., "Driven by Momentum and VIX expansion").
*   **Fee Reconciliation:** There is a potential risk of fee double-counting if "Quick Fees" are logged separately from transaction-integrated fees.

---

### Brainstormed Solutions & Implementation Plan

| Category | Proposed Solution |
| :--- | :--- |
| **Architecture** | **Unify the Scheduler:** Disable the scheduler in `flask_app.py` and move all background logic to `engine/scheduler.py`. Ensure the dashboard reads *exclusively* from SQL tables. |
| **Reliability** | **Integrated Staleness Checks:** Modify `run_ingestion` to call `check_staleness` at the end of every run and write a `CRITICAL` event to `pipeline_logs` if any asset is >3 days stale. |
| **Risk** | **Robust Covariance:** Implement `sklearn.covariance.LedoitWolf` in the feature pipeline to replace the standard `.cov()` call. |
| **Execution** | **Edge Thresholding:** Add a `min_delta_weight` (e.g., 1.5%) to the optimizer. If a suggested trade is smaller than the threshold, suppress the signal to save on fees. |
| **Observability** | **Daily Heartbeat:** Create a small cron-job script that checks the `MAX(run_date)` in `pipeline_runs`. If it's not "Today," send an emergency Slack/Email alert. |
| **Explainability** | **Signal Decomposition:** Update the `model_outputs` table to store the top 2-3 contributing features per signal, then display these as tags in the `rebalance.html` view. |

**Next Steps:**
I recommend prioritizing the **Architecture Unification** first to ensure you are looking at accurate data, followed by the **Staleness/Heartbeat** logic to protect the system against silent failures before you "go live."
