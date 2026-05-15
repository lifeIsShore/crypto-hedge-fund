import pandas_datareader.data as web
from datetime import datetime, timedelta

end = datetime.today()
start = end - timedelta(days=30)

series = {
    "ecb_rate": "ECBMAIN",
    "ger_10y": "IRLTLT01DEM156N",
    "eu_hy": "BAMLHE00EHYIOAS"
}

for name, sid in series.items():
    try:
        df = web.DataReader(sid, "fred", start, end)
        print(f"✅ {name} ({sid}): {len(df)} rows")
    except Exception as e:
        print(f"❌ {name} ({sid}): {e}")
