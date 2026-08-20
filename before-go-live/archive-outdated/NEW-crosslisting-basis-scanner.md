> **STATUS (2026-08-20, written by Claude): NOT IMPLEMENTED.** Design doc only.
> **Prerequisites**: Build and calibrate `NEW-ticker-liquidity-tiering.md` FIRST.
> The guardrail in this scanner (suppressing alerts on thin names) depends on
> `engine/data/liquidity_classifier.py` and the `ticker_liquidity_tier` table.
> Also depends on native US close prices being stored — see "Ingestion change"
> section. Both are blocking; don't wire the Flask panel until they're in place.

# Cross-Listing Basis Scanner
# `engine/screens/crosslisting_divergence.py` (new)
# `engine/db/schema.sql` (one new table)
# `flask_app.py` (one new route + advisory panel)
# `engine/scheduler.py` (one new weekly step)
# Estimated time: 1–1.5 days

---

## What this does

Compares each `.DE` cross-listing's **Xetra EOD close** against its **native US
market EOD close** (FX-adjusted) and flags pairs where the gap exceeds a
threshold. Surfaced as an advisory panel in the dashboard — same HITL pattern
as the existing ETF divergence screen (`engine/screens/etf_divergence.py`).

This is not an arbitrage in the strict sense. It is an **EOD gap-catch screen**:
*after a big US after-hours move (earnings, news, macro) the German market may
not fully reprice until the next Xetra open. If the pipeline runs before that
repricing closes, it can flag the pair for human review.*

The screen is **information only** — it does not generate orders. You decide.

---

## Why this is NOT the same as a simple price comparison

A raw comparison of `NVD.DE close (EUR)` vs `NVDA close (USD)` has two
confounding problems:

1. **Close-time mismatch**: Xetra closes 17:30 CET (11:30am ET); NYSE closes
   22:00 CET (4pm ET). On any ordinary day, the two closes legitimately differ
   by 4.5 hours of US trading. This is *structural*, not a lag.
2. **Currency noise**: FX moves between the two closes contribute to the raw gap
   even when prices are perfectly synchronised in their local terms.

The correct metric is:

```
basis_pct = (xetra_eur_close / (us_usd_close × USDEUR_rate)) − 1
```

A persistently **negative** basis (Xetra cheaper than FX-adjusted US) is the
signal: the Xetra close hasn't priced in the US session's gain yet. This gap
is most meaningful **after a large US after-hours move** (earnings night,
macro event), where the German market simply hasn't opened yet.

Ordinary-day basis fluctuations of ±0.5–1.5% are structural noise from the
close-time mismatch — the threshold is calibrated to filter these out.

---

## Prerequisite: ingestion must store native US closes

Currently, `engine/data/ingestion.py` only fetches the US fallback ticker when
the primary `.DE` fetch fails (emergency fallback, line 458). For this scanner
to work, the native US close must be fetched and stored **every day** for every
`.DE` ticker that has a `TICKER_MAPPING` entry — regardless of whether the Xetra
fetch succeeded.

### What to add to `ingestion.py` (inside `run_ingestion()`)

After the main `persist_prices(df_eur)` call, add a second pass:

```python
# ── Cross-listing US close storage ──────────────────────────────────────────
# Fetch and persist native US closes for all .DE tickers that have a US
# mapping in TICKER_MAPPING. These are stored under the US ticker symbol
# (e.g. 'NVDA') — NOT relabelled as 'NVD.DE'. The crosslisting_divergence
# screen joins on (date, us_ticker) against this data.
# Only liquid cross-listings are used by the scanner (liquidity_classifier
# guardrail), but we store all of them — the classifier decides later.

from portfolio.src.config import TICKER_MAPPING

us_tickers_to_fetch = list(set(TICKER_MAPPING.values()))
logger.info(f"[crosslisting] Fetching {len(us_tickers_to_fetch)} native US closes")

df_us_raw = asyncio.run(_fetch_all_async(us_tickers_to_fetch, from_date, to_date))
if not df_us_raw.empty:
    from engine.data.validation import validate_prices
    df_us_clean = validate_prices(df_us_raw)
    if not df_us_clean.empty:
        # Apply FX (US tickers → EUR) — but also store the pre-conversion
        # USD close in a separate column for the basis scanner.
        # Simpler: store them as-is in USD in a dedicated table.
        _persist_us_closes(df_us_clean, fx_rates)
        logger.info(f"[crosslisting] Stored {len(df_us_clean)} native US close rows")
```

### New helper: `_persist_us_closes(df, fx_rates)`

