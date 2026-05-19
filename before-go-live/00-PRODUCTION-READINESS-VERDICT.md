# Production Readiness Verdict

## Overall Status: ⚠️ NOT PRODUCTION READY — 7 Hard Blockers

This system is architecturally sophisticated. The Black-Litterman pipeline,
regime detection, PEAD engine, Flask Live Reconstruction model, and alerting
digest structure are all of genuine institutional quality. The schema design,
`atomic_write_json`, staleness detection logic, and `state_paths.py` pattern
are all correct and well-built.

However, 7 hard blockers must be fixed before this manages real money.

---

## 🔴 HARD BLOCKERS — Fix before going live

| # | Issue | Fix File | Time |
|---|-------|----------|------|
| B1 | API keys (FRED, Twelvedata, AlphaVantage, Finnhub) in `.env` plaintext | `B1-B2-B3-security-hardening.md` | 20 min |
| B2 | No auth on Flask — `/api/log_trade` open to entire LAN | `B1-B2-B3-security-hardening.md` | 30 min |
| B3 | `debug=True` in production — Werkzeug Python shell exposed | `B1-B2-B3-security-hardening.md` | 5 min |
| B4 | `fee_debug.log` written to disk root on every `/api/performance` call | `B4-remove-fee-debug-log.md` | 10 min |
| B5 | `check_staleness()` exists but never called — stale data enters optimizer silently | `B5-wire-staleness-check.md` | 15 min |
| B6 | Alerting completely unconfigured — all alert fields blank in `.env` | `B6-configure-alerting.md` | 20 min |
| B7 | Duplicate `engine_data.db` at root AND in `brain/` — split-brain risk | `B7-remove-duplicate-db.md` | 5 min |

**Total time to clear all blockers: ~1.5 hours**

---

## 🟡 HIGH PRIORITY — Fix within first week live

| # | Issue | Fix File | Time |
|---|-------|----------|------|
| H1 | Raw `.cov()` covariance — no Ledoit-Wolf shrinkage, noisy optimizer weights | `H1-ledoit-wolf-covariance.md` | 30 min |
| H2 | All MC simulations use `seed=0` — same output every run, hides true tail risk | `H2-H3-mc-seeds-and-fx-fallback.md` | 15 min |
| H3 | FX fallback hardcoded in `ledger_importer.py`, not reading from DB `fx_rates` | `H2-H3-mc-seeds-and-fx-fallback.md` | 20 min |
| H4 | `_persist_single_price()` calls undefined `_q_execute` — silent bug, prices never persisted | `H4-H5-silent-code-bugs.md` | 5 min |
| H5 | `step_lstm_train()` defined twice in `scheduler.py` — second silently overwrites first | `H4-H5-silent-code-bugs.md` | 5 min |
| H6 | No tolerance bands — 0.1% drift generates rebalance orders every run | `H6-tolerance-bands.md` | 45 min |
| H7 | Config drift: ticker key mismatches between `ASSET_UNIVERSE` and `TICKER_SECTORS` | `H7-config-drift.md` | 30 min |

---

## 🟢 IMPROVEMENTS — After stable go-live

| # | Issue | Fix File |
|---|-------|----------|
| I1 | No light/cream theme | `I1-light-theme.md` |
| I2 | No signal explainability (Why is the model suggesting this trade?) | `I2-signal-explainability.md` |
| I3 | No hard stop-loss circuit breakers per position | `I3-circuit-breakers.md` |
| I4 | No paper trading sandbox gate before promoting new code | `I4-paper-trading-sandbox.md` |
| I5 | No benchmark equity curve overlay — cannot measure true alpha | `I5-benchmark-tracking.md` |

---

## Recommended fix order

```
Day 1 (before any live trades):
  B3 → B1 → B2 → B4 → B7 → B5 → B6

  Start with debug=True (B3, 5 min) because it's the highest-impact/lowest-effort.
  Then security (B1+B2), then housekeeping (B4, B7), then data integrity (B5),
  then alerting (B6 — requires external service setup).

Week 1 (first week with real money):
  H4 → H5 (silent bugs, 10 min total)
  H3 (FX fallback, 20 min)
  H2 (MC seeds, 15 min)
  H7 (config drift, 30 min)
  H1 (Ledoit-Wolf, 30 min)
  H6 (tolerance bands, 45 min)

Weeks 2–4:
  I5 (benchmark tracking — most useful for accountability)
  I3 (circuit breakers — important before position sizes grow)
  I2 (signal explainability — improves override quality)
  I1 (light theme — quality of life)
  I4 (paper sandbox — required before next major code change)
```

---

## What IS production-quality — do not change

- `_live_positions()` Live Reconstruction — correct and elegant design
- Database schema — proper indexes, `ON CONFLICT` upserts throughout
- `atomic_write_json()` — prevents half-written state file reads
- Pre/post trade risk check architecture — correctly structured
- `digest.py` alerting module — well-designed, just needs credentials
- `state_paths.py` single-source-of-truth pattern — correct
- `check_staleness()` logic in `validation.py` — correct, just not wired in
- Regime + PEAD as separate sub-engines — right architecture
- `DASHBOARD_ONLY` environment flag — good operational design
- `system_bootstrap.py` first-run schema — correct
- Multi-source FX fallback chain in `ingestion.py` — correct design
- `validate_prices()` volatility-adjusted spike detection — solid
