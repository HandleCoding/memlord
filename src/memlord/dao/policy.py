import logging

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from memlord.config import settings
from memlord.dao.workspace import WorkspaceDao
from memlord.models.workspace import Workspace
from memlord.models.workspace_policy import WorkspacePolicy
from memlord.schemas.policy import PolicyInfo, PolicyStructured
from memlord.schemas.workspace import WorkspaceRole
from memlord.utils.dt import utcnow

logger = logging.getLogger(__name__)


class PolicyError(Exception):
    """A memory write violated the workspace policy protocol.

    `code` is stable and machine-readable; str(exc) is "<code>: <message>".
    Conflict codes (stale policy_version / revision) map to HTTP 409, the rest to 400.
    """

    CONFLICT_CODES = frozenset({"policy_version_mismatch", "revision_conflict"})

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code

    @property
    def is_conflict(self) -> bool:
        return self.code in self.CONFLICT_CODES


def require_or_log(present: bool, code: str, message: str) -> None:
    """Raise PolicyError when enforcement is on; otherwise only log (transition mode)."""
    if present:
        return
    if settings.policy_enforce:
        raise PolicyError(code, message)
    logger.warning("policy not enforced, allowing write: %s: %s", code, message)


class PolicyDao:
    def __init__(self, s: AsyncSession, uid: int) -> None:
        self._s = s
        self._uid = uid
        self._ws_dao = WorkspaceDao(s, uid)

    async def get(self, workspace_id: int) -> PolicyInfo:
        if not await self._ws_dao.can_read(workspace_id):
            raise ValueError(f"No read access to workspace {workspace_id}")
        row = (
            (
                await self._s.execute(
                    select(
                        Workspace.name.label("workspace"),
                        WorkspacePolicy.version,
                        WorkspacePolicy.body,
                        WorkspacePolicy.structured,
                        WorkspacePolicy.updated_at,
                    )
                    .join(Workspace, Workspace.id == WorkspacePolicy.workspace_id)
                    .where(WorkspacePolicy.workspace_id == workspace_id)
                )
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            raise ValueError(f"Policy not found for workspace {workspace_id}")
        return PolicyInfo(
            workspace=row["workspace"],
            version=row["version"],
            body=row["body"],
            structured=PolicyStructured.model_validate(row["structured"]),
            enforced=settings.policy_enforce,
            updated_at=row["updated_at"],
        )

    async def get_versions(self, workspace_ids: list[int]) -> dict[int, int]:
        """Current policy version per workspace (plain read, no lock)."""
        if not workspace_ids:
            return {}
        rows = await self._s.execute(
            select(WorkspacePolicy.workspace_id, WorkspacePolicy.version).where(
                WorkspacePolicy.workspace_id.in_(workspace_ids)
            )
        )
        return {row.workspace_id: row.version for row in rows.fetchall()}

    async def check_write(self, workspace_id: int, policy_version: int | None) -> int:
        """Lock the workspace policy row FOR SHARE and validate policy_version.

        Must run inside the memory write's transaction: the shared lock is held
        until commit, and policy updates need the row lock, so a version bump
        either waits for this write to commit or commits first and makes this
        check fail. Returns the current version.
        """
        current = await self._s.scalar(
            select(WorkspacePolicy.version)
            .where(WorkspacePolicy.workspace_id == workspace_id)
            .with_for_update(read=True)
        )
        if current is None:
            raise PolicyError("policy_not_found", f"Workspace {workspace_id} has no policy")
        require_or_log(
            policy_version is not None,
            "policy_version_required",
            "Call get_memory_policy and pass its version as policy_version",
        )
        if policy_version is not None and policy_version != current:
            raise PolicyError(
                "policy_version_mismatch",
                f"policy_version {policy_version} is not current; "
                "call get_memory_policy, re-read the rules and retry",
            )
        return current

    async def update(self, workspace_id: int, body: str, expected_version: int) -> PolicyInfo:
        """Replace the policy text and bump its version (compare-and-swap on version).

        Callers must authenticate the policy manager separately (see
        api/workspaces.update_policy); workspace ownership alone is not enough
        because agents acting for the owner share the owner's role.
        """
        if await self._ws_dao.get_role(workspace_id, self._uid) != WorkspaceRole.owner:
            raise PermissionError("Only the workspace owner can change its policy")
        if not body.strip():
            raise ValueError("Policy body must not be empty")
        version = await self._s.scalar(
            update(WorkspacePolicy)
            .where(
                WorkspacePolicy.workspace_id == workspace_id,
                WorkspacePolicy.version == expected_version,
            )
            .values(
                body=body,
                version=WorkspacePolicy.version + 1,
                updated_by=self._uid,
                updated_at=utcnow(),
            )
            .returning(WorkspacePolicy.version)
        )
        if version is None:
            raise PolicyError(
                "policy_version_mismatch",
                f"Policy is no longer at version {expected_version}; reload and retry",
            )
        return await self.get(workspace_id)
