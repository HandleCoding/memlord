<p align="center">
  <img src="https://raw.githubusercontent.com/MyrikLD/memlord/refs/heads/main/media/logo.svg" alt="Self-hosted MCP memory server with hybrid BM25 + semantic search, backed by PostgreSQL +
pgvector" width="100%">
</p>

<h2 align="center">Self-hosted MCP memory server for personal use and teams</h4>

<p align="center">
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-AGPL%203.0-blue.svg" alt="License"></a>
  <a href="pyproject.toml"><img src="https://img.shields.io/badge/python-3.12-brightgreen.svg" alt="Python"></a>
  <a href="https://github.com/MyrikLD/memlord/releases"><img src="https://img.shields.io/github/v/tag/MyrikLD/memlord?label=version&color=green" alt="Version"></a>
  <a href="https://github.com/modelcontextprotocol/servers"><img src="https://img.shields.io/badge/MCP-compatible-purple.svg" alt="MCP"></a>
  <a href="https://github.com/astral-sh/ruff"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json" alt="Ruff"></a>
  <a href="https://glama.ai/mcp/servers/MyrikLD/memlord"><img src="https://glama.ai/mcp/servers/MyrikLD/memlord/badges/score.svg" alt="MCP score"></a>
</p>

<p align="center">
  <a href="#-quickstart">Quickstart</a> •
  <a href="#-how-it-works">How It Works</a> •
  <a href="#️-mcp-tools">MCP Tools</a> •
  <a href="#️-configuration">Configuration</a> •
  <a href="#-system-requirements">Requirements</a> •
  <a href="#-license">License</a>
</p>

---

## ✨ Features

- 🔍 **Hybrid search** — BM25 (full-text) + vector KNN (pgvector) fused via Reciprocal Rank Fusion
- 📂 **Multi-user** — each user sees only their own memories; workspaces for shared team knowledge
- 🛠️ **11 MCP tools** — store, retrieve, recall, list, search by tag, get, update, delete, move, list workspaces, dream report
- 💤 **Dreaming** — a guided consolidation pass (`dream` MCP prompt + `dream_report` tool): finds near-duplicate and conflicting memories, merges them into insights non-destructively, driven by the client LLM
- 🌐 **Web UI** — browse, search, edit and delete memories in the browser; export/import JSON
- 🔒 **OAuth 2.1** — full in-process authorization server, always enabled
- 🐘 **PostgreSQL** — pgvector for embeddings, tsvector for full-text search
- 📊 **Progressive disclosure** — search returns compact snippets by default; call `get_memory(name)` only for what you
  need, reducing token usage
- 🔁 **Deduplication** — automatically detects near-identical memories before saving, preventing noise accumulation

---

## 🆚 How Memlord compares

