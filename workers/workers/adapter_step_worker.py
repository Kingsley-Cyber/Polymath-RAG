"""ADAPTER STEP WORKER (COGNITIVE-ADAPTER-V1, ADR-0018, plan E2) — the durable executor of automatic adapter steps.

Loop: lease ONE running adapter run (FOR UPDATE SKIP LOCKED, lease renewed per step) → drive it with
`polymath_shared.adapter.service.advance` until it awaits the connected agent, reaches COMPILE_RESULT, hits a typed
gap, or the per-claim step budget is spent → release the lease. A crash mid-step leaves the lease to expire; the
next claim re-executes the ISSUED step idempotently (every step is a single committed unit).

Knowledge steps reach Polymath through the orchestrator's HTTP API (POLYMATH_ORCH_URL, default 127.0.0.1:7200) —
the same seam research/ uses; workers never import orchestrator code (architecture/dependencies.json). The outbound
surface is an ALLOW-LIST owned by polymath_shared.adapter.evidence_boundary: the legacy retrieve lane, the plan lane, and
(GOVERNED-CONVERGENCE-V1 TG2b, opt-in per manifest step via `config.surface: evidence_boundary`) the evidence route, which
returns an EvidencePacket with NO synthesis. This worker never reaches a Polymath synthesis route.
EXTERNAL_OPERATION steps call TrailSignal's BOUNDED synchronous operations (ADR-0019 §8): registry.project, gaps.compile,
evidence.admit, hypotheses.judge, territory.project, opportunity.qualify, opportunity.score. HARNESS_ACTION steps are never
executed here — the host harness answers them through adapter_submit.

    python -m workers.adapter_step_worker [--once] [--max-steps N] [--lease-s S] [--poll-s P] [--owner NAME] [--crash-after N]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import pathlib
import re
import socket
import subprocess
import sys
import time
from typing import Any

import httpx

from polymath_shared.adapter import evidence_boundary as EB, service
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


class OrchUnavailable(RuntimeError):
    """The orchestrator could not be reached or failed server-side (transport error, timeout, 5xx)."""


class OrchRejected(RuntimeError):
    """The orchestrator refused the request (4xx): a caller defect, never an availability problem — so never a fallback."""


def _ua(step: dict[str, Any], state: RunState) -> str:
    return EB.user_agent(state.run_id, step["step_id"], step["sequence"])


def _orch_post(path: str, body: dict[str, Any], *, user_agent: str | None = None) -> dict[str, Any]:
    """POST to the orchestrator — ONLY to a path on the evidence-boundary allow-list. The User-Agent names run/step/sequence so
    every call's query receipt is attributable to the adapter step that made it."""
    EB.assert_allowed_path(path)
    try:
        with httpx.Client(timeout=HTTP_TIMEOUT_S) as c:
            r = c.post(f"{ORCH}{path}", json=body, headers=({"User-Agent": user_agent} if user_agent else None))
    except httpx.HTTPError as exc:
        raise OrchUnavailable(f"orchestrator {path} unreachable: {type(exc).__name__}: {exc}"[:400]) from exc
    if r.status_code >= 500:
        raise OrchUnavailable(f"orchestrator {path} -> {r.status_code}: {r.text[:300]}")
    if r.status_code >= 400:
        raise OrchRejected(f"orchestrator {path} -> {r.status_code}: {r.text[:300]}")
    return r.json()


def _legacy_mode(cfg: dict[str, Any]) -> str:
    """A step that opted into the evidence boundary keeps its pre-boundary retrieve mode under `legacy_mode`, so the kill switch
    and the unavailable-fallback reproduce the legacy lane exactly (`mode` then means the BOUNDARY mode)."""
    return str(cfg.get("legacy_mode", "EXPLORE") if cfg.get("surface") == EB.SURFACE_BOUNDARY else cfg.get("mode", "EXPLORE"))


