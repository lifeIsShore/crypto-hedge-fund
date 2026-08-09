# B7: Remove Duplicate `engine_data.db`
**Blocker: 7 of 7 | Files: root + `brain/e775c32d-a074-491a-82d3-02c0dd283ee8/`**

---

## What is wrong

There are two separate SQLite database files:

```
hedge-fund/
  engine_data.db                           ← PRODUCTION (used by Flask + scheduler)
  brain/
    e775c32d-a074-491a-82d3-02c0dd283ee8/
      engine_data.db                       ← STALE COPY (from a Claude agent session)
```

The root `engine_data.db` is the real one — `engine/db/db.py` resolves the
path relative to the project root, and Flask reads from there.

The `brain/` copy is from a Claude computer-use agent session that ran scratch
scripts. Any Python script run from inside the `brain/` directory with a
relative `engine_data.db` path will read/write the wrong database and appear
to work while actually doing nothing (or corrupting the stale copy).

The `brain/e775c32d.../scratch/` folder contains 15 diagnostic scripts:
`check_schema.py`, `verify_fred_eu.py`, `check_db_tickers.py`, etc. If any of
these are ever re-run, they will operate on the stale brain-copy database, not
the real one, producing misleading results.

---

## Fix

### Step 1 — Delete the stale database
```batch
del "C:\Users\ahmty\Desktop\hedge-fund\brain\e775c32d-a074-491a-82d3-02c0dd283ee8\engine_data.db"
```

### Step 2 — Archive or delete the scratch scripts
These are leftover diagnostic tools from the build phase. They have no role in
production. Either delete the `brain/` directory entirely, or move it to
`_archive/` to keep as historical context:
```batch
move "C:\Users\ahmty\Desktop\hedge-fund\brain" "C:\Users\ahmty\Desktop\hedge-fund\_archive\brain"
```

### Step 3 — Add to `.gitignore`
```
# Database files — never commit production DB
engine_data.db
*.db
```

### Step 4 — Verify only one DB path is used
Confirm `engine/db/db.py` resolves correctly:
```python
_default_db = f"sqlite:///{os.path.abspath(os.path.join(_root, 'engine_data.db'))}"
```
This is correct — it anchors to the project root regardless of CWD. Good.

---

## Why this matters

SQLite databases are single-file, single-writer. Having two copies means:
- Any script that accidentally opens the brain copy makes writes that
  disappear silently (the root DB is unaffected)
- Diagnostic queries against the brain DB give wrong results (stale schema,
  empty tables) causing false alarm debugging sessions
- In the worst case, if paths get confused during a refactor, live trades
  could write to the wrong database

Clean this up before going live. It takes 30 seconds.
