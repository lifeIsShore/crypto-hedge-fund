import pandas_datareader.data as web
from datetime import datetime, timedelta

end = datetime.today()
start = end - timedelta(days=365)

series = {
    "ecb_rate": "ECBMAIN",
    "ger_10y": "IRLTLT01DEM156N",
    "eu_hy": "BAMLHE00EHYIOAS"
}

for name, sid in series.items():
    try:
        df = web.DataReader(sid, "fred", start, end)
        print(f"OK: {name} ({sid}): {len(df)} rows, latest date: {df.index[-1] if not df.empty else 'N/A'}")
    except Exception as e:
        print(f"FAIL: {name} ({sid}): {e}")
