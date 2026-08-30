"""add_liquidity_tier

Revision ID: e6906f4b0325
Revises: 7280544cbb83
Create Date: 2026-08-30 17:53:38.596085

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e6906f4b0325'
down_revision: Union[str, None] = '7280544cbb83'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Liquidity Tier
    op.execute("""
        CREATE TABLE IF NOT EXISTS ticker_liquidity_tier (
            date            TEXT    NOT NULL,
            ticker          TEXT    NOT NULL,
            tier            TEXT    NOT NULL,
            trading_days_90d INTEGER,
            avg_range_pct   REAL,
            history_days    INTEGER,
            days_since_update INTEGER,
            score           REAL,
            computed_at     TEXT    DEFAULT (datetime('now')),
            PRIMARY KEY (date, ticker)
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_liquidity_tier_ticker ON ticker_liquidity_tier (ticker, date)")

    # Onchain Metrics
    op.execute("""
        CREATE TABLE IF NOT EXISTS onchain_metrics (
            date            TEXT    NOT NULL,
            total_tvl       REAL,
            stablecoin_mcap REAL,
            PRIMARY KEY (date)
        )
    """)

    # Crypto Sentiment
    op.execute("""
        CREATE TABLE IF NOT EXISTS crypto_sentiment (
            date            TEXT    NOT NULL,
            sentiment_score REAL    NOT NULL,
            PRIMARY KEY (date)
        )
    """)

    # Correlation Clusters
    op.execute("""
        CREATE TABLE IF NOT EXISTS correlation_clusters (
            date        TEXT NOT NULL,
            ticker      TEXT NOT NULL,
            cluster_id  INTEGER NOT NULL,
            computed_at TEXT DEFAULT (datetime('now')),
            PRIMARY KEY (date, ticker)
        )
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS ticker_liquidity_tier")
    op.execute("DROP TABLE IF EXISTS onchain_metrics")
    op.execute("DROP TABLE IF EXISTS crypto_sentiment")
    op.execute("DROP TABLE IF EXISTS correlation_clusters")
