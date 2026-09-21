"""Restoration Slice 5 — reporting and auditability (SEMANTIC_TRANSDUCTION_RESTORATION_REFERENCE §13).

The dossier explains where a hypothesis came from, what was abstracted, which bridge it earned, what supported and contradicted it,
what concepts resulted and which REAL products compete — read from authoritative state, not from the four-field step view:
§13.1 hypothesis table · §13.2 transduction · §13.3 product reality (generated vs. existing, never conflated) · §13.4 governance ·
§13.5 the journal records the materials the agent was shown.

The journal is recorded from the complete scripted ecommerce run (stub TrailSignal, in-memory store); the dossier is built OUT OF
PROCESS through the engine's own CLI, exactly as a host would. No database, no network."""
from __future__ import annotations

import json
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
for _p in (ROOT / "workers", ROOT / "shared", pathlib.Path(__file__).resolve().parent, ROOT / "adapters" / "ecommerce" / "python"):
    sys.path.insert(0, str(_p))

from polymath_shared.adapter import semantic_view as SV  # noqa: E402
from polymath_shared.adapter import service  # noqa: E402
import governed_run as JOURNAL  # noqa: E402
import test_adapter_ecommerce_dossier as DOSSIER  # noqa: E402
import test_adapter_ecommerce_product_research_e2e as SCRIPT  # noqa: E402

runtime = DOSSIER.runtime                                   # the same in-memory store + stub TrailSignal fixture


def test_the_code_under_test_is_this_checkout():
    for mod in (SV, service, JOURNAL):
        assert pathlib.Path(mod.__file__).resolve().is_relative_to(ROOT), mod.__file__


@pytest.fixture
def dossier(runtime, tmp_path):
    journal = DOSSIER._journaled_run(SCRIPT.Agent())
    html, model = DOSSIER._dossier(journal, tmp_path)
    return journal, html, model


def test_the_hypothesis_table_is_read_from_the_ledger_not_from_the_four_field_view(dossier):
    _, html, model = dossier
    g = model["governed"]
    assert g["hypothesis_state_from"] == "RESULT"
    rows = g["hypotheses"]
    assert rows and all(r["population"] == "runners" and r["activity"] == "running" and r["suspected_friction"] == "access_interruption" for r in rows)
    assert all(r["knowledge_support"] >= 1 and r["revision"] is not None for r in rows)                        # before: 0 and empty on every row
    assert any(r["field_evidence"] > 0 for r in rows) and "Population · activity · task · context" in html and "runners · running" in html
    assert "four-field step view carries no mechanism" not in html


def test_the_transduction_section_shows_structure_origin_and_the_earned_bridge_with_authorities_apart(dossier):
    _, html, model = dossier
    t = model["governed"]["transduction"]
    assert t["latent_structures"] and t["hypotheses"] and all(h["bridge"] and h["bridge"]["first_inference_at"] and len(h["bridge"]["path"]) >= 3 for h in t["hypotheses"])
    assert model["bridges"] and all(b["path"] and b["boundary"] for b in model["bridges"])                       # no longer hard-coded []
    assert "Transduction — from the corpus to the hypothesis" in html and "evidence-backed" in html and "inferred" in html
    assert "POLYMATH KNOWLEDGE" in html and "AGENT INFERENCE" in html and "TRAIL DETERMINATION" in html and "LIVE-WORLD OBSERVATION" in html
    # an origin the hypothesis did not declare is SAID, never invented
    assert all(h["origin_declared"] is False for h in t["hypotheses"]) and "not declared by the hypothesis" in html


def test_generated_concepts_and_existing_products_are_joined_and_never_conflated(dossier):
    _, html, model = dossier
    pr = model["governed"]["product_reality"]
    assert {c["concept_id"] for c in pr["concepts"]} == {"pc_1", "pc_2", "pc_3"} and pr["jobs"] > 0
    product = pr["existing_products"][0]
    assert product["product_name"] == "running belt" and product["concept_id"] in ("pc_1", "pc_2", "pc_3")
    assert "GENERATED CONCEPT" in html and "EXISTING product" in html and "Product Reality — generated concepts vs. existing products" in html
    concept_names = {c["name"] for c in model["product_concepts"]}
    assert "running belt" not in concept_names                                                                   # a real product never enters the concept list


def test_governance_coordinates_and_gates_are_rendered(dossier):
    _, html, model = dossier
    g = model["governed"]
    assert g["coordinates"]["priors"] and "Registry Coordinates" in html and "never evidence" in html
    assert g["qualifications"] and "qualification" in html and g["trail_scores"] and "HARD_GATE_UNMET" in html


def test_the_journal_records_what_the_agent_was_shown_bounded(dossier):
    journal, _, model = dossier
    steps = [e["data"] for e in journal["events"] if e["kind"] == "step"]
    shown = {s["step"]["step_id"]: s["materials"] for s in steps if s.get("materials")}
    assert {"C_hypotheses", "G_mechanisms", "K_revise", "N_concepts", "P_reality", "W_interpret"} <= set(shown)
    assert shown["G_mechanisms"]["values"]["hypothesis_semantics"][0]["semantics"]["population"] == "runners"
    assert "reality_plan" in shown["P_reality"]["values"] and model["governed"]["materials_recorded"] == sum(1 for s in steps if s.get("materials"))   # every pass of a looped step
    big = JOURNAL._materials_record({"values": {"small": {"a": 1}, "huge": "x" * (JOURNAL.MAX_MATERIAL_VALUE_BYTES + 10)}, "missing": ["m"], "too_large": []})
    assert big["values"] == {"small": {"a": 1}} and big["oversized_bytes"]["huge"] > JOURNAL.MAX_MATERIAL_VALUE_BYTES and big["missing"] == ["m"]
    assert JOURNAL._materials_record(None) is None


def test_an_older_journal_falls_back_honestly(dossier, tmp_path):
    journal, _, _ = dossier
    old = json.loads(json.dumps(journal))
    for e in old["events"]:
        if e["kind"] == "result":
            e["data"]["result"]["output"].pop("hypothesis_semantics", None)
    _, model = DOSSIER._dossier(old, tmp_path)
    assert model["governed"]["hypothesis_state_from"].startswith("MATERIALS@") and model["governed"]["hypotheses"][0]["population"] == "runners"
    for e in old["events"]:
        if e["kind"] == "step":
            e["data"].pop("materials", None)
    html, model = DOSSIER._dossier(old, tmp_path)
    assert model["governed"]["hypothesis_state_from"] == "STEP_CONTEXT_4_FIELDS" and model["governed"]["hypotheses"][0]["population"] is None
    assert "four-field step view carries no mechanism" in html                                                   # an empty column is explained, not presented as a finding


def test_the_result_carries_the_derived_view_for_every_hypothesis_and_nothing_reads_it_back(runtime):
    journal = DOSSIER._journaled_run(SCRIPT.Agent())
    result = next(e["data"]["result"] for e in journal["events"] if e["kind"] == "result")
    views = result["output"]["hypothesis_semantics"]
    assert views and all(v["view_version"] == SV.VIEW_VERSION and set(v) >= {"hypothesis", "origin", "semantics", "knowledge", "bridge", "concepts", "field_evidence", "trail"} for v in views)
    assert {v["hypothesis"]["hypothesis_id"] for v in views} == set(result["lineage"]["hypothesis_ids"])       # absorbed hypotheses included: the whole story
    for key in ("primitives", "latent_structures", "bridges", "priors", "existing_products", "concept_reality"):
        assert key in result["output"], key
