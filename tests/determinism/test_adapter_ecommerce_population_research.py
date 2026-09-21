"""Consolidation migration Phase 5 (AUTO_DECISIONS M-009) — population discovery becomes research PLANNING, and TrailSignal's
research directive is enriched by the domain ("Trail says WHAT, the engine says HOW") with NO runtime change: the existing
`service._compile_harness_action` hands the newest `research_directive` to the harness, whoever produced it.

No database (in-memory store), no network (TrailSignal is an httpx.MockTransport answering two bounded operations).
"""
from __future__ import annotations

import copy
import hashlib
import json
import pathlib
import sys

import httpx
import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
for _sub in ("workers", "shared"):
    sys.path.insert(0, str(ROOT / _sub))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from polymath_shared.adapter import contracts as C  # noqa: E402
from polymath_shared.adapter import manifest as M  # noqa: E402
from polymath_shared.adapter import service  # noqa: E402
from polymath_shared.adapter import trail_client as TC  # noqa: E402
from polymath_shared.adapter.transitions import RunState  # noqa: E402
import workers.adapter_step_worker as W  # noqa: E402
from _adapter_memory_store import MemoryStore  # noqa: E402

FIXTURES = ROOT / "tests" / "fixtures" / "adapter_domain_binding"
ADAPTER_ID = "fixture.research_planning"
ENGINE = ROOT / "adapters" / "ecommerce"
SNAP = {"snapshot_id": "trs_stub_phase5", "content_hash": "sha256:" + "c" * 64}
SEED = "runners lose access to small items while moving"
#: the shape TrailSignal's gaps.compile returns today (generic, unfilled templates — defect D6 of the first real run)
DIRECTIVE = {"objective": "find first-person field evidence", "geography": "US", "language": "en",
             "evidence_gaps": [{"gap_id": "gap_0", "hypothesis_id": "hyp_" + "0" * 12, "question": "do runners complain that keys bounce out of pockets mid stride", "evidence_role": "friction"}],
             "search_intents": [{"intent_id": "q-complaint", "intent": "Find direct complaint language", "evidence_goal": "complaint", "evidence_roles": ["friction", "behavior"], "template": "{activity} {task} annoying"},
                                {"intent_id": "q-workaround", "intent": "Find workaround discussions", "evidence_goal": "workaround", "evidence_roles": ["workaround"], "template": None}],
             "preferred_source_roles": ["community_discussion"], "disallowed_source_roles": ["supplier_listing"], "minimum_independent_sources": 3,
             "freshness_requirement": {"max_age_days": 14, "policy_ref": "strictest-routed-source"}, "budget": {"max_queries": 8, "max_sources": 20, "max_observations": 80},
             "success_condition": "10 independent complaints", "falsification_condition": "no recurring complaints"}
PRIMITIVES = {"physical_jobs": ["carry keys while running"], "frictions": ["access_interruption"], "shared_predicates": ["carry"],
              "population_leads": [{"name": "trail runners", "frictions": ["keys bounce in pocket"], "activities": ["trail running"]}],
              "latent_structures": [{"id": "ls1", "kind": "FRICTION", "text": "small items bounce and fall out during repetitive motion",
                                     "possible_populations": ["dog walkers"], "evidence_refs": ["chunk_0001"]}]}
SOURCE_NAMES = ("reddit", "youtube", "tiktok", "amazon", "twitter", "xiaohongshu")


def _exec(operation: str, inputs: dict) -> dict:
    """One operation through the REAL executor: a one-step manifest whose config selects `inputs` from a prior output."""
    raw = {"adapter_id": "fixture.one_op", "adapter_version": "1.0.0", "workflow_version": "1.0.0", "retrieval_policy_version": "1.0.0", "input_schema_version": "1.0.0",
           "output_schema_version": "1.0.0", "description": "one domain operation", "input_schema": {"type": "object"}, "output_schema": {"type": "object"},
           "budgets": {"max_steps": 4, "max_agent_reason": 0, "max_branch_loops": 0}, "entry_step_id": "op", "terminal_step_id": "end",
           "steps": [{"step_id": "op", "type": "DOMAIN_OPERATION", "title": "op", "next": "end",
                      "config": {"domain": "ecommerce", "operation": operation, "inputs": {k: f"outputs.given.{k}" for k in inputs}}},
                     {"step_id": "end", "type": "COMPILE_RESULT", "title": "end", "next": None, "config": {"include": ["lineage"]}}]}
    assert C.validate("adapter_manifest", raw) == [] and M.graph_integrity_errors(raw) == []
    m = M.Manifest(adapter_id=raw["adapter_id"], adapter_version="1.0.0", workflow_version="1.0.0", retrieval_policy_version="1.0.0", input_schema_version="1.0.0",
                   output_schema_version="1.0.0", entry_step_id="op", terminal_step_id="end", budgets=raw["budgets"], steps={s["step_id"]: s for s in raw["steps"]}, raw=raw)
    state = RunState(run_id="adr_" + "2" * 32, adapter_id=raw["adapter_id"], status="running", input={}, outputs={"given": inputs})
    return W.exec_domain({"run_id": state.run_id, "step_id": "op", "sequence": 1, "step_type": "DOMAIN_OPERATION", "context": {}}, state, m)


