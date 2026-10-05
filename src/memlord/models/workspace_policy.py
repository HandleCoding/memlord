import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from .base import Base


class WorkspacePolicy(Base):
    """Memory-usage policy of a workspace (one row per workspace).

    Not a memory: never returned by search/list, never touched by memory CRUD.
    Memory writes take FOR SHARE on this row; policy updates take the row lock,
    so a version bump cannot interleave with an in-flight write.
    """

    __tablename__ = "workspace_policies"

    workspace_id = sa.Column(
        sa.Integer,
        sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    )
    body = sa.Column(sa.Text, nullable=False)
    version = sa.Column(sa.Integer, nullable=False, server_default="1")
    structured = sa.Column(JSONB, nullable=False, server_default="{}")
    updated_by = sa.Column(
        sa.Integer, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    updated_at = sa.Column(
        sa.DateTime(timezone=False), server_default=sa.func.now(), nullable=False
    )
