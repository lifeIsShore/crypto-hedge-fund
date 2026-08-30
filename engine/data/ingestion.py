import os
import sys

# Ensure root is in path for absolute imports
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.normpath(os.path.join(_HERE, '..', '..'))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from portfolio.src.config import ASSET_UNIVERSE

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

"""
Production crypto data ingestion pipeline.
Primary source: CCXT (Binance)
"""

import asyncio
import pandas as pd
import ccxt.async_support as ccxt
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

async def _fetch_ccxt_single(exchange: ccxt.Exchange, ticker: str, from_ts: int, to_ts: int) -> pd.DataFrame:
    """Fetch history from CCXT exchange."""
    try:
        # Binance uses milliseconds for timestamps
        limit = 1000
        all_ohlcv = []
        current_ts = from_ts
        
        while current_ts < to_ts:
            ohlcv = await exchange.fetch_ohlcv(ticker, timeframe='1d', since=current_ts, limit=limit)
            if not ohlcv:
                break
            all_ohlcv.extend(ohlcv)
            # update current_ts to the last fetched timestamp + 1 ms to get next batch
            current_ts = ohlcv[-1][0] + 1
        
        if not all_ohlcv:
            return pd.DataFrame()
            
        df = pd.DataFrame(all_ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['date'] = pd.to_datetime(df['timestamp'], unit='ms').dt.date
        df['ticker'] = ticker
        df['adj_close'] = df['close']  # Crypto has no splits/dividends
        df['source'] = 'ccxt_binance'
        df['currency'] = 'EUR' if 'EUR' in ticker else 'USDT'
        
        # filter by range exactly
        from_date = pd.to_datetime(from_ts, unit='ms').date()
        to_date = pd.to_datetime(to_ts, unit='ms').date()
        df = df[(df['date'] >= from_date) & (df['date'] <= to_date)]
        
        return df[['date', 'ticker', 'open', 'high', 'low', 'close', 'volume', 'adj_close', 'currency', 'source']]
        
    except Exception as e:
        logger.error(f"CCXT fetch failed for {ticker}: {e}")
        return pd.DataFrame()


async def _fetch_all_async(tickers: list, from_date: str, to_date: str) -> pd.DataFrame:
    from_ts = int(pd.Timestamp(from_date).timestamp() * 1000)
    to_ts = int(pd.Timestamp(to_date).timestamp() * 1000)
    
    frames = []
    exchange = ccxt.binance({
        'enableRateLimit': True,
    })
    
    try:
        for ticker in tickers:
            df = await _fetch_ccxt_single(exchange, ticker, from_ts, to_ts)
            if not df.empty:
                frames.append(df)
                logger.info(f"Successfully fetched {len(df)} rows for {ticker} from Binance")
            else:
                logger.warning(f"Failed to fetch {ticker} from Binance")
    finally:
        await exchange.close()

    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


def persist_prices(df: pd.DataFrame):
    if df.empty:
        logger.warning("persist_prices: empty DataFrame — nothing to write")
        return

    from engine.db.db import get_session
    from sqlalchemy import text

    before = len(df)
    df = df[df['close'].notna() & df['adj_close'].notna()].copy()
    dropped = before - len(df)
    if dropped:
        logger.warning(f"persist_prices: dropped {dropped} rows with NaN close/adj_close")

    if df.empty:
        logger.warning("persist_prices: no valid rows to write after NaN filter")
        return

    session = get_session()
    count = 0
    try:
        for _, row in df.iterrows():
            session.execute(text("""
                INSERT INTO prices
                    (date, ticker, open, high, low, close, volume, adj_close, currency, source)
                VALUES
                    (:date, :ticker, :open, :high, :low, :close, :volume, :adj_close, :currency, :source)
                ON CONFLICT (date, ticker) DO UPDATE SET
                    adj_close = EXCLUDED.adj_close,
                    source    = EXCLUDED.source,
                    currency  = EXCLUDED.currency
            """), {
                'date':      row['date'],
                'ticker':    row['ticker'],
                'open':      row.get('open'),
                'high':      row.get('high'),
                'low':       row.get('low'),
                'close':     row.get('close'),
                'volume':    row.get('volume'),
                'adj_close': row.get('adj_close'),
                'currency':  row.get('currency', 'EUR'),
                'source':    row.get('source', 'ccxt_binance'),
            })
            count += 1

        session.commit()
        logger.info(f"Persisted {count} price rows to DB.")
    except Exception as e:
        session.rollback()
        logger.error(f"persist_prices failed: {e}")
        raise
    finally:
        session.close()


def run_ingestion(
    tickers: list,
    from_date: str,
    to_date: str,
    apply_fx: bool = False, # Unused now for crypto
) -> pd.DataFrame:
    
    logger.info(
        f"Ingestion starting: {len(tickers)} tickers, "
        f"{from_date} → {to_date} via CCXT Binance"
    )

    df_raw = asyncio.run(_fetch_all_async(tickers, from_date, to_date))
    if df_raw.empty:
        logger.error("Ingestion: no data returned from Binance")
        return pd.DataFrame()

    from engine.data.validation import validate_prices
    df_clean = validate_prices(df_raw)

    if df_clean.empty:
        logger.error("Ingestion: all rows rejected by validation")
        return pd.DataFrame()

    persist_prices(df_clean)

    logger.info(f"Ingestion complete: {len(df_clean)} rows persisted.")

    # Staleness check
    try:
        from engine.data.validation import check_staleness
        from engine.db.db import get_session
        from sqlalchemy import text as _text

        session = get_session()
        try:
            if not tickers:
                rows = []
            else:
                tickers_list = "', '".join(str(t) for t in tickers)
                rows = session.execute(_text(f"""
                    SELECT ticker, MAX(date) as last_date
                    FROM prices
                    WHERE ticker IN ('{tickers_list}')
                    GROUP BY ticker
                """)).fetchall()
        finally:
            session.close()

        if rows:
            stale_df = pd.DataFrame([
                {"ticker": r[0], "date": r[1]}
                for r in rows
            ])
            # Crypto is 24/7 so a gap > 1 day is stale
            stale_list = check_staleness(stale_df, max_gap_days=2)

            if stale_list:
                stale_tickers = [s["ticker"] for s in stale_list]
                logger.warning(
                    f"⚠️  STALE DATA DETECTED: {len(stale_list)} tickers — {stale_tickers}"
                )
            else:
                logger.info("✅ Staleness check: all tickers fresh.")
    except Exception as e:
        logger.warning(f"Staleness check failed (non-fatal): {e}")

    return df_clean

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('tickers', nargs='*', help='Tickers to ingest')
    parser.add_argument('--days', type=int, default=30, help='Days of history to fetch')
    args = parser.parse_args()

    from datetime import date
    today = str(date.today())
    start_date = str(date.today() - timedelta(days=args.days))

    tickers_to_run = args.tickers if args.tickers else ASSET_UNIVERSE
    logging.basicConfig(level=logging.INFO)
    result = run_ingestion(tickers_to_run, start_date, today)
    print(f"\nResult: {len(result)} rows, tickers: {result['ticker'].unique().tolist() if not result.empty else []}")
