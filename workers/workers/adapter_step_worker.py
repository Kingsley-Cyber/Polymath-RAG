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
from polymath_shared.execution import heartbeat, register_worker, worker_identity
from polymath_shared.logging import configure_logging

ORCH = os.environ.get("POLYMATH_ORCH_URL", "http://127.0.0.1:7200")
HTTP_TIMEOUT_S = float(os.environ.get("POLYMATH_ADAPTER_HTTP_TIMEOUT_S", "120"))
log = logging.getLogger("worker-adapter-step")
WORKER_TYPE = "adapter_step"          # == the supervisor slot name


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
    for k in ("question", "seed", "seed_idea", "query", "signal", "topic", "problem"):
        v = state.input.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
    for v in state.input.values():                      # last resort: the first non-empty string field of the domain input
        if isinstance(v, str) and v.strip():
            return v.strip()
    raise ValueError("no query text in input (set config.source on the step, e.g. input.seed_idea)")


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


def _present(node: Any, path: str) -> bool:
    """Closed presence check over accepted outputs: `a.b`, and `list[].field` meaning EVERY element has a non-empty field."""
    head, _, rest = path.partition(".")
    if head.endswith("[]"):
        seq = node.get(head[:-2]) if isinstance(node, dict) else None
        return isinstance(seq, list) and bool(seq) and all(_present(x, rest) if rest else bool(x) for x in seq)
    if not isinstance(node, dict) or head not in node:
        return False
    val = node[head]
    return _present(val, rest) if rest else (val not in (None, "", [], {}))


def exec_validate(step: dict[str, Any], state: RunState, m: Manifest) -> service.ExecOutcome:
    """VALIDATE is closed and schema-free: corpus-scope presence and `require` paths over the accepted outputs
    (`theses[].counterargument`, `article.citation_ids`, …). A failed requirement is a typed gap, never a guess."""
    cfg = m.step(step["step_id"]).get("config") or {}
    checked = ["input_schema"]
    if cfg.get("require_corpus"):
        checked.append("corpus_scope")
        if not _corpus_ids(state):
            return {"gap": {"code": "INPUT_SCOPE_MISSING", "message": "adapter requires corpus_ids"}}
    missing = []
    for req in cfg.get("require") or []:
        checked.append(req)
        if not any(_present(out or {}, req) for out in state.outputs.values()):
            missing.append(req)
    if missing:
        return {"gap": {"code": "VALIDATION_FAILED", "message": "required outputs missing: " + ", ".join(missing)}}
    return {"output": {"ok": True, "checked": checked}}


def exec_branch(step: dict[str, Any], state: RunState, m: Manifest) -> service.ExecOutcome:
    return {"output": {"evaluated": True}}          # the branch itself is resolved by transitions.next_step_id


# ─────────────────────────────────────────────────────────── TrailSignal (E4)
from polymath_shared.adapter import trail_client as TC  # noqa: E402  (shared typed client — never Trail internals)

_TRAIL: TC.TrailMCPClient | None = None


def trail() -> TC.TrailMCPClient:
    global _TRAIL
    if _TRAIL is None:
        _TRAIL = TC.TrailMCPClient.from_env()
    return _TRAIL


def _hypothesis_queries(state: RunState, m: Manifest, fallback: str) -> list[str]:
    """Discovery queries: the agent's hypotheses (activity + friction / direction), else the seed."""
    out: list[str] = []
    for sid, o in state.outputs.items():
        for h in (o or {}).get("hypotheses") or []:
            q = " ".join(str(h.get(k) or "") for k in ("activity", "friction", "direction")).strip()
            if q:
                out.append(q)
    return out or [fallback]


def _leads_from_prior(state: RunState) -> list[dict[str, Any]]:
    for sid in reversed(list(state.outputs)):
        leads = (state.outputs[sid] or {}).get("leads")
        if leads:
            return leads
    return []


