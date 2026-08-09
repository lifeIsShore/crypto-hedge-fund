# I4: Paper Trading Sandbox Gate
**Improvement (post go-live) | New: `sandbox/` directory**

---

## Overview

Your `improvements.md` recommends:
> "Never test new code in the production environment. New algorithms and model
> versions must run in this isolated sandbox for 21 trading days using live data
> but 'Paper' execution."

This is how professional quant funds operate. No code change should touch
live capital without first proving itself on paper. The architecture to do
this is straightforward given your existing setup.

---

## Design

The sandbox is a second instance of the full pipeline running against a
**separate SQLite database** (`sandbox_data.db`). It:
- Fetches real live market data (same as production)
- Runs the full BL optimizer and ML pipeline
- Generates orders — but never executes them; logs them as "paper trades"
- Tracks a synthetic P&L against a notional €10,000 starting balance
- Runs via a separate `.bat` file or a `SANDBOX=1` environment flag

After 21 trading days (~4 calendar weeks), you review the sandbox Sharpe ratio,
max drawdown, and signal quality before promoting the new version to production.

---

## Implementation

### Step 1 — Environment flag

Add to `.env`:
```
SANDBOX_MODE=0
SANDBOX_NOTIONAL_EUR=10000
```

In `engine/db/db.py`, respect the flag:
```python
if os.getenv('SANDBOX_MODE') == '1':
    _sandbox_path = os.path.abspath(os.path.join(_root, 'sandbox_data.db'))
    DATABASE_URL = f"sqlite:///{_sandbox_path}"
    logger.info("🧪 SANDBOX MODE — using sandbox_data.db")
```

### Step 2 — Paper trade execution

Create `engine/execution/paper_trader.py`:
```python
"""
paper_trader.py — Records order queue as executed without touching real cash.
Used in SANDBOX_MODE to simulate live execution at closing prices.
"""
import logging
from engine.db.db import get_session
from sqlalchemy import text

logger = logging.getLogger(__name__)


def execute_paper_orders(orders: list, current_prices: dict, notional_eur: float):
    """
    'Execute' all orders at current prices in the sandbox DB.
    Writes to trades table with source='paper'.
    """
    session = get_session()
    try:
        for order in orders:
            price = current_prices.get(order.ticker)
            if not price:
                logger.warning(f"[paper] No price for {order.ticker} — skipping")
                continue

            qty = order.value_eur / price
            session.execute(text("""
                INSERT INTO trades
                    (date, ticker, action, quantity, price_eur, value_eur, source, notes)
                VALUES (CURRENT_DATE, :ticker, :action, :qty, :price, :value, 'paper', 'sandbox')
            """), {
                "ticker": order.ticker,
                "action": order.action,
                "qty":    qty,
                "price":  price,
                "value":  order.value_eur,
            })
            logger.info(f"[paper] {order.action} {order.ticker} €{order.value_eur:.0f} @ €{price:.2f}")
        session.commit()
    finally:
        session.close()
```

### Step 3 — Sandbox scheduler wrapper

Create `RUN_SANDBOX.bat`:
```batch
@echo off
set SANDBOX_MODE=1
set PYTHONIOENCODING=utf-8

echo ============================================================
echo   HEDGE FUND SANDBOX — Paper Trading Mode
echo   Database: sandbox_data.db
echo   Real money: NONE
echo ============================================================

python -m engine.scheduler --pipeline-only
echo.
echo Sandbox run complete. Check sandbox_data.db for paper trade log.
pause
```

### Step 4 — Promotion checklist

After 21 trading days, evaluate the sandbox using this checklist before
promoting to production:

```
SANDBOX PROMOTION CHECKLIST
============================
[ ] Sharpe ratio (annualized) >= 0.5
[ ] Max drawdown <= 20%
[ ] No pipeline step failures in last 7 days
[ ] All pre-trade checks passing (0 violations)
[ ] Signal IC (Information Coefficient) > 0.03 for at least 3 models
[ ] Fee drag < 2% of notional (not over-trading)
[ ] Circuit breaker fired <= 2 times (if more: review stops)
[ ] Benchmark comparison: outperforming EUNL.DE on risk-adjusted basis
[ ] Reviewed override log — no systematic model errors

RESULT: [ ] PROMOTE   [ ] EXTEND SANDBOX   [ ] REJECT
Reviewed by: ________________  Date: ________________
```

---

## What this protects against

Without a sandbox, any change to the optimizer, a new alpha model, or a
feature pipeline modification goes directly into live capital. A single bug
in BL weights (like the wrong sign on a macro feature) could silently
suggest selling your best positions and buying your worst — and you would
not know until you see the P&L.

The sandbox adds 4 weeks of latency to new features but eliminates the
possibility of a code change causing a capital loss event.
