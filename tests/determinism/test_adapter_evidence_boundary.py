"""GOVERNED-CONVERGENCE-V1 TG2 — the adapter's evidence boundary (pure module) + its two service seams.

Covers: the orchestrator path allow-list; opt-in surface + env kill switch; the ORIGINAL-need rule; one corpus per call,
bounded, with the skip recorded; the exact request body; the FAIL-CLOSED packet check; packet -> rows -> refs (deterministic,
graded first, refs lawful on the AdapterStepV1 wire); unavailable = typed gap or `unknowns` (never `knowledge_gaps`);
`hydrate` caps / class balance / field-evidence join / loop passes / exact-ids; `adapter_next`'s sibling `evidence` key;
the collect-all include form; and the 2.2.0 manifest identity (still 28 steps, same step ids, other manifests untouched).
"""
from __future__ import annotations

import copy
import inspect
import json
import pathlib
import sys

import jsonschema
import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(ROOT / "shared") not in sys.path:
    sys.path.insert(0, str(ROOT / "shared"))

from polymath_shared.adapter import evidence_boundary as EB  # noqa: E402
from polymath_shared.adapter import service  # noqa: E402
from polymath_shared.adapter.contracts import schema  # noqa: E402
from polymath_shared.adapter.manifest import ADAPTER_DIR, list_manifests  # noqa: E402
from polymath_shared.adapter.transitions import RunState  # noqa: E402

assert pathlib.Path(EB.__file__).resolve().is_relative_to(ROOT), EB.__file__      # executed path == this checkout
assert pathlib.Path(service.__file__).resolve().is_relative_to(ROOT), service.__file__

EXAMPLE = json.loads((ROOT / "contracts/evidence/v1/evidence_packet.example.json").read_text())


def _item(cid, grade=None, role="DIRECT", origin="USER", text="t"):
    return {"chunk_id": cid, "document_id": "doc_" + cid, "source": "src " + cid, "text": text, "origin": origin, "query_ids": ["q0"],
            "lineage": [{"query_id": "q0", "origin": origin, "role": "PRIMARY"}], "utility_role": role, "synthesis_role": None,
            "ca4_grade": grade, "c4_valid": grade in ("DIRECT", "PARTIAL"), "provenance": {"origin": origin}}


def _packet(items):
    return {**copy.deepcopy(EXAMPLE), "evidence": items}


# ─────────────────────────────────────────────────────────── allow-list + surface
def test_the_outbound_surface_is_exactly_three_paths_and_synthesis_routes_are_refused():
    assert EB.ALLOWED_ORCH_PATHS == frozenset({"/chat/evidence", "/retrieve", "/retrieve/plan"})
    for ok in EB.ALLOWED_ORCH_PATHS:
        assert EB.assert_allowed_path(ok) == ok
    for forbidden in ("/chat", "/chat/stream", "/ask", "/chat/evidence/", "/upload", ""):
        with pytest.raises(EB.PathNotAllowed):
            EB.assert_allowed_path(forbidden)


def test_default_surface_is_legacy_and_the_boundary_is_opt_in():
    assert EB.resolve_surface({}, {}) == ("retrieve", [])
    assert EB.resolve_surface(None, None) == ("retrieve", [])
    assert EB.resolve_surface({"surface": "evidence_boundary"}, {}) == ("evidence_boundary", [])
    with pytest.raises(ValueError):
        EB.resolve_surface({"surface": "chat"}, {})


def test_kill_switch_only_forces_legacy_and_says_so():
    env = {EB.ENV_SURFACE: "retrieve"}
    assert EB.resolve_surface({"surface": "evidence_boundary"}, env) == ("retrieve", ["surface_forced_by_env"])
    assert EB.resolve_surface({}, env) == ("retrieve", [])                         # a legacy step was never forced
    # the env can NOT switch the boundary on: the default surface in code stays legacy
    assert EB.resolve_surface({}, {EB.ENV_SURFACE: "evidence_boundary"}) == ("retrieve", [])
    assert EB.resolve_surface({"surface": "evidence_boundary"}, {EB.ENV_SURFACE: "RETRIEVE "}) == ("retrieve", ["surface_forced_by_env"])


def test_user_agent_correlates_run_step_and_sequence():
    assert EB.user_agent("adr_x", "B_retrieve", 3) == "polymath-adapter-step/adr_x/B_retrieve/3"
    assert len(EB.user_agent("adr_" + "f" * 32, "F_retrieve", 999)) <= 120           # query_receipts.client keeps 120 chars


