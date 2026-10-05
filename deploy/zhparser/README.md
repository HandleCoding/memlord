# zhparser dictionaries for Memlord

Used by PostgreSQL (zhparser / SCWS) for Chinese full-text search. They are
**not** part of the memlord app image: segmentation runs inside Postgres.
Full usage: see the "中文全文检索（zhparser + 词表）" section in the top-level README.

| File | What | Notes |
|---|---|---|
| `dicts/dict_chinese_extra.txt` | ~92k general words | jieba top-80k + THUOCL_IT + forced common words |
| `dicts/dict_memlord_domain.txt` | product / domain terms | edit & PR freely |
| `dicts/dict_user.txt` | private terms template | keep real one outside git via `ZHPARSER_USER_DICT` |
| `Dockerfile` | optional DB image with dicts baked in | `docker build -t memlord-postgres-zh deploy/zhparser` |
| `reindex.sql` | re-segment existing memories after dict changes | run in a fresh connection, then restart memlord |

Format (SCWS txt, UTF-8): `word<TAB>tf<TAB>idf<TAB>attr`, lines starting with `#` are comments.
File names must match `[A-Za-z0-9_.-]+` and sit directly in `tsearch_data/` (no sub-directories).

## Sources / licenses

- jieba `dict.txt` — https://github.com/fxsjy/jieba (MIT)
- THUOCL IT 词库 — https://github.com/thunlp/THUOCL (MIT)
