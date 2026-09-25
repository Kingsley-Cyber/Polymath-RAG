"""K1b (gap K-04, register 11.487) — a response to a scoped request confirms the scope; Trail refuses one that does not.

Pre-K1 code ignores `scope` (its request models drop unknown fields) and answers 200 with evidence from every knowledge
role — the K1 live check's control run showed it on the fleet. So Trail cannot trust a 200; it must see its scope confirmed:
  1. the helpers: `echo_scope` (server), `echo_matches` (consumer), `EB.scope_violation`;
  2. every route whose request model takes a `scope` returns through `echo_scope` (an AST pin: a new scoped route that
     forgets it fails CI), and the routes Trail calls confirm in behaviour (/retrieve, /retrieve/plan, the chat runtime
     behind /chat and /chat/evidence);
  3. on the wire: a real local HTTP stand-in plays a pre-K1 orchestrator (200, no confirmation), a K1b one (confirms) and a
     widening one (confirms both roles). Every Trail path — the evidence route, its legacy fallback, the kill switch, the
     plan lane and the graph lane — is driven through the REAL `_orch_post` and fails closed on an unconfirmed answer.

The worker module is loaded BY FILE PATH (the editable .pth resolves `workers` to the main checkout)."""
from __future__ import annotations

import ast
import asyncio
import copy
import http.server
import importlib.util
import json
import pathlib
import sys
import threading
from types import SimpleNamespace

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(ROOT / "shared") not in sys.path:
    sys.path.insert(0, str(ROOT / "shared"))

from polymath_shared.adapter import evidence_boundary as EB  # noqa: E402
from polymath_shared.adapter.manifest import ADAPTER_DIR, list_manifests  # noqa: E402
from polymath_shared.adapter.transitions import RunState  # noqa: E402
from polymath_shared.code.scope import ECHO_KEY, echo_matches, echo_scope, parse_scope  # noqa: E402

API = ROOT / "orchestrator" / "orchestrator" / "api"
WORKER = ROOT / "workers" / "workers" / "adapter_step_worker.py"
REF = {"roles": ["reference"]}


# ─────────────────────────────────────────────────────────── 1. the helpers
def test_a_reply_is_confirmed_only_when_the_request_sent_a_scope():
    assert echo_scope({"a": 1}, None) == {"a": 1}                                        # no scope: unchanged
    assert echo_scope({"a": 1}, REF) == {"a": 1, ECHO_KEY: {"roles": ["reference"]}}
    assert echo_scope({}, {"roles": ["reference", "implementation"]})[ECHO_KEY] == {"roles": ["implementation", "reference"]}
    assert echo_scope({}, {"roles": [" Reference"]})[ECHO_KEY] == REF                    # the parsed scope, not the raw text
    assert echo_scope(["a list"], REF) == ["a list"]


def test_the_consumer_accepts_only_the_exact_confirmation():
    assert echo_matches(REF, {ECHO_KEY: {"roles": ["reference"]}})
    for bad in ({}, {ECHO_KEY: None}, {ECHO_KEY: {"roles": ["implementation", "reference"]}}, {ECHO_KEY: {"roles": ["implementation"]}},
                {ECHO_KEY: {"roles": "reference"}}, {ECHO_KEY: "reference"}, None, [], "reference"):
        assert not echo_matches(REF, bad), bad


def test_scope_violation_says_why_and_ignores_an_unscoped_call():
    assert EB.scope_violation({"query": "q"}, {"evidence": []}) is None
    assert EB.scope_violation({"scope": EB.TRAIL_SCOPE}, {ECHO_KEY: {"roles": ["reference"]}}) is None
    why = EB.scope_violation({"scope": EB.TRAIL_SCOPE}, {"evidence": []})
    assert why and "does not confirm the knowledge scope" in why and "got None" in why
    assert "got {'roles': ['implementation', 'reference']}" in EB.scope_violation(
        {"scope": EB.TRAIL_SCOPE}, {ECHO_KEY: {"roles": ["implementation", "reference"]}})


# ─────────────────────────────────────────────────────────── 2. the server confirms
#: /chat and /chat/evidence return what `run_chat` builds, and `run_chat` confirms (pinned below)
DELEGATES_TO_RUN_CHAT = {("chat.py", "chat"), ("chat.py", "chat_evidence")}
#: the SSE stream is not a JSON reply to confirm: no stream client sends a scope (the UI never does); its receipt keeps it (K1)
STREAM_ROUTES = {("ui.py", "chat_stream")}


