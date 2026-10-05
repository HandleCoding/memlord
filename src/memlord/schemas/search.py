from .base import Schema
from .memory_type import MemoryType


class SearchResult(Schema):
    id: int
    name: str
    content: str
    memory_type: MemoryType
    rrf_score: float
    vec_similarity: float | None
    workspace: str | None = None
    workspace_id: int | None = None
    snippet: str | None = None
    # Optional fusion breakdown (populated when MEMLORD_SEARCH_DEBUG=true)
    score_fts: float | None = None
    score_vec: float | None = None
    score_name: float | None = None
