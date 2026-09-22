"""The deterministic verification shell's own tests — the ONLY authority on the gate (docs/migration/DETERMINISTIC_VERIFICATION_SHELL.md §4, §7).

  * HISTORICAL fixture: run 5 (`adr_c994b32a…`, adapter 0.1.0, exported read-only) must FAIL, and at the stages the audit found — T5 (priors
    without meaning), T6 (unbound `{slot}` templates, no intent provenance), T9 (no plan / join) — plus T3 (a pre-restoration ledger names no
    origin). The gate must reproduce the audit, not rubber-stamp.
  * SYNTHETIC fixture: a minimal run that satisfies every stage must PASS; one mutation per stage must flip exactly that stage; an
    infrastructure failure is NOT_EVALUABLE, a lawful early end makes T10 SKIP_LAWFUL, a software failure is FAIL at T11.
  * DETERMINISM: the same run state gives byte-identical JSON.
  * PREFLIGHT: the manifest's pinned seed passes; a presupposing seed is refused.
No database, no network, no LLM."""
from __future__ import annotations

import copy
import json
import pathlib
import subprocess
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
GATE = ROOT / "scripts" / "semantic_restoration_gate.py"
MANIFEST = ROOT / "config" / "benchmarks" / "cinema-transduction-v1.yaml"
RUN5 = ROOT / "tests" / "fixtures" / "benchmark_gate" / "run5_adr_c994b32a.json.gz"
SEED_S1 = "How a camera crew keeps equipment working through a shooting day — who handles what, what is moved between setups, and what repeatedly goes wrong in hand-offs."

sys.path.insert(0, str(ROOT / "scripts"))
import semantic_restoration_gate as G  # noqa: E402


def _gate(argv: list[str]) -> tuple[int, dict]:
    out = pathlib.Path(__import__("tempfile").mkdtemp()) / "verdict.json"
    p = subprocess.run([sys.executable, str(GATE), *argv, "--json", str(out)], cwd=ROOT, capture_output=True, text=True)
    return p.returncode, json.loads(out.read_text(encoding="utf-8"))


def _stages(verdict: dict) -> dict[str, str]:
    return {c["id"]: c["status"] for c in verdict["checks"]}


# ─────────────────────────────────────────────────────────── historical: run 5 must FAIL where the audit said
def test_run5_fails_and_at_the_stages_the_audit_found():
    code, v = _gate(["--phase", "benchmark", "--run-file", str(RUN5), "--manifest", str(MANIFEST)])
    st = _stages(v)
    assert code == 1 and v["overall"] == "FAIL" and v["target"]["adapter_version"] == "0.1.0"
    assert st["T5"] == "FAIL" and st["T6"] == "FAIL" and st["T9"] == "FAIL" and st["T3"] == "FAIL"
    facts = {c["id"]: c["facts"] for c in v["checks"]}
    assert facts["T5"]["priors_without_meaning"] == facts["T5"]["priors"] > 0 and facts["T5"]["mapping_paths"] == ["None"]
    assert any("unbound placeholder" in i for i in facts["T6"]["issues"]) and facts["T6"]["observations_tagged"] == 0
    assert facts["T9"]["jobs"] == 0 and facts["T9"]["concepts_without_job"]
    assert st["T11"] == "PASS" and facts["T11"]["outcome"] == "HARD_GATE_UNMET"          # a lawful refusal is a PASS at T11, never a failure


def test_run5_verdict_is_byte_deterministic():
    _, a = _gate(["--phase", "benchmark", "--run-file", str(RUN5), "--manifest", str(MANIFEST)])
    _, b = _gate(["--phase", "benchmark", "--run-file", str(RUN5), "--manifest", str(MANIFEST)])
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


# ─────────────────────────────────────────────────────────── synthetic: a run that satisfies every stage
H1, H2 = "hyp_" + "a" * 24, "hyp_" + "b" * 24
RUN = "adr_" + "7" * 32


