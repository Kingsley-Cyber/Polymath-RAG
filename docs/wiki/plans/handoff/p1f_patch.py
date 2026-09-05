"""P1.f — ChatRuntime: /chat runs the same event generator as /chat/stream (modulo transport); MCP `ask` inherits.
Apply after the P1.e patches."""
import pathlib, re
ROOT = pathlib.Path("/Users/king/Documents/polymath-rebuild/polymath-v4")

# ------------------------------------------------------------------ ui.py: extract chat_events
p = ROOT / "orchestrator/orchestrator/api/ui.py"; s = p.read_text(encoding="utf-8")
old = '''@router.post("/chat/stream")
async def chat_stream(req: StreamChatRequest) -> StreamingResponse:
    query = (req.message or "").strip()'''
new = '''def chat_events(req: StreamChatRequest):
    """CHAT-RUNTIME-V1 (plan §4 P1.f): the ONE chat runtime — compiler, budgets,
    lanes, composer, carry, synthesis — as a generator of SSE frames.
    `/chat/stream` streams it; `/chat` (and therefore MCP `ask`) consumes it
    and returns the final `answer` frame. Same request ⇒ same plan, same
    evidence ids on every route; only the transport differs."""
    query = (req.message or "").strip()'''
assert s.count(old) == 1; s = s.replace(old, new)
old = '''    return StreamingResponse(generate(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache",
                                      "X-Accel-Buffering": "no"})'''
new = '''    return generate()


@router.post("/chat/stream")
async def chat_stream(req: StreamChatRequest) -> StreamingResponse:
    return StreamingResponse(chat_events(req), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache",
                                      "X-Accel-Buffering": "no"})


def run_chat(req: StreamChatRequest) -> dict:
    """Consume the runtime's frames and return the answer as one JSON object
    (the /chat shape): the answer event's `result` merged with `retrieval`,
    the phases, and the runtime tag. Errors raise HTTPException(status,
    detail) exactly as the stream would have emitted them."""
    phases: list[dict] = []
    answer: dict | None = None
    cur = None
    for frame in chat_events(req):
        for line in str(frame).split("\\n"):
            if line.startswith("event:"):
                cur = line[6:].strip()
            elif line.startswith("data:"):
                try:
                    data = json.loads(line[5:].strip())
                except Exception:  # noqa: BLE001
                    continue
                if cur == "phase":
                    phases.append(data)
                elif cur == "answer":
                    answer = data
                elif cur == "error":
                    raise HTTPException(status_code=int(data.get("status") or 502),
                                        detail={k: v for k, v in data.items() if k != "status"} or {"message": "chat runtime error"})
    if answer is None:
        raise HTTPException(status_code=502, detail={"error_code": "no_answer", "message": "the chat runtime produced no answer frame"})
    result = dict(answer.get("result") or {})
    result.setdefault("meta", {})
    result["retrieval"] = answer.get("retrieval") or {}
    result["kind"] = answer.get("kind")
    result["latency_ms"] = answer.get("latency_ms")
    result["phases"] = phases
    result["runtime"] = "chat-runtime-v1"
    return result'''
assert s.count(old) == 1; s = s.replace(old, new)
# receipt control: /chat records its own receipt (kind "chat"); the runtime skips when asked
old = '''    # P1.d/P1.e: lane composition override (evaluation and A/B): e.g. ["HIERARCHICAL_ROUTE","GLOBAL_DENSE_CHILD"] = VECTOR
    lanes: Optional[list[str]] = None
'''
new = old + '''    # P1.f: the /chat wrapper writes the `chat` receipt itself; the runtime then skips its `chat_stream` receipt
    receipt: bool = True
'''
assert s.count(old) == 1; s = s.replace(old, new)
old = '''    """QUERY-RECEIPTS on the streaming path (plan §3.6). Best effort, never
    on the critical path; the UI's turns were previously invisible."""
    try:'''
new = '''    """QUERY-RECEIPTS on the streaming path (plan §3.6). Best effort, never
    on the critical path; the UI's turns were previously invisible."""
    if getattr(req, "receipt", True) is False:
        return
    try:'''
assert s.count(old) == 1; s = s.replace(old, new)
p.write_text(s, encoding="utf-8")
import ast; ast.parse(s); print("ui.py: chat_events + run_chat")