def _with_degraded(outcome: service.ExecOutcome, reasons: list[str]) -> service.ExecOutcome:
    if reasons and isinstance(outcome.get("output"), dict):
        outcome["output"]["degraded"] = True
        outcome["output"]["degraded_reasons"] = list(outcome["output"].get("degraded_reasons") or []) + list(reasons)
    return outcome


def _retrieve_legacy(step: dict[str, Any], state: RunState, m: Manifest, corpus_ids: list[str]) -> service.ExecOutcome:
    cfg = m.step(step["step_id"]).get("config") or {}
    mode = _legacy_mode(cfg)
    body = {"query": _query_text(step, state, m), "corpus_ids": corpus_ids, "limit": int(cfg.get("top_k", state.input.get("top_k") or 16))}
    if mode == "EXPLORE":
        body["explore"] = True                 # contract rows (retrieve-evidence-rows-v1): the view an agent consumes
    else:
        body["mode"] = mode                    # FAST/HYBRID/GRAPH answer with hits; normalised below
    out = _orch_post("/retrieve", body, user_agent=_ua(step, state))
    rows = _rows(out, corpus_ids)
    return {"output": {"surface": EB.SURFACE_LEGACY, "query": body["query"], "mode": mode, "corpus_ids": corpus_ids, "rows": _trim_rows(rows),
                       "evidence_contract": out.get("evidence_contract")}, "evidence_refs": _refs_from_rows(rows)}


def exec_retrieve(step: dict[str, Any], state: RunState, m: Manifest) -> service.ExecOutcome:
    cfg = m.step(step["step_id"]).get("config") or {}
    corpus_ids = _corpus_ids(state)
    if not corpus_ids:
        return {"gap": {"code": "INPUT_SCOPE_MISSING", "message": "no corpus_ids in input or request_options"}}
    surface, forced = EB.resolve_surface(cfg, os.environ)
    if surface == EB.SURFACE_BOUNDARY:
        return exec_evidence(step, state, m, corpus_ids, legacy=_retrieve_legacy)
    return _with_degraded(_retrieve_legacy(step, state, m, corpus_ids), forced)


