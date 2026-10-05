from ..base import Schema


class StoreResult(Schema):
    name: str
    created: bool
    revision: int | None = None
