# H4 + H5: Two Silent Code Bugs
**High Priority: Fix within first week | Files: `flask_app.py`, `engine/scheduler.py`**

---

## H4 — `_persist_single_price()` calls undefined `_q_execute`

### What is wrong

In `flask_app.py`, the function `_persist_single_price()` exists to save a
live yfinance fallback price to the DB. It is called when a position's price
is missing from the database (e.g. new holding, weekend gap):

```python
def _persist_single_price(ticker, price, currency):
    """Save a single price point to DB so ML and future loads can use it."""
    try:
        from sqlalchemy import text
        _q_execute("""              # ← THIS FUNCTION DOES NOT EXIST
            INSERT INTO prices ...
        """, {"t": ticker, "p": price, "c": currency})
```

`_q_execute` is not defined anywhere in `flask_app.py`. The file has `_exec()`
and `_q()` as helpers, but `_q_execute` is a ghost name.

**Consequence:** Every time a position has a missing price and yfinance
successfully fetches a live price, the persist silently throws a `NameError`
(caught by the outer `except Exception`), the live price is NOT saved to the DB,
and the next page load re-fetches from yfinance again. The fallback works for
display, but the DB is never updated.

### Fix

Replace `_q_execute` with `_exec` (the existing write helper):

```python
def _persist_single_price(ticker, price, currency):
    """Save a single price point to DB so ML and future loads can use it."""
    try:
        _exec("""
            INSERT INTO prices (date, ticker, open, high, low, close, volume, adj_close, currency, source)
            VALUES (CURRENT_DATE, :t, :p, :p, :p, :p, 0, :p, :c, 'live_fallback')
            ON CONFLICT (date, ticker) DO UPDATE SET
                adj_close = EXCLUDED.adj_close,
                source    = 'live_fallback'
        """, {"t": ticker, "p": price, "c": currency})
        log.info(f"Persisted live price for {ticker} to DB.")
    except Exception as e:
        log.warning(f"Failed to persist live price for {ticker}: {e}")
```

---

## H5 — Duplicate `step_lstm_train()` in `scheduler.py`

### What is wrong

`engine/scheduler.py` defines `step_lstm_train()` **twice**:

**First definition** (around line 215):
```python
def step_lstm_train():
    from engine.alpha.ml_alpha import train_all_lstms
    train_all_lstms()
```

**Second definition** (around line 310, inside the weekend block):
```python
def step_lstm_train():
    """Saturday — walk-forward train LSTM for all tickers and save models."""
    from engine.alpha.lstm_model import LSTMAlpha
    try:
        model = LSTMAlpha()
        summary = model.train_all(tickers=TICKERS, date=TODAY)
        passed = sum(1 for v in summary.values() if v.get('auc', 0) >= 0.53)
        logger.info(f"[lstm_train] {passed}/{len(summary)} tickers above AUC gate")
    except Exception as e:
        logger.error(f"[lstm_train] Training failed: {e}")
```

Python silently overwrites the first definition with the second. The first
implementation (which calls `train_all_lstms()`) is completely unreachable.

The second implementation (using `LSTMAlpha().train_all()`) also has the proper
AUC gate check and is more complete. The first is orphaned dead code.

### Fix

Delete the first (weaker) definition entirely. Keep only the second:

```python
def step_lstm_train():
    """Saturday — walk-forward train LSTM for all tickers and save models."""
    from engine.alpha.lstm_model import LSTMAlpha
    try:
        model = LSTMAlpha()
        summary = model.train_all(tickers=TICKERS, date=TODAY)
        passed = sum(1 for v in summary.values() if v.get('auc', 0) >= 0.53)
        logger.info(f"[lstm_train] {passed}/{len(summary)} tickers above AUC gate")
    except Exception as e:
        logger.error(f"[lstm_train] Training failed: {e}")
```

Also verify that `engine/alpha/ml_alpha.py` has `train_all_lstms()` as an alias
or remove that reference if it's dead. The `LSTMAlpha` path is the correct one.
