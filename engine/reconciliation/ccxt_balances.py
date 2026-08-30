import ccxt
import os
import logging
from typing import Dict, Tuple

logger = logging.getLogger(__name__)

def get_binance_balances() -> Tuple[Dict[str, Dict[str, float]], float]:
    """
    Fetches real balances from Binance via CCXT.
    Returns (broker_positions, broker_cash_eur).
    broker_positions format: {'BTC/EUR': {'quantity': 1.5, 'price': 0.0}, ...}
    """
    api_key = os.getenv("BINANCE_API_KEY")
    secret = os.getenv("BINANCE_SECRET")
    
    if not api_key or not secret:
        logger.warning("No BINANCE_API_KEY or BINANCE_SECRET found. Returning empty balances for reconciliation.")
        return {}, 0.0
        
    try:
        exchange = ccxt.binance({
            'apiKey': api_key,
            'secret': secret,
            'enableRateLimit': True,
        })
        
        balance = exchange.fetch_balance()
        broker_positions = {}
        broker_cash_eur = 0.0
        
        for currency, amount_dict in balance['total'].items():
            amount = float(amount_dict)
            if amount > 0:
                if currency in ['EUR', 'USDT']:
                    broker_cash_eur += amount # Simplification: Treating USDT as EUR equivalent for cash balance if EUR not present.
                else:
                    # Construct ticker like 'BTC/EUR'
                    ticker = f"{currency}/EUR"
                    broker_positions[ticker] = {
                        "quantity": amount,
                        "price": 0.0 # Price is not strictly needed for reconciliation qty check
                    }
                    
        return broker_positions, broker_cash_eur
    except Exception as e:
        logger.error(f"Failed to fetch Binance balances: {e}")
        return {}, 0.0
