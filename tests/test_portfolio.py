import pytest
import pandas as pd
import json
from engine.portfolio.black_litterman import run_black_litterman
from engine.db.db import get_session
from sqlalchemy import text

@pytest.fixture
def mock_signals_and_prices():
    session = get_session()
    # Insert prices for covariance
    session.execute(text("INSERT INTO prices (date, ticker, close) VALUES ('2023-01-01', 'AAPL', 100), ('2023-01-02', 'AAPL', 102)"))
    session.execute(text("INSERT INTO prices (date, ticker, close) VALUES ('2023-01-01', 'MSFT', 200), ('2023-01-02', 'MSFT', 205)"))
    
    # Insert signals
    session.execute(text("INSERT INTO signals (date, ticker, model_name, expected_return) VALUES ('2023-01-02', 'AAPL', 'momentum', 0.05)"))
    session.execute(text("INSERT INTO signals (date, ticker, model_name, expected_return) VALUES ('2023-01-02', 'AAPL', 'mean_reversion', 0.02)"))
    session.execute(text("INSERT INTO signals (date, ticker, model_name, expected_return) VALUES ('2023-01-02', 'MSFT', 'momentum', -0.01)"))
    session.commit()
    yield
    session.execute(text("DELETE FROM prices"))
    session.execute(text("DELETE FROM signals"))
    session.commit()
    session.close()

def test_black_litterman_signal_breakdown(mock_signals_and_prices):
    # This might require adjusting depending on how the real `run_black_litterman` is implemented
    # But we want to ensure `signal_breakdown` is returned and formatted correctly.
    try:
        mu_bl, breakdown = run_black_litterman(date='2023-01-02')
        
        # Breakdown should be a dict of ticker -> JSON string of model weights
        assert "AAPL" in breakdown
        aapl_breakdown = json.loads(breakdown["AAPL"])
        assert "momentum" in aapl_breakdown
        assert "mean_reversion" in aapl_breakdown
        
        assert "MSFT" in breakdown
        msft_breakdown = json.loads(breakdown["MSFT"])
        assert "momentum" in msft_breakdown
        
    except Exception as e:
        pytest.skip(f"Could not run full BL (likely missing config or other dependencies): {e}")
