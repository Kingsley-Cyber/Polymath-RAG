"""C2 canonical projection plan invariants (no stores).

The projection plan is a pure function of Postgres rows: canonical
nodes, membership edges, evidence->chunk links. Ordering is sorted;
identical input yields an identical plan. Membership edges carry the
C1 decision/basis/version verbatim — Neo4j never decides identity.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "shared"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "workers"))

from workers.project_canonical_worker import canonical_projection_plan  # noqa: E402

NODES = [
    {"canonical_id": "cent_b", "canonical_type": "Organization",
     "normalized_name": "acmecorp", "corpus_id": "c1",
     "canonicalizer_version": "1.0.0"},
    {"canonical_id": "cent_a", "canonical_type": "Person",
     "normalized_name": "john smith", "corpus_id": "c1",
     "canonicalizer_version": "1.0.0"},
]

MEMBERSHIPS = [
    {"canonical_id": "cent_b", "local_entity_id": "ent_b",
     "decision": "SAME_AS", "confidence": 1.0,
     "basis": ["normalized_exact_match", "compatible_core_type"],
     "canonicalizer_version": "1.0.0"},
    {"canonical_id": "cent_b", "local_entity_id": "ent_a",
     "decision": "ALIAS_OF", "confidence": 1.0,
     "basis": ["explicit_source_alias"],
     "canonicalizer_version": "1.0.0"},
    {"canonical_id": "cent_a", "local_entity_id": "ent_c",
     "decision": "SELF", "confidence": 1.0,
     "basis": ["homonym_risk_type_class"],
     "canonicalizer_version": "1.0.0"},
]

EVIDENCE = [
    {"evidence_id": "ev_2", "chunk_id": "chunk_2"},
    {"evidence_id": "ev_1", "chunk_id": "chunk_1"},
]


def test_plan_is_deterministic_and_sorted() -> None:
    a = canonical_projection_plan(NODES, MEMBERSHIPS, EVIDENCE)
    b = canonical_projection_plan(
        list(reversed(NODES)), list(reversed(MEMBERSHIPS)),
        list(reversed(EVIDENCE)),
    )
    assert a == b
    assert [n["canonical_id"] for n in a["nodes"]] == ["cent_a", "cent_b"]
    # Sorted by (canonical_id, local_entity_id): cent_a's member first.
    assert [m["local_entity_id"] for m in a["memberships"]] == ["ent_c", "ent_a", "ent_b"]
    assert [e["evidence_id"] for e in a["evidence_chunks"]] == ["ev_1", "ev_2"]


def test_membership_edges_carry_c1_decision_basis_version() -> None:
    plan = canonical_projection_plan(NODES, MEMBERSHIPS, EVIDENCE)
    alias = [m for m in plan["memberships"] if m["local_entity_id"] == "ent_a"][0]
    assert alias["decision"] == "ALIAS_OF"
    assert alias["basis"] == ["explicit_source_alias"]
    assert alias["canonicalizer_version"] == "1.0.0"
    assert alias["confidence"] == 1.0


def test_evidence_rows_without_chunk_are_excluded() -> None:
    plan = canonical_projection_plan(NODES, MEMBERSHIPS, [
        {"evidence_id": "ev_orphan", "chunk_id": None},
        {"evidence_id": "ev_1", "chunk_id": "chunk_1"},
    ])
    assert [e["evidence_id"] for e in plan["evidence_chunks"]] == ["ev_1"]


def test_plan_never_creates_synthetic_facts() -> None:
    """The plan contains only nodes/memberships/source links — no new
    fact or REL rows can enter through this projection."""
    plan = canonical_projection_plan(NODES, MEMBERSHIPS, EVIDENCE)
    assert set(plan) == {"nodes", "memberships", "evidence_chunks"}