def exec_evidence(step: dict[str, Any], state: RunState, m: Manifest, corpus_ids: list[str], *, legacy,
                  union_legacy: bool = False) -> service.ExecOutcome:
    """The evidence-boundary surface (GOVERNED-CONVERGENCE-V1 TG2b). The ORIGINAL need — the run's seed, or one need per live
    hypothesis — goes to the evidence route, ONE corpus per call, bounded; Polymath plans, explores and grades, and returns an
    EvidencePacket with no synthesis. The rules live in the pure module; this function only performs the calls:
      * a packet that fails the contract is a TERMINAL gap (EVIDENCE_CONTRACT_MISMATCH) — never a fallback, never partial use;
      * an unreachable surface falls back to the legacy lane when `config.fallback == "retrieve"` (recorded `degraded`), else
        follows `config.on_unavailable` (gap | continue);
      * empty evidence is a SUCCESS (`retrieval_completed: true`) — the corpus not supporting a need is a finding.
    `union_legacy` (graph steps): the packet carries chunks, not graph facts, so the legacy graph rows are unioned in."""
    sid = step["step_id"]
    cfg = m.step(sid).get("config") or {}
    needs = EB.original_needs(cfg, state.input, state.options, (step.get("context") or {}).get("hypotheses"))
    plan = EB.plan_calls(needs, corpus_ids, max_calls=int(cfg.get("max_calls", EB.DEFAULT_MAX_CALLS)))
    mode, explorer = str(cfg.get("mode") or "WILDCARD").upper(), bool(cfg.get("corpus_explorer", True))
    calls: list[dict[str, Any]] = []
    row_lists: list[list[dict[str, Any]]] = []
    failures: list[dict[str, Any]] = []
    for call in plan["calls"]:
        try:
            resp = _orch_post(EB.EVIDENCE_PATH, EB.request_body(call["need"], call["corpus_id"], mode=mode, corpus_explorer=explorer),
                              user_agent=_ua(step, state))
        except OrchUnavailable as exc:
            failures.append({"need_index": call["need_index"], "corpus_id": call["corpus_id"], "error": str(exc)[:300]})
            continue
        errs = EB.check_response(resp)
        if errs:
            return {"gap": {"code": EB.GAP_CONTRACT_MISMATCH, "message": f"{sid}: " + "; ".join(errs[:5])}}
        rows = EB.rows_from_packet(resp["evidence_packet"], call["corpus_id"])
        calls.append(EB.call_record(call, resp["evidence_packet"], rows))
        row_lists.append(rows)
    if failures and not calls:
        reason = failures[0]["error"]
        if cfg.get("fallback") == EB.SURFACE_LEGACY:
            try:
                out = _with_degraded(legacy(step, state, m, corpus_ids), ["evidence_boundary_unavailable"])
            except OrchUnavailable as exc:
                return EB.unavailable_outcome(str(cfg.get("on_unavailable") or "gap"), sid, f"evidence surface and legacy fallback unreachable: {exc}")
            out["output"].update({"fallback": EB.SURFACE_LEGACY, "boundary_failures": failures[:6]})
            return out
        return EB.unavailable_outcome(str(cfg.get("on_unavailable") or "gap"), sid, reason)
    rows, dropped = EB.merge_rows(row_lists, max_rows=int(cfg.get("max_rows", EB.DEFAULT_MAX_ROWS)))
    truncated = list(plan["truncated"]) + ([{"reason": "max_rows", "dropped": dropped}] if dropped else [])
    output: dict[str, Any] = {"surface": EB.SURFACE_BOUNDARY, "mode": mode, "corpus_explorer": explorer, "needs": needs, "corpus_ids": corpus_ids,
                              "rows": rows, "calls": calls, "retrieval_completed": not failures, "evidence_contract": EB.PACKET_SCHEMA_VERSION}
    refs = EB.refs_from_rows(rows)
    reasons: list[str] = []
    if truncated:
        output["truncated"] = truncated
    if failures:
        output["boundary_failures"] = failures[:6]
        reasons.append("evidence_boundary_partial")
    if union_legacy:
        try:
            g = legacy(step, state, m, corpus_ids)
            output["graph_rows"] = (g.get("output") or {}).get("graph_rows") or []
            output["graph_facts"] = (g.get("output") or {}).get("graph_facts") or 0
            refs = refs + [r for r in (g.get("evidence_refs") or []) if r["id"] not in {x["id"] for x in refs}]
        except OrchUnavailable as exc:
            output["graph_rows"], output["graph_facts"] = [], 0
            output["graph_failure"] = str(exc)[:300]
            reasons.append("graph_facts_unavailable")
    return _with_degraded({"output": output, "evidence_refs": refs}, reasons)


def exec_compile_plan(step: dict[str, Any], state: RunState, m: Manifest) -> service.ExecOutcome:
    corpus_ids = _corpus_ids(state)
    if not corpus_ids:
        return {"gap": {"code": "INPUT_SCOPE_MISSING", "message": "no corpus_ids in input or request_options"}}
    out = _orch_post("/retrieve/plan", {"signal": _query_text(step, state, m), "corpus_ids": corpus_ids, "limit": 24, "explore": True},
                     user_agent=_ua(step, state))
    rows = out.get("evidence_rows") or out.get("rows") or _rows(out, corpus_ids)
    return {"output": {"queries": out.get("queries") or out.get("plan") or [], "rows": _trim_rows(rows)}, "evidence_refs": _refs_from_rows(rows)}


def _graph_legacy(step: dict[str, Any], state: RunState, m: Manifest, corpus_ids: list[str]) -> service.ExecOutcome:
    cfg = m.step(step["step_id"]).get("config") or {}
    out = _orch_post("/retrieve", {"query": _query_text(step, state, m), "corpus_ids": corpus_ids, "explore": True,
                                   "limit": int(cfg.get("max_facts", 20))}, user_agent=_ua(step, state))
    rows = [r for r in (out.get("evidence_rows") or []) if r.get("kind") in ("graph_fact", "graph_hop")]
    return {"output": {"surface": EB.SURFACE_LEGACY, "graph_rows": _trim_rows(rows), "graph_facts": len(out.get("graph_facts") or [])},
            "evidence_refs": _refs_from_rows(rows)}


