import logging
import feedparser
import pandas as pd
from datetime import datetime, timezone
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.normpath(os.path.join(_HERE, '..', '..'))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from engine.db.db import get_session
from sqlalchemy import text

logger = logging.getLogger(__name__)

# Popular and free Crypto RSS Feeds
RSS_FEEDS = {
    "coindesk": "https://www.coindesk.com/arc/outboundfeeds/rss/",
    "cointelegraph": "https://cointelegraph.com/rss",
    "cryptoslate": "https://cryptoslate.com/feed/"
}

def fetch_crypto_headlines():
    """Fetches latest crypto headlines from popular RSS feeds."""
    all_articles = []
    
    for source, url in RSS_FEEDS.items():
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries:
                pub_date = None
                if hasattr(entry, 'published_parsed') and entry.published_parsed:
                    pub_date = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
                else:
                    pub_date = datetime.now(timezone.utc)
                    
                all_articles.append({
                    'date': pub_date.strftime('%Y-%m-%d'),
                    'source': source,
                    'title': entry.title,
                    'summary': entry.summary if hasattr(entry, 'summary') else ''
                })
        except Exception as e:
            logger.error(f"Failed to fetch RSS feed {source}: {e}")
            
    df = pd.DataFrame(all_articles)
    if not df.empty:
        # Drop duplicates
        df = df.drop_duplicates(subset=['title'])
    return df

def run_sentiment_ingestion():
    """Fetches headlines, scores them using VADER, and stores them in DB."""
    logger.info("[sentiment] Fetching latest crypto news from RSS feeds...")
    df = fetch_crypto_headlines()
    
    if df.empty:
        logger.warning("[sentiment] No headlines found.")
        return
        
    logger.info(f"[sentiment] Fetched {len(df)} headlines. Processing NLP...")
    
    try:
        from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
        analyzer = SentimentIntensityAnalyzer()
        
        # We will add custom crypto-specific lexicon to VADER
        crypto_lexicon = {
            "bullish": 2.0, "bearish": -2.0, "moon": 2.0, "rekt": -3.0, 
            "rug": -3.0, "scam": -3.0, "hack": -2.5, "pump": 1.5, "dump": -2.0,
            "ath": 2.0, "fud": -2.0, "fomo": 1.5, "adoption": 1.5, "partnership": 1.5
        }
        analyzer.lexicon.update(crypto_lexicon)
        
        df['compound_score'] = df['title'].apply(lambda x: analyzer.polarity_scores(str(x))['compound'])
        
        # Aggregate daily mean score (portfolio wide)
        # You could also do per-ticker by searching for "BTC", "Bitcoin", etc in the title
        daily_sentiment = df.groupby('date')['compound_score'].mean().reset_index()
        daily_sentiment = daily_sentiment.rename(columns={'compound_score': 'sentiment_score'})
        
        # Save to DB
        session = get_session()
        
        # Create table if not exists
        session.execute(text("""
            CREATE TABLE IF NOT EXISTS crypto_sentiment (
                date TEXT PRIMARY KEY,
                sentiment_score REAL
            )
        """))
        
        for _, row in daily_sentiment.iterrows():
            session.execute(text("""
                INSERT INTO crypto_sentiment (date, sentiment_score)
                VALUES (:date, :score)
                ON CONFLICT(date) DO UPDATE SET sentiment_score = :score
            """), {"date": row['date'], "score": row['sentiment_score']})
            
        session.commit()
        session.close()
        
        logger.info(f"[sentiment] Inserted/Updated sentiment for {len(daily_sentiment)} dates.")
        
    except ImportError:
        logger.error("[sentiment] vaderSentiment not installed. Run `pip install vaderSentiment`.")
    except Exception as e:
        logger.error(f"[sentiment] Error processing sentiment: {e}")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_sentiment_ingestion()
