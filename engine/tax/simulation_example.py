import logging
from datetime import datetime, timedelta
from engine.tax.ingestion import push_raw_event
from engine.tax.ledger import create_ledger_entry
from engine.tax.lot_manager import LotManager
from engine.tax.disposals import record_disposal
from engine.tax.reporting import generate_tax_package

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def run_simulation():
    logger.info("Starting Tax Engine Simulation...")

    # 1. Mock Binance Trades (Raw Events)
    buy1 = {
        "symbol": "BTCEUR",
        "id": 28457,
        "orderId": 100234,
        "price": "60000.00",
        "qty": "0.10",
        "quoteQty": "6000.00",
        "commission": "0.0001",
        "commissionAsset": "BNB",
        "time": int((datetime.now() - timedelta(days=400)).timestamp() * 1000),
        "isBuyer": True
    }
    
    buy2 = {
        "symbol": "BTCEUR",
        "id": 28458,
        "orderId": 100235,
        "price": "80000.00",
        "qty": "0.05",
        "quoteQty": "4000.00",
        "commission": "0.00005",
        "commissionAsset": "BNB",
        "time": int((datetime.now() - timedelta(days=100)).timestamp() * 1000),
        "isBuyer": True
    }

    sell1 = {
        "symbol": "BTCEUR",
        "id": 28459,
        "orderId": 100236,
        "price": "90000.00",
        "qty": "0.12",
        "quoteQty": "10800.00",
        "commission": "10.80",
        "commissionAsset": "EUR",
        "time": int(datetime.now().timestamp() * 1000),
        "isBuyer": False
    }

    # Push to immutable event store
    dt1 = datetime.fromtimestamp(buy1["time"] / 1000)
    dt2 = datetime.fromtimestamp(buy2["time"] / 1000)
    dt3 = datetime.fromtimestamp(sell1["time"] / 1000)

    e1_id = push_raw_event("binance", "myTrades", str(buy1["id"]), dt1, buy1)
    e2_id = push_raw_event("binance", "myTrades", str(buy2["id"]), dt2, buy2)
    e3_id = push_raw_event("binance", "myTrades", str(sell1["id"]), dt3, sell1)

    # 2. Normalize to Ledger
    # Assuming BNB fee was worth 50 EUR at the time for buy1, 55 EUR for buy2
    l1_id = create_ledger_entry(
        source_event_id=e1_id, timestamp_utc=dt1, asset="BTC", quantity=0.10, direction="BUY",
        transaction_type="TRADE", fiat_value_eur=6000.0, price_eur=60000.0,
        fee_asset="BNB", fee_quantity=0.0001, fee_eur=5.0
    )
    
    l2_id = create_ledger_entry(
        source_event_id=e2_id, timestamp_utc=dt2, asset="BTC", quantity=0.05, direction="BUY",
        transaction_type="TRADE", fiat_value_eur=4000.0, price_eur=80000.0,
        fee_asset="BNB", fee_quantity=0.00005, fee_eur=2.75
    )

    l3_id = create_ledger_entry(
        source_event_id=e3_id, timestamp_utc=dt3, asset="BTC", quantity=0.12, direction="SELL",
        transaction_type="TRADE", fiat_value_eur=10800.0, price_eur=90000.0,
        fee_asset="EUR", fee_quantity=10.80, fee_eur=10.80
    )

    # 3. Lot Management (FIFO)
    lm = LotManager(method='FIFO')
    lm.create_lot("BTC", dt1, 0.10, 6000.0, 5.0, l1_id)
    lm.create_lot("BTC", dt2, 0.05, 4000.0, 2.75, l2_id)

    # 4. Process Disposal (The SELL event)
    consumed_lots = lm.consume_lots("BTC", 0.12)
    
    # Total EUR fee for the sale was 10.80. We prorate it across the consumed lots by quantity.
    total_sell_qty = 0.12
    total_sale_value = 10800.0
    total_sell_fee = 10.80
    
    for chunk in consumed_lots:
        qty_ratio = chunk['quantity_consumed'] / total_sell_qty
        sale_val_chunk = total_sale_value * qty_ratio
        sale_fee_chunk = total_sell_fee * qty_ratio
        
        record_disposal(
            asset="BTC",
            disposal_timestamp=dt3,
            quantity_disposed=chunk['quantity_consumed'],
            sale_value_eur=sale_val_chunk,
            sale_fee_eur=sale_fee_chunk,
            acquisition_lot_id=chunk['lot_id'],
            acquisition_timestamp=chunk['acquisition_timestamp'],
            acquisition_cost_eur=chunk['cost_basis_eur'],
            method_used=lm.method
        )

    # 5. Generate Tax Report
    year = dt3.year
    manifest = generate_tax_package(year)
    logger.info(f"Simulation completed successfully. Manifest: {manifest}")

if __name__ == '__main__':
    run_simulation()