def _synthetic() -> dict:
    seed = "How a camera crew keeps equipment working through a shooting day"
    lead = {"id": "lead_1", "kind": "POPULATION", "name": "lone landscape photographers", "source_lane": "LATENT", "search_mode": "LATENT", "voi": 0.4, "seed_population": False}
    lead2 = {"id": "lead_2", "kind": "POPULATION", "name": "camera assistants", "source_lane": "CORPUS", "voi": 0.2, "seed_population": True}
    structure = {"id": "ls_1", "kind": "role_collapse", "statement": "one person operates and tends the tool"}
    state1 = {"hypothesis_id": H1, "statement": "photographers miss shots digging for batteries", "population": "lone landscape photographers", "lead_ids": ["lead_1"], "latent_structure_ids": ["ls_1"], "contradictions": [{"id": "ctr_1", "evidence_id": "fev_2"}]}
    state2 = {"hypothesis_id": H2, "statement": "assistants lose media between setups", "population": "camera assistants", "lead_ids": ["lead_2"], "latent_structure_ids": []}
    outputs = {
        "C_primitives": {"primitives": {"frictions": ["consumables live away from the point of use"], "transferable_invariants": ["tending interrupts operating"], "evidence_refs": {"frictions": ["chunk_1"]}}},
        "C_lineage": {"latent_structures": [structure]},
        "C_population": {"population_leads": [lead, lead2], "ranked_lead_ids": ["lead_1", "lead_2"]},
        "C_hypotheses": {"hypothesis_ids": [H1, H2]},
        "C_bridge": {"bridges": [{"hypothesis_id": H1, "path": ["set: media kept away", "lone operator has no runner", "spares buried in the pack"], "grounding": "CORPUS_ONLY",
                                  "gaps": ["do lone photographers report it?"], "falsifiers": ["pack access is quick"], "evidence_boundary": {"first_inference_at": "lone operator has no runner"}}]},
        "D_project": {"priors": [{"registry_record_id": "fr-12", "prior_role": "friction_primitive", "label": "buried_accessories", "section": "friction_primitives", "match_strength": 0.9, "mapping_path": "structured", "hypothesis_ids": [H1]}]},
        "O_territory": {"territories": [{"territory_id": "pt-06", "territory_name": "camera carry", "mapping_path": "lexical", "hypothesis_ids": [H1]}]},
        "N_concepts": {"mechanisms": [{"id": "m_1", "hypothesis_id": H1, "name": "strap-mounted carry"}],
                       "product_concepts": [{"id": "pc_1", "name": "Universal strap camera mount", "buyer": "lone photographers", "form_factor": "strap clamp", "target_moment": "walking between shots", "mechanism_id": "m_1", "problem": "camera buried in the pack"}]},
        "O_plan": {"reality_plan": [{"job_id": "job_pc_1", "concept_id": "pc_1", "hypothesis_id": H1, "query": "strap camera mount review"}]},
        "Q_join": {"existing_products": [{"observation_id": "obs_9", "concept_id": "pc_1", "job_id": "job_pc_1", "relation": "solves"}], "concept_reality": [{"concept_id": "pc_1", "status": "EXISTING_PRODUCTS_FOUND"}], "joined": {"joined": 1}},
        "S_plan": {"sourcing_plan": []}, "S_supply": {"sources": []}, "T_admit": {"evidence_admission": {}}, "T_leads": {"leads": []},
        "V_score": {"trail_scores": [], "score_refusals": [{"hypothesis_id": H1, "reason_code": "HARD_GATE_UNMET"}]},
    }
    intent = {"intent_id": "gap_h1_0:reddit", "hypothesis_id": H1, "gap_id": "gap_h1_0", "query": "landscape photographer spare battery buried pack", "evidence_goal": "complaint"}
    steps = [{"sequence": 7, "step_id": "C_primitives", "step_type": "AGENT_REASON", "status": "accepted", "harness_action": None, "context_hypothesis_ids": [], "context_evidence_ref_ids": ["chunk_1", "chunk_2"], "submission": None, "output": None, "receipt_failure": None},
             {"sequence": 23, "step_id": "I_research", "step_type": "HARNESS_ACTION", "status": "accepted", "harness_action": {"action_kind": "AGENT_RESEARCH", "search_intents": [intent], "evidence_gaps": [{"gap_id": "gap_h1_0", "hypothesis_id": H1}]},
              "context_hypothesis_ids": [H1, H2], "context_evidence_ref_ids": [], "submission": None, "output": None, "receipt_failure": None},
             {"sequence": 31, "step_id": "K_revise", "step_type": "AGENT_REASON", "status": "accepted", "harness_action": None, "context_hypothesis_ids": [H1, H2], "context_evidence_ref_ids": ["fev_1"],
              "submission": {"transitions": [{"kind": "REVISE", "hypothesis_id": H1, "cause_refs": [{"kind": "field_evidence", "id": "fev_1"}]}]}, "output": None, "receipt_failure": None}]
    admitted = [{"evidence_id": "fev_1", "action_id": "hact_1", "observation_id": "obs_1", "evidence_role": "friction", "polarity": "supporting", "independence_group": "reddit", "hypothesis_ids": [H1],
                 "record": {"context": "forum thread; intent: gap_h1_0:reddit", "hypothesis_relations": [{"hypothesis_id": H1, "relation": "SUPPORTS"}]}},
                {"evidence_id": "fev_2", "action_id": "hact_1", "observation_id": "obs_2", "evidence_role": "behavior", "polarity": "contradicting", "independence_group": "blog", "hypothesis_ids": [H1],
                 "record": {"context": "blog; intent: gap_h1_0:reddit", "hypothesis_relations": [{"hypothesis_id": H1, "relation": "CONTRADICTS"}]}}]
    return {"run_id": RUN, "adapter_id": "ecommerce.product_research", "adapter_version": "0.6.0", "status": "completed", "input": {"seed": seed}, "outputs": outputs, "output_order": list(outputs),
            "gap": None, "failure": None, "request_options": {}, "steps": steps,
            "hypotheses": [{"hypothesis_id": H1, "revision": 2, "status": "revised", "state": state1}, {"hypothesis_id": H2, "revision": 0, "status": "proposed", "state": state2}], "admitted": admitted}