Add to `ingestion.py`:

```python
def _persist_us_closes(df: pd.DataFrame, fx_rates: dict):
    """
    Stores native US closes for cross-listing basis scanner.
    Table: us_closes (date, ticker, close_usd, close_eur, source)
    close_usd: raw USD close (for basis calculation, no conversion)
    close_eur: FX-converted EUR equivalent at that date's rate
    These are the 4pm ET closes — distinct from the 11:30am ET Xetra closes
    stored in `prices`. The scanner uses the time mismatch explicitly.
    """
    from engine.db.db import get_session
    from sqlalchemy import text

    usd_eur_map = fx_rates.get('USDEUR', {})

    session = get_session()
    count = 0
    try:
        for _, row in df.iterrows():
            ticker   = row['ticker']
            date_str = str(row['date'])
            close_usd = float(row.get('adj_close') or row.get('close') or 0)
            if not close_usd:
                continue
            # USD→EUR using that day's rate
            rate = usd_eur_map.get(date_str, FALLBACK_USDEUR)
            close_eur = close_usd * rate

            session.execute(text("""
                INSERT INTO us_closes (date, ticker, close_usd, close_eur, source)
                VALUES (:date, :ticker, :close_usd, :close_eur, :source)
                ON CONFLICT (date, ticker) DO UPDATE SET
                    close_usd = excluded.close_usd,
                    close_eur = excluded.close_eur,
                    source    = excluded.source
            """), {
                'date':      date_str,
                'ticker':    ticker,
                'close_usd': close_usd,
                'close_eur': close_eur,
                'source':    row.get('source', 'yfinance'),
            })
            count += 1
        session.commit()
        logger.info(f"[crosslisting] Persisted {count} US close rows")
    except Exception as e:
        session.rollback()
        logger.error(f"_persist_us_closes failed: {e}")
        raise
    finally:
        session.close()
```

---

## Schema

```sql
-- Stores native US-market EOD closes (4pm ET) for cross-listed names.
-- Separate from `prices` because it is a different close time (4pm ET vs
-- 11:30am ET for Xetra). The basis scanner uses both tables together.
CREATE TABLE IF NOT EXISTS us_closes (
    date        TEXT    NOT NULL,
    ticker      TEXT    NOT NULL,   -- US symbol: 'NVDA', 'AAPL', etc.
    close_usd   REAL    NOT NULL,
    close_eur   REAL,               -- FX-converted at that date's USDEUR rate
    source      TEXT,
    PRIMARY KEY (date, ticker)
);

CREATE INDEX IF NOT EXISTS idx_us_closes_ticker ON us_closes (ticker, date);

-- Stores daily basis readings and flagged events for the scanner.
-- Not every day is flagged — only days where basis exceeds threshold.
CREATE TABLE IF NOT EXISTS crosslisting_basis (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    date            TEXT    NOT NULL,
    de_ticker       TEXT    NOT NULL,   -- e.g. 'NVD.DE'
    us_ticker       TEXT    NOT NULL,   -- e.g. 'NVDA'
    xetra_close_eur REAL    NOT NULL,   -- from `prices` table
    us_close_usd    REAL    NOT NULL,   -- from `us_closes` table
    fx_rate_usdeur  REAL    NOT NULL,   -- USDEUR rate used
    us_implied_eur  REAL    NOT NULL,   -- us_close_usd × fx_rate_usdeur
    basis_pct       REAL    NOT NULL,   -- (xetra / us_implied) - 1
    liquidity_tier  TEXT,               -- from ticker_liquidity_tier
    flagged         INTEGER DEFAULT 0,  -- 1 if |basis_pct| > threshold
    flag_direction  TEXT,               -- 'xetra_lagging' | 'xetra_leading'
    notes           TEXT,               -- auto-generated context string
    computed_at     TEXT    DEFAULT (datetime('now')),
    UNIQUE (date, de_ticker)
);

CREATE INDEX IF NOT EXISTS idx_clbasis_ticker ON crosslisting_basis (de_ticker, date);
CREATE INDEX IF NOT EXISTS idx_clbasis_flagged ON crosslisting_basis (flagged, date);
```

Add both blocks to `engine/db/schema.sql`. They will be picked up automatically
by `ensure_schema()` on the next process start (fixed in the 2026-08-20 session
to detect any missing table individually).

---

## Implementation

Create `engine/screens/crosslisting_divergence.py`:

