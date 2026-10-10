"""memories.content_hash: enforce content uniqueness on sha256, not raw text

Revision ID: c3d4e5f6a7b8
Revises: b1c2d3e4f5a6
Create Date: 2026-10-10 19:30:00.000000

UNIQUE(content, workspace_id) puts the whole text into a btree row, which
Postgres caps at ~2704 bytes, so long memories failed to insert/update.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c3d4e5f6a7b8"
down_revision: Union[str, Sequence[str], None] = "b1c2d3e4f5a6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("memories", sa.Column("content_hash", sa.LargeBinary(32), nullable=True))
    # sha256() is built in since PG11; must match memlord.models.memory.content_sha256.
    op.execute("UPDATE memories SET content_hash = sha256(convert_to(content, 'UTF8'))")
    op.alter_column("memories", "content_hash", nullable=False)
    op.drop_constraint("uq_memories_content_workspace", "memories", type_="unique")
    op.create_unique_constraint(
        "uq_memories_content_hash_workspace", "memories", ["workspace_id", "content_hash"]
    )


def downgrade() -> None:
    op.drop_constraint("uq_memories_content_hash_workspace", "memories", type_="unique")
    # Fails if any content is too long for a btree row; shorten those first.
    op.create_unique_constraint(
        "uq_memories_content_workspace", "memories", ["content", "workspace_id"]
    )
    op.drop_column("memories", "content_hash")
