"""Workspace memory policy (P0): policy_version gate, revision CAS, policy management."""

import asyncio
import uuid

import pytest
from fastmcp.exceptions import ToolError
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from memlord.auth import hash_password
from memlord.config import settings
from memlord.dao import MemoryDao, PolicyDao, PolicyError
from memlord.dao.api_key import ApiKeyDao
from memlord.dao.user import UserDao
from memlord.dao.workspace import WorkspaceDao
from memlord.models import Memory, User
from memlord.policy_defaults import DEFAULT_POLICY_BODY
from memlord.schemas import MemoryType
from memlord.schemas.workspace import WorkspaceRole

_SRC = {"source": "test"}


async def _create(s, uid, ws, content="policy memory", **kwargs):
    kwargs.setdefault("metadata", dict(_SRC))
    kwargs.setdefault("policy_version", 1)
    mid, _ = await MemoryDao(s, uid).create(
        content=content,
        memory_type=MemoryType.fact,
        tags=set(),
        name=content,
        workspace_id=ws,
        force=True,
        **kwargs,
    )
    return mid


# ── seeding / reading ────────────────────────────────────────────────────────


async def test_new_workspaces_get_default_policy(session, user_id, workspace_id):
    dao = PolicyDao(session, user_id)
    personal = await dao.get(workspace_id)
    assert personal.version == 1
    assert personal.body == DEFAULT_POLICY_BODY
    assert personal.structured.forbid_credentials is True
    assert personal.enforced is True

    shared = await WorkspaceDao(session, user_id).create(name="team")
    assert (await dao.get(shared.id)).version == 1


async def test_get_memory_policy_tool(mcp_client, session, user_id):
    r = await mcp_client.call_tool("get_memory_policy", {})
    assert r.data.version == 1
    assert "记忆使用规范" in r.data.body

    await WorkspaceDao(session, user_id).create(name="proj")
    r = await mcp_client.call_tool("get_memory_policy", {"workspace": "proj"})
    assert r.data.workspace == "proj"

    with pytest.raises(ToolError):
        await mcp_client.call_tool("get_memory_policy", {"workspace": "nope"})


async def test_policy_is_not_a_memory(mcp_client):
    """The policy text never shows up in memory search or listing."""
    r = await mcp_client.call_tool("retrieve_memory", {"query": "记忆使用规范 凭据 删除"})
    assert r.data == []
    r = await mcp_client.call_tool("list_memories", {})
    assert r.data.total == 0
    r = await mcp_client.call_tool("search_by_tag", {"tags": ["todo"]})
    assert r.data.items == []


# ── policy_version gate (enforced) ───────────────────────────────────────────


async def test_store_requires_policy_version_and_source(session, user_id, workspace_id):
    dao = MemoryDao(session, user_id)
    with pytest.raises(PolicyError) as e:
        await _create(session, user_id, workspace_id, policy_version=None)
    assert e.value.code == "policy_version_required"

    with pytest.raises(PolicyError) as e:
        await _create(session, user_id, workspace_id, policy_version=7)
    assert e.value.code == "policy_version_mismatch"

    with pytest.raises(PolicyError) as e:
        await _create(session, user_id, workspace_id, metadata={})
    assert e.value.code == "source_required"

    with pytest.raises(PolicyError) as e:
        await _create(session, user_id, workspace_id, metadata={"source": "  "})
    assert e.value.code == "source_required"

    mid = await _create(session, user_id, workspace_id)
    item = await dao.get(id=mid, workspace_id=workspace_id)
    assert item is not None and item.revision == 1


async def test_old_policy_version_rejected_after_bump(session, user_id, workspace_id):
    await PolicyDao(session, user_id).update(workspace_id, "new rules", expected_version=1)
    with pytest.raises(PolicyError, match="policy_version_mismatch"):
        await _create(session, user_id, workspace_id, policy_version=1)
    await _create(session, user_id, workspace_id, policy_version=2)


