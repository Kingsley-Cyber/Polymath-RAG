"""Consolidation migration Phase 5b (AUTO_DECISIONS M-009 §3) — evidence cards, lived clusters, lived situations, hypothesis
anchors and corpus questions are computed AFTER admission, from what TrailSignal ADMITTED, with TrailSignal's independence groups
taken as given. The laws are the imported engine's own (`lived_world.py`).

One operation at a time through the REAL executor. No database, no network.
"""
from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
for _sub in ("workers", "shared"):
    sys.path.insert(0, str(ROOT / _sub))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from polymath_shared.adapter import contracts as C  # noqa: E402
from polymath_shared.adapter import manifest as M  # noqa: E402
from polymath_shared.adapter.transitions import RunState  # noqa: E402
import workers.adapter_step_worker as W  # noqa: E402

HYP = "hyp_" + "a" * 12
HYPOTHESES = [{"hypothesis_id": HYP, "statement": "runners lose small items because pockets bounce", "suspected_friction": "access_interruption"}]


def _exec(operation: str, inputs: dict) -> dict:
    raw = {"adapter_id": "fixture.one_op", "adapter_version": "1.0.0", "workflow_version": "1.0.0", "retrieval_policy_version": "1.0.0", "input_schema_version": "1.0.0",
           "output_schema_version": "1.0.0", "description": "one domain operation", "input_schema": {"type": "object"}, "output_schema": {"type": "object"},
           "budgets": {"max_steps": 4, "max_agent_reason": 0, "max_branch_loops": 0}, "entry_step_id": "op", "terminal_step_id": "end",
           "steps": [{"step_id": "op", "type": "DOMAIN_OPERATION", "title": "op", "next": "end",
                      "config": {"domain": "ecommerce", "operation": operation, "inputs": {k: f"outputs.given.{k}" for k in inputs}}},
                     {"step_id": "end", "type": "COMPILE_RESULT", "title": "end", "next": None, "config": {"include": ["lineage"]}}]}
    assert C.validate("adapter_manifest", raw) == [] and M.graph_integrity_errors(raw) == []
    m = M.Manifest(adapter_id=raw["adapter_id"], adapter_version="1.0.0", workflow_version="1.0.0", retrieval_policy_version="1.0.0", input_schema_version="1.0.0",
                   output_schema_version="1.0.0", entry_step_id="op", terminal_step_id="end", budgets=raw["budgets"], steps={s["step_id"]: s for s in raw["steps"]}, raw=raw)
    state = RunState(run_id="adr_" + "3" * 32, adapter_id=raw["adapter_id"], status="running", input={}, outputs={"given": inputs})
    return W.exec_domain({"run_id": state.run_id, "step_id": "op", "sequence": 1, "step_type": "DOMAIN_OPERATION", "context": {}}, state, m)


def _world(n: int, *, groups: int, threads: int, community: str | None = "r/running", rejected: int = 0):
    """`n` admitted observations spread over `threads` sources and `groups` TrailSignal independence groups (+ `rejected` observations
    the receipt carries but TrailSignal did NOT admit)."""
    sources = [{"source_id": f"src_{t}", "url": f"https://www.reddit.com/r/running/comments/t{t}/", "source_class": "community_discussion",
                "retrieved_at": "2026-09-20T10:00:00Z", "published_at_if_known": "2026-09-10T00:00:00Z"} for t in range(threads)]
    ctx = (f"community: {community} · " if community else "") + "activity: running · moment: during"
    obs = [{"observation_id": f"obs_{i}", "source_id": f"src_{i % threads}", "claim": f"keys bounce out of the pocket mid stride ({i})", "paraphrase_or_excerpt": f"my keys fell out again on the trail {i}",
            "metric_if_present": None, "context": ctx, "evidence_role_claimed": "friction", "hypothesis_ids": [HYP]} for i in range(n + rejected)]
    admitted = [{"admitted_evidence_id": f"fev_{i:04d}", "observation_id": f"obs_{i}", "source_id": f"src_{i % threads}", "evidence_role": "friction" if i else "workaround",
                 "source_class": "community_discussion", "freshness": "fresh", "independence_group": f"grp_{i % groups}", "polarity": "supporting", "hypothesis_ids": [HYP]} for i in range(n)]
    return {"receipts": [{"sources": sources, "observations": obs}], "admissions": [{"admission_id": "hadm_1", "admitted": admitted, "rejected": []}], "hypotheses": HYPOTHESES}


