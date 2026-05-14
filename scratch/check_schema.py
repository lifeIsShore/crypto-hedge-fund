import sqlite3
conn = sqlite3.connect('engine_data.db')
cursor = conn.cursor()
cursor.execute("PRAGMA table_info(price_targets);")
print(cursor.fetchall())
conn.close()
