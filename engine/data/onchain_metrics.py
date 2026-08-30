import requests
import pandas as pd
import logging
import sys
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.normpath(os.path.join(_HERE, '..', '..'))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from engine.db.db import get_session
from sqlalchemy import text

logger = logging.getLogger(__name__)

def fetch_defillama_metrics() -> pd.DataFrame:
    """
    Fetches historical Total Value Locked (TVL) and Stablecoin Total Market Cap 
    from the free DeFiLlama API. Returns a daily DataFrame.
    """
    # 1. Fetch TVL
    tvl_url = "https://api.llama.fi/v2/historicalChainTvl"
    try:
        r = requests.get(tvl_url)
        r.raise_for_status()
        tvl_data = r.json()
        df_tvl = pd.DataFrame(tvl_data)
        df_tvl['date'] = pd.to_datetime(df_tvl['date'], unit='s').dt.date
        df_tvl = df_tvl.rename(columns={'tvl': 'total_tvl'})
        df_tvl = df_tvl.set_index('date')
    except Exception as e:
        logger.error(f"Failed to fetch TVL from DeFiLlama: {e}")
        df_tvl = pd.DataFrame()

    # 2. Fetch Stablecoin Market Cap
    sc_url = "https://stablecoins.llama.fi/stablecoincharts/all"
    try:
        r = requests.get(sc_url)
        r.raise_for_status()
        sc_data = r.json()
        
        parsed = []
        for row in sc_data:
            dt = pd.to_datetime(int(row['date']), unit='s').date()
            val = row.get('totalCirculatingUSD', {}).get('peggedUSD', 0)
            parsed.append({'date': dt, 'stablecoin_mcap': val})
            
        df_sc = pd.DataFrame(parsed).set_index('date')
    except Exception as e:
        logger.error(f"Failed to fetch Stablecoin metrics from DeFiLlama: {e}")
        df_sc = pd.DataFrame()

    if df_tvl.empty and df_sc.empty:
        return pd.DataFrame()
        
    df = df_tvl.join(df_sc, how='outer').ffill().reset_index()
    return df

def persist_onchain_metrics(df: pd.DataFrame):
    if df.empty:
        return
        
    session = get_session()
    count = 0
    
    # Ensure table exists
    session.execute(text("""
        CREATE TABLE IF NOT EXISTS onchain_metrics (
            date DATE PRIMARY KEY,
            total_tvl REAL,
            stablecoin_mcap REAL
        )
    """))
    
    try:
        for _, row in df.iterrows():
            session.execute(text("""
                INSERT INTO onchain_metrics (date, total_tvl, stablecoin_mcap)
                VALUES (:date, :total_tvl, :stablecoin_mcap)
                ON CONFLICT(date) DO UPDATE SET
                    total_tvl = EXCLUDED.total_tvl,
                    stablecoin_mcap = EXCLUDED.stablecoin_mcap
            """), {
                'date': row['date'],
                'total_tvl': row.get('total_tvl'),
                'stablecoin_mcap': row.get('stablecoin_mcap')
            })
            count += 1
        session.commit()
        logger.info(f"Persisted {count} on-chain metric rows to DB.")
    except Exception as e:
        session.rollback()
        logger.error(f"Failed to persist on-chain metrics: {e}")
    finally:
        session.close()

def run_onchain_ingestion():
    logger.info("On-chain metrics ingestion (DeFiLlama) starting.")
    df = fetch_defillama_metrics()
    if not df.empty:
        persist_onchain_metrics(df)
        logger.info("On-chain metrics ingestion complete.")
    else:
        logger.warning("No on-chain data fetched.")

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    run_onchain_ingestion()
