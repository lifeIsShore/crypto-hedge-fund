"""baseline_schema

Revision ID: 7280544cbb83
Revises: 
Create Date: 2026-08-09 03:16:34.906465

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7280544cbb83'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    import os
    schema_path = os.path.join(os.path.dirname(__file__), '..', '..', 'engine', 'db', 'schema.sql')
    with open(schema_path, 'r') as f:
        sql = f.read()
    
    statements = [s.strip() for s in sql.split(';') if s.strip()]
    for stmt in statements:
        # Execute only valid non-pragma SQL commands
        if not stmt.upper().startswith("PRAGMA") and not stmt.startswith("--"):
            op.execute(stmt)

def downgrade() -> None:
    pass

