# H2: Fix Deterministic MC Seeds + H3: FX Fallback from DB
**High Priority | Files: `flask_app.py`, `engine/reconciliation/ledger_importer.py`**

---

## H2 — Deterministic Monte Carlo Seeds

### What is wrong

Every Monte Carlo simulation in `flask_app.py` uses fixed seeds:

```python
# In _mc_portfolio():
rng = np.random.default_rng(seed=0)

# In api_ticker_mc():
rng = np.random.default_rng(42)

# In api_portfolio_mc():
rng = np.random.default_rng(0)
```

`seed=0` and `seed=42` produce the same sequence every time. This means:
- The VaR and CVaR numbers on the Risk page are identical every load
- Users (and you) get a false sense that the numbers are "stable and reliable"
  when in fact they are just deterministic outputs of the same random sequence
- True tail risk (which requires seeing many independent paths) is hidden

For the per-ticker charts (`api_ticker_mc`), seed=42 is acceptable for
reproducibility. But for portfolio-level risk metrics (`_mc_portfolio`,
`api_portfolio_mc`), the simulation should reflect genuine Monte Carlo
uncertainty across runs.

### Fix

**Portfolio MC** (the numbers on the Risk page) — remove the fixed seed:
```python
# _mc_portfolio() — remove seed
rng = np.random.default_rng()           # cryptographically seeded, different each run

# api_portfolio_mc() — same change
rng = np.random.default_rng()
```

**Per-ticker histogram** (`api_ticker_mc`) — keep the seed for chart stability,
but increase n from 10,000 to 50,000 for smoother histograms:
```python
rng = np.random.default_rng(42)   # OK to keep for chart reproducibility
n = 50_000                        # smoother histogram, same speed
```

**Institutional MC** (`api_institutional_mc` → `_get_single_mc_summary`) —
remove seed for genuine variation:
```python
rng = np.random.default_rng()     # was: np.random.default_rng() — already no seed here, good
```

---

## H3 — FX Fallback Hardcoded in `ledger_importer.py`

### What is wrong

`engine/reconciliation/ledger_importer.py` has:
```python
FALLBACK_USDEUR = 0.92
FALLBACK_GBPEUR = 1.17
```

These are module-level constants, not pulled from the DB's `fx_rates` table.
When yfinance is unavailable for FX, the ledger importer uses these stale
constants to value USD and GBP positions.

Your DB has an `fx_rates` table with daily historical rates populated by
ingestion. If EURUSD moves from 0.92 to 0.88 (a 4.3% move that has happened
in recent years), your US stock valuations will be off by that amount, which
corrupts portfolio weights and therefore all optimizer output.

The same issue exists in `flask_app.py`'s `_get_latest_fx_rate()` — but that
function already correctly queries the DB first and only falls back to hardcoded
values as a last resort. The ledger importer needs the same pattern.

### Fix

In `engine/reconciliation/ledger_importer.py`, replace the module-level
constants with a DB-first function:

**Add this function** near the top of the file:
```python
def _get_fx_rate(pair: str) -> float:
    """
    Get FX rate from DB (most recent), falling back to env var, then hardcoded constant.
    pair: 'USDEUR' or 'GBPEUR'
    """
    HARDCODED = {"USDEUR": 0.92, "GBPEUR": 1.17}
    
    # 1. Try DB
    try:
        from engine.db.db import get_session
        from sqlalchemy import text
        session = get_session()
        try:
            row = session.execute(text(
                "SELECT rate FROM fx_rates WHERE pair = :p ORDER BY date DESC LIMIT 1"
            ), {"p": pair}).fetchone()
            if row and row[0]:
                return float(row[0])
        finally:
            session.close()
    except Exception:
        pass

    # 2. Try env var
    env_key = f"FALLBACK_{pair}"
    env_val = os.getenv(env_key)
    if env_val:
        try:
            return float(env_val)
        except ValueError:
            pass

    # 3. Hardcoded last resort
    logger.warning(f"Using hardcoded FX fallback for {pair}: {HARDCODED[pair]}")
    return HARDCODED.get(pair, 1.0)
```

**Then update** `_apply_fx_if_needed()` to use it:
```python
def _apply_fx_if_needed(ticker: str, price: float) -> float:
    """Converts price to EUR if ticker is non-EUR (US/UK)."""
    if any(ticker.endswith(s) for s in EUR_SUFFIXES):
        return price

    if any(ticker.endswith(s) for s in GBP_SUFFIXES):
        rate = _get_fx_rate("GBPEUR")
    else:
        rate = _get_fx_rate("USDEUR")

    return price * rate
```

Remove the `yfinance` live-fetch block inside `_apply_fx_if_needed` — it adds
latency to every ledger import and the DB already has yesterday's rate from
the ingestion step.