# ─────────────────────────────────────────────────────────── the ORIGINAL need
def test_explore_steps_send_the_original_seed_never_a_reformulation():
    assert "outputs" not in inspect.signature(EB.original_needs).parameters            # a step output can not reach it at all
    needs = EB.original_needs({"source": "input.seed"}, {"seed": "  running belts   bounce on long runs "}, {}, None)
    assert needs == ["running belts bounce on long runs"]
    assert EB.original_needs({}, {"question": "q?"}) == ["q?"]
    with pytest.raises(ValueError):
        EB.original_needs({"source": "input.seed"}, {}, {}, None)


def test_hypothesis_steps_send_one_need_per_live_hypothesis_deduplicated_and_bounded_in_length():
    hyps = [{"statement": "Belts bounce because the load sits off-centre"}, {"statement": "belts bounce because the load sits off-centre "},
            {"statement": ""}, {"statement": "x" * 5000}]
    needs = EB.original_needs({"query_from": "hypotheses", "source": "input.seed"}, {"seed": "s"}, {}, hyps)
    assert needs[0] == "Belts bounce because the load sits off-centre" and len(needs) == 2 and len(needs[1]) == EB.MAX_NEED_CHARS
    # no live hypothesis yet -> the ORIGINAL seed, never an invented query
    assert EB.original_needs({"query_from": "hypotheses", "source": "input.seed"}, {"seed": "s"}, {}, []) == ["s"]


def test_one_corpus_per_call_bounded_and_the_skip_is_recorded():
    plan = EB.plan_calls(["n0", "n1"], ["c0", "c1", "c2"], max_calls=3)
    assert [(c["need_index"], c["corpus_id"]) for c in plan["calls"]] == [(0, "c0"), (1, "c0"), (0, "c1")]
    assert plan["truncated"] == [{"corpus_id": "c1", "need_index": 1, "reason": "max_calls"}, {"corpus_id": "c2", "need_index": 0, "reason": "max_calls"},
                                 {"corpus_id": "c2", "need_index": 1, "reason": "max_calls"}]
    assert EB.plan_calls(["n0"], ["c0"]) == {"calls": [{"need_index": 0, "need": "n0", "corpus_id": "c0"}], "truncated": []}
    assert EB.plan_calls(["n0"], ["c0"], max_calls=0)["calls"]                       # never zero calls for a real need
    assert EB.plan_calls(["n0", "n1"], ["c0"]) == EB.plan_calls(["n0", "n1"], ["c0"])  # deterministic


def test_request_body_is_exactly_five_fields():
    # K1 (register 11.485): the fifth field is the reference-only scope — Trail ideation never reads implementation material
    body = EB.request_body("need", "cinema", mode="wildcard", corpus_explorer=True)
    assert body == {"message": "need", "corpus_id": "cinema", "mode": "WILDCARD", "corpus_explorer": True,
                    "scope": {"roles": ["reference"]}}
    assert set(EB.request_body("n", "c", mode="GRAPH", corpus_explorer=False)) == {"message", "corpus_id", "mode", "corpus_explorer",
                                                                                  "scope"}
    for bad in ("ASK", "LEGACY", "", "EXPLORE"):
        with pytest.raises(ValueError):
            EB.request_body("n", "c", mode=bad)
    with pytest.raises(ValueError):
        EB.request_body("", "c")
    with pytest.raises(ValueError):
        EB.request_body("n", "")


# ─────────────────────────────────────────────────────────── the packet contract, fail-closed
def test_a_lawful_response_passes_and_empty_evidence_is_lawful():
    assert EB.check_response({"evidence_packet": EXAMPLE, "synthesis_performed": False}) == []
    assert EB.check_response({"evidence_packet": _packet([])}) == []                  # empty evidence is a SUCCESS, not a mismatch


@pytest.mark.parametrize("resp, needle", [
    (None, "not an object"),
    ({}, "no evidence_packet"),
    ({"evidence_packet": {**EXAMPLE, "schema_version": "evidence-packet-v2"}}, "schema_version"),
    ({"evidence_packet": {**EXAMPLE, "synthesis_performed": True}}, "synthesis_performed"),
    ({"evidence_packet": {k: v for k, v in EXAMPLE.items() if k != "synthesis_performed"}}, "synthesis_performed"),
    ({"evidence_packet": EXAMPLE, "synthesis_performed": True}, "response.synthesis_performed"),
    ({"evidence_packet": {k: v for k, v in EXAMPLE.items() if k != "plan"}}, "plan"),
    ({"evidence_packet": _packet([{**_item("c1"), "utility_role": "INVENTED"}])}, "utility_role"),
    ({"evidence_packet": _packet([{k: v for k, v in _item("c1").items() if k != "ca4_grade"}])}, "ca4_grade"),
])
def test_contract_mismatch_is_detected_fail_closed(resp, needle):
    errs = EB.check_response(resp)
    assert errs and any(needle in e for e in errs), errs


