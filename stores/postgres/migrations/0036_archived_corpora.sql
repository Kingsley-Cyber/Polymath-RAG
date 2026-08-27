-- 0036: ARCHIVED-CORPUS REGISTRY (Stage-K pilot finding, 2026-08-25).
--
-- Ticket archival alone loses a war of attrition against
-- reconcile_contract_drift: stranded old-contract chains get superseded
-- AND generation-successor chains minted EVERY tick (measured: 9,373
-- regenerated ready scale events occupied the claim FIFO minutes after
-- cleanup). An archived corpus is OUT of the scheduling lifecycle until
-- explicitly restored.

CREATE TABLE archived_corpora (
    corpus_id   text PRIMARY KEY,
    reason      text NOT NULL,
    archived_at timestamptz NOT NULL DEFAULT now()
);

INSERT INTO archived_corpora (corpus_id, reason)
VALUES ('scale-10k-v1',
        'stale scale-qualification mass: dead chains regenerated via contract-drift reconciliation; archived to stop scheduler occupancy');