def test_the_code_under_test_is_this_checkout():
    for mod in (C, M, W):
        assert pathlib.Path(mod.__file__).resolve().is_relative_to(ROOT), f"{mod.__name__} resolved outside {ROOT}: {mod.__file__}"


def test_only_admitted_observations_become_field_records_under_the_field_evidence_id():
    out = _exec("population.evidence_cards", _world(5, groups=3, threads=2, rejected=4))["output"]
    assert [r["id"] for r in out["field_records"]] == [f"fev_{i:04d}" for i in range(5)]                    # the ids the agent can cite; the 4 unadmitted observations do not exist here
    assert out["joined"] == {"admitted": 5, "without_observation": 0, "without_community": 0}
    rec = out["field_records"][1]
    assert rec["community"] == "r/running" and rec["moment"] == "during" and rec["friction_family"] == "access_interruption"       # friction family comes from the LINKED ledger hypothesis
    assert rec["evidence_roles"] == ["FRICTION_EVIDENCE"] and rec["independence_group"] == "grp_1" and rec["freshness"] == {"class": "fresh"}
    assert "author_key" not in rec["source_identity"]                                                      # a receipt carries no author; none is invented


def test_anchor_needs_records_threads_and_trailsignals_independent_groups():
    anchor = _exec("population.evidence_cards", _world(5, groups=3, threads=2))["output"]
    assert [c["authority"] for c in anchor["lived_clusters"]] == ["ANCHOR"] and anchor["anchors"] == [anchor["lived_clusters"][0]["id"]]
    assert anchor["lived_clusters"][0]["independent_voices"] == 3 and anchor["lived_clusters"][0]["thread_count"] == 2
    # the SAME five records in two threads, but TrailSignal says they are ONE independent group (e.g. one platform = one voice): THIN.
    one_voice = _exec("population.evidence_cards", _world(5, groups=1, threads=2))["output"]["lived_clusters"][0]
    assert one_voice["authority"] == "THIN" and one_voice["independent_voices"] == 1                       # the engine's own arithmetic would have said 2 — it is not consulted
    few = _exec("population.evidence_cards", _world(4, groups=4, threads=4))["output"]["lived_clusters"][0]
    assert few["authority"] == "THIN" and any("no PURCHASE_INTENT recorded" == u for u in few["unknowns"])


def test_missing_community_is_counted_and_nothing_admitted_is_a_state_not_a_dead_run():
    out = _exec("population.evidence_cards", _world(2, groups=2, threads=2, community=None))["output"]
    assert out["joined"]["without_community"] == 2 and out["lived_clusters"][0]["community"] == "reddit.com"   # falls back to the source host, and says so
    empty = {"receipts": [], "admissions": [{"admission_id": "x", "admitted": []}], "hypotheses": HYPOTHESES}
    nothing = _exec("population.evidence_cards", empty)["output"]                                          # TrailSignal still has to judge a run with no admitted evidence
    assert nothing["field_records"] == [] and nothing["lived_clusters"] == [] and nothing["anchors"] == [] and nothing["round"] == 1
    second = _exec("population.evidence_cards", {**_world(2, groups=2, threads=2), "prior_field_records": [{"id": "fev_old", "community": "r/running", "friction_family": "access_interruption",
                                                                                                          "independence_group": "g_old", "source_identity": {"platform": "forum", "thread_key": "t_old"}}], "prior_round": 1})["output"]
    assert second["round"] == 2 and [r["id"] for r in second["field_records"]] == ["fev_old", "fev_0000", "fev_0001"]                  # research rounds accumulate


def _situation(cluster_id, authority, refs, **extra):
    return {"id": "ls_1", "cluster_id": cluster_id, "authority": authority, "participants": "trail runners", "activity": "running", "moment": "DURING",
            "frictions": [{"text": "keys bounce out", "authority": "FIELD_OBSERVATION", "refs": refs}], "unknowns": ["how often per run"], **extra}


