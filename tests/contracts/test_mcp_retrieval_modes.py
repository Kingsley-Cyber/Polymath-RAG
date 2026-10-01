"""MCP-RETRIEVAL-MODES-V1 (the owner, 2026-10-01: "tools are stale and outdated. polymath has different types of retrieval").

Both MCP surfaces offer the app's own retrieval: the five public modes (one shared description), search = the app's evidence
route with planning off (before: /retrieve's frozen LEGACY lane path, because no mode was sent), explore = planning on,
answer = the full turn with a reasoning style and a model, compare = several modes side by side, deep research = the cited
report, models = what `model` may name. The legacy tools still answer old callers but are no longer listed.
In process: every orchestrator call is faked; no network, no database."""
from __future__ import annotations

import asyncio
import contextlib
import importlib
import importlib.util
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
for _sub in ("orchestrator", "shared"):
    sys.path.insert(0, str(ROOT / _sub))

import pytest
from polymath_shared import mcp_retrieval as MR
from starlette.testclient import TestClient

OWNER_KEY = "owner-modes-key-0123456789"
ACCEPT = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json", "Host": "127.0.0.1:8930",
          "Authorization": f"Bearer {OWNER_KEY}"}


@pytest.fixture()
def server_a(monkeypatch, tmp_path):
    registry = tmp_path / "principals.json"
    registry.write_text(json.dumps({"schema": "polymath_mcp_principals.v1", "principals": []}))
    registry.chmod(0o600)
    monkeypatch.setenv("POLYMATH_MCP_API_KEY", OWNER_KEY)
    monkeypatch.setenv("POLYMATH_MCP_PRINCIPALS_FILE", str(registry))
    from orchestrator import mcp_principals, mcp_server
    importlib.reload(mcp_principals)
    mod = importlib.reload(mcp_server)
    assert pathlib.Path(mod.__file__).is_relative_to(ROOT), mod.__file__
    calls: list[tuple] = []
    replies: dict = {}

    async def fake_orch(method, path, **kw):
        calls.append((method, path, kw.get("json"), kw.get("timeout")))
        return replies.get(path, {})

    async def fake_events(path, body, timeout=1800.0):
        calls.append(("STREAM", path, body, timeout))
        return replies.get(path, [])
    monkeypatch.setattr(mod, "_orch", fake_orch)
    monkeypatch.setattr(mod, "_orch_events", fake_events)
    return type("A", (), {"mod": mod, "calls": calls, "replies": replies})


