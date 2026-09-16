"""ADAPTER STEP WORKER (COGNITIVE-ADAPTER-V1, ADR-0018, plan E2) — the durable executor of automatic adapter steps.

Loop: lease ONE running adapter run (FOR UPDATE SKIP LOCKED, lease renewed per step) → drive it with
`polymath_shared.adapter.service.advance` until it awaits the connected agent, reaches COMPILE_RESULT, hits a typed
gap, or the per-claim step budget is spent → release the lease. A crash mid-step leaves the lease to expire; the
next claim re-executes the ISSUED step idempotently (every step is a single committed unit).

Knowledge steps reach Polymath through the orchestrator's HTTP API (POLYMATH_ORCH_URL, default 127.0.0.1:7200) —
the same seam research/ uses; workers never import orchestrator code (architecture/dependencies.json).
EXTERNAL_OPERATION steps call TrailSignal's BOUNDED synchronous operations (ADR-0019 §8): registry.project, gaps.compile,
evidence.admit, hypotheses.judge, territory.project, opportunity.qualify, opportunity.score. HARNESS_ACTION steps are never
executed here — the host harness answers them through adapter_submit.

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
    if cfg.get("query_from") == "hypotheses":                 # generic engine state: the live hypotheses' statements
        stmts = [str(h.get("statement", "")).strip() for h in step.get("context", {}).get("hypotheses") or []]
        stmts = [x for x in stmts if x]
        if stmts:
            return "; ".join(stmts)[:2000]
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
    out: dict[str, Any] = {"ok": True, "checked": checked}
    if cfg.get("phi") == "deduplicate":
        # closed φ rule (ADR-0019 §3): identical normalised statements merge into the earliest-generated hypothesis (the context lists
        # live hypotheses in generation order, never hash order); later duplicates merge into it and the engine records the MERGE
        checked.append("phi:deduplicate")
        groups: dict[str, list[str]] = {}
        for h in step.get("context", {}).get("hypotheses") or []:
            key = " ".join(str(h.get("statement", "")).lower().split())
            groups.setdefault(key, []).append(h["hypothesis_id"])
        verdicts = [{"hypothesis_id": dup, "kind": "MERGE", "into_hypothesis_id": ids[0], "cause_refs": [{"kind": "hypothesis", "id": ids[0]}],
                     "reason_code": "DUPLICATE_STATEMENT"} for ids in groups.values() for dup in ids[1:]]
        if verdicts:
            out["hypothesis_verdicts"] = verdicts
    return {"output": out}


def exec_branch(step: dict[str, Any], state: RunState, m: Manifest) -> service.ExecOutcome:
    return {"output": {"evaluated": True}}          # the branch itself is resolved by transitions.next_step_id


# ─────────────────────────────────────────────────────────── TrailSignal bounded operations (ADR-0019 §8)
from polymath_shared.adapter import trail_client as TC  # noqa: E402  (shared typed client — never Trail internals)

_TRAIL: TC.TrailMCPClient | None = None


def trail() -> TC.TrailMCPClient:
    global _TRAIL
    if _TRAIL is None:
        _TRAIL = TC.TrailMCPClient.from_env()
    return _TRAIL


def _newest_output_with(state: RunState, key: str) -> dict[str, Any] | None:
    """The most recently accepted step output carrying `key` (acceptance order, not dict order — JSONB drops it)."""
    for sid in reversed(state.output_order or tuple(state.outputs)):
        out = state.outputs.get(sid)
        if isinstance(out, dict) and key in out:
            return out
    return None


def _ordered_outputs(state: RunState) -> list[dict[str, Any]]:
    """Step outputs in the run's authoritative ACCEPTANCE order. JSONB does not preserve dict order, so any selection that depends
    on order (chronological gap accumulation, market_delta-before-supply qualifications, `latest`/`[-N:]`) must read them this way,
    never `state.outputs.values()`."""
    return [state.outputs[sid] for sid in (state.output_order or tuple(state.outputs)) if isinstance(state.outputs.get(sid), dict)]


def _payload_for(kind: str, step: dict[str, Any], state: RunState, cfg: dict[str, Any]) -> dict[str, Any]:
    """The typed payload of a bounded Trail operation, assembled from generic engine state only (live hypotheses, admitted
    evidence ids, the latest research receipt, physical jobs, qualifications) — never from a source or harness name."""
    ctx = step.get("context") or {}
    hyps = list(ctx.get("hypotheses") or [])
    # admitted_evidence_ids is the COMPLETE set of Trail-admitted observation ids from every prior evidence.admit output, in
    # acceptance order and deduped — NEVER the display context, whose per-class budget caps how many refs an issued step carries
    # for citation. The qualify/score hard gates count independent groups over exactly these ids, so a display cap must not reach them.
    admitted: list[str] = []
    _seen_adm: set[str] = set()
    for _out in _ordered_outputs(state):
        for _a in (_out.get("evidence_admission") or {}).get("admitted") or []:
            _aid = _a.get("admitted_evidence_id")
            if _aid and _aid not in _seen_adm:
                _seen_adm.add(_aid)
                admitted.append(_aid)
    payload: dict[str, Any] = {"stage": cfg.get("stage"), "hypotheses": hyps, "admitted_evidence_ids": admitted}
    if kind == "registry.project":
        payload["max_priors_per_hypothesis"] = int(cfg.get("max_priors_per_hypothesis", 12))
    elif kind == "gaps.compile":
        gaps = []
        for out in _ordered_outputs(state):
            gaps += [g for g in (out.get("knowledge_gaps") or []) if isinstance(g, dict)]
        payload["knowledge_gaps"] = gaps[-100:]
        payload["open_gaps"] = list((_newest_output_with(state, "open_gaps") or {}).get("open_gaps") or [])[:100]
    elif kind == "evidence.admit":
        rec = _newest_output_with(state, "_harness_action_id")
        if not rec:
            raise ValueError("evidence.admit needs a harness receipt in a prior step output")
        payload["action_id"] = rec["_harness_action_id"]
        payload["receipt"] = {k: v for k, v in rec.items() if not k.startswith("_")}
    elif kind == "hypotheses.judge":
        payload["redundancy_groups"] = list((_newest_output_with(state, "redundancy_groups") or {}).get("redundancy_groups") or [])
        payload["latest_admission_id"] = ((_newest_output_with(state, "evidence_admission") or {}).get("evidence_admission") or {}).get("admission_id")
    elif kind == "territory.project":
        payload["physical_jobs"] = list((_newest_output_with(state, "physical_jobs") or {}).get("physical_jobs") or [])[:100]
    elif kind == "opportunity.qualify":
        payload["latest_admission_id"] = ((_newest_output_with(state, "evidence_admission") or {}).get("evidence_admission") or {}).get("admission_id")
    elif kind == "opportunity.score":
        payload["qualifications"] = [o["qualification"] for o in _ordered_outputs(state) if isinstance(o.get("qualification"), dict)]
    return payload


def exec_external(step: dict[str, Any], state: RunState, m: Manifest) -> service.ExecOutcome:
    """EXTERNAL_OPERATION = one bounded synchronous Trail operation through the public MCP boundary. The immutable result
    becomes the step output (registry snapshot + priors as `trail_prior` refs, research directives, admission projections,
    φ verdicts, qualifications, the score record) and an ExternalOperationReceiptV1 (TERMINAL at once). A planned Trail
    capability, a missing principal, or a refusal ends the run with a TYPED gap — never invention."""
    spec = m.step(step["step_id"])
    ext = spec.get("external") or {}
    kind = ext.get("operation_kind")
    if ext.get("availability") == "planned":
        return {"gap": {"code": "TRAIL_CAPABILITY_PLANNED",
                        "message": f"{kind} is not yet a TrailSignal production capability (graph node {ext.get('planned_node')})"}}
    if kind not in TC.BOUNDED_OPERATIONS:
        return {"gap": {"code": "TRAIL_OPERATION_UNSUPPORTED", "message": f"{kind}: not a bounded TrailSignal operation of this build"}}
    client = trail()
    if not client.configured:
        return {"gap": {"code": "TRAIL_PRINCIPAL_MISSING", "message": "no Trail principal token/secret configured for Polymath (owner action O1)"}}
    cfg = spec.get("config") or {}
    principal = os.environ.get("POLYMATH_TRAIL_PRINCIPAL", "polymath")
    key = TC.identifier(state.run_id, step["step_id"], str(step["sequence"]))
    snap = (step.get("context") or {}).get("registry_snapshot") or {}
    req = TC.bounded_request(kind, _payload_for(kind, step, state, cfg), key=key, run_ref=state.run_id, registry_snapshot_id=snap.get("snapshot_id"))
    try:
        resp = client.operate(kind, req)
    except TC.TrailToolError as exc:
        return {"gap": {"code": "TRAIL_REFUSED", "message": f"{kind}: {exc}"}}
    except (TC.TrailTransportError, TC.TrailProtocolError) as exc:
        raise RuntimeError(f"trail transport: {exc}") from exc              # typed STEP_EXECUTOR_ERROR (retryable by re-run)
    # Trail response identity: the answer must belong to the request we sent, checked BEFORE we relabel or persist anything.
    # A wrong operation_kind, a result computed against a different registry snapshot, or an admission echoing another run's
    # run_ref is a typed refusal, never silently relabelled onto this run. (Same-key/different-payload is refused server-side.)
    expected_run_ref = req["run_ref"]
    if resp.get("operation_kind") != kind:
        return {"gap": {"code": "TRAIL_RESPONSE_MISMATCH", "message": f"{kind}: Trail answered operation_kind {resp.get('operation_kind')!r}"}}
    if resp.get("operation_id") in (None, ""):
        return {"gap": {"code": "TRAIL_RESPONSE_MISMATCH", "message": f"{kind}: Trail answer carries no operation_id"}}
    _resp_snap = (resp.get("registry_snapshot") or {}).get("snapshot_id")
    if req.get("registry_snapshot_id") and _resp_snap and _resp_snap != req["registry_snapshot_id"]:
        return {"gap": {"code": "TRAIL_RESPONSE_MISMATCH", "message": f"{kind}: Trail answered against snapshot {_resp_snap!r}, not {req['registry_snapshot_id']!r}"}}
    result = dict(resp.get("result") or {})
    output: dict[str, Any] = {"trail_operation_id": resp.get("operation_id"), "operation_kind": kind}
    refs: list[dict[str, Any]] = []
    record_ids: list[str] = []
    if kind == "registry.project":
        snapshot = resp.get("registry_snapshot") or result.get("registry_snapshot")
        if not snapshot:
            return {"gap": {"code": "TRAIL_REFUSED", "message": "registry.project returned no registry snapshot"}}
        output["registry_snapshot"] = {"snapshot_id": str(snapshot["snapshot_id"]), "content_hash": str(snapshot["content_hash"])}
        priors = list(result.get("priors") or [])
        output["priors"] = priors
        refs = [{"kind": "trail_prior", "id": str(p["registry_record_id"]), "note": str(p.get("prior_role") or "")[:500] or None} for p in priors if p.get("registry_record_id")]
        for r in refs:
            if r["note"] is None:
                r.pop("note")
        record_ids = [r["id"] for r in refs]
    for k, v in result.items():
        # Trail's ResearchResultV1 envelope always carries every optional field; a given operation leaves the ones it does not
        # produce null. Skip the nulls so an operation's empty `research_directive`/`evidence_admission`/… never shadows a real
        # value an earlier step produced (the step context gathers the NEWEST occurrence of each key).
        if k in ("priors", "registry_snapshot") or v is None:
            continue
        if k == "verdicts":
            # Trail's φ verdict carries its own VerdictKind (REJECT, CHALLENGE, DEDUPLICATE, REQUIRE_EVIDENCE, …) plus the
            # `polymath_transition` it maps to (KILL, CONTRADICT, MERGE, …, or null). Polymath's transition engine speaks the
            # transition vocabulary, so translate: a null transition (REQUIRE_EVIDENCE = keep gathering) is not a state change.
            def _translate(verdict: dict[str, Any]) -> dict[str, Any] | None:
                # `polymath_transition` present (real Trail) is authoritative: its value is the transition, null = no state change
                # (REQUIRE_EVIDENCE, keep gathering). A verdict without the key already speaks Polymath's transition vocabulary in `kind`.
                transition = verdict["polymath_transition"] if "polymath_transition" in verdict else verdict.get("kind")
                if not transition:
                    return None
                return {kk: vv for kk, vv in {**verdict, "kind": transition}.items() if kk != "polymath_transition"}
            output["hypothesis_verdicts"] = [w for verdict in v if isinstance(verdict, dict) for w in (_translate(verdict),) if w]
            continue
        output[k] = v
    adm = output.get("evidence_admission")
    if isinstance(adm, dict):
        # Validate the admission's echoed run identity corresponds to THIS run's wire run_ref before relabelling it to Polymath's
        # own run id (contracts/adapter/v1/evidence_admission uses `adr_…`; the Trail operation id stays the cross-system link).
        if adm.get("run_id") not in (None, "", expected_run_ref):
            return {"gap": {"code": "TRAIL_RESPONSE_MISMATCH", "message": f"evidence.admit: admission run_id {adm.get('run_id')!r} does not correspond to {expected_run_ref!r}"}}
        adm = {**adm, "run_id": state.run_id}; output["evidence_admission"] = adm
        record_ids += [a.get("trail_admission_record_id") for a in adm.get("admitted") or [] if a.get("trail_admission_record_id")]
    ts = output.get("trail_score")
    if isinstance(ts, dict) and ts.get("record_id"):
        output["trail_score_record_ids"] = [str(ts["record_id"])]
        record_ids.append(str(ts["record_id"]))
    rc = TC.bounded_receipt(state.run_id, step["step_id"], kind, resp, idempotency_key=req["idempotency_key"], principal=principal, record_ids=record_ids)
    return {"output": output, "external": rc, "evidence_refs": refs}


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
