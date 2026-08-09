# Control Tower — Project State & Handoff Notes

Last updated: 2026-08-10
Purpose: read this first in any new session to pick up exactly where things left off. Project lives at `C:\Users\ahmty\Desktop\hedge-fund` (accessed via Filesystem MCP connector - must be enabled in-chat to read/write it).

---

## 0. Changelog (most recent first)

**2026-08-10 (session 6) — Archive cleanup, no code changes (Claude, via Filesystem MCP):**
- **Moved J1, J2, J3, J4, J5 from `before-go-live/` root into `archive-implemented/`.** Verified each against this changelog and each doc's own status banner before moving (didn't trust the banners blindly, per the §0 2026-08-09 lesson about `archive-implemented/` integrity). J1/J2/J3 are fully closed. J4 and J5 are core-scope-done with one named follow-up each still open (J4: PEAD forward-trigger into `pead_alpha.py` not wired; J5: ticker-detail divergence-display UI not built) — archived anyway since the doc's main deliverable is live and the gaps are already tracked in §7b/§0 rather than being lost.
- **Left in root:** `J6-fundamental-data-source-decision.md` (open decision memo, no code to implement — recommends starting with yfinance, no `fundamental_data` table exists yet) and `J7-laggard-screen-wiring.md` (confirmed NOT implemented — no status banner, `run_laggard_screen()` still has no caller in `scheduler.py`).
- **Not otherwise touched:** no code, no other docs. `SOS-button.md` is still an empty stub — needs Ahmet's decision before anyone builds it.

