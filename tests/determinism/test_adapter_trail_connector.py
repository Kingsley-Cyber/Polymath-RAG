"""E4 — the reference adapter's Trail steps end to end against a STUB Trail daemon (httpx MockTransport speaking Trail's
JSON-RPC envelopes and lifecycle: PENDING → TERMINAL on the second poll, outputs, paging, CANCEL). Real Postgres substrate,
real worker executors, real transitions; only Polymath knowledge steps are faked. Proves: submit-once/poll-by-id, the
composite acquire+extract, lineage with Trail operation/record ids, typed gap at the first PLANNED Trail capability, and
best-effort cancel propagation. The live counterpart needs Trail's stack + a `polymath` principal (owner actions O1/O4)."""
from __future__ import annotations

import json
import os
import pathlib
import sys

import httpx
import psycopg
import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
for p in (ROOT / "shared", ROOT / "workers"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
from polymath_shared.adapter import service, store  # noqa: E402
from polymath_shared.adapter import trail_client as TC  # noqa: E402
from polymath_shared.adapter.contracts import validate  # noqa: E402
import workers.adapter_step_worker as W  # noqa: E402

DSN = os.environ.get("POLYMATH_PG_DSN", "postgresql://polymath:polymath-dev@127.0.0.1:5432/polymath")


class StubTrail:
    """In-memory Trail: every submit creates an operation that is RUNNING on its first poll and TERMINAL on the next."""
    def __init__(self):
        self.ops: dict[str, dict] = {}; self.calls: list[tuple[str, dict]] = []; self.n = 0

    def _op(self, kind, outputs):
        self.n += 1
        oid = f"op-{kind.split('.')[0]}-{self.n}"
        self.ops[oid] = {"kind": kind, "polls": 0, "outputs": outputs, "revision": 1, "phase": "PENDING", "outcome": None}
        return {"operation_id": oid, "operation_kind": kind, "temporal_workflow_id": oid, "temporal_run_id": None,
                "submitted_at": "2026-09-13T20:00:00Z", "status_revision": 0}

    def status(self, oid):
        op = self.ops[oid]; op["polls"] += 1
        if op["polls"] >= 2 and op["phase"] != "TERMINAL":
            op["phase"], op["outcome"], op["revision"] = "TERMINAL", "SUCCEEDED", op["revision"] + 1
        elif op["phase"] == "PENDING":
            op["phase"] = "RUNNING"
        return {"operation_id": oid, "execution_authority": "TEMPORAL", "phase": op["phase"], "terminal_outcome": op["outcome"], "waiting_reason": None,
                "output_refs": [{"output_kind": k, "output_id": i, "generation": None} for k, i in op["outputs"]] if op["phase"] == "TERMINAL" else [],
                "issue_refs": [], "revision": op["revision"], "updated_at": "2026-09-13T20:00:01Z",
                "terminal_at": "2026-09-13T20:00:02Z" if op["phase"] == "TERMINAL" else None, "failure_code": None}

    def handle(self, req: httpx.Request) -> httpx.Response:
        body = json.loads(req.content); name = body["params"]["name"]; args = body["params"]["arguments"]
        self.calls.append((name, args))
        assert req.headers["authorization"].startswith("Bearer ") and "mcp-session-id" not in req.headers
        def ok(value):
            return httpx.Response(200, json={"jsonrpc": "2.0", "id": body["id"], "result": {"content": [{"type": "text", "text": json.dumps(value)}], "structuredContent": value, "isError": False}})
        if name == "discover.submit":
            r = args["request"]; assert r["time_range"] is None and r["categories"] == ["general"]
            return ok(self._op("discover.submit", [("URL_CANDIDATE_RESULT", "disc-res-1")]))
        if name == "scrape.submit":
            items = args["request"]["items"]; assert [i["ordinal"] for i in items] == list(range(len(items)))
            return ok(self._op("scrape.submit", [("RAW_ARTIFACT", f"art-{i}") for i in range(min(2, len(items)))]))
        if name == "extract.submit":
            art = args["request"]["artifact_id"]; assert args["request"]["parser_profile_ref"] == TC.PARSER_PROFILE_REF
            return ok(self._op("extract.submit", [("DOCUMENT_RESULT", f"docres-{art}")]))
        if name == "operation.get":
            return ok(self.status(args["reference"]["operation_id"]))
        if name == "operation.command":
            cmd = args["command"]; op = self.ops[cmd["operation_id"]]
            assert cmd["command"] == "CANCEL" and cmd["expected_revision"] == op["revision"]
            op.update(phase="TERMINAL", outcome="CANCELLED", revision=op["revision"] + 1)
            return ok(self.status(cmd["operation_id"]) | {"terminal_outcome": "CANCELLED"})
        if name == "result.page":
            r = args["request"]
            if r["target_kind"] == "URL_CANDIDATE_RESULT":
                items = [{"candidate_id": f"cand-{i}", "rank": i, "url": f"https://lead.example/{i}", "title": f"lead {i}", "snippet": "…", "record_class": "OPERATIONAL_LEAD", "evidence_eligible": False} for i in (1, 2, 3)]
                return ok({"output_kind": "URL_CANDIDATE_RESULT", "result_page": None, "url_candidate_page": {"items": items, "returned_count": 3, "has_more": False, "next_cursor": None}})
            recs = [{"record_id": f"{r['target_id']}-rec-{i}", "ordinal": i, "record_kind": "PARAGRAPH", "text": f"record {i} of {r['target_id']}"} for i in range(2)]
            return ok({"output_kind": "DOCUMENT_RESULT", "url_candidate_page": None, "result_page": {"response_kind": "DOCUMENT_RESULT", "dataset_page": None,
                       "document_page": {"records": recs, "page": {"returned_count": 2, "has_more": False, "next_cursor": None}}}})
        return httpx.Response(200, json={"jsonrpc": "2.0", "id": body["id"], "result": {"content": [{"type": "text", "text": f"unknown tool {name}"}], "isError": True}})


FAKE_ROWS = [{"kind": "chunk", "id": "chunk_k1", "doc_id": "doc_k", "corpus_id": "probe", "score": 0.9}]
def _fake_knowledge(step, state, m):
    return {"output": {"rows": FAKE_ROWS}, "evidence_refs": [{"kind": "chunk", "id": "chunk_k1", "doc_id": "doc_k", "corpus_id": "probe"}]}


@pytest.fixture()
def rig(monkeypatch):
    try:
        c = psycopg.connect(DSN, autocommit=False, connect_timeout=3)
    except Exception as exc:  # pragma: no cover
        pytest.skip(f"postgres unavailable: {exc}")
    if c.execute("SELECT to_regclass('public.adapter_runs')").fetchone()[0] is None:
        pytest.skip("migration 0061 not applied")
    stub = StubTrail()
    monkeypatch.setattr(W, "_TRAIL", TC.TrailMCPClient("http://trail.stub/mcp", "stub-token", transport=httpx.MockTransport(stub.handle)))
    executors = {**W.EXECUTORS, "POLYMATH_RETRIEVE": _fake_knowledge, "POLYMATH_COMPILE_PLAN": _fake_knowledge, "POLYMATH_GRAPH_EXPAND": _fake_knowledge}
    runs: list[str] = []
    try:
        yield c, stub, executors, runs
    finally:
        c.rollback()
        for rid in runs:
            store.delete_run(c, rid)
        c.commit(); c.close()


def _drive(conn, rid, ex, *, until_status, limit=60):
    for _ in range(limit):
        st = service.advance(conn, rid, ex, max_steps=1); conn.commit()
        if st.status == until_status:
            return st
    raise AssertionError(f"run did not reach {until_status}")


def test_reference_adapter_runs_its_trail_steps_end_to_end_against_the_stub(rig):
    conn, stub, ex, runs = rig
    ref = service.start(conn, adapter_id="trail.product_discovery", input_payload={"seed": "cold plunge recovery for amateur athletes", "corpus_ids": ["probe"]},
                        request_options={"corpus_ids": ["probe"], "agent_identity": "t"})
    conn.commit(); rid = ref["run_id"]; runs.append(rid)
    st = _drive(conn, rid, ex, until_status="awaiting_agent")
    assert st.current_step_id == "C_hypotheses"
    service.submit(conn, rid, {"step_id": "C_hypotheses", "submitted_by": {"agent_identity": "t"}, "payload": {"hypotheses": [
        {"activity": "home cold-water immersion", "friction": "temperature control", "direction": "passive insulation", "supporting_evidence_ids": ["chunk_k1"], "confidence": "medium"}]}}); conn.commit()
    st = _drive(conn, rid, ex, until_status="awaiting_agent")                     # D_discover + E_acquire ran via the stub
    assert st.current_step_id == "F_normalize"
    rows = {r["step_id"]: r for r in store.list_steps(conn, rid)}
    d, e = rows["D_discover"], rows["E_acquire"]
    assert d["status"] == "executed" and d["external_operation"]["outcome"] == "SUCCEEDED" and d["external_operation"]["record_ids"] == ["cand-1", "cand-2", "cand-3"]
    assert [l["url"] for l in d["output"]["leads"]] == ["https://lead.example/1", "https://lead.example/2", "https://lead.example/3"]
    assert e["status"] == "executed" and e["output"]["phase"] == "done" and len(e["output"]["records"]) == 4 and len(e["output"]["extractions"]) == 2
    assert e["external_operation"]["operation_kind"] == "scrape.submit" and set(e["receipt"]["evidence_ids"]) == {r["record_id"] for r in e["output"]["records"]}
    submits = [n for n, _ in stub.calls if n.endswith(".submit")]
    assert submits == ["discover.submit", "scrape.submit", "extract.submit", "extract.submit"]       # submit ONCE each, polled by id
    step = service.next_step(conn, rid)["step"]
    ctx_ids = {r["id"] for r in step["context"]["evidence_refs"] if r["kind"] == "trail_record"}
    assert ctx_ids == {r["record_id"] for r in e["output"]["records"]}                              # the agent sees the Trail records
    cite = sorted(ctx_ids)[:2]
    service.submit(conn, rid, {"step_id": "F_normalize", "submitted_by": {"agent_identity": "t"}, "payload": {"candidates": [
        {"activity": "a", "task": "t", "context": "c", "friction": "f", "workaround": "w", "product_territory": "p", "candidate": "insulated tub", "trail_record_ids": cite, "unknowns": ["seasonality"]}]}}); conn.commit()
    st = _drive(conn, rid, ex, until_status="terminal_gap")                       # G_gates is a PLANNED Trail capability (C1)
    assert st.gap["code"] == "TRAIL_CAPABILITY_PLANNED" and st.gap["step_id"] == "G_gates"
    res = service.result(conn, rid)
    assert validate("adapter_result", res) == [] and res["status"] == "terminal_gap"
    ops = {(o["operation_kind"], o["operation_id"]) for o in res["lineage"]["external_operations"]}
    assert {k for k, _ in ops} == {"discover.submit", "scrape.submit", "extract.submit"} and len(ops) == 4
    assert set(cite) <= {r for o in res["lineage"]["external_operations"] for r in o["record_ids"]}
    assert res["unknowns"] == [{"about": "seasonality"}] and res["lineage"]["polymath_evidence_ids"] == ["chunk_k1"]


def test_cancel_propagates_to_a_pending_trail_operation(rig):
    conn, stub, ex, runs = rig
    ref = service.start(conn, adapter_id="trail.product_discovery", input_payload={"seed": "cold plunge recovery", "corpus_ids": ["probe"]}, request_options={"corpus_ids": ["probe"]})
    conn.commit(); rid = ref["run_id"]; runs.append(rid)
    _drive(conn, rid, ex, until_status="awaiting_agent")
    service.submit(conn, rid, {"step_id": "C_hypotheses", "submitted_by": {"agent_identity": "t"}, "payload": {"hypotheses": [
        {"activity": "a", "friction": "f", "direction": "d", "supporting_evidence_ids": ["chunk_k1"], "confidence": "low"}]}}); conn.commit()
    st = service.advance(conn, rid, ex, max_steps=1); conn.commit()                # D_discover submitted -> pending
    row = store.current_step(conn, rid)
    assert st.status == "running" and row["step_id"] == "D_discover" and row["status"] == "issued" and row["external_operation"]["phase"] == "PENDING"
    def external_cancel(ext):
        client = W.trail(); status = client.status({"operation_id": ext["operation_id"], "operation_kind": ext["operation_kind"], "submitted_at": ext["submitted_at"]})
        cmd = TC.cancel_command(ext["operation_id"], expected_revision=status["revision"], key="k")
        return TC.receipt_after_poll(ext, client.cancel(cmd))
    view = service.cancel(conn, rid, external_cancel=external_cancel); conn.commit()
    assert view["status"] == "cancelled"
    row = store.current_step(conn, rid)
    assert row["external_operation"]["outcome"] == "CANCELLED" and stub.ops[row["external_operation"]["operation_id"]]["outcome"] == "CANCELLED"
    assert service.result(conn, rid)["status"] == "cancelled"
