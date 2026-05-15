import sqlite3
from pathlib import Path

ROOT = Path(__file__).parent.parent
DB_PATH = ROOT / "engine_data.db"

def check_tickers():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT ticker FROM price_targets WHERE date = (SELECT MAX(date) FROM price_targets);")
    tickers = [r[0] for r in cursor.fetchall()]
    conn.close()
    print(f"Available tickers in price_targets: {len(tickers)}")
    print(tickers[:20])
    
    # Also check if we have benchmarks
    benchmarks = ['VUSA.DE', 'EXXT.DE', 'BTC-USD', 'AAPL', 'APC.DE', 'NVD.DE']
    available_benchmarks = [b for b in benchmarks if b in tickers]
    print(f"Available benchmarks: {available_benchmarks}")

if __name__ == "__main__":
    check_tickers()
