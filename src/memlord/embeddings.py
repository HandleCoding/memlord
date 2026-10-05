"""Local ONNX embeddings + optional OpenAI-compatible remote embeddings.

Local paraphrase-multilingual-MiniLM-L12-v2 (384-d) is always available.
When MEMLORD_EMBEDDING_PROVIDER=openai_compatible is configured, callers that
need both vectors use ``embed_pair``: remote is attempted first for the remote
slot, and failures fall back to local-only (remote=None).
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from functools import cache

import httpx
import numpy as np
from onnxruntime import InferenceSession
from tokenizers import Tokenizer

from memlord.config import REMOTE_EMBEDDING_DIM, settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class EmbedPair:
    """Local vector always present; remote only when the cloud call succeeds."""

    local: list[float]
    remote: list[float] | None

    @property
    def used_remote(self) -> bool:
        return self.remote is not None


@cache
def _get_session() -> InferenceSession:
    return InferenceSession(str(settings.model_dir / "model.onnx"))


@cache
def _get_tokenizer() -> Tokenizer:
    # No truncation/padding: long inputs are chunked and padded manually in `embed_local`.
    return Tokenizer.from_file(str(settings.model_dir / "tokenizer.json"))


def _split_ids(ids: list[int], window: int = 510, stride: int = 384) -> list[list[int]]:
    if len(ids) <= window:
        return [ids]
    return [ids[i : i + window] for i in range(0, len(ids) - window + stride, stride)]


async def embed_local(text: str) -> list[float]:
    """Embed with the local ONNX MiniLM model (384-d)."""
    tokenizer = _get_tokenizer()
    session = _get_session()

    # XLM-R special tokens (paraphrase-multilingual-MiniLM-L12-v2).
    cls_id = tokenizer.token_to_id("<s>")
    sep_id = tokenizer.token_to_id("</s>")
    pad_id = tokenizer.token_to_id("<pad>")
    if cls_id is None or sep_id is None or pad_id is None:
        raise RuntimeError("tokenizer missing expected special tokens (<s>/</s>/<pad>)")

    # Encode without special tokens, chunk on content, then wrap each chunk in
    # <s> ... </s> so every window matches the framing the model was trained on.
    encoding = tokenizer.encode(text, add_special_tokens=False)
    chunks = [[cls_id, *c, sep_id] for c in _split_ids(encoding.ids)]
    width = max(len(c) for c in chunks)

    input_ids = np.full((len(chunks), width), pad_id, dtype=np.int64)
    attention_mask = np.zeros((len(chunks), width), dtype=np.int64)
    for i, chunk in enumerate(chunks):
        input_ids[i, : len(chunk)] = chunk
        attention_mask[i, : len(chunk)] = 1
    token_type_ids = np.zeros_like(input_ids, dtype=np.int64)

    loop = asyncio.get_running_loop()
    future: asyncio.Future[list[np.ndarray]] = loop.create_future()

    def _callback(results: list[np.ndarray], _user_data: None, err: str) -> None:
        if err:
            loop.call_soon_threadsafe(future.set_exception, RuntimeError(err))
        else:
            loop.call_soon_threadsafe(future.set_result, results)

    session.run_async(
        None,
        {
            "input_ids": input_ids,
            "attention_mask": attention_mask,
            "token_type_ids": token_type_ids,
        },
        _callback,
        None,
    )

    outputs = await future

    # per-chunk mean pooling with attention mask
    token_embeddings = np.asarray(outputs[0])  # (n_chunks, seq_len, 384)
    mask = attention_mask[..., np.newaxis].astype(np.float32)  # (n_chunks, seq_len, 1)
    pooled = (token_embeddings * mask).sum(axis=1) / mask.sum(axis=1).clip(min=1e-9)

    # L2 normalize each chunk, then average chunks and normalize again
    pooled /= np.linalg.norm(pooled, axis=1, keepdims=True).clip(min=1e-9)
    mean = pooled.mean(axis=0)
    mean /= np.linalg.norm(mean).clip(min=1e-9)

    return mean.astype(np.float32).tolist()


def _embeddings_url() -> str:
    base = (settings.embedding_base_url or "").rstrip("/")
    if base.endswith("/embeddings"):
        return base
    return f"{base}/embeddings"


async def embed_remote(text: str) -> list[float]:
    """Call an OpenAI-compatible embeddings API. Raises on failure."""
    if not settings.remote_embedding_configured:
        raise RuntimeError("remote embedding is not configured")

    headers = {
        "Authorization": f"Bearer {settings.embedding_api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": settings.embedding_model,
        "input": text,
        "encoding_format": "float",
    }
    url = _embeddings_url()
    timeout = httpx.Timeout(settings.embedding_timeout)
    last_err: Exception | None = None
    attempts = settings.embedding_retries + 1

    async with httpx.AsyncClient(timeout=timeout) as client:
        for attempt in range(attempts):
            try:
                resp = await client.post(url, headers=headers, json=payload)
                resp.raise_for_status()
                data = resp.json()
                items = data.get("data") or []
                if not items or "embedding" not in items[0]:
                    raise RuntimeError("remote embeddings response missing data[0].embedding")
                vec = items[0]["embedding"]
                if not isinstance(vec, list) or not vec:
                    raise RuntimeError("remote embedding is empty")
                if len(vec) != settings.embedding_dim:
                    raise RuntimeError(
                        f"remote embedding dim mismatch: got {len(vec)}, "
                        f"expected MEMLORD_EMBEDDING_DIM={settings.embedding_dim}"
                    )
                # L2-normalize for cosine distance consistency with local vectors
                arr = np.asarray(vec, dtype=np.float32)
                arr /= np.linalg.norm(arr).clip(min=1e-9)
                return arr.tolist()
            except Exception as exc:
                last_err = exc
                if attempt + 1 < attempts:
                    await asyncio.sleep(0.2 * (attempt + 1))
                    continue
                break

    assert last_err is not None
    raise last_err


async def embed_pair(text: str) -> EmbedPair:
    """Always compute local; try remote when configured, else remote=None."""
    local = await embed_local(text)
    if not settings.remote_embedding_configured:
        return EmbedPair(local=local, remote=None)
    try:
        remote = await embed_remote(text)
        return EmbedPair(local=local, remote=remote)
    except Exception as exc:
        # Never log the API key; exception message from httpx may include URL only.
        logger.warning("remote embedding failed, falling back to local only: %s", exc)
        return EmbedPair(local=local, remote=None)


async def embed(text: str) -> list[float]:
    """Backward-compatible alias: local ONNX embedding (384-d)."""
    return await embed_local(text)


# Re-export for callers that need the constant without importing config.
__all__ = [
    "EmbedPair",
    "REMOTE_EMBEDDING_DIM",
    "embed",
    "embed_local",
    "embed_pair",
    "embed_remote",
]
