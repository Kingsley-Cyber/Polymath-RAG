"""ADAPTER STEP WORKER (COGNITIVE-ADAPTER-V1, ADR-0018, plan E2) — the durable executor of automatic adapter steps.

Loop: lease ONE running adapter run (FOR UPDATE SKIP LOCKED, lease renewed per step) → drive it with
`polymath_shared.adapter.service.advance` until it awaits the connected agent, reaches COMPILE_RESULT, hits a typed
gap, or the per-claim step budget is spent → release the lease. A crash mid-step leaves the lease to expire; the
next claim re-executes the ISSUED step idempotently (every step is a single committed unit).

Knowledge steps reach Polymath through the orchestrator's HTTP API (POLYMATH_ORCH_URL, default 127.0.0.1:7200) —
the same seam research/ uses; workers never import orchestrator code (architecture/dependencies.json).
EXTERNAL_OPERATION steps are typed gaps until the Trail connector (E4) lands.

    python -m workers.adapter_step_worker [--once] [--max-steps N] [--lease-s S] [--poll-s P] [--owner NAME] [--crash-after N]
"""
from __future__ import annotations

import argparse
import logging
import os
import socket
import sys
import time
from typing import Any

import httpx

from polymath_shared.adapter import service
from polymath_shared.adapter.manifest import Manifest
from polymath_shared.adapter.transitions import RunState
from polymath_shared.db import tx
from polymath_shared.logging import configure_logging

ORCH = os.environ.get("POLYMATH_ORCH_URL", "http://127.0.0.1:7200")
HTTP_TIMEOUT_S = float(os.environ.get("POLYMATH_ADAPTER_HTTP_TIMEOUT_S", "120"))
log = logging.getLogger("worker-adapter-step")


# ─────────────────────────────────────────────────────────── executors
def _path(obj: dict[str, Any], dotted: str, default: Any = None) -> Any:
    cur: Any = obj
    for part in dotted.split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            return default
    return cur


def _query_text(step: dict[str, Any], state: RunState, m: Manifest) -> str:
    cfg = m.step(step["step_id"]).get("config") or {}
    src = cfg.get("source")
    if src:
        v = _path({"input": state.input, "options": state.options}, src)
        if isinstance(v, str) and v.strip():
            return v.strip()
    for k in ("question", "seed", "query", "signal"):
        v = state.input.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
    raise ValueError("no query text in input (expected question/seed/query)")


def _corpus_ids(state: RunState) -> list[str]:
    ids = state.input.get("corpus_ids") or state.options.get("corpus_ids") or []
    return [c for c in ids if isinstance(c, str) and c.strip()]


