import sqlite3

conn = sqlite3.connect('engine_data.db')
cursor = conn.cursor()
cursor.execute("SELECT date, regime_composite FROM regime_history WHERE region = 'EU' ORDER BY date DESC LIMIT 5")
rows = cursor.fetchall()
for r in rows:
    print(r)
conn.close()
