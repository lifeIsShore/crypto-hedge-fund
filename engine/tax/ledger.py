import logging
from datetime import datetime
from engine.db.db import get_session
from sqlalchemy import text

logger = logging.getLogger(__name__)

def create_ledger_entry(
    source_event_id: int,
    timestamp_utc: datetime,
    asset: str,
    quantity: float,
    direction: str,
    transaction_type: str,
    fiat_value_eur: float,
    price_eur: float,
    fee_asset: str = None,
    fee_quantity: float = 0.0,
    fee_eur: float = 0.0,
    exchange: str = 'binance',
    symbol: str = None,
    order_id: str = None,
    trade_id: str = None,
    is_internal_transfer: bool = False,
    wallet_from: str = None,
    wallet_to: str = None,
    tx_hash: str = None
) -> int:
    """
    Creates a normalized financial ledger entry from a raw event.
    """
    session = get_session()
    try:
        result = session.execute(
            text("""
                INSERT INTO tax_ledger_entries 
                (timestamp_utc, asset, quantity, direction, transaction_type, 
                 fiat_value_eur, price_eur, fee_asset, fee_quantity, fee_eur, 
                 exchange, symbol, order_id, trade_id, source_event_id, 
                 is_internal_transfer, wallet_from, wallet_to, tx_hash)
                VALUES 
                (:ts_utc, :asset, :qty, :dir, :ttype, :fiat, :price, :fasset, :fqty, :feur,
                 :exch, :sym, :oid, :tid, :srcid, :internal, :wfrom, :wto, :txh)
            """),
            {
                'ts_utc': timestamp_utc.isoformat(),
                'asset': asset,
                'qty': quantity,
                'dir': direction,
                'ttype': transaction_type,
                'fiat': fiat_value_eur,
                'price': price_eur,
                'fasset': fee_asset,
                'fqty': fee_quantity,
                'feur': fee_eur,
                'exch': exchange,
                'sym': symbol,
                'oid': order_id,
                'tid': trade_id,
                'srcid': source_event_id,
                'internal': int(is_internal_transfer),
                'wfrom': wallet_from,
                'wto': wallet_to,
                'txh': tx_hash
            }
        )
        session.commit()
        return result.lastrowid
    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()
