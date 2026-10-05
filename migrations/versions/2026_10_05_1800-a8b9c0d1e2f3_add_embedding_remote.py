"""Add optional embedding_remote column (1024-d) for cloud embeddings

Revision ID: a8b9c0d1e2f3
Revises: e7a1c2b3d4f5
Create Date: 2026-10-05 18:00:00.000000

Local embedding (vector 384) remains the source of truth / fallback.
Remote column is nullable; populate via store/update or scripts/reembed.py
after configuring MEMLORD_EMBEDDING_PROVIDER=openai_compatible.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import VECTOR

# revision identifiers, used by Alembic.
revision: str = "a8b9c0d1e2f3"
down_revision: Union[str, Sequence[str], None] = "e7a1c2b3d4f5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

REMOTE_DIM = 1024


def upgrade() -> None:
    op.add_column(
        "memories",
        sa.Column("embedding_remote", VECTOR(REMOTE_DIM), nullable=True),
    )
    op.create_index(
        "ix_memories_embedding_remote",
        "memories",
        ["embedding_remote"],
        unique=False,
        postgresql_using="hnsw",
        postgresql_with={"m": 16, "ef_construction": 64},
        postgresql_ops={"embedding_remote": "vector_cosine_ops"},
    )


def downgrade() -> None:
    op.drop_index("ix_memories_embedding_remote", table_name="memories")
    op.drop_column("memories", "embedding_remote")