```python
"""
engine/screens/crosslisting_divergence.py
==========================================
Cross-listing basis scanner — compares Xetra EOD close against FX-adjusted
US-market EOD close for .DE tickers that have a US mapping.

Detection:
  basis_pct = (xetra_eur_close / us_implied_eur) - 1
  where us_implied_eur = us_close_usd × USDEUR_rate

A negative basis > FLAG_THRESHOLD_PCT means Xetra is lagging the US close
(typical after-hours-move-not-yet-repriced scenario). Positive basis means
Xetra is trading at a premium (less actionable from a "buy the lag" angle).

Guardrail: 'thin' and 'unreliable' tickers from ticker_liquidity_tier are
SKIPPED — divergence on thin cross-listings is stale-quote noise, not signal.
Only 'liquid' tickers are flagged.

This is an advisory/informational screen, same pattern as etf_divergence.py.
No orders are generated. Surfaced in the Flask dashboard for human review.
"""

import logging
import pandas as pd
import numpy as np
from sqlalchemy import text
from datetime import datetime

from portfolio.src.config import TICKER_MAPPING

logger = logging.getLogger(__name__)

# ── Tuning knobs ─────────────────────────────────────────────────────────────
# A basis of ±1.5% is within normal close-time-mismatch noise on most days.
# Only flag when the gap meaningfully exceeds that structural noise floor.
FLAG_THRESHOLD_PCT = 0.02      # 2% — flag if |basis| exceeds this
FLAG_DIRECTION_MIN = -0.015    # Only flag xetra_lagging if basis < -1.5%
                                # (asymmetric: leading is less interesting)
LOOKBACK_DAYS = 20              # For rolling average (context only, not gate)


def detect_basis_gaps(date: str) -> list:
    """
    Compute basis for all liquid .DE cross-listings on `date`.
    Returns list of dicts — all computed, not just flagged ones. Caller persists.
    """
    from engine.db.db import get_session
    from engine.data.liquidity_classifier import get_tier

    session = get_session()
    results = []

    try:
        # Latest USDEUR rate for this date (or most recent available)
        fx_row = session.execute(text("""
            SELECT rate FROM fx_rates
            WHERE pair = 'USDEUR' AND date <= :d
            ORDER BY date DESC LIMIT 1
        """), {'d': date}).fetchone()

        if not fx_row:
            logger.warning("[crosslisting] No USDEUR rate available — skipping basis scan")
            return []

        fx_rate = float(fx_row[0])

        for de_ticker, us_ticker in TICKER_MAPPING.items():
            # Guardrail: skip thin/unreliable tickers
            tier = get_tier(de_ticker, date)
            if tier in ('thin', 'unreliable'):
                logger.debug(f"[crosslisting] Skipping {de_ticker} (tier={tier})")
                continue

            # Xetra close from prices table
            xetra_row = session.execute(text("""
                SELECT adj_close FROM prices
                WHERE ticker = :t AND date = :d
                LIMIT 1
            """), {'t': de_ticker, 'd': date}).fetchone()

            if not xetra_row or not xetra_row[0]:
                logger.debug(f"[crosslisting] No Xetra close for {de_ticker} on {date}")
                continue

            xetra_eur = float(xetra_row[0])

            # US close from us_closes table
            us_row = session.execute(text("""
                SELECT close_usd FROM us_closes
                WHERE ticker = :t AND date = :d
                LIMIT 1
            """), {'t': us_ticker, 'd': date}).fetchone()

            if not us_row or not us_row[0]:
                logger.debug(f"[crosslisting] No US close for {us_ticker} on {date}")
                continue

            us_usd = float(us_row[0])
            us_implied_eur = us_usd * fx_rate

            if us_implied_eur <= 0:
                continue

            basis_pct = round((xetra_eur / us_implied_eur) - 1.0, 6)

            flagged = abs(basis_pct) > FLAG_THRESHOLD_PCT
            # Further restrict: only flag lagging (negative) if below the direction minimum
            if flagged and basis_pct > 0:
                flagged = False  # Leading (Xetra premium) — informational but not flagged
            if flagged and basis_pct > FLAG_DIRECTION_MIN:
                flagged = False  # Not negative enough to be meaningful

            flag_direction = None
            if flagged:
                flag_direction = 'xetra_lagging' if basis_pct < 0 else 'xetra_leading'

            notes = (
                f"Xetra {xetra_eur:.2f} EUR vs US {us_usd:.2f} USD "
                f"(implied {us_implied_eur:.2f} EUR @ {fx_rate:.4f} USDEUR). "
                f"Basis: {basis_pct*100:+.2f}%."
            )

            results.append({
                'date':            date,
                'de_ticker':       de_ticker,
                'us_ticker':       us_ticker,
                'xetra_close_eur': xetra_eur,
                'us_close_usd':    us_usd,
                'fx_rate_usdeur':  fx_rate,
                'us_implied_eur':  round(us_implied_eur, 4),
                'basis_pct':       basis_pct,
                'liquidity_tier':  tier,
                'flagged':         1 if flagged else 0,
                'flag_direction':  flag_direction,
                'notes':           notes,
            })

    except Exception as e:
        logger.error(f"[crosslisting] detect_basis_gaps failed: {e}")
        raise
    finally:
        session.close()

    flagged_count = sum(1 for r in results if r['flagged'])
    logger.info(
        f"[crosslisting] {date}: {len(results)} pairs computed, "
        f"{flagged_count} flagged"
    )
    return results


def save_basis_records(records: list):
    """Upsert basis records to crosslisting_basis table."""
    if not records:
        return

    from engine.db.db import get_session

    session = get_session()
    try:
        for r in records:
            session.execute(text("""
                INSERT INTO crosslisting_basis
                    (date, de_ticker, us_ticker, xetra_close_eur, us_close_usd,
                     fx_rate_usdeur, us_implied_eur, basis_pct, liquidity_tier,
                     flagged, flag_direction, notes)
                VALUES
                    (:date, :de, :us, :xeur, :uusd, :fx, :uimpl,
                     :basis, :tier, :flagged, :dir, :notes)
                ON CONFLICT (date, de_ticker) DO UPDATE SET
                    basis_pct      = excluded.basis_pct,
                    flagged        = excluded.flagged,
                    flag_direction = excluded.flag_direction,
                    notes          = excluded.notes
            """), {
                'date':   r['date'],   'de':     r['de_ticker'],
                'us':     r['us_ticker'], 'xeur': r['xetra_close_eur'],
                'uusd':   r['us_close_usd'], 'fx': r['fx_rate_usdeur'],
                'uimpl':  r['us_implied_eur'], 'basis': r['basis_pct'],
                'tier':   r['liquidity_tier'], 'flagged': r['flagged'],
                'dir':    r['flag_direction'], 'notes': r['notes'],
            })
        session.commit()
        logger.info(f"[crosslisting] Saved {len(records)} basis records")
    except Exception as e:
        session.rollback()
        logger.error(f"[crosslisting] save_basis_records failed: {e}")
        raise
    finally:
        session.close()


def run_basis_scan(date: str):
    """Public entry point — detect and persist. Called from scheduler."""
    records = detect_basis_gaps(date)
    save_basis_records(records)
    return records


def get_flagged_basis(limit: int = 30) -> list:
    """Returns most recent flagged basis events for the dashboard panel."""
    from engine.db.db import get_session

    session = get_session()
    try:
        rows = session.execute(text("""
            SELECT date, de_ticker, us_ticker, xetra_close_eur,
                   us_close_usd, us_implied_eur, basis_pct,
                   liquidity_tier, flag_direction, notes
            FROM crosslisting_basis
            WHERE flagged = 1
            ORDER BY date DESC, ABS(basis_pct) DESC
            LIMIT :lim
        """), {'lim': limit}).fetchall()
        cols = ['date', 'de_ticker', 'us_ticker', 'xetra_close_eur',
                'us_close_usd', 'us_implied_eur', 'basis_pct',
                'liquidity_tier', 'flag_direction', 'notes']
        return [dict(zip(cols, r)) for r in rows]
    finally:
        session.close()
```