# ------------------------------------------------------------------ chat.py: non-LEGACY modes go through the runtime
p = ROOT / "orchestrator/orchestrator/api/chat.py"; s = p.read_text(encoding="utf-8")
old = '''    mode = resolve_chat_mode(req.mode)
    if mode == MODE_GRAPH:'''
new = '''    mode = resolve_chat_mode(req.mode)
    # CHAT-RUNTIME-V1 (P1.f): every non-LEGACY mode runs the same runtime as /chat/stream
    # (compiler → v2 lanes → composer → carry → synthesis); LEGACY keeps its historical path.
    if mode in ("FAST", "VECTOR", "HYBRID", "GRAPH", "WILDCARD") and not getattr(req, "legacy_runtime", False):
        from orchestrator.api.ui import StreamChatRequest, run_chat
        corpus_ids = list(scope.corpus_ids)
        sreq = StreamChatRequest(
            message=query, corpus_id=(corpus_ids[0] if len(corpus_ids) == 1 else None), corpus_ids=(corpus_ids if len(corpus_ids) != 1 else None),
            workspace=getattr(req, "workspace", None), all_authorized=bool(getattr(req, "all_authorized", False)),
            mode=("FAST" if mode == "VECTOR" else mode), latent=getattr(req, "latent", None),
            synthesizer=(getattr(req, "synthesizer", None) or "deterministic-template-v3"),
            history=[], carry_context=[], compiler=getattr(req, "compiler", None), retrieval=getattr(req, "retrieval", None),
            lanes=getattr(req, "lanes", None), receipt=False)
        out = run_chat(sreq)
        out["meta"]["mode"] = mode
        return out
    if mode == MODE_GRAPH:'''
assert s.count(old) == 1; s = s.replace(old, new)
old = "    # CHAT-RETRIEVAL-V2 P1.a: per-request override (v1 | v2) for evaluation and A/B.\n    retrieval: str | None = None\n"
new = old + "    # P1.f: evaluation hooks mirrored from the stream request; `legacy_runtime` keeps the pre-runtime /chat path\n    synthesizer: str | None = None\n    compiler: str | None = None\n    lanes: list[str] | None = None\n    legacy_runtime: bool = False\n"
assert s.count(old) == 1; s = s.replace(old, new)
p.write_text(s, encoding="utf-8"); ast.parse(s); print("chat.py: runtime path")

