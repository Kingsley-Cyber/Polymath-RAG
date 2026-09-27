"""TRAIL-EXT-BUGHUNT-V1 B-55 — the query compiler reads words in any script, and never issues an empty search.

`executors._gap_keywords` (behind `query_semantics.keywords`, the one word rule of every search string, template binding, gap query
and market phrase) kept ASCII letters only: Spanish words split at every accent, Chinese semantics compiled to nothing, and
`product_reality.plan` then issued a direct-competitor job whose search template was ''. The engine runs out of process (its flat
module names never enter this interpreter). No database, no network. Every text is synthetic.
"""
from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys

ENGINE = pathlib.Path(__file__).resolve().parents[2] / "adapters" / "ecommerce"
ENV = {"PATH": os.environ.get("PATH", ""), "LANG": "en_US.UTF-8", "PYTHONDONTWRITEBYTECODE": "1"}
H1 = "hyp_" + "c" * 12


def _engine(code: str, payload) -> object:
    proc = subprocess.run([sys.executable, "-c", "import json, sys; sys.path.insert(0, 'python'); " + code, json.dumps(payload, ensure_ascii=False)],
                          cwd=ENGINE, env=ENV, capture_output=True, text=True, check=False, timeout=60)
    assert proc.returncode == 0, proc.stderr[-800:]
    return json.loads(proc.stdout)


def _binding(operation: str, inputs: dict) -> dict:
    req = {"schema_version": "domain_operation_request.v1", "domain": "ecommerce", "operation": operation, "run_id": "adr_" + "9" * 32, "step_id": "op",
           "input": {}, "inputs": inputs, "config": {}}
    proc = subprocess.run([sys.executable, str(ENGINE / "binding.py")], input=json.dumps(req), cwd=ENGINE, env=ENV, capture_output=True, text=True,
                          check=False, timeout=120)
    assert proc.returncode == 0, proc.stderr[-800:]
    return json.loads(proc.stdout)


def test_words_are_read_in_any_script_and_english_is_unchanged():
    got = _engine("import query_semantics as QS; print(json.dumps([QS.keywords(t) for t in json.loads(sys.argv[1])], ensure_ascii=False))",
                  ["fotógrafos de paisaje", "fotógrafos de paisaje con guantes térmicos", "风景摄影师", "手袋をしたまま", "사진 작가",
                   "Runners' keys bounce out of the e-mail pocket mid-stride"])
    assert got == [["fotógrafos", "paisaje"], ["fotógrafos", "paisaje", "con", "guantes", "térmicos"], ["风景摄影师"], ["手袋をしたまま"], ["사진", "작가"],
                   ["runners'", "keys", "bounce", "e-mail", "pocket", "mid-stride"]]


def test_a_chinese_hypothesis_binds_templates_and_compiles_a_gap_query():
    view = {"hypothesis_id": H1, "population": "风景摄影师", "activity": "户外摄影", "task": "戴手套调节相机", "suspected_friction": "手指冻僵"}
    got = _engine("import query_semantics as QS; v = json.loads(sys.argv[1]); "
                  "print(json.dumps([QS.bind_template('{activity} {task}', v), QS.gap_query({'evidence_role': 'friction'}, v, origin='trail_gate')], ensure_ascii=False))",
                  view)
    assert got[0] == ["户外摄影 戴手套调节相机", []]
    assert got[1]["query"] == "风景摄影师 戴手套调节相机 手指冻僵"


def test_product_reality_never_issues_an_empty_search_template():
    directive = {"objective": "map current products", "hypothesis_ids": [H1], "evidence_gaps": [], "budget": {"max_queries": 24},
                 "search_intents": [{"intent_id": "q-comp", "intent": "who already sells it", "evidence_goal": "competition", "evidence_roles": ["competition"],
                                     "template": "existing products"}]}
    mechs = [{"id": "m_1", "name": "grip", "hypothesis_id": H1}]
    concepts = [{"id": "pc_1", "mechanism_id": "m_1", "name": "zz", "form_factor": "x", "variations": []},                 # no word of 3+ letters anywhere
                {"id": "pc_2", "mechanism_id": "m_1", "name": "silicone dial sleeve", "form_factor": "dial sleeve", "variations": []}]
    out = _binding("product_reality.plan", {"research_directive": directive, "product_concepts": concepts, "mechanisms": mechs,
                                            "live_hypotheses": [{"hypothesis_id": H1, "status": "proposed"}], "semantics": []})["output"]
    assert all(str(i.get("template") or "").strip() for i in out["research_directive"]["search_intents"]), out["research_directive"]["search_intents"]
    assert out["planned"]["concepts_without_a_job"] == ["pc_1"] and {u["concept_id"] for u in out["planned"]["unresolved"]} == {"pc_1"}
    assert {j["concept_id"] for j in out["reality_plan"]} == {"pc_2"}
