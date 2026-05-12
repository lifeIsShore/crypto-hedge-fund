import sqlite3
conn = sqlite3.connect('engine_data.db')
c = conn.cursor()
try:
    print("trades:", c.execute('SELECT count(*) FROM trades').fetchone()[0])
except Exception as e: print(e)
try:
    print("cash_history:", c.execute('SELECT count(*) FROM cash_history').fetchone()[0])
except Exception as e: print(e)
try:
    print("positions_history:", c.execute('SELECT count(*) FROM positions_history').fetchone()[0])
except Exception as e: print(e)
try:
    print("performance_history:", c.execute('SELECT count(*) FROM performance_history').fetchone()[0])
except Exception as e: print(e)
