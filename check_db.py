import sqlite3
import pandas as pd

conn = sqlite3.connect('engine_data.db')
tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
print("Tables:", tables)

for t in ['earnings_calendar', 'pead_setups', 'regime_history_new', 'regime_history']:
    try:
        df = pd.read_sql(f"SELECT * FROM {t} LIMIT 5", conn)
        print(f"\n--- {t} ---")
        print(df)
        count = conn.execute(f"SELECT count(*) FROM {t}").fetchone()[0]
        print(f"Total rows in {t}: {count}")
    except Exception as e:
        print(f"\n{t} table not found or error: {e}")
