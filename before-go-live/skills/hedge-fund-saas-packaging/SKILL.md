---
name: hedge-fund-saas-packaging
description: >
  Architecture, open decisions, and implementation context for packaging the
  Control Tower hedge-fund system as a hosted SaaS product. Use when working on
  provisioning, multi-instance management, export/import, schema migration,
  auth/billing integration, or any work that touches the per-customer-isolated
  deployment model. Surfaces known conflicts and unresolved decisions to avoid
  re-litigating settled choices.
---

# Hedge Fund SaaS Packaging — Skill

## Confirmed architecture (do not re-litigate)

These decisions were made explicitly by Ahmet and are FINAL for the current design:

| Decision | What's confirmed |
|---|---|
| **Hosting model** | Hosted, server-side. NOT a desktop/local app. |
| **Multi-tenancy** | Single-tenant isolation: one SQLite file + one container per customer. No shared DB. |
| **DB engine** | SQLite. Do NOT migrate to PostgreSQL for multi-tenancy — that would break the isolation model. |
| **Short-selling** | Current scope = informational inverse-ETF advisory only. Live broker API execution (IBKR) is explicitly future/optional. |
| **Trade Republic** | Primary broker context for the first customer (Ahmet). Manual execution. No live broker API. |

---

## Explicitly conflicting documents — read before doing anything

- **`how-desktop.md`** — PyInstaller + Inno Setup Windows desktop packaging. **DO NOT IMPLEMENT.** Architecture is hosted containers.
- **`how-to-make-money.md` Path 1** — recommends PostgreSQL + shared multi-tenant DB + Flask-Login. **DO NOT implement the PostgreSQL/shared-tenancy parts.** The yfinance ToS point in this doc survives (see Data section below).
- **`short-investing.md`** — full IBKR live short execution architecture. **FUTURE/OPTIONAL**, not current scope. Don't build unless explicitly asked, and clarify which "short selling" is meant.

---

## Per-customer instance model

Each customer gets:
- One Python process (Flask app) running in an isolated container
- One `engine_data.db` SQLite file (all state)
- One set of scheduler runs (pipeline + weekly refresh)
- Separate API keys (see Data section below)

### New customer provisioning flow (not yet implemented)

```
1. Customer signs up → Stripe checkout
2. Stripe webhook fires → provisioning service
3. Provision: spin up new container, copy fresh engine_data.db template,
   set DASHBOARD_SECRET, inject API keys, start Flask
4. Send customer their instance URL + credentials
5. Customer completes first-run onboarding wizard (not yet designed)
```

Open decisions here:
- Container orchestration: Docker Compose on a single VPS (simple, right for early stage) vs. Fly.io/Railway per-app vs. K8s namespaces. Recommend Docker Compose to start.
- Stripe integration: webhook → entitlement check per instance, grace period on failed payment. Not yet designed.
- First-run onboarding wizard: not yet designed anywhere.

---

## Data / API key strategy (unresolved — flag before implementing)

### The yfinance problem
`yfinance` is against its ToS for commercial/SaaS use. Every isolated instance would still call Yahoo Finance endpoints. Options:
- **(a) Auto-provision free-tier keys per instance** — works for providers that have free tiers (e.g., Financial Modeling Prep, Alpaca Data)
- **(b) Shared metered proxy** — Ahmet runs a middle tier, all instances route through it, single paid key
- **(c) Bring-your-own-key onboarding** — customer provides their own API key on signup

No decision made yet. Blocks the provisioning design. Current keys in use:
- FRED (macro data)
- Twelvedata
- AlphaVantage
- Finnhub

### Key rotation reminder
**Ahmet still needs to manually:** rotate all 4 API keys (FRED, Twelvedata, AlphaVantage, Finnhub), audit git history for any `.env` secrets committed, set a real `DASHBOARD_SECRET`.

---

## Export / import — DONE ✅

`export_data.py` — standalone CLI tool at project root.

