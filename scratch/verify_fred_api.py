import requests
import pandas as pd
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv

load_dotenv()
FRED_KEY = os.getenv("FRED_API_KEY")

test_ids = {
    "US VIX": "VIXCLS",
    "US 10Y-2Y": "T10Y2Y",
    "EU German 10Y (API ID)": "IRLTLT01DEM156N",
    "EU German 3M": "IR3TIB01DEM156N"
}

print(f"Testing FRED API Key: {FRED_KEY[:5]}...{FRED_KEY[-5:]}")

for name, series_id in test_ids.items():
    try:
        url = f"https://api.stlouisfed.org/fred/series/observations?series_id={series_id}&api_key={FRED_KEY}&file_type=json"
        res = requests.get(url, timeout=10).json()
        obs = res.get("observations", [])
        if obs:
            print(f"[SUCCESS] {name} ({series_id}): {len(obs)} rows found. Latest value: {obs[-1]['value']}")
        else:
            print(f"[FAILED] {name} ({series_id}): No observations returned. Response: {res}")
    except Exception as e:
        print(f"[ERROR] {name} ({series_id}): {e}")
