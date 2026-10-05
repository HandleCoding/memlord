"""Full MCP tool pipeline: list_workspaces → policy → store → get → update → search → delete."""

import pytest
from fastmcp.exceptions import ToolError

from memlord.dao.workspace import WorkspaceDao
from memlord.schemas import MemoryType


async def test_pipeline(mcp_client, session, user_id):
    # --- list_workspaces (a fresh user has exactly one personal workspace) ---
    r = await mcp_client.call_tool("list_workspaces", {})
    personal = [w for w in r.data if w.is_personal]
    assert len(personal) == 1
    personal_ws = personal[0].name

    # --- policy ---
    r = await mcp_client.call_tool("get_memory_policy", {})
    policy_version = r.data.version
    assert r.data.workspace == personal_ws

    # --- store ---
    r = await mcp_client.call_tool(
        "store_memory",
        {
            "content": "pipeline test memory",
            "memory_type": MemoryType.fact,
            "tags": ["pipeline", "test"],
            "name": "pipeline-test",
            "source": "test",
            "policy_version": policy_version,
        },
    )
    assert r.data.created is True
    assert r.data.revision == 1
    mid = r.data.name

    # --- get ---
    r = await mcp_client.call_tool("get_memory", {"name": mid})
    assert r.data.content == "pipeline test memory"
    assert r.data.memory_type == MemoryType.fact
    assert sorted(r.data.tags) == ["pipeline", "test"]
    assert r.data.revision == 1

    # --- update ---
    r = await mcp_client.call_tool(
        "update_memory",
        {
            "name": mid,
            "memory_type": MemoryType.fact,
            "content": "updated pipeline memory",
            "tags": ["pipeline", "updated"],
            "policy_version": policy_version,
            "expected_revision": 1,
        },
    )
    assert r.data.name == mid
    assert r.data.revision == 2

    r = await mcp_client.call_tool("get_memory", {"name": mid})
    assert r.data.content == "updated pipeline memory"
    assert sorted(r.data.tags) == ["pipeline", "updated"]

    # --- retrieve ---
    r = await mcp_client.call_tool(
        "retrieve_memory",
        {"query": "updated pipeline memory", "limit": 10},
    )
    names = [m.name for m in r.data]
    assert mid in names

    # --- list_memories ---
    r = await mcp_client.call_tool("list_memories", {"page": 1, "page_size": 50})
    names = [m.name for m in r.data.items]
    assert mid in names
    assert next(m for m in r.data.items if m.name == mid).revision == 2

    # --- search by tag ---
    r = await mcp_client.call_tool(
        "search_by_tag", {"tags": ["pipeline", "updated"], "operation": "AND"}
    )
    ids = [m.name for m in r.data.items]
    assert mid in ids

    # --- move to another workspace: refused while the policy is enforced ---
    target_ws = await WorkspaceDao(session, user_id).create(name="pipeline-target")
    with pytest.raises(ToolError, match="cross_workspace_move_disabled"):
        await mcp_client.call_tool(
            "move_memory",
            {"name": mid, "to_workspace": target_ws.name, "from_workspace": personal_ws},
        )

    # --- delete ---
    await mcp_client.call_tool(
        "delete_memory",
        {"name": mid, "policy_version": policy_version, "expected_revision": 2},
    )

    with pytest.raises(ToolError):
        await mcp_client.call_tool("get_memory", {"name": mid})