async def test_mcp_errors_are_machine_readable(mcp_client):
    base = {"content": "x", "memory_type": MemoryType.fact, "name": "x"}
    with pytest.raises(ToolError, match="policy_version_required"):
        await mcp_client.call_tool("store_memory", {**base, "source": "t"})
    with pytest.raises(ToolError, match="policy_version_mismatch"):
        await mcp_client.call_tool("store_memory", {**base, "source": "t", "policy_version": 9})
    with pytest.raises(ToolError, match="source_required"):
        await mcp_client.call_tool("store_memory", {**base, "policy_version": 1})

    r = await mcp_client.call_tool("store_memory", {**base, "source": "t", "policy_version": 1})
    assert r.data.revision == 1

    with pytest.raises(ToolError, match="expected_revision_required"):
        await mcp_client.call_tool(
            "update_memory",
            {"name": "x", "memory_type": MemoryType.fact, "content": "y", "policy_version": 1},
        )
    with pytest.raises(ToolError, match="revision_conflict"):
        await mcp_client.call_tool(
            "update_memory",
            {
                "name": "x",
                "memory_type": MemoryType.fact,
                "content": "y",
                "policy_version": 1,
                "expected_revision": 5,
            },
        )
    with pytest.raises(ToolError, match="expected_revision_required"):
        await mcp_client.call_tool("delete_memory", {"name": "x", "policy_version": 1})
    with pytest.raises(ToolError, match="revision_conflict"):
        await mcp_client.call_tool(
            "delete_memory", {"name": "x", "policy_version": 1, "expected_revision": 5}
        )
    r = await mcp_client.call_tool("get_memory", {"name": "x"})
    assert r.data.revision == 1
    await mcp_client.call_tool(
        "delete_memory", {"name": "x", "policy_version": 1, "expected_revision": 1}
    )


# ── revision CAS ─────────────────────────────────────────────────────────────


async def test_update_and_delete_cas(session, user_id, workspace_id):
    dao = MemoryDao(session, user_id)
    mid = await _create(session, user_id, workspace_id)

    with pytest.raises(PolicyError) as e:
        await dao.update(id=mid, workspace_id=workspace_id, content="a", policy_version=1)
    assert e.value.code == "expected_revision_required"

    _, _, rev = await dao.update(
        id=mid, workspace_id=workspace_id, content="a", policy_version=1, expected_revision=1
    )
    assert rev == 2

    # stale revision: no silent overwrite
    with pytest.raises(PolicyError, match="revision_conflict"):
        await dao.update(
            id=mid, workspace_id=workspace_id, content="b", policy_version=1, expected_revision=1
        )
    item = await dao.get(id=mid, workspace_id=workspace_id)
    assert item is not None and item.content == "a" and item.revision == 2

    with pytest.raises(PolicyError, match="expected_revision_required"):
        await dao.delete(mid, workspace_id, policy_version=1)
    with pytest.raises(PolicyError, match="revision_conflict"):
        await dao.delete(mid, workspace_id, policy_version=1, expected_revision=1)
    assert await dao.get(id=mid, workspace_id=workspace_id) is not None

    await dao.delete(mid, workspace_id, policy_version=1, expected_revision=2)
    assert await dao.get(id=mid, workspace_id=workspace_id) is None


async def test_cross_workspace_move_refused(session, user_id, workspace_id):
    other = await WorkspaceDao(session, user_id).create(name="other")
    mid = await _create(session, user_id, workspace_id)
    with pytest.raises(PolicyError, match="cross_workspace_move_disabled"):
        await MemoryDao(session, user_id).move(mid, workspace_id, other.id, expected_revision=1)
    item = await MemoryDao(session, user_id).get(id=mid, workspace_id=workspace_id)
    assert item is not None


# ── policy management ────────────────────────────────────────────────────────


async def test_mcp_cannot_change_policy(mcp_client):
    names = {t.name for t in await mcp_client.list_tools()}
    assert "get_memory_policy" in names
    assert not any("policy" in n and n != "get_memory_policy" for n in names)


async def test_only_owner_can_change_policy(session, user_id):
    ws = await WorkspaceDao(session, user_id).create(name="shared")
    editor = await UserDao(session).create(
        email="editor@example.com", display_name="Editor", hashed_password=hash_password("pw")
    )
    await WorkspaceDao(session, user_id).add_member(ws.id, editor.id, role=WorkspaceRole.editor)
    with pytest.raises(PermissionError):
        await PolicyDao(session, editor.id).update(ws.id, "editor rules", expected_version=1)
    # but the editor can read it
    assert (await PolicyDao(session, editor.id).get(ws.id)).version == 1


async def test_policy_update_concurrent_admins(session, user_id, workspace_id):
    dao = PolicyDao(session, user_id)
    assert (await dao.update(workspace_id, "v2", expected_version=1)).version == 2
    with pytest.raises(PolicyError, match="policy_version_mismatch"):
        await dao.update(workspace_id, "lost update", expected_version=1)


