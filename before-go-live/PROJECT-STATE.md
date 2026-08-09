# Control Tower — Project State & Handoff Notes

Last updated: 2026-08-03
Purpose: read this first in any new session to pick up exactly where things left off. Project lives at `C:\Users\ahmty\Desktop\hedge-fund` (accessed via Filesystem MCP connector — must be enabled in-chat to read/write it).

---

## 0. Changelog (most recent first)

**2026-08-03 — Hard blockers B1–B7 addressed in code:**
- **B3 (debug=True):** Fixed. `flask_app.py` now reads `FLASK_DEBUG` env var (defaults to `0`/off).
- **B2 (no auth):** Fixed. Added `require_auth` decorator to `flask_app.py`, applied to `/api/log_trade`, `/api/override`, `/api/label`, `/api/sync_ledger`. Gated on `DASHBOARD_SECRET` env var — blank = open (dev mode), set it to require a token. **Ahmet: set `DASHBOARD_SECRET` in `.env` before this instance is ever reachable outside localhost.**
- **B4 (fee_debug.log):** Fixed. Removed the per-request file write and the `debug_ledger` list in `api_performance()`; replaced with a single `log.debug()` call. Emptied the existing `fee_debug.log` on disk (no delete tool available — file exists but empty; safe to manually delete).
- **B5 (staleness check not wired):** Fixed. `run_ingestion()` in `engine/data/ingestion.py` now calls `check_staleness()` after persisting prices, writes CRITICAL entries to `pipeline_logs` and `risk_events` on any stale ticker. Wrapped in try/except so a missing table doesn't crash ingestion.
- **B7 (duplicate DB):** Turned out to be **already resolved** — no `engine_data.db` exists under `brain/` anymore. Added `engine_data.db` / `*.db` to `.gitignore` anyway as a guard against recurrence.
- **B1 (plaintext keys):** Partially addressed — created `.env.example` with blank values, added `DASHBOARD_SECRET` and `FLASK_DEBUG` fields to both `.env` and `.env.example`. **Still needs Ahmet to do manually: rotate the FRED/Twelvedata/AlphaVantage/Finnhub keys via each provider's dashboard, and check `git log --all --full-history -- .env` to see if they were ever committed.** Claude has no way to run git commands or access provider dashboards on Ahmet's behalf.
- **B6 (alerting unconfigured):** No code fix needed — confirmed `engine/alerting/digest.py` exists and is already correctly built per the doc's claim. **Still needs Ahmet to do manually: create a Slack webhook or Gmail app password and add to `.env`, then schedule the heartbeat check via Windows Task Scheduler.**
- **Bonus finding:** H4 (`_persist_single_price()` calling undefined `_q_execute`) turned out to be **already fixed in the live code** — `_q_execute` is properly defined at line 163 of `flask_app.py` and works correctly. The H4 doc is stale; don't re-fix this.
- **Bonus finding:** `flask_app.py` already has `_ensure_signal_queue_table()` and a working `/api/watchlist/*` route set — meaning parts of the HITL/watchlist roadmap in `impr/dashboard_improvements.md` may already be partially built. **Not yet verified how complete this is — check before treating watchlist/signal-queue as greenfield work.**
- **H1 (Ledoit-Wolf covariance):** Fixed in `scheduler.py`.
- **H2 (MC seeds):** Fixed in `flask_app.py`.
- **H3 (FX fallback):** DB lookup instead of yfinance live-fetch fixed in `ledger_importer.py`.
- **H5 (duplicate function):** Removed the first (dead) `step_lstm_train` definition in `scheduler.py`.

- **H6 (tolerance bands):** Added logic in `order_manager.py` and `optimizer.py` to prevent noise trading.
- **H7 (config drift):** Standardized tickers to `.DE` and updated `TICKER_SECTORS` in `config.py`.

**2026-08-04 — Split-brain scheduler unified (§5 architectural debt):**
- **Split-brain fixed:** `flask_app.py`'s APScheduler `weekly_refresh` job was subprocess-calling `portfolio/recalculate_engine.py` (legacy CSV→JSON path; output never read by the dashboard). Replaced with a direct `from engine.scheduler import run_pipeline; run_pipeline()` call — the unified 13-step SQL pipeline. Schedule (Monday 17:00 CET) and DASHBOARD_ONLY guard preserved unchanged.
- **Cleanup:** Removed now-unused `import subprocess` from `flask_app.py`.
- **Deprecated:** Added a deprecation header to `portfolio/recalculate_engine.py` — it is no longer reachable from any production path; kept for reference, safe to delete once the unified pipeline is confirmed stable.

