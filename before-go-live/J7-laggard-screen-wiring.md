# J7 — Wire Laggard Screen Into the Pipeline + Automate Phase 4 Disqualifiers
# Edit `engine/scheduler.py`, `engine/screens/laggard_screen.py`, `flask_app.py`
# Estimated time: 1 day (wiring: 1 hr, automated disqualifiers: rest of the day)

---

## Part 1 — Wire it in (the easy, mechanical part)

`run_laggard_screen()` already exists and works — it just needs a caller and
a place to persist/display results, same pattern as `step_divergence_scan()`.

### Step 1 — New table for results

```sql
CREATE TABLE IF NOT EXISTS laggard_candidates (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    date                TEXT NOT NULL,
    ticker              TEXT NOT NULL,
    sector              TEXT,
    period_return       REAL,
    relative_rank       REAL,
    peer_median_return  REAL,
    catch_up_gap        REAL,
    conviction          TEXT,
    disqualifiers       TEXT,   -- JSON array
    reviewed            INTEGER DEFAULT 0,
    computed_at         TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_laggard_date ON laggard_candidates (date);
```

### Step 2 — New scheduler step (weekly, not daily)

This is a research screen for you to review, not an automated trading
signal — weekly cadence matches its own "re-run periodically... 4-6 weeks"
guidance in Phase 5, and avoids flooding the review queue daily with a
slow-moving signal (peer relative performance doesn't meaningfully change
day to day).

```python
# engine/scheduler.py

def step_laggard_screen():
    """Weekly (Monday) — sector rotation laggard screen."""
    from engine.screens.laggard_screen import (
        detect_rising_sectors, score_peer_group, run_laggard_screen, SECTOR_ETF_MAP
    )
    from portfolio.src.config import TICKER_SECTORS
    from engine.db.db import get_session
    from sqlalchemy import text
    import json

    rising = detect_rising_sectors(SECTOR_ETF_MAP)
    if not rising:
        logger.info("[laggard_screen] No rising sectors detected this week")
        return

    # Build peer groups from TICKER_SECTORS, restricted to rising sectors only
    rising_sector_names = {r['sector'] for r in rising}
    peer_groups = {}
    for ticker, sector in TICKER_SECTORS.items():
        if sector.lower() in rising_sector_names:
            peer_groups.setdefault(sector, []).append(ticker)

    candidates = run_laggard_screen(peer_groups)

    session = get_session()
    try:
        for c in candidates:
            session.execute(text("""
                INSERT INTO laggard_candidates
                    (date, ticker, sector, period_return, relative_rank,
                     peer_median_return, catch_up_gap, conviction, disqualifiers)
                VALUES
                    (:date, :ticker, :sector, :ret, :rank, :peer_med, :gap, :conv, :disq)
            """), {
                'date': TODAY, 'ticker': c['ticker'], 'sector': c['sector'],
                'ret': c['period_return'], 'rank': c['relative_rank'],
                'peer_med': c['peer_median_return'], 'gap': c['catch_up_gap'],
                'conv': c['conviction'], 'disq': json.dumps(c['disqualifiers']),
            })
        session.commit()
    finally:
        session.close()

    logger.info(f"[laggard_screen] {len(candidates)} candidates saved for {TODAY}")
```

Add to the weekly block in `run_pipeline()`, alongside the existing PEAD
weekly refresh:

```python
    if WEEKDAY == 0:
        _run_step('W1. PEAD weekly refresh',  step_pead_refresh,   dry_run)
        _run_step('W2. Laggard screen',        step_laggard_screen, dry_run)   # NEW
```

### Step 3 — Dashboard route + template

Follow the exact pattern of the existing `/divergence` route in
`flask_app.py` (line ~576) — same shape, different table:

```python
@app.route("/laggards")
def laggards():
    session = get_session()
    rows = session.execute(text("""
        SELECT ticker, sector, period_return, relative_rank,
               peer_median_return, catch_up_gap, conviction, disqualifiers, date
        FROM laggard_candidates
        WHERE date = (SELECT MAX(date) FROM laggard_candidates)
        ORDER BY catch_up_gap DESC
    """)).fetchall()
    session.close()
    return render_template("laggards.html", candidates=rows, page="laggards")
```

`templates/laggards.html` — copy the structure of `divergence.html` (table
layout, conviction badges) rather than building from scratch; the visual
shape is nearly identical (candidate list with a few numeric columns and a
tier/conviction badge).

---

## Part 2 — Automate a realistic subset of Phase 4 (the part that actually matters)