def test_lived_situation_law_anchored_needs_an_anchor_cluster_and_cited_records():
    anchor = _exec("population.evidence_cards", _world(5, groups=3, threads=2))["output"]
    thin = _exec("population.evidence_cards", _world(4, groups=4, threads=4))["output"]
    run = lambda world, sit: _exec("population.validate_situations", {"lived_situations": [sit], "lived_clusters": world["lived_clusters"], "field_records": world["field_records"]})["output"]  # noqa: E731
    on_thin = run(thin, _situation(thin["lived_clusters"][0]["id"], "FIELD_ANCHORED", ["fev_0000"]))
    assert on_thin["valid"] is False and any("is THIN" in e for e in on_thin["errors"])
    invented = run(anchor, _situation(anchor["lived_clusters"][0]["id"], "FIELD_ANCHORED", ["fev_9999"]))
    assert any("must cite known record ids" in e for e in invented["errors"])
    simulated = run(anchor, _situation(anchor["lived_clusters"][0]["id"], "SIMULATED", ["fev_0000"]))
    assert any("not SIMULATED" in e for e in simulated["errors"])
    ok = run(anchor, _situation(anchor["lived_clusters"][0]["id"], "FIELD_ANCHORED", ["fev_0000", "fev_0001"]))
    assert ok == {"valid": True, "errors": [], "situations_checked": 1, "_domain": ok["_domain"]}           # schema-valid AND lawful


_BRIDGE = {"source": "s", "path": ["a", "b", "c"], "evidence_boundary": {"first_inference_at": "b"}, "gaps": ["?"], "status": "WORKING_HYPOTHESIS",
           "alternatives": ["alt"], "falsifiers": ["kill"], "hop_refs": {"0": ["chunk_1"]}}


def test_after_admission_a_hypothesis_anchors_on_an_anchor_cluster_or_declares_corpus_only():
    anchor = _exec("population.evidence_cards", _world(5, groups=3, threads=2))["output"]
    thin = _exec("population.evidence_cards", _world(4, groups=4, threads=4))["output"]
    hyps = lambda **kw: [dict(_BRIDGE, id=f"p{i}", target_mechanism=m, **kw) for i, m in enumerate(("magnet", "clamp", "strap"), 1)]  # noqa: E731
    silent = _exec("hypotheses.validate_bridge", {"hypotheses": hyps(), "lived_clusters": anchor["lived_clusters"]})["output"]
    assert silent["admissible"] is False and any("silence is not a lane" in e for e in silent["anchor_errors"])
    on_thin = _exec("hypotheses.validate_bridge", {"hypotheses": hyps(lived_anchor_ids=[thin["lived_clusters"][0]["id"]]), "lived_clusters": thin["lived_clusters"]})["output"]
    assert any("is THIN" in e for e in on_thin["anchor_errors"])
    good = _exec("hypotheses.validate_bridge", {"hypotheses": hyps(lived_anchor_ids=anchor["anchors"]), "lived_clusters": anchor["lived_clusters"]})["output"]
    assert good["admissible"] is True and good["anchor_errors"] == []
    before_admission = _exec("hypotheses.validate_bridge", {"hypotheses": hyps(grounding="CORPUS_ONLY")})["output"]
    assert before_admission["admissible"] is True and before_admission["anchor_errors"] == []            # no clusters supplied: the anchor laws do not run yet


def test_corpus_questions_come_from_lived_clusters_never_from_hypothesis_statements():
    world = _exec("population.evidence_cards", _world(5, groups=3, threads=2))["output"]
    out = _exec("knowledge.corpus_questions", {"lived_clusters": world["lived_clusters"], "field_records": world["field_records"]})["output"]
    qs = out["corpus_questions"]
    assert qs and all(q["authority_of_answer"] == "CORPUS_EVIDENCE_PACKET" and q["cluster_id"] == world["lived_clusters"][0]["id"] for q in qs)
    assert any("access interruption" in q["question"] for q in qs) and all(HYPOTHESES[0]["statement"] not in q["question"] for q in qs)   # the fix for defect D2
    assert out["need"] and len(out["need"]) <= 2000
    assert _exec("knowledge.corpus_questions", {"lived_clusters": []})["output"]["need"] == ""              # no cluster: the knowledge step keeps its seed need