# ------------------------------------------------------------------ tests
p = ROOT / "tests/determinism/test_chat_hygiene.py"; t = p.read_text(encoding="utf-8")
old = '''    assert impl.count('["mode"] = mode') == 3, "every _chat_impl return stamps the executed mode"'''
new = '''    assert impl.count('["mode"] = mode') >= 3, "every _chat_impl return stamps the executed mode (runtime path included)"'''
assert t.count(old) == 1; t = t.replace(old, new); p.write_text(t, encoding="utf-8")
p = ROOT / "tests/determinism/test_chat_runtime.py"
p.write_text('''"""CHAT-RUNTIME-V1 (plan §4 P1.f): /chat == /chat/stream == MCP modulo transport.
Offline: run_chat parses the runtime frames into the /chat shape and surfaces
runtime errors as HTTP errors. Live: the same request on both routes yields the
same compiled plan and the same evidence ids (compiler off ⇒ deterministic plan)."""
from __future__ import annotations

import json
import pathlib
import sys
import urllib.request

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
for sub in ("shared", "orchestrator"):
    p = str(ROOT / sub)
    if p not in sys.path:
        sys.path.insert(0, p)

from fastapi import HTTPException  # noqa: E402
from orchestrator.api import ui  # noqa: E402


def _frames(events):
    for ev, data in events:
        yield f"event: {ev}\\ndata: {json.dumps(data)}\\n\\n"


def test_run_chat_returns_the_answer_frame_in_the_chat_shape(monkeypatch):
    events = [("phase", {"stage": "compile"}), ("phase", {"stage": "retrieve_done", "evidence_count": 2}),
              ("answer", {"kind": "chat", "result": {"answer": "A [S1].", "citations": [{"citation_id": 1, "locators": ["chunk:c1"]}], "meta": {"verdict": "grounded"}},
                          "retrieval": {"mode": "HYBRID", "engine": "chat-retrieval-v2", "used_evidence": ["c1"], "chat_plan": {"queries": [{"id": "q0"}]}}, "latency_ms": 12.5}),
              ("done", {})]
    monkeypatch.setattr(ui, "chat_events", lambda req: _frames(events))
    out = ui.run_chat(ui.StreamChatRequest(message="q", corpus_id="cinema", mode="HYBRID", receipt=False))
    assert out["answer"] == "A [S1]." and out["citations"][0]["locators"] == ["chunk:c1"]
    assert out["retrieval"]["used_evidence"] == ["c1"] and out["retrieval"]["chat_plan"]["queries"][0]["id"] == "q0"
    assert [p["stage"] for p in out["phases"]] == ["compile", "retrieve_done"] and out["runtime"] == "chat-runtime-v1" and out["kind"] == "chat"
    assert out["meta"]["verdict"] == "grounded" and out["latency_ms"] == 12.5


def test_run_chat_surfaces_runtime_errors_as_http_errors(monkeypatch):
    monkeypatch.setattr(ui, "chat_events", lambda req: _frames([("phase", {"stage": "compile"}), ("error", {"status": 422, "error_code": "corpus_required", "message": "x"})]))
    with pytest.raises(HTTPException) as ei:
        ui.run_chat(ui.StreamChatRequest(message="q", mode="HYBRID", receipt=False))
    assert ei.value.status_code == 422 and ei.value.detail["error_code"] == "corpus_required"
    monkeypatch.setattr(ui, "chat_events", lambda req: _frames([("done", {})]))
    with pytest.raises(HTTPException) as ei2:
        ui.run_chat(ui.StreamChatRequest(message="q", mode="HYBRID", receipt=False))
    assert ei2.value.status_code == 502 and ei2.value.detail["error_code"] == "no_answer"


def test_receipt_flag_silences_the_runtime_receipt(monkeypatch):
    calls = []
    import polymath_shared.query_receipts as qr
    monkeypatch.setattr(qr, "record_query_receipt", lambda *a, **k: calls.append(1))
    ui._record_stream_receipt(ui.StreamChatRequest(message="q", receipt=False), question="q", scope=None, wall_ms=1.0, ui_mode="HYBRID", answer="a", meta={})
    assert calls == []


def _post(path: str, body: dict):
    req = urllib.request.Request(f"http://127.0.0.1:7200{path}", data=json.dumps(body).encode(), headers={"content-type": "application/json", "accept": "text/event-stream"})
    with urllib.request.urlopen(req, timeout=420) as r:
        raw = r.read().decode("utf-8", "replace")
    if path == "/chat":
        return json.loads(raw)
    answer, cur = {}, None
    for line in raw.split("\\n"):
        if line.startswith("event:"):
            cur = line[6:].strip()
        elif line.startswith("data:") and cur == "answer":
            answer = json.loads(line[5:].strip())
    return answer


def test_live_chat_and_stream_agree_on_plan_and_evidence_ids():
    try:
        urllib.request.urlopen("http://127.0.0.1:7200/ready", timeout=3)
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"orchestrator not reachable: {exc}")
    body = {"message": "What does the book say about making your own chroma keyer?", "corpus_id": "cinema", "mode": "HYBRID",
            "compiler": "off", "synthesizer": "deterministic-template-v3"}
    a = _post("/chat", body)
    b = _post("/chat/stream", body)
    ra, rb = a.get("retrieval") or {}, b.get("retrieval") or {}
    assert a.get("runtime") == "chat-runtime-v1" and ra.get("engine") == rb.get("engine") == "chat-retrieval-v2"
    assert (ra.get("chat_plan") or {}).get("queries") == (rb.get("chat_plan") or {}).get("queries")
    assert [e.get("chunk_id") for e in ra.get("legend") or []] == [e.get("chunk_id") for e in rb.get("legend") or []]
    assert ra.get("used_evidence") == rb.get("used_evidence") and a["meta"]["mode"] == "HYBRID"
''', encoding="utf-8")
# scaffold + README
p = ROOT / "scripts/scaffold_polymath_v4.py"; s = p.read_text(encoding="utf-8")
anchor = '    ("docs/wiki/experiments/chat-baseline-p1d-B-hybrid.md", "md", None),\n'; assert s.count(anchor) == 1
add = ''.join(f'    ("{f}", "{f.rsplit(".",1)[1]}", None),\n' for f in [
    "tests/determinism/test_chat_runtime.py", "docs/wiki/work-log/2026-09-05-p1f-chat-runtime.md"])
p.write_text(s.replace(anchor, anchor + add), encoding="utf-8")
print("P1.f patch applied")
