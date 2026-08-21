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


def test_capture_is_pre_dedupe_and_pre_mapping():
    """_entity_spans dedupes by span and drops unmapped labels; the sink must
    see EVERYTHING the provider returned."""
    from polymath_shared.contracts import CoreType  # noqa: F401  (import guard)
    from workers.extract_worker import _entity_spans

    class _Fake:
        def entity_pass(self, text, labels, threshold):
            return {"spans": [
                {"start": 0, "end": 6, "text": "Nimbus", "label": "Organization", "score": 0.6},
                {"start": 0, "end": 6, "text": "Nimbus", "label": "Organization", "score": 0.9},
                {"start": 10, "end": 14, "text": "zzzz", "label": "NoSuchLabel", "score": 0.8},
            ]}

    sink: list = []
    spans, rejected = _entity_spans(
        _Fake(), "Nimbus is zzzz here", "c1", "d1",
        {"label_set": ["Organization"], "profile_id": "core",
         "core_labels": ["Organization"], "active_modules": []},
        raw_sink=sink)
    assert len(sink) == 3, "sink must capture pre-dedupe, pre-mapping"
    assert len(spans) == 1 and spans[0].score == 0.9
    assert any(r["reason"] == "no core mapping for label" for r in rejected)


def test_ledger_capture_does_not_move_the_semantic_bundle():
    """Phase 2 is evidence plumbing. The recorded baseline is the qualified
    subtoken candidate; if this hash moves, capture leaked into semantics."""
    from polymath_shared.execution import semantic_authority_sha256

    # ADMISSION-IMPL-MEMO-V1 moved the authority code hash: behavior-
    # identical memoization in concept_evidence.py, licensed by
    # test_concept_evidence_equivalence.py plus a B8 same-corpus run
    # with identical semantic state (perf-baseline-v1, 2026-08-21).
    assert semantic_authority_sha256().startswith("fd68fc57f4c18057")
