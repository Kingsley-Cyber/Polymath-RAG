"""PREDICATE-COMPILER-V2 slice 1: provenance schema contract.

The owner decision record replaces association-based intake with
syntax-grounded generation. Before any generator changes, the contract
must make violations measurable: a candidate without a spaCy token id
refuses; a candidate bound by anything except dependency structure
refuses; the L4 ledger records the difference.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))
sys.path.insert(0, str(ROOT / "workers"))

from polymath_shared.contracts import (  # noqa: E402
    BindingSource,
    EntitySpan,
    EvidenceSpan,
    RelationCandidate,
    v2_binding_refusal,
)
from polymath_shared.raw_evidence import relation_candidate_row  # noqa: E402


MIGRATION = ROOT / "stores/postgres/migrations/0023_predicate_v2_provenance.sql"


def _candidate(**overrides) -> RelationCandidate:
    evidence = EvidenceSpan(
        chunk_id="c0", start=10, end=18, text="acquired",
        evidence_class="acquisition", trigger_lemma="acquire",
        score=1.0, extractor_version="test",
        trigger_predicate_id="acquired",
        trigger_lexical_class="VERB",
        trigger_match_source="verbs",
    )
    subject = EntitySpan(
        doc_id="d1", chunk_id="c0", start=0, end=5, text="Apple",
        core_type="Organization", score=0.9, extractor_version="test")
    object_ = EntitySpan(
        doc_id="d1", chunk_id="c0", start=19, end=28, text="Beats",
        core_type="Organization", score=0.9, extractor_version="test")

    class _Cand:
        pass

    from polymath_shared.contracts import EntityCandidate
    base = dict(
        evidence=evidence,
        subject=EntityCandidate(span=subject, resolved_entity_id="ent_s"),
        object=EntityCandidate(span=object_, resolved_entity_id="ent_o"),
        ontology_profile="core",
        sentence_index=3,
    )
    base.update(overrides)
    return RelationCandidate(**base)


def test_bindingsource_defines_v2_dependency_sources():
    assert BindingSource.UD_DEPENDENCY.value == "UD_DEPENDENCY"
    assert BindingSource.NOMINAL_DEPENDENCY.value == "NOMINAL_DEPENDENCY"
    assert BindingSource.BOUNDED_LINEAR_RECALL not in (
        BindingSource.UD_DEPENDENCY, BindingSource.NOMINAL_DEPENDENCY)


def test_candidate_without_trigger_token_refuses():
    cand = _candidate()
    assert cand.trigger_token_id is None
    assert v2_binding_refusal(cand) == "NO_TRIGGER_TOKEN"


def test_candidate_with_proximity_binding_refuses():
    cand = _candidate(
        trigger_token_id=4,
        binding_source=BindingSource.BOUNDED_LINEAR_RECALL)
    assert v2_binding_refusal(cand) == "UNLICENSED_BINDING_SOURCE"

    cand2 = _candidate(trigger_token_id=4)
    assert v2_binding_refusal(cand2) == "UNLICENSED_BINDING_SOURCE"


def test_dependency_bound_candidate_passes_the_v2_rule():
    ud = _candidate(
        trigger_token_id=4,
        subject_token_id=1, object_token_id=6,
        dependency_path="nsubj>dobj",
        binding_source=BindingSource.UD_DEPENDENCY)
    nominal = _candidate(
        trigger_token_id=7,
        binding_source=BindingSource.NOMINAL_DEPENDENCY)
    assert v2_binding_refusal(ud) is None
    assert v2_binding_refusal(nominal) is None


class _Decision:
    decision = "REJECT"
    reason = "test"
    rule_id = None
    fact = None


def test_l4_row_records_v2_provenance_columns():
    v1_cand = _candidate()
    row = relation_candidate_row("d1", "c0", v1_cand, _Decision())
    assert len(row) == 19
    assert row[13] is None and row[14] is None and row[15] is None
    assert row[16] is None and row[17] is None
    assert row[18] == "c0#s3"

    v2_cand = _candidate(
        document_id="d1",
        trigger_token_id=4, subject_token_id=1, object_token_id=6,
        dependency_path="nsubj>dobj",
        binding_source=BindingSource.UD_DEPENDENCY,
        sentence_id="c0#sent-0003")
    row2 = relation_candidate_row("d1", "c0", v2_cand, _Decision())
    assert (row2[13], row2[14], row2[15]) == (4, 1, 6)
    assert row2[16] == "nsubj>dobj"
    assert row2[17] == "UD_DEPENDENCY"
    assert row2[18] == "c0#sent-0003"


def test_l4_row_falls_back_to_lse_binding_source():
    from polymath_shared.contracts import LexicalSemanticEvidence
    lse = LexicalSemanticEvidence(
        evidence_class="acquisition", evidence_surface="acquired",
        evidence_start=10, evidence_end=18,
        trigger_surface="acquired", trigger_lemma="acquire",
        binding_sources=[BindingSource.BOUNDED_LINEAR_RECALL])
    cand = _candidate(lexical_semantic_evidence=lse)
    row = relation_candidate_row("d1", "c0", cand, _Decision())
    assert row[17] == "BOUNDED_LINEAR_RECALL"


def test_migration_declares_the_provenance_columns():
    sql = MIGRATION.read_text()
    for col in ("trigger_token_id", "subject_token_id", "object_token_id",
                "dependency_path", "binding_source", "sentence_id"):
        assert f"ADD COLUMN IF NOT EXISTS {col}" in sql, col
    assert "relation_candidates_binding_source_idx" in sql
