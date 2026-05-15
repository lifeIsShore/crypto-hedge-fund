import pandas_datareader.data as web
from datetime import datetime, timedelta

end = datetime.today()
start = end - timedelta(days=60)

try:
    df = web.DataReader("RBDEU01", "fred", start, end)
    print(f"OK: RBDEU01: {len(df)} rows")
except Exception as e:
    print(f"FAIL: RBDEU01: {e}")
