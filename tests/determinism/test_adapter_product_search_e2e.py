"""PRODUCT-SEARCH-E2E (owner, 2026-11-01) — the adapter slice, through the REAL runtime (`service.start / advance / next_step / submit`, the
real worker executors and the real out-of-process ecommerce domain) on the in-memory store double. No Postgres, no network, no CJ key:
  * seed optional: a seed-less start derives a CORPUS seed (lineage in the start receipt) and the knowledge steps search it, receipted;
    a limit (category, language) never silently becomes the search need;
  * corpus_ids default: the caller's share of "all libraries" — the owner and a friend, through the real HTTP route and web_scope;
  * F12: a merchandising-only seed is refused AT START with a plain hint;
  * every HARNESS_ACTION step carries `agent_reach` (exact local commands per search intent, from the channel DATA table) beside it;
  * S_supply: the host's supplier reads arrive as a draft HarnessResearchReceiptV1, and a failed read as a fallback to Agent Reach;
  * A-09 / A-10 / A-12, F2 (law at submit, portfolio direction, generation cap), F3 / F4 (cache, parallel, row budget, fair merge),
    F7 (three phases, lease per call, the fallback path), F8 (cancel closes the step, idle expiry), F15 (list filter), check-page URLs.
"""
from __future__ import annotations

import contextlib
import copy
import json
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
for _sub in ("workers", "shared", "orchestrator"):
    sys.path.insert(0, str(ROOT / _sub))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
sys.path.insert(0, str(ROOT / "adapters" / "ecommerce" / "python"))

from polymath_shared.adapter import contracts as C  # noqa: E402
from polymath_shared.adapter import corpus_seed as CS  # noqa: E402
from polymath_shared.adapter import evidence_boundary as EB  # noqa: E402
from polymath_shared.adapter import hypotheses as H  # noqa: E402
from polymath_shared.adapter import service  # noqa: E402
from polymath_shared.adapter import transitions as T  # noqa: E402
from polymath_shared.adapter.transitions import RunState, SubmissionRejected  # noqa: E402
import workers.adapter_step_worker as W  # noqa: E402
import test_adapter_ecommerce_product_research_e2e as SCRIPT  # noqa: E402
from _adapter_memory_store import MemoryStore  # noqa: E402

ADAPTER = "ecommerce.product_research"


def _row(cid, docs, *, all_libs=True):
    return {"corpus_id": cid, "purpose": "production", "query_enabled": True, "documents": docs, "query_ready": docs > 0, "in_all_libraries": all_libs}


CATALOG = {
    "corpora": [_row("c-big", 9), _row("c-mid", 4), _row("c-small", 2), _row("fr-fred", 3), _row("c-probe", 7, all_libs=False)],
    "profiles": [{"corpus_id": "c-big", "doc_id": "d1", "topics": ["night shift nursing", "sleep loss"], "questions": ["How do night-shift nurses keep meals cold?"], "terms": []},
                 {"corpus_id": "c-big", "doc_id": "d2", "topics": ["Night shift nursing", "ward breaks"], "questions": [], "terms": []},
                 {"corpus_id": "c-mid", "doc_id": "d3", "topics": ["ward breaks"], "questions": [], "terms": []}],
    "atoms": [{"corpus_id": "c-big", "doc_id": "d2", "kind": "TENSION", "text": "Nurses need food breaks but cannot leave the ward"}],
    "summaries": [],
}
OWNER_VIEW = lambda ids: [c for c in ids if not c.startswith("fr-")]                          # noqa: E731 — web_scope.all_libraries_view, owner


@pytest.fixture
def store(monkeypatch):
    s = MemoryStore()
    monkeypatch.setattr(service, "store", s)
    service.reset_registry()
    yield s
    service.reset_registry()


def test_the_code_under_test_is_this_checkout():
    for mod in (C, CS, EB, service, W):
        assert pathlib.Path(mod.__file__).resolve().is_relative_to(ROOT), f"{mod.__name__} resolved outside {ROOT}"


# ─────────────────────────────────────────────────────────── 1. seed optional: the corpus seed, its lineage, the receipt
def test_a_seedless_start_derives_a_corpus_seed_with_lineage_and_every_knowledge_step_searches_it(store, monkeypatch):
    store.catalog = copy.deepcopy(CATALOG)
    ref = service.start(None, adapter_id=ADAPTER, input_payload={}, corpus_view=OWNER_VIEW)
    rec = ref["start_receipt"]
    assert C.validate("adapter_run_ref", {k: v for k, v in ref.items() if k != "start_receipt"}) == []          # the ref contract is unchanged
    assert rec["corpus_scope"] == {"corpus_ids": ["c-big", "c-mid", "c-small"], "origin": "default", "candidates": 3, "ranked_by": None}
    seed = rec["seed"]
    assert seed["origin"] == "corpus" and seed["text"].startswith("The problems, workarounds and situations people meet around night shift nursing")
    assert "Open question: How do night-shift nurses keep meals cold?" in seed["text"] and "Tension: Nurses need food breaks" in seed["text"]
    lin = seed["lineage"]
    assert lin["derivation"] == "corpus-seed-v1" and lin["corpora"] == ["c-big", "c-mid", "c-small"] and lin["doc_ids"] == ["d1", "d2", "d3"]
    assert lin["fields"][0] == {"field": "doc_profile.topics", "value": "night shift nursing", "doc_ids": ["d1", "d2"], "documents": 2}
    assert {f["field"] for f in lin["fields"]} >= {"doc_profile.questions", "document_profile_atoms.TENSION"} and "ROUTING ONLY" in lin["authority"]
    state = store.load_run(None, ref["run_id"])[0]
    assert state.input == {"seed": seed["text"], "seed_origin": "corpus"} and state.options["corpus_ids"] == ["c-big", "c-mid", "c-small"]
    assert "seed_check" not in rec                                                              # a corpus seed is never put through the seed check

    sent = []
    monkeypatch.setattr(W, "_orch_post", lambda path, body, user_agent=None: sent.append((path, body)) or {"queries": [], "rows": []})
    st = service.advance(None, ref["run_id"], W.EXECUTORS, max_steps=2)                         # A_understand (VALIDATE) + B_plan (compile plan)
    rows = store.list_steps(None, ref["run_id"])
    assert rows[0]["output"]["start_receipt"] == rec                                             # the entry step keeps the start receipt on record
    assert sent[0][0] == "/retrieve/plan" and sent[0][1]["signal"] == seed["text"] and sent[0][1]["corpus_ids"] == ["c-big", "c-mid", "c-small"]
    assert rows[1]["output"]["need_source"] == "input.seed" and rows[1]["output"]["seed_origin"] == "corpus" and st.status == "running"


