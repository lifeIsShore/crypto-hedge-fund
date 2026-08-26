> **STATUS (2026-08-26, written by Claude): NOT IMPLEMENTED.** Design doc only.
> This is `FINAL-GO-LIVE-CHECKLIST.md` item **2.4**. It is a wiring task, not new
> logic — both halves it connects already exist and are working independently:
> `get_recently_reported()` in `engine/data/earnings_calendar.py` (built for J4,
> see `archive-implemented/J4-earnings-calendar.md` Step 4 — flagged there as
> "ready to use, but `pead_alpha.py` still only reacts to price anomalies") and
> the PEAD engine's own weekly anomaly scan (`ml_quant_finance_research/quant_research/pead_engine/`).
> This doc closes that gap.

# 2.4 — Wire the PEAD Calendar Trigger
# Edit `engine/scheduler.py` + `ml_quant_finance_research/quant_research/pead_engine/screener.py`
# Estimated time: 2–3 hours

---

## The problem this closes

Confirmed directly against the live code:

- **`PEADAlpha.generate_signals()`** (`engine/alpha/pead_alpha.py`) only ever reads
  `shared/state/pead_setups.csv`. It has no awareness of the earnings calendar at all —
  it just consumes whatever the PEAD engine already wrote.
- **The PEAD engine itself** (`ml_quant_finance_research/quant_research/pead_engine/run_engine.py`)
  only runs on the weekly cadence (`run_pead_engine_weekly()`, called Mondays per
  `PROJECT-STATE.md`), and finds earnings events by fetching `fetch_all_earnings(PEAD_UNIVERSE)`
  and scanning everything in the `lookback_days=90` window for surprise/underreaction —
  it discovers "did someone report?" from the earnings data feed itself, not from
  `earnings_calendar` (the table J4 built specifically to answer that question forward-looking).
- **`get_recently_reported()`** (`engine/data/earnings_calendar.py`) already does exactly
  what's needed here — returns tickers that reported in the last N days, in the same
  primary-ticker form (`NVD.DE`, not `NVDA`) the rest of the engine uses — but grepping
  the codebase confirms it has zero callers. It was built and left unused, the same
  "logic exists, never wired to its caller" pattern already found and fixed for Kelly
  sizing (J3) and the sector constraint (session 3 bonus fix).

**Net effect today:** if a held position reports earnings on a Tuesday, nothing about
that fact reaches the PEAD alpha model until the next Monday's full-universe weekly
scan runs — up to a 6-day blind spot on exactly the setups PEAD exists to catch, since
PEAD's edge depends on entering within days of the surprise (`ACTIVE_WINDOW_DAYS = 21`
in `pead_alpha.py`, but `ENTRY_DAYS_AFTER_EARNINGS` in the engine's own config is much
tighter — check `pead_engine/config.py` before assuming the full 21 days is safe to wait).

---

## Design

