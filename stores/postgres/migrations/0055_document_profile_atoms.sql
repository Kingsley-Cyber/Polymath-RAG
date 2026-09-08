-- FINAL-RETRIEVAL-ROUTING-SYNTHESIS-V1 R4 PROFILE_ATOM — independent atom persistence (2026-09-08)
--
-- The routing plan's Profile Atom primitive is a SEPARATE lane from the global Document
-- Profile: "one profile atom = one dense vector" (§34), used for semantic routing/expansion
-- (§9 R4), NOT for document discovery and NEVER as factual evidence (routing-inferred).
-- The document-profile compiler already produces the atom fields (THEORY / CONCEPT /
-- LATENT-PATTERN / BOUNDARY / SEEALSO / BRIDGE / ANCHOR / TENSION / INVERSION / RECALLQ),
-- but they were only ever folded into the global profile point as a few multivectors. This
-- table makes each atom a first-class, independently persisted + projectable record so the
-- atom lane can search them on their own — the "do not silently collapse Profile Atoms into
-- the global profile" requirement.
--
-- Postgres is authority (§51: atom provenance); the Qdrant atom collection is a rebuildable
-- projection. Additive: no existing table is touched. Idempotent: safe to re-run.

CREATE TABLE IF NOT EXISTS document_profile_atoms (
    atom_id             TEXT PRIMARY KEY,          -- content id: hash(doc_id|profile_contract|atom_kind|normalized_text)
    doc_id              TEXT NOT NULL REFERENCES documents(doc_id) ON DELETE CASCADE,
    corpus_id           TEXT,
    profile_contract    TEXT NOT NULL,             -- profile schema+prompt version the atom came from
    atom_kind           TEXT NOT NULL              -- the canonical (hyphen-free) atom kind
                        CHECK (atom_kind IN ('THEORY','CONCEPT','LATENT_PATTERN','BOUNDARY',
                                             'SEEALSO','BRIDGE','ANCHOR','TENSION','INVERSION','RECALLQ')),
    atom_text           TEXT NOT NULL,
    ordinal             INTEGER NOT NULL DEFAULT 0, -- position within (doc, kind), for stable ordering
    source_profile_hash TEXT,                       -- compiled-profile artifact hash the atom was extracted from
    active              BOOLEAN NOT NULL DEFAULT TRUE,
    created_at          timestamptz NOT NULL DEFAULT now(),
    updated_at          timestamptz NOT NULL DEFAULT now()
);

-- Per-document read (extraction / supersede / reconcile scope).
CREATE INDEX IF NOT EXISTS document_profile_atoms_doc_idx
    ON document_profile_atoms (doc_id, profile_contract);
-- Retrieval / reconcile: active atoms of a corpus, optionally by kind.
CREATE INDEX IF NOT EXISTS document_profile_atoms_kind_idx
    ON document_profile_atoms (corpus_id, atom_kind)
    WHERE active;