def test_a_corpus_with_no_signal_refuses_the_start_and_nothing_is_stored(store):
    store.catalog = {"corpora": [_row("c-empty", 3)], "profiles": [], "atoms": [], "summaries": []}
    with pytest.raises(CS.StartRefused) as e:
        service.start(None, adapter_id=ADAPTER, input_payload={}, corpus_view=OWNER_VIEW)
    assert e.value.code == "SEED_UNAVAILABLE" and "give a seed" in e.value.hint and store.runs == {}


def test_a_limit_never_becomes_the_search_need():
    m = service.manifest_for(ADAPTER)
    state = RunState(run_id="adr_" + "1" * 32, adapter_id=ADAPTER, input={"category": "kitchen", "language": "en", "geography": "US"})
    with pytest.raises(ValueError, match="NEED_MISSING"):
        W._need({"step_id": "B_plan", "context": {}}, state, m)
    with pytest.raises(ValueError):
        EB.original_needs({"source": "input.seed"}, {"category": "kitchen", "language": "en"})
    assert EB.original_needs({"source": "input.seed"}, {"seed": "nurses skip meals", "category": "kitchen"}) == ["nurses skip meals"]
    assert W._need({"step_id": "B_plan", "context": {}}, RunState(run_id=state.run_id, adapter_id=ADAPTER, input={"seed": "s1", "category": "k"}), m) == ("s1", "input.seed")


# ─────────────────────────────────────────────────────────── 2. corpus_ids default: the owner and a friend, through the real route
def _route_client(monkeypatch, store, principal=None):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    import orchestrator.api.adapter as API
    import orchestrator.mcp_principals as P
    import orchestrator.web_scope as WS
    monkeypatch.setattr(API, "tx", contextlib.nullcontext)                                     # no database: the store double answers
    if principal:
        monkeypatch.setattr(API.principal_context, "current", lambda: principal["principal_id"])
        monkeypatch.setattr(WS, "current_principal", lambda: P.Principal(principal_id=principal["principal_id"], corpus_ids=frozenset(principal["corpus_ids"]),
                                                                         adapter_ids=frozenset(principal["adapter_ids"])))
    else:
        monkeypatch.setattr(WS, "current_principal", lambda: None)
    app = FastAPI()
    app.include_router(API.router)
    return TestClient(app)


def test_the_owner_and_a_friend_get_the_same_default_scope_rule_through_the_route(store, monkeypatch):
    store.catalog = copy.deepcopy(CATALOG)
    owner = _route_client(monkeypatch, store)
    r = owner.post("/adapter/start", json={"adapter_id": ADAPTER, "input": {"seed": "night-shift nurses skip meals on the ward"}})
    assert r.status_code == 200, r.text
    assert r.json()["start_receipt"]["corpus_scope"]["corpus_ids"] == ["c-big", "c-mid", "c-small"]                # never a friend's private library
    assert store.run_owner(None, r.json()["run_id"]) == (True, None)

    fred = {"principal_id": "prn_fred", "corpus_ids": ["c-small", "fr-fred", "c-probe"], "adapter_ids": [ADAPTER]}
    friend = _route_client(monkeypatch, store, fred)
    r = friend.post("/adapter/start", json={"adapter_id": ADAPTER, "input": {"seed": "night-shift nurses skip meals on the ward"}})
    assert r.status_code == 200, r.text                                                         # the defect: 422 CORPUS_IDS_REQUIRED
    scope = r.json()["start_receipt"]["corpus_scope"]
    assert scope["origin"] == "default" and scope["corpus_ids"] == ["fr-fred", "c-small"]       # its grant ∩ all libraries, ranked by size
    state = store.load_run(None, r.json()["run_id"])[0]
    assert state.options["corpus_ids"] == ["fr-fred", "c-small"] and store.run_owner(None, r.json()["run_id"]) == (True, "prn_fred")
    named = friend.post("/adapter/start", json={"adapter_id": ADAPTER, "input": {"seed": "nurses skip meals", "corpus_ids": ["c-big"]}})
    assert named.status_code == 403                                                             # outside the grant: refused, never defaulted around


