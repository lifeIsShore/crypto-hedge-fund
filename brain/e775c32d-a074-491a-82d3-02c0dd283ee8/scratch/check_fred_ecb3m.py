import requests
series_id = "ECB3M"
url = f"https://fred.stlouisfed.org/series/{series_id}"
resp = requests.get(url)
print(f"Status for {series_id}: {resp.status_code}")
