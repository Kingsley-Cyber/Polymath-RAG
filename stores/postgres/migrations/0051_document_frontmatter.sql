-- RETRIEVE-EVIDENCE-ROWS-V1 (2026-09-03): documents carry their frontmatter
-- (title, channel, upload_date, video_id, url, source_file …) so an evidence
-- row's `source` is human-auditable ("title · channel · date · 9:25–9:41")
-- instead of an absolute file path. Stamped by intake for new documents;
-- scripts/backfill_frontmatter.py fills existing ones from their first chunk.
ALTER TABLE documents ADD COLUMN IF NOT EXISTS frontmatter jsonb;
