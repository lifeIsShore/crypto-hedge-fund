import sqlite3, json

conn = sqlite3.connect("engine_data.db")
tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()]
result = {}
for t in tables:
    rows = conn.execute(f"SELECT COUNT(*) FROM [{t}]").fetchone()[0]
    cols = [r[1] for r in conn.execute(f"PRAGMA table_info([{t}])").fetchall()]
    result[t] = {"rows": rows, "cols": cols}
conn.close()
print(json.dumps(result, indent=2))