async def test_rest_policy_update_needs_password(api_client, session, user_id, workspace_id):
    url = f"/api/workspaces/{workspace_id}/policy"
    r = await api_client.get(url)
    assert r.status_code == 200 and r.json()["version"] == 1

    payload = {"body": "我的新规则", "expected_version": 1, "current_password": "wrong"}
    r = await api_client.put(url, json=payload)
    assert r.status_code == 403

    r = await api_client.put(url, json={**payload, "current_password": "test-password"})
    assert r.status_code == 200
    assert r.json()["version"] == 2 and r.json()["body"] == "我的新规则"

    r = await api_client.put(url, json={**payload, "current_password": "test-password"})
    assert r.status_code == 409
    assert r.json()["code"] == "policy_version_mismatch"


async def test_rest_rejects_agent_credentials(api_client, session, user_id, workspace_id):
    """An MCP API key (what agents hold) does not authenticate /api at all."""
    raw = await ApiKeyDao(session).create(user_id, "agent")
    api_client.cookies.clear()
    r = await api_client.put(
        f"/api/workspaces/{workspace_id}/policy",
        json={"body": "x", "expected_version": 1, "current_password": "test-password"},
        headers={"Authorization": f"Bearer {raw}"},
    )
    assert r.status_code == 307  # redirected to the login page
    assert (await PolicyDao(session, user_id).get(workspace_id)).version == 1


async def test_rest_memory_writes(api_client, session, user_id, workspace_id):
    mid = await _create(session, user_id, workspace_id)
    url = f"/api/memories/{workspace_id}/{mid}"

    r = await api_client.post("/api/memories", json={})
    item = r.json()["items"][0]
    assert item["revision"] == 1 and item["policy_version"] == 1

    r = await api_client.put(url, json={"memory_type": "fact", "content": "c2"})
    assert r.status_code == 400 and r.json()["code"] == "policy_version_required"
    r = await api_client.put(
        url, json={"memory_type": "fact", "content": "c2", "policy_version": 3}
    )
    assert r.status_code == 409 and r.json()["code"] == "policy_version_mismatch"
    r = await api_client.put(
        url,
        json={"memory_type": "fact", "content": "c2", "policy_version": 1, "expected_revision": 9},
    )
    assert r.status_code == 409 and r.json()["code"] == "revision_conflict"
    r = await api_client.put(
        url,
        json={"memory_type": "fact", "content": "c2", "policy_version": 1, "expected_revision": 1},
    )
    assert r.status_code == 200 and r.json()["revision"] == 2

    other = await WorkspaceDao(session, user_id).create(name="dest")
    r = await api_client.post(
        f"{url}/move", json={"to_workspace_id": other.id, "expected_revision": 2}
    )
    assert r.status_code == 400 and r.json()["code"] == "cross_workspace_move_disabled"

    r = await api_client.delete(url, params={"policy_version": 1})
    assert r.status_code == 400 and r.json()["code"] == "expected_revision_required"
    r = await api_client.delete(url, params={"policy_version": 1, "expected_revision": 1})
    assert r.status_code == 409
    r = await api_client.delete(url, params={"policy_version": 1, "expected_revision": 2})
    assert r.status_code == 204


# ── transition mode (MEMLORD_POLICY_ENFORCE=0) ───────────────────────────────


async def test_transition_mode_lets_legacy_clients_through(mcp_client, monkeypatch):
    monkeypatch.setattr(settings, "policy_enforce", False)
    base = {"content": "legacy", "memory_type": MemoryType.fact, "name": "legacy"}
    # no policy_version / source: not rejected by the schema, reaches the DAO, allowed
    r = await mcp_client.call_tool("store_memory", base)
    assert r.data.created and r.data.revision == 1
    r = await mcp_client.call_tool(
        "update_memory", {"name": "legacy", "memory_type": MemoryType.fact, "content": "legacy2"}
    )
    assert r.data.revision == 2
    # values that ARE sent are still checked
    with pytest.raises(ToolError, match="policy_version_mismatch"):
        await mcp_client.call_tool("delete_memory", {"name": "legacy", "policy_version": 4})
    with pytest.raises(ToolError, match="revision_conflict"):
        await mcp_client.call_tool("delete_memory", {"name": "legacy", "expected_revision": 1})
    await mcp_client.call_tool("delete_memory", {"name": "legacy"})