def _run(run: dict) -> tuple[int, dict]:
    path = pathlib.Path(__import__("tempfile").mkdtemp()) / "run.json"
    path.write_text(json.dumps(run), encoding="utf-8")
    return _gate(["--phase", "benchmark", "--run-file", str(path), "--manifest", str(MANIFEST)])


def test_a_run_that_satisfies_every_stage_passes():
    code, v = _run(_synthetic())
    assert code == 0 and v["overall"] == "PASS", _stages(v)
    assert all(s == "PASS" for s in _stages(v).values()) and set(_stages(v)) == {f"T{i}" for i in range(1, 12)}
    assert {c["id"]: c["facts"] for c in v["checks"]}["T11"]["outcome"] == "HARD_GATE_UNMET"


def _mutate(fn):
    r = _synthetic(); fn(r); return r


@pytest.mark.parametrize("stage, mutate", [
    ("T1", lambda r: r["outputs"]["C_primitives"]["primitives"].update(transferable_invariants=[])),
    ("T1", lambda r: r["outputs"]["C_primitives"]["primitives"]["evidence_refs"].update(frictions=["chunk_invented"])),
    ("T2", lambda r: r["outputs"]["C_population"]["population_leads"][0].update(source_lane="CORPUS", search_mode=None)),   # no LATENT candidate considered
    ("T3", lambda r: r["hypotheses"][0]["state"].update(lead_ids=["lead_unknown"])),
    ("T4", lambda r: r["outputs"]["C_bridge"]["bridges"][0]["evidence_boundary"].update(first_inference_at="not a hop")),
    ("T5", lambda r: r["outputs"]["D_project"]["priors"][0].pop("label")),
    ("T5", lambda r: r["outputs"]["O_territory"]["territories"][0].pop("territory_name")),
    ("T6", lambda r: r["steps"][1]["harness_action"]["search_intents"][0].update(query="{activity} {task} annoying")),
    ("T6", lambda r: r["admitted"][0]["record"].update(context="forum; intent: never_issued")),
    ("T7", lambda r: r["admitted"][0]["record"]["hypothesis_relations"].append({"hypothesis_id": H2, "relation": "SUPPORTS"})),   # a relation to an unlinked hypothesis
    ("T7", lambda r: r["steps"][2]["submission"]["transitions"][0].update(cause_refs=[{"kind": "field_evidence", "id": "fev_ghost"}])),
    ("T8", lambda r: r["outputs"]["N_concepts"]["product_concepts"][0].update(mechanism_id="m_missing")),
    ("T9", lambda r: r["outputs"]["O_plan"].update(reality_plan=[])),
    ("T10", lambda r: r["outputs"].pop("T_leads")),
    ("T11", lambda r: r.update(status="terminal_gap", gap={"code": "STEP_EXECUTOR_ERROR", "message": "KeyError: 'x'"})),
])
def test_one_mutation_flips_exactly_that_stage(stage, mutate):
    code, v = _run(_mutate(mutate))
    st = _stages(v)
    assert code == 1 and v["overall"] == "FAIL" and st[stage] == "FAIL", (stage, st)
    assert [k for k, s in st.items() if s != "PASS"] == [stage]