def test_rows_refs_and_merge_are_deterministic_graded_first_and_lawful_on_the_wire():
    a = EB.rows_from_packet(_packet([_item("c_rel", "RELATED", "COMPLEMENTARY", "CORPUS_EXPLORE"), _item("c_none", None, "RELATED"),
                                     _item("c_dir", "DIRECT", text="x" * 5000)]), "cinema")
    b = EB.rows_from_packet(_packet([_item("c_dir", "DIRECT"), _item("c_par", "PARTIAL", "DIVERGENT", "BRIDGE")]), "cinema")
    assert all(r["kind"] == "chunk" and r["corpus_id"] == "cinema" for r in a + b) and len(a[2]["text"]) == EB.ROW_TEXT_CHARS
    rows, dropped = EB.merge_rows([a, b])
    assert [r["id"] for r in rows] == ["c_dir", "c_par", "c_rel", "c_none"] and dropped == 0          # graded first, first occurrence wins
    assert EB.merge_rows([a, b]) == EB.merge_rows([copy.deepcopy(a), copy.deepcopy(b)])
    assert EB.merge_rows([a, b], max_rows=2) == (rows[:2], 2)
    refs = EB.refs_from_rows(rows)
    assert refs[0] == {"kind": "chunk", "id": "c_dir", "corpus_id": "cinema", "doc_id": "doc_c_dir", "utility_role": "DIRECT", "ca4_grade": "DIRECT",
                       "c4_valid": True, "origin": "USER"}
    assert "ca4_grade" not in refs[3] and refs[1]["origin"] == "BRIDGE" and refs[2]["utility_role"] == "COMPLEMENTARY"
    ref_schema = schema("adapter_step")["properties"]["context"]["properties"]["evidence_refs"]
    jsonschema.Draft202012Validator(ref_schema).validate(refs)
    # an out-of-vocabulary value stays on the row and is NOT projected onto the wire (the step must always validate)
    odd = EB.refs_from_rows([{"id": "c9", "kind": "chunk", "utility_role": "invented", "ca4_grade": "MAYBE", "origin": "lower case!", "c4_valid": "yes"}])
    assert odd == [{"kind": "chunk", "id": "c9"}]
    jsonschema.Draft202012Validator(ref_schema).validate(odd)
    # legacy refs (no boundary properties) stay lawful: the four properties are OPTIONAL
    jsonschema.Draft202012Validator(ref_schema).validate([{"kind": "chunk", "id": "c1", "score": 0.5}])
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.Draft202012Validator(ref_schema).validate([{"kind": "chunk", "id": "c1", "utility_role": "INVENTED"}])


def test_call_record_is_bounded_and_carries_the_contract_verdict():
    rows = EB.rows_from_packet(EXAMPLE, "cinema")
    rec = EB.call_record({"need_index": 0, "corpus_id": "cinema"}, EXAMPLE, rows)
    assert rec["contract"] == {"schema_version": "evidence-packet-v1", "synthesis_performed": False, "valid": True}
    assert rec["n_evidence"] == 2 and rec["grades"] == {"DIRECT": 1, "RELATED": 1} and rec["corpus_explorer_used"] is True
    assert "need" not in rec and "evidence" not in rec                                      # the packet itself is not stored


def test_unavailable_is_a_typed_gap_or_an_unknown_never_a_knowledge_gap():
    gap = EB.unavailable_outcome("gap", "B_retrieve", "connection refused")
    assert gap == {"gap": {"code": "EVIDENCE_SURFACE_UNAVAILABLE", "message": "B_retrieve: connection refused"}}
    cont = EB.unavailable_outcome("continue", "B_retrieve", "connection refused")
    assert cont["evidence_refs"] == [] and cont["output"]["rows"] == [] and cont["output"]["retrieval_completed"] is False
    assert cont["output"]["degraded"] is True and cont["output"]["unknowns"][0]["step_id"] == "B_retrieve"
    assert "knowledge_gaps" not in json.dumps(cont)                                          # that key is forwarded to TrailSignal
    with pytest.raises(ValueError):
        EB.unavailable_outcome("fallback", "s", "r")