def _refs_from_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Evidence refs from contract rows (retrieve-evidence-rows-v1: id/kind/doc_id/corpus_id/score)."""
    refs = []
    for r in rows or []:
        rid, kind = r.get("id"), r.get("kind")
        if not rid or kind not in ("chunk", "document", "graph_fact", "graph_hop"):
            continue
        ref = {"kind": kind, "id": str(rid)}
        for k in ("corpus_id", "doc_id"):
            if r.get(k):
                ref[k] = str(r[k])
        if isinstance(r.get("score"), (int, float)):
            ref["score"] = float(r["score"])
        refs.append(ref)
    return refs


def _rows_from_hits(hits: list[dict[str, Any]], corpus_ids: list[str]) -> list[dict[str, Any]]:
    """The HYBRID/FAST/GRAPH lanes answer with `evidence` hits (chunk_id, doc_id, text, title, fused_score) rather
    than contract rows; normalise them to the row shape so every lane yields re-resolvable chunk ids."""
    rows = []
    for h in hits or []:
        cid = h.get("chunk_id")
        if not cid:
            continue
        rows.append({"id": str(cid), "kind": "chunk", "doc_id": h.get("doc_id"), "corpus_id": corpus_ids[0] if len(corpus_ids) == 1 else None,
                     "title": h.get("title") or h.get("source_name"), "source": h.get("human_locator") or h.get("source_name"),
                     "text": h.get("text"), "score": h.get("fused_score") if isinstance(h.get("fused_score"), (int, float)) else h.get("rerank_score"),
                     "heading_path": h.get("heading_path")})
    return rows


def _rows(out: dict[str, Any], corpus_ids: list[str]) -> list[dict[str, Any]]:
    return out.get("evidence_rows") or _rows_from_hits(out.get("evidence") or out.get("hits") or [], corpus_ids)


def _trim_rows(rows: list[dict[str, Any]], max_text: int = 700) -> list[dict[str, Any]]:
    out = []
    for r in rows or []:
        out.append({k: (v[:max_text] if isinstance(v, str) and k in ("text", "text_clean", "summary") else v)
                    for k, v in r.items() if k in ("id", "kind", "doc_id", "corpus_id", "title", "source", "text", "text_clean", "score", "lanes", "heading_path")})
    return out


def _orch_post(path: str, body: dict[str, Any]) -> dict[str, Any]:
    with httpx.Client(timeout=HTTP_TIMEOUT_S) as c:
        r = c.post(f"{ORCH}{path}", json=body)
    if r.status_code >= 400:
        raise RuntimeError(f"orchestrator {path} -> {r.status_code}: {r.text[:300]}")
    return r.json()


def exec_retrieve(step: dict[str, Any], state: RunState, m: Manifest) -> service.ExecOutcome:
    cfg = m.step(step["step_id"]).get("config") or {}
    corpus_ids = _corpus_ids(state)
    if not corpus_ids:
        return {"gap": {"code": "INPUT_SCOPE_MISSING", "message": "no corpus_ids in input or request_options"}}
    mode = cfg.get("mode", "EXPLORE")
    body = {"query": _query_text(step, state, m), "corpus_ids": corpus_ids, "limit": int(cfg.get("top_k", state.input.get("top_k") or 16))}
    if mode == "EXPLORE":
        body["explore"] = True                 # contract rows (retrieve-evidence-rows-v1): the view an agent consumes
    else:
        body["mode"] = mode                    # FAST/HYBRID/GRAPH answer with hits; normalised below
    out = _orch_post("/retrieve", body)
    rows = _rows(out, corpus_ids)
    return {"output": {"query": body["query"], "mode": mode, "corpus_ids": corpus_ids, "rows": _trim_rows(rows),
                       "evidence_contract": out.get("evidence_contract")}, "evidence_refs": _refs_from_rows(rows)}


def exec_compile_plan(step: dict[str, Any], state: RunState, m: Manifest) -> service.ExecOutcome:
    corpus_ids = _corpus_ids(state)
    if not corpus_ids:
        return {"gap": {"code": "INPUT_SCOPE_MISSING", "message": "no corpus_ids in input or request_options"}}
    out = _orch_post("/retrieve/plan", {"signal": _query_text(step, state, m), "corpus_ids": corpus_ids, "limit": 24, "explore": True})
    rows = out.get("evidence_rows") or out.get("rows") or _rows(out, corpus_ids)
    return {"output": {"queries": out.get("queries") or out.get("plan") or [], "rows": _trim_rows(rows)}, "evidence_refs": _refs_from_rows(rows)}


def exec_graph_expand(step: dict[str, Any], state: RunState, m: Manifest) -> service.ExecOutcome:
    corpus_ids = _corpus_ids(state)
    if not corpus_ids:
        return {"gap": {"code": "INPUT_SCOPE_MISSING", "message": "no corpus_ids in input or request_options"}}
    cfg = m.step(step["step_id"]).get("config") or {}
    out = _orch_post("/retrieve", {"query": _query_text(step, state, m), "corpus_ids": corpus_ids, "explore": True,
                                   "limit": int(cfg.get("max_facts", 20))})
    rows = [r for r in (out.get("evidence_rows") or []) if r.get("kind") in ("graph_fact", "graph_hop")]
    return {"output": {"graph_rows": _trim_rows(rows), "graph_facts": len(out.get("graph_facts") or [])}, "evidence_refs": _refs_from_rows(rows)}


def exec_validate(step: dict[str, Any], state: RunState, m: Manifest) -> service.ExecOutcome:
    cfg = m.step(step["step_id"]).get("config") or {}
    if cfg.get("require_corpus") and not _corpus_ids(state):
        return {"gap": {"code": "INPUT_SCOPE_MISSING", "message": "adapter requires corpus_ids"}}
    return {"output": {"ok": True, "checked": ["input_schema"] + (["corpus_scope"] if cfg.get("require_corpus") else [])}}


def exec_branch(step: dict[str, Any], state: RunState, m: Manifest) -> service.ExecOutcome:
    return {"output": {"evaluated": True}}          # the branch itself is resolved by transitions.next_step_id


def exec_external(step: dict[str, Any], state: RunState, m: Manifest) -> service.ExecOutcome:
    ext = m.step(step["step_id"]).get("external") or {}
    if ext.get("availability") == "planned":
        return {"gap": {"code": "TRAIL_CAPABILITY_PLANNED",
                        "message": f"{ext.get('operation_kind')} is not yet a TrailSignal production capability (graph node {ext.get('planned_node')})"}}
    return {"gap": {"code": "TRAIL_CONNECTOR_PENDING",
                    "message": f"{ext.get('operation_kind')}: the Polymath→TrailSignal connector (plan E4) is not wired in this build"}}


EXECUTORS: dict[str, service.Executor] = {
    "POLYMATH_RETRIEVE": exec_retrieve, "POLYMATH_COMPILE_PLAN": exec_compile_plan, "POLYMATH_GRAPH_EXPAND": exec_graph_expand,
    "VALIDATE": exec_validate, "BRANCH": exec_branch, "EXTERNAL_OPERATION": exec_external,
}


# ─────────────────────────────────────────────────────────── loop
def process_one(owner: str, lease_s: int, *, max_steps: int | None = None, crash_after: int | None = None) -> str | None:
    """Claim + drive one run. Returns the run_id worked on (None = nothing claimable)."""
    with tx() as conn:
        run_id = service.store.claim_run(conn, owner, lease_s)
    if not run_id:
        return None
    steps_done = 0
    try:
        while True:
            with tx() as conn:
                if not service.store.renew_lease(conn, run_id, owner, lease_s):
                    log.warning("lease lost on %s; stopping", run_id)
                    return run_id
                before = service.store.load_run(conn, run_id)[0].sequence
                state = service.advance(conn, run_id, EXECUTORS, max_steps=1)
                after = state.sequence
            steps_done += 1 if after != before or state.terminal else 0
            log.info("run %s -> %s step=%s (%s)", run_id[:16], state.status, state.current_step_id, state.sequence)
            if crash_after is not None and steps_done >= crash_after:
                log.error("CRASH-AFTER %s reached: exiting without releasing the lease (test hook)", crash_after)
                os._exit(137)
            if state.status != "running" or (max_steps is not None and steps_done >= max_steps):
                return run_id
    finally:
        with tx() as conn:
            service.store.release_lease(conn, run_id, owner)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", action="store_true", help="drain claimable runs once, then exit")
    ap.add_argument("--max-steps", type=int, default=None, help="steps per claim before releasing (default: until the run waits/ends)")
    ap.add_argument("--lease-s", type=int, default=int(os.environ.get("POLYMATH_ADAPTER_LEASE_S", "120")))
    ap.add_argument("--poll-s", type=float, default=2.0)
    ap.add_argument("--owner", default=f"adapter-step@{socket.gethostname()}:{os.getpid()}")
    ap.add_argument("--crash-after", type=int, default=None, help="TEST HOOK: os._exit after N steps without releasing the lease")
    args = ap.parse_args(argv)
    configure_logging("worker-adapter-step")
    while True:
        worked = process_one(args.owner, args.lease_s, max_steps=args.max_steps, crash_after=args.crash_after)
        if worked is None:
            if args.once:
                return 0
            time.sleep(args.poll_s)
        elif args.once and args.max_steps is not None:
            return 0


if __name__ == "__main__":
    sys.exit(main())
