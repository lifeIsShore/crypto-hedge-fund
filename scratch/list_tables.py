import sqlite3
conn = sqlite3.connect('engine_data.db')
rows = conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()
print([r[0] for r in rows])
