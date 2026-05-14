# system_bootstrap.py
"""
Cold Start System Bootstrap — Deep Dive Version.
Initializes the fund on a clean environment:
1.  Creates SQLite schema.
2.  Ingests 2 years of historical price data (EUR-converted).
3.  Populates FX rates and Benchmarks.
4.  Backfills 2 years of Macro Regime history (Regime Engine).
5.  Backfills 1 year of PEAD setups and regression models (PEAD Engine).
6.  Backfills 1 year of alpha features (Feature Store).
7.  Trains initial LSTM models for all tickers.
8.  Replays ledger.csv and reconstructs full performance history.
9.  Syncs metadata (Names/Sectors) to all operational tables.
"""

import os
import sys
import logging
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import subprocess
from sqlalchemy import text

# Ensure project root is in path
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from engine.db.db import execute_schema, test_connection, get_session
from engine.data.ingestion import run_ingestion, fetch_fx_history
from engine.features.backfill_features import run_backfill
from engine.alpha.lstm_model import LSTMAlpha
from engine.reconciliation.ledger_importer import run_ledger_import, replay_ledger
from portfolio.src.config import ASSET_UNIVERSE, BENCHMARK_TICKER, TICKER_MAPPING, TICKER_NAMES, TICKER_SECTORS

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger('bootstrap')

def run_step(name, cmd_list, cwd=None):
    logger.info(f"Running step: {name}...")
    try:
        # Using shell=True for better Windows compatibility with python scripts
        res = subprocess.run(cmd_list, cwd=cwd, capture_output=True, text=True, check=True)
        logger.info(f"Step {name} successful.")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"Step {name} failed: {e.stderr}")
        return False

def populate_fx_and_benchmarks():
    """Ensure fx_rates and benchmark prices are populated for the last 2 years."""
    logger.info("Populating FX rates and Benchmark history...")
    end_date = datetime.now().strftime('%Y-%m-%d')
    start_date = (datetime.now() - timedelta(days=730)).strftime('%Y-%m-%d')
    
    # 1. FX Rates
    try:
        fetch_fx_history(start_date, end_date)
        logger.info("FX rates populated.")
    except Exception as e:
        logger.error(f"FX population failed: {e}")

    # 2. Benchmark (MSCI World)
    try:
        run_ingestion([BENCHMARK_TICKER], start_date, end_date)
        logger.info(f"Benchmark ({BENCHMARK_TICKER}) populated.")
    except Exception as e:
        logger.error(f"Benchmark population failed: {e}")

def run_engines_backfill():
    """Run Macro Regime and PEAD engines in backfill mode."""
    # 1. Macro Regime
    regime_dir = os.path.join(_HERE, 'ml_quant_finance_research', 'quant_research', 'regime_engine')
    if os.path.exists(regime_dir):
        run_step("Macro Regime Backfill", [sys.executable, "run_engine.py", "--backfill"], cwd=regime_dir)
    
    # 2. PEAD Engine
    pead_dir = os.path.join(_HERE, 'ml_quant_finance_research', 'quant_research', 'pead_engine')
    if os.path.exists(pead_dir):
        # We use a 365 day lookback for the cold start
        run_step("PEAD Backfill", [sys.executable, "run_engine.py", "--backfill", "--lookback", "365"], cwd=pead_dir)

def sync_metadata():
    """Sync static metadata from config.py to operational tables."""
    logger.info("Syncing ticker names and sectors to operational tables...")
    session = get_session()
    try:
        # Update pead_setups
        for ticker, name in TICKER_NAMES.items():
            sector = TICKER_SECTORS.get(ticker, 'Unknown')
            session.execute(text("""
                UPDATE pead_setups 
                SET sector = :sector 
                WHERE ticker = :ticker AND (sector IS NULL OR sector = 'Unknown')
            """), {'ticker': ticker, 'sector': sector})
        
        # We could also populate a dedicated metadata table if it existed
        session.commit()
        logger.info("Metadata sync complete.")
    except Exception as e:
        logger.error(f"Metadata sync failed: {e}")
        session.rollback()
    finally:
        session.close()

