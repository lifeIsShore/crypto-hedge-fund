import sqlite3

conn = sqlite3.connect('engine_data.db')
cursor = conn.cursor()
cursor.execute("SELECT region, COUNT(*) FROM regime_history GROUP BY region")
rows = cursor.fetchall()
for r in rows:
    print(r)
conn.close()
