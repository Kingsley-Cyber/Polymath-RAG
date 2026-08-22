-- 0022: ENTITY KNOWLEDGE ADMISSION — the E1–E7 decision ledger.
--
-- ENTITY-KNOWLEDGE-ADMISSION-V1 was built, tested, qualified and frozen,
-- and then had ZERO production callers. Every report describing its
-- behaviour was describing a shadow harness. This table is where the gate
-- chain records what it decided in production, so the claim "E1–E7 is
-- active" becomes a query rather than an assertion.
--
-- The boundary this enforces is the architecture's, not a new one:
--
--   filtering decides what becomes KNOWLEDGE
--   it never decides whether EVIDENCE survives
--
-- So a REJECT never deletes a mention and never removes a raw proposal.
-- It demotes the interpretation to MENTION_ONLY: the surface stays
-- readable, searchable and attributable at its exact offsets, but it
-- stops being a durable identity and stops being projected as a graph
-- node. `Figure 4-7` remains a thing the corpus says; it stops being a
-- thing the graph claims exists.
--
-- Mirrors 0021 deliberately, including `shadow`. Wiring and enforcing are
-- separate steps: the chain runs and records first, its production
-- behaviour is measured against the same corpus, and only then does a
-- flag flip. Cutover changes what governs; it never rewrites history.

CREATE TABLE IF NOT EXISTS entity_admission_decisions (
    entity_id        TEXT NOT NULL,
    mention_id       TEXT NOT NULL,
    corpus_id        TEXT NOT NULL,
    doc_id           TEXT NOT NULL,
    chunk_id         TEXT,
    surface          TEXT NOT NULL,           -- exact source surface
    core_type        TEXT,                    -- SETTLED class, never the raw label
    outcome          TEXT NOT NULL,           -- PASS | REJECT
    gate             TEXT,                    -- E1..E7 that decided (NULL when admitted)
    reason           TEXT,                    -- stable reason code
    -- `shadow` means: computed, recorded, and NOT governing. The entity is
    -- still admitted to the graph while this is true. It governs only when
    -- false, which is the cutover.
    shadow           BOOLEAN NOT NULL DEFAULT TRUE,
    -- what the demotion actually did, when it governed
    demoted          BOOLEAN NOT NULL DEFAULT FALSE,
    contract_version TEXT NOT NULL,           -- entity-knowledge-admission-v1
    policy_version   TEXT NOT NULL,           -- entity-admission-policy-v2
    region_policy_version TEXT,               -- region-policy-v1
    decided_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (mention_id, contract_version, policy_version)
);

CREATE INDEX IF NOT EXISTS entity_admission_decisions_corpus_idx
    ON entity_admission_decisions (corpus_id, outcome);

CREATE INDEX IF NOT EXISTS entity_admission_decisions_gate_idx
    ON entity_admission_decisions (gate)
    WHERE outcome = 'REJECT';

CREATE INDEX IF NOT EXISTS entity_admission_decisions_entity_idx
    ON entity_admission_decisions (entity_id);

-- Which entities the gate chain would refuse (or has refused) durable
-- identity. Derived, so a re-qualification changes membership without
-- touching a single mention row.
CREATE OR REPLACE VIEW entity_knowledge_refusals AS
SELECT d.corpus_id,
       d.doc_id,
       d.entity_id,
       d.mention_id,
       d.surface,
       d.core_type,
       d.gate,
       d.reason,
       d.shadow,
       d.demoted
  FROM entity_admission_decisions d
 WHERE d.outcome = 'REJECT';
