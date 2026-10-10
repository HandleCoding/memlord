import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from memlord.dao import MemoryDao
from memlord.models import Memory
from memlord.models.memory import content_sha256
from memlord.schemas import MemoryType

# ~9KB UTF-8: far beyond the ~2704-byte btree row limit that broke
# UNIQUE(content, workspace_id).
LONG = "记忆内容超长测试。" * 400


async def _create(dao, workspace_id, content, name):
    return await dao.create(
        content=content,
        memory_type=MemoryType.fact,
        metadata={"source": "test"},
        tags=set(),
        name=name,
        workspace_id=workspace_id,
        policy_version=1,
    )


async def test_long_content_store_update_idempotent(session, user_id, workspace_id):
    dao = MemoryDao(session, user_id)
    mid, created = await _create(dao, workspace_id, LONG, "long")
    assert created is True
    stored = await session.scalar(select(Memory.content_hash).where(Memory.id == mid))
    assert stored == content_sha256(LONG)

    mid2, created2 = await _create(dao, workspace_id, LONG, "long again")
    assert (mid2, created2) == (mid, False)

    longer = LONG + "补充。"
    _, _, revision = await dao.update(
        id=mid,
        workspace_id=workspace_id,
        content=longer,
        policy_version=1,
        expected_revision=1,
    )
    assert revision == 2
    stored = await session.scalar(select(Memory.content_hash).where(Memory.id == mid))
    assert stored == content_sha256(longer)


async def test_update_to_duplicate_content_rejected(session, user_id, workspace_id):
    dao = MemoryDao(session, user_id)
    await _create(dao, workspace_id, LONG, "a")
    mid_b, _ = await _create(dao, workspace_id, "完全不同的另一条内容", "b")
    with pytest.raises(IntegrityError):
        await dao.update(
            id=mid_b,
            workspace_id=workspace_id,
            content=LONG,
            policy_version=1,
            expected_revision=1,
        )
