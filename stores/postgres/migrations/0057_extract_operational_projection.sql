-- EXTRACT-OPERATIONAL-PROJECTION-V1 (execution authority §20A, 2026-09-12)
--
-- Root cause, measured with EXPLAIN (ANALYZE, BUFFERS): control_plane_status.py's
-- _graph_provider and document_status.py's corpus_document_summaries both filter
-- `stage='extract' AND jsonb_exists(payload,'llm_extraction')` over `artifacts`. That
-- filter forces Postgres to detoast the `payload` column for effectively the WHOLE
-- table on every call — 108 extract rows average 116 KB (max 789 KB), TOAST is 455 of
-- the table's 456 MB for only 1,107 logical rows — measured at ~45,000 buffer reads
-- (~350+ MB) and 490-605 ms PER CALL on a single corpus, on an endpoint the Control
-- Plane and Files pages poll frequently. pMAP's own operational read
-- (doc_parent_map artifacts) is untouched — its payload is small; this is specific to
-- the full extraction artifact (entities/relations/spans/raw-response detail), which
-- stays authoritative for forensic/replay/detail reads. This migration adds narrow
-- scalar columns so the hot aggregate never touches `payload` — additive, nullable,
-- no existing column altered, no payload data changed or deleted.
--
-- Semantic inventory (live data, 2026-09-12): 100% of the 108 current stage='extract'
-- rows have llm_extraction present, stats is always an object, and
-- calls/entities/relations are always present as numbers — but the columns stay
-- NULLable so a future extraction contract that omits the key, or a row this backfill
-- has not reached yet, reads as NULL (unknown), never a silently-invented 0.
ALTER TABLE artifacts ADD COLUMN IF NOT EXISTS extract_stats_present boolean;
ALTER TABLE artifacts ADD COLUMN IF NOT EXISTS extract_llm_calls int;
ALTER TABLE artifacts ADD COLUMN IF NOT EXISTS extract_entity_count int;
ALTER TABLE artifacts ADD COLUMN IF NOT EXISTS extract_relation_count int;
ALTER TABLE artifacts ADD COLUMN IF NOT EXISTS extract_neighborhoods_sent int;
ALTER TABLE artifacts ADD COLUMN IF NOT EXISTS extract_neighborhoods_unaccounted int;
ALTER TABLE artifacts ADD COLUMN IF NOT EXISTS extract_neighborhoods_dropped int;
