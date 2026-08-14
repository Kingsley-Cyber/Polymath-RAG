"""R3a EvidenceBundle acceptance tests. No live stores required."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "shared"))

from polymath_shared.evidence_bundle import (  # noqa: E402
    EvidenceAssemblyError,
    assemble_evidence_bundle,
)


PASSAGE = {
    "chunk_id": "chunk_a",
    "doc_id": "doc_a",
    "source_name": "a.md",
    "text": "Acme uses ToolX for retrieval.",
    "char_start": 10,
    "char_end": 40,
    "contract_ids": ["lexical-v1", "embed-v1", "lexical-v1"],
    "retrieval_paths": [
        {
            "lane": "child_lexical",
            "representation_kind": "child_chunk",
            "contract_id": "lexical-v1",
            "rank": 1,
            "raw_score": 2.0,
        },
        {
            "lane": "child_dense",
            "representation_kind": "child_chunk",
            "contract_id": "embed-v1",
            "rank": 0,
            "raw_score": 0.82,
        },
    ],
}


def _fact_row(
    fact_id: str = "fact_1",
    evidence_id: str = "ev_1",
    obj: str = "ToolX",
    object_id: str = "ent_toolx",
) -> dict:
    return {
        "fact_id": fact_id,
        "predicate": "uses",
        "subject_id": "ent_acme",
        "subject": "Acme",
        "object_id": object_id,
        "object": obj,
        "qualifiers": {"conditional": False},
        "decision": "ACCEPT",
        "rule_id": "uses_rule",
        "rule_version": "1.0.1",
        "provenance": {"roleset": "use.01", "semlink_resolved": True},
        "evidence_id": evidence_id,
        "doc_id": "doc_a",
        "chunk_id": "chunk_a",
        "span_offsets": {"chunk_char_start": 10},
        "evidence_rule_id": "uses_rule",
        "extractor_version": "gliner-2pass-v1",
        "source_name": "a.md",
        "text": "Acme uses ToolX for retrieval.",
        "char_start": 10,
        "char_end": 40,
    }


def test_passage_support_preserves_exact_source_and_retrieval_paths() -> None:
    bundle = assemble_evidence_bundle(
        "what does Acme use?",
        passages=[PASSAGE],
        graph_facts=[],
        fact_support_rows=[],
    )
    item = bundle.evidence_bundle[0]
    assert item.support_kind == "passage"
    assert item.source_span.text == PASSAGE["text"]
    assert item.source_span.char_start == 10
    assert item.source_span.char_end == 40
    assert [p.lane for p in item.retrieval] == ["child_dense", "child_lexical"]
    assert item.provenance["contract_ids"] == ["embed-v1", "lexical-v1"]


def test_graph_fact_resolves_to_source_and_compiler_provenance() -> None:
    bundle = assemble_evidence_bundle(
        "what does Acme use?",
        passages=[],
        graph_facts=[{"fact_id": "fact_1", "predicate": "uses"}],
        fact_support_rows=[_fact_row()],
    )
    item = bundle.evidence_bundle[0]
    assert item.support_kind == "fact"
    assert item.fact_id == "fact_1"
    assert item.evidence_id == "ev_1"
    assert item.claim_candidate == {
        "kind": "relation",
        "subject_id": "ent_acme",
        "subject": "Acme",
        "predicate": "uses",
        "object_id": "ent_toolx",
        "object": "ToolX",
    }
    assert item.provenance["roleset"] == "use.01"
    assert item.epistemics["decision"] == "ACCEPT"
    assert item.applicability["qualifiers"] == {"conditional": False}
    assert item.source_span.text == "Acme uses ToolX for retrieval."


def test_duplicate_nominations_collapse_deterministically() -> None:
    graph = [
        {"fact_id": "fact_1"},
        {"fact_id": "fact_1"},
    ]
    rows = [_fact_row(), _fact_row()]
    a = assemble_evidence_bundle(
        "query",
        passages=[PASSAGE, PASSAGE],
        graph_facts=graph,
        fact_support_rows=rows,
    )
    b = assemble_evidence_bundle(
        "query",
        passages=[PASSAGE, PASSAGE],
        graph_facts=graph,
        fact_support_rows=rows,
    )
    assert [i.support_id for i in a.evidence_bundle] == [i.support_id for i in b.evidence_bundle]
    assert len(a.evidence_bundle) == 2  # one fact support + one passage support


def test_conflicting_fact_support_can_coexist() -> None:
    rows = [
        _fact_row("fact_1", "ev_1", "ToolX", "ent_toolx"),
        _fact_row("fact_2", "ev_2", "ToolY", "ent_tooly"),
    ]
    rows[1]["decision"] = "QUALIFY"
    rows[1]["qualifiers"] = {"conditional": True}
    bundle = assemble_evidence_bundle(
        "what does Acme use?",
        passages=[],
        graph_facts=[{"fact_id": "fact_1"}, {"fact_id": "fact_2"}],
        fact_support_rows=rows,
    )
    assert {i.fact_id for i in bundle.evidence_bundle} == {"fact_1", "fact_2"}
    assert {i.claim_candidate["object"] for i in bundle.evidence_bundle} == {"ToolX", "ToolY"}


def test_missing_authoritative_fact_evidence_fails_loudly() -> None:
    with pytest.raises(EvidenceAssemblyError, match="no authoritative Postgres evidence"):
        assemble_evidence_bundle(
            "query",
            passages=[],
            graph_facts=[{"fact_id": "fact_missing"}],
            fact_support_rows=[],
        )


def test_missing_compiler_provenance_fails_loudly() -> None:
    row = _fact_row()
    row["provenance"] = {}
    with pytest.raises(EvidenceAssemblyError, match="missing compiler provenance"):
        assemble_evidence_bundle(
            "query",
            passages=[],
            graph_facts=[{"fact_id": "fact_1"}],
            fact_support_rows=[row],
        )


def test_missing_passage_retrieval_provenance_fails_loudly() -> None:
    row = dict(PASSAGE)
    row["retrieval_paths"] = []
    with pytest.raises(EvidenceAssemblyError, match="missing retrieval provenance"):
        assemble_evidence_bundle(
            "query", passages=[row], graph_facts=[], fact_support_rows=[]
        )
