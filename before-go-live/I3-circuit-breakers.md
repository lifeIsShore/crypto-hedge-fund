# I3: Hard Stop-Loss Circuit Breakers
**Improvement (post go-live) | Files: `engine/scheduler.py`, `flask_app.py`**

---

## Overview

ML models are slow to react to sudden catastrophic events: a CEO fraud scandal,
an overnight regulatory ban, or a geopolitical shock. The system currently has
no hard floor that triggers an emergency exit regardless of what the model says.

Your `improvements.md` calls this out:
> "Hard Stop-Loss Circuit Breakers: Set absolute hard floors for every position
> (e.g., -15% from entry). If a stock hits this floor, the system triggers an
> emergency exit signal that overrides any Hold or Buy recommendation."

---

## Design

A circuit breaker checks each position against its entry price. If the
position has declined more than a configured threshold from entry, it
generates a `CIRCUIT_BREAKER_SELL` risk event and adds an urgent SELL
to the order queue — regardless of the model's current recommendation.

This is implemented as a new pipeline step that runs **before** portfolio
construction, so the circuit breaker's SELL signal can influence weights.

---

## Implementation

### Step 1 — Add entry price tracking to `trades` table

We need the average cost basis per ticker. The `trades` table already has
all buy prices. Add a helper query:

```python
# In flask_app.py or a new engine/risk/circuit_breaker.py module:
def get_average_entry_prices() -> dict:
    """Returns {ticker: avg_entry_price_eur} for all current long positions."""
    rows = _q("""
        SELECT ticker,
               SUM(quantity * price_eur) / SUM(quantity) AS avg_price
        FROM trades
        WHERE action = 'BUY' AND quantity > 0 AND price_eur > 0
        GROUP BY ticker
    """)
    return {r["ticker"]: float(r["avg_price"]) for r in rows if r["avg_price"]}
```

### Step 2 — Create `engine/risk/circuit_breaker.py`

```python
"""
circuit_breaker.py — Hard stop-loss enforcement.
Runs before portfolio construction. Generates SELL signals for positions
that have declined beyond the configured threshold from average entry price.
"""
import logging
from engine.db.db import get_session
from sqlalchemy import text

logger = logging.getLogger(__name__)

# Hard stop thresholds — configurable per asset class
STOP_LOSS_INDIVIDUAL = -0.15   # -15% from average entry: individual stock
STOP_LOSS_ETF        = -0.12   # -12% for ETFs (lower vol, tighter stop)


def run_circuit_breaker_check(positions: dict, current_prices: dict, entry_prices: dict) -> list:
    """
    positions:      {ticker: quantity}
    current_prices: {ticker: current_price_eur}
    entry_prices:   {ticker: avg_entry_price_eur}

    Returns list of tickers that have triggered a circuit breaker.
    These should be added as forced SELL signals in portfolio construction.
    """
    triggered = []

    for ticker, qty in positions.items():
        if qty <= 0:
            continue

        entry  = entry_prices.get(ticker)
        current = current_prices.get(ticker)

        if not entry or not current or entry <= 0:
            continue

        drawdown = (current - entry) / entry   # negative if down

        threshold = STOP_LOSS_ETF if ticker.endswith(('.DE', '.AS')) and 'ETF' in ticker else STOP_LOSS_INDIVIDUAL

        if drawdown <= threshold:
            logger.critical(
                f"🚨 CIRCUIT BREAKER: {ticker} down {drawdown:.1%} from entry "
                f"(entry=€{entry:.2f}, current=€{current:.2f}) — FORCED SELL"
            )
            triggered.append(ticker)

            # Write to risk_events
            session = get_session()
            try:
                session.execute(text("""
                    INSERT INTO risk_events (date, event_type, ticker, detail)
                    VALUES (CURRENT_DATE, 'circuit_breaker', :ticker, :detail)
                """), {
                    "ticker": ticker,
                    "detail": f"Drawdown {drawdown:.1%} exceeded {threshold:.0%} threshold. Entry=€{entry:.2f}, Current=€{current:.2f}"
                })
                session.commit()
            finally:
                session.close()

    return triggered
```

### Step 3 — Wire into `step_portfolio_construction()` in `scheduler.py`

After loading current weights, before running BL:

```python
from engine.risk.circuit_breaker import run_circuit_breaker_check

# Get entry prices and current prices
entry_prices = get_average_entry_prices()
current_prices = {
    r["ticker"]: float(r["price"] or 0)
    for r in _q("SELECT ticker, adj_close as price FROM prices p "
                "INNER JOIN (SELECT ticker, MAX(date) md FROM prices GROUP BY ticker) l "
                "ON p.ticker=l.ticker AND p.date=l.md")
}
positions_qty = {t: float(current_weights.get(t, 0)) * portfolio_value / current_prices.get(t, 1)
                 for t in available_tickers if current_weights.get(t, 0) > 0}

triggered_tickers = run_circuit_breaker_check(positions_qty, current_prices, entry_prices)

# Force triggered tickers to 0% weight target — overrides BL suggestion
if triggered_tickers:
    for ticker in triggered_tickers:
        if ticker in suggested_weights.index:
            suggested_weights[ticker] = 0.0   # force full exit
    logger.critical(f"Circuit breakers triggered: {triggered_tickers} — weights forced to 0")
    send_alert(f"🚨 CIRCUIT BREAKER activated for: {triggered_tickers}")
```

### Step 4 — Display on dashboard

On `overview.html` and `risk.html`, query recent circuit breaker events:
```python
circuit_events = _q("""
    SELECT ticker, detail, logged_at FROM risk_events
    WHERE event_type = 'circuit_breaker'
    AND date >= date('now', '-7 days')
    ORDER BY logged_at DESC
""")
```
Show a prominent red banner if any circuit breakers fired in the last 7 days.

---

## Configuration

Document threshold changes in `portfolio/docs/03-TUNING-LOG.md`:

| Threshold | Value | Rationale |
|-----------|-------|-----------|
| Individual stock stop | -15% | Covers 4σ daily move; below this is likely structural damage |
| ETF stop | -12% | Lower vol instrument; -12% represents significant regime shift |

These are hard floors — they override everything including conviction signals.