# ─────────────────────────────────────────────────────────── hydrate (TG2a)
def _stored():
    receipt = {"action_id": "hact_1", "harness_id": "h", "observations": [{"observation_id": "fr0", "source_id": "s0", "claim": "my pouch bounces", "paraphrase_or_excerpt": "it bounces on every stride", "metric_if_present": {"name": "price", "value": 19, "unit": "USD"}}],
               "sources": [{"source_id": "s0", "url": "https://forum.example/t/0", "source_class": "community_discussion", "published_at_if_known": "2026-09-01T00:00:00Z"}]}
    loop_receipt = {"action_id": "hact_2", "harness_id": "h", "observations": [{"observation_id": "fr0", "source_id": "s0", "claim": "second pass claim", "paraphrase_or_excerpt": "loop two"}],
                    "sources": [{"source_id": "s0", "url": "https://forum.example/t/9", "source_class": "community_discussion"}]}
    adm = lambda action, fev: {"admission_id": "adm_" + fev, "action_id": action, "admitted": [{"admitted_evidence_id": fev, "observation_id": "fr0", "source_id": "s0", "evidence_role": "friction", "polarity": "supporting", "hypothesis_ids": ["hyp_1"], "independence_group": "g1", "freshness": "fresh", "source_class": "community_discussion"}], "rejected": []}
    return [
        {"step_id": "B_plan", "sequence": 2, "output": {"rows": [{"id": "c_plan", "kind": "chunk", "text": "plan lane text", "title": "Doc A"}], "queries": ["q1", "q2"]}},
        {"step_id": "B_retrieve", "sequence": 3, "output": {"surface": "evidence_boundary", "mode": "WILDCARD", "needs": ["seed"], "corpus_ids": ["cinema"], "retrieval_completed": True,
                                                            "calls": [{"corpus_id": "cinema", "n_evidence": 2}],
                                                            "rows": [{"id": "c_dir", "kind": "chunk", "text": "D" * 2000, "ca4_grade": "DIRECT", "utility_role": "DIRECT", "source": "Book"},
                                                                     {"id": "c_plan", "kind": "chunk", "text": "graded copy", "ca4_grade": "PARTIAL", "utility_role": "DIRECT"}]}},
        {"step_id": "B_graph", "sequence": 4, "output": {"graph_rows": [{"id": "f1", "kind": "graph_fact", "text": "a -> b"}], "graph_facts": 1}},
        {"step_id": "I_research", "sequence": 13, "output": receipt},
        {"step_id": "J_admit", "sequence": 14, "output": {"evidence_admission": adm("hact_1", "fev_1")}},
        {"step_id": "I_research", "sequence": 20, "output": loop_receipt},                   # a bounded-loop pass re-runs the same step ids
        {"step_id": "J_admit", "sequence": 21, "output": {"evidence_admission": adm("hact_2", "fev_2")}},
        {"step_id": "K_revise", "sequence": 22, "output": None},
    ]


def test_hydrate_returns_readable_rows_for_exactly_the_context_ids():
    refs = [{"kind": "chunk", "id": "c_plan"}, {"kind": "chunk", "id": "c_dir", "ca4_grade": "DIRECT"}, {"kind": "graph_fact", "id": "f1"},
            {"kind": "field_evidence", "id": "fev_1"}, {"kind": "field_evidence", "id": "fev_2"}, {"kind": "trail_prior", "id": "prior_1"},
            {"kind": "chunk", "id": "c_dir"}]
    out = EB.hydrate(refs, _stored())
    by = {r["id"]: r for r in out["rows"]}
    assert set(by) == {"c_plan", "c_dir", "f1", "fev_1", "fev_2"}                              # never a row the step did not cite-list
    assert [r["id"] for r in out["rows"]] == ["fev_1", "fev_2", "c_dir", "c_plan", "f1"]          # class order, graded first inside a class
    assert len(by["c_dir"]["text"]) == EB.HYDRATE_MAX_CHARS and by["c_plan"]["text"] == "graded copy" and by["c_plan"]["ca4_grade"] == "PARTIAL"
    assert by["fev_1"]["text"] == "my pouch bounces — it bounces on every stride" and by["fev_1"]["source"] == "https://forum.example/t/0"
    assert by["fev_1"]["evidence_role"] == "friction" and by["fev_1"]["metric_if_present"]["value"] == 19
    assert by["fev_2"]["text"] == "second pass claim — loop two"                                  # the looped pass joins ITS OWN receipt
    assert out["coverage"] == {"refs": 6, "readable": 5, "returned": 5, "unresolved": 1, "max_rows": 60, "max_chars": 600}
    rcpt = {r["step_id"]: r for r in out["receipts"]}
    assert rcpt["B_retrieve"]["surface"] == "evidence_boundary" and rcpt["B_retrieve"]["needs"] == ["seed"] and rcpt["B_plan"]["compiled_queries"] == 2
    assert rcpt["B_graph"]["surface"] == "retrieve" and EB.hydrate(refs, _stored()) == out       # deterministic