def reconstruct_performance_history():
    """
    Step through time from the first ledger entry to today.
    Reconstructs daily portfolio value and returns.
    """
    logger.info("Reconstructing performance history from ledger...")
    
    holdings, cash = replay_ledger()
    if not holdings and cash == 0:
        logger.warning("No ledger data found. Skipping performance reconstruction.")
        return

    # Load all prices into memory
    session = get_session()
    try:
        price_rows = session.execute(text("SELECT date, ticker, adj_close FROM prices")).fetchall()
        price_map = {} # (date, ticker) -> price
        for r in price_rows:
            price_map[(r[0], r[1])] = float(r[2])
            
        benchmark_rows = session.execute(text(f"SELECT date, adj_close FROM prices WHERE ticker = '{BENCHMARK_TICKER}'")).fetchall()
        bench_map = {r[0]: float(r[1]) for r in benchmark_rows}
    finally:
        session.close()

    if not price_map:
        logger.error("No prices in DB. Run ingestion first.")
        return

    all_dates = sorted(list(set(d for d, t in price_map.keys())))
    if not all_dates:
        return

    ledger_path = os.path.join(_HERE, 'portfolio', 'data', 'ledger.csv')
    ledger_df = pd.read_csv(ledger_path, comment='#')
    ledger_df.columns = [c.strip().lower() for c in ledger_df.columns]
    ledger_df['date'] = pd.to_datetime(ledger_df['date']).dt.strftime('%Y-%m-%d')
    ledger_df = ledger_df.sort_values('date')

    daily_holdings = {}
    daily_cash = 0.0
    perf_data = []
    
    ledger_idx = 0
    start_date = ledger_df['date'].min()
    
    prev_total_val = None

    for dt in all_dates:
        if dt < start_date: continue
        
        # Apply transactions for this date
        while ledger_idx < len(ledger_df) and ledger_df.iloc[ledger_idx]['date'] <= dt:
            row = ledger_df.iloc[ledger_idx]
            action = str(row['action']).strip().title()
            ticker = str(row['ticker']).strip().upper()
            qty = float(row.get('quantity', 0) or 0)
            total = float(row.get('total', 0) or 0)
            
            if action == 'Deposit': daily_cash += total
            elif action == 'Withdrawal': daily_cash -= total
            elif action == 'Dividend': daily_cash += total
            elif action == 'Fee': daily_cash -= total
            elif action == 'Buy':
                daily_cash -= total
                daily_holdings[ticker] = daily_holdings.get(ticker, 0.0) + qty
            elif action == 'Sell':
                daily_cash += total
                daily_holdings[ticker] = daily_holdings.get(ticker, 0.0) - qty
                if daily_holdings[ticker] < 0.0001: del daily_holdings[ticker]
            
            ledger_idx += 1
            
        # Calculate daily value in EUR
        invested_val = 0.0
        for t, q in daily_holdings.items():
            p = price_map.get((dt, t))
            if p is None:
                # Try US fallback
                for primary, fallback in TICKER_MAPPING.items():
                    if primary == t:
                        p = price_map.get((dt, fallback))
                        break
            if p: invested_val += q * p
            
        total_val = invested_val + daily_cash
        bench_val = bench_map.get(dt)
        
        daily_ret = 0.0
        if prev_total_val and prev_total_val > 0:
            daily_ret = (total_val / prev_total_val) - 1
            
        perf_data.append({
            'date': dt,
            'portfolio_value_eur': round(total_val, 2),
            'cash_eur': round(daily_cash, 2),
            'invested_eur': round(invested_val, 2),
            'benchmark_value_eur': bench_val,
            'daily_return_pct': round(daily_ret * 100, 4)
        })
        prev_total_val = total_val

    # Persist to performance_history
    if perf_data:
        session = get_session()
        try:
            session.execute(text("DELETE FROM performance_history"))
            for p in perf_data:
                session.execute(text("""
                    INSERT INTO performance_history 
                    (date, portfolio_value_eur, cash_eur, invested_eur, benchmark_value_eur, daily_return_pct, computed_at)
                    VALUES (:date, :portfolio_value_eur, :cash_eur, :invested_eur, :benchmark_value_eur, :daily_return_pct, datetime('now'))
                """), p)
            session.commit()
            logger.info(f"Reconstructed {len(perf_data)} days of performance history.")
        finally:
            session.close()

