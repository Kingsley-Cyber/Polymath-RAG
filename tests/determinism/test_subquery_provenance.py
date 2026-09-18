"""P6 subquery provenance — deterministic lineage contract (SUBQUERY-PROVENANCE-V1).

Proves the acceptance list: every subquery ends with a role (closed vocabulary) + reason
(100 % provenance completeness); q0 (PRIMARY) is always role=direct, never scout-derived, text
untouched (100 % q0 preservation); a scout link survives only when the scout actually nominated
that doc (no fabricated provenance); a profile_surface not among the kept nominations' matched
surfaces is dropped; a None/empty scout degrades cleanly; roles follow the FINAL query type
after the compiler's type-normalization; the receipt carries per-subquery lineage. Pure — no
I/O, no LLM.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))

from pytest import approx  # noqa: E402
from polymath_shared.chat_plan import (  # noqa: E402
    ORIGIN_TYPES, ROLE_TYPES, QUERY_TYPES, ChatPlan, CompiledQuery, default_reason, derive_role,
    fallback_plan, plan_receipt, validate_plan,
)
from polymath_shared.document_profile.profile_scout import (  # noqa: E402
    ProfileNomination, ProfileScoutResult,
)
from polymath_shared.subquery_provenance import (  # noqa: E402
    annotate_subquery_provenance, provenance_complete, provenance_completeness, q0_preserved,
)


def _nom(doc_id, *, rank=1, surfaces=("theme",)):
    return ProfileNomination(
        doc_id=doc_id, fused_score=1.0 / (60 + rank), rank=rank,
        matched_surfaces=tuple(surfaces), surface_types=("profile",),
        representative_surface=surfaces[0] if surfaces else None,
        representative_text="snippet" if surfaces else None,
        contributions=(), provenance=(),
    )


def _scout(*noms):
    return ProfileScoutResult(nominations=tuple(noms))


def _plan(queries):
    p = ChatPlan(
        contract="chat-intent-plan-v1", original_request="q", resolved_request="the resolved q",
        task_type="GROUNDED_QA", evidence_policy="corpus_grounded", retrieval_required=True,
        retrieval_goal=None, queries=queries, semantic_queries=[q.query for q in queries],
        exact_terms=[], entities=[], must_answer=[], user_constraints=[], response_type="answer",
        antecedent=None, graph_useful=False,
    )
    return p


# --- role/reason derivation (deterministic, type-driven) ---------------------------------

def test_every_query_type_maps_to_a_valid_role():
    for qt in QUERY_TYPES:
        assert derive_role(qt) in ROLE_TYPES
    assert derive_role("PRIMARY") == "direct"
    assert derive_role("COMPARISON") == "contrast"
    assert derive_role("COUNTERPOINT") == "inversion"
    assert derive_role("BRIDGE") == "bridge" and derive_role("ADJACENT") == "bridge"
    assert derive_role("DEFINITION") == "prerequisite"
    # unknown type is a supplementary complement, never direct
    assert derive_role("WHATEVER") == "complement"


def test_post_init_derives_role_and_reason_on_bare_query():
    q = CompiledQuery(id="q0", type="PRIMARY", query="x")
    assert q.role == "direct" and q.reason == default_reason("PRIMARY", "direct")
    q2 = CompiledQuery(id="q1", type="MECHANISM", query="y")
    assert q2.role == "complement" and q2.reason.startswith("aspect:mechanism")
    # inspired_by given as a list is normalized to a tuple
    q3 = CompiledQuery(id="q2", type="ENTITY", query="z", inspired_by_profile=["d1", "d2"])
    assert q3.inspired_by_profile == ["d1", "d2"]


def test_explicit_role_is_preserved_over_derivation():
    q = CompiledQuery(id="q0", type="MECHANISM", query="y", role="resolution", reason="round 2 gap")
    assert q.role == "resolution" and q.reason == "round 2 gap"


# --- validate_plan reads planner-supplied provenance -------------------------------------

def test_validate_plan_reads_supplied_provenance():
    raw = {
        "resolved_request": "compare A and B thoroughly",
        "task_type": "GROUNDED_SYNTHESIS", "evidence_policy": "corpus_grounded",
        "retrieval_required": True,
        "queries": [
            {"id": "q0", "type": "PRIMARY", "query": "how A works"},
            {"id": "q1", "type": "MECHANISM", "query": "how B works", "role": "complement",
             "reason": "mechanism of B", "inspired_by": ["docB"], "profile_surface": "theme",
             "target": "entity:B"},
        ],
    }
    plan, err = validate_plan(raw, "compare A and B")
    assert err is None and plan is not None
    q1 = plan.queries[1]
    assert q1.inspired_by_profile == ["docB"] and q1.profile_surface == "theme"
    assert q1.target == "entity:B" and q1.reason == "mechanism of B"


def test_validate_plan_drops_invalid_role_and_derives():
    raw = {
        "resolved_request": "explain the mechanism here",
        "task_type": "GROUNDED_QA", "retrieval_required": True,
        "queries": [{"id": "q0", "type": "PRIMARY", "query": "explain the thing",
                     "role": "not-a-role"}],
    }
    plan, err = validate_plan(raw, "explain the thing")
    assert err is None and plan.queries[0].role == "direct"   # invalid role → derived


def test_role_follows_final_type_after_adjacent_demotion():
    # two ADJACENT queries on a synthesis task: the 2nd is demoted to MECHANISM (ADJACENT_MAX=1);
    # its role must follow the FINAL type, not the ADJACENT it was born as.
    raw = {
        "resolved_request": "synthesize the underlying principle across sources",
        "task_type": "GROUNDED_SYNTHESIS", "retrieval_required": True,
        "queries": [
            {"id": "q0", "type": "PRIMARY", "query": "the asked topic"},
            {"id": "q1", "type": "ADJACENT", "query": "underlying principle one"},
            {"id": "q2", "type": "ADJACENT", "query": "underlying principle two"},
        ],
    }
    plan, err = validate_plan(raw, "synthesize the principle")
    assert err is None
    demoted = [q for q in plan.queries if q.type == "MECHANISM"]
    assert demoted and all(q.role == "complement" for q in demoted)   # not stale 'bridge'
    assert all(q.role in ROLE_TYPES and q.reason for q in plan.queries)


# --- annotate: q0 authority + fabricated-link rejection ----------------------------------

def test_annotate_preserves_q0_and_ignores_claimed_scout_link_on_primary():
    # even if a PRIMARY somehow carried a scout link, q0 stays authoritative.
    q0 = CompiledQuery(id="q0", type="PRIMARY", query="the user question",
                       inspired_by_profile=["docX"], profile_surface="theme")
    plan = _plan([q0])
    block = annotate_subquery_provenance(plan, _scout(_nom("docX")))
    assert plan.queries[0].role == "direct"
    assert plan.queries[0].inspired_by_profile == [] and plan.queries[0].profile_surface is None
    assert plan.queries[0].query == "the user question"   # text untouched
    assert block["q0_preserved"] is True


def test_annotate_keeps_only_real_nominations():
    q0 = CompiledQuery(id="q0", type="PRIMARY", query="primary")
    q1 = CompiledQuery(id="q1", type="MECHANISM", query="aspect",
                       inspired_by_profile=["docReal", "docFake"], profile_surface="theme")
    plan = _plan([q0, q1])
    annotate_subquery_provenance(plan, _scout(_nom("docReal", surfaces=("theme",))))
    assert plan.queries[1].inspired_by_profile == ["docReal"]   # docFake dropped
    assert plan.queries[1].profile_surface == "theme"


def test_annotate_drops_surface_not_in_matched():
    q1 = CompiledQuery(id="q1", type="ENTITY", query="aspect",
                       inspired_by_profile=["docReal"], profile_surface="questions")
    plan = _plan([CompiledQuery(id="q0", type="PRIMARY", query="p"), q1])
    annotate_subquery_provenance(plan, _scout(_nom("docReal", surfaces=("theme", "concepts"))))
    # 'questions' is not among the kept nomination's matched surfaces → dropped
    assert plan.queries[1].inspired_by_profile == ["docReal"]
    assert plan.queries[1].profile_surface is None


def test_annotate_stamps_profile_origin_on_kept_link():
    q0 = CompiledQuery(id="q0", type="PRIMARY", query="primary")
    q1 = CompiledQuery(id="q1", type="MECHANISM", query="aspect", inspired_by_profile=["docReal"])
    plan = _plan([q0, q1])
    annotate_subquery_provenance(plan, _scout(_nom("docReal", surfaces=("theme",))))
    assert plan.queries[0].origin == "USER" and plan.queries[0].origin in ORIGIN_TYPES
    assert plan.queries[1].origin == "PROFILE"          # a surviving scout link ⇒ PROFILE-originated
    # dropped link ⇒ stays USER
    q2 = CompiledQuery(id="q1", type="MECHANISM", query="aspect", inspired_by_profile=["ghost"])
    plan2 = _plan([CompiledQuery(id="q0", type="PRIMARY", query="p"), q2])
    annotate_subquery_provenance(plan2, _scout(_nom("docReal")))
    assert plan2.queries[1].origin == "USER"


def test_validate_plan_reads_origin():
    raw = {"resolved_request": "explain the mechanism here", "task_type": "GROUNDED_QA",
           "retrieval_required": True,
           "queries": [{"id": "q0", "type": "PRIMARY", "query": "explain the thing",
                        "origin": "graph"}]}
    plan, err = validate_plan(raw, "explain the thing")
    assert err is None and plan.queries[0].origin == "GRAPH"


def test_annotate_with_no_scout_degrades_cleanly():
    q0 = CompiledQuery(id="q0", type="PRIMARY", query="p")
    q1 = CompiledQuery(id="q1", type="MECHANISM", query="a", inspired_by_profile=["docX"])
    plan = _plan([q0, q1])
    block = annotate_subquery_provenance(plan, None)
    assert block["scout_present"] is False and block["scout_nominations"] == []
    assert plan.queries[1].inspired_by_profile == []   # nothing to link against
    assert provenance_complete(plan) and block["q0_preserved"] is True


# --- completeness / preservation metrics -------------------------------------------------

def test_provenance_completeness_full_on_normal_plan():
    plan = _plan([CompiledQuery(id="q0", type="PRIMARY", query="p"),
                  CompiledQuery(id="q1", type="MECHANISM", query="a")])
    annotate_subquery_provenance(plan, None)
    assert provenance_completeness(plan) == approx(1.0)
    assert provenance_complete(plan) and q0_preserved(plan)


def test_no_retrieval_plan_is_vacuously_preserved_and_complete():
    plan = _plan([])
    block = annotate_subquery_provenance(plan, None)
    assert block["q0_preserved"] is True and block["provenance_completeness"] == approx(1.0)
    assert block["subqueries"] == []


def test_fallback_plan_is_q0_preserved_and_complete():
    plan = fallback_plan("just the raw message", reason="transport:x")
    annotate_subquery_provenance(plan, None)
    assert q0_preserved(plan) and provenance_complete(plan)
    assert plan.queries[0].type == "PRIMARY" and plan.queries[0].role == "direct"


# --- receipt carries lineage -------------------------------------------------------------

def test_provenance_fields_are_json_stable():
    # inspired_by_profile must be a LIST, not a tuple — plan receipts round-trip through JSON,
    # and a tuple () would deserialize to [] and break equality of the two receipt copies.
    import json
    q = CompiledQuery(id="q1", type="MECHANISM", query="x", inspired_by_profile=("docA", "docB"))
    assert isinstance(q.inspired_by_profile, list)
    plan = _plan([CompiledQuery(id="q0", type="PRIMARY", query="p"), q])
    annotate_subquery_provenance(plan, _scout(_nom("docA"), _nom("docB")))
    rec = plan_receipt(plan)
    assert rec == json.loads(json.dumps(rec))     # JSON round-trip is identity (no tuples anywhere)


def test_plan_receipt_carries_subquery_lineage():
    plan = _plan([CompiledQuery(id="q0", type="PRIMARY", query="p"),
                  CompiledQuery(id="q1", type="COMPARISON", query="other side")])
    annotate_subquery_provenance(plan, _scout(_nom("docA")))
    rec = plan_receipt(plan)
    assert rec["subquery_provenance"]["contract"] == "subquery-provenance-v1"
    # per-query fields are present in the receipt's query list
    q1 = next(q for q in rec["queries"] if q["id"] == "q1")
    assert q1["role"] == "contrast" and q1["reason"]
    assert rec["subquery_provenance"]["subqueries"][0]["role"] == "direct"
