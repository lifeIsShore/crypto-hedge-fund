import tkinter as tk
from tkinter import ttk, scrolledtext
import threading
import logging
import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

# Import the actual engine components
from src.config import (
    ASSET_UNIVERSE, TREND_FILTER_MA_PERIODS, 
    DRIFT_THRESHOLD_SELL, DRIFT_THRESHOLD_BUY, 
    MIN_TRADE_EUR_FLOOR, FEE_DRAG_TARGET
)
from src.math_optimizer import run_all_scenarios
from src.rules_engine import apply_trend_filter
from src.data_loader import calculate_log_returns

class TextHandler(logging.Handler):
    def __init__(self, text_widget):
        super().__init__()
        self.text_widget = text_widget

    def emit(self, record):
        msg = self.format(record)
        def append():
            self.text_widget.configure(state='normal')
            self.text_widget.insert(tk.END, msg + '\n')
            self.text_widget.configure(state='disabled')
            self.text_widget.yview(tk.END)
        self.text_widget.after(0, append)

class BacktestUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Hedge Fund Portfolio Backtester")
        self.geometry("1000x800")
        self.configure(padx=10, pady=10)

        # Setup UI
        control_frame = ttk.LabelFrame(self, text="Settings")
        control_frame.pack(fill=tk.X, pady=5)

        ttk.Label(control_frame, text="Start Date (YYYY-MM-DD):").grid(row=0, column=0, padx=5, pady=5)
        self.start_entry = ttk.Entry(control_frame, width=15)
        self.start_entry.insert(0, (datetime.today() - timedelta(days=365*2)).strftime('%Y-%m-%d'))
        self.start_entry.grid(row=0, column=1, padx=5, pady=5)

        ttk.Label(control_frame, text="End Date (YYYY-MM-DD):").grid(row=0, column=2, padx=5, pady=5)
        self.end_entry = ttk.Entry(control_frame, width=15)
        self.end_entry.insert(0, datetime.today().strftime('%Y-%m-%d'))
        self.end_entry.grid(row=0, column=3, padx=5, pady=5)

        ttk.Label(control_frame, text="Initial Cash (€):").grid(row=0, column=4, padx=5, pady=5)
        self.cash_entry = ttk.Entry(control_frame, width=15)
        self.cash_entry.insert(0, "10000")
        self.cash_entry.grid(row=0, column=5, padx=5, pady=5)

        self.run_btn = ttk.Button(control_frame, text="Run Backtest", command=self.start_backtest)
        self.run_btn.grid(row=0, column=6, padx=15, pady=5)

        # Matplotlib Figure
        self.fig, self.ax = plt.subplots(figsize=(8, 4))
        self.ax.set_title("Portfolio Equity Curve")
        self.canvas = FigureCanvasTkAgg(self.fig, master=self)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True, pady=5)

        # Log Output
        log_frame = ttk.LabelFrame(self, text="Execution Logs")
        log_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        self.log_text = scrolledtext.ScrolledText(log_frame, state='disabled', height=10)
        self.log_text.pack(fill=tk.BOTH, expand=True)

        # Setup Logging to capture EVERYTHING (root logger)
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.INFO)
        # Clear existing handlers to prevent duplicate prints
        if root_logger.hasHandlers():
            root_logger.handlers.clear()
        handler = TextHandler(self.log_text)
        handler.setFormatter(logging.Formatter('%(asctime)s - %(message)s', '%H:%M:%S'))
        root_logger.addHandler(handler)
        
        self.logger = root_logger

    def start_backtest(self):
        self.run_btn.config(state=tk.DISABLED)
        self.log_text.configure(state='normal')
        self.log_text.delete(1.0, tk.END)
        self.log_text.configure(state='disabled')
        self.ax.clear()
        self.ax.set_title("Portfolio Equity Curve (Running...)")
        self.canvas.draw()
        
        # Run in thread to keep UI responsive
        threading.Thread(target=self.run_engine_backtest, daemon=True).start()

    def run_engine_backtest(self):
        import shutil
        import os
        
        # 0. Clean up any existing yfinance cache to avoid disk garbage
        cache_dir = os.path.join(os.path.expanduser('~'), '.cache', 'yfinance')
        local_cache = 'yfinance.cache'
        for c_path in [cache_dir, local_cache]:
            if os.path.exists(c_path):
                try:
                    if os.path.isdir(c_path):
                        shutil.rmtree(c_path)
                    else:
                        os.remove(c_path)
                    self.logger.info(f"🧹 Cleared old cache data at {c_path}")
                except Exception as e:
                    pass

        try:
            start_date_str = self.start_entry.get()
            end_date_str = self.end_entry.get()
            initial_cash = float(self.cash_entry.get())
            
            self.logger.info(f"Starting backtest from {start_date_str} to {end_date_str} with \u20ac{initial_cash}")
            
            start_date = pd.to_datetime(start_date_str)
            end_date = pd.to_datetime(end_date_str)

            
            # Fetch data with enough buffer for 252 log returns + 200 SMA
            fetch_start = start_date - timedelta(days=500)
            
            self.logger.info("Downloading historical data (this may take a moment)...")
            data = yf.download(ASSET_UNIVERSE, start=fetch_start.strftime('%Y-%m-%d'), end=end_date.strftime('%Y-%m-%d'), auto_adjust=True, progress=False)
            
            if 'Close' not in data.columns:
                prices_df = pd.DataFrame({ASSET_UNIVERSE[0]: data['Close']}) if len(ASSET_UNIVERSE) == 1 else data
            else:
                prices_df = data['Close']
                
            prices_df = prices_df.reindex(columns=ASSET_UNIVERSE)
            
            # Drop completely dead columns to avoid crash
            dead = [c for c in prices_df.columns if prices_df[c].isna().all()]
            if dead:
                prices_df = prices_df.drop(columns=dead)
                
            # Fill gaps safely
            prices_df.ffill(inplace=True)
            prices_df.bfill(inplace=True)

            # FX Conversion (Dynamic)
            self.logger.info("Fetching FX history for EURUSD...")
            fx_data = yf.download("EURUSD=X", start=fetch_start.strftime('%Y-%m-%d'), end=end_date.strftime('%Y-%m-%d'), auto_adjust=True, progress=False)
            if 'Close' in fx_data.columns:
                fx_series = 1 / fx_data["Close"]
            else:
                fx_series = pd.Series(0.92, index=prices_df.index)
            fx_series = fx_series.reindex(prices_df.index, method="ffill").fillna(0.92)

            self.logger.info("Applying dynamic EUR/USD FX rate to US stocks...")
            EUR_SUFFIXES = ('.DE', '.AS', '.PA')
            for col in prices_df.columns:
                if not any(col.endswith(s) for s in EUR_SUFFIXES):
                    prices_df[col] = prices_df[col] * fx_series

            # Filter valid trading days within backtest window
            bt_prices = prices_df[(prices_df.index >= start_date) & (prices_df.index <= end_date)]
            if bt_prices.empty:
                self.logger.error("No trading days found in the selected range.")
                self.run_btn.after(0, lambda: self.run_btn.config(state=tk.NORMAL))
                return

            valid_dates = bt_prices.index.tolist()
            
            current_holdings = {}
            current_cash = initial_cash
            equity_curve = []
            dates_curve = []
            
            # We rebalance every ~20 trading days (1 month)
            REBALANCE_DAYS = 20
            
            self.logger.info("Beginning simulation loop...")
            
            for i, current_date in enumerate(valid_dates):
                latest_prices = prices_df.loc[current_date]
                
                # Daily Equity Tracking
                total_equity = sum(qty * latest_prices[ticker] for ticker, qty in current_holdings.items() if not pd.isna(latest_prices.get(ticker)))
                portfolio_value = total_equity + current_cash
                
                equity_curve.append(portfolio_value)
                dates_curve.append(current_date)
                
                # Rebalance Logic (Only on day 0 or every REBALANCE_DAYS)
                if i % REBALANCE_DAYS == 0 and i + 1 < len(valid_dates):
                    self.logger.info(f"--- Rebalance Date: {current_date.strftime('%Y-%m-%d')} ---")
                    
                    # 1. Lookback data up to today
                    hist_slice = prices_df.loc[:current_date]
                    if len(hist_slice) < 252:
                        self.logger.warning("Not enough history for Markowitz. Skipping rebalance.")
                        continue
                        
                    execution_date = valid_dates[i + 1]
                    execution_prices = prices_df.loc[execution_date]
                        
                    # 2. Log Returns
                    log_returns = calculate_log_returns(hist_slice.tail(252))
                    
                    # 3. Optimize (Markowitz)
                    try:
                        all_results = run_all_scenarios(log_returns)
                        optimal_weights = all_results['max_sharpe']
                    except Exception as e:
                        self.logger.error(f"Optimization failed: {e}")
                        continue
                        
                    # 4. Apply Trend Filter (200 SMA)
                    adjusted_weights = apply_trend_filter(hist_slice, optimal_weights)
                    
                    # 5. Execute Trades based on Drift (T+1)
                    total_equity_exec = sum(qty * execution_prices.get(ticker, latest_prices.get(ticker, 0.0)) 
                                            for ticker, qty in current_holdings.items() 
                                            if not pd.isna(execution_prices.get(ticker, latest_prices.get(ticker))))
                    portfolio_value_exec = total_equity_exec + current_cash
                    
                    dynamic_min_trade = max(MIN_TRADE_EUR_FLOOR, portfolio_value_exec * FEE_DRAG_TARGET)
                    
                    # Process Sells First
                    for ticker, target_weight in adjusted_weights.items():
                        if ticker == 'CASH': continue
                        exec_price = execution_prices.get(ticker, latest_prices.get(ticker, 0.0))
                        if exec_price == 0: continue
                        
                        target_euro = target_weight * portfolio_value_exec
                        current_euro = current_holdings.get(ticker, 0.0) * exec_price
                        trade_euro = target_euro - current_euro
                        
                        drift_pct = (current_euro / portfolio_value_exec) - target_weight if portfolio_value_exec > 0 else 0
                        
                        if abs(trade_euro) >= dynamic_min_trade and drift_pct >= DRIFT_THRESHOLD_SELL:
                            qty_to_sell = abs(trade_euro) / exec_price
                            current_holdings[ticker] -= qty_to_sell
                            current_cash += abs(trade_euro)
                            self.logger.info(f"🔴 SELL {ticker}: \u20ac{abs(trade_euro):.2f} | Reason: Drift +{drift_pct*100:.1f}% breached +{DRIFT_THRESHOLD_SELL*100:.1f}% sell limit. Locking profits.")
                            if current_holdings[ticker] <= 1e-6:
                                del current_holdings[ticker]

                    # Process Buys
                    for ticker, target_weight in adjusted_weights.items():
                        if ticker == 'CASH': continue
                        exec_price = execution_prices.get(ticker, latest_prices.get(ticker, 0.0))
                        if exec_price == 0: continue
                        
                        target_euro = target_weight * portfolio_value_exec
                        current_euro = current_holdings.get(ticker, 0.0) * exec_price
                        trade_euro = target_euro - current_euro
                        
                        drift_pct = (current_euro / portfolio_value_exec) - target_weight if portfolio_value_exec > 0 else 0
                        
                        if trade_euro > dynamic_min_trade and drift_pct <= DRIFT_THRESHOLD_BUY:
                            amount_to_buy = min(trade_euro, current_cash)
                            if amount_to_buy > 10:
                                qty_to_buy = amount_to_buy / exec_price
                                current_holdings[ticker] = current_holdings.get(ticker, 0.0) + qty_to_buy
                                current_cash -= amount_to_buy
                                self.logger.info(f"🟢 BUY {ticker}: \u20ac{amount_to_buy:.2f} | Reason: Drift {drift_pct*100:.1f}% breached {DRIFT_THRESHOLD_BUY*100:.1f}% buy limit. Rebalancing.")

                    # Live plot update every month
                    if i > 0:
                        cur_ret = ((portfolio_value / initial_cash) - 1) * 100
                        # Pass a shallow copy of lists so the background thread doesn't mutate while drawing
                        self.after(0, self._draw_live_plot, list(dates_curve), list(equity_curve), cur_ret)

            # Finalize
            total_return = ((equity_curve[-1] / initial_cash) - 1) * 100
            self.logger.info(f"=== Backtest Complete ===")
            self.logger.info(f"Final Value: \u20ac{equity_curve[-1]:.2f}")
            self.logger.info(f"Total Return: {total_return:.2f}%")
            
            # Final Plot
            self.after(0, self._draw_live_plot, dates_curve, equity_curve, total_return)
            
        except Exception as e:

            self.logger.error(f"Error during backtest: {e}")
            import traceback
            traceback.print_exc()
        finally:
            # Free up RAM by deleting large data structures explicitly
            if 'prices_df' in locals():
                del prices_df
            if 'data' in locals():
                del data
            import gc
            gc.collect()
            
            self.run_btn.after(0, lambda: self.run_btn.config(state=tk.NORMAL))

    def _draw_live_plot(self, dates, equity, return_pct):
        self.ax.clear()
        self.ax.plot(dates, equity, color='#00E5A0', linewidth=2)
        self.ax.set_title(f"Backtest Equity Curve (Return: {return_pct:.2f}%)")
        self.ax.set_ylabel("Portfolio Value (\u20ac)")
        self.ax.grid(True, alpha=0.3)
        self.canvas.draw_idle()

if __name__ == "__main__":
    app = BacktestUI()
    app.mainloop()