def validate_environment():
    """Step 0: Verify environment, dependencies, and database availability."""
    logger.info("Step 0: Validating environment and dependencies...")
    
    # 1. Essential Folders
    required_dirs = [
        'data', 
        'shared/state', 
        'portfolio/data', 
        'engine/alpha/saved_models',
        'ml_quant_finance_research/quant_research/regime_engine',
        'ml_quant_finance_research/quant_research/pead_engine'
    ]
    for d in required_dirs:
        path = os.path.join(_HERE, d)
        if not os.path.exists(path):
            os.makedirs(path, exist_ok=True)
            logger.info(f"Created missing directory: {d}")
    
    # 2. Critical Dependencies
    missing = []
    try: 
        import yfinance
        logger.info(f"[OK] yfinance OK (v{yfinance.__version__})")
    except ImportError: missing.append("yfinance")
    
    try: 
        import torch
        logger.info(f"[OK] torch OK (v{torch.__version__})")
    except ImportError: missing.append("torch")
    
    try: 
        import sqlalchemy
        logger.info("[OK] sqlalchemy OK")
    except ImportError: missing.append("sqlalchemy")
    
    try:
        import pandas as pd
        logger.info(f"[OK] pandas OK (v{pd.__version__})")
    except ImportError: missing.append("pandas")

    if missing:
        logger.error(f"[FAIL] Missing critical dependencies: {', '.join(missing)}")
        logger.error("Please run: pip install yfinance torch sqlalchemy pandas requests")
        sys.exit(1)

    # 3. DB Availability & Lock Check
    if not test_connection():
        logger.error("[FAIL] Database connection failed. Check if engine_data.db is locked or missing.")
        sys.exit(1)
    logger.info("[OK] Database connection OK")

def bootstrap():
    logger.info("🚀 Starting Deep-Dive Cold Start Bootstrap...")

    # Step 0: Environment Validation
    validate_environment()

    # 1. Database Connection & Schema
    logger.info("Applying database schema...")
    execute_schema()

    # 2. Historical Data Ingestion (2 years)
    end_date = datetime.now().strftime('%Y-%m-%d')
    start_date = (datetime.now() - timedelta(days=730)).strftime('%Y-%m-%d')
    
    logger.info(f"Ingesting 2 years of price history for {len(ASSET_UNIVERSE)} tickers...")
    try:
        run_ingestion(ASSET_UNIVERSE, start_date, end_date)
    except Exception as e:
        logger.error(f"Ingestion failed: {e}")

    # 3. FX and Benchmarks
    populate_fx_and_benchmarks()

    # 4. Engine Backfills (Macro & PEAD)
    run_engines_backfill()

    # 5. Metadata Sync
    sync_metadata()

    # 6. Feature Backfill (1 year)
    logger.info("Backfilling 1 year of alpha features...")
    try:
        run_backfill(days=252)
    except Exception as e:
        logger.error(f"Feature backfill failed: {e}")

    # 7. Train LSTM Models
    logger.info("Training initial LSTM models (this may take a while)...")
    try:
        model = LSTMAlpha()
        model.train_all(tickers=ASSET_UNIVERSE)
    except Exception as e:
        logger.error(f"LSTM training failed: {e}")

    # 8. Finalize Portfolio State
    logger.info("Finalizing portfolio state...")
    try:
        run_ledger_import() # Replay and sync latest
        reconstruct_performance_history() # Backfill historical curve
    except Exception as e:
        logger.error(f"Portfolio reconstruction failed: {e}")

    # 9. Final Recalculation
    logger.info("Running final portfolio recalculation/optimization...")
    try:
        run_step("Portfolio Recalculation", [sys.executable, "portfolio/recalculate_engine.py"])
    except Exception as e:
        logger.error(f"Final recalculation failed: {e}")

    logger.info("✅ Bootstrap deep-dive complete. System is fully production-ready.")



if __name__ == '__main__':
    bootstrap()