def test_the_code_under_test_is_this_checkout():
    for mod in (C, M, service, TC, W):
        assert pathlib.Path(mod.__file__).resolve().is_relative_to(ROOT), f"{mod.__name__} resolved outside {ROOT}: {mod.__file__}"


# ─────────────────────────────────────────────────────────── population discovery
def test_population_nomination_covers_every_lane_ranks_by_voi_and_compiles_channel_queries():
    cache = ENGINE / "registry" / "compiled" / "registry_snapshot.json"
    before = cache.stat().st_mtime_ns if cache.exists() else None
    out = _exec("population.nominate", {"signal": SEED, "primitives": PRIMITIVES, "communities": ["r/running"]})["output"]
    leads = out["population_leads"] + out["community_leads"]
    assert {l["source_lane"] for l in leads} >= {"SIGNAL", "CORPUS", "LATENT", "REGISTRY"}                  # the seed, the knowledge, the latent problem, the registry situations
    assert any(l.get("search_mode") == "LATENT" for l in leads)                                           # a population nobody named: searched by its friction language
    assert all(l["authority"] == "LEAD" and l["channel_queries"] and isinstance(l["voi"], float) for l in leads)
    by_id = {l["id"]: l for l in leads}
    vois = [by_id[i]["voi"] for i in out["ranked_lead_ids"]]
    assert sorted(out["ranked_lead_ids"]) == sorted(by_id) and vois == sorted(vois, reverse=True)
    assert 1 <= len(out["batch"]) <= 4 and out["batch"] == out["ranked_lead_ids"][: len(out["batch"])]
    again = _exec("population.nominate", {"signal": SEED, "primitives": PRIMITIVES, "communities": ["r/running"]})["output"]
    assert {k: v for k, v in again.items() if k != "_domain"} == {k: v for k, v in out.items() if k != "_domain"}       # deterministic: no clock, no cache
    assert (cache.stat().st_mtime_ns if cache.exists() else None) == before                               # a governed operation never writes the engine's registry build cache


def test_population_refusals_are_typed():
    assert _exec("population.nominate", {"signal": SEED})["gap"]["code"] == "POPULATION_INPUT_MISSING"
    assert _exec("research.plan", {"research_directive": {"objective": "x"}})["gap"]["code"] == "RESEARCH_DIRECTIVE_MISSING"


# ─────────────────────────────────────────────────────────── Trail says WHAT, the engine says HOW
def test_research_plan_keeps_governance_and_trail_intents_and_adds_channel_intents_within_budget():
    leads = _exec("population.nominate", {"signal": SEED, "primitives": PRIMITIVES, "communities": ["r/running"]})["output"]
    out = _exec("research.plan", {"research_directive": DIRECTIVE, "leads": leads["population_leads"] + leads["community_leads"], "batch": leads["batch"],
                                  "communities": leads["communities"]})["output"]
    d = out["research_directive"]
    for key in ("objective", "evidence_gaps", "preferred_source_roles", "disallowed_source_roles", "freshness_requirement", "geography", "language",
                "minimum_independent_sources", "success_condition", "falsification_condition", "budget"):
        assert d[key] == DIRECTIVE[key], key                                                              # WHAT is TrailSignal's, untouched
    assert out["governance_unchanged"] is True
    assert d["search_intents"][:2] == DIRECTIVE["search_intents"]                                          # Trail's intents first, in order, unmodified
    added = d["search_intents"][2:]
    assert added and len(d["search_intents"]) == DIRECTIVE["budget"]["max_queries"] == out["planned"]["intent_cap"]
    assert out["planned"]["dropped_over_budget"] > 0 and out["planned"]["channel_intents"] == len(added)   # what did not fit is COUNTED
    asked = {r for i in DIRECTIVE["search_intents"] for r in i["evidence_roles"]}
    for i in added:
        assert set(i["evidence_roles"]) <= asked and i["evidence_goal"] in {"complaint", "workaround"}     # a channel serves only roles Trail asked for
        assert "{" not in i["template"] and any(s in i["intent"] for s in SOURCE_NAMES + ("forum",))       # a compiled procedure, not an unfilled template
    assert any("keys bounce" in i["template"] or "bounce" in i["template"] for i in added)                 # the gap's own language reached the query


def test_without_gaps_the_live_hypothesis_statements_are_the_subjects():
    directive = {**copy.deepcopy(DIRECTIVE), "evidence_gaps": []}
    out = _exec("research.plan", {"research_directive": directive, "hypotheses": [{"hypothesis_id": "hyp_" + "1" * 12, "statement": "dog walkers drop treat bags when the leash pulls"}]})["output"]
    assert out["planned"]["subjects"] == 1 and any("leash" in i["template"] or "treat" in i["template"] for i in out["research_directive"]["search_intents"][2:])