def test_hydrate_caps_at_sixty_rows_and_no_class_starves_another():
    stored = [{"step_id": "B_retrieve", "sequence": 3, "output": {"rows": [{"id": f"c{i}", "kind": "chunk", "text": "t", **({"ca4_grade": "DIRECT"} if i >= 150 else {})} for i in range(200)]}},
              {"step_id": "B_graph", "sequence": 4, "output": {"graph_rows": [{"id": f"f{i}", "kind": "graph_fact", "text": "t"} for i in range(40)]}}]
    refs = [{"kind": "chunk", "id": f"c{i}"} for i in range(200)] + [{"kind": "graph_fact", "id": f"f{i}"} for i in range(40)]
    out = EB.hydrate(refs, stored)
    kinds = [r["kind"] for r in out["rows"]]
    assert len(out["rows"]) == 60 and kinds.count("graph_fact") == 10 and kinds.count("chunk") == 50
    assert out["rows"][0]["id"] == "c150" and all(r.get("ca4_grade") == "DIRECT" for r in out["rows"][:50])   # graded first
    assert out["coverage"]["readable"] == 240 and out["coverage"]["returned"] == 60
    small = EB.hydrate(refs, stored, max_rows=6, max_chars=1)
    assert len(small["rows"]) == 6 and all(len(r["text"]) <= 1 for r in small["rows"])
    assert EB.hydrate([], stored)["rows"] == [] and EB.hydrate(refs, [])["coverage"]["unresolved"] == 240


# ─────────────────────────────────────────────────────────── the two service seams
def test_adapter_next_carries_a_sibling_evidence_key_and_the_step_is_unchanged(monkeypatch):
    step = {"run_id": "adr_t", "step_id": "C_hypotheses", "step_type": "AGENT_REASON", "sequence": 5,
            "context": {"evidence_refs": [{"kind": "chunk", "id": "c_dir"}, {"kind": "graph_fact", "id": "f1"}]}}
    frozen = copy.deepcopy(step)
    monkeypatch.setattr(service, "status", lambda conn, run_id, directory=None: {"status": "awaiting_agent"})
    monkeypatch.setattr(service.store, "current_step", lambda conn, run_id: {"status": "issued", "step": step})
    monkeypatch.setattr(service.store, "list_steps", lambda conn, run_id: _stored())
    nxt = service.next_step(None, "adr_t")
    assert set(nxt) == {"kind", "step", "status", "evidence"} and nxt["kind"] == "step" and nxt["step"] == frozen
    assert [r["id"] for r in nxt["evidence"]["rows"]] == ["c_dir", "f1"] and nxt["evidence"]["rows"][0]["text"].startswith("DDD")
    # a run that awaits nothing answers exactly as before
    monkeypatch.setattr(service, "status", lambda conn, run_id, directory=None: {"status": "running"})
    assert service.next_step(None, "adr_t") == {"kind": "status", "status": {"status": "running"}}


def test_a_hydration_failure_is_said_not_hidden_and_never_takes_adapter_next_down(monkeypatch):
    monkeypatch.setattr(service.store, "list_steps", lambda conn, run_id: (_ for _ in ()).throw(RuntimeError("boom")))
    out = service._readable_evidence(None, "adr_t", {"context": {"evidence_refs": [{"kind": "chunk", "id": "c1"}]}})
    assert out["rows"] == [] and out["receipts"] == [] and "RuntimeError: boom" in out["error"]


