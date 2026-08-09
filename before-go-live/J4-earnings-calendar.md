> **STATUS (2026-08-10): IMPLEMENTED — see PROJECT-STATE.md session-5 changelog.**
> `earnings_calendar` table added to schema, `engine/data/earnings_calendar.py`
> created (fetch + persist + `get_reporting_soon()` + `get_recently_reported()`),
> wired into `scheduler.py` as a daily step and into `order_manager.py`'s
> pre-earnings BUY throttle. PEAD forward-trigger (original Step 4) NOT yet
> wired into the PEAD engine itself — `get_recently_reported()` exists and is
> ready to use, but `pead_alpha.py` still only reacts to price anomalies.
> This doc is kept as design rationale.

# J4 — Earnings Calendar Integration
# New: `engine/data/earnings_calendar.py` + `earnings_calendar` table
# Estimated time: 1 day. Uses your existing Finnhub key — no new provider needed.

---

## The problem this closes

`engine/alpha/pead_alpha.py` reacts to earnings **after** they've happened —
it reads `pead_setups.csv`, generated once a surprise is already priced in.
There is no forward-looking calendar anywhere in the codebase (checked
`engine/data/` — only `ingestion.py` exists, no calendar file). This means:

1. You can't pre-size a position down before a binary earnings event —
   a stock the BL optimizer wants at 8% could report tomorrow and gap 15%
   overnight with zero warning on the dashboard.
2. The PEAD engine has to *discover* that earnings happened by scanning for
   price/volume anomalies after the fact, rather than knowing in advance
   which tickers to watch closely on which dates.

This is Gap 3 in `BRAINSTORM-new-features-and-gaps.md`, fully speced there
at a conceptual level but never built.

---

## Design

