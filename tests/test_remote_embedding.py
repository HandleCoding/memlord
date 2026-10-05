"""Remote embedding provider + local fallback."""

from __future__ import annotations

from unittest.mock import patch

import httpx
import pytest
from sqlalchemy import select

from memlord.config import LOCAL_EMBEDDING_DIM, REMOTE_EMBEDDING_DIM, settings
from memlord.dao import MemoryDao
from memlord.embeddings import embed_pair, embed_remote
from memlord.models import Memory
from memlord.schemas import MemoryType

_RealAsyncClient = httpx.AsyncClient


def _enable_remote(monkeypatch, *, dim: int = REMOTE_EMBEDDING_DIM) -> None:
    monkeypatch.setattr(settings, "embedding_provider", "openai_compatible")
    monkeypatch.setattr(settings, "embedding_base_url", "https://api.example.com/v1")
    monkeypatch.setattr(settings, "embedding_api_key", "sk-test-not-real")
    monkeypatch.setattr(settings, "embedding_model", "BAAI/bge-m3")
    monkeypatch.setattr(settings, "embedding_dim", dim)
    monkeypatch.setattr(settings, "embedding_timeout", 5.0)
    monkeypatch.setattr(settings, "embedding_retries", 0)


def _mock_client(handler):
    transport = httpx.MockTransport(handler)

    def factory(*args, **kwargs):
        kwargs = dict(kwargs)
        kwargs["transport"] = transport
        return _RealAsyncClient(*args, **kwargs)

    return factory


@pytest.mark.asyncio
async def test_embed_pair_local_only_when_unconfigured():
    assert settings.embedding_provider == "local"
    assert not settings.remote_embedding_configured
    pair = await embed_pair("中文语义测试 hello")
    assert len(pair.local) == LOCAL_EMBEDDING_DIM
    assert pair.remote is None
    assert not pair.used_remote


@pytest.mark.asyncio
async def test_embed_remote_success(monkeypatch):
    _enable_remote(monkeypatch)
    vec = [0.01] * REMOTE_EMBEDDING_DIM

    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url).endswith("/embeddings")
        assert request.headers.get("Authorization") == "Bearer sk-test-not-real"
        assert b"BAAI/bge-m3" in request.content
        return httpx.Response(200, json={"data": [{"embedding": vec, "index": 0}]})

    with patch("memlord.embeddings.httpx.AsyncClient", _mock_client(handler)):
        out = await embed_remote("北京购房预算")
    assert len(out) == REMOTE_EMBEDDING_DIM
    # L2-normalized
    assert abs(sum(x * x for x in out) - 1.0) < 1e-3


@pytest.mark.asyncio
async def test_embed_pair_falls_back_on_remote_error(monkeypatch):
    _enable_remote(monkeypatch)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={"error": "busy"})

    with patch("memlord.embeddings.httpx.AsyncClient", _mock_client(handler)):
        pair = await embed_pair("fallback please")
    assert len(pair.local) == LOCAL_EMBEDDING_DIM
    assert pair.remote is None


@pytest.mark.asyncio
async def test_embed_remote_dim_mismatch(monkeypatch):
    _enable_remote(monkeypatch)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": [{"embedding": [0.1] * 8}]})

    with patch("memlord.embeddings.httpx.AsyncClient", _mock_client(handler)):
        with pytest.raises(RuntimeError, match="dim mismatch"):
            await embed_remote("x")


@pytest.mark.asyncio
async def test_store_writes_remote_when_available(session, user_id, workspace_id, monkeypatch):
    _enable_remote(monkeypatch)
    remote_vec = [0.02] * REMOTE_EMBEDDING_DIM

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": [{"embedding": remote_vec}]})

    with patch("memlord.embeddings.httpx.AsyncClient", _mock_client(handler)):
        mid, created = await MemoryDao(session, user_id).create(
            content="硅基流动 bge-m3 测试记忆",
            memory_type=MemoryType.fact,
            metadata={},
            tags=set(),
            name="remote-embed-smoke",
            workspace_id=workspace_id,
            force=True,
        )
    assert created
    row = (
        await session.execute(
            select(Memory.embedding, Memory.embedding_remote).where(Memory.id == mid)
        )
    ).one()
    assert row.embedding is not None
    assert len(list(row.embedding)) == LOCAL_EMBEDDING_DIM
    assert row.embedding_remote is not None
    assert len(list(row.embedding_remote)) == REMOTE_EMBEDDING_DIM


@pytest.mark.asyncio
async def test_store_local_only_when_remote_fails(session, user_id, workspace_id, monkeypatch):
    _enable_remote(monkeypatch)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="boom")

    with patch("memlord.embeddings.httpx.AsyncClient", _mock_client(handler)):
        mid, created = await MemoryDao(session, user_id).create(
            content="远端挂了仍应写入本地向量",
            memory_type=MemoryType.fact,
            metadata={},
            tags=set(),
            name="remote-fail-local-ok",
            workspace_id=workspace_id,
            force=True,
        )
    assert created
    row = (
        await session.execute(
            select(Memory.embedding, Memory.embedding_remote).where(Memory.id == mid)
        )
    ).one()
    assert row.embedding is not None
    assert row.embedding_remote is None