def test_a_named_corpus_is_validated_at_start(store):
    store.catalog = copy.deepcopy(CATALOG)
    with pytest.raises(CS.StartRefused) as e:
        service.start(None, adapter_id=ADAPTER, input_payload={"seed": "nurses skip meals", "corpus_ids": ["nope"]})
    assert e.value.code == "CORPUS_UNKNOWN"
    store.catalog["corpora"].append(_row("c-new", 0))
    with pytest.raises(CS.StartRefused) as e:
        service.start(None, adapter_id=ADAPTER, input_payload={"seed": "nurses skip meals"}, request_options={"corpus_ids": ["c-new"]})
    assert e.value.code == "CORPUS_NOT_READY" and store.runs == {}                               # never a run that dies later with INPUT_SCOPE_MISSING


# ─────────────────────────────────────────────────────────── 3. F12: a seed that can generate nothing, told at start
def test_a_merchandising_only_seed_is_refused_at_start_with_a_plain_hint(store, monkeypatch):
    with pytest.raises(CS.StartRefused) as e:
        service.start(None, adapter_id=ADAPTER, input_payload={"seed": "Holiday gifts under $50", "corpus_ids": ["probe"]})
    assert e.value.code == "SEED_NOT_GENERATIVE" and "problem, an audience or a situation" in e.value.hint and "leave the seed out" in e.value.hint
    assert store.runs == {}
    ok = service.start(None, adapter_id=ADAPTER, input_payload={"seed": "commuters spill coffee in the car", "corpus_ids": ["probe"]})
    assert ok["start_receipt"]["seed_check"]["generative"] is True and ok["start_receipt"]["seed"]["origin"] == "user"
    client = _route_client(monkeypatch, store)
    r = client.post("/adapter/start", json={"adapter_id": ADAPTER, "input": {"seed": "trending products under $20", "corpus_ids": ["probe"]}})
    assert r.status_code == 422 and r.json()["detail"]["error_code"] == "SEED_NOT_GENERATIVE" and r.json()["detail"]["hint"]


def test_the_genuine_no_signal_refusal_says_what_to_do_next():
    from polymath_shared.adapter import domain as DOMAIN
    for origin, needle in (("user", "leave the seed out"), ("corpus", "the seed was derived from the corpora")):
        req = DOMAIN.request(domain="ecommerce", operation="understanding.no_signal", run_id="adr_" + "2" * 32, step_id="Z_no_signal", run_input={},
                             scope={"x": {"primitives": {"generative_signal": False}, "origin": origin}},
                             config={"inputs": {"primitives": "x.primitives", "seed_origin": "x.origin"}})
        gap = DOMAIN.run("ecommerce", "understanding.no_signal", req)["gap"]
        assert gap["code"] == "NO_GENERATIVE_SIGNAL" and "retained as knowledge only" in gap["message"] and needle in gap["message"]


# ─────────────────────────────────────────────────────────── 4 + 5. agent_reach beside every research step; the supply draft
def _fake_supplier(calls):
    def search(principal_id, args):
        calls.append((principal_id, dict(args)))
        q = args["query"]
        if "belt clip" in q:
            return {"status": "OK", "query": q, "retrieved_at": "2026-11-01T10:00:00Z",
                    "sources": [{"source_id": "src_cj1", "url": "https://cjdropshipping.com/product/magnetic-key-clip-p-1234567890AB.html",
                                 "source_class": "supplier_listing", "retrieved_at": "2026-11-01T10:00:00Z", "published_at_if_known": None}],
                    "items": [{"item_id": "itm_1", "kind": "listing", "source_id": "src_cj1", "excerpt": "Magnetic key clip",
                               "listing": {"title": "Magnetic key clip for runners", "price_as_listed": "US$2.10", "minimum_order_as_listed": "1 unit",
                                           "supplier": None, "product_id": "1234567890AB"}}],
                    "limitations": ["from the supplier's own catalogue API"]}
        if "wrist" in q:
            from polymath_shared.acquisition.service import AcquisitionRefused
            raise AcquisitionRefused(403, "OWNER_ONLY", "the supplier tools use the owner's account")
        return {"status": "UNAVAILABLE", "items": [], "sources": [], "limitations": ["the supplier API could not answer (timeout)"],
                "fallback": {"kind": "AGENT_REACH", "reason_code": "SUPPLIER_API_TIMEOUT", "why": "timeout", "commands": [{"step": 1, "run": "echo s1-fallback"}],
                             "install": {"repo": "https://github.com/Panniantong/Agent-Reach", "verify": "agent-reach doctor --json"}}}
    return search


def _drive(agent, store):
    execs = {**W.EXECUTORS, "POLYMATH_RETRIEVE": SCRIPT._knowledge, "POLYMATH_COMPILE_PLAN": SCRIPT._knowledge, "POLYMATH_GRAPH_EXPAND": SCRIPT._knowledge}
    rid = service.start(None, adapter_id=ADAPTER, input_payload={"seed": SCRIPT.SEED, "corpus_ids": ["probe"]})["run_id"]
    seen: dict[str, dict] = {}
    st = None
    for _ in range(200):
        st = service.advance(None, rid, execs, max_steps=1)
        if st.terminal:
            break
        if st.status in ("awaiting_agent", "awaiting_harness"):
            nxt = service.next_step(None, rid)
            step = nxt["step"]
            if st.status == "awaiting_agent":
                try:
                    service.submit(None, rid, {"step_id": step["step_id"], "payload": agent.answer(nxt), "submitted_by": {"agent_identity": "test-agent"}})
                except SubmissionRejected as exc:
                    agent.rejections.setdefault(step["step_id"], []).append(list(exc.errors))
            else:
                seen[step["step_id"]] = nxt
                service.submit(None, rid, {"step_id": step["step_id"], "payload": SCRIPT._harness(step, rid), "submitted_by": {"agent_identity": "t"}, "kind": "receipt"})
    return rid, st, seen


