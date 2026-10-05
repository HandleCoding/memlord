from fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import Field
from sqlalchemy.ext.asyncio import AsyncSession

from memlord.auth import MCPUserDep
from memlord.dao import PolicyDao
from memlord.dao.workspace import WorkspaceDao
from memlord.db import MCPSessionDep
from memlord.schemas import PolicyInfo

mcp = FastMCP()


@mcp.tool(
    output_schema=PolicyInfo.model_json_schema(),
    annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False),
)
async def get_memory_policy(
    workspace: str | None = Field(
        None, description="Workspace name. Omit for your personal workspace."
    ),
    s: AsyncSession = MCPSessionDep,  # type: ignore[assignment]
    uid: int = MCPUserDep,  # type: ignore[assignment]
) -> PolicyInfo:
    """Read the workspace's memory-usage policy. Call this before writing memories.

    Follow the rules in `body`, and pass `version` as policy_version to
    store_memory / update_memory / delete_memory in that workspace. When the
    policy changes its version increases and writes with the old one are rejected.
    The policy can only be changed by a human in the web UI.
    """
    ws_dao = WorkspaceDao(s, uid)
    if workspace is not None:
        ws = await ws_dao.get_by_name(workspace)
        if ws is None:
            raise ValueError(
                f"Workspace '{workspace}' not found or you are not a member. "
                "Use list_workspaces() to see available workspaces."
            )
    else:
        ws = await ws_dao.get_personal()
    return await PolicyDao(s, uid).get(ws.id)