def _poll_receipt(client: TC.TrailMCPClient, receipt: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    ref = {"operation_id": receipt["operation_id"], "operation_kind": receipt["operation_kind"],
           "temporal_workflow_id": receipt.get("temporal_workflow_id"), "temporal_run_id": receipt.get("temporal_run_id"),
           "submitted_at": receipt["submitted_at"]}
    status = client.status(ref)
    return status, TC.receipt_after_poll(receipt, status)


def exec_external(step: dict[str, Any], state: RunState, m: Manifest) -> service.ExecOutcome:
    """EXTERNAL_OPERATION through Trail's public boundary. Two-phase: submit once (receipt persisted, `pending`), then each
    re-execution polls by operation_id; a TERMINAL status pages the referenced outputs into the step output. A planned
    Trail capability, a missing principal, or a refused operation all end the run with a TYPED gap — never invention."""
    spec = m.step(step["step_id"])
    ext = spec.get("external") or {}
    kind = ext.get("operation_kind")
    if ext.get("availability") == "planned":
        return {"gap": {"code": "TRAIL_CAPABILITY_PLANNED",
                        "message": f"{kind} is not yet a TrailSignal production capability (graph node {ext.get('planned_node')})"}}
    client = trail()
    if not client.configured:
        return {"gap": {"code": "TRAIL_PRINCIPAL_MISSING", "message": "no Trail principal token/secret configured for Polymath (owner action O1)"}}
    cfg = spec.get("config") or {}
    principal = os.environ.get("POLYMATH_TRAIL_PRINCIPAL", "polymath")
    key_base = TC.identifier(state.run_id, step["step_id"], str(step["sequence"]))
    receipt = step.get("_external_receipt")
    partial = dict(step.get("_partial_output") or {})
    try:
        if kind == "discover.submit":
            return _exec_discover(client, step, state, m, cfg, principal, key_base, receipt)
        if kind == "scrape.submit+extract.submit":
            return _exec_acquire_extract(client, step, state, m, cfg, principal, key_base, receipt, partial)
        return {"gap": {"code": "TRAIL_OPERATION_UNSUPPORTED", "message": f"{kind}: no connector path in this build"}}
    except TC.TrailToolError as exc:
        return {"gap": {"code": "TRAIL_REFUSED", "message": f"{kind}: {exc}"}, "external": receipt}
    except (TC.TrailTransportError, TC.TrailProtocolError) as exc:
        raise RuntimeError(f"trail transport: {exc}") from exc              # typed STEP_EXECUTOR_ERROR (retryable by re-run)


def _exec_discover(client, step, state, m, cfg, principal, key_base, receipt):
    if receipt is None:
        query = _hypothesis_queries(state, m, _query_text(step, state, m))[0]
        req = TC.discovery_request(query, key=key_base, maximum_candidates=int(cfg.get("maximum_candidates", 16)),
                                   language=str(cfg.get("language", "en")))
        ref = client.submit("discover.submit", req)
        rc = TC.receipt_from_ref(state.run_id, step["step_id"], ref, idempotency_key=req["idempotency_key"], principal=principal)
        return {"pending": True, "external": rc, "output": {"query": query}}
    status, rc = _poll_receipt(client, receipt)
    if rc["phase"] != "TERMINAL":
        return {"pending": True, "external": rc}
    if rc["outcome"] in ("FAILED", "CANCELLED"):
        return {"gap": {"code": f"TRAIL_DISCOVERY_{rc['outcome']}", "message": (rc.get("failure") or {}).get("message") or rc["outcome"]}, "external": rc}
    leads = []
    for rid in TC.outputs_of(status, "URL_CANDIDATE_RESULT"):
        for c in client.page_all("URL_CANDIDATE_RESULT", rid, key=key_base, page_size=min(64, int(cfg.get("maximum_candidates", 16)))):
            leads.append({"candidate_id": c.get("candidate_id"), "rank": c.get("rank"), "url": c.get("url"), "title": (c.get("title") or "")[:300],
                          "snippet": (c.get("snippet") or "")[:500], "record_class": c.get("record_class", "OPERATIONAL_LEAD"), "evidence_eligible": False})
    rc = TC.receipt_after_poll(rc, status, record_ids=[l["candidate_id"] for l in leads if l.get("candidate_id")])
    rc["poll_count"] -= 1                                                    # the fold above already counted this poll
    return {"output": {"leads": leads, "outcome": rc["outcome"]}, "external": rc, "evidence_refs": []}


def _exec_acquire_extract(client, step, state, m, cfg, principal, key_base, receipt, partial):
    """Composite: ONE batch scrape (the receipt), then bounded sequential extractions, each a Trail operation tracked in
    the step's partial output; terminal when every planned extraction is paged."""
    phase = partial.get("phase") or "batch"
    if phase == "batch":
        if receipt is None:
            urls = [l["url"] for l in _leads_from_prior(state) if l.get("url")][: int(cfg.get("batch_max", 16))]
            if not urls:
                return {"gap": {"code": "TRAIL_NO_LEADS", "message": "discovery returned no leads to acquire"}}
            req = TC.batch_request(urls, key=key_base)
            ref = client.submit("scrape.submit", req)
            rc = TC.receipt_from_ref(state.run_id, step["step_id"], ref, idempotency_key=req["idempotency_key"], principal=principal)
            return {"pending": True, "external": rc, "output": {"phase": "batch", "urls": urls}}
        status, rc = _poll_receipt(client, receipt)
        if rc["phase"] != "TERMINAL":
            return {"pending": True, "external": rc, "output": partial}
        if rc["outcome"] in ("FAILED", "CANCELLED"):
            return {"gap": {"code": f"TRAIL_ACQUISITION_{rc['outcome']}", "message": (rc.get("failure") or {}).get("message") or rc["outcome"]}, "external": rc}
        artifacts = TC.outputs_of(status, "RAW_ARTIFACT")[: int(cfg.get("extract_max", 6))]
        partial = {**partial, "phase": "extract", "artifacts": artifacts, "extractions": {}, "records": [], "batch_outcome": rc["outcome"]}
        if not artifacts:
            return {"output": {**partial, "phase": "done"}, "external": rc, "evidence_refs": []}
        return {"pending": True, "external": rc, "output": partial}
    # phase == extract: one extraction operation at a time, tracked in partial["extractions"][artifact_id]
    extractions = dict(partial.get("extractions") or {})
    todo = [a for a in partial.get("artifacts") or [] if extractions.get(a, {}).get("state") != "done"]
    if not todo:
        records = partial.get("records") or []
        refs = [{"kind": "trail_record", "id": r["record_id"]} for r in records if r.get("record_id")]
        rc = TC.receipt_after_poll(receipt, {"phase": "TERMINAL", "terminal_outcome": partial.get("batch_outcome"), "revision": receipt.get("status_revision", 0)},
                                   record_ids=[r["record_id"] for r in records if r.get("record_id")])
        sub_ops = [{"external_system": "trailsignal", "operation_kind": "extract.submit", "operation_id": ex.get("operation_id"),
                    "record_ids": [r["record_id"] for r in records if r.get("artifact_id") == art and r.get("record_id")]}
                   for art, ex in (partial.get("extractions") or {}).items() if ex.get("operation_id")]
        return {"output": {**partial, "phase": "done", "_external_operations": sub_ops}, "external": rc, "evidence_refs": refs}
    art = todo[0]
    ex = dict(extractions.get(art) or {})
    if not ex.get("ref"):
        req = TC.extraction_request(art, key=TC.identifier(key_base, "x", art), maximum_records=int(cfg.get("records_max_per_artifact", 24)))
        ex = {"state": "submitted", "ref": client.submit("extract.submit", req), "idempotency_key": req["idempotency_key"]}
        extractions[art] = ex
        return {"pending": True, "external": receipt, "output": {**partial, "extractions": extractions}}
    status = client.status(ex["ref"])
    if status.get("phase") != "TERMINAL":
        return {"pending": True, "external": receipt, "output": {**partial, "extractions": extractions}}
    records = list(partial.get("records") or [])
    if status.get("terminal_outcome") in ("SUCCEEDED", "PARTIAL"):
        for res_id in TC.outputs_of(status, "DOCUMENT_RESULT"):
            for r in client.page_all("DOCUMENT_RESULT", res_id, key=TC.identifier(key_base, "p", art), page_size=64, max_pages=2):
                records.append({"record_id": r.get("record_id"), "artifact_id": art, "result_id": res_id, "ordinal": r.get("ordinal"),
                                "record_kind": r.get("record_kind"), "text": (r.get("text") or "")[:700]})
    ex["state"] = "done"; ex["outcome"] = status.get("terminal_outcome"); ex["operation_id"] = ex["ref"]["operation_id"]
    extractions[art] = ex
    return {"pending": True, "external": receipt, "output": {**partial, "extractions": extractions, "records": records}}


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
                before_state = service.store.load_run(conn, run_id)[0]
                before_row = service.store.current_step(conn, run_id)
                state = service.advance(conn, run_id, EXECUTORS, max_steps=1)
                after_row = service.store.current_step(conn, run_id)
            progressed = state.terminal or state.sequence != before_state.sequence or \
                (after_row or {}).get("status") != (before_row or {}).get("status")
            steps_done += 1 if progressed else 0
            log.info("run %s -> %s step=%s (%s)%s", run_id[:16], state.status, state.current_step_id, state.sequence,
                     "" if progressed else " [external pending]")
            if crash_after is not None and steps_done >= crash_after:
                log.error("CRASH-AFTER %s reached: exiting without releasing the lease (test hook)", crash_after)
                os._exit(137)
            if not progressed:
                return run_id                             # a pending external operation: release, poll again later
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
    # SUPERVISED SLOT (process_supervisor `adapter_step`): register + heartbeat like every fleet worker so the supervisor's
    # health gate (a FRESH registration for worker_type == slot name) and the fence/quarantine paths see this process.
    identity = worker_identity(WORKER_TYPE)
    with tx() as conn:
        register_worker(conn, identity)
    log.info("registered %s (bundle %s)", identity["worker_id"], identity.get("execution_bundle_id"))
    while True:
        worked = process_one(args.owner, args.lease_s, max_steps=args.max_steps, crash_after=args.crash_after)
        with tx() as conn:
            heartbeat(conn, identity["worker_id"], processed_count=1 if worked else None)
        if worked is None:
            if args.once:
                return 0
            time.sleep(args.poll_s)
        elif args.once and args.max_steps is not None:
            return 0


if __name__ == "__main__":
    sys.exit(main())