def test_an_infrastructure_failure_is_not_evaluable_never_a_thesis_failure():
    _, v = _run(_mutate(lambda r: r.update(status="failed", failure={"code": "STEP_EXECUTOR_ERROR", "message": "httpx.ConnectTimeout: provider timed out"})))
    assert v["overall"] == "NOT_EVALUABLE" and _stages(v)["T11"] == "NOT_EVALUABLE"


def test_supply_is_skip_lawful_when_every_concept_was_contested_before_supply():
    def mutate(r):
        r["outputs"]["Q_join"]["concept_reality"][0]["status"] = "EXISTING_PRODUCT_CONTESTS"
        for k in ("S_plan", "S_supply", "T_admit", "T_leads"):
            r["outputs"].pop(k)
        r["output_order"] = list(r["outputs"])
    code, v = _run(_mutate(mutate))
    assert code == 0 and v["overall"] == "PASS" and _stages(v)["T10"] == "SKIP_LAWFUL"


def test_an_unfinished_run_is_not_adjudicated():
    _, v = _run(_mutate(lambda r: r.update(status="awaiting_agent")))
    assert v["overall"] == "NOT_EVALUABLE" and _stages(v) == {"T0": "NOT_EVALUABLE"}


def test_the_manifest_can_forbid_a_terminal_state():
    r = _synthetic()
    path = pathlib.Path(__import__("tempfile").mkdtemp()); (path / "run.json").write_text(json.dumps(r), encoding="utf-8")
    (path / "m.yaml").write_text(MANIFEST.read_text(encoding="utf-8").replace("allowed_terminal_states: [SCORED, HARD_GATE_UNMET,", "allowed_terminal_states: [SCORED,"), encoding="utf-8")
    _, v = _gate(["--phase", "benchmark", "--run-file", str(path / "run.json"), "--manifest", str(path / "m.yaml")])
    assert _stages(v)["T11"] == "FAIL"


# ─────────────────────────────────────────────────────────── preflight
def test_preflight_accepts_the_pinned_seed_and_refuses_a_presupposing_one():
    code, v = _gate(["--phase", "benchmark", "--preflight", "--manifest", str(MANIFEST), "--seed", SEED_S1])
    assert code == 0 and v["overall"] == "PASS"
    code, v = _gate(["--phase", "benchmark", "--preflight", "--manifest", str(MANIFEST), "--seed", "Hikers who need a camera backpack clip"])
    assert code == 1 and _stages(v)["B1"] == "FAIL" and _stages(v)["B2"] == "FAIL"
    assert {c["id"]: c["facts"] for c in v["checks"]}["B2"]["forbidden_terms_found"] == ["backpack", "clip", "hikers"]


def test_the_gate_version_is_the_manifests():
    import yaml
    assert yaml.safe_load(MANIFEST.read_text(encoding="utf-8"))["gate_version"] == G.GATE_VERSION == "1.0.0"