Two consumers of one new table:
1. **Pre-earnings position throttle** — a multiplicative sizing scalar
   (similar pattern to J3's Kelly scalar) that shrinks new BUY orders for
   tickers reporting within N days.
2. **PEAD trigger** — instead of `pead_engine` having to detect an earnings
   event happened by scanning prices, it can check the calendar directly
   and know exactly when to look.

---

## Implementation

### Step 1 — New table

```sql
CREATE TABLE IF NOT EXISTS earnings_calendar (
    ticker           TEXT NOT NULL,
    report_date      TEXT NOT NULL,
    report_time      TEXT,     -- 'BMO' (before market open) or 'AMC' (after close)
    eps_estimate     REAL,
    revenue_estimate REAL,
    fetched_at       TEXT DEFAULT (datetime('now')),
    PRIMARY KEY (ticker, report_date)
);
CREATE INDEX IF NOT EXISTS idx_earnings_date ON earnings_calendar (report_date);
```

### Step 2 — Weekly ingestion via Finnhub

You already have a Finnhub key (per `improvements.md` Phase 3 item 4 —
`d82nd81r01qmgc0gq7c0d82nd81r01qmgc0gq7cg`, though per your instructions I'm
not touching key rotation/handling here, that's yours to manage). Finnhub's
free tier covers `/calendar/earnings` for the next ~30 days.

```python
# engine/data/earnings_calendar.py
"""
Weekly earnings calendar fetch. Runs Sundays alongside fundamental_ingestion
(if you build J-alpha docs / NEW-alpha-*.md — this shares the "light Sunday
job" slot with that ingestion rather than adding a third scheduled job).

Finnhub free tier: 60 calls/min, calendar endpoint covers ~30 days forward.
"""
import requests
import logging
import os
from datetime import date, timedelta
from sqlalchemy import text
from engine.db.db import get_session

logger = logging.getLogger(__name__)

FINNHUB_BASE = "https://finnhub.io/api/v1/calendar/earnings"
LOOKAHEAD_DAYS = 30


def fetch_earnings_calendar(api_key: str = None) -> list:
    """Fetches upcoming earnings dates for the next LOOKAHEAD_DAYS. Returns raw Finnhub rows."""
    api_key = api_key or os.getenv("FINNHUB_API_KEY")
    if not api_key:
        logger.error("[earnings_calendar] FINNHUB_API_KEY not set — skipping")
        return []

    today = date.today()
    to_date = today + timedelta(days=LOOKAHEAD_DAYS)

    try:
        resp = requests.get(FINNHUB_BASE, params={
            "from": today.isoformat(),
            "to": to_date.isoformat(),
            "token": api_key,
        }, timeout=15)
        resp.raise_for_status()
        return resp.json().get("earningsCalendar", [])
    except Exception as e:
        logger.error(f"[earnings_calendar] Fetch failed: {e}")
        return []


def run_earnings_ingestion(tradeable_tickers: set) -> int:
    """
    Fetches and persists earnings dates, filtered to your actual universe
    (Finnhub returns the whole US market — no point storing thousands of
    tickers you'll never trade).
    """
    rows = fetch_earnings_calendar()
    if not rows:
        return 0

    session = get_session()
    count = 0
    try:
        for row in rows:
            ticker = row.get("symbol")
            if ticker not in tradeable_tickers:
                continue
            session.execute(text("""
                INSERT INTO earnings_calendar
                    (ticker, report_date, report_time, eps_estimate, revenue_estimate)
                VALUES (:ticker, :report_date, :report_time, :eps_est, :rev_est)
                ON CONFLICT (ticker, report_date) DO UPDATE SET
                    report_time      = :report_time,
                    eps_estimate     = :eps_est,
                    revenue_estimate = :rev_est,
                    fetched_at       = datetime('now')
            """), {
                "ticker": ticker,
                "report_date": row.get("date"),
                "report_time": row.get("hour"),  # Finnhub returns 'bmo'/'amc'/'dmh'
                "eps_est": row.get("epsEstimate"),
                "rev_est": row.get("revenueEstimate"),
            })
            count += 1
        session.commit()
    finally:
        session.close()

    logger.info(f"[earnings_calendar] {count} earnings dates persisted (of {len(rows)} fetched)")
    return count
```

**Note on European tickers (`.DE`, `.PA`, etc.):** Finnhub's earnings
calendar coverage is much thinner outside the US. Expect this to mostly
populate for your US names. That's fine — the throttle in Step 3 simply
won't trigger for `.DE` tickers without data, same graceful-degradation
pattern already used elsewhere in your codebase (e.g. options data being
`NaN` for European tickers per `todo-general.md`'s Notes section).

### Step 3 — Pre-earnings position throttle in `order_manager.py`

Same integration point and pattern as J3's Kelly scalar — add alongside it,
not as a separate pass over the order list:

```python
# engine/execution/order_manager.py

EARNINGS_THROTTLE_DAYS = 3       # start throttling this many days before report
EARNINGS_THROTTLE_SCALAR = 0.5   # cut new BUY size in half heading into earnings


def get_upcoming_earnings(tickers: list, within_days: int = EARNINGS_THROTTLE_DAYS) -> set:
    """Returns the subset of tickers reporting within `within_days` of today."""
    session = get_session()
    try:
        placeholders = ','.join([f':t{i}' for i in range(len(tickers))])
        params = {f't{i}': t for i, t in enumerate(tickers)}
        rows = session.execute(text(f"""
            SELECT DISTINCT ticker FROM earnings_calendar
            WHERE ticker IN ({placeholders})
            AND date(report_date) BETWEEN date('now') AND date('now', '+{within_days} days')
        """), params).fetchall()
        return {r[0] for r in rows}
    finally:
        session.close()
```

Inside `generate_order_queue()`, right next to the Kelly scalar block from
J3 (both are BUY-only sizing scalars, same reasoning — don't shrink sells,
you want risk-reducing trades to go through at full size, especially heading
into an unpredictable earnings print):

```python
        # ... existing Kelly scalar block from J3 ...
        if action == "BUY" and apply_earnings_throttle:
            upcoming_earnings = upcoming_earnings_set  # computed once outside the loop
            if ticker in upcoming_earnings:
                pre_throttle_eur = abs_delta_eur
                abs_delta_eur *= EARNINGS_THROTTLE_SCALAR
                logger.info(
                    f"[Earnings Throttle] {ticker}: €{pre_throttle_eur:,.0f} -> €{abs_delta_eur:,.0f} "
                    f"(reports within {EARNINGS_THROTTLE_DAYS}d)"
                )
```

(Compute `upcoming_earnings_set = get_upcoming_earnings(list(suggested_weights.index))`
once at the top of `generate_order_queue()`, same as `kelly_scalars` in J3.)

### Step 4 — Feed the PEAD engine forward instead of only backward

In `pead_engine/` (wherever `run_engine.py` lives), add an earnings-calendar
check as a *trigger*, not just a post-hoc detector: on each pipeline run,
query `earnings_calendar` for tickers that reported in the last 1-2 days and
prioritize those for PEAD setup evaluation first, rather than scanning the
full universe for anomalies. This doesn't replace the existing anomaly
detection (keep it as a fallback for tickers Finnhub doesn't cover) — it
just gives PEAD a fast path for the tickers you do have calendar data on.

### Step 5 — Surface on the dashboard

- **Overview page:** small badge next to any held position reporting within
  3 days — "NVDA reports Thu AMC" — this is the single highest-value UI
  addition here, it's exactly the "risk event log" from Gap 3's original spec.
- **Health page:** count of upcoming earnings in the next 7 days across your
  holdings, as a simple heads-up metric.

---

## Tuning notes

- `EARNINGS_THROTTLE_DAYS = 3` and `EARNINGS_THROTTLE_SCALAR = 0.5` are
  starting points from the original brainstorm doc ("reduce position size
  by 30% 3 days before report" was the original suggestion — I used 50%
  here since binary earnings risk on a fresh entry is a bigger unhedged bet
  than on an existing position; tune to your own risk tolerance).
- Consider **not** throttling SELLS or existing-position trims at all near
  earnings — if the optimizer wants to reduce a position ahead of a report,
  let that go through at full size; that's risk reduction, which you want
  faster, not slower, heading into a binary event.
