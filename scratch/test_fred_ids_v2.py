
import pandas_datareader.data as web
from datetime import datetime, timedelta

def test_fred(ids):
    end = datetime.today()
    start = end - timedelta(days=365)
    for sid in ids:
        try:
            print(f"Fetching {sid}...")
            df = web.DataReader(sid, "fred", start, end)
            if df.empty:
                print(f"  {sid}: EMPTY")
            else:
                print(f"  {sid}: {len(df)} rows, Latest: {df.iloc[-1].values[0]} on {df.index[-1]}")
        except Exception as e:
            print(f"  {sid}: ERROR: {e}")

ids_to_test = [
    "ECBDF",       # ECB Deposit Facility
    "EUROSHORT",   # Euro Short-Term Rate
    "IRLTLT01DEM156N", # 10Y Germany
    "IR3TIB01DEM156N", # 3M Germany
    "DEURIBOR3M",      # 3M Euribor
]

test_fred(ids_to_test)
