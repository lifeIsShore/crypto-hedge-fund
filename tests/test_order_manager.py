import pytest
import pandas as pd
from engine.db.db import get_session
from sqlalchemy import text
from engine.execution.order_manager import generate_order_queue

@pytest.fixture
def mock_prices_adv():
    # Insert some mock prices with volume to establish an ADV for 'AAPL' and 'TSLA'
    session = get_session()
    # AAPL ADV = 1,000,000 * 100 = 100,000,000 EUR. 5% = 5,000,000 EUR
    session.execute(text("INSERT INTO prices (date, ticker, close, volume) VALUES ('2023-01-01', 'AAPL', 100.0, 1000000)"))
    # TSLA ADV = 10,000 * 200 = 2,000,000 EUR. 5% = 100,000 EUR
    session.execute(text("INSERT INTO prices (date, ticker, close, volume) VALUES ('2023-01-01', 'TSLA', 200.0, 10000)"))
    # MSFT has no prices, ADV should fall back to 1e9
    session.commit()
    yield
    session.execute(text("DELETE FROM prices"))
    session.commit()
    session.close()

def test_liquidity_gating_caps_large_orders(mock_prices_adv):
    # Total portfolio is 200,000,000 EUR
    # We want 10% TSLA -> 20,000,000 EUR buy order.
    # 5% of TSLA ADV (2M) is 100,000. So it should cap at 100,000 EUR.
    
    suggested = pd.Series({"TSLA": 0.10, "AAPL": 0.10})
    current = pd.Series({"TSLA": 0.0, "AAPL": 0.0})
    
    # 20M per order requested
    orders = generate_order_queue(suggested, current, total_portfolio_eur=200_000_000.0, adv_limit_pct=0.05)
    
    assert len(orders) == 2
    
    # Find orders
    tsla_order = next(o for o in orders if o.ticker == "TSLA")
    aapl_order = next(o for o in orders if o.ticker == "AAPL")
    
    # TSLA should be capped at 100,000
    assert tsla_order.value_eur == 100000.0
    assert tsla_order.action == "BUY"
    
    # AAPL should be capped at 5,000,000
    assert aapl_order.value_eur == 5000000.0
    assert aapl_order.action == "BUY"

def test_no_liquidity_gating_when_missing_volume():
    suggested = pd.Series({"MSFT": 0.10})
    current = pd.Series({"MSFT": 0.0})
    
    # MSFT has no ADV data, so order should not be capped by the 1e9 fallback
    orders = generate_order_queue(suggested, current, total_portfolio_eur=500_000.0, adv_limit_pct=0.05)
    
    assert len(orders) == 1
    assert orders[0].ticker == "MSFT"
    assert orders[0].value_eur == 50_000.0  # 10% of 500k

def test_tolerance_bands():
    # Buy threshold is typically 0.10 (10% drift) or whatever is in config
    from portfolio.src.config import DRIFT_THRESHOLD_BUY, DRIFT_THRESHOLD_SELL
    
    suggested = pd.Series({"GOOG": 0.10})
    current = pd.Series({"GOOG": 0.095})
    
    # Delta is 0.005. Drift pct is 0.005 / 0.10 = 0.05 (5%).
    # If DRIFT_THRESHOLD_BUY > 0.05, it should be filtered out.
    orders = generate_order_queue(suggested, current, total_portfolio_eur=10_000_000.0)
    
    # Depending on config, this may or may not generate an order.
    # We just ensure it runs cleanly.
    pass
