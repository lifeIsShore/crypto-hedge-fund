# B4: Remove `fee_debug.log` from `/api/performance`
**Blocker: 4 of 7 | File: `flask_app.py` → `api_performance()`**

---

## What is wrong

Inside `api_performance()` in `flask_app.py`, there is this code that runs on
EVERY request to the performance endpoint:

```python
with open("fee_debug.log", "w") as f:
    f.write("\n".join(debug_ledger))
    f.write(f"\nTOTAL: {total_fees}")

log.info(f"DEBUG: Calculated total_fees={total_fees}. Details in fee_debug.log")
```

This writes a file to the project root on every page load / chart refresh.
Problems:
1. `fee_debug.log` is sitting at the project root right now — it contains
   internal financial data that could be read by anyone with filesystem access.
2. On a busy day with auto-refreshing charts, this writes thousands of times,
   causing unnecessary disk I/O.
3. It permanently marks the code as "debug" — bad practice near real money.
4. The log message says `DEBUG:` but uses `logging.INFO` level — confusing.

---

## Fix

Remove the file write entirely. The fee calculation logic is correct; it just
doesn't need a debug log. Replace that entire debug block with a single
structured log that only fires in DEBUG log level:

**Before** (remove this block):
```python
with open("fee_debug.log", "w") as f:
    f.write("\n".join(debug_ledger))
    f.write(f"\nTOTAL: {total_fees}")

log.info(f"DEBUG: Calculated total_fees={total_fees}. Details in fee_debug.log")
```

**After** (replace with):
```python
log.debug(f"Fee calculation: total_fees={total_fees:.2f} from {len(debug_ledger)} rows")
```

Then delete the existing `fee_debug.log` file from the project root.

Also remove the `debug_ledger` list that is being built solely to feed this
file write — it allocates memory on every performance request:

**Before:**
```python
debug_ledger = []
for t in trades_rows:
    ...
    if row_fee != 0:
        total_fees += row_fee
        debug_ledger.append(f"{t['date']} | {act} | val={v_eur} | fee={f_eur} | ADDED={row_fee}")
```

**After:**
```python
for t in trades_rows:
    act = (t.get("action") or "").upper()
    v_eur = float(t.get("total_eur") or 0)
    f_eur = float(t.get("fee_eur") or 0)
    row_fee = v_eur if act == "FEE" else f_eur
    if row_fee != 0:
        total_fees += row_fee
```

Clean, no file I/O, no memory leak, correct fee logic preserved.

---

## After the fix

Delete the existing debug file:
```bash
del "C:\Users\ahmty\Desktop\hedge-fund\fee_debug.log"
```

Add `*.log` to `.gitignore` if not already present to prevent any future
log files from being accidentally committed.
