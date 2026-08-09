# SOS Button — Emergency Halt / Liquidate Protocol

> **STATUS: This file was empty before this pass — no spec ever existed.**
> `RISK-POLICY.md` §4 already references an "Emergency Halt (SOS Protocol)"
> as if it's built ("the pipeline can be manually halted, blocking all API
> execution routes"). It is **not** built. This is a spec, not implemented code.
> Since it touches real money on a single click, **read this fully and decide
> the exact behavior yourself before building it** — I've laid out the
> options below rather than picking one for you, because this is a decision
> that should be yours, not a default I choose.

---

## What problem this solves

Every other safety mechanism in the system (circuit breakers, tolerance
bands, pre-trade checks) is *automatic and gradual*. There is currently no
single, fast, manual override for "something is wrong that the model can't
see — stop everything right now." Examples of when you'd want this:
- A geopolitical event breaks overnight and you don't trust any signal until
  you've had time to think
- You notice a bug in a rebalance suggestion before approving it and want to
  freeze the whole pipeline while you investigate
- You're going to be unreachable for a while (travel, etc.) and want the
  system to stop generating new suggestions in your absence

## Decision 1 — What does "SOS" actually DO?

Three different things get conflated under "panic button" — pick which one(s)
you actually want, because they have very different risk profiles:

**Option A — Halt (safest, recommended default)**
Stops the pipeline from generating *new* order suggestions or auto-pushing to
the signal queue. Does **not** touch existing positions. You're frozen, not
liquidated. Reversible with one click.

**Option B — Halt + Flatten to Cash (aggressive)**
Same as A, plus immediately generates SELL orders for every open position at
market. This is a real, consequential action — it realizes all gains/losses
and incurs the full tax hit (see `J2-tax-aware-selling.md`) on every winning
position simultaneously, with no optimizer consideration of *which* sells
make sense. Only appropriate for genuine "the world is ending" scenarios, not
for "I'm unsure today."

**Option C — Halt + Widen All Circuit Breakers (defensive, not destructive)**
Same as A, plus temporarily tightens the I3 circuit breaker thresholds
(e.g. -15%/-12% → -8%/-6%) so any position that moves against you gets
auto-exited faster, without force-selling everything immediately. A middle
ground between A and B.

**Recommendation:** Build Option A first. It's reversible, low-risk, and
covers the most common real use case (pause and think). Add B as a distinct,
separately-confirmed action later if you find you actually need it — don't
build the most dangerous option first "just in case."

## Decision 2 — Where does the state live?

A single row is enough — this isn't complex state:

```sql
CREATE TABLE IF NOT EXISTS system_halt (
    id            INTEGER PRIMARY KEY CHECK (id = 1),  -- singleton row
    is_halted     INTEGER NOT NULL DEFAULT 0,
    halted_at     TEXT,
    halted_reason TEXT,
    halted_by     TEXT DEFAULT 'manual'
);
INSERT OR IGNORE INTO system_halt (id, is_halted) VALUES (1, 0);
```

## Decision 3 — What checks this flag?

If you go with **Option A (Halt)**:

1. `engine/scheduler.py`, top of `run_pipeline()`:
```python
def is_system_halted() -> bool:
    session = get_session()
    try:
        row = session.execute(text("SELECT is_halted FROM system_halt WHERE id = 1")).fetchone()
        return bool(row[0]) if row else False
    finally:
        session.close()

def run_pipeline():
    if is_system_halted():
        logger.warning("[SOS] System is HALTED — skipping pipeline run entirely")
        send_alert("⚠️ Pipeline run skipped — system is in SOS halt state")
        return
    # ... existing pipeline steps
```

2. `step_push_signals_to_queue()` (already exists — added 2026-08-04 for the
   watchlist auto-push) should also check the flag independently, in case
   someone calls it outside `run_pipeline()`.

3. `flask_app.py` — the manual "Approve" button on the rebalance/signal-queue
   pages should also check the flag and block approval with a clear message,
   not just silently stop the background pipeline. A halted system that still
   lets you click "Approve" on a stale suggestion defeats the purpose.

## Decision 4 — The UI

Add a persistent, unmissable button to `base.html`'s header (visible on every
page, not buried in `/health`) — red when halted, otherwise a neutral outline
button so it doesn't look alarming during normal operation:

```html
<button id="sos-btn" onclick="toggleHalt()">🛑 SOS</button>
```

```javascript
async function toggleHalt() {
    const isHalted = document.getElementById('sos-btn').classList.contains('halted');
    const action = isHalted ? 'resume' : 'halt';
    const reason = isHalted ? null : prompt("Reason for halt (optional, logged):");
    if (!isHalted && reason === null) return;  // user cancelled the prompt — don't halt silently

    const confirmed = confirm(
        isHalted
            ? "Resume normal pipeline operation?"
            : "Halt the pipeline? No new rebalance suggestions will be generated until you resume. Existing positions are NOT affected."
    );
    if (!confirmed) return;

    await fetch('/api/system_halt', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({halt: !isHalted, reason})
    });
    location.reload();
}
```

`/api/system_halt` Flask route — gate this behind the existing
`require_auth` decorator from B2, same as `/api/log_trade`:

```python
@app.route('/api/system_halt', methods=['POST'])
@require_auth
def api_system_halt():
    data = request.get_json()
    halt = bool(data.get('halt'))
    reason = data.get('reason', '')
    session = get_session()
    try:
        session.execute(text("""
            UPDATE system_halt SET is_halted = :halt,
                halted_at = CASE WHEN :halt THEN datetime('now') ELSE NULL END,
                halted_reason = :reason
            WHERE id = 1
        """), {"halt": int(halt), "reason": reason})
        session.commit()
        log_pipeline_event('WARNING' if halt else 'INFO',
                            f"System {'HALTED' if halt else 'RESUMED'}: {reason}")
        return jsonify({"status": "ok", "halted": halt})
    finally:
        session.close()
```

## What NOT to do

- Don't wire this into Task Scheduler / the `.bat` files at the OS level —
  keep it purely a DB flag the Python code checks. An OS-level kill is harder
  to reason about, harder to reverse cleanly mid-run, and doesn't give you a
  reason/audit trail the way a DB row does.
- Don't make Option A silently also cancel already-queued manual orders
  sitting in `signal_queue` that you haven't reviewed yet — halting stops
  *new* generation, it shouldn't retroactively delete a queue you were
  already about to review. Let those sit; you decide what to do with them.
- Don't build B and C on day one. Get A live, use it for a month, then decide
  if you actually need the more aggressive options based on real experience
  rather than a hypothetical.
