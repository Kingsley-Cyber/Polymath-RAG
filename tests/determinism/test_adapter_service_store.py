"""COGNITIVE-ADAPTER-V1 E2 — the durable substrate on real Postgres (migration 0061): start → automatic step (fake
executor, no HTTP) → AGENT_REASON issued → next/submit (rejected, then accepted) → COMPILE_RESULT → result with lineage;
idempotent start; cancel; worker leases (claim / no double-claim / renew / release / expiry). Every probe run is deleted."""
from __future__ import annotations

import os
import pathlib
import sys
import time
import uuid

import psycopg
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

ROOT = pathlib.Path(__file__).resolve().parents[2]
for p in (ROOT / "shared", ROOT / "orchestrator"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from polymath_shared.adapter import service, store  # noqa: E402
from polymath_shared.adapter.contracts import validate  # noqa: E402
from polymath_shared.adapter.transitions import SubmissionRejected  # noqa: E402

DSN = os.environ.get("POLYMATH_PG_DSN", "postgresql://polymath:polymath-dev@127.0.0.1:5432/polymath")
ADAPTER = "polymath.knowledge_brief"
FAKE_ROWS = [{"kind": "chunk", "id": "chunk_fake_1", "doc_id": "doc_fake", "corpus_id": "probe", "score": 0.9, "text": "cold plunge lowers perceived soreness"},
             {"kind": "graph_fact", "id": "fact_fake_2", "corpus_id": "probe", "score": 0.7, "text": "immersion → vasoconstriction"}]


def _fake_retrieve(step, state, m):
    return {"output": {"query": state.input["question"], "rows": FAKE_ROWS},
            "evidence_refs": [{k: r[k] for k in ("kind", "id", "corpus_id") if k in r} | ({"doc_id": r["doc_id"]} if "doc_id" in r else {}) for r in FAKE_ROWS]}


FAKE_EXECUTORS = {"POLYMATH_RETRIEVE": _fake_retrieve}


@pytest.fixture()
def conn():
    try:
        c = psycopg.connect(DSN, autocommit=False, connect_timeout=3)
    except Exception as exc:  # pragma: no cover
        pytest.skip(f"postgres unavailable: {exc}")
    if c.execute("SELECT to_regclass('public.adapter_runs')").fetchone()[0] is None:
        pytest.skip("migration 0061 not applied")
    runs: list[str] = []
    c.runs = runs  # type: ignore[attr-defined]
    try:
        yield c
    finally:
        c.rollback()
        for rid in runs:
            store.delete_run(c, rid)
        c.commit()
        c.close()


def _start(conn, key=None):
    opts = {"corpus_ids": ["probe"], "agent_identity": "test-agent"}
    if key:
        opts["idempotency_key"] = key
    ref = service.start(conn, adapter_id=ADAPTER, input_payload={"question": "does cold water immersion reduce soreness?", "corpus_ids": ["probe"]},
                        request_options=opts)
    conn.commit()
    conn.runs.append(ref["run_id"])
    assert validate("adapter_run_ref", ref) == [] and ref["status"] == "running"
    return ref["run_id"]


def test_full_substrate_walk_with_fake_executor(conn):
    rid = _start(conn)
    # a run that has not reached an agent step reports status, not a step
    assert service.next_step(conn, rid)["kind"] == "status"
    st = service.advance(conn, rid, FAKE_EXECUTORS); conn.commit()
    assert st.status == "awaiting_agent" and st.current_step_id == "brief" and st.sequence == 2
    rows = store.list_steps(conn, rid)
    assert [r["status"] for r in rows] == ["executed", "issued"] and rows[0]["receipt"]["evidence_ids"] == ["chunk_fake_1", "fact_fake_2"]
    nxt = service.next_step(conn, rid)
    assert nxt["kind"] == "step" and nxt["step"]["step_type"] == "AGENT_REASON"
    assert {r["id"] for r in nxt["step"]["context"]["evidence_refs"]} == {"chunk_fake_1", "fact_fake_2"}
    sub = lambda payload: {"step_id": "brief", "payload": payload, "submitted_by": {"agent_identity": "test-agent", "model": "fake"}}
    with pytest.raises(SubmissionRejected):                                   # schema: key_points required
        service.submit(conn, rid, sub({"brief": {"thesis": "x" * 12, "unknowns": []}}))
    with pytest.raises(SubmissionRejected) as e:                              # cites an id that was never supplied
        service.submit(conn, rid, sub({"brief": {"thesis": "immersion helps soreness", "key_points": [{"point": "helps recovery", "supporting_evidence_ids": ["chunk_invented"]}], "unknowns": []}}))
    assert "not in context.evidence_refs" in e.value.errors[0]
    assert store.current_step(conn, rid)["status"] == "issued"               # a rejection keeps the step open
    good = {"brief": {"thesis": "cold water immersion reduces perceived soreness", "key_points": [{"point": "lower perceived soreness", "supporting_evidence_ids": ["chunk_fake_1"]}], "unknowns": ["dose"]}}
    st_view = service.submit(conn, rid, sub(good)); conn.commit()
    assert st_view["status"] == "running" and st_view["steps_accepted"] == 2
    assert store.current_step(conn, rid)["status"] == "accepted"
    st = service.advance(conn, rid, FAKE_EXECUTORS); conn.commit()
    assert st.status == "completed"
    res = service.result(conn, rid)
    assert validate("adapter_result", res) == [] and res["status"] == "completed"
    assert res["output"]["brief"]["thesis"].startswith("cold water") and res["lineage"]["polymath_evidence_ids"] == ["chunk_fake_1", "fact_fake_2"]
    # lineage carries the receipts that EXIST when the result is compiled (retrieve executed, brief accepted);
    # the compile step's own receipt records the result hash and cannot be inside the result it hashes
    assert len(res["lineage"]["step_receipt_hashes"]) == 2 and res["unknowns"] == [{"about": "dose"}]
    assert store.current_step(conn, rid)["output"] == {"result_hash": service.stable_hash(res)}
    assert service.advance(conn, rid, FAKE_EXECUTORS).status == "completed"   # a terminal run is left untouched


def test_start_is_idempotent_on_the_request_key(conn):
    key = "probe-" + uuid.uuid4().hex[:8]
    a = _start(conn, key)
    ref = service.start(conn, adapter_id=ADAPTER, input_payload={"question": "does cold water immersion reduce soreness?", "corpus_ids": ["probe"]}, request_options={"idempotency_key": key, "corpus_ids": ["probe"]})
    assert ref["run_id"] == a


def test_cancel_is_terminal_and_result_is_synthesised(conn):
    rid = _start(conn)
    st = service.cancel(conn, rid); conn.commit()
    assert st["status"] == "cancelled"
    res = service.result(conn, rid)
    assert res["status"] == "cancelled" and validate("adapter_result", res) == []
    assert service.cancel(conn, rid)["status"] == "cancelled"                 # idempotent


def test_worker_leases_claim_renew_release_and_expire(conn):
    rid = _start(conn)
    assert store.claim_run(conn, "w1", 2) == rid
    conn.commit()
    with psycopg.connect(DSN) as other:
        assert store.claim_run(other, "w2", 2) is None                       # leased: no double claim
    assert store.renew_lease(conn, rid, "w1", 2) is True and store.renew_lease(conn, rid, "w2", 2) is False
    store.release_lease(conn, rid, "w1"); conn.commit()
    with psycopg.connect(DSN) as other:
        assert store.claim_run(other, "w2", 1) == rid; other.commit()
    time.sleep(1.2)                                                            # lease expiry -> claimable again
    with psycopg.connect(DSN) as third:
        assert store.claim_run(third, "w3", 5) == rid; third.rollback()


def test_http_routes_are_thin_wrappers(conn, monkeypatch):
    app = FastAPI(); from orchestrator.api.adapter import router; app.include_router(router)
    client = TestClient(app)
    listing = client.get("/adapter/list").json()
    assert {a["adapter_id"] for a in listing["adapters"]} >= {ADAPTER, "trail.product_discovery"}
    r = client.post("/adapter/start", json={"adapter_id": ADAPTER, "input": {"question": "does cold water immersion reduce soreness?", "corpus_ids": ["probe"]}, "request_options": {"corpus_ids": ["probe"]}})
    assert r.status_code == 200, r.text
    rid = r.json()["run_id"]; conn.runs.append(rid)
    assert client.get(f"/adapter/{rid}/status").json()["status"] == "running"
    assert client.get(f"/adapter/{rid}/next").json()["kind"] == "status"
    assert client.get(f"/adapter/{rid}/result").status_code == 409
    assert client.post("/adapter/start", json={"adapter_id": "nope.x", "input": {}}).status_code == 404
    assert client.post("/adapter/start", json={"adapter_id": ADAPTER, "input": {"corpus_ids": ["probe"]}}).status_code == 422   # question required
    assert client.post(f"/adapter/{rid}/submit", json={"step_id": "brief", "payload": {}}).status_code == 422                    # nothing awaiting
    assert client.post(f"/adapter/{rid}/cancel").json()["status"] == "cancelled"
    assert client.get("/adapter/adr_ffffffffffffffffffffffffffffffff/status").status_code == 404
