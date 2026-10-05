-- Re-segment all memories after changing zhparser dictionaries.
-- Run in a NEW connection (dictionaries are loaded once per backend):
--   docker compose exec -T postgres psql -U postgres -d memlord < deploy/zhparser/reindex.sql
-- then restart the app so its pooled connections pick up the new dicts:
--   docker compose restart memlord
-- search_vector is a STORED generated column, so touching the row recomputes it.
UPDATE memories SET content = content;
REINDEX INDEX ix_memories_search_vector;
SELECT to_tsvector('chinese', '美团入职时间') AS sample;
