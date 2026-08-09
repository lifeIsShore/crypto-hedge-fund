# B5: Wire `check_staleness()` into Ingestion Pipeline
**Blocker: 5 of 7 | File: `engine/data/ingestion.py`**

---

## What is wrong

`engine/data/validation.py` has a complete, correct `check_staleness()` function
that detects tickers with data gaps larger than 3 days:

```python
def check_staleness(df: pd.DataFrame, max_gap_days: int = 3) -> list:
    """
    Detects tickers with gaps larger than max_gap_days.
    Returns list of {ticker, last_date, gap_days} dicts.
    """
```

This function is **never called** during the main ingestion run. The validation
function `validate_prices()` IS called (it correctly rejects price spikes and
zero prices), but staleness is silently ignored.

**Consequence:** If yfinance stops returning data for a ticker (IP block, API
change, delisting, corporate action), the optimizer will continue using the last
known price — possibly weeks old — without any warning. This corrupts:
- Portfolio weights (stale price = wrong value_eur)
- Black-Litterman expected returns
- Risk metrics (VaR based on wrong current price)

---

## Fix

At the end of `run_ingestion()` in `engine/data/ingestion.py`, after prices have
been written to the DB, load them back and run the staleness check. Then write
any stale tickers as `CRITICAL` events to `pipeline_logs` so they appear on
`health.html`.

Find the end of `run_ingestion()` and add:

```python
# ── Post-ingestion staleness check ────────────────────────────────────────
from engine.data.validation import check_staleness
from engine.db.db import get_session
from sqlalchemy import text as _text

# Load last-known dates for all tickers from DB
session = get_session()
try:
    rows = session.execute(_text("""
        SELECT ticker, MAX(date) as last_date, MAX(date) as date, adj_close
        FROM prices
        GROUP BY ticker
    """)).fetchall()
finally:
    session.close()

if rows:
    stale_df = pd.DataFrame([
        {"ticker": r[0], "date": r[1], "adj_close": 1.0}  # adj_close dummy for check
        for r in rows
    ])
    stale_list = check_staleness(stale_df, max_gap_days=3)

    if stale_list:
        stale_tickers = [s["ticker"] for s in stale_list]
        logger.warning(
            f"⚠️  STALE DATA DETECTED: {len(stale_list)} tickers — {stale_tickers}"
        )
        # Write to pipeline_logs so health.html shows it
        session2 = get_session()
        try:
            for s in stale_list:
                session2.execute(_text("""
                    INSERT INTO pipeline_logs (level, step_name, message, detail, run_date)
                    VALUES ('CRITICAL', 'data_ingestion',
                            :msg, :detail, date('now'))
                """), {
                    "msg": f"STALE: {s['ticker']} last seen {s['last_date']} ({s['gap_days']} days ago)",
                    "detail": str(s),
                })
            session2.commit()
        finally:
            session2.close()

        # Also write to risk_events so overview.html shows it
        session3 = get_session()
        try:
            for s in stale_list:
                session3.execute(_text("""
                    INSERT INTO risk_events (date, event_type, ticker, detail)
                    VALUES (CURRENT_DATE, 'stale_data', :ticker, :detail)
                """), {
                    "ticker": s["ticker"],
                    "detail": f"Data {s['gap_days']} days stale (last: {s['last_date']})",
                })
            session3.commit()
        finally:
            session3.close()
    else:
        logger.info("✅ Staleness check: all tickers fresh.")
```

---

## Why this is a blocker

The existing `before-go-live/fix-before.md` already identified this:
> "Undetected Staleness: `check_staleness` function is not called during the
> main `run_ingestion` flow."

The function is written and correct. The only missing step is calling it.
This is a 15-minute fix with material risk protection.