def test_collect_all_include_gathers_every_admission_in_sequence_order(monkeypatch):
    RUN = "adr_" + "0" * 32
    m = next(x for x in list_manifests(ADAPTER_DIR) if x.adapter_id == "trail.product_discovery")
    a1, a2, a3 = ({"admission_id": f"adm_{i}", "admitted": [], "rejected": [{"observation_id": "o", "reason_code": "STALE_BEYOND_POLICY"}]} for i in (1, 2, 3))
    steps = [{"sequence": 14, "step_id": "J_admit", "output": {"evidence_admission": a1}, "receipt": None, "external_operation": None},
             {"sequence": 21, "step_id": "J_admit", "output": {"evidence_admission": a2}, "receipt": None, "external_operation": None},
             {"sequence": 30, "step_id": "K_revise", "output": None, "receipt": None, "external_operation": None},
             {"sequence": 35, "step_id": "Q_admit", "output": {"evidence_admission": a3}, "receipt": None, "external_operation": None}]
    # state.outputs keeps ONLY the newest pass of a looped step — a plain include would lose adm_1
    state = RunState(run_id=RUN, adapter_id=m.adapter_id, status="completed", input={}, options={},
                     outputs={"J_admit": {"evidence_admission": a2}, "Q_admit": {"evidence_admission": a3}, "W_interpret": {"product_opportunity": {"name": "x"}}},
                     output_order=("J_admit", "Q_admit", "W_interpret"))
    monkeypatch.setattr(service.store, "load_run", lambda conn, run_id, **kw: (state, {"created_at": "2026-09-20T00:00:00Z", "terminal_at": "2026-09-20T00:01:00Z", "agent_identity": "t"}))
    monkeypatch.setattr(service.store, "list_steps", lambda conn, run_id: steps)
    monkeypatch.setattr(service.store, "list_harness_actions", lambda conn, run_id: [])
    monkeypatch.setattr(service.store, "current_hypotheses", lambda conn, run_id: {})
    monkeypatch.setattr(service.store, "admitted_evidence_refs", lambda conn, run_id: [])
    res = service._compile_result(None, RUN, state, m, output=None, persist=False)
    assert [a["admission_id"] for a in res["output"]["evidence_admissions"]] == ["adm_1", "adm_2", "adm_3"]
    assert res["output"]["evidence_admissions"][0]["rejected"][0]["reason_code"] == "STALE_BEYOND_POLICY"   # rejected WITH reason codes
    assert res["output"]["product_opportunity"] == {"name": "x"}                                          # plain includes unchanged


# ─────────────────────────────────────────────────────────── the manifest
def test_manifest_2_2_0_opts_four_steps_in_and_keeps_the_workflow():
    ms = {m.adapter_id: m for m in list_manifests(ADAPTER_DIR)}
    m = ms["trail.product_discovery"]
    assert (m.identity["adapter_version"], m.identity["workflow_version"], m.identity["retrieval_policy_version"]) == ("2.2.1", "2.0.0", "2.0.0")   # 2.2.1: source classes Trail routes (gap S-07); workflow unchanged
    example = json.loads((ROOT / "contracts/adapter/v1/adapter_manifest.example.json").read_text())
    assert len(m.steps) == 28 and list(m.steps) == [s["step_id"] for s in example["steps"]]              # no step id added, removed or renamed
    cfg = {sid: m.step(sid).get("config") or {} for sid in m.steps}
    for sid in ("B_retrieve", "F_retrieve"):
        assert (cfg[sid]["surface"], cfg[sid]["mode"], cfg[sid]["corpus_explorer"], cfg[sid]["legacy_mode"]) == ("evidence_boundary", "WILDCARD", True, "EXPLORE")
    for sid in ("B_graph", "F_graph"):
        assert (cfg[sid]["surface"], cfg[sid]["mode"]) == ("evidence_boundary", "GRAPH")
    for sid in ("B_retrieve", "F_retrieve", "B_graph", "F_graph"):
        assert cfg[sid]["max_calls"] == 3 and cfg[sid]["fallback"] == "retrieve" and cfg[sid]["on_unavailable"] in EB.ON_UNAVAILABLE
        assert EB.resolve_surface(cfg[sid], {}) == ("evidence_boundary", [])
    assert m.step("B_plan")["type"] == m.step("F_plan")["type"] == "POLYMATH_COMPILE_PLAN"               # the cheap find lane stays
    assert {"collect_all": "evidence_admission", "as": "evidence_admissions"} in cfg["X_compile"]["include"]
    assert cfg["B_retrieve"]["source"] == "input.seed" and cfg["F_retrieve"]["query_from"] == "hypotheses"
    for other in ("polymath.knowledge_brief", "substack.article_development"):                            # untouched: default surface = legacy
        assert all("surface" not in (ms[other].step(sid).get("config") or {}) for sid in ms[other].steps)