Two small, additive pieces — **do not replace the weekly full-universe scan**, it stays
as the comprehensive fallback (per the original J4 doc: "keep the existing anomaly
detection as a fallback for tickers Finnhub doesn't cover"). This adds a fast path on
top of it:

1. **A daily scheduler step** that checks `get_recently_reported()` against the tickers
   that actually matter (current holdings + watchlist — not the full universe, to keep
   this cheap) and flags any that reported but have no fresh PEAD setup yet.
2. **A targeted single/few-ticker screen function** in the PEAD engine that can be
   called out-of-cycle for just those flagged tickers, instead of waiting for Monday's
   full run. This reuses the engine's existing `fetch_prices()` / `fetch_all_earnings()`
   / `screen_recent_earnings()` pipeline — just scoped to a small ticker list instead of
   `PEAD_UNIVERSE`, so it's fast enough to run daily.

---

## Implementation

### Step 1 — Targeted screen entry point in the PEAD engine

Add to `ml_quant_finance_research/quant_research/pead_engine/run_engine.py`, alongside
the existing `run()`:

```python
def run_targeted(tickers: list, lookback_days: int = 21) -> dict:
    """
    Fast path for run() — screens ONLY the given tickers instead of the full
    PEAD_UNIVERSE. Called by engine/scheduler.py's daily calendar-trigger step
    when get_recently_reported() flags a ticker outside the normal Monday cycle.

    Reuses cached regression models (does not refit) and a short earnings
    lookback (default 21d, vs. the weekly run's 90d) since this only needs to
    catch the specific event that triggered it, not backfill history.
    """
    if not tickers:
        return {}

    log.info(f"PEAD targeted screen — {len(tickers)} ticker(s): {tickers}")

    prices_df = fetch_prices(tickers, force_refresh=False)
    earnings_df = fetch_all_earnings(tickers, force_refresh=False)
    if earnings_df.empty:
        log.info("  No earnings data for targeted tickers — nothing to screen")
        return {}

    models = load_regression_models()
    if not models:
        log.warning("  No cached regression models — skipping targeted screen "
                     "(will be caught by next weekly run instead)")
        return {}

    setups_df = screen_recent_earnings(
        earnings_df, prices_df, models, lookback_days=lookback_days
    )

    if not setups_df.empty:
        _attach_regime_labels(setups_df)
        save_setups(setups_df)
        log.info(f"  {len(setups_df)} new setup(s) saved from targeted screen")

    db = load_setups()
    return write_pead_state(setups_df, db)
```

Note this deliberately skips `backfill_outcomes()` (Step 2 of the full `run()`) — that's
housekeeping for existing setups' drift tracking, not needed for a same-day trigger, and
skipping it is most of why this is fast enough to run daily.

### Step 2 — Daily scheduler step

Add to `engine/scheduler.py`:

```python
def step_pead_calendar_trigger():
    """
    Daily fast-path check: did any held/watchlisted ticker report earnings in
    the last 2 days? If so and it has no active PEAD setup yet, run a targeted
    PEAD screen for just that ticker instead of waiting for Monday's full scan.
    Non-fatal — logs and continues on any failure, same pattern as the other
    daily steps.
    """
    from engine.data.earnings_calendar import get_recently_reported
    from engine.alpha.pead_alpha import PEAD_SETUPS_PATH
    import pandas as pd

    watch_tickers = _get_held_and_watchlisted_tickers()  # existing helper — reuse
                                                           # whatever step_earnings_calendar()
                                                           # or the watchlist step already
                                                           # uses to build this list
    if not watch_tickers:
        return

    reported = get_recently_reported(watch_tickers, within_days=2)
    if not reported:
        return

    # Skip tickers that already have a fresh PEAD setup — no need to re-screen
    already_covered = set()
    if os.path.exists(PEAD_SETUPS_PATH):
        try:
            existing = pd.read_csv(PEAD_SETUPS_PATH)
            if 'entry_date' in existing.columns and 'ticker' in existing.columns:
                existing['entry_date'] = pd.to_datetime(existing['entry_date'], errors='coerce')
                recent_cutoff = pd.Timestamp(TODAY) - pd.Timedelta(days=5)
                already_covered = set(
                    existing[existing['entry_date'] >= recent_cutoff]['ticker']
                )
        except Exception as e:
            logger.warning(f"[pead_calendar_trigger] Could not read pead_setups.csv: {e}")

    to_screen = list(reported - already_covered)
    if not to_screen:
        logger.info(f"[pead_calendar_trigger] {len(reported)} ticker(s) reported "
                     f"recently, all already covered by an active setup")
        return

    logger.info(f"[pead_calendar_trigger] Triggering targeted PEAD screen for: {to_screen}")

    pead_dir = os.path.join(_PROJECT_ROOT, 'ml_quant_finance_research',
                             'quant_research', 'pead_engine')
    original_dir = os.getcwd()
    try:
        os.chdir(pead_dir)
        if pead_dir not in sys.path:
            sys.path.insert(0, pead_dir)
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "run_engine", os.path.join(pead_dir, "run_engine.py"))
        run_engine = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(run_engine)
        run_engine.run_targeted(to_screen)
        from engine.alpha.pead_alpha import _mirror_pead_to_shared
        _mirror_pead_to_shared(pead_dir)
    except Exception as e:
        logger.error(f"[pead_calendar_trigger] Targeted screen failed (non-fatal, "
                      f"Monday's full run will still catch it): {e}")
    finally:
        os.chdir(original_dir)
        if pead_dir in sys.path:
            sys.path.remove(pead_dir)
```

Wire it into `run_pipeline()` as a **daily** step (not the Monday-only block the weekly
PEAD refresh lives in) — placement matters: it needs to run **after** `step_earnings_calendar()`
(so `earnings_calendar` has today's data) and **before** `step_alpha()` (so a same-day
setup actually reaches `PEADAlpha.generate_signals()` on this same pipeline run, not just
in time for tomorrow):

```python
_run_step('3c. PEAD calendar trigger', step_pead_calendar_trigger, dry_run)
```

### Step 3 — `_get_held_and_watchlisted_tickers()` helper

If this doesn't already exist under a different name, add a small helper (or reuse
whatever `step_push_signals_to_queue()` — already in `scheduler.py` per session 4's
changelog entry — uses to enumerate current holdings, since the watchlist promotion
logic needs the same list):

```python
def _get_held_and_watchlisted_tickers() -> list:
    session = get_session()
    try:
        held = session.execute(text(
            "SELECT DISTINCT ticker FROM positions_history "
            "WHERE date = (SELECT MAX(date) FROM positions_history)"
        )).fetchall()
        watched = session.execute(text("SELECT DISTINCT ticker FROM watchlist")).fetchall()
        return sorted({r[0] for r in held} | {r[0] for r in watched})
    finally:
        session.close()
```

Deliberately scoped to holdings + watchlist, **not** the full 126-ticker universe — the
whole point of this fast path is that it's cheap enough to run daily, and PEAD only
matters for tickers you'd actually act on.

---

## Tuning notes

- `within_days=2` in `get_recently_reported()` mirrors J4's own default and the "1-2
  days ago" framing from the original Step 4 spec — a ticker that reported yesterday
  or the day before is squarely in the underreaction-detection window; widening this
  much further starts to overlap with what the weekly full scan already catches fine.
- The `already_covered` check uses a 5-day window, looser than the 2-day report window,
  so this doesn't re-screen a ticker the weekly Monday run already picked up mid-week.
- If `load_regression_models()` returns nothing (first-ever run, or cache cleared), this
  step correctly no-ops rather than fitting models synchronously inside the daily
  pipeline — model fitting is the expensive part of the PEAD engine and belongs in the
  weekly cycle only, per the existing 7-day re-fit check in `run()`.

## Explicitly out of scope for this doc

- Does not change PEAD's quality scoring, drift windows, or regression models — pure
  scheduling/trigger wiring.
- Does not touch the weekly Monday full-universe run — that stays exactly as-is, this
  is additive.
- Dashboard surfacing of "this setup arrived via same-day trigger vs. weekly scan" is
  not included — see `NEW-ui-badges.md` (2.5) for the earnings-related UI work, which
  is deliberately kept separate since it's a different layer (display, not signal wiring).
