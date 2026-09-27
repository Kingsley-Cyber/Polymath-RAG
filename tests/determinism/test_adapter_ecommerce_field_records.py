"""TRAIL-EXT-BUGHUNT-V1 batch C — what the lived world is built from: the lineage law's word lists and the admitted field records.

B-31 the lineage law names a friction / shared predicate / community written as an object (population nomination reads them as
words) · B-54 a record sits in the cluster of a hypothesis TrailSignal says it SUPPORTS (ADR-069 per-hypothesis relation), never
counted as support for one it contradicts · B-60 a record TrailSignal marks `duplicate_of` another is kept citable but counted once.

One operation at a time through the REAL executor (`exec_domain`, the binding out of process). No database, no network. Every text is
synthetic.
"""
from __future__ import annotations

import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
for _sub in ("workers", "shared"):
    sys.path.insert(0, str(ROOT / _sub))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import workers.adapter_step_worker as W
from polymath_shared.adapter import contracts as C
from polymath_shared.adapter import manifest as M
from polymath_shared.adapter.transitions import RunState

H1, H2 = "hyp_" + "a" * 12, "hyp_" + "b" * 12
ROWS = [{"id": "ch_0", "text": "a synthetic passage about cold hands and small camera dials", "kind": "chunk"}]
LAWFUL = {"generative_signal": True, "row_relevance": {"ch_0": "SEMANTIC_MATCH"}, "evidence_refs": {"frictions": ["ch_0"]},
          "frictions": ["access_interruption"], "shared_predicates": ["access"], "communities": ["r/photography"]}
HYPOTHESES = [{"hypothesis_id": H1, "statement": "gloved hands cannot reach the dial", "suspected_friction": "access_interruption"},
              {"hypothesis_id": H2, "statement": "cold fingers lose their grip", "suspected_friction": "grip_loss"}]


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
    state = RunState(run_id="adr_" + "8" * 32, adapter_id=raw["adapter_id"], status="running", input={}, outputs={"given": inputs})
    return W.exec_domain({"run_id": state.run_id, "step_id": "op", "sequence": 1, "step_type": "DOMAIN_OPERATION", "context": {}}, state, m)


def _cards(records: list[dict]) -> dict:
    """records: {i, hyps, polarity, relations, duplicate_of, thread} -> population.evidence_cards over them."""
    sources = [{"source_id": f"src_{r['thread']}", "url": f"https://www.reddit.com/r/photography/comments/t{r['thread']}/", "source_class": "community_discussion",
                "retrieved_at": "2026-09-26T10:00:00Z", "published_at_if_known": None} for r in records]
    obs = [{"observation_id": f"obs_{r['i']}", "source_id": f"src_{r['thread']}", "claim": f"my fingers go numb on the dial ({r['i']})",
            "paraphrase_or_excerpt": f"synthetic quote {r['i']}", "context": "community: r/photography · moment: during"} for r in records]
    admitted = [{"admitted_evidence_id": f"fev_{r['i']}", "observation_id": f"obs_{r['i']}", "source_id": f"src_{r['thread']}", "evidence_role": "friction",
                 "source_class": "community_discussion", "freshness": "fresh", "independence_group": f"grp_{r['i'] % 3}", "polarity": r.get("polarity", "supporting"),
                 "duplicate_of": r.get("duplicate_of"), "hypothesis_ids": r["hyps"], **({"hypothesis_relations": r["relations"]} if r.get("relations") else {})}
                for r in records]
    return _exec("population.evidence_cards", {"receipts": [{"sources": sources, "observations": obs}], "admissions": [{"admitted": admitted, "rejected": []}],
                                                "hypotheses": HYPOTHESES})["output"]


def test_the_code_under_test_is_this_checkout():
    for mod in (C, M, W):
        assert pathlib.Path(mod.__file__).resolve().is_relative_to(ROOT), f"{mod.__name__} resolved outside {ROOT}: {mod.__file__}"


# ─────────────────────────────────────────────────────────── B-31: the lineage law and the words population nomination reads
def test_a_lawful_interpretation_with_word_lists_still_passes():
    out = _exec("understanding.validate_primitives", {"primitives": LAWFUL, "corpus_evidence": ROWS})["output"]
    assert out["valid"] is True and out["errors"] == []


@pytest.mark.parametrize("change, needle", [
    ({"frictions": [{"text": "gloves block fine dial control", "evidence_refs": ["ch_0"]}]}, "primitives.frictions[0]: expected a string"),
    ({"shared_predicates": [["access", "retain"]]}, "primitives.shared_predicates[0]: expected a string"),
    ({"communities": [{"name": "r/photography"}]}, "primitives.communities[0]: expected a string"),
    ({"frictions": "gloves block fine dial control"}, "primitives.frictions: expected a list of strings"),
])
def test_the_lineage_law_names_a_word_written_as_an_object(change, needle):
    prim = {**LAWFUL, **change}
    out = _exec("understanding.validate_primitives", {"primitives": prim, "corpus_evidence": ROWS})["output"]
    assert out["valid"] is False and any(e.startswith(needle) for e in out["errors"]), out["errors"]
    nominated = _exec("population.nominate", {"signal": "cold hands and small camera dials", "primitives": prim, "corpus_evidence": ROWS})
    assert nominated.get("output", {}).get("ranked_lead_ids") or nominated.get("gap"), nominated          # and nomination answers, never crashes


# ─────────────────────────────────────────────────────────── B-54: TrailSignal's relation decides which cluster a record strengthens
def test_a_record_that_supports_h2_and_contradicts_h1_strengthens_h2s_cluster_only():
    rows = [{"i": i, "thread": i % 2, "hyps": [H1, H2], "relations": [{"hypothesis_id": H1, "relation": "CONTRADICTS"}, {"hypothesis_id": H2, "relation": "SUPPORTS"}]}
            for i in range(5)]
    out = _cards(rows)
    rec = out["field_records"][0]
    assert (rec["friction_family"], rec["contradicts"], rec["polarity"], rec["contradicts_hypothesis_ids"]) == ("grip_loss", False, "supporting", [H1])
    assert [(c["friction_family"], c["record_count"], c["authority"]) for c in out["lived_clusters"]] == [("grip_loss", 5, "ANCHOR")]


def test_a_record_that_contradicts_its_only_hypothesis_stays_out_of_its_cluster():
    out = _cards([{"i": 0, "thread": 0, "hyps": [H1], "relations": [{"hypothesis_id": H1, "relation": "CONTRADICTS"}]},
                  {"i": 1, "thread": 1, "hyps": [H1]}])
    recs = {r["id"]: r for r in out["field_records"]}
    assert recs["fev_0"]["contradicts"] is True and recs["fev_0"]["contradicts_hypothesis_ids"] == [H1] and recs["fev_1"]["contradicts_hypothesis_ids"] == []
    assert [c["record_ids"] for c in out["lived_clusters"]] == [["fev_1"]]


# ─────────────────────────────────────────────────────────── B-60: TrailSignal's duplicates count once
def test_a_trail_duplicate_is_counted_once_and_stays_citable():
    out = _cards([{"i": 0, "thread": 0, "hyps": [H1]}, {"i": 1, "thread": 1, "hyps": [H1], "duplicate_of": "fev_0"}])
    assert out["joined"]["duplicates"] == 1
    (cluster,) = out["lived_clusters"]
    assert (cluster["record_count"], cluster["thread_count"], cluster["record_ids"]) == (1, 1, ["fev_0"])
    assert {r["id"]: r.get("duplicate_of") for r in out["field_records"]} == {"fev_0": None, "fev_1": "fev_0"}      # still an id the agent may cite