@pytest.fixture
def stub_run(monkeypatch):
    import httpx
    from polymath_shared.adapter import trail_client as TC
    store, trail, calls = MemoryStore(), SCRIPT.StubTrail(), []
    monkeypatch.setattr(service, "store", store)
    monkeypatch.setattr(W, "_TRAIL", TC.TrailMCPClient("http://trail.stub/mcp", "stub-token", transport=httpx.MockTransport(trail.handle)))
    monkeypatch.setitem(W.HOST_TOOLS, "supplier_search", _fake_supplier(calls))
    service.reset_registry()
    SCRIPT.NEEDS.clear()
    yield store, calls
    service.reset_registry()


def test_every_research_step_carries_exact_local_commands_for_every_search_intent(stub_run):
    store, _calls = stub_run
    rid, st, seen = _drive(SCRIPT.Agent(), store)
    assert st.status == "completed", (st.gap, st.failure)
    for sid, stage in (("I_research", "AGENT_RESEARCH"), ("P_reality", "PRODUCT_REALITY_CHECK"), ("S_supply", "SUPPLIER_RESEARCH")):
        nxt = seen[sid]
        ar, action = nxt["agent_reach"], nxt["step"]["harness_action"]
        assert ar["local_only"] is True and ar["stage"] == stage and ar["install"]["verify"] == "agent-reach doctor --json"
        assert ar["install"]["repo"] == "https://github.com/Panniantong/Agent-Reach" and any("built-in web search" in n for n in ar["never"])
        assert [p["intent_id"] for p in ar["per_intent"]] == [i["intent_id"] for i in action["search_intents"]], sid      # S-17: no intent unmapped
        for p in ar["per_intent"]:
            assert p["commands"] and p["tool_class"] in ("browser", "web_search", "web_fetch", "api") and f"intent: {p['intent_id']}" in p["receipt_tags"]
            assert p["channel"] in ar["channels"] and not any("{" in c for c in p["commands"])
        for intent in action["search_intents"]:                                                    # the action itself stays harness-neutral
            assert not any(t in f"{intent.get('template') or ''} {intent['intent']}".lower() for t in ("opencli", "mcporter", "curl ", "yt-dlp"))
    field = seen["I_research"]["agent_reach"]
    assert len({p["channel"] for p in field["per_intent"]}) >= 3 and any(p["assigned_by"] == "planner" for p in field["per_intent"])
    reality = seen["P_reality"]["agent_reach"]["per_intent"]
    assert {p["channel"] for p in reality} <= {"amazon_listings", "retail_web", "amazon_reviews", "youtube_reviews"}
    assert any(t.startswith("concept: pc_") for p in reality for t in p["receipt_tags"])
    supply = seen["S_supply"]["agent_reach"]["per_intent"]
    assert {p["channel"] for p in supply} == {"alibaba", "cjdropshipping"} and all(p["parse"]["tool"] == "supplier_parse" for p in supply)
    ali = next(p for p in supply if p["channel"] == "alibaba")
    assert ali["commands"][0].startswith("mcporter call exa.web_search_exa 'query=site:alibaba.com ") and "objective=" in ali["commands"][0]


def test_the_supply_step_carries_a_draft_receipt_from_the_host_reads_and_a_fallback_for_each_failed_read(stub_run):
    store, calls = stub_run
    rid, st, seen = _drive(SCRIPT.Agent(), store)
    assert st.status == "completed", (st.gap, st.failure)
    nxt = seen["S_supply"]
    action, draft = nxt["step"]["harness_action"], nxt["supplier_draft"]
    assert [c[0] for c in calls] == [None, None, None]                                           # the run OWNER's principal (the owner: None)
    assert {c[1]["source"] for c in calls} == {"cj"} and any("belt clip" in c[1]["query"] for c in calls)
    receipt = draft["receipt"]
    assert C.validate("harness_receipt", receipt) == [] and T.validate_receipt(nxt["step"], receipt) == []        # a valid receipt for THIS action
    assert receipt["action_id"] == action["action_id"] and receipt["harness_id"] == "polymath-host/supplier-api-draft"
    ctx = " | ".join(o["context"] for o in receipt["observations"])
    for tag in ("listing: Magnetic key clip for runners", "supplier: none", "price as listed: US$2.10", "MOQ as listed: 1 unit", "channel: cjdropshipping", "concept: pc_1"):
        assert tag in ctx, tag
    assert {o["evidence_role_claimed"] for o in receipt["observations"]} == {"price", "supply"} and receipt["tool_trace"][0]["tool_class"] == "api"
    by = {x["concept_id"]: x for x in draft["lookups"]}
    assert by["pc_1"]["status"] == "OK" and by["pc_1"]["items"] == 1 and "fallback" not in by["pc_1"]
    assert by["pc_2"]["fallback"]["kind"] == "AGENT_REACH" and by["pc_2"]["fallback"]["reason_code"] == "OWNER_ONLY"            # refused -> built from the table
    assert by["pc_2"]["fallback"]["commands"][0]["run"].startswith("mcporter call exa.web_search_exa 'query=site:cjdropshipping.com ")
    assert by["pc_3"]["fallback"]["commands"] == [{"step": 1, "run": "echo s1-fallback"}]                                   # the acquisition slice's own fallback, as given
    cj = {p["intent_id"]: p for p in nxt["agent_reach"]["per_intent"] if p["channel"] == "cjdropshipping"}
    assert sorted(p["host_api"]["status"] for p in cj.values()) == ["OK", "UNAVAILABLE", "UNAVAILABLE"]
    assert sum(1 for p in cj.values() if "fallback" in p) == 2
    accepted = next(r for r in store.list_steps(None, rid) if r["step_id"] == "S_supply")
    assert [x["status"] for x in accepted["output"]["_host_prefetch"]] == [x["status"] for x in draft["lookups"]]          # the lineage stays


