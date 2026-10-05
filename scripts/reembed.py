"""Re-embed all memories after changing the embedding model / enabling remote.

Always refreshes the local 384-d ONNX embedding. When remote embedding is
configured (MEMLORD_EMBEDDING_PROVIDER=openai_compatible), also refreshes
embedding_remote; on remote failure that row keeps embedding_remote as NULL
(or leaves the previous value only if you skip the update — this script sets
it to whatever embed_pair returns, which is None on failure).

Run after downloading the local model:
    uv run python scripts/download_model.py
    uv run python scripts/reembed.py
"""

import asyncio

import sqlalchemy as sa

from memlord.db import session
from memlord.embeddings import embed_pair
from memlord.models import Memory


async def main() -> None:
    async with session() as s:
        rows = (await s.execute(sa.select(Memory.id, Memory.content))).fetchall()

    print(f"Re-embedding {len(rows)} memories...")

    remote_ok = 0
    async with session() as s:
        for i, (memory_id, content) in enumerate(rows, 1):
            pair = await embed_pair(content)
            await s.execute(
                sa.update(Memory)
                .where(Memory.id == memory_id)
                .values(embedding=pair.local, embedding_remote=pair.remote)
            )
            if pair.used_remote:
                remote_ok += 1
            flag = "remote" if pair.used_remote else "local-only"
            print(f"  [{i}/{len(rows)}] id={memory_id} ({flag})")

    print(f"Done. remote_ok={remote_ok}/{len(rows)}")


asyncio.run(main())