**2026-08-04 — Signal Queue / Watchlist verification (#4) + pipeline auto-push:**
- **Verified complete:** Watchlist (full CRUD, enrichment, conviction-trend tracking, auto-promote, ⚡ QUEUE button) and Signal Review Queue (pending table, approve/skip modal, regime-warning discount, Decision Journal, nav badges) are both fully built and wired. No greenfield work needed on the UI or backend CRUD.
- **One gap found and fixed:** `signal_queue` was never auto-populated by the pipeline — it was purely manual. Added `step_push_signals_to_queue()` to `engine/scheduler.py` as step 14. Runs after performance logging each daily pipeline run. Pushes long signals (conviction ≥ 0.65, AUC ≥ 0.53), short signals (conviction ≥ 0.45, regime-gated), and all active PEAD setups. Deduped: no re-insert if same ticker+signal_type already pending within 3 days. Source field = 'pipeline' or 'pead' so it's distinguished from manual queue entries.

**Not yet touched this session:** all I1–I5, all NEW-alpha-*, API key/data-provider decision (§rec #5), SaaS packaging (§6). Pick up here next.

**2026-08-04 — Export / import schema (#6) — DONE:**
- Built `export_data.py` — a standalone CLI tool (`python export_data.py export / import`) with schema version `1.0`.
- **Exports 9 user-owned tables:** `trades`, `positions_history`, `cash_history`, `override_log`, `signal_queue`, `watchlist`, `divergence_labels`, `saved_portfolios`, `performance_history`. Produces a versioned JSON bundle with metadata.
- **Skips 14 pipeline-derived tables** (prices, feature_store, fx_rates, signals, model_outputs, price_targets, regime_history etc.) — these re-compute on the next pipeline run so there’s no point migrating them.
- **Import is idempotent:** uses `INSERT OR IGNORE` — running twice leaves data intact, no duplicates. Verified on live DB (281 rows export/import, second run = 0 inserted).
- **Schema bump protocol:** increment `EXPORT_SCHEMA_VERSION` constant + add migration note in the constant block header when tables change.
- **Tested:** export → import → idempotent re-import on live DB, confirmed.


## 1. What this project is

**Control Tower** — a personal quant hedge fund engine (Flask + SQLite) built by Ahmet, now being turned into a **paid subscription product**. Core: Black-Litterman portfolio construction, regime detection, PEAD sub-engine, ML ensemble/LSTM signals, manual-approval execution (no live broker API), 12+ tab dashboard.

## 2. The pivot — confirmed architecture (do not re-litigate)

Ahmet confirmed the SaaS model on 2026-08-03:

- **Hosted, isolated, single-tenant per customer.** Each subscriber gets their own container/instance on Ahmet's infrastructure.
- **Not** a shared multi-tenant database.
- **Not** a local desktop app.
- Each instance has its **own separate SQLite file** — privacy via isolation, not via on-customer-hardware storage.
- Customers must be able to **export/import** their data (format not yet defined — open item).
- Single flat monthly subscription (tiering not yet confirmed either way).

## 3. Skills created this session

Three project skills were drafted (not yet run through the full skill-creator eval loop — built "vibe" style per Ahmet's preference for speed) and packaged as `.skill` files (delivered to Ahmet in-chat, not stored in this repo):

1. `hedge-fund-quant-engine.skill` — engine architecture, known bugs/blockers, alpha model conventions, roadmap priority.
2. `hedge-fund-dashboard-frontend.skill` — dark/light theme design system, UX roadmap (HITL review queue, conviction scoring, short-advisory panel).
3. `hedge-fund-saas-packaging.skill` — the confirmed hosting architecture, provisioning/auth/billing/API-key/migration/export requirements and open decisions.

**Next step if continuing skills work**: ask Ahmet if he wants to actually save/install these (via the Save skill button on the presented files) and/or run them through the skill-creator eval loop for triggering-accuracy tuning. Not yet done.

## 4. Source docs already read — FULL SWEEP COMPLETE (don't re-read blindly — reference instead)

All under `C:\Users\ahmty\Desktop\hedge-fund\before-go-live\`. Every file in the folder has now been read at least once as of 2026-08-03:

- `00-PRODUCTION-READINESS-VERDICT.md` — master index: 7 hard blockers (B1–B7), 7 high-priority silent bugs (H1–H7), 5 post-launch improvements (I1–I5), with fix-file pointers, time estimates, and recommended fix order
- `B1-B2-B3-security-hardening.md` — plaintext API keys, no Flask auth, `debug=True` — code-level fixes included
- `B4-remove-fee-debug-log.md` — stray `fee_debug.log` write on every `/api/performance` call — code-level fix included
- `B5-wire-staleness-check.md` — `check_staleness()` written but never called — code-level fix included
- `B6-configure-alerting.md` — Slack/email alerting unconfigured, heartbeat check not scheduled — setup steps included
- `B7-remove-duplicate-db.md` — stale `engine_data.db` copy in `brain/` from an old agent session — cleanup steps included
- `H1-ledoit-wolf-covariance.md` — raw `.cov()` instead of Ledoit-Wolf shrinkage — code-level fix included
- `H2-H3-mc-seeds-and-fx-fallback.md` — hardcoded MC seeds, hardcoded FX fallback instead of DB-sourced — code-level fixes included
- `H4-H5-silent-code-bugs.md` — undefined `_q_execute` call, duplicate `step_lstm_train()` definition — code-level fixes included
- `H6-tolerance-bands.md` — no drift tolerance bands, causes over-trading — code-level fix included
- `H7-config-drift.md` — ticker key mismatches between `ASSET_UNIVERSE`/`TICKER_SECTORS`/`TICKER_MAPPING` — code-level fixes included
- `I1-light-theme.md` — cream/light theme implementation, 5 phases, code included (canonical version — see §7a re: duplicates elsewhere)
- `I2-signal-explainability.md` — proportional signal-contribution breakdown for rebalance page (see §7a re: conflict with SHAP approach in improvements.md)
- `I3-circuit-breakers.md` — hard stop-loss per position, forced-exit logic — code-level implementation included
- `I4-paper-trading-sandbox.md` — isolated sandbox DB + paper execution + 21-day promotion checklist — code-level implementation included
- `I5-benchmark-tracking.md` — benchmark equity curve overlay + Active Share KPI — code-level implementation included
- `NEW-alpha-earnings-revision.md` — new alpha model (analyst estimate revision momentum), full implementation incl. new `fundamental_data` table
- `NEW-alpha-quality-factor.md` — new alpha model (ROE/leverage/earnings-stability composite, regime-conditional scaling), full implementation
- `NEW-feature-expansion-8-to-24.md` — expands LSTM feature set 8→24 features, full implementation; **trailing content is misplaced/unrelated — see §7a and §7b**
- `BRAINSTORM-new-features-and-gaps.md` — feature/alpha model roadmap, prioritized (origin doc for the NEW-alpha-* files above)
- `fix-before.md` — split-brain pipeline issue (legacy JSON scheduler vs. SQL scheduler), origin doc for the B/H items above
- `improvements.md` — origin/brainstorm doc for explainability, tax-aware selling, circuit breakers, benchmark tracking, override tracking, correlation-cluster constraints, the 15/30 concentration rule, retraining schedule, sandbox gate; **has leftover AI-meta-text pasted in — see §7a**
- `missing-parts.md` — deliberate scope exclusions (live broker API is explicitly optional, not a gap); origin doc for alerting, data validation, slippage modeling, light theme (**duplicated content — see §7a**)
- `how-desktop.md` — **CONFLICTS with confirmed architecture, do not implement** — see §7a
- `how-to-make-money.md` — three monetization paths (SaaS/B2B-license/trade-own-capital) explored before the architecture was confirmed; **Path 1 partially conflicts — see §7a** for the still-relevant yfinance ToS point
- `short-investing.md` — IBKR migration + live short-selling execution architecture; **future/optional, separate from the current informational short-advisory scope — see §7a**
- `SOS-button.md` — **empty file**, unspecified panic-button concept, nothing to act on yet
- `impr/dashboard_improvements.md` — HITL signal review queue, conviction scoring formula, short-sell advisory panel (informational-only — see §7a re: short-investing.md), watchlist, position sizing advisory, signal decay warnings, analytics attribution — full priority table included
- `impr/new.md` — one-line note ("add watchlist functionality") — already fully covered by dashboard_improvements.md Improvement 7, not a separate task

## 5. Known open technical issues (updated 2026-08-03 — see §0 changelog for what's now fixed)

**Hard blockers — STATUS AS OF 2026-08-03, see §0 for detail:**
- ~~Plaintext API keys in `.env`~~ — `.env.example` created; **key rotation + git-history check still needs Ahmet manually**
- ~~No Flask auth at all~~ — ✅ fixed, gated on `DASHBOARD_SECRET`
- ~~`debug=True` in production~~ — ✅ fixed, gated on `FLASK_DEBUG`
- ~~Stray debug log file write (`fee_debug.log`)~~ — ✅ fixed
- ~~`check_staleness()` written but never wired into ingestion~~ — ✅ fixed
- Alerting configured but not connected — code confirmed correct; **Slack/SMTP credentials + Task Scheduler setup still needs Ahmet manually**
- ~~Duplicate `engine_data.db` living in `brain/`~~ — already resolved on its own, `.gitignore` guard added

**Silent correctness bugs (H1–H7) — ALL FIXED:**
- ~~No Ledoit-Wolf shrinkage on covariance matrix (raw `.cov()` — noisy)~~ — ✅ fixed
- ~~Monte Carlo sims hardcoded `seed=0`~~ — ✅ fixed
- ~~Hardcoded FX fallback instead of DB-sourced rate~~ — ✅ fixed
- ~~`_persist_single_price()` calls undefined `_q_execute`~~ — turned out to already be fixed, `_q_execute` exists and works (H4 doc is stale)
- ~~`step_lstm_train()` defined twice in `scheduler.py` — second definition silently wins~~ — ✅ fixed
- ~~No tolerance bands on rebalancing — 0.1% drift triggers unnecessary trades~~ — ✅ fixed
- ~~Ticker key mismatches between `ASSET_UNIVERSE` and `TICKER_SECTORS`~~ — ✅ fixed

**Architectural debt:**
- Split-brain: `flask_app.py`'s own scheduler (legacy JSON state, `recalculate_engine.py`) vs. `engine/scheduler.py` (modern SQL path) — needs full unification before packaging for distribution.

## 6. SaaS-specific open decisions (not yet resolved — surface, don't assume)

- API key strategy across isolated customer instances: (a) auto-provision free-tier keys per instance, (b) Ahmet runs a shared metered proxy, or (c) bring-your-own-key onboarding.
- Export/import format spec — not yet designed. Needs versioned schema (JSON/CSV) covering positions, trade ledger, signal/override history, prefs.
- Schema migration framework for pushing updates across many isolated SQLite instances — not yet chosen (Alembic vs. hand-rolled).
- Provisioning automation (spin up new instance + fresh DB on signup) — not yet designed.
- Subscription-to-access binding mechanism (Stripe webhook → entitlement check per instance, grace period on failed payment) — not yet designed.
- Container orchestration choice for isolated per-customer hosting (Docker Compose on a VPS vs. Fly.io/Railway per-app vs. K8s namespaces) — not yet chosen; should match expected early customer count, not over-engineered.
- Pricing/tiering — flat vs. usage-based — not yet confirmed.
- First-run onboarding wizard (broker context, API keys if BYO) — not yet designed anywhere.

## 7a. ⚠️ Conflict Watch — read before implementing anything from these files

Full sweep of `before-go-live/` (including files not read in the first pass: B1–B7, H1–H7, I1–I5, NEW-alpha-*, how-desktop.md, how-to-make-money.md, short-investing.md, SOS-button.md) turned up docs that **actively conflict** with the confirmed SaaS architecture (§2) or with each other. Check here before acting on any of these topics.

- **`how-desktop.md` — DO NOT IMPLEMENT.** Full PyInstaller + Inno Setup Windows desktop packaging guide (client installs an .exe locally). This was written for a different distribution model than what's confirmed. Confirmed model is hosted/isolated containers, not a desktop app. Keep the doc for reference only; don't act on it unless the architecture decision changes again.
- **`how-to-make-money.md` Path 1 ("Quant SaaS") — PARTIALLY SUPERSEDED.** Recommends migrating to PostgreSQL + shared multi-tenant DB + Flask-Login. This conflicts with the confirmed per-customer-isolated-SQLite decision — don't migrate to Postgres/shared-tenancy based on this doc. **However, one point in it survives the architecture decision and is NOT yet resolved anywhere else: `yfinance` is against its ToS for commercial/SaaS use, regardless of multi-tenancy model, since every isolated instance would still be calling it.** This needs the same resolution path already flagged in §6 (API key/data-provider strategy) — likely means budgeting for a paid data provider (Polygon.io, Alpaca, Financial Modeling Prep) per the doc's suggestion, not just an API-key-per-customer workaround.
- **`short-investing.md` — FUTURE/OPTIONAL, separate from current short-advisory work.** This is a large, fully-speced architecture for migrating to Interactive Brokers and doing *live, real* short selling (margin, borrow fees, IBKR auto-liquidation, `ib_insync` execution layer). This is a different and much bigger undertaking than the short-sell advisory panel already speced in `impr/dashboard_improvements.md` (Improvement 2), which is explicitly **informational/inverse-ETF-only, no live execution, no broker API** — consistent with `missing-parts.md`'s existing verdict that live broker API integration is optional/not-for-us. Don't conflate the two — if asked to "build short selling," confirm which one is meant.
- **Signal explainability has two different specs — pick one before building.** `improvements.md` (item 1) wants true SHAP value integration. `I2-signal-explainability.md` specs a simpler proportional-contribution breakdown per alpha model (no SHAP, just normalized signal weights) — this is the more concrete, ready-to-implement version with actual schema/code. Recommend building I2's version first (SHAP is heavier and mentioned only at the brainstorm level); flag to Ahmet that "explainability" in casual conversation could mean either.
- **Light/cream theme content is triplicated.** The same roadmap appears in `missing-parts.md` (twice, seemingly pasted in by accident) and in `I1-light-theme.md` (the actionable, code-level version). Treat `I1-light-theme.md` as the single source of truth; the copies in `missing-parts.md` are brainstorm residue, not additional scope.
- **`improvements.md` and `NEW-feature-expansion-8-to-24.md` both have leftover AI-response artifacts pasted into them** (visible "Summary of Work" sections, meta-commentary like "Does this roadmap align with your vision?"). This is noise from a prior editing session, not actionable content — don't treat it as a separate task list from what's already in the B/H/I files.
- **`SOS-button.md` is empty** — a stub for a presumably panic-sell / emergency-liquidate-everything button, never fleshed out. No spec exists yet; ask Ahmet what he wants before building anything here.

## 7b. Genuinely new items found in this sweep (not in the B1–B7/H1–H7/I1–I5 lists)

Buried in `NEW-feature-expansion-8-to-24.md`'s trailing (misplaced) content — real and not duplicated elsewhere:

- **Missing liquidity/ADV gating in the order queue.** No check that a trade's value stays under ~5% of the asset's Average Daily Volume before routing. Worth adding alongside H6 (tolerance bands) since both live in `order_manager.py`.
- **No formal, written Risk Policy / governance document** — max drawdown halt trigger, override protocol criteria, position sizing rationale, benchmark mandate. This is a decisions-not-code item; needs Ahmet's sign-off, not implementation.
- **Execution/reconciliation modules appear never actually run** (no `__pycache__` present for them) — the full BL-weights → order-queue → broker-routing loop is unverified end-to-end. Recommend a dry-run/sandbox pass (ties directly into I4's paper trading sandbox) before trusting the pipeline with real capital.

## 7. Recommended next steps (pick up here)

1. **Ahmet's manual items:** rotate the 4 API keys + check git history for `.env`; set up Slack webhook or Gmail app password for alerting; set a real `DASHBOARD_SECRET` before any hosted exposure.
2. ~~Move on to H1–H7 (silent bugs)~~ — **ALL H1-H7 FIXED**.
3. ~~Resolve the split-brain pipeline issue~~ — ✅ **FIXED 2026-08-04** (weekly_refresh now calls `engine.scheduler.run_pipeline()` directly).
4. ~~Verify how complete the existing `signal_queue`/`watchlist` code in `flask_app.py` actually is before treating those as greenfield HITL work~~ — ✅ **DONE 2026-08-04** (both fully built; added pipeline auto-push `step_push_signals_to_queue()` as step 14 in `engine/scheduler.py`).
5. Make the API key/data-provider strategy decision — blocks both provisioning design and the yfinance ToS issue (§7a).
6. ~~Design the export/import schema~~ — **DONE 2026-08-04.** `export_data.py` created. Schema v1.0, 9 user tables exported to versioned JSON, idempotent import with `INSERT OR IGNORE`. Skips all pipeline-derived tables.
7. ~~Revisit the three drafted skills~~ — **DONE 2026-08-04.** All three re-drafted from scratch (with current codebase state) and saved to disk:
   - `before-go-live/skills/hedge-fund-quant-engine/SKILL.md`
   - `before-go-live/skills/hedge-fund-dashboard-frontend/SKILL.md`
   - `before-go-live/skills/hedge-fund-saas-packaging/SKILL.md`

## 8. How to resume a session efficiently

- Re-attach the Filesystem MCP connector to `C:\Users\ahmty\Desktop\hedge-fund` (has to be re-opted-in each new session it seems).
- Point Claude at this file first: `PROJECT-STATE.md` (this doc) — lives at `before-go-live\PROJECT-STATE.md`, naturally picked up alongside the other planning docs when the folder is read.
- This file is kept updated in place as decisions are made and blockers are cleared — treat it as the living source of truth, not a one-time snapshot.
