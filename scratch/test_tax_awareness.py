import sys
sys.path.insert(0, r"c:\Users\ahmty\Desktop\SW-PROJECTS\crypto-hedge-fund")
from engine.db.db import get_session
from sqlalchemy import text
from datetime import datetime, timedelta
from engine.execution.order_manager import Order
from engine.risk.pre_trade import check_tax_awareness

def test_tax_awareness():
    session = get_session()
    
    # 1. Insert a fake short-term tax lot for BTC
    # Let's say acquired 100 days ago
    acq_date = (datetime.now() - timedelta(days=100)).isoformat()
    session.execute(text("""
        INSERT INTO tax_lots (asset, acquisition_timestamp, quantity_original, quantity_remaining, acquisition_cost_eur, acquisition_fee_eur, wallet, method)
        VALUES ('BTC', :ts, 0.5, 0.5, 30000.0, 15.0, 'binance', 'FIFO')
    """), {"ts": acq_date})
    session.commit()
    print("Inserted mock short-term lot for BTC.")
    
    # 2. Insert a fake price for BTC
    session.execute(text("""
        INSERT INTO prices (date, ticker, close, adj_close, volume)
        VALUES (CURRENT_DATE, 'BTC/EUR', 70000.0, 70000.0, 1000)
    """))
    session.commit()
    print("Inserted mock price for BTC/EUR.")
    
    # 3. Create a mock order to sell 0.1 BTC (value = 7000)
    orders = [
        Order(ticker="BTC/EUR", action="SELL", value_eur=7000.0)
    ]
    
    print("Running check_tax_awareness...")
    check_tax_awareness(orders)
    
    for o in orders:
        print(f"Order: {o.action} {o.ticker} €{o.value_eur}")
        print(f"Notes: {o.notes}")
        
    # Cleanup
    session.execute(text("DELETE FROM tax_lots WHERE asset = 'BTC' AND acquisition_cost_eur = 30000.0"))
    session.execute(text("DELETE FROM prices WHERE ticker = 'BTC/EUR' AND adj_close = 70000.0"))
    session.commit()
    session.close()

if __name__ == "__main__":
    test_tax_awareness()