# ─────────────────────────────────────────────────────────── 6. A-09 / A-10 / A-12
def _hyp(hid, status, rev=0):
    return {"hypothesis_id": hid, "run_id": "adr_" + "3" * 32, "parent_hypothesis_ids": [], "revision": rev, "statement": "runners lose keys",
            "mechanism": None, "population": None, "activity": None, "task": None, "context": None, "suspected_friction": None, "status": status,
            "knowledge_support": [], "trail_priors": [], "field_evidence_ids": [], "assumptions": [], "contradictions": [], "falsifiers": [],
            "knowledge_gaps": [], "created_at": "2026-11-01T00:00:00Z", "updated_at": "2026-11-01T00:00:00Z"}


def test_a09_a_reasoning_revise_never_erases_the_judges_verdict():
    weak, fresh = "hyp_" + "a" * 24, "hyp_" + "b" * 24
    step = {"step_id": "K_revise", "sequence": 9}
    req = lambda hid: [{"hypothesis_id": hid, "kind": "REVISE", "cause_refs": [{"kind": "chunk", "id": "chunk_1"}], "changes": {"context": "mid-stride"}}]  # noqa: E731
    states, trs = H.apply("adr_" + "3" * 32, step, {weak: _hyp(weak, "weakened", 2)}, req(weak), actor="theta", allowed_causes={"chunk_1": "chunk"},
                          recorded_at="2026-11-01T00:00:00Z")
    assert states[0]["status"] == "weakened" and states[0]["context"] == "mid-stride" and trs[0]["resulting_status"] == "weakened"   # was `revised` (eligible)
    states, _ = H.apply("adr_" + "3" * 32, step, {fresh: _hyp(fresh, "proposed")}, req(fresh), actor="theta", allowed_causes={"chunk_1": "chunk"},
                        recorded_at="2026-11-01T00:00:00Z")
    assert states[0]["status"] == "revised"
    import re
    eligible = re.search(r"ELIGIBLE_HYPOTHESIS_STATUSES = frozenset\(\{([^}]*)\}\)", (ROOT / "adapters/ecommerce/binding.py").read_text()).group(1)
    assert '"weakened"' not in eligible and '"revised"' in eligible                                   # so a revised-but-weakened hypothesis stays ineligible


def test_a10_one_friction_worded_two_ways_is_one_lived_cluster():
    import graph
    import lived_world as LW
    recs = [{"id": f"r{i}", "community": "trail runners", "friction_family": wording, "source": f"https://f{i}.example/t/{i}", "independence_group": f"g{i}",
             "source_identity": {"platform": f"f{i}", "thread_key": f"https://f{i}.example/t/{i}"}, "evidence_roles": ["FRICTION_EVIDENCE"]}
            for i, wording in enumerate(["keys bounce while running", "keys bouncing during runs", "Keys bounce, running", "keys bounce while running"])]
    state = {"data": {"field_records": recs, "population_leads": [], "community_leads": []}}
    LW.cards(state, graph.load_policies())
    clusters = state["data"]["lived_clusters"]
    assert len(clusters) == 1 and clusters[0]["friction_family"] == "keys bounce while running" and clusters[0]["record_count"] == 4
    assert LW.friction_key("gloves block zips") == LW.friction_key("glove blocks zip") != LW.friction_key("keys bounce")


def test_a12_the_final_interpretation_can_cite_every_research_stage(monkeypatch):
    s = MemoryStore()
    monkeypatch.setattr(service, "store", s)
    for n, adm in enumerate(("hadm_field", "hadm_reality", "hadm_supply")):
        for i in range(120 if n == 0 else 30):
            s.admitted.append({"evidence_id": f"fev_{n}_{i:03d}", "run_id": "adr_" + "4" * 32, "admission_id": adm, "evidence_role": "friction", "polarity": "supporting"})
    m = service.manifest_for(ADAPTER)
    state = RunState(run_id="adr_" + "4" * 32, adapter_id=ADAPTER, current_step_id="V_score", status="running")
    refs = service._context_refs(None, state, m)                                                   # the step about to be issued: W_interpret
    fev = [r["id"] for r in refs if r["kind"] == "field_evidence"]
    assert len(fev) == 180 and {i.split("_")[1] for i in fev} == {"0", "1", "2"}                     # every admission, all of supply and reality
    assert sum(1 for i in fev if i.startswith("fev_2_")) == 30
    default = service._context_refs(None, RunState(run_id=state.run_id, adapter_id=ADAPTER, current_step_id="C_hypotheses", status="running"), m)
    shares = [sum(1 for r in default if r["id"].startswith(f"fev_{n}_")) for n in range(3)]
    assert len(default) == 180 and min(shares) >= 26                                                # the default 200-ref display shares fairly too