def exec_graph_expand(step: dict[str, Any], state: RunState, m: Manifest) -> service.ExecOutcome:
    corpus_ids = _corpus_ids(state)
    if not corpus_ids:
        return {"gap": {"code": "INPUT_SCOPE_MISSING", "message": "no corpus_ids in input or request_options"}}
    surface, forced = EB.resolve_surface(m.step(step["step_id"]).get("config") or {}, os.environ)
    if surface == EB.SURFACE_BOUNDARY:
        return exec_evidence(step, state, m, corpus_ids, legacy=_graph_legacy, union_legacy=True)
    return _with_degraded(_graph_legacy(step, state, m, corpus_ids), forced)


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
    # admitted_evidence_ids = the COMPLETE admitted set the service threaded into the step context (store accumulator, never the
    # display cap). The service includes every admitted observation in evidence_refs — across all bounded-loop passes — precisely so
    # the qualify/score hard gates, which count independent groups over exactly these ids, always see the full set (see _context_refs).
    # the COMPLETE gate-facing admitted set the service threaded into the context from the store accumulator (never the display cap,
    # never state.outputs which loses bounded-loop passes). The qualify/score hard gates count independent groups over exactly these ids.
    admitted = list(ctx.get("admitted_evidence_ids") or [])
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
        # HR4 (ADR-064) portfolio: each qualify step returns `qualifications` (one record per live hypothesis, hypothesis_ids set);
        # Trail filters them per hypothesis, so the caller forwards EVERY record of every stage in acceptance order and never
        # selects a winner. The pre-HR4 singular `qualification` is still forwarded when present.
        quals: list[dict[str, Any]] = []
        for o in _ordered_outputs(state):
            if isinstance(o.get("qualification"), dict):
                quals.append(o["qualification"])
            quals += [q for q in (o.get("qualifications") or []) if isinstance(q, dict)]
        payload["qualifications"] = quals
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
    # HR4 (ADR-064) portfolio: one deterministic score per hypothesis whose gates passed and one typed refusal per hypothesis that
    # did not; every record id is Trail's and joins the cross-system lineage (LAW 1: Polymath never reads or ranks the score value).
    plural = [str(s["record_id"]) for s in (output.get("trail_scores") or []) if isinstance(s, dict) and s.get("record_id")]
    if plural:
        output["trail_score_record_ids"] = list(output.get("trail_score_record_ids") or []) + plural
        record_ids += plural
    refused = [str(r["record_id"]) for r in (output.get("score_refusals") or []) if isinstance(r, dict) and r.get("record_id")]
    if refused:
        output["trail_score_refusal_record_ids"] = refused
        record_ids += refused
    rc = TC.bounded_receipt(state.run_id, step["step_id"], kind, resp, idempotency_key=req["idempotency_key"], principal=principal, record_ids=record_ids)
    return {"output": output, "external": rc, "evidence_refs": refs}


# ─────────────────────────────────────────────────────────── DOMAIN_OPERATION (ADR-0020): manifest-named domain code, out of process
#: where domain bindings live: <repo>/adapters/<domain>/binding.py. The manifest names the domain and the operation; this file never does.
_DOMAINS_DIR = pathlib.Path(__file__).resolve().parents[2] / "adapters"
_DOMAIN_RE = re.compile(r"^[a-z][a-z0-9_]{1,40}$")
DOMAIN_REQUEST_VERSION = "domain_operation_request.v1"
DOMAIN_TIMEOUT_S = float(os.environ.get("POLYMATH_DOMAIN_OPERATION_TIMEOUT_S", "120"))
DOMAIN_OUTPUT_MAX_BYTES = 1_000_000


