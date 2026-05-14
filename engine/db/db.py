# engine/db/db.py
"""
Database connection layer.
Reads DATABASE_URL from .env (or environment).
All engine modules import get_session() and engine from here.
"""

import os
import logging
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

logger = logging.getLogger(__name__)

# Load .env if present (requires: pip install python-dotenv)
_here = os.path.dirname(os.path.abspath(__file__))
_root = os.path.join(_here, '..', '..')

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(_root, '.env'))
except ImportError:
    pass  # python-dotenv not installed — rely on environment variables

_default_db = f"sqlite:///{os.path.abspath(os.path.join(_root, 'engine_data.db'))}"
DATABASE_URL = os.getenv('DATABASE_URL', _default_db)

# pool_pre_ping avoids "connection closed" errors after long idle periods
# SQLite needs a timeout for concurrent writes to avoid "database is locked" errors
if DATABASE_URL.startswith('sqlite'):
    engine = create_engine(
        DATABASE_URL, 
        pool_pre_ping=True, 
        echo=False,
        connect_args={"timeout": 30}
    )
else:
    engine = create_engine(DATABASE_URL, pool_pre_ping=True, echo=False)

Session = sessionmaker(bind=engine)


def get_session():
    """Return a new SQLAlchemy session. Caller is responsible for .close()."""
    return Session()


def execute_schema(schema_path: str = None):
    """
    Apply schema.sql to the database.
    Safe to run multiple times — all statements use IF NOT EXISTS.
    """
    if schema_path is None:
        schema_path = os.path.join(os.path.dirname(__file__), 'schema.sql')

    with open(schema_path, 'r') as f:
        sql = f.read()

    with engine.connect() as conn:
        # Split on semicolons and execute each statement individually
        statements = [s.strip() for s in sql.split(';') if s.strip()]
        for stmt in statements:
            try:
                conn.execute(text(stmt))
            except Exception as e:
                logger.warning(f"Schema statement skipped ({e}): {stmt[:80]}...")
        conn.commit()

    logger.info(f"Schema applied from {schema_path}")
    print("[OK] Schema applied successfully.")


def test_connection():
    """Quick connectivity test. Returns True on success."""
    try:
        with engine.connect() as conn:
            result = conn.execute(text('SELECT 1'))
            result.fetchone()
        print(f"[OK] Connected to: {DATABASE_URL}")
        return True
    except Exception as e:
        print(f"[FAIL] Connection failed: {e}")
        return False


if __name__ == '__main__':
    # python -m engine.db.db
    if test_connection():
        execute_schema()