# ─────────────────────────────────────────────────────────── F2: the law at submit; the portfolio's direction; the generation cap
class TwoHypothesesAgent(SCRIPT.Agent):
    """Generates TWO hypotheses (below the portfolio's floor of three), then — sent back to generation — the third."""
    def answer(self, nxt):
        out = super().answer(nxt)
        if nxt["step"]["step_id"] == "C_hypotheses":
            out["hypotheses"] = out["hypotheses"][:2] if len(self.seen["C_hypotheses"]) == 1 else out["hypotheses"][2:3]
        return out


def test_too_few_hypotheses_return_to_generation_not_to_the_bridges(stub_run):
    store, _ = stub_run
    rid, st, _seen = _drive(TwoHypothesesAgent(), store)
    order = [r["step_id"] for r in store.list_steps(None, rid)]
    first_bridge = order.index("C_bridge_route")
    assert order[first_bridge + 1] == "C_hypotheses"                                                 # was: back to C_bridge, three times
    law = next(r["output"] for r in store.list_steps(None, rid) if r["step_id"] == "C_bridge_law")
    assert law["portfolio_unreachable"] is True and law["portfolio_needs"] == "more"
    assert st.status == "completed", (st.gap, st.failure)


def test_a_generation_step_cannot_leave_more_live_hypotheses_than_the_portfolio_allows(stub_run):
    store, _ = stub_run
    m = service.manifest_for(ADAPTER)
    assert m.step("C_hypotheses")["config"]["max_live_hypotheses"] == 6 and m.step("C_hypotheses")["output_schema"]["properties"]["hypotheses"]["maxItems"] == 6
    for sid in ("C_primitives", "C_bridge", "K_situations", "N_concepts"):
        assert m.step(sid)["config"]["law_at_submit"] is True


def test_a_law_refusal_arrives_in_the_submit_response_and_beside_the_open_step(stub_run):
    store, _ = stub_run
    agent = SCRIPT.Agent()
    rid, st, _seen = _drive(agent, store)
    first = agent.rejections["C_primitives"][0]
    assert first[0].startswith("LAW_UNSATISFIED (C_lineage)") and any("UNCLASSIFIED" in e for e in first)
    assert any("UNCLASSIFIED" in e for e in agent.shown_rejection["C_primitives"][0]["errors"])
    rows = [r for r in store.list_steps(None, rid) if r["step_id"] == "C_lineage"]
    assert len(rows) == 1 and rows[0]["output"]["valid"] is True and st.branch_loops == 3             # same repair budget as before


# ─────────────────────────────────────────────────────────── F3 / F4 / F7: the evidence calls
EXAMPLE_PACKET = json.loads((ROOT / "contracts/evidence/v1/evidence_packet.example.json").read_text())


def _need_tag(need):
    return "n" + str(sum(map(ord, need)))                                                        # a stable tag per need (never `hash`, salted per process)


def _packet(need, corpus, n=12):
    items = [{"chunk_id": f"{corpus}:{_need_tag(need)}:{i}", "document_id": "doc_x", "source": "src", "text": f"{need} row {i}", "origin": "USER", "query_ids": ["q0"],
              "lineage": [{"query_id": "q0", "origin": "USER", "role": "PRIMARY"}], "utility_role": "DIRECT", "synthesis_role": None,
              "ca4_grade": "DIRECT" if i < 3 else "RELATED", "c4_valid": i < 3, "provenance": {"origin": "USER"}} for i in range(n)]
    return {"evidence_packet": {**copy.deepcopy(EXAMPLE_PACKET), "evidence": items}, "synthesis_performed": False}


def _evidence_step(m, sid="F_retrieve", hyps=6):
    return {"run_id": "adr_" + "5" * 32, "step_id": sid, "sequence": 7, "step_type": "POLYMATH_RETRIEVE",
            "context": {"hypotheses": [{"hypothesis_id": f"hyp_{c * 12}", "revision": 0, "status": "proposed", "statement": f"hypothesis {c}"} for c in "abcdef"[:hyps]]},
            "_corpus_generations": {"probe": "g1"}}


