-- 0016: LAYOUT-EVIDENCE-V1 + SENTENCE-SLICE-MANIFEST-V1.
--
-- Both are EVIDENCE PLUMBING. No semantic rule changes, no chunk text
-- changes, no re-embedding, no Qdrant rebuild. Chunk ids are content-hashed
-- from chunk text, which is untouched, so every existing chunk keeps its id.
--
-- WHY THESE EXIST
--
-- Two production defects had the same shape: a semantic authority depended
-- on information the live representation had already destroyed, and neither
-- the unit tests nor the fact-level score could see it.
--
--   HEADING CONTEXT   Chunk text is assembled with `" ".join(sentences)`,
--                     so line structure is gone. Recomputing heading regions
--                     from chunk text marked an ENTIRE newline-free chunk as
--                     one heading and withdrew identity from every span in
--                     it (I4: graph-eligible 55 -> 13).
--
--   DISCOURSE CONTEXT Which sentence slices the interpreter actually saw is
--                     a function of GLiNER evidence-trigger placement and was
--                     never persisted, so reprocessing had to guess. A
--                     narrower guess lost an antecedent; a wider one can
--                     invent antecedents that never existed.
--
-- The rule both cases teach:
--
--     Layout and context are EVIDENCE. Evidence is persisted at the point it
--     still exists, never reconstructed downstream from a representation
--     that was lossy by design.

-- LAYOUT-EVIDENCE-V1 -------------------------------------------------------
-- Explicit layout regions, in MATERIALIZED SOURCE offsets. Detected at
-- intake where line structure is intact, and authoritative thereafter.
CREATE TABLE IF NOT EXISTS document_layout (
    doc_id      TEXT    NOT NULL REFERENCES documents(doc_id) ON DELETE CASCADE,
    kind        TEXT    NOT NULL,          -- 'atx_heading' | 'setext_heading'
    char_start  INTEGER NOT NULL,
    char_end    INTEGER NOT NULL,
    contract    TEXT    NOT NULL DEFAULT 'layout-evidence-v1',
    PRIMARY KEY (doc_id, char_start, char_end, kind)
);

CREATE INDEX IF NOT EXISTS document_layout_doc_idx ON document_layout(doc_id);

-- The chunk-relative projection of those regions, computed by the chunker,
-- which is the only component holding BOTH coordinate systems at once.
-- Sentence granularity is insufficient: a heading with no terminal
-- punctuation is merged with the following prose into one sentence, so the
-- projection is character-level.
ALTER TABLE chunks ADD COLUMN IF NOT EXISTS layout_map JSONB;

COMMENT ON COLUMN chunks.layout_map IS
  'layout-evidence-v1: chunk-relative [start,end) ranges that are heading '
  'text, projected from document_layout by the chunker. NULL means the '
  'chunk predates this migration — admission must then ABSTAIN from heading '
  'suppression rather than assume "no headings", because absent evidence is '
  'not evidence of absence.';

-- SENTENCE-SLICE-MANIFEST-V1 ----------------------------------------------
-- Exactly which slices the interpreter saw, in what order, under which
-- contract. Reprocessing CONSUMES this; it never re-derives it.
CREATE TABLE IF NOT EXISTS sentence_slices (
    doc_id        TEXT    NOT NULL,
    chunk_id      TEXT    NOT NULL,
    slice_index   INTEGER NOT NULL,        -- ordering WITHIN the document
    chunk_start   INTEGER NOT NULL,        -- chunk-relative sentence span
    chunk_end     INTEGER NOT NULL,
    in_context    BOOLEAN NOT NULL,        -- was it in the interpreter's view
    contract      TEXT    NOT NULL DEFAULT 'sentence-slice-manifest-v1',
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (doc_id, chunk_id, slice_index)
);

CREATE INDEX IF NOT EXISTS sentence_slices_doc_idx ON sentence_slices(doc_id);

-- No backfill for either table, deliberately. Reconstructing layout or slice
-- membership for historical rows would fabricate evidence about runs that
-- never recorded it. Historical documents carry NULL/absent rows and the
-- consumers abstain.
