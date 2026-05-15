import sqlite3

conn = sqlite3.connect('engine_data.db')
cursor = conn.cursor()
cursor.execute("PRAGMA table_info(regime_history)")
rows = cursor.fetchall()
for r in rows:
    print(r)
conn.close()
