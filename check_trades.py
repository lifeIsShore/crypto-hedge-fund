import sqlite3
import pandas as pd
pd.set_option('display.max_columns', None)
pd.set_option('display.max_colwidth', None)
conn = sqlite3.connect('sandbox_data.db')
print("--- TRADES ---")
print(pd.read_sql("SELECT date, ticker, action, quantity, notes FROM trades ORDER BY id DESC LIMIT 5", conn))
print("\n--- PIPELINE LOGS ---")
print(pd.read_sql("SELECT step_name, message, detail FROM pipeline_logs WHERE detail LIKE '%kelly%' OR detail LIKE '%earnings%' OR message LIKE '%kelly%' OR message LIKE '%earnings%' ORDER BY id DESC LIMIT 10", conn))
conn.close()