|                       | **Memlord**                                | [**OpenMemory**](https://github.com/mem0ai/mem0/tree/main/openmemory) | [**mcp-memory-service**](https://github.com/doobidoo/mcp-memory-service) | [**basic-memory**](https://github.com/basicmachines-co/basic-memory) |
|-----------------------|--------------------------------------------|-----------------------------------------------------------------------|--------------------------------------------------------------------------|----------------------------------------------------------------------|
| **Search**            | BM25 + vector + RRF                        | Vector only (Qdrant)                                                  | BM25 + vector + RRF                                                      | BM25 + vector                                                        |
| **Embeddings**        | Local ONNX, zero config                    | OpenAI default; Ollama optional                                       | Local ONNX, zero config                                                  | Local FastEmbed                                                      |
| **Storage**           | PostgreSQL + pgvector                      | PostgreSQL + Qdrant                                                   | SQLite-vec / Cloudflare Vectorize                                        | SQLite + Markdown files                                              |
| **Multi-user**        | ✅                                          | ❌ single-user in practice                                             | ⚠️ agent-ID scoping, no isolation                                        | ❌                                                                    |
| **Workspaces**        | ✅ shared + personal, invite links          | ⚠️ "Apps" namespace                                                   | ⚠️ tags + conversation_id                                                | ✅ per-project flag                                                   |
| **Authentication**    | ✅ OAuth 2.1                                | ❌ none (self-hosted)                                                  | ✅ OAuth 2.0 + PKCE                                                       | ❌                                                                    |
| **Web UI**            | ✅ browse, edit, export                     | ✅ Next.js dashboard                                                   | ✅ rich UI, graph viz, quality scores                                     | ❌ local; cloud only                                                  |
| **MCP tools**         | 11                                         | 5                                                                     | 15+                                                                      | ~20                                                                  |
| **Self-hosted**       | ✅ single process                           | ✅ Docker (3 containers)                                               | ✅                                                                        | ✅                                                                    |
| **Memory input**      | Manual (explicit store)                    | Auto-extracted by LLM                                                 | Manual                                                                   | Manual (Markdown notes)                                              |
| **Memory types**      | fact / preference / instruction / feedback / decision / insight | auto-extracted facts                                                  | —                                                                        | observations + wiki links                                            |
| **Time-aware search** | ✅ natural language dates                   | ⚠️ REST only, not in MCP tools                                        | —                                                                        | ✅ recent_activity                                                    |
| **Token efficiency**  | ✅ progressive disclosure                   | ❌                                                                     | —                                                                        | ✅ build_context traversal                                            |
| **Import / Export**   | ✅ JSON                                     | ✅ ZIP (JSON + JSONL)                                                  | —                                                                        | ✅ Markdown (human-readable)                                          |
| **License**           | AGPL-3.0 / Commercial                      | Apache 2.0                                                            | Apache 2.0                                                               | AGPL-3.0                                                             |

**Where competitors have a real edge:**

- **OpenMemory** — auto-extracts memories from raw conversation text; no need to decide what to store manually; good
  import/export
- **mcp-memory-service** — richer web UI (graph visualization, quality scoring, 8 tabs); more permissive license (Apache
  2.0); multiple transport options (stdio, SSE, HTTP)
- **basic-memory** — memories are human-readable Markdown files you can edit, version-control, and read without any
  server; wiki-style entity links form a local knowledge graph; ~20 MCP tools

**When to pick Memlord:**

- You want **zero-config local embeddings** — ONNX model ships with the server, no Ollama or external API needed
- You run a **multi-user team server** with proper OAuth 2.1 auth and invite-based workspaces
- You want a **production-grade database** (PostgreSQL) that scales beyond a single machine's SQLite
- You manage memories **explicitly** — store exactly what matters, typed and tagged, not everything the LLM decides to
  extract
- You want a **self-hosted Web UI** with full CRUD and JSON export, without a cloud subscription

---

## 🚀 Quickstart

### 🐳 Docker

```bash
cp .env.example .env
docker compose up
```

> 中文用户：默认 compose 已经用了带 zhparser 的 Postgres 镜像并挂好了中文词表，
> 直接 `docker compose up` 即可。自己部署/换镜像前请先读
> [中文全文检索（zhparser + 词表）](#-中文全文检索zhparser--词表)。

### HTTP server (multi-user, Web UI, OAuth)

```bash
# Install dependencies
uv sync --dev

# Download ONNX model (~23 MB)
uv run python scripts/download_model.py

# Run migrations
alembic upgrade head

# Start the server
memlord
```

Open **http://localhost:8000** for the Web UI. The MCP endpoint is at `/mcp`.

---

## 🔍 How It Works

Each search request runs BM25 and vector KNN **in parallel**, then merges results via **Reciprocal Rank Fusion**:

```mermaid
flowchart TD
    Q([query]) --> BM25["BM25\nsearch_vector @@ websearch_to_tsquery"]
    Q --> EMB["ONNX embed\nparaphrase-multilingual-MiniLM-L12-v2 · 384d · local"]
    EMB --> KNN["KNN\nembedding <=> query_vector\ncosine distance"]
    BM25 --> RRF["Weighted RRF\nw_fts/(k+rank_fts) + w_vec/(k+rank_vec)\n+ title boost · default k=20"]
    KNN --> RRF
    RRF --> R([top-N results])
```

---

## ⚙️ Configuration

All settings use the `MEMLORD_` prefix. See [`.env.example`](.env.example) for the full list.


### Optional remote embeddings

By default Memlord embeds everything with the bundled ONNX model
(`paraphrase-multilingual-MiniLM-L12-v2`, 384-d) — same as upstream.

You can also point at an OpenAI-compatible embeddings API (e.g. SiliconFlow
`BAAI/bge-m3`). Local vectors are **always** written; remote vectors go into the
nullable `embedding_remote` column (1024-d). Store and search prefer remote when
it is configured and healthy, and fall back to local on failure/timeout.

```bash
MEMLORD_EMBEDDING_PROVIDER=openai_compatible
MEMLORD_EMBEDDING_BASE_URL=https://api.siliconflow.cn/v1
MEMLORD_EMBEDDING_API_KEY=sk-...
MEMLORD_EMBEDDING_MODEL=BAAI/bge-m3
MEMLORD_EMBEDDING_DIM=1024
```

After enabling remote on an existing database, run migrations then re-embed:

```bash
alembic upgrade head
uv run python scripts/reembed.py
```

Changing `MEMLORD_EMBEDDING_DIM` requires a new migration (the pgvector column
size is fixed).

### Hybrid fusion tuning

Search merges FTS + vector ranks with **weighted Reciprocal Rank Fusion**, then
adds a small title boost. All knobs are `MEMLORD_*` env vars (see `.env.example`).

| Knob | Default | Notes |
|------|---------|-------|
| `MEMLORD_RRF_K` | `20` | Lower → steeper rank gaps. `20` is a solid default for personal and mid-size stores; raise toward `40–60` if a very large corpus produces too many near-ties. |
| `MEMLORD_FUSION_W_VEC` | `1.0` | Weight on the vector leg. |
| `MEMLORD_FUSION_W_FTS_LOCAL` | `1.0` | FTS weight when using the local 384-d vectors. |
| `MEMLORD_FUSION_W_FTS_REMOTE` | `0.5` | FTS weight when remote embeddings drive vector search (reduces keyword dilution of strong semantic hits). Raise toward `1.0` if exact keyword/title recall matters more than paraphrase. |
| `MEMLORD_FTS_WEAK_RATIO` | `0.3` | FTS hits with `ts_rank < ratio × max(ts_rank)` contribute **no** FTS score (they can still appear via vector/title). Lower if weak keyword matches should still count. |
| `MEMLORD_EXACT_NAME_BOOST` / `MEMLORD_PARTIAL_NAME_BOOST` | `1.0` / `0.025` | Added after RRF. Keep partial boost well below a single-path rank-1 score (`≈1/(k+1)`). |
| `MEMLORD_SEARCH_DEBUG` | `false` | When true, results include `score_fts` / `score_vec` / `score_name`. |

These defaults are meant to be **corpus-size agnostic**: they do not assume a
fixed number of memories. Tune from observed ranking quality, not from a
hard-coded library size.


| Variable                   | Default                                                    | Description                                       |
|----------------------------|------------------------------------------------------------|---------------------------------------------------|
| `MEMLORD_DB_URL`           | `postgresql+asyncpg://postgres:postgres@localhost/memlord` | PostgreSQL connection URL                         |
| `MEMLORD_PORT`             | `8000`                                                     | Server port                                       |
| `MEMLORD_BASE_URL`         | `http://localhost:8000`                                    | Public URL for OAuth (HTTP mode)                  |
| `MEMLORD_OAUTH_JWT_SECRET` | `memlord-dev-secret-please-change`                         | JWT signing secret (HTTP mode)                    |

Set `MEMLORD_BASE_URL` to your public URL and change `MEMLORD_OAUTH_JWT_SECRET` before deploying.

---

## 🀄 中文全文检索（zhparser + 词表）

Memlord 的混合检索 = 向量 KNN + Postgres 全文检索（FTS）。这个 fork 的 FTS 用
[zhparser](https://github.com/amutu/zhparser)（SCWS 分词）做中文切词，
`search_vector` 是 `chinese` 配置生成的 tsvector（标题权重 A、正文 B）。

### 1. 必须用带 zhparser 的 Postgres 镜像

迁移 `e7a1c2b3d4f5_zh_fts` 会执行 `CREATE EXTENSION zhparser`。普通的
`postgres` / `pgvector/pgvector` 镜像**没有这个扩展，迁移会直接失败**。

- 默认：`moailaozi/postgres-images:zhparser-pgvector-17`（zhparser + pgvector，PG 17，compose 里已固定 digest）
- 自建镜像也行，只要同时装了 `zhparser` 和 `vector` 两个扩展；
  下文路径里的 `17` 换成你的 PG 大版本。

### 2. 中文词表：放在哪、怎么配

词表都在 [`deploy/zhparser/dicts/`](deploy/zhparser/dicts)，格式是 SCWS txt：
`词<TAB>tf<TAB>idf<TAB>词性`，`#` 开头为注释。tf 越高、idf 越低越倾向整词切出。

| 文件 | 内容 | 是否提交到仓库 |
|---|---|---|
| `dict_chinese_extra.txt` | 通用词表：jieba 高频 8 万词 + THUOCL IT 词库 + 常用词（约 9.2 万条，~2 MB） | ✅ |
| `dict_memlord_domain.txt` | 业务/产品词：美团、入职、京东云、AnyTLS、硅基流动、向量检索… | ✅，可直接 PR 补充 |
| `dict_user.txt` | 你自己的私有词（人名、主机名、内部项目名），仓库里是空模板 | 模板 ✅；真实内容建议放仓库外 |

接线方式（`docker-compose.yml` 已写好）：

1. 把三个文件 bind-mount 到 Postgres 容器的 `/usr/share/postgresql/17/tsearch_data/`
   （zhparser 只从这个目录按文件名加载，**不支持子目录/绝对路径**）；
2. 用启动参数设置 GUC：
   `postgres -c zhparser.extra_dicts=dict_chinese_extra.txt,dict_memlord_domain.txt,dict_user.txt`。

私有词不想进 git：在 `.env` 里写
`ZHPARSER_USER_DICT=/opt/memlord/zhparser-private/dict_user.txt`，compose 会改挂这个文件
（文件必须存在，否则 Docker 会在宿主机上创建一个同名**目录**）。

不用 compose / 想要自包含的 DB 镜像：

```bash
docker build -t memlord-postgres-zh deploy/zhparser   # 词表 + extra_dicts 打进镜像
```

已有数据库（不方便改启动参数）也可以：
`ALTER SYSTEM SET zhparser.extra_dicts = 'dict_chinese_extra.txt,dict_memlord_domain.txt,dict_user.txt';`
再重启 Postgres。

### 3. 修改词表后

词表在每个数据库连接**第一次分词时加载一次**，而 `search_vector` 是写入时算好的，所以改完要：

```bash
docker compose restart postgres            # 新连接才会读到新词表
docker compose exec -T postgres psql -U postgres -d memlord < deploy/zhparser/reindex.sql
docker compose restart memlord             # 应用连接池里的旧连接也要换掉
```

验证切词：

```sql
SELECT to_tsvector('chinese', '美团入职时间');
-- 有词表： '入职':2 '时间':3 '美团':1
```

缺少某个词表文件时 zhparser 只在 Postgres 日志里打一行
`zhparser: failed to add extra dict ...`，不会报错——切词效果变差时先看这个日志。

### 4. 不挂词表会怎样

zhparser 自带的 SCWS 词典很小，专名、公司名、新词经常切不出来。例如
「美团入职时间」会被切成 `美/团/入/职/时间`。检索侧为了降噪会丢弃单字，于是查询只剩
「时间」去匹配，目标记忆**根本进不了 FTS 候选**，反而是其他含「时间」的记忆被关键词加分，
混合排序后正确结果掉到第 4 名之后。挂上词表后同一查询切成 `美团/入职/时间`，排第 1。

服务仍能运行（只是 FTS 召回变差，向量检索不受影响），所以这个问题很容易被忽略。

### 5. 为什么应用镜像（ghcr.io/…/memlord）里不带词表

分词发生在**数据库里**：写入时 Postgres 用 `to_tsvector('chinese', …)` 生成
`search_vector`，查询时用 `to_tsquery('chinese', …)`。词表只被 Postgres 进程里的 zhparser 读取，
Python 应用进程完全用不到它。把词表打进应用镜像既不生效，还会让「改个业务词」变成
「重新发布应用镜像」。所以词表跟着 Postgres 走：compose 挂载，或用
`deploy/zhparser/Dockerfile` 打进 DB 镜像。

---

## 🛠️ MCP Tools

| Tool              | Description                                                             |
|-------------------|-------------------------------------------------------------------------|
| `store_memory`    | Save a memory (idempotent by content); raises on near-duplicates; optional `expires_at` |
| `retrieve_memory` | Hybrid semantic + full-text search; returns snippets by default         |
| `recall_memory`   | Search by natural-language time expression; returns snippets by default |
| `list_memories`   | Paginated list with type/tag filters                                    |
| `search_by_tag`   | AND/OR tag search                                                       |
| `get_memory`      | Fetch a single memory by name with full content (expired included)      |
| `update_memory`   | Update content, type, tags, metadata, or expiry by name (and optionally rename) |
| `delete_memory`   | Delete by name                                                          |
| `move_memory`     | Move a memory to a different workspace                                  |
| `list_workspaces` | List workspaces you are a member of (including personal)                |
| `dream_report`    | Read-only consolidation candidates: similar memory pairs, expired and expiring-soon memories |

The `dream` MCP prompt walks the client LLM through a full consolidation pass over the
`dream_report` output: classify similar pairs (duplicate / complementary / conflict), merge
into `insight` memories, retire superseded ones via `expires_at` — never destructively.

Workspace management (create, invite, join, leave) is handled via the Web UI.

---

## 💻 System Requirements

- **Python** 3.12
- **PostgreSQL** ≥ 15 with [pgvector](https://github.com/pgvector/pgvector) and [zhparser](https://github.com/amutu/zhparser) extensions (Chinese FTS, see above)
- **uv** — Python package manager

---

## 👨‍💻 Development

```bash
pyright src/           # type check
ruff format .          # format
pytest                 # run tests
alembic-autogen-check  # verify migrations are up to date
```

---

## 📄 License

Memlord is dual-licensed:

- **[AGPL-3.0](LICENSE)** — free for open-source use. If you run a modified version as a network service, you must
  publish your source code.
- **[Commercial License](LICENSE-COMMERCIAL)** — for proprietary or closed-source deployments. Contact
  sergey@memlord.com or dmitry@memlord.com to purchase.
