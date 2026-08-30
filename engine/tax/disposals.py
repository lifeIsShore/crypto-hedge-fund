import logging
from datetime import datetime
from engine.db.db import get_session
from sqlalchemy import text

logger = logging.getLogger(__name__)

def record_disposal(
    asset: str,
    disposal_timestamp: datetime,
    quantity_disposed: float,
    sale_value_eur: float,
    sale_fee_eur: float,
    acquisition_lot_id: int,
    acquisition_timestamp: datetime,
    acquisition_cost_eur: float,
    method_used: str
) -> int:
    """
    Creates a formal tax disposal record for a consumed lot chunk.
    Calculates holding period and whether it is tax-free (German >365 day rule).
    """
    if isinstance(acquisition_timestamp, str):
        acquisition_timestamp = datetime.fromisoformat(acquisition_timestamp)
        
    holding_delta = disposal_timestamp - acquisition_timestamp
    holding_days = holding_delta.days
    holding_seconds = holding_delta.seconds
    
    # German BMF rules: holding period > 1 year (365 days) is tax-free for private crypto sales
    tax_category = 'TAXABLE'
    if holding_days > 365:
        tax_category = 'TAX_FREE_LONG_TERM'

    gain_loss_eur = sale_value_eur - acquisition_cost_eur - sale_fee_eur
    tax_year = disposal_timestamp.year

    session = get_session()
    try:
        result = session.execute(
            text("""
                INSERT INTO tax_disposals 
                (asset, disposal_timestamp, quantity, sale_value_eur, sale_fee_eur, 
                 acquisition_lot_id, acquisition_timestamp, acquisition_cost_eur,
                 holding_period_days, holding_period_seconds, gain_loss_eur, 
                 tax_category, tax_year, method_used)
                VALUES 
                (:asset, :dts, :qty, :sval, :sfee, :lot_id, :acq_ts, :acq_cost,
                 :hdays, :hsecs, :gl, :tcat, :tyear, :method)
            """),
            {
                'asset': asset,
                'dts': disposal_timestamp.isoformat(),
                'qty': quantity_disposed,
                'sval': sale_value_eur,
                'sfee': sale_fee_eur,
                'lot_id': acquisition_lot_id,
                'acq_ts': acquisition_timestamp.isoformat(),
                'acq_cost': acquisition_cost_eur,
                'hdays': holding_days,
                'hsecs': holding_seconds,
                'gl': gain_loss_eur,
                'tcat': tax_category,
                'tyear': tax_year,
                'method': method_used
            }
        )
        session.commit()
        return result.lastrowid
    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()
