import hashlib

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR

from memlord.config import REMOTE_EMBEDDING_DIM

from .base import Base


class Memory(Base):
    __tablename__ = "memories"

    id = sa.Column(sa.Integer, primary_key=True, autoincrement=True)
    name = sa.Column(sa.Text, nullable=False)
    content = sa.Column(sa.Text, nullable=False)
    # sha256 of the UTF-8 content. Uniqueness is enforced on this instead of the
    # raw text: a btree row is capped at ~2.7KB, so long content cannot be indexed.
    content_hash = sa.Column(sa.LargeBinary(32), nullable=False)
    created_by = sa.Column(
        sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    memory_type = sa.Column(sa.String(50), nullable=False)
    extra_data = sa.Column("metadata", JSONB, nullable=False, server_default="{}")
    created_at = sa.Column(
        sa.DateTime(timezone=False), server_default=sa.func.now(), nullable=False
    )
    expires_at = sa.Column(sa.DateTime(timezone=False), nullable=True)
    # Optimistic-lock counter: bumped by every successful update/move; writers
    # pass it back as expected_revision (compare-and-swap in the UPDATE WHERE).
    revision = sa.Column(sa.Integer, nullable=False, server_default="1")
    workspace_id = sa.Column(
        sa.Integer,
        sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
    )
    # Always populated: local ONNX paraphrase-multilingual-MiniLM-L12-v2 (384-d).
    embedding = sa.Column(Vector(384), nullable=True)
    # Optional remote embedding (e.g. BAAI/bge-m3 via SiliconFlow). Dimension is
    # fixed at REMOTE_EMBEDDING_DIM; changing it requires a new migration.
    embedding_remote = sa.Column(Vector(REMOTE_EMBEDDING_DIM), nullable=True)
    search_vector = sa.Column(
        TSVECTOR,
        sa.Computed(
            "setweight(to_tsvector('chinese'::regconfig, name), 'A') || "
            "setweight(to_tsvector('chinese'::regconfig, content), 'B')",
            persisted=True,
        ),
        nullable=False,
    )

    __table_args__ = (
        sa.UniqueConstraint(
            "workspace_id", "content_hash", name="uq_memories_content_hash_workspace"
        ),
        sa.UniqueConstraint("name", "workspace_id", name="uq_memories_name_workspace"),
        sa.Index("ix_memories_search_vector", "search_vector", postgresql_using="gin"),
        sa.Index(
            "ix_memories_embedding",
            "embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
        sa.Index(
            "ix_memories_embedding_remote",
            "embedding_remote",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embedding_remote": "vector_cosine_ops"},
        ),
    )


def content_sha256(content: str) -> bytes:
    """Digest stored in memories.content_hash (matches SQL sha256(convert_to(content, 'UTF8')))."""
    return hashlib.sha256(content.encode("utf-8")).digest()
