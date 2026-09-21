#!/usr/bin/env python3
"""Domain binding: the ONE door between the Polymath adapter runtime and this engine (DOMAIN_OPERATION, ADR-0020).

The adapter worker runs this file out of process — one JSON request on stdin, one JSON object on stdout — so the engine's flat
module names (`transitions`, `graph`, `store`, `models`, …) never enter the worker's namespace and an engine crash is a typed
step failure, not a dead worker.

    request   {"schema_version": "domain_operation_request.v1", "domain", "operation", "run_id", "step_id",
               "input": {…run input…}, "inputs": {…values the manifest step selected…}, "config": {…step config…}}
    response  {"ok": true,  "output": {…}}                      the step output
              {"ok": false, "code": "UPPER_SNAKE", "message"}   a typed domain refusal (the run stops with this gap code)
    exit != 0 / anything else on stdout                          a crash — the runtime records STEP_EXECUTOR_ERROR

`OPERATIONS` WRAPS existing engine functions. Nothing here re-implements domain logic, reads or writes run state, or touches a
ledger: the runtime owns state, this file only computes. Anything the engine prints goes to stderr, never into the response.
"""
from __future__ import annotations

import contextlib
import json
import os
import sys
from typing import Any, Callable

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ROOT, "python"))

REQUEST_VERSION = "domain_operation_request.v1"


class Refusal(Exception):
    """A typed domain refusal: the request is well-formed but the engine declines it."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code, self.message = code, message


def _op_validate_bridge(req: dict[str, Any]) -> dict[str, Any]:
    """φ constraining θ: bridge admissibility (evidence boundary, bounded inference hops, a researchable gap) and the portfolio
    diversity law, exactly as `python/bridge.py` enforces them standalone. Inadmissible is an OUTPUT (the run can branch back
    to reasoning), not a refusal."""
    import bridge
    import graph as graphmod

    hyps = (req.get("inputs") or {}).get("hypotheses")
    if not isinstance(hyps, list) or not hyps or not all(isinstance(h, dict) for h in hyps):
        raise Refusal("HYPOTHESES_MISSING", "inputs.hypotheses must be a non-empty list of bridge hypotheses")
    known = (req.get("inputs") or {}).get("known_evidence_ids")
    policies = graphmod.load_policies()
    bridge_errors = bridge.validate_all(hyps, policies, set(known) if isinstance(known, list) else None)
    portfolio_errors = bridge.validate_portfolio(hyps, policies)
    return {"admissible": not bridge_errors and not portfolio_errors, "bridge_errors": bridge_errors,
            "portfolio_errors": portfolio_errors, "hypotheses_checked": len(hyps)}


#: operation id -> wrapper. One table; an id not listed here is a typed refusal.
OPERATIONS: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {
    "hypotheses.validate_bridge": _op_validate_bridge,
}


def handle(req: Any) -> dict[str, Any]:
    if not isinstance(req, dict) or req.get("schema_version") != REQUEST_VERSION:
        return {"ok": False, "code": "DOMAIN_REQUEST_INVALID", "message": f"expected a {REQUEST_VERSION} object"}
    op = OPERATIONS.get(str(req.get("operation")))
    if op is None:
        return {"ok": False, "code": "DOMAIN_OPERATION_UNKNOWN", "message": f"{req.get('operation')!r} is not an operation of this domain"}
    try:
        with contextlib.redirect_stdout(sys.stderr):
            output = op(req)
    except Refusal as exc:
        return {"ok": False, "code": exc.code, "message": exc.message}
    return {"ok": True, "output": output}


def main() -> int:
    try:
        req = json.loads(sys.stdin.read())
    except json.JSONDecodeError as exc:
        print(json.dumps({"ok": False, "code": "DOMAIN_REQUEST_INVALID", "message": f"request is not JSON: {exc}"}))
        return 0
    print(json.dumps(handle(req), sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
