"""TrailSignal's deterministic research core, embedded (docs/migration/ADR-TRAIL-EMBEDDING.md, AUTO_DECISIONS M-012).

Everything under `src/trail_signal/`, `config/` and `data/` is BYTE-IDENTICAL to TrailSignal HR6 @ 829a0ab (ADR-069 re-pin of A41 @ de64d84; `PROVENANCE.json`
pins every sha256; `tests/contracts/test_trail_core_embedding.py` fails on any edit). This file is the ONLY Polymath-authored code
here. It does what TrailSignal's daemon composition root does (`entrypoints/daemon/composition.py:1081`) and what its MCP tool layer
does (`entrypoints/mcp/tools/research.py`) — nothing more:

  * `build_service()`      the real `ResearchOperationService` over the real compiled registry snapshot and the real planning /
                           evidence / scoring functions;
  * `SqliteResearchStore`  TrailSignal's store port (`commit`, `load`, `load_admitted`): one audit operation + one immutable result,
                           first commit wins, replayed for the same identity — durable across a worker restart;
  * `transport()`          an `httpx` transport that answers the same JSON-RPC `tools/call` the daemon answers, so Polymath's
                           unchanged `TrailMCPClient` / `exec_external` reach the embedded core exactly as they reach the daemon.

Logical ownership does not move: TrailSignal still owns the registry, admission, judgement, qualification and the only score.
Polymath hosts the process. Nothing here reads or writes Polymath state.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import sqlite3
import sys
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

import httpx  # noqa: E402
from trail_signal.contexts.planning.domain.gap_compiler import compile_research_directive, derive_registry_coordinates, map_product_territories  # noqa: E402
from trail_signal.contexts.planning.domain.judgement import judge_hypotheses  # noqa: E402
from trail_signal.contexts.planning.domain.registry_compiler import compile_registry_snapshot, prior_record_ids  # noqa: E402
from trail_signal.contexts.platform.public.contracts import PrincipalCapabilityV6, PrincipalContextV6  # noqa: E402
from trail_signal.contexts.scoring.domain.engine import load_score_weights  # noqa: E402
from trail_signal.contexts.workflow.application.research_operations import (  # noqa: E402
    RESEARCH_OPERATIONS, ResearchFunctions, ResearchOperationRecord, ResearchOperationService, ResearchRefused, ResearchResultRecord)
from trail_signal.contexts.workflow.public.operations import BoundedResearchRequestV1  # noqa: E402

MAXIMUM_REQUEST_BYTES = 65536          # the daemon's configured ceiling (composition.py) — a policy value, not tuned here
FUNCTIONS = ResearchFunctions(derive_registry_coordinates=derive_registry_coordinates, compile_research_directive=compile_research_directive,
                              judge_hypotheses=judge_hypotheses, map_product_territories=map_product_territories, prior_record_ids=prior_record_ids)
_OP_COLS = ("operation_id", "principal_id", "audit_identity", "operation_kind", "idempotency_key", "request_id", "run_ref", "purpose_ref", "registry_snapshot_id",
            "registry_snapshot_hash", "request_sha256", "request_json", "status_json", "committed_at")
_RES_COLS = ("operation_id", "result_schema_name", "result_sha256", "result_json", "committed_at")


class SqliteResearchStore:
    """TrailSignal's audit store. `path=None` keeps it in memory (tests); a file path makes it survive a worker restart."""

    def __init__(self, path: str | Path | None = None) -> None:
        self._db = sqlite3.connect(str(path) if path else ":memory:", check_same_thread=False, isolation_level=None)
        self._lock = threading.Lock()
        self._db.execute(f"CREATE TABLE IF NOT EXISTS research_operations ({', '.join(c + ' TEXT NOT NULL' for c in _OP_COLS)}, PRIMARY KEY (operation_id))")
        self._db.execute(f"CREATE TABLE IF NOT EXISTS research_results ({', '.join(c + ' TEXT NOT NULL' for c in _RES_COLS)}, PRIMARY KEY (operation_id))")

    @staticmethod
    def _row(record, cols) -> tuple:
        return tuple(getattr(record, c).isoformat() if c == "committed_at" else getattr(record, c) for c in cols)

    def _load(self, operation_id: str):
        op = self._db.execute(f"SELECT {', '.join(_OP_COLS)} FROM research_operations WHERE operation_id=?", (operation_id,)).fetchone()
        if op is None:
            return None
        res = self._db.execute(f"SELECT {', '.join(_RES_COLS)} FROM research_results WHERE operation_id=?", (operation_id,)).fetchone()
        when = lambda row, cols: {**dict(zip(cols, row)), "committed_at": datetime.fromisoformat(row[-1])}  # noqa: E731
        return ResearchOperationRecord(**when(op, _OP_COLS)), (ResearchResultRecord(**when(res, _RES_COLS)) if res else None)

    async def commit(self, operation: ResearchOperationRecord, result: ResearchResultRecord):
        with self._lock:                       # one audit operation + one immutable result, atomically; the FIRST commit for an identity wins
            self._db.execute("BEGIN IMMEDIATE")
            try:
                self._db.execute(f"INSERT OR IGNORE INTO research_operations VALUES ({', '.join('?' * len(_OP_COLS))})", self._row(operation, _OP_COLS))
                self._db.execute(f"INSERT OR IGNORE INTO research_results VALUES ({', '.join('?' * len(_RES_COLS))})", self._row(result, _RES_COLS))
                self._db.execute("COMMIT")
            except BaseException:
                self._db.execute("ROLLBACK")
                raise
            return self._load(operation.operation_id)

    async def load(self, operation_id: str):
        with self._lock:
            return self._load(operation_id)

    async def load_admitted(self, run_ref: str) -> tuple[str, ...]:
        with self._lock:
            rows = self._db.execute("""SELECT r.result_json FROM research_operations o JOIN research_results r USING (operation_id)
                                        WHERE o.run_ref=? AND o.operation_kind='evidence.admit' ORDER BY o.committed_at, o.operation_id""", (run_ref,)).fetchall()
        return tuple(r[0] for r in rows)