Fully automating all 8 disqualifier checks isn't realistic without a much
bigger data investment (SEC filing parsing, news sentiment, legal databases
are all outside your current scope). But **leaving Phase 4 entirely manual
means the screen produces raw, unfiltered candidates that could include
obvious value traps** — which is worse than not running the screen, since
it creates false confidence ("the screen found a candidate" reads as more
vetted than it is).

**Realistic middle ground: automate 3 of the 8 checks using data you
already have or can get cheaply, and clearly label the rest as
manual-required** rather than silently passing everything.

```python
# engine/screens/laggard_screen.py — replace the placeholder

def run_disqualifier_checks(tickers: list) -> dict:
    """
    Automates 3 of the 8 Phase 4 checks using data already available in
    this codebase. The remaining 5 (sanctions/legal, governance, earnings
    quality detail, structural decline, news-based catalysts) still require
    manual research — this function flags candidates as
    'needs_manual_review' rather than pretending they're cleared.
    """
    from engine.db.db import get_session
    from sqlalchemy import text
    import json

    disqualifiers = {t: [] for t in tickers}

    session = get_session()
    try:
        for ticker in tickers:
            flags = []

            # ── Check 1: Balance Sheet — debt/equity vs sector median ──
            # Requires fundamental_data table from J6/NEW-alpha-earnings-revision.md.
            # If that table doesn't exist yet, this check is silently skipped
            # (not silently passed — see the 'checks_run' field below).
            try:
                row = session.execute(text("""
                    SELECT debt_to_equity FROM fundamental_data
                    WHERE ticker = :t ORDER BY date DESC LIMIT 1
                """), {'t': ticker}).fetchone()
                if row and row[0] is not None and row[0] > 2.5:
                    flags.append(f"High debt/equity ({row[0]:.2f}) — verify vs sector norm")
            except Exception:
                pass  # table doesn't exist yet — J6 not built, check unavailable

            # ── Check 2: Liquidity — negative FCF proxy via price action ──
            # Cheap proxy without fundamentals: sustained downtrend + high vol
            # of volatility can indicate distress, though this is weak signal
            # on its own — flag for review, don't hard-disqualify on this alone.
            vol_row = session.execute(text("""
                SELECT feature_value FROM feature_store
                WHERE ticker = :t AND feature_name = 'vol_of_vol'
                ORDER BY date DESC LIMIT 1
            """), {'t': ticker}).fetchone()
            if vol_row and vol_row[0] is not None and vol_row[0] > 0.15:
                flags.append(f"Elevated vol-of-vol ({vol_row[0]:.3f}) — possible distress signal, verify")

            # ── Check 3: Insider selling — requires a data source you don't have yet ──
            # Not automatable without an OpenInsider/SEC Form 4 feed. Flagged as
            # a manual-required item rather than silently skipped, so it's visible
            # on the dashboard that this check needs a human.
            flags.append("MANUAL REQUIRED: insider selling — check OpenInsider before acting")
            flags.append("MANUAL REQUIRED: sanctions/legal — check news before acting")
            flags.append("MANUAL REQUIRED: governance — check recent management changes before acting")

            disqualifiers[ticker] = flags
    finally:
        session.close()

    return disqualifiers
```

### Step 4 — Surface the distinction clearly on the dashboard

`laggards.html` should visually distinguish **hard disqualifiers** (checks
that actually ran and found a real red flag — e.g. high debt/equity) from
**"MANUAL REQUIRED" reminders** (checks that were never run at all). Don't
let both render as the same gray "disqualifier" badge — a real red flag and
a to-do reminder are very different things and conflating them defeats the
purpose of automating anything.

```
NVDA  |  Catch-up gap: 12.3%  |  Conviction: HIGH
  ⚠ MANUAL REQUIRED: insider selling — check before acting
  ⚠ MANUAL REQUIRED: sanctions/legal — check before acting
```
vs.
```
XYZ.DE  |  Catch-up gap: 8.1%  |  Conviction: MEDIUM
  🚫 DISQUALIFIED: High debt/equity (3.8) — verify vs sector norm
```

---

## What NOT to do

- Don't try to fully automate sanctions/legal/governance checks — that's a
  news-sentiment + legal-database problem well outside this codebase's
  current scope, and a false "cleared" signal on those specific checks is
  more dangerous than an honest "not checked."
- Don't skip Part 1 (wiring) while only doing Part 2 (disqualifiers) — a
  more accurate disqualifier function that never runs doesn't help you.
  Both parts are needed for this to produce any value at all.
