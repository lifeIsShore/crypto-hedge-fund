import ccxt.async_support as ccxt
import asyncio
import pandas as pd
import logging
from engine.db.db import get_session
from sqlalchemy import text
from datetime import datetime

logger = logging.getLogger(__name__)

async def _fetch_funding_rate_single(exchange: ccxt.Exchange, symbol: str) -> pd.DataFrame:
    """Fetch funding rate history from CCXT exchange."""
    try:
        # Binance has funding rate history
        res = await exchange.fetch_funding_rate_history(symbol)
        if not res:
            return pd.DataFrame()
        
        df = pd.DataFrame(res)
        df['date'] = pd.to_datetime(df['timestamp'], unit='ms').dt.date
        df['ticker'] = symbol.replace('USDT', 'EUR') # Match engine's ticker mapping
        df['funding_rate'] = df['fundingRate']
        
        return df[['date', 'ticker', 'funding_rate', 'timestamp']]
    except Exception as e:
        logger.error(f"CCXT funding rate fetch failed for {symbol}: {e}")
        return pd.DataFrame()

async def fetch_funding_rates(tickers: list) -> pd.DataFrame:
    """
    Fetch funding rates for a list of tickers.
    Converts BTC/EUR to BTC/USDT to fetch from Binance Futures.
    """
    exchange = ccxt.binance({
        'enableRateLimit': True,
        'options': {'defaultType': 'future'}, # Perpetual futures
    })
    
    frames = []
    try:
        for ticker in tickers:
            # Map BTC/EUR to BTC/USDT
            symbol = ticker.replace('EUR', 'USDT')
            df = await _fetch_funding_rate_single(exchange, symbol)
            if not df.empty:
                frames.append(df)
                logger.info(f"Successfully fetched funding rates for {ticker}")
            else:
                logger.warning(f"No funding rate data for {ticker}")
    finally:
        await exchange.close()

    if not frames:
        return pd.DataFrame()
    
    # Aggregate daily average funding rate since multiple updates happen per day
    df_all = pd.concat(frames, ignore_index=True)
    df_daily = df_all.groupby(['date', 'ticker'])['funding_rate'].mean().reset_index()
    return df_daily

def persist_funding_rates(df: pd.DataFrame):
    if df.empty:
        return
        
    session = get_session()
    count = 0
    
    # Ensure table exists
    session.execute(text("""
        CREATE TABLE IF NOT EXISTS funding_rates (
            date DATE,
            ticker TEXT,
            funding_rate REAL,
            PRIMARY KEY (date, ticker)
        )
    """))
    
    try:
        for _, row in df.iterrows():
            session.execute(text("""
                INSERT INTO funding_rates (date, ticker, funding_rate)
                VALUES (:date, :ticker, :funding_rate)
                ON CONFLICT(date, ticker) DO UPDATE SET
                    funding_rate = EXCLUDED.funding_rate
            """), {
                'date': row['date'],
                'ticker': row['ticker'],
                'funding_rate': row['funding_rate']
            })
            count += 1
        session.commit()
        logger.info(f"Persisted {count} funding rate rows to DB.")
    except Exception as e:
        session.rollback()
        logger.error(f"Failed to persist funding rates: {e}")
    finally:
        session.close()

def run_funding_rate_ingestion(tickers: list):
    logger.info(f"Funding rate ingestion starting for {len(tickers)} tickers.")
    df = asyncio.run(fetch_funding_rates(tickers))
    if not df.empty:
        persist_funding_rates(df)
        logger.info("Funding rate ingestion complete.")
    else:
        logger.warning("No funding rate data fetched.")

if __name__ == '__main__':
    from portfolio.src.config import ASSET_UNIVERSE
    logging.basicConfig(level=logging.INFO)
    run_funding_rate_ingestion(ASSET_UNIVERSE)
