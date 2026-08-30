import os
import logging
import ccxt
import time
from datetime import datetime
from dotenv import load_dotenv
from portfolio.src.config import TICKER_MAPPING
from engine.db.db import get_session
from sqlalchemy import text
from engine.tax.ingestion import push_raw_event
from engine.tax.ledger import create_ledger_entry
from engine.tax.lot_manager import LotManager
from engine.tax.disposals import record_disposal
from engine.execution.order_manager import OrderState, Order

load_dotenv()
logger = logging.getLogger(__name__)

class CryptoBroker:
    """
    Live Execution interface to Binance.
    Includes Sandbox protection.
    """
    def __init__(self):
        self.sandbox_mode = os.environ.get("SANDBOX_MODE", "0") == "1"
        self.api_key = os.environ.get("BINANCE_API_KEY", "")
        self.api_secret = os.environ.get("BINANCE_API_SECRET", "")
        
        self.exchange = None
        if not self.sandbox_mode:
            if not self.api_key or not self.api_secret:
                logger.error("Live mode active but Binance API credentials missing.")
            else:
                self.exchange = ccxt.binance({
                    'apiKey': self.api_key,
                    'secret': self.api_secret,
                    'enableRateLimit': True,
                    'options': {
                        'defaultType': 'spot'
                    }
                })

    def _get_latest_price_eur(self, ticker: str) -> float:
        """Fetch latest price_eur from local DB to compute base quantity."""
        session = get_session()
        try:
            row = session.execute(
                text("SELECT adj_close FROM prices WHERE ticker = :t ORDER BY date DESC LIMIT 1"),
                {'t': ticker}
            ).fetchone()
            return float(row[0]) if row else 0.0
        finally:
            session.close()
            
    def _get_usd_eur_rate(self) -> float:
        session = get_session()
        try:
            row = session.execute(
                text("SELECT rate FROM fx_rates WHERE pair = 'USDEUR' ORDER BY date DESC LIMIT 1")
            ).fetchone()
            return float(row[0]) if row else 0.92
        finally:
            session.close()

    def execute_market_order(self, order: Order) -> dict:
        """
        Executes a market order. If SANDBOX_MODE=1, simulates the fill.
        """
        # Map to Binance ticker (e.g. BTC/EUR -> BTC/USDT)
        binance_symbol = TICKER_MAPPING.get(order.ticker, order.ticker)
        
        # Calculate quantity in base asset
        local_price = self._get_latest_price_eur(order.ticker)
        if local_price <= 0:
            logger.error(f"Cannot execute {order.ticker}: No local price found to compute quantity.")
            order.state = OrderState.FAILED
            return {"status": "failed", "error": "No local price"}

        quantity = order.value_eur / local_price
        
        # ── SANDBOX EXECUTION ──
        if self.sandbox_mode:
            logger.info(f"[SANDBOX] Simulating {order.action} {quantity:.6f} {binance_symbol} (~€{order.value_eur:.2f})")
            
            # Simulate a fill event payload
            mock_id = f"mock_{int(time.time()*1000)}"
            fill = {
                "id": mock_id,
                "orderId": f"ord_{mock_id}",
                "symbol": binance_symbol.replace("/", ""),
                "price": local_price,
                "qty": quantity,
                "quoteQty": order.value_eur,
                "commission": 1.50 if order.action == 'SELL' else 0.001,
                "commissionAsset": 'EUR' if order.action == 'SELL' else 'BNB',
                "time": int(time.time() * 1000),
                "isBuyer": (order.action == 'BUY')
            }
            self._route_to_tax_engine(order.ticker, order.action, fill)
            self._log_to_trades(order.ticker, order.action, quantity, local_price, order.value_eur, "sandbox_fill")
            
            order.state = OrderState.CONFIRMED
            return {"status": "filled", "mock": True, "fill": fill}

        # ── LIVE EXECUTION ──
        if not self.exchange:
            logger.error("Exchange not initialized. Execution aborted.")
            order.state = OrderState.FAILED
            return {"status": "failed", "error": "Exchange not init"}

        logger.warning(f"[LIVE] Executing {order.action} {quantity:.6f} {binance_symbol}")
        try:
            side = 'buy' if order.action == 'BUY' else 'sell'
            # Execute market order on CCXT
            result = self.exchange.create_market_order(binance_symbol, side, quantity)
            
            # Note: create_market_order returns the order. We often need fetch_my_trades or wait for the fill to get exact fees.
            # For simplicity, we use the returned result structure from CCXT which contains 'trades' (fills) if immediate.
            
            # In a robust production setup, you'd pull from CCXT's normalized trade objects.
            # Let's map it into a standardized fill dict for the tax engine.
            filled_qty = result.get('filled', quantity)
            filled_price = result.get('average', local_price)
            cost_usd = result.get('cost', filled_qty * filled_price)
            
            # CCXT fee structure
            fee_info = result.get('fee', {})
            fee_asset = fee_info.get('currency', 'USDT')
            fee_cost = fee_info.get('cost', 0.0)
            
            # Convert USDT values to EUR for the ledger
            usd_eur = self._get_usd_eur_rate()
            cost_eur = cost_usd * usd_eur
            
            # Build the raw event
            raw_event = {
                "id": result.get('id', f"live_{int(time.time())}"),
                "symbol": binance_symbol,
                "price": filled_price,
                "qty": filled_qty,
                "quoteQty": cost_usd,
                "commission": fee_cost,
                "commissionAsset": fee_asset,
                "time": result.get('timestamp', int(time.time()*1000)),
                "isBuyer": (order.action == 'BUY'),
                "raw_ccxt": result
            }
            
            self._route_to_tax_engine(order.ticker, order.action, raw_event, force_price_eur=filled_price * usd_eur, force_cost_eur=cost_eur)
            self._log_to_trades(order.ticker, order.action, filled_qty, filled_price * usd_eur, cost_eur, "live_ccxt_fill")
            
            order.state = OrderState.CONFIRMED
            logger.info(f"[LIVE] Order {order.ticker} FILLED successfully.")
            return {"status": "filled", "fill": raw_event}
            
        except Exception as e:
            logger.error(f"[LIVE] Order execution failed for {order.ticker}: {str(e)}")
            order.state = OrderState.FAILED
            return {"status": "failed", "error": str(e)}

    def _route_to_tax_engine(self, ticker: str, action: str, fill: dict, force_price_eur=None, force_cost_eur=None):
        """Pipes the fill directly into the German Tax Engine."""
        event_time = datetime.fromtimestamp(fill["time"] / 1000)
        eid = str(fill["id"])
        
        # 1. Raw Event
        src_id = push_raw_event("binance", "market_order", eid, event_time, fill)
        
        # Determine EUR values
        price_eur = force_price_eur if force_price_eur else fill["price"]
        value_eur = force_cost_eur if force_cost_eur else fill["quoteQty"]
        
        fee_asset = fill["commissionAsset"]
        fee_qty = fill["commission"]
        
        # Rough fee EUR conversion (mock logic for simplicity)
        fee_eur = 0.0
        if fee_asset == 'EUR':
            fee_eur = fee_qty
        elif fee_asset == 'USDT':
            fee_eur = fee_qty * self._get_usd_eur_rate()
        elif fee_asset == 'BNB':
            fee_eur = fee_qty * 500.0  # Placeholder BNB price

        # 2. Ledger
        ledger_id = create_ledger_entry(
            source_event_id=src_id, timestamp_utc=event_time, asset=ticker.split('/')[0],
            quantity=fill["qty"], direction=action, transaction_type="TRADE",
            fiat_value_eur=value_eur, price_eur=price_eur,
            fee_asset=fee_asset, fee_quantity=fee_qty, fee_eur=fee_eur
        )
        
        # 3. Lots and Disposals (Tax Engine Logic)
        asset_base = ticker.split('/')[0]
        lm = LotManager(method='FIFO')
        
        if action == 'BUY':
            lm.create_lot(asset_base, event_time, fill["qty"], value_eur, fee_eur, ledger_id)
        elif action == 'SELL':
            consumed = lm.consume_lots(asset_base, fill["qty"])
            for chunk in consumed:
                qty_ratio = chunk['quantity_consumed'] / fill["qty"]
                sale_val_chunk = value_eur * qty_ratio
                sale_fee_chunk = fee_eur * qty_ratio
                
                record_disposal(
                    asset=asset_base, disposal_timestamp=event_time,
                    quantity_disposed=chunk['quantity_consumed'],
                    sale_value_eur=sale_val_chunk, sale_fee_eur=sale_fee_chunk,
                    acquisition_lot_id=chunk['lot_id'],
                    acquisition_timestamp=chunk['acquisition_timestamp'],
                    acquisition_cost_eur=chunk['cost_basis_eur'],
                    method_used='FIFO'
                )

    def _log_to_trades(self, ticker: str, action: str, qty: float, price_eur: float, value_eur: float, notes: str):
        """Log to the general trades table for immediate portfolio calculation."""
        session = get_session()
        try:
            session.execute(text("""
                INSERT INTO trades (date, ticker, action, quantity, price_eur, value_eur, source, notes)
                VALUES (CURRENT_DATE, :ticker, :action, :qty, :price, :value, 'broker', :notes)
            """), {
                "ticker": ticker, "action": action, "qty": qty,
                "price": price_eur, "value": value_eur, "notes": notes,
            })
            session.commit()
        finally:
            session.close()

# Singleton instance
broker = CryptoBroker()
