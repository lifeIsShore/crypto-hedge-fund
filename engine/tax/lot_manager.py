import logging
from datetime import datetime
from typing import List, Dict, Tuple
from engine.db.db import get_session
from sqlalchemy import text

logger = logging.getLogger(__name__)

class LotManager:
    """
    Manages tax lots for assets.
    Supports allocation methods (currently FIFO).
    """

    def __init__(self, method: str = 'FIFO'):
        self.method = method
        if self.method not in ['FIFO', 'LIFO', 'HIFO']:
            logger.warning(f"Method {self.method} not fully supported, defaulting to FIFO logic")

    def create_lot(self, asset: str, acquisition_timestamp: datetime, quantity: float,
                   acquisition_cost_eur: float, acquisition_fee_eur: float, 
                   source_ledger_id: int, wallet: str = 'binance') -> int:
        session = get_session()
        try:
            result = session.execute(
                text("""
                    INSERT INTO tax_lots 
                    (asset, acquisition_timestamp, quantity_original, quantity_remaining,
                     acquisition_cost_eur, acquisition_fee_eur, wallet, method, source_ledger_id)
                    VALUES 
                    (:asset, :ts, :qty, :qty_rem, :cost, :fee, :wallet, :method, :src)
                """),
                {
                    'asset': asset,
                    'ts': acquisition_timestamp.isoformat(),
                    'qty': quantity,
                    'qty_rem': quantity,
                    'cost': acquisition_cost_eur,
                    'fee': acquisition_fee_eur,
                    'wallet': wallet,
                    'method': self.method,
                    'src': source_ledger_id
                }
            )
            session.commit()
            return result.lastrowid
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()

    def consume_lots(self, asset: str, sell_quantity: float, wallet: str = 'binance') -> List[Dict]:
        """
        Consumes lots according to the defined method (FIFO).
        Returns a list of consumed lot portions: 
        [{'lot_id': X, 'quantity_consumed': Y, 'cost_basis_eur': Z, 'acquisition_timestamp': T}, ...]
        """
        session = get_session()
        consumed = []
        remaining_to_sell = sell_quantity

        try:
            # Fetch available lots ordered by acquisition time (FIFO)
            order_clause = "ORDER BY acquisition_timestamp ASC"
            if self.method == 'LIFO':
                order_clause = "ORDER BY acquisition_timestamp DESC"
            elif self.method == 'HIFO':
                # highest cost basis first (cost / original_qty)
                order_clause = "ORDER BY (acquisition_cost_eur / quantity_original) DESC"

            lots = session.execute(
                text(f"""
                    SELECT lot_id, quantity_original, quantity_remaining, acquisition_cost_eur, acquisition_timestamp 
                    FROM tax_lots 
                    WHERE asset = :asset AND quantity_remaining > 0 AND wallet = :wallet
                    {order_clause}
                """),
                {'asset': asset, 'wallet': wallet}
            ).fetchall()

            for lot in lots:
                if remaining_to_sell <= 0:
                    break

                lot_id = lot[0]
                qty_orig = lot[1]
                qty_rem = lot[2]
                cost_eur = lot[3]
                acq_ts = lot[4]

                consume_qty = min(remaining_to_sell, qty_rem)
                
                # Prorated cost basis for this chunk
                cost_basis_chunk = (consume_qty / qty_orig) * cost_eur

                # Update the database
                new_rem = qty_rem - consume_qty
                session.execute(
                    text("UPDATE tax_lots SET quantity_remaining = :rem WHERE lot_id = :lid"),
                    {'rem': new_rem, 'lid': lot_id}
                )

                consumed.append({
                    'lot_id': lot_id,
                    'quantity_consumed': consume_qty,
                    'cost_basis_eur': cost_basis_chunk,
                    'acquisition_timestamp': acq_ts
                })

                remaining_to_sell -= consume_qty

            if remaining_to_sell > 1e-8:
                logger.warning(f"Could not fully consume lots for {asset}. Missing: {remaining_to_sell}")

            session.commit()
            return consumed
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()
