from datetime import datetime

from ..base import Schema
from ..memory_type import MemoryType


class UpdateMemoryRequest(Schema):
    content: str | None = None
    name: str | None = None
    memory_type: MemoryType | None = None
    tags: set[str] | None = None
    metadata: dict | None = None
    expires_at: datetime | None = None
    # Policy P0: optional at the schema level so MEMLORD_POLICY_ENFORCE=0 still
    # reaches the DAO; the DAO decides whether a missing value is an error.
    policy_version: int | None = None
    expected_revision: int | None = None
