import pytest

from memlord.dao import MemoryDao
from memlord.schemas import MemoryType


async def test_crud(session, user_id, workspace_id):
    dao = MemoryDao(session, user_id)

    # create
    mid, created = await dao.create(
        content="hello world",
        memory_type=MemoryType.fact,
        metadata={"k": "v", "source": "test"},
        tags={"foo", "bar"},
        name="hello world",
        workspace_id=workspace_id,
        policy_version=1,
    )
    assert created is True
    assert mid > 0

    # idempotent create (same user, same content, same workspace)
    mid2, created2 = await dao.create(
        content="hello world",
        memory_type=MemoryType.fact,
        metadata={"source": "test"},
        tags=set(),
        name="hello world",
        workspace_id=workspace_id,
        policy_version=1,
    )
    assert created2 is False
    assert mid2 == mid

    # fetch_tags
    tags = await dao.fetch_tags([mid])
    assert sorted(tags[mid]) == ["bar", "foo"]

    # fetch_metadata
    meta = await dao.fetch_metadata([mid])
    assert meta[mid][0] == {"k": "v", "source": "test"}

    # update content + tags (CAS on revision)
    _, _, revision = await dao.update(
        id=mid,
        workspace_id=workspace_id,
        content="updated content",
        tags={"baz"},
        policy_version=1,
        expected_revision=1,
    )
    assert revision == 2
    tags2 = await dao.fetch_tags([mid])
    assert tags2[mid] == {"baz"}

    # delete
    await dao.delete(mid, workspace_id=workspace_id, policy_version=1, expected_revision=2)
    with pytest.raises(ValueError):
        await dao.delete(mid, workspace_id=workspace_id, policy_version=1, expected_revision=2)