**2026-08-10 (session 5) — J3, J4, J5 implemented; portfolio drawdown protocol drafted (Claude, via Filesystem MCP):**
- **J3 (Kelly sizing wire-in) - DONE.** `get_kelly_scalars()` (reads `kelly_half` from the latest `price_targets` row, clipped to 0.1-1.0) and `get_regime_scalar()` (0.6 in Risk-Off, 1.0 otherwise, reads `regime_state.json`) added to `engine/execution/order_manager.py`. Wired into `generate_order_queue()` as a BUY-only multiplicative scalar, gated by a new `apply_kelly_sizing` flag (default True) so it can be A/B tested in `SANDBOX_MODE`. Kelly was computed and stored since Session 5 of `todos/fix.md` but never affected order sizing until now.
- **J4 (earnings calendar) - DONE.** New `earnings_calendar` table in `schema.sql`. New `engine/data/earnings_calendar.py`: `fetch_earnings_calendar()` (Finnhub), `run_earnings_ingestion(symbol_to_primary)`, `get_reporting_soon()`, `get_recently_reported()`. Important fix vs. the original doc: Finnhub returns US-style symbols (NVDA) but this engine trades .DE-suffixed primary tickers (NVD.DE) - added a `symbol_to_primary` remap built from `TICKER_MAPPING` in `scheduler.py`'s new `step_earnings_calendar()` step, so calendar rows land under the same ticker key `order_manager.py` and the rest of the engine already use. Wired as daily pipeline step 3b. Pre-earnings BUY throttle (50% size cut within 3 days of a report) wired into `generate_order_queue()` alongside J3's Kelly scalar, gated by `apply_earnings_throttle`. Not done: the PEAD engine forward-trigger (original doc Step 4) - `get_recently_reported()` exists and is ready to call from `pead_alpha.py`, but PEAD still only reacts to price anomalies, not the calendar. Also not done: dashboard badge for upcoming earnings on held positions (doc's Step 5) - data-layer only this session. Needs Ahmet: confirm `FINNHUB_API_KEY` is actually set in `.env` (field already existed in `.env.example`) - this step logs a non-fatal warning and skips silently if it's blank.
- **J5 (sector-relative momentum) - DONE.** `compute_sector_relative_features()` added to `engine/features/feature_store.py` (intra-sector percentile rank across 1/3/6/12-month windows, neutral 0.5 for singleton sectors), wired into `run_feature_pipeline()`. New `engine/alpha/sector_momentum.py` - `SectorMomentumAlpha`, reads `sector_mom_12m`, RETURN_SCALE=0.03. Wired into both `step_alpha()`'s model_map (daily signal generation/persistence) and `step_portfolio_construction()`'s `models_dict` (so it gates through `is_live_approved()` and actually influences Black-Litterman posterior returns, not just sits in the `signals` table unused - same wiring mistake J3 found with Kelly, avoided here from the start). Not done: the ticker-detail page divergence display (doc's Step 4, showing universe-rank vs. sector-rank side by side) - data/signal layer only this session.
- **Portfolio-level Drawdown Protocol drafted - NOT implemented, needs Ahmet's sign-off.** Added new section 2b to `RISK-POLICY.md`: a 3-tier proposal (-10% alert-only / -15% halve new BUY sizing / -20% pause new BUYs, SELLs and circuit-breaker exits unaffected). This was flagged as a real gap in `BRAINSTORM-new-features-and-gaps.md` (existing Section 2 only covers per-position circuit breakers, nothing at the portfolio level). Explicitly a decision document, not code - three open questions logged in the doc itself (high-water-mark basis, manual vs. auto un-pause, whether it should interact with per-position breakers). `RISK-POLICY.md` bumped to v1.1 with a mixed implemented/proposed status line so the two don't get conflated later.
- **Status banners added to J3/J4/J5 docs** pointing back to this changelog entry, following the same pattern as J1/J2/I1-I5.
- **Not touched this session:** the data-provider/API-key decision (section 6/7a - Ahmet explicitly deferred this to last), sandbox 21-day dry run (I4's infrastructure already exists, just needs to actually be run and observed), and all "new alpha signal" ideas (quality factor, insider transactions, EPS revision) from `BRAINSTORM-new-features-and-gaps.md`.
- **Recommended next session:** run the sandbox dry run (`RUN_SANDBOX.bat`) with today's J3/J4/J5 changes live, comparing `apply_kelly_sizing`/`apply_earnings_throttle` True vs False, before any of this touches real capital. After that, the data-provider decision is the last major open item per Ahmet's own ranking.

**2026-08-09 (session 4) — Monetization + architecture brainstorm, legal checklist, archive cleanup (Claude, via Filesystem MCP):**
- **New doc: `SAAS-MONETIZATION-AND-SCALE-ARCHITECTURE.md`.** Covers pricing ($9.99/mo flat, no tiers), a concrete referral program design (1 free month per paid referral, 12/year cap, credit fires on friend's 2nd paid month, card-required trials), and — the substantive part — a redesign of the confirmed §2 hosting architecture. **Flags that the current 'isolated container + SQLite per customer' model does not scale economically past a few hundred users**, because the expensive work (data ingestion, features, ML inference, regime detection) is currently per-container but isn't actually customer-specific. Proposes splitting into a shared signal engine (runs once for everyone) + a cheap per-tenant portfolio-construction layer (Black-Litterman + personal settings only), with tenant_id-based row isolation on a shared Postgres instead of one DB per customer. Includes a 3-phase scale roadmap (0-1k / 1k-10k / 10k-100k+). **Not yet implemented — this revises the §2 architecture decision and needs Ahmet's sign-off before the SQLite->Postgres migration or scheduler split begins.**
- **New doc: `LEGAL-DOCS-CHECKLIST.md`.** Structural list of required legal pages (ToS, Privacy Policy, Financial/Investment Disclaimer, Billing Terms, Acceptable Use, Cookie Policy, Risk Disclosure, German Impressum, DPA/sub-processor list) with the sections each should cover. Explicitly a checklist to bring to a lawyer, not drafted legal text — no clause in it should be treated as launch-ready as written.
- **Regulatory risk elevated to the top open item.** Both new docs flag that generating personalized BUY/SELL/target-weight output for paying strangers is close to the legal definition of investment advice in most jurisdictions (SEC in the US, BaFin/MiFID II in Germany/EU) — ahead of pricing or infra as the thing to resolve first. Personalization (reading the user's actual holdings/tax settings and computing suggestions specific to them) is the trigger, not the BUY/SELL button label — removing or renaming the labels alone does not resolve this; see the answer logged in-chat this session for the full reasoning. Needs actual legal counsel before the first non-friend paying customer, not a documentation fix.
- **Archive hygiene: new `archive-outdated/` folder, distinct from `archive-implemented/`.** `archive-implemented/` is for finished work; `archive-outdated/` is for docs superseded by a later decision, which didn't have a home before. **Moved `how-desktop.md` here** — it's a single-user Windows desktop installer guide, which now directly conflicts with the SaaS multi-tenant hosting direction reaffirmed in this session's architecture doc (consistent with §7a's pre-existing 'do not implement' note on this file, just formalizing where it lives).
- **Not yet touched this session:** no code changes. `how-to-make-money.md` and `short-investing.md` were reviewed but left in place (still useful context, not fully superseded — see §7a). yfinance ToS / paid data provider decision still open (§6, §7a) — now more urgent per the new monetization doc's §0.

**2026-08-09 (session 3) — J1 (correlation cluster constraint) actually implemented and tested (Claude, via Filesystem MCP):**
- **Implemented directly in `engine/portfolio/optimizer.py`:** added `build_correlation_clusters()` (hierarchical clustering on the correlation-distance matrix), `build_cluster_constraints()`, and `persist_correlation_clusters()`. Wired into `optimize_with_bl()` via a new `apply_cluster_constraint=True` default parameter, and into `engine/scheduler.py`'s `step_portfolio_construction()` by passing `date=TODAY`.
- **Bonus fix found and applied in the same file:** `optimize_with_bl()` has always accepted a `sector_map` parameter to enforce `MAX_SECTOR_SHARE`, but `scheduler.py`'s only call site never passed one — meaning the 30%-per-sector constraint has **never actually been enforced in production**, despite `build_sector_constraints()` existing and being correctly implemented. Fixed by importing `TICKER_SECTORS` from `portfolio/src/config.py` and passing it through. This was the same class of bug as the Kelly-sizing gap found earlier (logic built, never wired to its caller) — worth scanning the rest of the codebase for the same pattern (a function with an optional parameter that every call site happens to skip).
- **Verified correctness with a synthetic test** (not just a syntax check): built a 5-asset covariance matrix with two genuinely correlated pairs (shared factor + noise) and one independent asset, confirmed `build_correlation_clusters()` correctly grouped the pairs and left the independent asset alone, and confirmed the resulting constraint function correctly flags a violation when 60% of the portfolio sits in one 2-asset cluster against the 25% cap.
- **Not yet done:** J2 (tax-aware selling), J3 (Kelly sizing wire-in), J4 (earnings calendar), J5 (sector-relative momentum), J6 (fundamental data decision — memo only, no code to write), J7 (laggard screen wiring) are all still spec-only, same as before this session.
- **Also archived** `todos/fix.md` and `todos/todo-general.md` (+ its implementation log) into a new `todos/archive-implemented/` folder — both had zero remaining open items per the corrections logged in session 2.

**2026-08-09 (session 2) — Corrections to session 1's audit + laggard screen wiring doc + regime stratification note (Claude, via Filesystem MCP):**
- **Corrected two claims from earlier today that were wrong.** Session 1 said "zero code exists" for both `laggard_screen_strategy.md` and `etf_component_divergence_strategy.md" — that was based on only reading the strategy docs, not checking `engine/screens/` or `scheduler.py`. Actually checking the code:
  - **ETF divergence screen is fully built and running daily** (`engine/screens/etf_divergence.py`, wired into `scheduler.py` as steps 9-10, with a live `/divergence` UI in `flask_app.py` + `templates/divergence.html`). Status banner corrected in `todos/etf_component_divergence_strategy.md`. Only real gap: `ETF_COMPONENT_MAP` only covers 3 ETFs, worth expanding.
  - **Laggard screen is partially built but never wired in.** `engine/screens/laggard_screen.py` implements the scoring logic but is never called from `scheduler.py`, has no dashboard route, and Phase 4 (disqualifier checks — the doc's own "most critical phase") is a stub that unconditionally passes everything. Status banner corrected in `todos/laggard_screen_strategy.md`; fix written up in `before-go-live/J7-laggard-screen-wiring.md` (wiring + a realistic partial-automation plan for Phase 4, since full automation of sanctions/governance/insider checks isn't realistic with current data sources).
- **Also corrected `todos/todo-general.md`:** Streams 6 and 7, which session 1 listed as the two remaining open items, are **both actually done** — verified directly: Stream 6 (drop Streamlit) has zero Streamlit references left in any `.bat` file or `.env.example`, Flask is the sole dashboard; Stream 7 (ML integrity) has both the 7-day purge/embargo buffer (`evaluator.py`) and correlation-based feature deduplication (`feature_builder.py`) already implemented, going beyond the original spec with a `get_walk_forward_report()` diagnostic. **This means `todos/todo-general.md` has no remaining open items at all** — worth archiving alongside `todos/fix.md` (also fully done, per session 1's notes).
- **New docs this session:** `before-go-live/J4-earnings-calendar.md`, `J5-sector-relative-momentum.md`, `J6-fundamental-data-source-decision.md`, `J7-laggard-screen-wiring.md`.
- **Lesson reinforced:** don't trust a strategy/todo doc's own "Status: TODO" header either — verify against `scheduler.py`'s step list and the actual module, both directions of error happened in the same day (docs marked done that weren't, and docs marked TODO that were actually built).

**2026-08-09 — Full audit + archive integrity fix + 3 new implementation-ready docs (Claude, via Filesystem MCP):**
- **Archive integrity bug found and fixed:** `archive-implemented/` contained 3 files that were never actually built — verified directly against live code, not just against this changelog. Moved back to `before-go-live/` root with STATUS banners:
  - `NEW-alpha-earnings-revision.md` — no `engine/alpha/earnings_revision.py`, no `fundamental_data` table, no `fundamental_ingestion.py` exist.
  - `NEW-alpha-quality-factor.md` — no `engine/alpha/quality_factor.py` exists (also depends on the fundamental ingestion above).
  - `NEW-feature-expansion-8-to-24.md` — `engine/features/feature_store.py` still computes exactly the original 8 features, none of the 16 proposed additions exist. Also stripped stray AI-meta content that had been pasted into the bottom of this file (an unrelated "institutional strengths/gaps" writeup that duplicated already-fixed items).
  - **Takeaway for future sessions: don't trust `archive-implemented/` at face value — spot-check against the actual code before assuming a doc's content is live, especially for anything moved there by a non-Claude tool session.**
- **`SOS-button.md` written from scratch** — was completely empty despite `RISK-POLICY.md` §4 referencing an "Emergency Halt (SOS Protocol)" as if built. Now a full spec with 3 options (Halt / Halt+Flatten / Halt+Tighten-breakers), recommends building Halt-only first. **Not yet implemented in code** — needs Ahmet's decision on which option(s) before building.
- **3 new ready-to-implement docs written** (same detail level as the archived B/H/I files), for gaps that were discussed at brainstorm level across multiple docs but never actually speced or built — verified against live code first:
  - `J1-correlation-cluster-constraint.md` — hierarchical clustering on the correlation matrix, 25% max weight per cluster, closes the gap where `optimizer.py` only constrains by ticker (10%) and nominal sector (30%), not actual statistical co-movement.
  - `J2-tax-aware-selling.md` — Abgeltungsteuer (26.375%) drag penalty on the optimizer's objective function for sells of positions with unrealized gains, reusing `get_average_entry_prices()` from I3's circuit breaker rather than re-deriving cost basis a second way.
  - `J3-kelly-sizing-wire-in.md` — found that `kelly_half` is computed and stored in `price_targets` (Session 5, `todos/fix.md`) and shown on the Risk page, but **never actually affects order sizing** in `order_manager.py` — confirmed directly, `generate_order_queue()` only uses `delta_w * total_portfolio_eur`. This doc wires it in as a buy-side sizing scalar.
- **None of J1/J2/J3/SOS are implemented yet** — these are specs only, same status as an unbuilt B/H/I doc before it's actioned. Pick up here: J1 and J3 are both small, single-file changes to `optimizer.py`/`order_manager.py` and are good candidates for the next coding session.

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

**2026-08-09 — I3 Circuit Breakers implemented:**
- Created `engine/risk/circuit_breaker.py` — standalone module with `get_average_entry_prices()` (weighted avg cost basis from trades table) and `run_circuit_breaker_check()` (compares current DB prices vs entry prices, fires CRITICAL log + `risk_events` row if drawdown ≤ threshold).
- Thresholds: individual stocks -15%, broad-market ETFs -12% (documented in docstring, record changes in TUNING-LOG.md).
- Wired into `step_portfolio_construction()` in `engine/scheduler.py` as a post-BL, pre-pre-trade hook: forced tickers get weight zeroed before the optimizer's suggestion hits the order queue. Non-fatal: if CB check fails (exception), pipeline continues with original weights.
- Added `/api/circuit_breakers` Flask route in `flask_app.py` — queries `risk_events` filtered to `event_type='circuit_breaker'` within last 7 days.
- Added red `🚨 CIRCUIT BREAKER ACTIVATED` alert banner to `overview.html` — hidden by default, appears automatically if any CB event exists in last 7 days, links to `/health` for full log.
- **(Verified 2026-08-09 by Claude, separate session):** confirmed this exists on disk exactly as described — `circuit_breaker.py` present, scheduler wiring present, syntax-checked clean. This was built by a different tool (Gemini Antigravity IDE) between Claude sessions — checks out, but worth spot-verifying cross-tool work rather than assuming it's correct.

**2026-08-09 — I5 Benchmark Equity Curve Overlay + Active Share — DONE (by Claude):**
- **`engine/scheduler.py`, `step_performance_log()`:** now computes and persists `benchmark_value_eur` each pipeline run — tracks MSCI World (`EUNL.DE`, via `BENCHMARK_TICKER`) as a parallel equity curve, normalized to the portfolio's first-deposit starting value. Wrapped in try/except, non-fatal if `prices` lacks benchmark data yet.
- **`flask_app.py`, `api_performance()`:** `perf_rows` query now selects `benchmark_value_eur`; response includes new `benchmark_series` array. Added `active_share_pct` + `benchmark_ticker` to `kpis` — Active Share computed as `(1 - ETF weight in current portfolio) * 100`, the rough proxy per spec (imports `ETF_TICKERS`, `BENCHMARK_TICKER` from `portfolio.src.config`).
- **`templates/analytics.html`:** equity chart renders a second dashed "MSCI World (EUNL.DE)" dataset aligned to the portfolio's date axis via date-keyed lookup (`spanGaps: true`, since benchmark history may start later). Added "ACTIVE SHARE" KPI tile, color-coded (green ≥80%, neutral ≥60%, red below — matches the "closet indexer" framing).
- **Note:** benchmark curve stays empty/flat until `EUNL.DE` has ≥2 days of price history post-ingestion — not a bug, just needs a couple of pipeline runs.
- `scheduler.py`, `flask_app.py`, `ledger_importer.py` all AST-syntax-checked clean after this round.

**Remaining I-series: I1 (light theme), I2 (signal explainability), I4 (paper trading sandbox) — not yet started.**


**2026-08-09 — I1 Light/Cream Theme Toggle — DONE (by Claude):**
- **Found first:** the I1 doc's spec used fictional CSS variable names (`--text-muted`, `--accent-red`, `--shadow`) that don't match the actual codebase (`--muted`, `--accent2`/`--accent3`, no `--shadow`). Adapted the whole implementation to the real variable set (`--bg`, `--surface`, `--surface2`, `--border`, `--accent`, `--accent2/3/4`, `--text`, `--muted`) rather than copy-pasting the doc's snippets verbatim.
- **Also found:** `base.html`'s top-level CSS was already almost entirely variable-driven (Phase 1 was largely already done) — only ~11 genuinely hardcoded colors existed outside the `:root` block itself.
- **`templates/base.html` changes:**
  - Anti-flash inline script as the very first thing in `<head>` (reads `localStorage['ct-theme']`, adds `.light-theme` class before first paint).
  - `html.light-theme { ... }` override block added right after `:root`, using the real variable names, cream/ivory palette per spec (`--bg:#fdfaf3`, `--surface:#ffffff`, `--text:#33302b`, `--accent:#059669` etc.).
  - Fixed two real bugs found along the way: `.logo-text` and the `.kpi-value`/`.kpi.neutral` default color were hardcoded `#fff` — invisible on a light background. Now use `var(--text)`.
  - Phase 5 special-component overrides added: `#tooltip` background, `.sig-lean-buy` color, scanline (`body::before`) opacity, `::-webkit-scrollbar` colors — all scoped under `html.light-theme`.
  - Theme toggle button (☀️/🌙) added to header, next to the clock. `toggleTheme()` persists to `localStorage`, and — important since Chart.js doesn't inherit CSS variables — re-colors `Chart.defaults` and every live chart instance's ticks/grid/legend on toggle via a new `_chartColors()` helper, replacing the two previously-hardcoded `Chart.defaults.color`/`.borderColor` lines.
- **`templates/analytics.html`:** fixed the equity-curve portfolio line, which I hardcoded to `#ffffff` earlier today building I5 — would've been invisible on a cream background. Now reads `var(--text)` via `getComputedStyle` and switches its fill color based on `.light-theme` presence.
- **Follow-up completed (2026-08-09):** Performed per-page Chart.js color audit across all remaining templates. Removed hardcoded ticks/grid colors in `ticker_detail.html`, `regime.html`, and `pairs.html` to allow inheritance from `Chart.defaults`. Converted hardcoded white line colors in `history.html` and `lab.html` to dynamic CSS variables based on the active theme.


**2026-08-09 — I2 Signal Explainability — DONE:**
- **Key lesson (repeat of I1):** verified actual code before touching anything — the I2 doc's code snippets don't exactly match reality (same caveat as I1). Inspect each file individually; don't paste doc snippets verbatim.
- **Verified before starting:**
  - `model_outputs` table definition confirmed — no `signal_breakdown` column yet (was not pre-existing).
  - `/api/rebalance` route found and read — uses `_q()` (returns plain mutable dicts, no ORM friction). Confirmed it does NOT yet return `signal_breakdown`.
  - `rebalance.html` JS row-builder inspected — identified exact injection point for the new "Why" column tags.
- **DONE — `engine/db/schema.sql`:** `signal_breakdown TEXT` column added to `model_outputs` table definition with comment `-- I2: JSON, e.g. {"momentum": 58.0, "ml_model": 31.0}`. Column confirmed present on disk (grep-verified 2026-08-09).
- **DONE — `engine/portfolio/black_litterman.py`:** Added logic to `run_black_litterman` to compute `signal_breakdown` directly from `signals_df` (using raw signal weights instead of SHAP), and updated signature to return `mu_bl, signal_breakdown`.
- **DONE — `engine/portfolio/optimizer.py`:** Updated `persist_model_outputs` to accept `signal_breakdown` and persist it as JSON.
- **DONE — `engine/scheduler.py`:** Updated the Black-Litterman and `persist_model_outputs` calls to capture and pass `signal_breakdown`.
- **DONE — `flask_app.py`:** Updated `/api/rebalance` to fetch and JSON-parse `signal_breakdown`.
- **DONE — `templates/rebalance.html`:** Added "WHY (SIGNAL BREAKDOWN)" column and generated colored signal tags using the JSON output.
- **DONE — Live DB migration:** Ran `ALTER TABLE model_outputs ADD COLUMN signal_breakdown TEXT` on `engine_data.db`. All Python files passed syntax checks.


**2026-08-09 — I4 Paper Trading Sandbox Gate — DONE:**
- **`engine/db/db.py`:** Added `SANDBOX_MODE` environment flag support. Overrides `DATABASE_URL` to use `sandbox_data.db` if set to `1`.
- **`engine/execution/paper_trader.py`:** Created new module with `execute_paper_orders` to record generated orders into the sandbox `trades` table without touching real cash, marking `source='paper'`.
- **`engine/scheduler.py`:** Wired `execute_paper_orders` to run at the end of `step_portfolio_construction` (after `generate_order_queue`) when `SANDBOX_MODE` is enabled. Also added a bypass for `send_digest` to prevent sandbox runs from firing Slack/Email alerts.
- **`RUN_SANDBOX.bat`:** Created root-level batch script to easily trigger the pipeline in sandbox mode.
- **`sandbox/promotion_checklist.md`:** Created the 21-day review checklist template for promoting models from sandbox to live.



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
8. ~~I3 — Circuit Breakers~~ — ✅ **DONE 2026-08-09.** `engine/risk/circuit_breaker.py` created, wired into `step_portfolio_construction()`, `/api/circuit_breakers` Flask route added, red 🚨 banner in `overview.html`.
9. ~~I5 — Benchmark overlay~~ — ✅ **DONE 2026-08-09.** `benchmark_value_eur` now populated in `step_performance_log()`, `benchmark_series` + `active_share_pct`/`benchmark_ticker` KPIs added to `/api/performance`, second dashed line + ACTIVE SHARE tile added to `analytics.html`.
10. ~~I1 — Light/cream theme toggle~~ — ✅ **DONE 2026-08-09.** Implemented in `base.html`. Follow-up per-page Chart.js color audit across all templates completed (removed hardcoded ticks/grid colors, updated dynamic line colors).
11. ~~I2 — Signal Explainability~~ — ✅ **DONE 2026-08-09.** Computed proportional breakdown in `black_litterman.py`, saved to DB via `optimizer.py`, surfaced in `flask_app.py` and `rebalance.html`.
12. ~~I4 — Paper Trading Sandbox Gate~~ — ✅ **DONE 2026-08-09.** `SANDBOX_MODE` env flag added to `db.py`, `paper_trader.py` execution built and wired into `scheduler.py` (with alert suppression), `RUN_SANDBOX.bat` launcher and `promotion_checklist.md` created.
13. ~~J3, J4, J5~~ — ✅ **DONE 2026-08-10.** Kelly sizing wired into order sizing, earnings calendar built and wired into the pre-earnings throttle, sector-relative momentum feature + alpha model wired into Black-Litterman. See session-5 changelog.
14. Portfolio-level Drawdown Protocol (`RISK-POLICY.md` §2b) — drafted as a proposal, needs Ahmet's sign-off before it's coded.
15. **Next up:** The still-open SaaS decision in §6 (API key/data-provider strategy — Ahmet has explicitly deferred this to last). Before that, recommend an end-to-end sandbox dry run (`RUN_SANDBOX.bat`) exercising today's J3/J4/J5 changes.

### Recently Completed:
- **Liquidity Gating (2026-08-09):** Added ADV (Average Daily Volume) checks to `engine/execution/order_manager.py`. The `generate_order_queue` now queries the `prices` table for the 21-day average daily volume in EUR. It caps order sizes at 5% of ADV (`adv_limit_pct=0.05`), logging a warning if an order is scaled down to prevent routing orders that are too large relative to the asset's normal trading volume.

## 8. How to resume a session efficiently

- Re-attach the Filesystem MCP connector to `C:\Users\ahmty\Desktop\hedge-fund` (has to be re-opted-in each new session it seems).
- Point Claude at this file first: `PROJECT-STATE.md` (this doc) — lives at `before-go-live\PROJECT-STATE.md`, naturally picked up alongside the other planning docs when the folder is read.
- This file is kept updated in place as decisions are made and blockers are cleared — treat it as the living source of truth, not a one-time snapshot.