def _own_nodes(fn: ast.AST):
    """The function's own statements and expressions, not those of functions nested inside it."""
    stack = list(fn.body)
    while stack:
        n = stack.pop()
        yield n
        stack.extend(c for c in ast.iter_child_nodes(n) if not isinstance(c, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)))


def _scoped_models() -> set[str]:
    return {n.name for f in API.glob("*.py") for n in ast.walk(ast.parse(f.read_text()))
            if isinstance(n, ast.ClassDef) and any(isinstance(b, ast.AnnAssign) and getattr(b.target, "id", None) == "scope" for b in n.body)}


def _routes():
    for f in sorted(API.glob("*.py")):
        for fn in ast.walk(ast.parse(f.read_text())):
            if isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)) and any(
                    isinstance(d, ast.Call) and isinstance(d.func, ast.Attribute) and d.func.attr in ("post", "get", "put", "api_route")
                    for d in fn.decorator_list):
                yield f.name, fn


def _assert_every_return_confirms(where: str, fn: ast.AST) -> None:
    returns = [n for n in _own_nodes(fn) if isinstance(n, ast.Return)]
    assert returns, where
    for r in returns:
        assert isinstance(r.value, ast.Call) and ast.unparse(r.value.func) == "echo_scope", f"{where}: {ast.unparse(r)}"
        assert ast.unparse(r.value.args[1]) in ("req.scope", "getattr(req, 'scope', None)"), f"{where}: {ast.unparse(r)}"


def test_every_route_that_takes_a_scope_confirms_it():
    models = _scoped_models()
    assert {"RetrieveRequest", "PlanRequest", "ChatRequest", "StreamChatRequest", "EvidenceRequest", "AskRequest", "CompareRequest"} <= models
    seen = set()
    for fname, fn in _routes():
        if not {ast.unparse(a.annotation) for a in fn.args.args if a.annotation is not None} & models:
            continue
        seen.add((fname, fn.name))
        if (fname, fn.name) in DELEGATES_TO_RUN_CHAT | STREAM_ROUTES:
            continue
        _assert_every_return_confirms(f"{fname}:{fn.name}", fn)
    assert seen >= DELEGATES_TO_RUN_CHAT | STREAM_ROUTES | {("retrieve.py", "retrieve"), ("corpus_plan.py", "retrieve_plan"),
                                                            ("evidence.py", "evidence"), ("ask.py", "ask"), ("compare_review.py", "compare")}
    run_chat = next(n for n in ast.walk(ast.parse((API / "ui.py").read_text())) if isinstance(n, ast.FunctionDef) and n.name == "run_chat")
    _assert_every_return_confirms("ui.py:run_chat", run_chat)
    chat_src = (API / "chat.py").read_text()
    assert "out = run_chat(" in chat_src and "return run_chat(" in chat_src                 # _chat_impl / _evidence_impl


def test_retrieve_confirms_the_scope_and_leaves_an_unscoped_reply_unchanged(monkeypatch):
    from orchestrator.api import retrieve as R

    async def impl(req):
        return {"evidence": [], "meta": {"mode": "GRAPH"}}
    monkeypatch.setattr(R, "_retrieve_impl", impl)
    monkeypatch.setattr(R, "record_query_receipt", lambda *a, **k: None)
    http_req = SimpleNamespace(headers={"user-agent": "test"})
    assert asyncio.run(R.retrieve(R.RetrieveRequest(query="q", corpus_id="c", scope=REF), http_req))[ECHO_KEY] == REF
    assert ECHO_KEY not in asyncio.run(R.retrieve(R.RetrieveRequest(query="q", corpus_id="c"), http_req))


def test_the_plan_lane_confirms_the_scope_it_passed_to_every_reformulation(monkeypatch):
    from orchestrator.api import corpus_plan as CP, retrieve as R
    seen = []

    async def impl(rreq):
        seen.append(rreq.scope)
        return {"evidence_rows": [{"id": f"c{len(seen)}", "kind": "chunk"}]}
    monkeypatch.setattr(R, "_retrieve_impl", impl)
    out = asyncio.run(CP.retrieve_plan(CP.PlanRequest(signal="running belts bounce on long runs", corpus_id="cinema", scope=REF)))
    assert out[ECHO_KEY] == REF and seen and all(s == REF for s in seen)
    assert ECHO_KEY not in asyncio.run(CP.retrieve_plan(CP.PlanRequest(signal="running belts bounce on long runs", corpus_id="cinema")))


