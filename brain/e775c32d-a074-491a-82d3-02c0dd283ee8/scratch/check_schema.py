import sqlite3

conn = sqlite3.connect('engine_data.db')
cursor = conn.cursor()
cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='regime_history'")
row = cursor.fetchone()
if row:
    print(row[0])
else:
    print("Table not found")
conn.close()