async def test_transition_mode_rest(api_client, session, user_id, workspace_id, monkeypatch):
    monkeypatch.setattr(settings, "policy_enforce", False)
    mid = await _create(session, user_id, workspace_id, policy_version=None, metadata={})
    r = await api_client.put(
        f"/api/memories/{workspace_id}/{mid}", json={"memory_type": "fact", "content": "z"}
    )
    assert r.status_code == 200 and r.json()["revision"] == 2
    r = await api_client.delete(f"/api/memories/{workspace_id}/{mid}")
    assert r.status_code == 204


# ── real concurrency (separate connections, committed transactions) ──────────


@pytest.fixture
async def committed(test_db_url):
    """A committed user + personal workspace visible to independent connections."""
    engine = create_async_engine(test_db_url)
    sm = async_sessionmaker(engine, expire_on_commit=False)
    async with sm() as s, s.begin():
        user = await UserDao(s).create(
            email=f"conc-{uuid.uuid4().hex[:8]}@example.com",
            display_name="Concurrency",
            hashed_password=hash_password("pw"),
        )
        ws = (await WorkspaceDao(s, user.id).get_personal()).id
    yield sm, user.id, ws
    async with sm() as s, s.begin():
        await s.execute(delete(User).where(User.id == user.id))
    await engine.dispose()


async def _store_tx(sm, uid, ws, content, policy_version):
    async with sm() as s, s.begin():
        return await _create(s, uid, ws, content, policy_version=policy_version)


async def _bump_tx(sm, uid, ws, expected_version):
    async with sm() as s, s.begin():
        return await PolicyDao(s, uid).update(ws, "bumped", expected_version=expected_version)


async def _update_tx(sm, uid, ws, mid, content, expected_revision):
    async with sm() as s, s.begin():
        return await MemoryDao(s, uid).update(
            id=mid,
            workspace_id=ws,
            content=content,
            policy_version=1,
            expected_revision=expected_revision,
        )


async def _blocked(task: asyncio.Task) -> bool:
    await asyncio.sleep(0.5)
    return not task.done()


async def test_policy_bump_waits_for_write_paused_after_check(committed):
    """Write passes the policy check, pauses; a concurrent bump must wait for it."""
    sm, uid, ws = committed
    async with sm() as writer, writer.begin():
        await PolicyDao(writer, uid).check_write(ws, 1)  # validated v1, lock held
        bump = asyncio.create_task(_bump_tx(sm, uid, ws, 1))
        assert await _blocked(bump), "policy bump committed while a v1 write was in flight"
        await _create(writer, uid, ws, "written under v1", policy_version=1)
    # writer committed first; only now may the bump go through
    assert (await asyncio.wait_for(bump, 10)).version == 2
    async with sm() as s:
        assert await s.scalar(select(Memory.id).where(Memory.name == "written under v1"))
    with pytest.raises(PolicyError, match="policy_version_mismatch"):
        await _store_tx(sm, uid, ws, "late v1 write", 1)


async def test_write_with_old_version_fails_when_bump_wins(committed):
    """Bump holds the row first; the v1 write waits, then fails after the bump commits."""
    sm, uid, ws = committed
    async with sm() as admin, admin.begin():
        await PolicyDao(admin, uid).update(ws, "v2", expected_version=1)
        write = asyncio.create_task(_store_tx(sm, uid, ws, "racing v1 write", 1))
        assert await _blocked(write)
    with pytest.raises(PolicyError, match="policy_version_mismatch"):
        await asyncio.wait_for(write, 10)
    async with sm() as s:
        assert await s.scalar(select(Memory.id).where(Memory.name == "racing v1 write")) is None


async def test_concurrent_updates_only_one_wins(committed):
    sm, uid, ws = committed
    mid = await _store_tx(sm, uid, ws, "cas target", 1)
    async with sm() as a, a.begin():
        await MemoryDao(a, uid).update(
            id=mid, workspace_id=ws, content="A wins", policy_version=1, expected_revision=1
        )
        b = asyncio.create_task(_update_tx(sm, uid, ws, mid, "B loses", 1))
        assert await _blocked(b)  # B's conditional UPDATE waits on A's row lock
    with pytest.raises(PolicyError, match="revision_conflict"):
        await asyncio.wait_for(b, 10)
    async with sm() as s:
        row = (
            await s.execute(select(Memory.content, Memory.revision).where(Memory.id == mid))
        ).one()
    assert row.content == "A wins" and row.revision == 2
