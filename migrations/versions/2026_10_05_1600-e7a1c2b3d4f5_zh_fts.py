"""Chinese full-text search via zhparser; weight name (A) above content (B)

Revision ID: e7a1c2b3d4f5
Revises: d4e5f6a1b2c3
Create Date: 2026-10-05 16:00:00.000000

Requires a PostgreSQL image that ships the zhparser extension
(e.g. moailaozi/postgres-images:zhparser-pgvector-17).

Idempotent: on a database where the 'chinese' config and the weighted
search_vector column were already created by hand, this is a no-op.
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e7a1c2b3d4f5"
down_revision: Union[str, Sequence[str], None] = "d4e5f6a1b2c3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_ZH_EXPR = (
    "setweight(to_tsvector('chinese'::regconfig, name), 'A') || "
    "setweight(to_tsvector('chinese'::regconfig, content), 'B')"
)
_SIMPLE_EXPR = "to_tsvector('simple', content)"


def _rebuild_search_vector(expr: str) -> None:
    op.execute("DROP INDEX IF EXISTS ix_memories_search_vector")
    op.execute("ALTER TABLE memories DROP COLUMN IF EXISTS search_vector")
    op.execute(
        "ALTER TABLE memories ADD COLUMN search_vector tsvector "
        f"GENERATED ALWAYS AS ({expr}) STORED NOT NULL"
    )
    op.execute("CREATE INDEX ix_memories_search_vector ON memories USING gin (search_vector)")


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS zhparser")
    op.execute(
        """
        DO $$
        BEGIN
          IF NOT EXISTS (SELECT 1 FROM pg_ts_config WHERE cfgname = 'chinese') THEN
            CREATE TEXT SEARCH CONFIGURATION chinese (PARSER = zhparser);
            ALTER TEXT SEARCH CONFIGURATION chinese
              ADD MAPPING FOR n,v,a,i,e,l,j,t WITH simple;
          END IF;
        END $$;
        """
    )
    conn = op.get_bind()
    current = conn.exec_driver_sql(
        """
        SELECT pg_get_expr(d.adbin, d.adrelid)
        FROM pg_attrdef d
        JOIN pg_attribute a ON a.attrelid = d.adrelid AND a.attnum = d.adnum
        WHERE a.attrelid = 'memories'::regclass AND a.attname = 'search_vector'
        """
    ).scalar()
    if current is None or "chinese" not in current:
        _rebuild_search_vector(_ZH_EXPR)


def downgrade() -> None:
    _rebuild_search_vector(_SIMPLE_EXPR)
    op.execute("DROP TEXT SEARCH CONFIGURATION IF EXISTS chinese")
