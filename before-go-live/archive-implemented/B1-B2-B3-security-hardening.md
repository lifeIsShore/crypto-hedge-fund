# B1 + B2 + B3: Security Hardening
**Blockers: 3 of 7 | Priority: Fix first, before anything else**

---

## B1 — API Keys in `.env` Committed to Repo

### What is wrong
Your `.env` file contains live API keys for FRED, Twelvedata, AlphaVantage,
and Finnhub in plaintext. This file is in the project root and is likely
(or at risk of being) committed to version control.

Current `.env`:
```
FRED_API_KEY=77a2715b6594f71d7f396e16ed7b8db8
TWELVEDATA_API_KEY=4ac48ac6588d473ca2151c4eadb8022b
ALPHAVANTAGE_API_KEY=75JQ8RG89HGRI5Z4
FINNHUB_API_KEY=d82nd81r01qmgc0gq7c0d82nd81r01qmgc0gq7cg
```

### Fix

1. Confirm `.env` is in `.gitignore` (it is — good). But rotate all keys NOW
   because they may already be in git history.
2. Add `.env` to `.gitignore` if not already there (it is — confirmed).
3. Create a `.env.example` with blank values for documentation:

```bash
# .env.example — copy to .env and fill in values, never commit .env
POLYGON_API_KEY=
FRED_API_KEY=
TWELVEDATA_API_KEY=
ALPHAVANTAGE_API_KEY=
FINNHUB_API_KEY=
FALLBACK_USDEUR=0.92
FALLBACK_GBPEUR=1.17
SLACK_WEBHOOK_URL=
SMTP_HOST=
SMTP_PORT=587
SMTP_USER=
SMTP_PASSWORD=
DIGEST_EMAIL_TO=
```

4. Run `git log --all --full-history -- .env` to check if keys were ever committed.
   If yes, run `git filter-branch` or BFG Repo Cleaner to purge history.
5. Rotate every key immediately via each provider's dashboard.

---

## B2 — No Authentication on Flask

### What is wrong
`/api/log_trade` is a POST endpoint that writes directly to your trade ledger
and updates cash balance. It has zero authentication. Any machine on your local
network (or if you ever expose this to the internet) can POST fake trades that
drain your cash account or inflate positions.

Example attack — one line from any computer on your WiFi:
```bash
curl -X POST http://YOUR_IP:5000/api/log_trade \
  -H "Content-Type: application/json" \
  -d '{"action":"Sell","ticker":"NVDA","quantity":100,"price":1,"date":"2025-01-01"}'
```

### Fix

Add a simple token-based auth middleware. This is a single-user system so a
shared secret is sufficient.

**Step 1** — Add to `.env`:
```
DASHBOARD_SECRET=your-long-random-secret-here
```

**Step 2** — Add this decorator to `flask_app.py`, before the routes:
```python
import secrets
from functools import wraps
from flask import request, abort

_SECRET = os.getenv("DASHBOARD_SECRET", "")

def require_auth(f):
    """Simple token auth for write endpoints. Add to any mutating route."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not _SECRET:
            return f(*args, **kwargs)   # dev mode: no secret set = open
        token = (
            request.headers.get("X-Dashboard-Token") or
            request.args.get("token") or
            (request.get_json(silent=True) or {}).get("token")
        )
        if not secrets.compare_digest(token or "", _SECRET):
            abort(403)
        return f(*args, **kwargs)
    return decorated
```

**Step 3** — Apply to every write endpoint:
```python
@app.route("/api/log_trade", methods=["POST"])
@require_auth
def api_log_trade():
    ...

@app.route("/api/override", methods=["POST"])
@require_auth
def api_override():
    ...

@app.route("/api/label", methods=["POST"])
@require_auth
def api_label():
    ...

@app.route("/api/sync_ledger", methods=["POST"])
@require_auth
def api_sync_ledger():
    ...
```

**Step 4** — Update the frontend JavaScript in `trades.html` to include
the token in the request header when logging trades.

---

## B3 — `debug=True` in Production

### What is wrong
The last line of `flask_app.py`:
```python
app.run(host="0.0.0.0", port=5000, debug=True)
```

`debug=True` activates the Werkzeug interactive debugger. If any page throws
an unhandled exception, a browser on your network sees a Python REPL with
full filesystem access. This is a complete system compromise.

### Fix

**Option A (recommended for a single-user local setup):**
```python
if __name__ == "__main__":
    start_scheduler()
    debug_mode = os.getenv("FLASK_DEBUG", "0") == "1"
    log.info(f"Control Tower starting — http://localhost:5000 (debug={debug_mode})")
    app.run(host="0.0.0.0", port=5000, debug=debug_mode)
```

Then in your `.bat` files, never set `FLASK_DEBUG=1`.
Only set it manually when you need to debug:
```batch
set FLASK_DEBUG=1
python flask_app.py
```

**Option B (production-grade):**
Run Flask behind Waitress (a production WSGI server):
```bash
pip install waitress
```
```python
# In flask_app.py __main__ block:
from waitress import serve
start_scheduler()
log.info("Control Tower starting — http://localhost:5000")
serve(app, host="0.0.0.0", port=5000)
```
Waitress has no debug mode concept — it is always production-safe.
This is the recommended approach once you go fully live.
