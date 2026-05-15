import pandas_datareader.data as web
import sys
from datetime import datetime, timedelta

end = datetime.today()
start = end - timedelta(days=365)

try:
    df = web.DataReader("VSTOXXCLS", "fred", start, end)
    print(f"OK: VSTOXXCLS: {len(df)} rows")
except Exception as e:
    print(f"FAIL: VSTOXXCLS: {e}")
sys.stdout.flush()
