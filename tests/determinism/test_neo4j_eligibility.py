"""D1: one shared Neo4j-eligibility predicate (projector/census/verify).

MENTION_ONLY-dependent facts are intentionally parked in Postgres and
must never count as projection failures. The predicate is deterministic
and corpus-independent (admission classes live on entity rows).
"""
from __future__ import annotations

import sys
from pathlib import Path

sys_path = str(Path(__file__).resolve().parents[2])
if sys_path not in sys.path:
    sys.path.insert(0, sys_path)

from polymath_shared.neo4j_eligibility import (  # noqa: E402
    entity_eligible_sql,
    fact_eligible_from_classes,
    fact_eligible_from_row,
    fact_eligible_sql,
    ineligible_fact_ids_sql,
)


def test_pure_predicate_truth_table():
    assert fact_eligible_from_classes("GLOBAL", "GLOBAL")
    assert fact_eligible_from_classes("GLOBAL", "CORPUS_SCOPED")
    assert fact_eligible_from_classes("DOCUMENT_SCOPED", "CORPUS_SCOPED")
    assert fact_eligible_from_classes(None, "GLOBAL")          # legacy rows
    assert not fact_eligible_from_classes("MENTION_ONLY", "GLOBAL")
    assert not fact_eligible_from_classes("GLOBAL", "MENTION_ONLY")
    assert not fact_eligible_from_classes("MENTION_ONLY", "MENTION_ONLY")


def test_sql_predicates_are_stable_and_parameter_free():
    e = entity_eligible_sql("e")
    assert e == "e.admission_class IS DISTINCT FROM 'MENTION_ONLY'"
    f = fact_eligible_sql("f")
    assert "f.subject_id" in f and "f.object_id" in f
    assert "MENTION_ONLY" in f
    assert " EXISTS " in f
    # No placeholders: the fragments embed into consumer queries that
    # already use %s for their own parameters.
    assert "%s" not in e and "%s" not in f
    # Eligible and ineligible id queries are complements.
    assert ineligible_fact_ids_sql().startswith(
        "SELECT f.fact_id FROM facts f WHERE NOT ("
    )


def test_sql_predicates_agree_with_pure_predicate_on_classes():
    """The SQL fragment must encode exactly the same rule."""
    # The pure rule is: eligible iff neither endpoint is MENTION_ONLY.
    # The SQL fragment joins entities for both endpoints with
    # IS DISTINCT FROM 'MENTION_ONLY' (NULL=legacy GLOBAL eligible).
    f = fact_eligible_sql("f")
    assert "IS DISTINCT FROM 'MENTION_ONLY'" in f
    assert f.count("IS DISTINCT FROM 'MENTION_ONLY'") == 2


def test_rejected_facts_are_graph_ineligible_qualified_stay():
    """GRAPH-ELIGIBILITY-DECISION-V1: a REJECT decision is Postgres proving
    the edge is not knowledge; QUALIFY is hedged knowledge and stays."""
    assert fact_eligible_from_row("GLOBAL", "GLOBAL", "ACCEPT")
    assert fact_eligible_from_row("GLOBAL", "GLOBAL", "QUALIFY")
    assert not fact_eligible_from_row("GLOBAL", "GLOBAL", "REJECT")
    assert not fact_eligible_from_row("MENTION_ONLY", "GLOBAL", "ACCEPT")
    f = fact_eligible_sql("f")
    assert "f.decision <> 'REJECT'" in f
    assert "QUALIFY" not in f
