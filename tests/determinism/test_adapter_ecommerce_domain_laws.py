"""TRAIL-EXT-BUGHUNT-V1 B-01 / B-08 / B-09 — the domain LAWS answer every submission with a verdict, and the bridge law reads the ledger.

A law step's verdict is an OUTPUT the manifest branches on: back to reasoning while repair budget is left, else a typed refusal. A
shape the law could not read used to crash the out-of-process binding (exit 1); the runtime records that as STEP_EXECUTOR_ERROR, a
FAILED run whose repair loop never runs. Every shape below is one the manifest's output schemas leave open to the agent.

One operation at a time through the REAL executor (`exec_domain`, the binding out of process). No database, no network. Text is
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

H1, H2, H3 = "hyp_" + "a" * 12, "hyp_" + "b" * 12, "hyp_" + "c" * 12
ROWS = [{"id": f"ch_{i}", "text": f"synthetic passage {i} about cold hands and small dials", "kind": "chunk"} for i in range(3)]
LAWFUL_PRIMITIVES = {"generative_signal": True, "row_relevance": {"ch_0": "SEMANTIC_MATCH", "ch_1": "LEXICAL_MATCH"},
                     "evidence_refs": {"frictions": ["ch_0"]}, "frictions": ["access_interruption"], "shared_predicates": ["access"]}


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
    state = RunState(run_id="adr_" + "5" * 32, adapter_id=raw["adapter_id"], status="running", input={}, outputs={"given": inputs})
    return W.exec_domain({"run_id": state.run_id, "step_id": "op", "sequence": 1, "step_type": "DOMAIN_OPERATION", "context": {}}, state, m)


def test_the_code_under_test_is_this_checkout():
    for mod in (C, M, W):
        assert pathlib.Path(mod.__file__).resolve().is_relative_to(ROOT), f"{mod.__name__} resolved outside {ROOT}: {mod.__file__}"


# ─────────────────────────────────────────────────────────── B-01: C_lineage (understanding.validate_primitives)
def test_a_lawful_interpretation_still_passes_the_lineage_law():
    out = _exec("understanding.validate_primitives", {"primitives": LAWFUL_PRIMITIVES, "corpus_evidence": ROWS})["output"]
    assert out["valid"] is True and out["errors"] == [] and out["row_relevance"]["ch_0"] == "SEMANTIC_MATCH"


@pytest.mark.parametrize("change, needle", [
    ({"evidence_refs": ["ch_0"]}, "primitives.evidence_refs: expected an object"),                                   # a flat list of ids
    ({"evidence_refs": {"frictions": "ch_0"}}, "primitives.evidence_refs.frictions: expected a list of evidence ids"),  # one id, not a list
    ({"evidence_refs": {"frictions": [{"kind": "chunk", "id": "ch_0"}]}}, "is not an evidence id"),                   # the {kind, id} ref shape
    ({"row_relevance": {"ch_0": {"class": "SEMANTIC_MATCH", "why": "names the friction"}}}, "row_relevance[ch_0]"),  # a class with a reason
    ({"row_relevance": [{"id": "ch_0", "class": "SEMANTIC_MATCH"}]}, "row_relevance: expected an object"),            # a list of rows
    ({"latent_structures": ["cold hands make small dials hard"]}, "latent_structures[0]: latent_structure: not an object"),
    ({"latent_structures": "cold hands make small dials hard"}, "latent_structures: expected a list of objects"),
    ({"corpus_observations": [["ch_0"]]}, "corpus_observations[0]: corpus_observation: not an object"),
])
def test_the_lineage_law_answers_a_malformed_interpretation_with_named_errors(change, needle):
    out = _exec("understanding.validate_primitives", {"primitives": {**LAWFUL_PRIMITIVES, **change}, "corpus_evidence": ROWS})["output"]
    assert out["valid"] is False and any(needle in e for e in out["errors"]), out["errors"]


# ─────────────────────────────────────────────────────────── B-01: K_situations_law (population.validate_situations)
def test_the_situations_law_answers_object_refs_and_a_list_cluster_id_and_still_judges_the_rest():
    object_refs = {"id": "ls_1", "authority": "RECONSTRUCTED", "unknowns": ["how often"], "evidence_refs": ["fev_1"],
                   "frictions": [{"text": "dials too small in gloves", "authority": "FIELD_OBSERVATION", "refs": [{"kind": "field_evidence", "id": "fev_1"}]}]}
    list_cluster = {"id": "ls_2", "authority": "RECONSTRUCTED", "unknowns": ["how often"], "cluster_id": ["cl_1", "cl_2"]}
    biography = {"id": "ls_3", "authority": "RECONSTRUCTED", "unknowns": [], "evidence_refs": ["fev_1"]}          # well-formed, unlawful
    out = _exec("population.validate_situations", {"lived_situations": [object_refs, list_cluster, biography], "lived_clusters": [],
                                                   "field_records": [{"id": "fev_1"}]})["output"]
    assert out["valid"] is False and out["situations_checked"] == 3
    assert any(e.startswith("lived_situations[0]: lived_situation.frictions[0].refs[0]: expected string") for e in out["errors"]), out["errors"]
    assert any(e.startswith("lived_situations[1]: lived_situation.cluster_id: expected string") for e in out["errors"]), out["errors"]
    assert any("ls_3: a reconstruction with no unknowns is a biography" in e for e in out["errors"])              # the law still judges the well-formed one


# ─────────────────────────────────────────────────────────── B-01: C_bridge_law (hypotheses.validate_bridge)
def _bridge(hid: str, mech: str, hop_refs=None) -> dict:
    return {"hypothesis_id": hid, "source": "a synthetic passage", "path": ["cold hands", "dials too small", mech, "product"], "target_mechanism": mech,
            "evidence_boundary": {"first_inference_at": mech}, "hop_refs": {"0": ["ch_0"], "1": ["ch_1"]} if hop_refs is None else hop_refs,
            "gaps": ["do gloved users skip settings?"], "alternatives": ["cold batteries, not dials"], "falsifiers": ["gloved users change settings easily"],
            "status": "WORKING_HYPOTHESIS"}


LAWFUL_BRIDGES = [_bridge(H1, "dial grip"), _bridge(H2, "battery keeper"), _bridge(H3, "fingertip flap")]


def test_a_lawful_bridge_portfolio_is_still_admissible():
    out = _exec("hypotheses.validate_bridge", {"hypotheses": LAWFUL_BRIDGES, "corpus_evidence": ROWS})["output"]
    assert out["admissible"] is True and out["bridge_errors"] == [] and out["portfolio_errors"] == []


@pytest.mark.parametrize("hop_refs, needle", [
    ({"0": [{"kind": "chunk", "id": "ch_0"}], "1": ["ch_1"]}, "hop 1 hop_refs must list evidence id strings"),
    ({"0": {"ids": ["ch_0"]}, "1": ["ch_1"]}, "hop 1 hop_refs must list evidence id strings"),
    ([["ch_0"], ["ch_1"]], "hop_refs must be an object"),
])
def test_the_bridge_law_answers_malformed_hop_refs_with_a_named_error(hop_refs, needle):
    bridges = [_bridge(H1, "dial grip", hop_refs), *LAWFUL_BRIDGES[1:]]
    out = _exec("hypotheses.validate_bridge", {"hypotheses": bridges, "corpus_evidence": ROWS})["output"]
    assert out["admissible"] is False and any(e.startswith(H1) and needle in e for e in out["bridge_errors"]), out["bridge_errors"]


# ─────────────────────────────────────────────────────────── B-01: C_population (population.nominate) reads what the lineage law let through
def test_population_nomination_reads_a_lead_whose_frictions_is_one_string():
    prim = {**LAWFUL_PRIMITIVES, "population_leads": [{"name": "winter landscape photographers", "why": "named in the passage", "frictions": "cold fingers on small dials",
                                                       "activities": "shooting outdoors", "evidence_refs": "ch_0"}]}
    out = _exec("population.nominate", {"signal": "cold hands and small camera dials", "primitives": prim, "corpus_evidence": ROWS})["output"]
    lead = next(l for l in out["population_leads"] if l["name"] == "winter landscape photographers")
    assert lead["expected_frictions"] == ["cold fingers on small dials"] and lead["activities"] == ["shooting outdoors"] and lead["nominated_by"] == ["ch_0"]


def test_population_nomination_reads_frictions_written_as_objects():
    prim = {**LAWFUL_PRIMITIVES, "frictions": [{"text": "gloves block fine dial control", "evidence_refs": ["ch_0"]}, "access_interruption"]}
    out = _exec("population.nominate", {"signal": "cold hands and small camera dials", "primitives": prim, "corpus_evidence": ROWS})["output"]
    assert out["ranked_lead_ids"] and out["batch"]


# ─────────────────────────────────────────────────────────── B-08: N_concepts_law (products.validate_concepts) + the net under every law
LIVE = [{"hypothesis_id": H1, "revision": 2, "status": "strengthened", "statement": "gloved hands cannot turn small dials"},
        {"hypothesis_id": H2, "revision": 1, "status": "revised", "statement": "cold batteries die mid shoot"}]
MECHS = [{"id": "m_grip", "name": "glove-operable dial grip", "hypothesis_id": H1}, {"id": "m_keep", "name": "warm battery keeper", "hypothesis_id": H2}]


def _concept(i: int, form: str, mech: str = "m_grip") -> dict:
    return {"id": f"pc_{i}", "mechanism_id": mech, "name": f"synthetic {form}", "form_factor": form, "target_moment": "DURING",
            "variations": [{"name": "standard"}, {"name": "reflective"}], "evidence_refs": ["fev_1"]}


CONCEPTS = [_concept(1, "dial grip sleeve"), _concept(2, "fingertip mitten"), _concept(3, "battery keeper pouch", mech="m_keep")]


def test_the_concepts_law_answers_a_mechanism_whose_hypothesis_id_is_a_list():
    mechs = [dict(MECHS[0], hypothesis_id=[H1]), MECHS[1]]
    out = _exec("products.validate_concepts", {"product_concepts": CONCEPTS, "mechanisms": mechs, "live_hypotheses": LIVE, "field_records": [{"id": "fev_1"}]})["output"]
    assert out["valid"] is False
    assert any(e.startswith("mechanisms[0].hypothesis_id: expected one live hypothesis id string") for e in out["errors"]), out["errors"]
    assert any("'m_grip' is not a SUPPORTED mechanism" in e for e in out["errors"])                       # and the concepts on it are not lawful


@pytest.mark.parametrize("operation, inputs, verdict, errors_key", [
    # shapes no named check anticipates (the manifest's output schemas type these fields; a direct request does not have to)
    ("hypotheses.validate_bridge", {"hypotheses": [dict(b, evidence_boundary="dials too small") for b in LAWFUL_BRIDGES], "corpus_evidence": ROWS},
     "admissible", "bridge_errors"),
    ("products.validate_concepts", {"product_concepts": [dict(c, form_factor=7) for c in CONCEPTS], "mechanisms": MECHS, "live_hypotheses": LIVE,
                                    "field_records": [{"id": "fev_1"}]}, "valid", "errors"),
])
def test_a_law_never_crashes_the_run_on_a_shape_it_cannot_read(operation, inputs, verdict, errors_key):
    out = _exec(operation, inputs)["output"]                                                           # exec_domain raises on a binding crash
    assert out[verdict] is False and out[errors_key] and out[errors_key][0].startswith("shape: "), out


# ─────────────────────────────────────────────────────────── B-09: the bridge law compares the bridges with the live LEDGER
H9 = "hyp_" + "9" * 12
LEDGER = [{"hypothesis_id": h, "revision": 1, "status": "proposed", "statement": f"synthetic statement {h[-1]}"} for h in (H1, H2, H3)] \
    + [{"hypothesis_id": H9, "revision": 2, "status": "killed", "statement": "an absorbed hypothesis"}]


def test_two_bridges_for_one_hypothesis_are_named_even_without_the_ledger():
    bridges = [_bridge(H1, "dial grip"), _bridge(H1, "dial heater"), _bridge(H2, "battery keeper")]
    out = _exec("hypotheses.validate_bridge", {"hypotheses": bridges, "corpus_evidence": ROWS})["output"]
    assert out["admissible"] is False and any(e.startswith(f"{H1}: 2 bridges name this hypothesis") for e in out["bridge_errors"]), out["bridge_errors"]


def test_the_bridge_law_names_duplicate_phantom_and_unbridged_hypotheses_against_the_ledger():
    bridges = [_bridge(H1, "dial grip"), _bridge(H1, "dial heater"), _bridge(H9, "battery keeper")]
    out = _exec("hypotheses.validate_bridge", {"hypotheses": bridges, "corpus_evidence": ROWS, "live_hypotheses": LEDGER})["output"]
    errs = out["bridge_errors"]
    assert out["admissible"] is False and out["portfolio_unreachable"] is False
    assert any(e.startswith(f"{H1}: 2 bridges") for e in errs) and any(e.startswith(f"{H9}: not a live hypothesis") for e in errs), errs
    assert {e.split(":")[0] for e in errs if "live hypothesis without a bridge" in e} == {H2, H3}
    lawful = _exec("hypotheses.validate_bridge", {"hypotheses": LAWFUL_BRIDGES, "corpus_evidence": ROWS, "live_hypotheses": LEDGER})["output"]
    assert lawful["admissible"] is True and lawful["bridge_errors"] == [] and lawful["portfolio_unreachable"] is False


def test_a_ledger_outside_the_portfolio_bounds_is_flagged_as_unreachable_by_bridges():
    two = _exec("hypotheses.validate_bridge", {"hypotheses": LAWFUL_BRIDGES[:2], "corpus_evidence": ROWS, "live_hypotheses": LEDGER[:2]})["output"]
    assert two["admissible"] is False and two["portfolio_unreachable"] is True and two["bridge_errors"] == []
    assert any("the ledger holds 2 live hypotheses" in e for e in two["portfolio_errors"]), two["portfolio_errors"]
    # without the ledger the law cannot tell a short generation from a missing bridge, and does not claim to
    blind = _exec("hypotheses.validate_bridge", {"hypotheses": LAWFUL_BRIDGES[:2], "corpus_evidence": ROWS})["output"]
    assert blind["admissible"] is False and blind["portfolio_unreachable"] is False
