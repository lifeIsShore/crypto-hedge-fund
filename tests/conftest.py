import pytest
import os
import sys

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

@pytest.fixture(autouse=True, scope="session")
def setup_test_db():
    import engine.db.db as db_module
    from sqlalchemy import create_engine
    
    # Overwrite engine to use in-memory sqlite
    test_url = "sqlite:///:memory:"
    db_module.DATABASE_URL = test_url
    db_module.engine = create_engine(test_url, pool_pre_ping=True)
    db_module.Session.configure(bind=db_module.engine)
    
    # Create tables
    schema_path = os.path.join(os.path.dirname(db_module.__file__), 'schema.sql')
    db_module.execute_schema(schema_path)