def exec_domain(step: dict[str, Any], state: RunState, m: Manifest) -> service.ExecOutcome:
    """DOMAIN_OPERATION = one bounded, stateless computation by a domain's own code. The binding runs OUT OF PROCESS (its module
    names never enter this worker; a crash is a typed step failure) with a MINIMAL environment (no DSN, no tokens). The domain
    computes; it never reads or writes run state, the ledger or a store. `{"ok": false, code, message}` is a typed gap carrying the
    domain's code; a crash, a timeout or a malformed response raises and the runtime records STEP_EXECUTOR_ERROR."""
    cfg = m.step(step["step_id"]).get("config") or {}
    domain, operation = str(cfg.get("domain") or ""), str(cfg.get("operation") or "")
    if not _DOMAIN_RE.match(domain):
        return {"gap": {"code": "DOMAIN_BINDING_INVALID", "message": f"{step['step_id']}: config.domain {domain!r} is not a domain name"}}
    root = _DOMAINS_DIR.resolve()
    binding = (root / domain / "binding.py").resolve()
    if root not in binding.parents or not binding.is_file():
        return {"gap": {"code": "DOMAIN_BINDING_MISSING", "message": f"{step['step_id']}: no binding for domain {domain!r}"}}
    scope = {"input": state.input, "options": state.options, "outputs": state.outputs, "context": step.get("context") or {}}
    request = {"schema_version": DOMAIN_REQUEST_VERSION, "domain": domain, "operation": operation, "run_id": state.run_id,
               "step_id": step["step_id"], "input": state.input,
               "inputs": {name: ([_path(scope, d) for d in sel] if isinstance(sel, list) else _path(scope, sel))
                          for name, sel in (cfg.get("inputs") or {}).items()},
               "config": {k: v for k, v in cfg.items() if k not in ("domain", "operation", "inputs")}}
    env = {"PATH": os.environ.get("PATH", ""), "LANG": os.environ.get("LANG", "en_US.UTF-8"), "PYTHONDONTWRITEBYTECODE": "1"}
    try:
        proc = subprocess.run([sys.executable, str(binding)], input=json.dumps(request), capture_output=True, text=True,
                              timeout=DOMAIN_TIMEOUT_S, cwd=str(binding.parent), env=env)
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"domain operation {operation} timed out after {DOMAIN_TIMEOUT_S:g}s") from exc
    if proc.returncode != 0:
        raise RuntimeError(f"domain operation {operation} exited {proc.returncode}: {proc.stderr.strip()[-600:]}")
    if len(proc.stdout.encode()) > DOMAIN_OUTPUT_MAX_BYTES:
        raise RuntimeError(f"domain operation {operation} returned more than {DOMAIN_OUTPUT_MAX_BYTES} bytes")
    try:
        resp = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"domain operation {operation} did not return one JSON object: {exc}") from exc
    if not isinstance(resp, dict) or not isinstance(resp.get("ok"), bool):
        raise RuntimeError(f"domain operation {operation} returned no boolean `ok`")
    if not resp["ok"]:
        code, message = str(resp.get("code") or ""), str(resp.get("message") or "")
        if not re.match(r"^[A-Z][A-Z0-9_]{2,60}$", code):
            raise RuntimeError(f"domain operation {operation} refused without a typed code: {code!r}")
        return {"gap": {"code": code, "message": f"{operation}: {message}"[:2000]}}
    if not isinstance(resp.get("output"), dict):
        raise RuntimeError(f"domain operation {operation} returned ok without an output object")
    output = dict(resp["output"])
    output["_domain"] = {"domain": domain, "operation": operation, "binding_sha256": hashlib.sha256(binding.read_bytes()).hexdigest()}
    return {"output": output}


EXECUTORS: dict[str, service.Executor] = {
    "POLYMATH_RETRIEVE": exec_retrieve, "POLYMATH_COMPILE_PLAN": exec_compile_plan, "POLYMATH_GRAPH_EXPAND": exec_graph_expand,
    "VALIDATE": exec_validate, "BRANCH": exec_branch, "EXTERNAL_OPERATION": exec_external, "DOMAIN_OPERATION": exec_domain,
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
