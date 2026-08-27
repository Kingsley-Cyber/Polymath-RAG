-- 0021: KNOWLEDGE STRATIFICATION — Tier 0 / Tier 1 / Tier 2.
--
-- INFORMATION IS NOT KNOWLEDGE. Polymath already separates evidence from
-- interpretation physically; this migration makes the third boundary —
-- interpretation vs. asserted knowledge — explicit and queryable rather
-- than implicit in "did a fact row get written".
--
--   T0 EVIDENCE     observed, append-only, never a knowledge claim:
--                   documents · chunks · sentence_slices · document_layout
--                   raw_entity_proposals · evidence
--   T1 INFORMATION  interpreted and plausible, useful for retrieval and
--                   debugging, NOT asserted: mentions · span_hypotheses ·
--                   relation_candidates · QUALIFY and REJECT decisions ·
--                   facts that fact admission did not pass
--   T2 KNOWLEDGE    asserted canonical claims: facts whose FactAdmission
--                   outcome is PASS and whose endpoints are graph-eligible.
--                   Neo4j's asserted graph should mirror exactly this set.
--
-- Nothing here deletes or rewrites an existing row. Tier membership is
-- DERIVED, so a re-qualification changes tiers without touching evidence.

CREATE TABLE IF NOT EXISTS fact_admission_decisions (
    fact_id          TEXT NOT NULL,
    candidate_id     TEXT NOT NULL,
    corpus_id        TEXT NOT NULL,
    doc_id           TEXT NOT NULL,
    outcome          TEXT NOT NULL,          -- PASS | QUALIFY | REJECT
    gate             TEXT,                   -- gate that decided (NULL when admitted)
    reason           TEXT,                   -- stable reason code
    flipped          BOOLEAN NOT NULL DEFAULT FALSE,
    -- `shadow` means: computed against the ledger but NOT projected. A
    -- decision only governs the canonical graph once this is false.
    shadow           BOOLEAN NOT NULL DEFAULT TRUE,
    contract_version TEXT NOT NULL,          -- fact-admission-v1
    policy_version   TEXT NOT NULL,          -- fact-admission-policy-v1
    region_policy_version TEXT,              -- region-policy-v1
    decided_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (fact_id, candidate_id, contract_version, policy_version)
);

CREATE INDEX IF NOT EXISTS fact_admission_decisions_outcome_idx
    ON fact_admission_decisions (corpus_id, outcome);
CREATE INDEX IF NOT EXISTS fact_admission_decisions_fact_idx
    ON fact_admission_decisions (fact_id);
CREATE INDEX IF NOT EXISTS fact_admission_decisions_reason_idx
    ON fact_admission_decisions (corpus_id, gate, reason);

-- Tier 2 candidate set: a fact is asserted knowledge only when EVERY
-- admission decision recorded for it passed. One REJECT anywhere demotes
-- the fact to Tier 1 — admission is fail-closed, so a fact is not
-- promoted by its most favourable evidence.
CREATE OR REPLACE VIEW knowledge_tier_facts AS
SELECT
    f.fact_id,
    d.corpus_id,
    d.contract_version,
    d.shadow,
    CASE
        WHEN bool_and(d.outcome = 'PASS') THEN 'T2_KNOWLEDGE'
        ELSE 'T1_INFORMATION'
    END AS tier,
    count(*)                                        AS decisions,
    count(*) FILTER (WHERE d.outcome = 'PASS')      AS passed,
    count(*) FILTER (WHERE d.outcome = 'QUALIFY')   AS qualified,
    count(*) FILTER (WHERE d.outcome = 'REJECT')    AS rejected,
    min(d.gate)   AS first_gate,
    min(d.reason) AS first_reason
FROM facts f
JOIN fact_admission_decisions d ON d.fact_id = f.fact_id
GROUP BY f.fact_id, d.corpus_id, d.contract_version, d.shadow;

COMMENT ON TABLE fact_admission_decisions IS
    'POLYMATH-FACT-ADMISSION-V1 gate decisions. shadow=TRUE means computed '
    'but not governing the projected graph.';
COMMENT ON VIEW knowledge_tier_facts IS
    'Tier membership per fact. T2 requires every recorded decision to PASS.';