def test_the_chat_runtime_reply_behind_chat_and_chat_evidence_confirms_the_scope(monkeypatch):
    from orchestrator.api import ui

    def frames(req, route="chat", receipt=None):
        answer = {"kind": "evidence", "result": {"evidence_packet": {"schema_version": "evidence-packet-v1"}, "synthesis_performed": False},
                  "retrieval": {"mode": "WILDCARD"}}
        yield "event: answer\ndata: " + json.dumps(answer) + "\n\n"
    monkeypatch.setattr(ui, "chat_events", frames)
    out = ui.run_chat(ui.StreamChatRequest(message="m", corpus_id="cinema", scope=REF), route="chat/evidence")
    assert out[ECHO_KEY] == REF and out["evidence_packet"]["schema_version"] == "evidence-packet-v1"
    assert ECHO_KEY not in ui.run_chat(ui.StreamChatRequest(message="m", corpus_id="cinema"), route="chat/evidence")


# ─────────────────────────────────────────────────────────── 3. Trail refuses, on the wire
EXAMPLE = json.loads((ROOT / "contracts/evidence/v1/evidence_packet.example.json").read_text())
REPLIES = {EB.EVIDENCE_PATH: {"evidence_packet": EXAMPLE, "synthesis_performed": False},
           "/retrieve": {"evidence_contract": "retrieve-evidence-rows-v1", "graph_facts": [1],
                         "evidence_rows": [{"id": "c_legacy", "kind": "chunk", "text": "legacy text", "corpus_id": "cinema"},
                                           {"id": "f_legacy", "kind": "graph_fact", "text": "a -> b"}]},
           "/retrieve/plan": {"plan": [{"id": "q1", "query": "q"}], "evidence_rows": [{"id": "c_plan", "kind": "chunk", "text": "t"}]}}


class _Orchestrator(http.server.BaseHTTPRequestHandler):
    """A stand-in orchestrator. Per path: `status` (default 200) and `confirm` — "none" (pre-K1: the scope is ignored),
    "exact" (K1b) or "widened" (confirms both roles)."""

    def do_POST(self):  # noqa: N802 — http.server's name
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        self.server.calls.append((self.path, body))
        status = self.server.status.get(self.path, 200)
        reply = copy.deepcopy(REPLIES[self.path]) if status == 200 else {"detail": "unavailable"}
        confirm = self.server.confirm.get(self.path, "none")
        if status == 200 and "scope" in body and confirm == "exact":
            reply[ECHO_KEY] = parse_scope(body["scope"]).as_dict()
        elif status == 200 and "scope" in body and confirm == "widened":
            reply[ECHO_KEY] = {"roles": ["implementation", "reference"]}
        data = json.dumps(reply).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args):  # quiet
        pass


@pytest.fixture()
def orch():
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Orchestrator)
    srv.calls, srv.status, srv.confirm = [], {}, {}
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield srv
    srv.shutdown()
    srv.server_close()


