"""Consolidation migration — the complete scripted `ecommerce.product_research` run on the REAL Postgres adapter store (`store.py`, the
hypothesis ledger tables, harness actions, admitted evidence), not the in-memory double. Same scripted agent / harness / stub TrailSignal as
`tests/determinism/test_adapter_ecommerce_product_research_e2e.py`.

ISOLATION (AGENT_OPERATING_DOCTRINE §14): between steps this run is COMMITTED in status `running`, exactly what a live adapter worker claims. It
therefore refuses to run unless the database is declared isolated: POLYMATH_ISOLATED_PG=1 together with POLYMATH_PG_DSN (a throwaway Postgres
with the repository migrations applied). Never point it at the fleet's database.
"""
from __future__ import annotations

import os
import pathlib
import sys
import uuid

import httpx
import pytest

pytest.importorskip("psycopg")
if not (os.environ.get("POLYMATH_PG_DSN") and os.environ.get("POLYMATH_ISOLATED_PG") == "1"):
    pytest.skip("needs an ISOLATED Postgres: POLYMATH_PG_DSN + POLYMATH_ISOLATED_PG=1 (never the fleet's database)", allow_module_level=True)

ROOT = pathlib.Path(__file__).resolve().parents[2]
for _p in (ROOT / "workers", ROOT / "shared", ROOT / "tests" / "determinism"):
    sys.path.insert(0, str(_p))

from polymath_shared.adapter import service, store  # noqa: E402
from polymath_shared.adapter import trail_client as TC  # noqa: E402
from polymath_shared.db import tx  # noqa: E402
import workers.adapter_step_worker as W  # noqa: E402
import test_adapter_ecommerce_product_research_e2e as SCRIPT  # noqa: E402


def test_the_complete_scripted_run_on_the_real_postgres_store(monkeypatch):
    for mod in (service, store, W):
        assert pathlib.Path(mod.__file__).resolve().is_relative_to(ROOT), f"{mod.__name__} resolved outside {ROOT}: {mod.__file__}"
    trail = SCRIPT.StubTrail()
    monkeypatch.setattr(W, "_TRAIL", TC.TrailMCPClient("http://trail.stub/mcp", "stub-token", transport=httpx.MockTransport(trail.handle)))
    service.reset_registry()
    execs = {**W.EXECUTORS, "POLYMATH_RETRIEVE": SCRIPT._knowledge, "POLYMATH_COMPILE_PLAN": SCRIPT._knowledge, "POLYMATH_GRAPH_EXPAND": SCRIPT._knowledge}
    agent = SCRIPT.Agent()
    with tx() as conn:
        rid = service.start(conn, adapter_id=SCRIPT.ADAPTER_ID, input_payload={"seed": SCRIPT.SEED, "corpus_ids": ["probe"]},
                            request_options={"corpus_ids": ["probe"], "idempotency_key": uuid.uuid4().hex})["run_id"]
    try:
        for _ in range(220):
            with tx() as conn:
                st = service.advance(conn, rid, execs, max_steps=1)
            if st.terminal:
                break
            if st.status in ("awaiting_agent", "awaiting_harness"):
                with tx() as conn:
                    nxt = service.next_step(conn, rid)
                    step = nxt["step"]
                    if st.status == "awaiting_agent":
                        service.submit(conn, rid, {"step_id": step["step_id"], "payload": agent.answer(nxt), "submitted_by": {"agent_identity": "test-agent"}})
                    else:
                        service.submit(conn, rid, {"step_id": step["step_id"], "payload": SCRIPT._harness(step, rid), "submitted_by": {"agent_identity": "test-harness"}, "kind": "receipt"})
        assert st.status == "completed", (st.status, st.gap, st.failure)
        with tx() as conn:
            out = service.result(conn, rid)["output"]
            rows = store.list_steps(conn, rid)
            hyps = store.current_hypotheses(conn, rid)
            admitted = store.admitted_evidence_refs(conn, rid)
        assert len(out["product_concepts"]) == 3 and [l["concept_id"] for l in out["leads"]] == ["pc_1", "pc_2"] and out["trail_scores"][0]["record_id"] == "score-1"
        assert sum(1 for r in rows if r["step_type"] == "DOMAIN_OPERATION" and r["status"] == "executed") == 15            # the new step type persists through the real step table
        assert len(hyps) == 3 and {h["status"] for h in hyps.values()} >= {"strengthened", "weakened"}                    # TrailSignal's verdicts moved the REAL ledger
        assert len(admitted) == 5 + 1 + 2                                                                                  # field + product reality + supply, from the real admitted-evidence table
        assert agent.keys["G_mechanisms"] == {"kind", "step", "status", "evidence"}                                       # `materials` stays strictly opt-in on the real store too
    finally:
        with tx() as conn:
            store.delete_run(conn, rid)
        service.reset_registry()