---

## Wiring into scheduler

Add to `engine/scheduler.py` alongside the daily steps:

```python
def step_crosslisting_basis():
    from engine.screens.crosslisting_divergence import run_basis_scan
    run_basis_scan(TODAY)

# in run_pipeline(), in the daily steps block (after ingestion, before ML):
_run_step('D5. Cross-listing basis scan', step_crosslisting_basis, dry_run)
```

Note: run daily (not weekly) — the gap-catch value is entirely in catching
the *next-session repricing*, which happens day-by-day.

---

## Flask panel

### New API endpoint — add to `flask_app.py`:

```python
@app.route("/api/crosslisting_basis")
def api_crosslisting_basis():
    """Flagged cross-listing basis gaps for the advisory panel."""
    from engine.screens.crosslisting_divergence import get_flagged_basis
    rows = get_flagged_basis(limit=25)
    for r in rows:
        r['basis_pct_display'] = f"{r['basis_pct']*100:+.2f}%"
    return jsonify(rows)
```

### Dashboard panel

Add an advisory panel to `templates/overview.html` (or a new
`templates/crosslisting.html` page following the `divergence.html` pattern):

```html
<!-- Cross-listing Basis Panel — advisory only, same visual as ETF divergence -->
<div class="panel">
  <div class="panel-header">
    <span class="panel-title">CROSS-LISTING BASIS GAPS</span>
    <span class="panel-badge">ADVISORY</span>
  </div>
  <p class="panel-note">
    Xetra close vs FX-adjusted US close. Negative basis = Xetra hasn't
    repriced yet after a US move. Liquid tickers only (thin names suppressed).
    This is informational — not a trade signal.
  </p>
  <table id="basis-table" class="data-table">
    <thead>
      <tr>
        <th>.DE Ticker</th>
        <th>US Ticker</th>
        <th>Xetra Close (EUR)</th>
        <th>US Implied (EUR)</th>
        <th>Basis</th>
        <th>Direction</th>
        <th>Date</th>
      </tr>
    </thead>
    <tbody id="basis-tbody">
      <tr><td colspan="7" style="opacity:.4">Loading…</td></tr>
    </tbody>
  </table>
</div>

<script>
fetch('/api/crosslisting_basis')
  .then(r => r.json())
  .then(rows => {
    const tbody = document.getElementById('basis-tbody');
    if (!rows.length) {
      tbody.innerHTML = '<tr><td colspan="7" style="opacity:.4">No gaps flagged today.</td></tr>';
      return;
    }
    tbody.innerHTML = rows.map(r => {
      const basisClass = r.basis_pct < -0.03 ? 'bad' : r.basis_pct < 0 ? 'warn' : 'neutral';
      return `<tr>
        <td>${r.de_ticker}</td>
        <td>${r.us_ticker}</td>
        <td>€${r.xetra_close_eur.toFixed(2)}</td>
        <td>€${r.us_implied_eur.toFixed(2)}</td>
        <td class="${basisClass}">${r.basis_pct_display}</td>
        <td>${r.flag_direction || '—'}</td>
        <td>${r.date}</td>
      </tr>`;
    }).join('');
  })
  .catch(() => {
    document.getElementById('basis-tbody').innerHTML =
      '<tr><td colspan="7" style="opacity:.4">Data unavailable.</td></tr>';
  });
</script>
```