# ─────────────────────────────────────────────────────────── the gate: the EXISTING runtime hands the enriched directive to the harness
class _Trail:
    def __init__(self):
        self.calls: list[str] = []

    def handle(self, req: httpx.Request) -> httpx.Response:
        body = json.loads(req.content); name = body["params"]["name"]; payload = (body["params"]["arguments"].get("request") or {}).get("payload") or {}
        self.calls.append(name)
        ids = [h["hypothesis_id"] for h in payload.get("hypotheses") or []]
        env = {"operation_id": f"op-{len(self.calls)}", "operation_kind": name, "status_revision": 1, "registry_snapshot": SNAP}
        if name == "registry.project":
            result = {"priors": [{"registry_record_id": "fr-03", "prior_role": "friction_primitive", "hypothesis_ids": ids}], "redundancy_groups": []}
        elif name == "gaps.compile":
            d = copy.deepcopy(DIRECTIVE)
            d["evidence_gaps"] = [{**g, "hypothesis_id": ids[0]} for g in d["evidence_gaps"]]
            result = {"research_directive": d}
        else:
            raise AssertionError(name)
        value = {**env, "result": result}
        return httpx.Response(200, json={"jsonrpc": "2.0", "id": body["id"], "result": {"content": [{"type": "text", "text": json.dumps(value)}], "structuredContent": value, "isError": False}})


def _knowledge(step, state, m):
    return {"output": {"rows": [{"id": "chunk_k1", "kind": "chunk", "corpus_id": "probe", "text": "pockets bounce"}]}, "evidence_refs": [{"kind": "chunk", "id": "chunk_k1", "corpus_id": "probe"}]}


@pytest.fixture
def runtime(monkeypatch):
    store, trail = MemoryStore(), _Trail()
    monkeypatch.setattr(service, "store", store)
    monkeypatch.setattr(W, "_TRAIL", TC.TrailMCPClient("http://trail.stub/mcp", "stub-token", transport=httpx.MockTransport(trail.handle)))
    service.reset_registry()
    yield store, trail
    service.reset_registry()


def test_the_existing_runtime_hands_the_enriched_directive_to_the_harness(runtime):
    store, trail = runtime
    execs = {**W.EXECUTORS, "POLYMATH_RETRIEVE": _knowledge}
    rid = service.start(None, adapter_id=ADAPTER_ID, input_payload={"seed": SEED, "corpus_ids": ["probe"]}, request_options={"corpus_ids": ["probe"]}, directory=FIXTURES)["run_id"]
    action = None
    for _ in range(30):
        st = service.advance(None, rid, execs, max_steps=1, directory=FIXTURES)
        if st.terminal:
            break
        if st.status == "awaiting_agent":
            step = service.next_step(None, rid, directory=FIXTURES)["step"]
            payload = {"hypotheses": [{"statement": "runners lose access to small items mid-stride because pockets bounce", "supporting_evidence_ids": ["chunk_k1"]}]}
            service.submit(None, rid, {"step_id": step["step_id"], "payload": payload, "submitted_by": {"agent_identity": "test-agent"}}, directory=FIXTURES)
        elif st.status == "awaiting_harness":
            step = service.next_step(None, rid, directory=FIXTURES)["step"]
            action = step["harness_action"]
            assert C.validate("harness_action", action) == []                                           # the enriched directive still makes a contract-valid HarnessActionV1
            rec = json.loads((ROOT / "contracts/adapter/v1/harness_receipt.example.json").read_text())
            rec.update({"action_id": action["action_id"], "run_id": rid, "harness_id": "test-harness"})
            for o in rec["observations"]:
                o["hypothesis_ids"] = action["hypothesis_ids"][:1]
            service.submit(None, rid, {"step_id": step["step_id"], "payload": rec, "submitted_by": {"agent_identity": "test-harness"}, "kind": "receipt"}, directory=FIXTURES)
    assert st.status == "completed", (st.status, st.gap, st.failure)
    assert trail.calls == ["registry.project", "gaps.compile"]
    assert [r["step_id"] for r in store.list_steps(None, rid)] == ["retrieve", "hypothesize", "project", "gaps", "plan", "research", "compile"]
    intents = action["search_intents"]
    assert [i["intent_id"] for i in intents[:2]] == ["q-complaint", "q-workaround"]                         # TrailSignal's intents, first
    assert len(intents) == DIRECTIVE["budget"]["max_queries"] and all("~" in i["intent_id"] for i in intents[2:])   # then the domain's compiled channel intents
    assert action["budget"]["max_queries"] == 24                                                          # the manifest's harness budget still wins, exactly as before
    assert action["freshness_requirement"]["max_age_days"] == 14 and action["minimum_independent_sources"] == 3 and action["disallowed_source_roles"] == ["supplier_listing"]
    assert hashlib.sha256(json.dumps(action["evidence_gaps"], sort_keys=True).encode()).hexdigest() == \
        hashlib.sha256(json.dumps(store.list_steps(None, rid)[3]["output"]["research_directive"]["evidence_gaps"], sort_keys=True).encode()).hexdigest()
