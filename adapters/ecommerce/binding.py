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


def _inputs(req: dict[str, Any]) -> dict[str, Any]:
    ins = req.get("inputs")
    return ins if isinstance(ins, dict) else {}


def _engine_state(**data: Any) -> dict[str, Any]:
    """The engine's functions take `(state, policies)` and read / write `state["data"][key]`. A governed operation gets a
    THROWAWAY state holding only what the manifest selected; the keys the function wrote are returned as the step output."""
    return {"data": {k: v for k, v in data.items() if v is not None}}


def _corpus_rows(value: Any) -> list[dict[str, Any]]:
    rows = value if isinstance(value, list) else []
    if not rows or not all(isinstance(r, dict) and r.get("id") for r in rows):
        raise Refusal("CORPUS_EVIDENCE_MISSING", "inputs.corpus_evidence must be the non-empty row list `knowledge.corpus_evidence` produced")
    return rows


def _op_corpus_evidence(req: dict[str, Any]) -> dict[str, Any]:
    """Governed knowledge rows (the adapter runtime's evidence-boundary output: chunk id, text, utility role, CA4 grade, origin)
    become the engine's corpus rows through the engine's OWN EvidencePacket mapping (`corpus_polymath.rows_from_packet`) — the
    one place a row gets its `polymath:chunk:<id>` identity, its authority hints and its role / grade tags. No HTTP here: the
    runtime already retrieved. `row_sets` is a list of row lists (one per knowledge step); the first occurrence of an id wins."""
    import corpus_polymath as cp

    sets = _inputs(req).get("row_sets")
    if not isinstance(sets, list) or not any(isinstance(s, list) and s for s in sets):
        raise Refusal("KNOWLEDGE_ROWS_MISSING", "inputs.row_sets must hold at least one non-empty list of governed evidence rows")
    by_corpus: dict[str, list[dict[str, Any]]] = {}
    skipped = 0
    for rows in sets:
        for r in rows if isinstance(rows, list) else []:
            if not isinstance(r, dict) or r.get("kind", "chunk") != "chunk" or not r.get("id") or not str(r.get("text") or "").strip() or not r.get("corpus_id"):
                skipped += 1                    # graph facts / rows without text or corpus carry nothing the engine can cite
                continue
            by_corpus.setdefault(str(r["corpus_id"]), []).append(
                {"chunk_id": r["id"], "text": r["text"], "source": r.get("source"), "document_id": r.get("doc_id"),
                 "utility_role": r.get("utility_role"), "synthesis_role": r.get("synthesis_role"), "ca4_grade": r.get("ca4_grade"),
                 "c4_valid": r.get("c4_valid"), "origin": r.get("origin"), "query_ids": r.get("query_ids") or [],
                 "text_truncated": r.get("text_truncated"), "text_chars": r.get("text_chars"),
                 "provenance": {"relation_to_q0": r["relation_to_q0"]} if r.get("relation_to_q0") else {}})
    out, seen = [], set()
    for corpus, items in by_corpus.items():
        for row in cp.rows_from_packet({"evidence": items}, corpus):
            # ONE id space in governed mode: the adapter runtime's evidence id (what `context.evidence_refs` shows the agent and
            # what Polymath's citation check enforces). The standalone `polymath:chunk:` prefix is dropped at this boundary.
            row["id"] = row["id"].split("polymath:chunk:", 1)[-1]
            if row["id"] not in seen:
                seen.add(row["id"])
                out.append(row)
    if not out:
        raise Refusal("KNOWLEDGE_ROWS_UNUSABLE", f"none of the {skipped} governed rows carries a chunk id, text and corpus")
    return {"corpus_evidence": out, "row_count": len(out), "skipped": skipped, "corpora": sorted(by_corpus)}


def _op_lenses(req: dict[str, Any]) -> dict[str, Any]:
    """`executors.lens_gate`: the lenses whose keywords appear in the seed signal + corpus evidence (never lens-less)."""
    import executors
    import graph as graphmod

    ins = _inputs(req)
    signal = str(ins.get("signal") or "").strip()
    if not signal:
        raise Refusal("SIGNAL_MISSING", "inputs.signal must be the seed / niche signal text")
    state = _engine_state(signal=signal, corpus_evidence=_corpus_rows(ins.get("corpus_evidence")))
    note = executors.lens_gate(state, graphmod.load_policies())
    return {"lenses": state["data"]["lenses"], "note": note}


def _op_validate_primitives(req: dict[str, Any]) -> dict[str, Any]:
    """The lineage law on a primitives submission (`lived_world.validate_primitives`, the same function the controller's submit
    path calls): interpretation objects are schema-valid and cite only corpus rows that exist, are CLASSIFIED and are not
    IRRELEVANT. Invalid is an OUTPUT (the run can branch back to reasoning), not a refusal."""
    import graph as graphmod
    import lived_world

    ins = _inputs(req)
    prim = ins.get("primitives")
    if not isinstance(prim, dict):
        raise Refusal("PRIMITIVES_MISSING", "inputs.primitives must be the primitives object")
    state = _engine_state(corpus_evidence=_corpus_rows(ins.get("corpus_evidence")), row_relevance=ins.get("row_relevance"))
    errors = lived_world.validate_primitives(prim, state, graphmod.load_policies())
    out: dict[str, Any] = {"valid": not errors, "errors": errors}
    if not errors:
        lived_world.merge_relevance(state, prim.get("row_relevance") or {})
        out.update(row_relevance=state["data"]["row_relevance"], latent_structures=list(prim.get("latent_structures") or []),
                   corpus_observations=list(prim.get("corpus_observations") or []))
    return out


#: operation id -> wrapper. One table; an id not listed here is a typed refusal.
OPERATIONS: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {
    "knowledge.corpus_evidence": _op_corpus_evidence,
    "understanding.lenses": _op_lenses,
    "understanding.validate_primitives": _op_validate_primitives,
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