def test_f3_f4_parallel_calls_a_row_budget_a_fair_merge_and_a_run_cache(monkeypatch):
    m = service.manifest_for(ADAPTER)
    posted, renewed = [], []
    monkeypatch.setattr(W, "_renew_lease", lambda: renewed.append(1))
    monkeypatch.setattr(EB, "scope_violation", lambda body, resp: None)

    def post(path, body, user_agent=None):
        W._renew_lease()
        posted.append(body["message"])
        assert "product" not in body          # the run's evidence calls stay byte-exact; the route skips product mode by user agent
        return _packet(body["message"], body["corpus_id"])
    monkeypatch.setattr(W, "_orch_post", post)
    state = RunState(run_id="adr_" + "5" * 32, adapter_id=ADAPTER, input={"seed": "s", "corpus_ids": ["probe"]})
    out = W.exec_evidence(_evidence_step(m), state, m, ["probe"], legacy=W._retrieve_legacy)["output"]
    assert len(posted) == 6 and out["parallel_calls"] == 2 and len(renewed) == 6                    # F_retrieve: min_rows_per_need 6 -> 40 // 6 = 6 calls
    assert len(out["rows"]) == 40 and {r["id"].split(":")[1] for r in out["rows"]} == {_need_tag(f"hypothesis {c}") for c in "abcdef"}   # every question kept rows
    assert [c["need_index"] for c in out["calls"]] == [0, 1, 2, 3, 4, 5] and out["need_source"] == "context.hypotheses"
    again = W.exec_evidence(_evidence_step(m), state, m, ["probe"], legacy=W._retrieve_legacy)["output"]
    assert len(posted) == 6 and again["cache_hits"] == 6 and [r["id"] for r in again["rows"]] == [r["id"] for r in out["rows"]]   # same question, same rows
    step = _evidence_step(m)
    step["_corpus_generations"] = {"probe": "g2"}                                                   # the corpus changed: asked again
    W.exec_evidence(step, state, m, ["probe"], legacy=W._retrieve_legacy)
    assert len(posted) == 12
    plan = EB.plan_calls(["a", "b", "c", "d", "e"], ["probe"], max_calls=5, row_budget=EB.row_budget_calls(40, 10))
    assert len(plan["calls"]) == 4 and plan["truncated"] == [{"corpus_id": "probe", "need_index": 4, "reason": "row_budget"}]


def test_f3_after_a_restart_the_cache_is_rebuilt_from_the_runs_own_stored_calls(monkeypatch):
    m = service.manifest_for(ADAPTER)
    posted = []
    monkeypatch.setattr(W, "_renew_lease", lambda: None)
    monkeypatch.setattr(EB, "scope_violation", lambda body, resp: None)
    monkeypatch.setattr(W, "_orch_post", lambda path, body, user_agent=None: posted.append(body["message"]) or _packet(body["message"], body["corpus_id"], n=6))
    state = RunState(run_id="adr_" + "8" * 32, adapter_id=ADAPTER, input={"seed": "s", "corpus_ids": ["probe"]})
    out = W.exec_evidence(_evidence_step(m), state, m, ["probe"], legacy=W._retrieve_legacy)["output"]
    assert len(posted) == 6 and len(out["rows"]) == 36 and all(c.get("cache_key") and len(c["row_ids"]) == 6 for c in out["calls"])
    W._EVIDENCE_CACHE.clear()                                                                       # a new worker process: no memory
    stored = RunState(run_id=state.run_id, adapter_id=ADAPTER, input=state.input, outputs={"F_retrieve": out}, output_order=("F_retrieve",))
    again = W.exec_evidence(_evidence_step(m), stored, m, ["probe"], legacy=W._retrieve_legacy)["output"]
    assert len(posted) == 6 and again["cache_hits"] == 6 and sorted(r["id"] for r in again["rows"]) == sorted(r["id"] for r in out["rows"])


def test_f7_the_fallback_path_runs_when_the_evidence_surface_is_down(monkeypatch):
    m = service.manifest_for(ADAPTER)
    renewed, paths = [], []
    monkeypatch.setattr(W, "_renew_lease", lambda: renewed.append(1))

    def post(path, body, user_agent=None):
        W._renew_lease()
        paths.append(path)
        if path == EB.EVIDENCE_PATH:
            raise W.OrchUnavailable("orchestrator /chat/evidence -> 503: breaker open")
        return {"evidence_rows": [{"id": "chunk_legacy", "kind": "chunk", "doc_id": "d", "corpus_id": "probe", "text": "legacy row", "score": 0.4}]}
    monkeypatch.setattr(W, "_orch_post", post)
    state = RunState(run_id="adr_" + "6" * 32, adapter_id=ADAPTER, input={"seed": "nurses skip meals", "corpus_ids": ["probe"]})
    step = {"run_id": state.run_id, "step_id": "B_retrieve", "sequence": 3, "step_type": "POLYMATH_RETRIEVE", "context": {}}
    out = W.exec_retrieve(step, state, m)
    assert out["output"]["fallback"] == "retrieve" and out["output"]["degraded"] is True and "evidence_boundary_unavailable" in out["output"]["degraded_reasons"]
    assert out["output"]["boundary_failures"][0]["error"].endswith("breaker open") and [r["id"] for r in out["evidence_refs"]] == ["chunk_legacy"]
    assert paths == [EB.EVIDENCE_PATH, "/retrieve"] and len(renewed) == 2                           # one lease renewal per call
    assert out["output"]["need_source"] == "input.seed"
    assert W.lease_seconds(120) == int(W.HTTP_TIMEOUT_S) + W.LEASE_MARGIN_S >= 74 + 75               # never shorter than one call + margin


def test_f7_an_outcome_is_never_applied_to_a_run_that_moved_on(store, monkeypatch):
    store.catalog = None
    rid = service.start(None, adapter_id=ADAPTER, input_payload={"seed": SCRIPT.SEED, "corpus_ids": ["probe"]})["run_id"]
    unit = service.prepare(None, rid, W.EXECUTORS)                                                # issues A_understand (automatic)
    assert unit.kind == "execute" and unit.step["step_id"] == "A_understand"
    outcome = service.execute(W.EXECUTORS, unit)                                                  # outside any transaction
    service.cancel(None, rid)                                                                     # meanwhile the requester cancels
    st = service.apply(None, rid, unit, outcome)
    assert st.status == "cancelled" and store.current_step(None, rid)["status"] == "skipped"        # discarded; the open step was closed (F8)
    with pytest.raises(service.LeaseLost):
        service.execute({"VALIDATE": lambda *a: (_ for _ in ()).throw(service.LeaseLost("lost"))}, unit)


