"""Neo4j projection eligibility (entity admission boundary).

ONE deterministic predicate defines which entities and facts are
Neo4j-eligible, shared by the three consumers that must agree:

  - project_neo4j_worker : projects only eligible entities/facts;
  - control census        : receipt expectations exclude ineligible
                            facts (parked facts are NOT projection
                            failures, and no synthetic receipts exist);
  - verify_worker         : reconciles edges/receipts only for
                            eligible facts; edges of ineligible facts
                            are removed, their receipts cleared.

Rule:
  an entity is eligible iff admission_class != 'MENTION_ONLY'
  (NULL = legacy pre-0007 rows are eligible);
  a fact is eligible iff BOTH endpoints are eligible entities
  AND its decision is not REJECT (GRAPH-ELIGIBILITY-DECISION-V1,
  2026-09-02: REL edges carry only predicate + fact_id and the GRAPH lane
  does not consult decisions, so a retired fact stayed servable; 13
  pronoun-endpoint facts retired to REJECT kept their 13 edges through a
  reconcile). QUALIFY stays eligible (hedged knowledge is projected and
  withheld by authorization — P9). REJECT = Postgres proving the edge is
  not knowledge; the verify reconciler removes it.
MENTION_ONLY-dependent facts stay parked in Postgres by design.

S4c — why this is NOT a second eligibility authority. SQL cannot call
`graph_eligible()`, so this reads a column. Under admission-harbor-v2 that
column is WRITTEN as the projection of that one predicate:

    MentionIdentity.admission_class == scope        if graph_eligible(d)
                                    == 'MENTION_ONLY' otherwise

so an ineligible decision is stored as MENTION_ONLY whatever its scope, and
this predicate reproduces `graph_eligible()` exactly rather than re-deriving
it. The projection is held by test_s4c_single_path.py; if it ever breaks,
these three consumers drift together, not apart.
"""
from __future__ import annotations

ADMITTED_SQL = "admission_class IS DISTINCT FROM 'MENTION_ONLY'"


def entity_eligible_sql(alias: str = "e") -> str:
    """SQL predicate for an eligible entity row (admission column)."""
    return f"{alias}.admission_class IS DISTINCT FROM 'MENTION_ONLY'"


def fact_eligible_sql(f_alias: str = "f") -> str:
    """SQL predicate for an eligible fact row: both endpoints admitted."""
    return (
        f"EXISTS (SELECT 1 FROM entities {f_alias}_s"
        f" WHERE {f_alias}_s.entity_id = {f_alias}.subject_id"
        f" AND {f_alias}_s.admission_class IS DISTINCT FROM 'MENTION_ONLY')"
        f" AND EXISTS (SELECT 1 FROM entities {f_alias}_o"
        f" WHERE {f_alias}_o.entity_id = {f_alias}.object_id"
        f" AND {f_alias}_o.admission_class IS DISTINCT FROM 'MENTION_ONLY')"
        f" AND {f_alias}.decision <> 'REJECT'"
    )


def fact_eligible_from_row(subject_class: str | None, object_class: str | None,
                           decision: str = "ACCEPT") -> bool:
    """Pure predicate over a fact row: endpoint classes + decision."""
    return fact_eligible_from_classes(subject_class, object_class) and decision != "REJECT"


def fact_eligible_from_classes(subject_class: str | None,
                               object_class: str | None) -> bool:
    """Pure predicate over persisted admission classes (deterministic).

    None (legacy pre-0007 rows) means GLOBAL and is eligible."""
    return (subject_class != "MENTION_ONLY") and (object_class != "MENTION_ONLY")


def eligible_fact_ids_sql() -> str:
    """All globally eligible fact ids (corpus-independent: eligibility
    is a property of a fact's endpoint entities, not of its corpus)."""
    return "SELECT f.fact_id FROM facts f WHERE " + fact_eligible_sql("f")


def ineligible_fact_ids_sql() -> str:
    return (
        "SELECT f.fact_id FROM facts f WHERE NOT ("
        + fact_eligible_sql("f") + ")"
    )
