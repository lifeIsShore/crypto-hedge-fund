"""
Backtesting Engine for FinAdvice ML Models
Simulates real-world trading by walking forward through historical data.
Zero data leakage ensures reliable results.
"""

import pandas as pd
import numpy as np
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
from pathlib import Path
import sys
import os

# Add parent directory to path to import other modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.data_storage import DataStorage
from core.data_fetcher import DataFetcher
from consensus_engine import MultiTimeframeConsensus, Sentiment

logger = logging.getLogger(__name__)

@dataclass
class Trade:
    type: str  # 'BUY' or 'SELL'
    date: datetime
    price: float
    amount: float
    value: float
    fee: float
    consensus: float

@dataclass
class BacktestResult:
    ticker: str
    start_date: datetime
    end_date: datetime
    initial_capital: float
    final_value: float
    total_return_pct: float
    buy_and_hold_return_pct: float
    max_drawdown_pct: float
    trade_count: int
    trades: List[Trade]
    equity_curve: pd.DataFrame

class BacktestEngine:
    """
    Simulates trading strategy using walk-forward validation
    """
    
    def __init__(self, 
                 ticker: str, 
                 start_date: str, 
                 end_date: Optional[str] = None,
                 initial_capital: float = 10000.0,
                 fee_pct: float = 0.001,
                 log_callback: Optional[callable] = None):  # 0.1% fee
        self.ticker = ticker
        self.start_date = pd.to_datetime(start_date)
        self.end_date = pd.to_datetime(end_date) if end_date else datetime.now()
        self.initial_capital = initial_capital
        self.fee_pct = fee_pct
        self.log_callback = log_callback
        
        self.storage = DataStorage(base_dir=os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
        self.fetcher = DataFetcher()
        self.portfolio = {
            'cash': initial_capital,
            'position': 0.0,  # Number of units held
            'equity': initial_capital
        }
        self.trades = []
        self.equity_history = []
        self.stop_requested = False
        
    def log(self, message: str):
        if self.log_callback:
            self.log_callback(message)
        else:
            print(message)

    def run(self, 
            interval: str = '1d', 
            consensus_threshold: float = 50.0, 
            sell_threshold: float = 0.0,
            sell_only_at_profit: bool = False,
            stop_loss_pct: Optional[float] = None,
            pos_size_pct: float = 100.0,
            boost_threshold: Optional[float] = None,
            boost_size_pct: float = 0.0) -> BacktestResult:
        """
        Run the simulation with advanced position management.
        pos_size_pct: Base % of cash to use per trade (100 = All-in)
        boost_threshold: Confidence level to trigger extra buying
        boost_size_pct: Extra % of initial capital/cash to add on boost
        """
        self.log(f"\n[BACKTEST] Starting simulation for {self.ticker}...")
        self.log(f"  Range: {self.start_date.date()} to {self.end_date.date()}")
        self.log(f"  Interval: {interval}, Buy Thresh: {consensus_threshold}%, Sell Thresh: {sell_threshold}%")
        self.log(f"  Positioning: Base {pos_size_pct}%" + (f", Boost {boost_size_pct}% at >{boost_threshold}%" if boost_threshold else ""))
        if sell_only_at_profit: self.log("  Strategy: PROTECT PROFITS (Sell only if Price > Entry)")
        if stop_loss_pct: self.log(f"  Strategy: STOP LOSS enabled at {stop_loss_pct}%")
        
        # Load full historical data for the ticker interval
        full_df = self.storage.load_ticker_data(self.ticker, interval)
        if full_df is None:
            self.log(f"  [DATA] Ticker {self.ticker} not found locally. Attempting to fetch...")
            # Try to fetch all intervals to ensure MultiTimeframe works if needed, 
            # but at least fetch the requested interval for the main loop.
            full_df = self.fetcher.fetch_ticker_data(self.ticker, interval)
            if full_df is not None:
                self.log(f"  [SUCCESS] Fetched {len(full_df)} rows for {self.ticker}. Saving locally...")
                self.storage.save_ticker_data(self.ticker, interval, full_df)
            else:
                raise ValueError(f"Could not fetch data for {self.ticker}. Please check connectivity or ticker symbol.")
            
        # Ensure Date column is datetime and timezone-naive to avoid comparison errors
        full_df['Date'] = pd.to_datetime(full_df['Date'])
        if full_df['Date'].dt.tz is not None:
            full_df['Date'] = full_df['Date'].dt.tz_localize(None)
        
        # Ensure start/end dates are also naive for comparison
        if not isinstance(self.start_date, pd.Timestamp):
            self.start_date = pd.Timestamp(self.start_date)
        if not isinstance(self.end_date, pd.Timestamp):
            self.end_date = pd.Timestamp(self.end_date)
            
        self.start_date = self.start_date.tz_localize(None) if self.start_date.tzinfo else self.start_date
        self.end_date = self.end_date.tz_localize(None) if self.end_date.tzinfo else self.end_date
        
        full_df = full_df.sort_values('Date')
        
        # Filter for the backtest range (but we need some history before start_date for training)
        backtest_dates = full_df[(full_df['Date'] >= self.start_date) & 
                                 (full_df['Date'] <= self.end_date)]['Date'].unique()
        
        if len(backtest_dates) == 0:
            raise ValueError(f"No data points in backtest range {self.start_date} to {self.end_date}")

        # Main Simulation Loop
        for sim_date in backtest_dates:
            if self.stop_requested:
                self.log("\n[ABORTED] Backtest cancelled by user.")
                return None
                
            sim_date = pd.to_datetime(sim_date)
            
            # 1. Truncate data to simulate "today" (No Leakage)
            current_df = full_df[full_df['Date'] < sim_date]
            
            # Need at least 30-50 rows to calculate indicators (RSI, MA20, etc.)
            if len(current_df) < 50:
                continue
                
            # Current price (at the open of sim_date or close of previous date)
            # We use the 'Close' of the latest available row as our execution price
            price_row = full_df[full_df['Date'] == sim_date].iloc[0]
            current_price = price_row['Open'] # We buy at open of the day we make the decision
            
            # 2. Run Consensus Engine
            # Note: For efficiency in backtest, we might want a lightweight consensus
            # but for accuracy, we use the real one.
            consensus_val, confidence = self._get_simulated_consensus(sim_date, full_df)
            
            # 3. Apply Trading Signal (Long Only)
            entry_price = self.trades[-1].price if self.trades and self.trades[-1].type == 'BUY' and self.portfolio['position'] > 0 else None
            
            # Check Stop Loss First
            if stop_loss_pct is not None and entry_price:
                pct_change = (current_price - entry_price) / entry_price * 100
                if pct_change <= -abs(stop_loss_pct):
                    self.log(f"  [STOP LOSS] Activated at {current_price:.2f} ({pct_change:.1f}%)")
                    self._execute_trade('SELL', sim_date, current_price, consensus_val, reason="STOP_LOSS")
                    continue

            if consensus_val >= consensus_threshold:
                # BUY Signal with Dynamic Scaling
                actual_size = pos_size_pct
                if boost_threshold and consensus_val >= boost_threshold:
                    actual_size += boost_size_pct
                
                # Limit size to 100% of current cash
                actual_size = min(actual_size, 100.0)
                
                if self.portfolio['cash'] > 10:
                    self._execute_trade('BUY', sim_date, current_price, consensus_val, size_pct=actual_size)
            elif consensus_val <= sell_threshold: # SELL Signal
                # SELL Signal
                if self.portfolio['position'] > 0:
                    # Optional: Profit Protection
                    if sell_only_at_profit and entry_price and current_price < entry_price:
                        # self.log(f"  [HOLD] Sell signal ignored (Price {current_price:.2f} < Entry {entry_price:.2f})")
                        pass
                    else:
                        # For now, SELL is always 100% (Scale-out can be added later if user wants)
                        self._execute_trade('SELL', sim_date, current_price, consensus_val)
            
            # Record Equity Tracker
            total_value = self.portfolio['cash'] + (self.portfolio['position'] * price_row['Close'])
            self.equity_history.append({
                'Date': sim_date,
                'Cash': self.portfolio['cash'],
                'Position': self.portfolio['position'],
                'Price': price_row['Close'],
                'Total_Value': total_value,
                'Consensus': consensus_val
            })
            
            # Print progress every 10 steps
            if len(self.equity_history) % 10 == 0:
                self.log(f"  {sim_date.date()} | Equity: {total_value:.2f} | Consensus: {consensus_val:.1f}%")

        return self._finalize_results(full_df)

    def _get_simulated_consensus(self, sim_date: datetime, full_df: pd.DataFrame) -> tuple:
        """
        Calculates consensus for a specific historical point in time.
        In a real backtest, we should call MultiTimeframeConsensus, 
        but we must mock the DataStorage to only return data UP TO sim_date.
        """
        # Temporal Storage Mock
        class MockStorage:
            def __init__(self, full_df, sim_date):
                self.full_df = full_df
                self.sim_date = sim_date
            def load_ticker_data(self, ticker, interval):
                # We assume the user has multiple intervals? 
                # For this simple backtest, we only use the primary interval data
                return self.full_df[self.full_df['Date'] < self.sim_date]

        # Use the actual engine
        mock_storage = MockStorage(full_df, sim_date)
        engine = MultiTimeframeConsensus(mock_storage, self.ticker)
        
        # We only generate consensus for the primary interval to save time in backtest
        # Real world would check 1h, 4h, 1d... but we don't have all data synced for old dates easily
        # So we adapt: We run models on the truncated single-interval data
        prediction = engine.predict_interval(mock_storage.load_ticker_data(self.ticker, None), 'backtest_interval', is_backtest=True)
        
        if prediction:
            return prediction.confidence if prediction.change_percent > 0 else -prediction.confidence, prediction.confidence
        return 0, 0

    def _execute_trade(self, side: str, date: datetime, price: float, consensus: float, reason: str = "SIGNAL", size_pct: float = 100.0):
        if side == 'BUY':
            # Buy with specified % of available cash
            trade_cash = self.portfolio['cash'] * (size_pct / 100.0)
            fee = trade_cash * self.fee_pct
            net_cash = trade_cash - fee
            amount = net_cash / price
            value = net_cash
            
            self.portfolio['position'] += amount
            self.portfolio['cash'] -= trade_cash
            
            trade = Trade('BUY', date, price, amount, value, fee, consensus)
            self.trades.append(trade)
            self.log(f"  >>> BUY {size_pct}% ({amount:.4f} units) at {price:.2f} (Consensus: {consensus:.1f}%)")
            
        elif side == 'SELL':
            # Sell all positions (100% exit)
            value = self.portfolio['position'] * price
            fee = value * self.fee_pct
            net_value = value - fee
            
            amount = self.portfolio['position']
            self.portfolio['cash'] += net_value
            self.portfolio['position'] = 0.0
            
            trade = Trade('SELL', date, price, amount, net_value, fee, consensus)
            self.trades.append(trade)
            self.log(f"  <<< SELL ALL ({amount:.4f} units) at {price:.2f} (Consensus: {consensus:.1f}%) [{reason}]")

    def _finalize_results(self, full_df: pd.DataFrame) -> BacktestResult:
        equity_df = pd.DataFrame(self.equity_history)
        
        if equity_df.empty:
            return None
            
        final_value = equity_df.iloc[-1]['Total_Value']
        total_return = ((final_value / self.initial_capital) - 1) * 100
        
        # Buy and Hold return
        start_price = equity_df.iloc[0]['Price']
        end_price = equity_df.iloc[-1]['Price']
        bh_return = ((end_price / start_price) - 1) * 100
        
        # Max Drawdown
        equity_df['Peak'] = equity_df['Total_Value'].cummax()
        equity_df['Drawdown'] = (equity_df['Total_Value'] - equity_df['Peak']) / equity_df['Peak'] * 100
        max_dd = equity_df['Drawdown'].min()
        
        return BacktestResult(
            ticker=self.ticker,
            start_date=self.start_date,
            end_date=self.end_date,
            initial_capital=self.initial_capital,
            final_value=final_value,
            total_return_pct=total_return,
            buy_and_hold_return_pct=bh_return,
            max_drawdown_pct=max_dd,
            trade_count=len(self.trades),
            trades=self.trades,
            equity_curve=equity_df
        )

if __name__ == "__main__":
    # Test execution
    engine = BacktestEngine(ticker='AAPL', start_date='2024-01-01', initial_capital=1000)
    # result = engine.run(interval='1d')
    # print(f"Final Return: {result.total_return_pct:.2f}%")