# ─────────────────────────────────────────────────────────── F8: cancel closes the step; an idle run expires
def test_f8_cancel_closes_the_open_step_and_an_idle_run_expires_typed(stub_run):
    store, _ = stub_run
    execs = {**W.EXECUTORS, "POLYMATH_RETRIEVE": SCRIPT._knowledge, "POLYMATH_COMPILE_PLAN": SCRIPT._knowledge, "POLYMATH_GRAPH_EXPAND": SCRIPT._knowledge}
    a = service.start(None, adapter_id=ADAPTER, input_payload={"seed": SCRIPT.SEED, "corpus_ids": ["probe"]})["run_id"]
    b = service.start(None, adapter_id=ADAPTER, input_payload={"seed": SCRIPT.SEED, "corpus_ids": ["probe"]})["run_id"]
    for rid in (a, b):
        assert service.advance(None, rid, execs).status == "awaiting_agent"                        # at C_primitives
    service.cancel(None, a)
    row = store.current_step(None, a)
    assert row["status"] == "skipped" and row["receipt"]["validation"]["errors"][0].startswith("RUN_CANCELLED")
    store.runs[b]["idle"] = True
    assert service.expire_idle(None, idle_s=86400) == [b]
    st = store.load_run(None, b)[0]
    assert st.status == "terminal_gap" and st.gap["code"] == "AGENT_IDLE_EXPIRED" and st.gap["step_id"] == "C_primitives"
    assert store.current_step(None, b)["status"] == "skipped" and service.expire_idle(None, idle_s=86400) == []
    assert service.IDLE_EXPIRY_S == 86400


# ─────────────────────────────────────────────────────────── F15: the web adapter list is filtered per principal
def test_f15_a_friend_sees_only_the_adapters_its_grant_opens(store, monkeypatch):
    friend = _route_client(monkeypatch, store, {"principal_id": "prn_fred", "corpus_ids": ["c-small"], "adapter_ids": [ADAPTER]})
    assert [a["adapter_id"] for a in friend.get("/adapter/list").json()["adapters"]] == [ADAPTER]
    owner = _route_client(monkeypatch, store)
    assert len(owner.get("/adapter/list").json()["adapters"]) >= 4


# ─────────────────────────────────────────────────────────── a receipt citing a check page's URL is refused
def test_an_observation_whose_source_url_is_a_check_page_is_refused():
    receipt = json.loads((ROOT / "contracts/adapter/v1/harness_receipt.example.json").read_text())
    step = {"run_id": receipt["run_id"], "harness_action": {"action_id": receipt["action_id"]}}
    assert not [e for e in T.validate_receipt(step, receipt) if "CHALLENGE_PAGE_AS_EVIDENCE" in e]
    bad = copy.deepcopy(receipt)
    bad["sources"][0]["url"] = "https://cjdropshipping.com/egg/cj/validation.html"
    errs = [e for e in T.validate_receipt(step, bad) if "CHALLENGE_PAGE_AS_EVIDENCE" in e]
    assert errs and "is a verification page" in errs[0] and bad["observations"][0]["observation_id"] in errs[0]


# ─────────────────────────────────────────────────────────── adding a channel is a DATA change (ADR-0019 decision 6)
def test_a_new_channel_row_produces_commands_with_zero_code_change():
    import executors
    table = executors.channel_table()
    table["channels"]["bluesky"] = {"kind": "evidence", "query": "{q}", "family": "community", "why": "public posts", "where": "bsky.app",
                                    "collect": "posts and their replies", "expected_roles": ["FRICTION_EVIDENCE"], "tool_class": "web_search",
                                    "commands": [["mcporter", "call", "exa.web_search_exa", "query=site:bsky.app {query}", "numResults=10", "objective=Posts about {query}"]],
                                    "receipt_tags": ["community: <the feed>"]}
    table["stages"]["AGENT_RESEARCH"] = ["bluesky"]
    plan = executors.agent_reach_plan([{"intent_id": "q1", "template": "keys bounce", "evidence_roles": ["friction"]}], stage="AGENT_RESEARCH", table=table)
    entry = plan["per_intent"][0]
    assert entry["channel"] == "bluesky" and entry["commands"] == ["mcporter call exa.web_search_exa 'query=site:bsky.app keys bounce' numResults=10 'objective=Posts about keys bounce'"]
    assert entry["receipt_tags"] == ["intent: q1", "community: <the feed>"] and plan["channels"]["bluesky"]["where"] == "bsky.app"
    qs = executors.channel_queries("gap_1", "do runners lose keys", {"data": {}}, {"evidence_channels": ["bluesky"], "_channel_table": table})
    assert [q["channel"] for q in qs] == ["bluesky"] and qs[0]["where"] == "bsky.app" and qs[0]["tools"][0].startswith("mcporter call exa.web_search_exa")
    src = (ROOT / "adapters/ecommerce/python/executors.py").read_text()
    assert "== \"reddit\"" not in src and "== 'cjdropshipping'" not in src                        # no channel branch left in the engine