---

## Calibration — do this before trusting the alerts

Same recommendation as the liquidity classifier:

1. **Run the scanner for 2–4 weeks** without acting on alerts. Look at the
   distribution of `basis_pct` values for your known-liquid names (`NVD.DE`,
   `APC.DE`, `MSF.DE`, `AMZ.DE`).
2. **Expected normal range**: on a typical day, basis should cluster within
   ±0.5–1.5% for liquid names. If you're seeing most days ±2%+, the threshold
   needs raising.
3. **True signal days to validate against**: earnings nights (NVDA, AAPL, etc.)
   where there was a large after-hours move. The scanner should flag these.
   If it misses them, the threshold is too high.
4. **Current `FLAG_THRESHOLD_PCT = 0.02` (2%)** is a reasonable starting point
   but is deliberately conservative — better to start too quiet and tune up
   than to be noisy immediately.

---

## Liquidity guardrail — how it works

```python
tier = get_tier(de_ticker, date)
if tier in ('thin', 'unreliable'):
    continue  # skip entirely
```

This is a hard skip — thin tickers never appear in the flagged list. The
rationale: for `639.DE` (Spotify), `TII.DE` (TI), `KLA.DE`, the Xetra close
is often stale by a session. A 3% basis there is normal, not a signal.
Once the classifier runs post-calibration and these tickers are correctly
classified as 'thin', they'll auto-drop from the scanner's output with no
other code changes needed.

---

## Explicitly out of scope

- No intraday monitoring — EOD pipeline only, matching the rest of the system
- No auto-trade trigger — HITL only, same as ETF divergence screen
- No "leading" (Xetra at premium to US) flagging by default — currently
  suppressed by `flag_direction` logic. This can be turned on later by
  removing the `if flagged and basis_pct > 0: flagged = False` gate.
- No pairs outside `TICKER_MAPPING` — purely European-only names (SAP, BMW,
  etc.) have no US listing to compare against and are not in scope
- No historical backtesting of basis signals — collect 2–4 weeks of live
  data first (same philosophy as the ETF divergence labeler)
- No GBP-listed cross-listings for now (AZN.L, BP.L, SHELL.AS) — the FX
  handling is more complex (pence → GBP → EUR) and the scanner doesn't include
  them until the GBP logic is validated separately
