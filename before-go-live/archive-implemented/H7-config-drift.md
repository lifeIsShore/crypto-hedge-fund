# H7: Config Drift — Ticker Mapping Inconsistencies
**High Priority | File: `portfolio/src/config.py`**

---

## What is wrong

`config.py` is the single source of truth for the asset universe, but there are
several inconsistencies that cause silent failures in the pipeline:

### Issue 1 — Ticker mismatch between `TICKER_MAPPING` and `ASSET_UNIVERSE`

`TICKER_MAPPING` maps primary Xetra tickers to US fallbacks. But several tickers
in `ASSET_UNIVERSE` use the US ticker directly, not the `.DE` primary:

```python
# In TICKER_MAPPING:
'KLAC': 'KLA.DE',   # Wait — this is backwards from the rest
'FIG':  '1S2.DE',   # FIG is the US form, 1S2.DE is the Xetra form

# In ASSET_UNIVERSE:
'KLAC', 'FIG',      # Using US tickers directly
```

The convention throughout the codebase is `.DE` primary → US fallback.
Having `'KLAC'` (US ticker) in `ASSET_UNIVERSE` means the ingestion engine
fetches the US price, stores it as USD, and the FX conversion is applied
correctly — but it creates a naming inconsistency in the `prices` table where
most tech stocks are stored as `NVD.DE`, `APC.DE`, etc., but KLAC is stored
as `KLAC`. The pairs scanner and TICKER_SECTORS lookups will silently miss it.

### Issue 2 — Missing `TICKER_SECTORS` entries

These tickers exist in `ASSET_UNIVERSE` but are absent from `TICKER_SECTORS`:
- `M9Z.DE` (Mastercard) — in `TICKER_MAPPING` as Mastercard but `TICKER_SECTORS`
  has `'M9N.DE'` for Morgan Stanley instead of `'M9Z.DE'`
- `AXP.DE` (American Express) — in `TICKER_SECTORS` as `'AEC.DE'`, not `'AXP.DE'`
- `BLQA.DE` (BlackRock) — in `TICKER_SECTORS` as `'BLA.DE'`, not `'BLQA.DE'`
- `1IN.DE` (Intel) — in `TICKER_SECTORS` as `'INZ.DE'`
- `QCI.DE` (Qualcomm) — correct in both

These mismatches mean the sector exposure check in `pre_trade.py` and the
pairs scanner in `api_pairs_scan()` silently assign "other" sector to these
tickers, bypassing the 30% sector concentration limit.

### Issue 3 — Benchmark ticker in ETF list but not `ASSET_UNIVERSE`

`BENCHMARK_TICKER = 'EUNL.DE'` is used for beta computation in
`/api/stress_tests`. `EUNL.DE` is in `ETF_TICKERS` which is appended to
`ASSET_UNIVERSE`. This is correct. But if someone removes it from `ETF_TICKERS`,
beta computation silently falls back to `beta=1.0` for all tickers. Add a
startup assertion to catch this.

---

## Fix

### Fix 1 — Standardize to `.DE` tickers in `ASSET_UNIVERSE`

Replace in `ASSET_UNIVERSE`:
```python
# Before:
'KLAC', 'FIG',

# After:
'KLA.DE', '1S2.DE',
```

Update `TICKER_MAPPING` to follow the standard direction:
```python
'KLA.DE':  'KLAC',   # was: 'KLAC': 'KLA.DE' (backwards)
'1S2.DE':  'FIG',    # was: 'FIG': '1S2.DE' (backwards)
```

### Fix 2 — Align `TICKER_SECTORS` keys with `ASSET_UNIVERSE`

Add or correct these entries:
```python
TICKER_SECTORS = {
    ...
    'M9Z.DE': 'Financials',    # Mastercard (was M9Z.DE missing, had M9N.DE=Morgan Stanley)
    'AXP.DE': 'Financials',    # American Express (was AEC.DE)
    'BLQA.DE': 'Financials',   # BlackRock (was BLA.DE)
    '1IN.DE': 'Semiconductors', # Intel (was INZ.DE)
    ...
}
```

### Fix 3 — Add startup assertion for benchmark ticker

Add to the bottom of `config.py`:
```python
# Sanity check: benchmark must be in the universe for beta computation
assert BENCHMARK_TICKER in ASSET_UNIVERSE, (
    f"BENCHMARK_TICKER '{BENCHMARK_TICKER}' is not in ASSET_UNIVERSE. "
    f"Beta computation will fail. Add it to ETF_TICKERS."
)
```

### Fix 4 — Quick validation script

After making changes, run this to verify consistency:
```python
# Run from project root: python -c "exec(open('validate_config.py').read())"
from portfolio.src.config import ASSET_UNIVERSE, TICKER_SECTORS, TICKER_MAPPING

missing_sectors = [t for t in ASSET_UNIVERSE if t not in TICKER_SECTORS]
if missing_sectors:
    print(f"WARNING: {len(missing_sectors)} tickers missing from TICKER_SECTORS:")
    for t in missing_sectors:
        print(f"  {t}")
else:
    print("OK: All ASSET_UNIVERSE tickers have sector assignments")
```

---

## Why this matters operationally

The sector concentration check (`MAX_SECTOR = 0.30`) is a hard risk limit.
If a sector's tickers are misnamed in `TICKER_SECTORS`, a concentrated tech
bet would pass pre-trade checks even if the real sector exposure is 40%+.
This is a compliance risk, not just a data quality issue.
