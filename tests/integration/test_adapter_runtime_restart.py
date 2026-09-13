"""COGNITIVE-ADAPTER-V1 E2 item 5 — RESUME AFTER A CONTROLLED WORKER CRASH, with REAL Polymath retrieval.

Live: needs Postgres (migration 0061) and the orchestrator at POLYMATH_ORCH_URL (default 127.0.0.1:7200) serving
POST /retrieve for the `cinema` corpus; skips otherwise. Flow: start polymath.knowledge_brief → worker #1 executes the
RETRIEVE step over HTTP then os._exit(137) WITHOUT releasing its lease (--crash-after 1) → the run is still `running`
and leased → after the 2-second lease expires worker #2 resumes, issues the AGENT_REASON step → the test submits a
brief citing REAL evidence ids from the issued step → worker #3 compiles → adapter_result carries that lineage."""
from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys
import time

import httpx
import psycopg
import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(ROOT / "shared") not in sys.path:
    sys.path.insert(0, str(ROOT / "shared"))
from polymath_shared.adapter import service, store  # noqa: E402
from polymath_shared.adapter.contracts import validate  # noqa: E402

DSN = os.environ.get("POLYMATH_PG_DSN", "postgresql://polymath:polymath-dev@127.0.0.1:5432/polymath")
ORCH = os.environ.get("POLYMATH_ORCH_URL", "http://127.0.0.1:7200")
CORPUS = os.environ.get("POLYMATH_ADAPTER_TEST_CORPUS", "cinema")


def _worker(*args: str) -> subprocess.CompletedProcess:
    env = {**os.environ, "PYTHONPATH": f"{ROOT / 'shared'}{os.pathsep}{ROOT / 'workers'}", "POLYMATH_PG_DSN": DSN, "POLYMATH_ORCH_URL": ORCH}
    return subprocess.run([sys.executable, "-m", "workers.adapter_step_worker", "--once", "--lease-s", "2", *args],
                          cwd=ROOT / "workers", env=env, capture_output=True, text=True, timeout=300)


@pytest.fixture()
def live():
    try:
        r = httpx.get(f"{ORCH}/health", timeout=3)
        assert r.status_code == 200
    except Exception as exc:  # pragma: no cover
        pytest.skip(f"orchestrator unreachable: {exc}")
    try:
        c = psycopg.connect(DSN, connect_timeout=3)
    except Exception as exc:  # pragma: no cover
        pytest.skip(f"postgres unavailable: {exc}")
    if c.execute("SELECT to_regclass('public.adapter_runs')").fetchone()[0] is None:
        pytest.skip("migration 0061 not applied")
    runs: list[str] = []
    try:
        yield c, runs
    finally:
        for rid in runs:
            store.delete_run(c, rid)
        c.commit(); c.close()


def test_worker_crash_between_retrieve_and_agent_step_resumes_without_losing_work(live):
    conn, runs = live
    ref = service.start(conn, adapter_id="polymath.knowledge_brief",
                        input_payload={"question": "How is a fight scene choreographed so the camera reads the action clearly?", "corpus_ids": [CORPUS], "top_k": 8},
                        request_options={"corpus_ids": [CORPUS], "agent_identity": "restart-test"})
    conn.commit(); rid = ref["run_id"]; runs.append(rid)

    p1 = _worker("--max-steps", "1", "--crash-after", "1")                # executes RETRIEVE (real HTTP) then dies holding the lease
    assert p1.returncode == 137, p1.stderr[-800:]
    state, meta = store.load_run(conn, rid)
    assert state.status == "running" and state.current_step_id == "retrieve" and meta["lease_owner"], "crash must leave the lease held"
    rows = store.list_steps(conn, rid)
    assert rows[-1]["status"] == "executed" and rows[-1]["receipt"]["evidence_ids"], "the executed step survived the crash"
    evidence_ids = set(rows[-1]["receipt"]["evidence_ids"])
    assert evidence_ids, "real retrieval returned evidence rows"

    time.sleep(2.5)                                                        # lease expiry
    p2 = _worker("--max-steps", "3")                                       # resumes: issues the AGENT_REASON step and stops (awaiting)
    assert p2.returncode == 0, p2.stderr[-800:]
    state, _ = store.load_run(conn, rid)
    assert state.status == "awaiting_agent" and state.current_step_id == "brief"
    nxt = service.next_step(conn, rid)
    assert nxt["kind"] == "step" and validate("adapter_step", nxt["step"]) == []
    ctx_ids = {r["id"] for r in nxt["step"]["context"]["evidence_refs"]}
    assert evidence_ids <= ctx_ids, "the agent step carries exactly the evidence retrieved before the crash"

    cite = sorted(ctx_ids)[:2]
    service.submit(conn, rid, {"step_id": "brief", "submitted_by": {"agent_identity": "restart-test", "model": "test"},
                               "payload": {"brief": {"thesis": "camera readability comes from staging the beats for the lens",
                                                     "key_points": [{"point": "choreography is staged for the camera", "supporting_evidence_ids": cite}],
                                                     "unknowns": ["how much rehearsal time is typical"]}}})
    conn.commit()
    p3 = _worker("--max-steps", "3")                                       # compiles
    assert p3.returncode == 0, p3.stderr[-800:]
    res = service.result(conn, rid)
    assert validate("adapter_result", res) == [] and res["status"] == "completed"
    assert set(cite) <= set(res["lineage"]["polymath_evidence_ids"]) and res["output"]["brief"]["key_points"][0]["supporting_evidence_ids"] == cite
    assert len(res["lineage"]["step_receipt_hashes"]) == 2 and res["gap"] is None
    print(json.dumps({"run_id": rid, "evidence": len(evidence_ids), "receipts": res["lineage"]["step_receipt_hashes"]}))