def build_service(*, store=None, clock=None) -> ResearchOperationService:
    now = (clock or (lambda: datetime.now(timezone.utc)))()
    snapshot = compile_registry_snapshot(ROOT / "data", ROOT / "config", ROOT / "data" / "source_capabilities.csv", compiled_at=now)
    kwargs = {"clock": clock} if clock else {}
    return ResearchOperationService(store=store or SqliteResearchStore(), snapshot=snapshot, weights=load_score_weights(ROOT / "config"),
                                    maximum_request_bytes=MAXIMUM_REQUEST_BYTES, functions=FUNCTIONS, **kwargs)


def polymath_principal(principal_id: str = "polymath") -> PrincipalContextV6:
    """The one caller of the embedded core: Polymath's adapter worker, with exactly the capabilities the daemon grants that principal."""
    now = datetime.now(timezone.utc)
    caps = tuple(PrincipalCapabilityV6(v) for v in ("operation.get", "operation.command") + RESEARCH_OPERATIONS)
    return PrincipalContextV6(principal_id=principal_id, audit_identity=principal_id, capabilities=caps, policy_ref="public-static-v1", budget_ref="p1-static-default-v1",
                              credential_binding_hash="sha256:" + hashlib.sha256(b"polymath-embedded-trail-core").hexdigest(),
                              authenticated_at=now - timedelta(seconds=1), expires_at=now + timedelta(hours=1))


def operate(service: ResearchOperationService, operation_kind: str, request: dict, principal_id: str = "polymath") -> dict:
    """What `entrypoints/mcp/tools/research.py` does for one tool call: one typed request in, one immutable typed result out."""
    parsed = BoundedResearchRequestV1.model_validate_json(json.dumps(request))
    if parsed.operation_kind != operation_kind:
        raise PermissionError(f"{operation_kind}: request names {parsed.operation_kind}")
    result = asyncio.run(service.operate(parsed, polymath_principal(principal_id)))
    return result.model_dump(mode="json")


def transport(service: ResearchOperationService | None = None) -> httpx.MockTransport:
    """An httpx transport answering the daemon's JSON-RPC surface in process. A refusal or an invalid request is a tool ERROR
    (`isError: true`), exactly as the daemon reports it — never an exception into the caller."""
    svc = service or build_service()

    def handle(req: httpx.Request) -> httpx.Response:
        body = json.loads(req.content)
        rid, method, params = body.get("id"), body.get("method"), body.get("params") or {}
        if method != "tools/call":                           # initialize / notifications: acknowledge, nothing to negotiate in process
            return httpx.Response(200, json={"jsonrpc": "2.0", "id": rid, "result": {"protocolVersion": "2025-03-26", "capabilities": {"tools": {}},
                                                                                     "serverInfo": {"name": "trailsignal-embedded", "version": "HR6@829a0ab"}}})
        name = str(params.get("name") or "")
        try:
            if name not in RESEARCH_OPERATIONS:
                raise PermissionError(f"unknown tool {name}")
            value = operate(svc, name, (params.get("arguments") or {}).get("request") or {})
            result = {"content": [{"type": "text", "text": json.dumps(value)}], "structuredContent": value, "isError": False}
        except ResearchRefused as exc:
            result = {"content": [{"type": "text", "text": f"{exc.code}: {exc}"}], "isError": True}
        except Exception as exc:  # noqa: BLE001 — validation / permission errors are tool errors on the wire, as in the daemon
            result = {"content": [{"type": "text", "text": f"{type(exc).__name__}: {exc}"[:2000]}], "isError": True}
        return httpx.Response(200, json={"jsonrpc": "2.0", "id": rid, "result": result})

    return httpx.MockTransport(handle)