@pytest.fixture()
def worker(monkeypatch, orch):
    for var in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.delenv(EB.ENV_SURFACE, raising=False)
    spec = importlib.util.spec_from_file_location("adapter_step_worker_k1b", WORKER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert pathlib.Path(mod.__file__).resolve() == WORKER.resolve()
    mod.ORCH = f"http://127.0.0.1:{orch.server_address[1]}"
    return mod


MANIFEST = next(m for m in list_manifests(ADAPTER_DIR) if m.adapter_id == "ecommerce.product_research")


def _state() -> RunState:
    return RunState(run_id="adr_" + "b" * 32, adapter_id=MANIFEST.adapter_id, status="running",
                    input={"seed": "running belts bounce on long runs", "corpus_ids": ["cinema"]}, options={}, outputs={}, output_order=())


def _step(step_id: str) -> dict:
    return {"run_id": "adr_" + "b" * 32, "step_id": step_id, "sequence": 4, "context": {"hypotheses": []}}


@pytest.mark.parametrize("path,body", [(EB.EVIDENCE_PATH, EB.request_body("need", "cinema")),
                                       ("/retrieve", {"query": "q", "corpus_ids": ["cinema"], "scope": dict(EB.TRAIL_SCOPE)}),
                                       ("/retrieve/plan", {"signal": "s", "corpus_ids": ["cinema"], "scope": dict(EB.TRAIL_SCOPE)})])
def test_the_one_outbound_function_refuses_an_unconfirmed_answer(worker, orch, path, body):
    for confirm in ("none", "widened"):
        orch.confirm[path] = confirm
        with pytest.raises(worker.ScopeNotConfirmed, match="does not confirm the knowledge scope"):
            worker._orch_post(path, body)
    orch.confirm[path] = "exact"
    assert worker._orch_post(path, body)[ECHO_KEY] == REF
    assert issubclass(worker.ScopeNotConfirmed, worker.OrchRejected) and not issubclass(worker.ScopeNotConfirmed, worker.OrchUnavailable)


def test_an_unscoped_call_needs_no_confirmation(worker, orch):
    assert worker._orch_post("/retrieve", {"query": "q", "corpus_ids": ["cinema"]})["evidence_rows"]


def test_the_evidence_route_is_refused_and_the_legacy_lane_is_never_a_way_around_it(worker, orch):
    orch.confirm = {"/retrieve": "exact"}                                          # the evidence route answers pre-K1
    with pytest.raises(worker.ScopeNotConfirmed):
        worker.exec_retrieve(_step("B_retrieve"), _state(), MANIFEST)
    assert [p for p, _ in orch.calls] == [EB.EVIDENCE_PATH]


def test_the_unavailable_fallback_is_refused_too(worker, orch):
    orch.status = {EB.EVIDENCE_PATH: 503}                                        # evidence route down → legacy fallback, pre-K1
    with pytest.raises(worker.ScopeNotConfirmed):
        worker.exec_retrieve(_step("B_retrieve"), _state(), MANIFEST)
    assert [p for p, _ in orch.calls] == [EB.EVIDENCE_PATH, "/retrieve"]
    orch.calls.clear()
    orch.confirm = {"/retrieve": "exact"}                                        # a K1b legacy lane: the fallback is used, degraded
    out = worker.exec_retrieve(_step("B_retrieve"), _state(), MANIFEST)
    assert out["output"]["fallback"] == "retrieve" and [r["id"] for r in out["output"]["rows"]] == ["c_legacy", "f_legacy"]


def test_the_kill_switch_lane_is_refused(worker, orch, monkeypatch):
    monkeypatch.setenv(EB.ENV_SURFACE, "retrieve")
    with pytest.raises(worker.ScopeNotConfirmed):
        worker.exec_retrieve(_step("B_retrieve"), _state(), MANIFEST)
    orch.confirm = {"/retrieve": "exact"}
    assert [r["id"] for r in worker.exec_retrieve(_step("B_retrieve"), _state(), MANIFEST)["output"]["rows"]] == ["c_legacy", "f_legacy"]


def test_the_plan_lane_is_refused(worker, orch):
    with pytest.raises(worker.ScopeNotConfirmed):
        worker.exec_compile_plan(_step("B_retrieve"), _state(), MANIFEST)
    orch.confirm = {"/retrieve/plan": "exact"}
    assert [r["id"] for r in worker.exec_compile_plan(_step("B_retrieve"), _state(), MANIFEST)["output"]["rows"]] == ["c_plan"]


def test_the_graph_union_never_adds_unconfirmed_graph_rows(worker, orch):
    orch.confirm = {EB.EVIDENCE_PATH: "exact"}                                    # the packet is fine; the legacy graph lane is pre-K1
    with pytest.raises(worker.ScopeNotConfirmed):
        worker.exec_graph_expand(_step("B_graph"), _state(), MANIFEST)
    orch.confirm = {EB.EVIDENCE_PATH: "exact", "/retrieve": "exact"}
    out = worker.exec_graph_expand(_step("B_graph"), _state(), MANIFEST)
    assert [r["id"] for r in out["output"]["graph_rows"]] == ["f_legacy"] and "degraded" not in out["output"]


def test_a_k1b_orchestrator_serves_every_trail_path_unchanged(worker, orch):
    orch.confirm = {EB.EVIDENCE_PATH: "exact", "/retrieve": "exact", "/retrieve/plan": "exact"}
    out = worker.exec_retrieve(_step("B_retrieve"), _state(), MANIFEST)
    assert out["output"]["surface"] == "evidence_boundary" and out["output"]["retrieval_completed"] is True
    assert [r["id"] for r in out["output"]["rows"]] == ["chunk_0001", "chunk_0002"] and "degraded" not in out["output"]
    assert all(body.get("scope") == REF for _, body in orch.calls)