@pytest.fixture()
def server_b(monkeypatch):
    spec = importlib.util.spec_from_file_location("modes_mcp_server_b", ROOT / "mcp_server" / "polymath_mcp.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    calls: list[tuple] = []
    replies: dict = {}

    def fake_post(path, payload, timeout=300):
        calls.append(("POST", path, payload))
        return replies.get(path, {})

    def fake_get(path, **params):
        calls.append(("GET", path, params))
        return replies.get(path, {})

    @contextlib.contextmanager
    def fake_stream(method, url, json=None, headers=None, timeout=None):
        calls.append(("STREAM", "/" + url.split("/", 3)[3], json))
        lines = replies.get("/research/deep", [])

        class R:
            status_code = 200

            def iter_lines(self):
                return iter(lines)
        yield R()
    monkeypatch.setattr(mod, "_post", fake_post)
    monkeypatch.setattr(mod, "_get", fake_get)
    monkeypatch.setattr(mod.httpx, "stream", fake_stream)
    return type("B", (), {"mod": mod, "calls": calls, "replies": replies})


# ---------------------------------------------------------------- the modes are the app's

def test_the_five_modes_are_exactly_the_apps_public_modes():
    ts = (ROOT / "frontend-v2" / "src" / "lib" / "contracts.ts").read_text()
    ui_modes = tuple(re.findall(r'"([A-Z]+)"', re.search(r"PUBLIC_MODES = \[([^\]]*)\]", ts).group(1)))
    from orchestrator.api.compare_review import COMPARABLE_MODES
    from polymath_shared.retrieval_modes import EXPOSED_MODES
    assert MR.RETRIEVAL_MODES == ui_modes == tuple(m for m in EXPOSED_MODES if m != "LEGACY") == tuple(COMPARABLE_MODES)
    assert set(MR.MODE_GUIDE) == set(MR.RETRIEVAL_MODES) and MR.DEFAULT_MODE == "HYBRID"


def test_the_reasoning_styles_and_depths_are_the_apps():
    from orchestrator.api.reasoning import CURATED_MODES
    from polymath_shared.deep_research.engine import PRESETS
    assert MR.REASONING_STYLES == tuple(CURATED_MODES)
    assert set(MR.DEPTHS) == set(PRESETS) and MR.DEFAULT_DEPTH in PRESETS
    for name, (breadth, depth) in PRESETS.items():
        assert MR.DEPTHS[name].startswith(f"{breadth} goals x {depth} round"), (name, MR.DEPTHS[name])


def test_a_mode_is_normalised_or_refused():
    assert [MR.normalize_mode(m) for m in ("graph", " Wildcard ", "VECTOR", "gnn", None, "")] == ["GRAPH", "WILDCARD", "FAST", "GNN", "HYBRID", "HYBRID"]
    assert MR.normalize_mode("LEGACY") is None and MR.normalize_mode("EXPLORE") is None
    err = MR.mode_error("LEGACY")
    assert err["status"] == 422 and set(err["modes"]) == set(MR.RETRIEVAL_MODES)


# ---------------------------------------------------------------- Server A

def _rows_reply(mode: str) -> dict:
    return {"meta": {"mode": mode}, "evidence_contract": "retrieve-evidence-rows-v1", "latency_ms": 812.0,
            "evidence_rows": [{"id": "c1", "kind": "chunk", "text": "x" * 1300, "utility_role": "DIRECT"},
                              {"id": "fact:f1", "kind": "graph_fact", "text": "A —causes→ B"},
                              {"id": "c2", "kind": "chunk", "text": "short"}],
            "retrieval": {"mode": mode, "wildcard": [{"chunk_id": "w1", "doc_id": "d9", "text": "y" * 900, "insight": "a lateral link",
                                                      "sources": [{"chunk_id": "s1", "doc_id": "d9", "junk": 1}]}],
                          "degraded": ["wildcard_timeout"]},
            "phases": [{"stage": "retrieve"}], "evidence_packet": {"evidence": []}}


def test_search_runs_the_apps_evidence_route_for_every_mode(server_a):
    for mode in MR.RETRIEVAL_MODES:
        server_a.replies["/chat/evidence"] = _rows_reply(mode)
        out = asyncio.run(server_a.mod.polymath_search("what does RAPO say", "cinema", mode=mode.lower(), max_evidence=1))
        method, path, body, _ = server_a.calls[-1]
        assert (method, path) == ("POST", "/chat/evidence")
        assert body == {"message": "what does RAPO say", "corpus_id": "cinema", "mode": mode, "compiler": "off",
                        "corpus_explorer": False, "evidence": True}                        # planning OFF, rows ON
        assert out["mode"] == mode and [r["id"] for r in out["evidence_rows"]] == ["c1", "fact:f1"]   # max 1 chunk, then facts
        assert out["evidence_rows"][0]["truncated"] is True and out["evidence_rows"][0]["full_length"] == 1300
        assert out["graph_facts"] == 1 and out["evidence_contract"] == "retrieve-evidence-rows-v1"
        assert out["wildcard"][0]["insight"] == "a lateral link" and out["wildcard"][0]["truncated"] is True
        assert out["wildcard"][0]["sources"] == [{"chunk_id": "s1", "doc_id": "d9"}] and out["degraded"] == ["wildcard_timeout"]
        assert "phases" not in out and "retrieval" not in out
    assert not [c for c in server_a.calls if c[1] == "/retrieve"]                          # never the LEGACY route again


def test_an_unknown_mode_is_refused_before_any_call(server_a):
    for tool, args in ((server_a.mod.polymath_search, ("q", "cinema")), (server_a.mod.polymath_explore, ("q", "cinema")),
                       (server_a.mod.polymath_answer, ("q", "cinema")), (server_a.mod.polymath_deep_research, ("q", "cinema"))):
        out = asyncio.run(tool(*args, mode="LEGACY"))
        assert out["status"] == 422 and "LEGACY" in out["error"], tool.__name__
    assert asyncio.run(server_a.mod.polymath_compare("q", "cinema", modes=["HYBRID", "EXPLORE"]))["status"] == 422
    assert asyncio.run(server_a.mod.polymath_answer("q", "cinema", reasoning="telepathy"))["status"] == 422
    assert asyncio.run(server_a.mod.polymath_deep_research("q", "cinema", depth="forever"))["status"] == 422
    assert server_a.calls == []


def test_explore_keeps_the_packet_and_drops_the_diagnostics(server_a):
    server_a.replies["/chat/evidence"] = {**_rows_reply("GRAPH"), "evidence_packet": {"schema_version": "evidence-packet-v1", "evidence": [{"chunk_id": "c1"}]},
                                          "graph_facts": [{"fact_id": "f1", "predicate": "causes"}], "synthesis_performed": False}
    out = asyncio.run(server_a.mod.polymath_explore("q", "cinema", corpus_explorer=False, mode="GRAPH"))
    assert server_a.calls[-1][2] == {"message": "q", "corpus_id": "cinema", "mode": "GRAPH", "corpus_explorer": False}
    assert out["evidence_packet"]["schema_version"] == "evidence-packet-v1" and out["graph_facts"] == [{"fact_id": "f1", "predicate": "causes"}]
    assert out["mode"] == "GRAPH" and out["synthesis_performed"] is False and not {"retrieval", "phases", "evidence_rows"} & set(out)


def test_answer_compare_and_models_send_what_the_app_sends(server_a):
    server_a.replies["/chat"] = {"answer": "RAPO shapes prompts [S1].", "evidence": [{"text": "z" * 900, "chunk_id": "c1"}] * 20}
    out = asyncio.run(server_a.mod.polymath_answer("q", "cinema", mode="WILDCARD", reasoning="Analytical", model="litellm:x"))
    assert server_a.calls[-1][1:3] == ("/chat", {"message": "q", "corpus_id": "cinema", "mode": "WILDCARD", "reasoning": "analytical",
                                                 "synthesizer": "litellm:x"})
    assert len(out["evidence"]) == 12 and len(out["evidence"][0]["text"]) == 600
    asyncio.run(server_a.mod.polymath_answer("q", "cinema"))
    assert server_a.calls[-1][2] == {"message": "q", "corpus_id": "cinema", "mode": "HYBRID"}       # defaults add nothing

    server_a.replies["/compare"] = {"contract": "compare-retrieval-v1", "corpus_id": "cinema", "question": "q", "arms": [
        {"mode": "FAST", "ok": True, "latency_ms": 900, "retrieval": {"evidence_count": 3, "documents": ["d1"],
                                                                      "rows": [{"chunk_id": "a"}, {"chunk_id": "b"}, {"chunk_id": "c"}]}},
        {"mode": "GRAPH", "ok": True, "latency_ms": 2100, "retrieval": {"evidence_count": 2, "documents": ["d1", "d2"],
                                                                        "rows": [{"chunk_id": "b"}, {"chunk_id": "z"}], "degraded": ["graph_degraded"]}},
        {"mode": "GNN", "ok": False, "latency_ms": 40, "error": "RuntimeError: no gnn collection"}]}
    out = asyncio.run(server_a.mod.polymath_compare("q", "cinema", modes=["fast", "graph", "GRAPH", "gnn"]))
    _, path, body, timeout = server_a.calls[-1]
    assert (path, body["modes"], timeout) == ("/compare", ["FAST", "GRAPH", "GNN"], 600)          # normalised, de-duplicated
    assert out["found_by_every_mode"] == ["b"] and out["only_this_mode"] == {"FAST": 2, "GRAPH": 1}
    assert out["arms"][1]["degraded"] == ["graph_degraded"] and out["arms"][2] == {"mode": "GNN", "ok": False, "latency_ms": 40,
                                                                                   "error": "RuntimeError: no gnn collection"}
    asyncio.run(server_a.mod.polymath_compare("q", "cinema"))
    assert server_a.calls[-1][2]["modes"] == list(MR.RETRIEVAL_MODES)

    server_a.replies["/synthesizers"] = {"synthesizers": [{"id": "litellm:a", "label": "A", "kind": "litellm"},
                                                          {"id": "litellm:b", "label": "B", "offered": False}, {"id": "ollama:c", "label": "C"}]}
    assert asyncio.run(server_a.mod.polymath_models()) == {"default": "litellm:a", "models": [{"id": "litellm:a", "label": "A"},
                                                                                             {"id": "ollama:c", "label": "C"}]}


_DEEP_ANSWER = {"kind": "deep", "latency_ms": 95000, "retrieval": None, "result": {
    "text": "RAPO reshapes prompts [c1]. Reward models matter [c2].", "model": "litellm:a", "unknown_citations": [],
    "citations": [{"cid": "c1", "id": "ch1", "kind": "chunk", "doc_id": "d1", "title": "Book", "source": "Book · ch 1", "text": "w" * 700}],
    "meta": {"verdict": "supported", "deep_research": {"stop_reason": "coverage_complete", "report_model": {
        "goals": [{"findings": [{"confidence": "strong"}, {"confidence": "contested"}]}], "counter": [], "open_questions": ["why"],
        "sources": [1, 2]}}}}}


def test_deep_research_returns_the_cited_report_or_a_typed_error(server_a):
    server_a.replies["/research/deep"] = [("phase", {"stage": "deep_start", "label": "Deep research over cinema"}),
                                          ("coverage", {"goals": 3, "documents": 4, "passages": 20}),
                                          ("token", {"token": "RAPO"}), ("answer", _DEEP_ANSWER)]
    out = asyncio.run(server_a.mod.polymath_deep_research("q", "cinema"))
    assert server_a.calls[-1][:3] == ("STREAM", "/research/deep", {"question": "q", "corpus_id": "cinema", "preset": "quick", "mode": "HYBRID"})
    assert out["report"].startswith("RAPO reshapes") and out["verdict"] == "supported" and out["stop_reason"] == "coverage_complete"
    assert out["counts"] == {"goals": 1, "findings": 2, "sources": 2, "open_questions": 1, "confidence": {"strong": 1, "single_source": 0, "contested": 1}}
    assert out["citations"][0]["truncated"] is True and len(out["citations"][0]["text"]) == MR.REPORT_CITATION_TEXT
    assert out["coverage"] == {"goals": 3, "documents": 4, "passages": 20} and (out["depth"], out["mode"]) == ("quick", "HYBRID")
    asyncio.run(server_a.mod.polymath_deep_research("q", "cinema", depth="Thorough", mode="graph", model="litellm:b"))
    assert server_a.calls[-1][2] == {"question": "q", "corpus_id": "cinema", "preset": "thorough", "mode": "GRAPH", "synthesizer": "litellm:b"}
    server_a.replies["/research/deep"] = [("error", {"error_code": "DEEP_RESEARCH_BUSY", "message": "one deep research run at a time"})]
    busy = asyncio.run(server_a.mod.polymath_deep_research("q", "cinema"))
    assert busy["status"] == 409 and busy["error_code"] == "DEEP_RESEARCH_BUSY"
    server_a.replies["/research/deep"] = [("phase", {"label": "Planning"})]
    assert asyncio.run(server_a.mod.polymath_deep_research("q", "cinema"))["status"] == 502


def test_fast_comes_back_as_fast_not_the_runtimes_internal_vector(server_a):
    """Seen live 2026-10-01: the runtime stamps an executed FAST turn `VECTOR`; the tools report the public name."""
    server_a.replies["/chat/evidence"] = _rows_reply("VECTOR")
    assert asyncio.run(server_a.mod.polymath_search("q", "cinema", mode="FAST"))["mode"] == "FAST"
    assert asyncio.run(server_a.mod.polymath_explore("q", "cinema", mode="FAST"))["mode"] == "FAST"


def test_the_event_stream_parser_skips_keep_alives_and_broken_frames():
    raw = ["event: phase\n", 'data: {"label": "a"}\n', "\n", ": keep-alive\n", "\n", "event: token\n", "data: {not json\n", "\n",
           "event: answer\n", 'data: {"kind": "deep"}\n']
    assert list(MR.parse_sse(raw)) == [("phase", {"label": "a"}), ("answer", {"kind": "deep"})]


# ---------------------------------------------------------------- what an agent is offered

def _rpc(r) -> dict:
    """The JSON-RPC message of a streamable-http reply (plain JSON or one SSE data line)."""
    text = r.text.strip()
    if text.startswith("{"):
        return json.loads(text)
    return json.loads([ln[5:].strip() for ln in text.splitlines() if ln.startswith("data:")][-1])


def test_the_old_tools_answer_old_callers_but_are_never_listed(server_a):
    listed = {t.name for t in asyncio.run(server_a.mod.mcp.list_tools())}
    registered = {t.name for t in server_a.mod.mcp._tool_manager.list_tools()}
    assert MR.HIDDEN_TOOLS_A <= registered and not MR.HIDDEN_TOOLS_A & listed
    assert {"polymath_search", "polymath_explore", "polymath_answer", "polymath_compare", "polymath_deep_research", "polymath_models"} <= listed
    server_a.replies["/retrieve"] = {"evidence": []}
    with TestClient(server_a.mod.build_app(), raise_server_exceptions=False) as c:
        r = c.post("/mcp", headers=ACCEPT, json={"jsonrpc": "2.0", "id": 7, "method": "tools/call",
                                                 "params": {"name": "retrieve", "arguments": {"query": "q", "corpus_id": "cinema"}}})
        listed_http = {t["name"] for t in _rpc(c.post("/mcp", headers=ACCEPT, json={"jsonrpc": "2.0", "id": 8, "method": "tools/list"}))["result"]["tools"]}
    assert r.status_code == 200 and _rpc(r)["result"]["isError"] is False and server_a.calls[-1][1] == "/retrieve"
    assert listed_http == listed


def test_every_retrieval_tool_and_both_servers_describe_the_five_modes(server_a, server_b):
    for server in (server_a.mod.mcp, server_b.mod.server):
        tools = {t.name: t for t in asyncio.run(server.list_tools())}
        for name in ("polymath_search", "polymath_explore", "polymath_answer", "polymath_compare"):
            desc = tools[name].description or ""
            assert all(m in desc for m in MR.RETRIEVAL_MODES), (name, desc[:120])
        assert all(s in tools["polymath_answer"].description for s in ("step_by_step", "debate", "concise"))
        assert all(d in tools["polymath_deep_research"].description for d in MR.DEPTHS)
        assert not MR.HIDDEN_TOOLS_B & set(tools) and not MR.HIDDEN_TOOLS_A & set(tools)
        assert all(f"{m}:" in server.instructions for m in MR.RETRIEVAL_MODES)
    assert "cheap baseline" not in server_a.mod.mcp.instructions                          # the stale three-mode line is gone


# ---------------------------------------------------------------- Server B sends the same requests

def test_server_b_sends_the_same_requests_and_shapes_the_same_answers(server_b):
    b = server_b
    b.replies["/chat/evidence"] = _rows_reply("GNN")
    out = b.mod.polymath_search("q", "cinema", mode="GNN", max_evidence=5)
    assert b.calls[-1] == ("POST", "/chat/evidence", MR.search_body("q", "cinema", "GNN"))
    assert out["mode"] == "GNN" and [r["id"] for r in out["evidence_rows"]] == ["c1", "c2", "fact:f1"]
    b.mod.polymath_explore("q", "cinema", mode="vector")
    assert b.calls[-1] == ("POST", "/chat/evidence", MR.explore_body("q", "cinema", "FAST", True))
    b.mod.polymath_answer("q", "cinema", mode="GRAPH", reasoning="debate")
    assert b.calls[-1] == ("POST", "/chat", MR.answer_body("q", "cinema", "GRAPH", reasoning="debate"))
    b.mod.polymath_answer("q", "cinema", mode="ASK")
    assert b.calls[-1] == ("POST", "/ask", {"question": "q", "corpus_id": "cinema"})               # Server B's stored-knowledge answer stays
    b.mod.polymath_compare("q", "cinema", modes=["wildcard"])
    assert b.calls[-1] == ("POST", "/compare", MR.compare_body("q", "cinema", ["WILDCARD"]))
    b.replies["/synthesizers"] = {"synthesizers": [{"id": "litellm:a", "label": "A"}]}
    assert b.mod.polymath_models()["default"] == "litellm:a"
    frames = ["event: answer\n", "data: " + json.dumps(_DEEP_ANSWER) + "\n", "\n"]
    b.replies["/research/deep"] = [ln.rstrip("\n") for ln in frames]
    out = b.mod.polymath_deep_research("q", "cinema", depth="standard")
    assert b.calls[-1] == ("STREAM", "/research/deep", MR.deep_body("q", "cinema", "standard", "HYBRID"))
    assert out["report"].startswith("RAPO reshapes") and out["depth"] == "standard"
    assert b.mod.polymath_search("q", "cinema", mode="LEGACY")["status"] == 422
