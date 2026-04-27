# Portfolio Engine - Component Testing Report

## CRITICAL ISSUES FOUND

### 1. **Function Signature Mismatch in `recalculate_engine.py`** ⚠️ CRITICAL
**Location:** [recalculate_engine.py](recalculate_engine.py#L62)

**Problem:**
```python
# INCORRECT - Line 62
kpis = generate_kpi_report(log_returns, portfolio_returns, latest_prices, BENCHMARK_TICKER)
```

**Expected Signature:** (from [performance.py](src/performance.py#L71))
```python
def generate_kpi_report(portfolio_returns, benchmark_returns, risk_free_rate=0.02, trade_pnls=None):
```

**Issue:** 
- Arguments 3 & 4 are wrong. Passing `latest_prices` (price data) and `BENCHMARK_TICKER` (string)
- Function expects `risk_free_rate` (float) and `trade_pnls` (list)
- Argument 2: Passing `portfolio_returns` where function expects `benchmark_returns` (different data)
- `benchmark_returns` should be RETURNS, not prices or ticker strings

**Impact:** ❌ Engine crash when recalculate() is called

---

### 2. **Missing Benchmark Returns Calculation**
**Location:** [recalculate_engine.py](recalculate_engine.py#L1-L100)

**Problem:** 
- Code calculates `portfolio_returns` from current positions
- Never calculates `benchmark_returns` from BENCHMARK_TICKER ('EUNL.DE')
- The `calculate_information_ratio()` function needs actual benchmark returns to work

**Impact:** ❌ Information ratio won't calculate correctly

---

### 3. **Input Field Validation Issues in Dashboard** ⚠️ FUNCTIONAL
**Location:** [dashboard.html](dashboard.html#L311) - logTransaction() function

**Issue:** 
- No validation that ticker matches action type
- For "Deposit" action, should auto-set ticker to "CASH" only
- State management in form: dropdown doesn't sync when manually selected
 
---

### 4. **Missing Required Fields Check**
**Location:** [dashboard.html](dashboard.html#L311) - Form element IDs

**Issues in logTransaction():**
- If form values are empty strings, should reject with message
- No check for NaN values after parsing
- Quantity field requires more strict validation for Buy/Sell

---

### 5. **Server API Error Handling** ⚠️ MINOR
**Location:** [server.py](server.py#L60-L90)

**Issue:**
- `refresh_engine` endpoint doesn't validate if engine_state.json exists before returning success
- No validation that ledger.csv is non-empty

---

## TEST EXECUTION LOG

### Missing Data Files
✅ Verified: All required data files exist
- `data/ledger.csv` - EXISTS
- `data/engine_state.json` - EXISTS  
- `data/historical_prices.csv` - EXISTS

### Python Dependencies
Status: Will check in next step

### API Endpoints
- POST `/api/log_transaction` - Need to test
- POST `/api/refresh_engine` - Need to test (will fail due to Issue #1)
- GET `/data/engine_state.json` - Need to test
- GET `/` - Dashboard serves correctly

### Form Input Validation
Checks needed:
✓ Action dropdown works
✓ Ticker dropdown works
✓ Quantity input accepts decimals
✓ Price input accepts decimals
✓ Notes field optional
⚠️ Cross-field validation (action ↔ ticker logic)

---

## RECOMMENDED FIXES (Priority Order)

1. **[CRITICAL]** Fix `generate_kpi_report` call in recalculate_engine.py
2. **[CRITICAL]** Add benchmark returns calculation
3. **[HIGH]** Improve form validation on dashboard
4. **[MEDIUM]** Add server-side validation for engine_state.json
5. **[MEDIUM]** Add more detailed error messages
