-- 0019: V5 P4 — DOCUMENT EVIDENCE BUNDLE (manifest/view, never a blob).
--
-- A deterministic, hashable MANIFEST of a document's evidence: member-set
-- hashes over the durable L1/L2 tables plus source identity. Consumers
-- stream/query members; nothing deserializes a whole document into RAM.
-- Written at the evidence-complete point of the extract stage — after raw
-- capture, syntax, slice manifest and rescue hypotheses; before settlement.

CREATE TABLE IF NOT EXISTS document_evidence_bundles (
    doc_id            TEXT PRIMARY KEY,
    evidence_contract TEXT NOT NULL,
    bundle_sha256     TEXT NOT NULL,
    member_hashes     JSONB NOT NULL,
    counts            JSONB NOT NULL,
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);
