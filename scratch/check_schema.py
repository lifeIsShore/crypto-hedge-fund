import sqlite3

def check_schema(table_name):
    conn = sqlite3.connect('engine_data.db')
    cursor = conn.cursor()
    cursor.execute(f"PRAGMA table_info({table_name})")
    columns = cursor.fetchall()
    print(f"Schema for {table_name}:")
    for col in columns:
        print(col)
    conn.close()

check_schema('trades')
check_schema('cash_history')
check_schema('positions_history')