```bash
python export_data.py export --out backup.json --pretty
python export_data.py import backup.json --db engine_data.db
python export_data.py import backup.json --dry-run   # preview only
```

**Schema version:** `1.0` (bump `EXPORT_SCHEMA_VERSION` constant when tables change).

**Exports (9 user-owned tables):**
`trades`, `positions_history`, `cash_history`, `override_log`, `signal_queue`, `watchlist`, `divergence_labels`, `saved_portfolios`, `performance_history`

**Skips (14 pipeline-derived tables):** `prices`, `feature_store`, `fx_rates`, `signals`, `alpha_signals`, `model_outputs`, `price_targets`, `risk_metrics`, `pead_setups`, `regime_history*`, `pipeline_runs`, `pipeline_logs`, `data_validation_log`, `reconciliation_log`, `risk_events`

**Import is idempotent** (`INSERT OR IGNORE`) — safe to re-run, no duplicates.

---

## Schema migration framework (unresolved)

When new tables or columns are added (e.g., to `engine_data.db`), all existing customer instances need to be updated. Options:
- **Alembic** — proper migration framework, versioned migration scripts, most reliable
- **Hand-rolled** — `ALTER TABLE IF NOT EXISTS` scripts run on container start
- **Hybrid** — `_ensure_*_table()` lazy-creation pattern already in `flask_app.py` handles new tables; Alembic for column additions

No decision made. Recommend Alembic for anything beyond new table creation (column additions, renames, type changes can't be done with CREATE IF NOT EXISTS alone).

---

## Auth / access control (partially implemented)

- `DASHBOARD_SECRET` env var → basic HTTP auth gate on Flask dashboard. Added; **Ahmet still needs to set a real secret before any hosted exposure.**
- `FLASK_DEBUG` env var → controls debug mode. Do not ship with `FLASK_DEBUG=1`.
- No user accounts, no per-user roles — single-user dashboard per instance by design.

---

## Alerting (code done, wiring needed)

`engine/alerting.py` has Slack webhook + SMTP email alert code. Called from the pipeline for staleness and risk events.  
**Ahmet still needs to manually:** provide Slack webhook URL or Gmail app password + configure in `.env`. Task Scheduler heartbeat check not yet set up.

---

## Pricing / tiering (unresolved)

- Single flat monthly subscription vs. usage-based tiers — not yet confirmed.
- No public pricing exists yet.

---

## Known risks / gotchas for SaaS

| Risk | Status |
|---|---|
| yfinance ToS commercial violation | Unresolved — API key strategy decision needed |
| `order_manager.py` execution layer never end-to-end tested | Verify before enabling for any customer |
| SQLite WAL mode needed for concurrent reads | Set `PRAGMA journal_mode=WAL` in DB init for Flask + pipeline running simultaneously |
| No ADV liquidity gating | Missing check that trade value < 5% ADV in `order_manager.py` |
| No formal risk policy document | Max drawdown halt trigger, override protocol, sizing rationale — Ahmet's sign-off needed |
| `SOS-button.md` is empty | Panic-liquidate concept, no spec — ask before building |

---

## Files to read first for implementation work

```
before-go-live/
  PROJECT-STATE.md                 ← master index, always read first
  00-PRODUCTION-READINESS-VERDICT.md
  B1-B2-B3-security-hardening.md
  I1-light-theme.md                ← canonical light theme spec
  I2-signal-explainability.md      ← proportional explainability (not SHAP)
  I3-circuit-breakers.md
  I4-paper-trading-sandbox.md
  I5-benchmark-tracking.md
  impr/dashboard_improvements.md  ← HITL, conviction scoring, short advisory
  skills/                         ← these skill files
```

Do NOT use as implementation sources:
- `how-desktop.md` (wrong architecture)
- `how-to-make-money.md` Path 1 (PostgreSQL/shared-tenancy)
- `short-investing.md` (live IBKR execution — future only)
