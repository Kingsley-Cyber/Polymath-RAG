"""V5 L1 — raw-evidence-ledger-v1 (Phase 2).

The ledger records what the provider said, exactly, idempotently — and its
existence must not move the semantic bundle: capture is plumbing, not
authority.
"""
import json

from polymath_shared.raw_evidence import (
    evidence_row, ledger_hash, proposal_row, provider_contract,
)

CONTRACT = provider_contract(provider="gliner", model_id="m", revision="r1",
                             task="entity", threshold=0.5, labels=["Person", "Org"])
ITEM = {"start": 4, "end": 16, "text": "Nimbus Cloud", "label": "Organization",
        "score": 0.912345678}


def test_proposal_ids_are_content_addressed_and_deterministic():
    a = proposal_row("d1", "c1", ITEM, CONTRACT)
    b = proposal_row("d1", "c1", dict(ITEM), dict(CONTRACT))
    assert a == b and a[0].startswith("rawent_")


def test_the_id_covers_the_observation_not_just_the_span():
    base = proposal_row("d1", "c1", ITEM, CONTRACT)[0]
    assert proposal_row("d1", "c1", {**ITEM, "label": "Product"}, CONTRACT)[0] != base
    assert proposal_row("d1", "c1", {**ITEM, "score": 0.4}, CONTRACT)[0] != base
    other = provider_contract(provider="gliner", model_id="m", revision="r2",
                              task="entity", threshold=0.5, labels=["Person", "Org"])
    assert proposal_row("d1", "c1", ITEM, other)[0] != base, (
        "a changed provider revision must yield NEW rows, not overwrite history")


def test_raw_surface_and_label_are_verbatim():
    row = proposal_row("d1", "c1", ITEM, CONTRACT)
    assert row[5] == "Nimbus Cloud" and row[6] == "Organization"
    assert json.loads(row[8])["labels_sha256"]


def test_entity_and_evidence_namespaces_are_disjoint():
    assert evidence_row("d1", "c1", ITEM, CONTRACT)[0].startswith("rawev_")


def test_ledger_capture_does_not_move_the_semantic_bundle():
    """Phase 2 is evidence plumbing. The recorded baseline is the qualified
    subtoken candidate; if this hash moves, capture leaked into semantics."""
    from polymath_shared.execution import semantic_authority_sha256

    # Pin history: ADMISSION-IMPL-MEMO-V1 (behavior-identical
    # memoization, licensed by test_concept_evidence_equivalence.py +
    # B8 identical-state run) moved it to 6976e483…; SCIENTIFIC-KAG-V1
    # slice A (9d0fce4: scientific entity ontology + concept gate) and
    # the enforcement wiring (266aa81) moved it again — both committed,
    # qualified semantic-layer work; bundle integrity is READY at this
    # hash. The pin exists to catch UNNOTICED movement.
    # LLM-DIRECT-CANON (ADR-0017, 2026-09-03): ATTESTATION-LEVELS-V1 changed
    # the gate (llm_extraction/gate.py is semantic authority) — a NOTICED,
    # committed, canary-measured move (work-log 2026-09-03-llm-direct-canon).
    assert semantic_authority_sha256().startswith("7b7fbcd284b47850")  # re-pinned 2026-09-03: LLM-DIRECT-CANON deletion — admission_interpreter lost its spaCy readiness assert, identity_evidence owns RetryableDependencyUnavailable (ADR-0017)
