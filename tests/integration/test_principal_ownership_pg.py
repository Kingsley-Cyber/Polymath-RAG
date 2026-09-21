"""HOSTED-MCP PRINCIPALS on the REAL Postgres store (migration 0066): run ownership written by `service.start`, enforced through
the REAL adapter API under the trusted principal context, the per-owner idempotency key, and query receipts stamped with the
principal and filtered by it — while `client` stays the software identity.

ISOLATION: this commits adapter runs in status `running` (what a live worker claims). It refuses to run unless the database
is declared isolated: POLYMATH_PG_DSN + POLYMATH_ISOLATED_PG=1 (a throwaway Postgres with the repository migrations applied).
"""
from __future__ import annotations

import os
import pathlib
import sys
import uuid

import pytest

pytest.importorskip("psycopg")
if not (os.environ.get("POLYMATH_PG_DSN") and os.environ.get("POLYMATH_ISOLATED_PG") == "1"):
    pytest.skip("needs an ISOLATED Postgres: POLYMATH_PG_DSN + POLYMATH_ISOLATED_PG=1 (never the fleet's database)", allow_module_level=True)

ROOT = pathlib.Path(__file__).resolve().parents[2]
for _p in (ROOT / "orchestrator", ROOT / "shared"):
    sys.path.insert(0, str(_p))

from fastapi import FastAPI  # noqa: E402
from starlette.testclient import TestClient  # noqa: E402

from orchestrator.api import adapter as adapter_api  # noqa: E402
from orchestrator.api import queries as queries_api  # noqa: E402
from polymath_shared import principal_context, query_receipts  # noqa: E402
from polymath_shared.adapter import service, store  # noqa: E402
from polymath_shared.db import tx  # noqa: E402

ADAPTER = "polymath.knowledge_brief"
START = {"adapter_id": ADAPTER, "input": {"question": "what do shoppers abandon carts over?"}}


@pytest.fixture()
def api():
    for mod in (adapter_api, queries_api, principal_context, query_receipts, service, store):
        assert pathlib.Path(mod.__file__).resolve().is_relative_to(ROOT), mod.__file__
    app = FastAPI()
    app.add_middleware(principal_context.PrincipalContextMiddleware)
    app.include_router(adapter_api.router)
    app.include_router(queries_api.router)
    with TestClient(app) as c:
        yield c


def _as(principal):
    return {"X-Polymath-Principal": principal} if principal else {}


def test_run_ownership_on_the_real_store(api):
    key = uuid.uuid4().hex
    body = {**START, "request_options": {"corpus_ids": ["probe"], "idempotency_key": key, "agent_identity": "claude-code"}}
    alice = api.post("/adapter/start", json=body, headers=_as("prn_alice")).json()["run_id"]
    bob = api.post("/adapter/start", json=body, headers=_as("prn_bob")).json()["run_id"]
    legacy = api.post("/adapter/start", json=body).json()["run_id"]
    try:
        assert len({alice, bob, legacy}) == 3                                       # one idempotency key, three owners, three runs
        assert api.post("/adapter/start", json=body, headers=_as("prn_alice")).json()["run_id"] == alice
        with tx() as conn:
            assert [store.run_owner(conn, r) for r in (alice, bob, legacy)] == [(True, "prn_alice"), (True, "prn_bob"), (True, None)]
            row = conn.execute("SELECT agent_identity, owner_principal_id FROM adapter_runs WHERE run_id=%s", (alice,)).fetchone()
        assert row == ("claude-code", "prn_alice")                                  # two columns, two meanings
        for path in ("status", "next"):
            assert api.get(f"/adapter/{alice}/{path}", headers=_as("prn_alice")).status_code == 200
            assert api.get(f"/adapter/{alice}/{path}", headers=_as("prn_bob")).status_code == 403
            assert api.get(f"/adapter/{legacy}/{path}", headers=_as("prn_alice")).status_code == 403    # NULL owner is not "public"
            assert api.get(f"/adapter/{alice}/{path}").status_code == 200           # trusted-local: unchanged
        assert api.get(f"/adapter/{alice}/result", headers=_as("prn_bob")).status_code == 403
        assert api.post(f"/adapter/{alice}/cancel", headers=_as("prn_bob")).status_code == 403
        assert api.get(f"/adapter/{alice}/status", headers=_as("prn_alice")).json()["status"] == "running"    # bob's cancel did nothing
        unknown = api.get("/adapter/adr_00000000000000000000000000000000/status", headers=_as("prn_bob"))
        assert (unknown.status_code, unknown.json()) == (403, api.get(f"/adapter/{alice}/status", headers=_as("prn_bob")).json())
        assert api.get("/adapter/adr_00000000000000000000000000000000/status").status_code == 404
    finally:
        with tx() as conn:                                                          # leave no claimable run behind
            conn.execute("DELETE FROM adapter_runs WHERE run_id = ANY(%s)", ([alice, bob, legacy],))


def test_query_receipts_carry_the_principal_and_history_is_the_callers_own(api):
    corpus = "probe-" + uuid.uuid4().hex[:8]

    class Req:
        mode, latent = "HYBRID", None

    def ask(principal, question):
        token = principal_context._current.set(principal)
        try:
            return query_receipts.record_query_receipt(tx, kind="retrieve", question=question, req=Req(), scope_corpora=[corpus], scope_kind="corpus",
                                                       wall_ms=12.0, out={"evidence_rows": []}, client="claude-code/2.1")
        finally:
            principal_context._current.reset(token)
    ids = {"alice": ask("prn_alice", "alice's question"), "bob": ask("prn_bob", "bob's question"), "local": ask(None, "the owner's question")}
    try:
        assert all(ids.values())
        with tx() as conn:
            rows = dict(conn.execute("SELECT query_id, (client, principal_id)::text FROM query_receipts WHERE query_id = ANY(%s)", (list(ids.values()),)).fetchall())
        assert rows[ids["alice"]] == '(claude-code/2.1,prn_alice)' and rows[ids["local"]] == '(claude-code/2.1,)'

        def seen(principal):
            out = api.get("/queries", params={"corpus_id": corpus}, headers=_as(principal)).json()
            return {q["query_id"] for q in out["queries"]}, sum(m.get("count", 0) for m in (out["summary"] if isinstance(out["summary"], list) else (out["summary"] or {}).get("modes", [])) if isinstance(m, dict))
        assert seen("prn_alice")[0] == {ids["alice"]}
        assert seen("prn_bob")[0] == {ids["bob"]}
        assert seen(None)[0] == set(ids.values())                                    # the trusted-local caller sees the corpus's history
    finally:
        with tx() as conn:
            conn.execute("DELETE FROM query_receipts WHERE query_id = ANY(%s)", (list(ids.values()),))
