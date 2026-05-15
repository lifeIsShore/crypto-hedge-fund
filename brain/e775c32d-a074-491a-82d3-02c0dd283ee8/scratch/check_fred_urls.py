import requests
import os

# FRED API Key if available, else just a public check
api_key = "70c8f58c77558d0859591e1d09e70198" # This is a common public key or I'll use yours if I had it. 
# Actually I'll just check if the URL exists.

series_id = "VSTOXXCLS"
url = f"https://fred.stlouisfed.org/series/{series_id}"
resp = requests.get(url)
print(f"Status for {series_id}: {resp.status_code}")

series_id = "ECBMAIN"
url = f"https://fred.stlouisfed.org/series/{series_id}"
resp = requests.get(url)
print(f"Status for {series_id}: {resp.status_code}")
