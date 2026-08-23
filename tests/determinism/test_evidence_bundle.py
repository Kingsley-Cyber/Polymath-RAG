"""V5 P4 — document-evidence-bundle-v1: a deterministic manifest, fail-closed."""
import pytest

from polymath_shared.raw_evidence import (
    BUNDLE_CONTRACT, IncompleteEvidence, bundle_manifest,
)


class _Conn:
    def __init__(self, rows_by_member):
        self.rows = rows_by_member
    def execute(self, sql, params=()):
        for key in ("FROM chunks", "FROM sentence_slices", "FROM document_layout",
                    "FROM raw_entity_proposals", "FROM raw_predicate_evidence",
                    "FROM span_hypotheses"):
            if key in sql:
                return _R(self.rows.get(key.split()[-1], []))
        raise AssertionError(sql)


class _R:
    def __init__(self, rows): self._rows = rows
    def fetchall(self): return self._rows


FULL = {"chunks": [("c1",)], "sentence_slices": [("c1", 0, 0, 40)],
        "document_layout": [("atx_heading", 0, 10)],
        "raw_entity_proposals": [("rawent_a",), ("rawent_b",)],
        "raw_predicate_evidence": [], "span_hypotheses": [("hyp_a",)]}


def test_bundle_hash_is_deterministic_and_content_addressed():
    a = bundle_manifest(_Conn(FULL), "d1")
    b = bundle_manifest(_Conn({k: list(v) for k, v in FULL.items()}), "d1")
    assert a["bundle_sha256"] == b["bundle_sha256"]
    assert a["evidence_contract"] == BUNDLE_CONTRACT
    changed = {**FULL, "raw_entity_proposals": [("rawent_a",)]}
    assert bundle_manifest(_Conn(changed), "d1")["bundle_sha256"] != a["bundle_sha256"]


def test_empty_optional_members_are_legal_and_recorded():
    """Zero raw predicate rows (lexical mode) and zero layout regions are
    real states, not gaps — counts say so explicitly."""
    m = bundle_manifest(_Conn({**FULL, "document_layout": [],
                               "span_hypotheses": []}), "d1")
    assert m["counts"]["layout"] == 0 and m["counts"]["span_hypotheses"] == 0


def test_missing_required_evidence_fails_closed():
    with pytest.raises(IncompleteEvidence):
        bundle_manifest(_Conn({**FULL, "sentence_slices": []}), "d1")
    with pytest.raises(IncompleteEvidence):
        bundle_manifest(_Conn({**FULL, "chunks": []}), "d1")


def test_bundle_does_not_move_the_semantic_bundle_hash():
    from polymath_shared.execution import semantic_authority_sha256

    # ADMISSION-IMPL-MEMO-V1 moved the authority code hash: behavior-
    # identical memoization in concept_evidence.py, licensed by
    # test_concept_evidence_equivalence.py plus a B8 same-corpus run
    # with identical semantic state (perf-baseline-v1, 2026-08-21).
    assert semantic_authority_sha256().startswith("6976e483c9934abf")
