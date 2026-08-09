import pytest
from engine.risk.circuit_breaker import run_circuit_breaker_check
from engine.db.db import get_session
from sqlalchemy import text

@pytest.fixture
def mock_circuit_breaker_data():
    session = get_session()
    # Insert risk event table setup is handled by conftest
    yield
    session.execute(text("DELETE FROM risk_events"))
    session.commit()
    session.close()

def test_circuit_breaker_triggers(mock_circuit_breaker_data):
    # AAPL is held (quantity 10)
    positions = {"AAPL": 10}
    # Average entry is 100
    entry_prices = {"AAPL": 100.0}
    
    # Current price is 80 (20% drawdown, which is > 15% threshold)
    current_prices = {"AAPL": 80.0}
    
    # 20% drawdown should trigger it
    forced_sells = run_circuit_breaker_check(
        positions=positions,
        current_prices=current_prices,
        entry_prices=entry_prices
    )
    
    assert "AAPL" in forced_sells
    
    # Check that a risk event was logged
    session = get_session()
    events = session.execute(text("SELECT * FROM risk_events WHERE event_type = 'circuit_breaker'")).fetchall()
    session.close()
    
    assert len(events) == 1
    assert events[0].ticker == "AAPL"
    assert "drawdown" in events[0].detail.lower()
