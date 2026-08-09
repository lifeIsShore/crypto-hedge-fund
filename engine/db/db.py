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

if os.getenv('SANDBOX_MODE') == '1':
    _sandbox_path = os.path.abspath(os.path.join(_root, 'sandbox_data.db'))
    DATABASE_URL = f"sqlite:///{_sandbox_path}"
    logger.info("🧪 SANDBOX MODE — using sandbox_data.db")

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


def ensure_schema():
    """Ensure database schema is initialized if tables are missing."""
    try:
        with engine.connect() as conn:
            if DATABASE_URL.startswith('sqlite'):
                res = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name='positions_history'"))
                if not res.fetchone():
                    logger.info("Database missing tables — applying schema automatically...")
                    execute_schema()
    except Exception as e:
        logger.warning(f"Could not auto-check database schema: {e}")


_schema_checked = False

def get_session():
    """Return a new SQLAlchemy session. Caller is responsible for .close()."""
    global _schema_checked
    if not _schema_checked:
        ensure_schema()
        _schema_checked = True
    return Session()


def execute_schema(schema_path: str = None):
    """
    Apply database schema.
    Tries to run Alembic migrations first. Falls back to applying schema.sql directly.
    """
    alembic_cfg_path = os.path.join(_root, 'alembic.ini')
    if os.path.exists(alembic_cfg_path):
        try:
            from alembic.config import Config
            from alembic import command
            logger.info("Applying Alembic migrations...")
            alembic_cfg = Config(alembic_cfg_path)
            alembic_cfg.set_main_option("script_location", os.path.join(_root, "alembic"))
            command.upgrade(alembic_cfg, "head")
            print("[OK] Alembic migrations applied successfully.")
            return
        except Exception as e:
            logger.error(f"Alembic migration failed: {e}. Falling back to schema.sql...")

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
