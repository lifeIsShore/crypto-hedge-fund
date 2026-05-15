import requests
try:
    # Test internal API via direct DB query since Flask might not be running in this terminal
    import sqlite3
    conn = sqlite3.connect("engine_data.db")
    cursor = conn.cursor()
    cursor.execute("SELECT region, COUNT(*) FROM regime_history GROUP BY region")
    print(f"DB Row Counts: {cursor.fetchall()}")
    conn.close()
except Exception as e:
    print(f"Check failed: {e}")
