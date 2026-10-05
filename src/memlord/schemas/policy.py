from datetime import UTC, datetime

from pydantic import ConfigDict, Field, NaiveDatetime, field_serializer

from .base import Schema


class PolicyStructured(Schema):
    """Machine-readable summary of the policy.

    These are declarations for clients. Only the write-path checks (policy_version,
    expected_revision, source presence) are enforced by the server, and only when
    MEMLORD_POLICY_ENFORCE is on. forbid_credentials is NOT detected server-side.
    """

    model_config = ConfigDict(extra="ignore")

    require_source_on_store: bool = True
    require_policy_version_on_write: bool = True
    require_expected_revision_on_update: bool = True
    require_expected_revision_on_delete: bool = True
    forbid_credentials: bool = Field(
        default=True,
        description="Rule for agents to follow. The server does not detect or block credentials.",
    )


class PolicyInfo(Schema):
    workspace: str
    version: int = Field(description="Pass back as policy_version on every memory write.")
    body: str
    structured: PolicyStructured
    enforced: bool = Field(
        description="True if the server currently rejects writes missing "
        "policy_version / expected_revision / source; false = transition mode (logged only)."
    )
    updated_at: NaiveDatetime

    @field_serializer("updated_at")
    def serialize_updated_at(self, v: datetime) -> str:
        return v.replace(tzinfo=UTC).isoformat()


class UpdatePolicyRequest(Schema):
    body: str
    expected_version: int
    current_password: str
    totp_code: str | None = None
