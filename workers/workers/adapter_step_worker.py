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
import collections
import concurrent.futures
import logging
import os
import pathlib
import socket
import subprocess  # noqa: F401 — the domain binding's runner (polymath_shared.adapter.domain) spawns through this module; tests patch it here
import sys
import threading
import time
from typing import Any

import httpx
import psycopg

from polymath_shared.adapter import domain as DOMAIN, evidence_boundary as EB, research_gaps as RG, service
from polymath_shared.adapter.manifest import Manifest, ManifestInvalid
from polymath_shared.adapter.transitions import RunState
from polymath_shared.db import tx
from polymath_shared.execution import heartbeat, register_worker, worker_identity
from polymath_shared.logging import configure_logging

ORCH = os.environ.get("POLYMATH_ORCH_URL", "http://127.0.0.1:7200")
#: F7: one evidence call measured up to 74 s plus up to 75 s waiting on the orchestrator's provider breaker — 149 s worst case, over the
#: old 120 s HTTP timeout. The timeout covers that; the LEASE covers one call and its transient backoff, because the lease is renewed
#: before every call (`_renew_lease`) — never once per step while a step's calls run for minutes.
HTTP_TIMEOUT_S = float(os.environ.get("POLYMATH_ADAPTER_HTTP_TIMEOUT_S", "180"))
LEASE_S_DEFAULT = int(os.environ.get("POLYMATH_ADAPTER_LEASE_S", "300"))
LEASE_MARGIN_S = 60                   # >= the longest transient backoff (TRANSIENT_BACKOFF_S) plus a renewal's own round trip
#: F8: how often the loop looks for runs idle on the agent (service.expire_idle; the bound is POLYMATH_ADAPTER_IDLE_EXPIRY_S, default 24 h)
IDLE_SWEEP_S = float(os.environ.get("POLYMATH_ADAPTER_IDLE_SWEEP_S", "60"))
log = logging.getLogger("worker-adapter-step")
WORKER_TYPE = "adapter_step"          # == the supervisor slot name


# ─────────────────────────────────────────────────────────── lease (F7): renewed before every outbound call of a step
#: the lease this process holds while a step executes OUTSIDE the run's transaction: (run_id, owner, lease_s), or None between steps
_LEASE: dict[str, Any] = {}


def _renew_lease() -> None:
    """F7: a step's executor runs outside the run's transaction (the row lock is free for submit / cancel) and may make several slow
    calls; the lease is renewed before each one, so a run is never claimed by a second worker mid-step. A lost lease raises LeaseLost
    and the unit is dropped (never applied). Outside a held lease (tests, `--once` drivers without a lease) this is a no-op."""
    held = dict(_LEASE)
    if not held:
        return
    with tx() as conn:
        if not service.store.renew_lease(conn, held["run_id"], held["owner"], int(held["lease_s"])):
            raise service.LeaseLost(f"lease on {held['run_id']} lost while its step executed")


# ─────────────────────────────────────────────────────────── executors
def _path(obj: dict[str, Any], dotted: str, default: Any = None) -> Any:
    cur: Any = obj
    for part in dotted.split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            return default
    return cur


def _need(step: dict[str, Any], state: RunState, m: Manifest) -> tuple[str, str]:
    """(the step's information need, where it came from). PRODUCT-SEARCH-E2E: the need is the live hypotheses (`query_from`), the
    path the step names (`config.source`), or the run's own NEED field (EB.NEED_FIELDS: the given seed or the corpus seed) — never
    another input field: a category, a language or a geography is a LIMIT on the research, and it no longer silently becomes the
    search query (W:77-79 removed). Nothing usable raises (STEP_EXECUTOR_ERROR), typed and named."""
    cfg = m.step(step["step_id"]).get("config") or {}
    if cfg.get("query_from") == "hypotheses":                 # generic engine state: the live hypotheses' statements
        stmts = [str(h.get("statement", "")).strip() for h in step.get("context", {}).get("hypotheses") or []]
        stmts = [x for x in stmts if x]
        if stmts:
            return "; ".join(stmts)[:2000], "context.hypotheses"
    src = cfg.get("source")
    if src:
        v = _path({"input": state.input, "options": state.options, "outputs": state.outputs}, src)      # a prior step may have compiled the need
        if isinstance(v, str) and v.strip():
            return v.strip(), str(src)
    for k in EB.NEED_FIELDS:
        v = state.input.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip(), f"input.{k}"
    raise ValueError("NEED_MISSING: no information need in the run input (no seed and no need field; set config.source on the step, "
                     "e.g. input.seed) — a limit such as category, language or geography is never searched in its place")


def _query_text(step: dict[str, Any], state: RunState, m: Manifest) -> str:
    return _need(step, state, m)[0]


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


class ScopeNotConfirmed(OrchRejected):
    """K1b (gap K-04): the orchestrator answered a scoped request without confirming that exact scope. Pre-K1 code ignores
    `scope` and searches every knowledge role, so the answer is refused like any contract defect: never a fallback, the step
    fails (STEP_EXECUTOR_ERROR) instead of reasoning over possibly unscoped evidence."""


def _ua(step: dict[str, Any], state: RunState) -> str:
    return EB.user_agent(state.run_id, step["step_id"], step["sequence"])


#: bug hunt B-30: a TRANSIENT transport failure — the peer restarting (connection refused / dropped), a gateway in front of it answering
#: 502 / 504 — is retried after these pauses before it counts as unavailable (one orchestrator bounce or Trail-daemon blip ended
#: multi-hour runs). A read timeout (the peer had the request for the whole HTTP timeout), a 500, a 503 (the server itself says it is
#: unavailable: the evidence boundary's fallback and `on_unavailable` policy answer that) and every refusal keep their meaning at once.
TRANSIENT_BACKOFF_S = (2.0, 8.0, 30.0)
TRANSIENT_STATUS = frozenset({502, 504})


def _orch_post(path: str, body: dict[str, Any], *, user_agent: str | None = None) -> dict[str, Any]:
    """POST to the orchestrator — ONLY to a path on the evidence-boundary allow-list. The User-Agent names run/step/sequence so
    every call's query receipt is attributable to the adapter step that made it. A scoped call whose answer does not confirm
    that scope raises ScopeNotConfirmed (K1b). A transient failure is retried within TRANSIENT_BACKOFF_S (bug hunt B-30)."""
    EB.assert_allowed_path(path)
    attempt = 0
    while True:
        _renew_lease()                                                   # F7: every attempt starts with a fresh lease
        try:
            with httpx.Client(timeout=HTTP_TIMEOUT_S) as c:
                r = c.post(f"{ORCH}{path}", json=body, headers=({"User-Agent": user_agent} if user_agent else None))
        except httpx.HTTPError as exc:
            if isinstance(exc, (httpx.NetworkError, httpx.RemoteProtocolError, httpx.ConnectTimeout, httpx.PoolTimeout)) and attempt < len(TRANSIENT_BACKOFF_S):
                log.warning("orchestrator %s: %s (%s); retry %d in %.0fs", path, type(exc).__name__, user_agent, attempt + 1, TRANSIENT_BACKOFF_S[attempt])
                time.sleep(TRANSIENT_BACKOFF_S[attempt])
                attempt += 1
                continue
            tried = f" after {attempt + 1} attempts" if attempt else ""
            raise OrchUnavailable(f"orchestrator {path} unreachable{tried}: {type(exc).__name__}: {exc}"[:400]) from exc
        if r.status_code in TRANSIENT_STATUS and attempt < len(TRANSIENT_BACKOFF_S):
            log.warning("orchestrator %s -> %s (%s); retry %d in %.0fs", path, r.status_code, user_agent, attempt + 1, TRANSIENT_BACKOFF_S[attempt])
            time.sleep(TRANSIENT_BACKOFF_S[attempt])
            attempt += 1
            continue
        break
    if r.status_code >= 500:
        raise OrchUnavailable(f"orchestrator {path} -> {r.status_code}: {r.text[:300]}")
    if r.status_code >= 400:
        raise OrchRejected(f"orchestrator {path} -> {r.status_code}: {r.text[:300]}")
    out = r.json()
    why = EB.scope_violation(body, out)            # K1b: a scoped call must come back confirmed (fail closed)
    if why:
        raise ScopeNotConfirmed(f"orchestrator {path}: {why}"[:600])
    return out


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
    need, need_source = _need(step, state, m)
    body = {"query": need, "corpus_ids": corpus_ids, "limit": int(cfg.get("top_k", state.input.get("top_k") or 16)),
            "scope": dict(EB.TRAIL_SCOPE)}          # K1: Trail ideation reads reference material only
    if mode == "EXPLORE":
        body["explore"] = True                 # contract rows (retrieve-evidence-rows-v1): the view an agent consumes
    else:
        body["mode"] = mode                    # FAST/HYBRID/GRAPH answer with hits; normalised below
    out = _orch_post("/retrieve", body, user_agent=_ua(step, state))
    rows = _rows(out, corpus_ids)
    return {"output": {"surface": EB.SURFACE_LEGACY, "query": body["query"], "need_source": need_source, **_seed_origin(state, need_source),
                       "mode": mode, "corpus_ids": corpus_ids, "rows": _trim_rows(rows),
                       "evidence_contract": out.get("evidence_contract")}, "evidence_refs": _refs_from_rows(rows)}


def _seed_origin(state: RunState, need_source: str) -> dict[str, Any]:
    """PRODUCT-SEARCH-E2E receipt: when a step searched the run's seed, whether the requester gave it or the corpus proposed it."""
    field = need_source.split(".", 1)[1] if need_source.startswith("input.") else None
    origin = state.input.get(f"{field}_origin") if field else None
    return {"seed_origin": origin} if origin else {}


def exec_retrieve(step: dict[str, Any], state: RunState, m: Manifest) -> service.ExecOutcome:
    cfg = m.step(step["step_id"]).get("config") or {}
    corpus_ids = _corpus_ids(state)
    if not corpus_ids:
        return {"gap": {"code": "INPUT_SCOPE_MISSING", "message": "no corpus_ids in input or request_options"}}
    surface, forced = EB.resolve_surface(cfg, os.environ)
    if surface == EB.SURFACE_BOUNDARY:
        return exec_evidence(step, state, m, corpus_ids, legacy=_retrieve_legacy)
    return _with_degraded(_retrieve_legacy(step, state, m, corpus_ids), forced)


#: F3: per-run evidence cache in this process — run_id -> {cache key: (rows, call record)}; bounded (oldest run evicted first). Rebuilt
#: from the run's own stored outputs after a restart (`_cached_from_outputs`), so a question asked again is answered the same way.
_EVIDENCE_CACHE: "collections.OrderedDict[str, dict[str, tuple[list[dict[str, Any]], dict[str, Any]]]]" = collections.OrderedDict()
EVIDENCE_CACHE_RUNS = 32
EVIDENCE_CACHE_ENTRIES = 64
_CACHE_LOCK = threading.Lock()


def _cache_for(run_id: str) -> dict[str, tuple[list[dict[str, Any]], dict[str, Any]]]:
    with _CACHE_LOCK:
        bucket = _EVIDENCE_CACHE.pop(run_id, None) or {}
        _EVIDENCE_CACHE[run_id] = bucket
        while len(_EVIDENCE_CACHE) > EVIDENCE_CACHE_RUNS:
            _EVIDENCE_CACHE.popitem(last=False)
        return bucket


def _cached_from_outputs(state: RunState, key: str) -> tuple[list[dict[str, Any]], dict[str, Any]] | None:
    """A call this run already made (its record carries the key) whose every row is still on that step's stored output."""
    for sid in reversed(state.output_order or tuple(state.outputs)):
        out = state.outputs.get(sid)
        if not isinstance(out, dict) or not isinstance(out.get("calls"), list):
            continue
        rows = {str(r.get("id")): r for r in out.get("rows") or [] if isinstance(r, dict) and r.get("id")}
        for rec in out["calls"]:
            if isinstance(rec, dict) and rec.get("cache_key") == key and rec.get("row_ids") is not None \
                    and all(str(i) in rows for i in rec["row_ids"]):
                return [rows[str(i)] for i in rec["row_ids"]], rec
    return None


def exec_evidence(step: dict[str, Any], state: RunState, m: Manifest, corpus_ids: list[str], *, legacy,
                  union_legacy: bool = False) -> service.ExecOutcome:
    """The evidence-boundary surface (GOVERNED-CONVERGENCE-V1 TG2b). The ORIGINAL need — the run's seed, or one need per live
    hypothesis — goes to the evidence route, ONE corpus per call, bounded; Polymath plans, explores and grades, and returns an
    EvidencePacket with no synthesis. The rules live in the pure module; this function only performs the calls:
      * a packet that fails the contract is a TERMINAL gap (EVIDENCE_CONTRACT_MISMATCH) — never a fallback, never partial use;
      * an unreachable surface falls back to the legacy lane when `config.fallback == "retrieve"` (recorded `degraded`), else
        follows `config.on_unavailable` (gap | continue);
      * empty evidence is a SUCCESS (`retrieval_completed: true`) — the corpus not supporting a need is a finding.
    PRODUCT-SEARCH-E2E: F4 — the calls run `config.parallel_calls` (default 2) at a time and no more are asked than the row limit keeps a
    fair share of (`config.min_rows_per_need`), merged fair-share per call; F3 — a call this run already made against the same corpus
    generation, mode and explorer switch is answered from the run's cache (said: `cache: hit`); F7 — every call renews the lease.
    `union_legacy` (graph steps): the packet carries chunks, not graph facts, so the legacy graph rows are unioned in."""
    sid = step["step_id"]
    cfg = m.step(sid).get("config") or {}
    # `_compiled_need`: resolved by the RUNTIME (service.advance -> EB.domain_compiled_need) from a DOMAIN_OPERATION step only; this
    # executor still never reads a step output
    needs = EB.original_needs(cfg, state.input, state.options, (step.get("context") or {}).get("hypotheses"), compiled_need=step.get("_compiled_need"))
    max_rows = int(cfg.get("max_rows", EB.DEFAULT_MAX_ROWS))
    plan = EB.plan_calls(needs, corpus_ids, max_calls=int(cfg.get("max_calls", EB.DEFAULT_MAX_CALLS)),
                         row_budget=EB.row_budget_calls(max_rows, cfg.get("min_rows_per_need")))
    mode, explorer = str(cfg.get("mode") or "WILDCARD").upper(), bool(cfg.get("corpus_explorer", True))
    generations = step.get("_corpus_generations") if isinstance(step.get("_corpus_generations"), dict) else {}
    cache = _cache_for(state.run_id)

    def one(call: dict[str, Any]) -> dict[str, Any]:
        key = EB.cache_key(call["need"], call["corpus_id"], mode, explorer, generations.get(call["corpus_id"]))
        with _CACHE_LOCK:
            hit = (cache.get(key) or _cached_from_outputs(state, key)) if key else None
        if hit:
            return {"call": call, "key": key, "rows": [dict(r) for r in hit[0]], "record": {**hit[1], "cache": "hit"}}
        try:
            resp = _orch_post(EB.EVIDENCE_PATH, EB.request_body(call["need"], call["corpus_id"], mode=mode, corpus_explorer=explorer),
                              user_agent=_ua(step, state))
        except OrchUnavailable as exc:
            return {"call": call, "failure": {"need_index": call["need_index"], "corpus_id": call["corpus_id"], "error": str(exc)[:300]}}
        errs = EB.check_response(resp)
        if errs:
            return {"call": call, "mismatch": errs}
        rows = EB.rows_from_packet(resp["evidence_packet"], call["corpus_id"])
        rec = {**EB.call_record(call, resp["evidence_packet"], rows), **({"cache_key": key} if key else {})}
        if key:
            with _CACHE_LOCK:                                              # two calls of one step finish on two threads
                cache[key] = (rows, rec)
                while len(cache) > EVIDENCE_CACHE_ENTRIES:                 # bounded per run: the oldest answer goes first
                    cache.pop(next(iter(cache)))
        return {"call": call, "key": key, "rows": rows, "record": rec}

    width = max(1, min(int(cfg.get("parallel_calls", EB.DEFAULT_PARALLEL_CALLS)), len(plan["calls"]) or 1))
    if width > 1:
        with concurrent.futures.ThreadPoolExecutor(max_workers=width) as pool:
            results = list(pool.map(one, plan["calls"]))            # plan order, whatever finishes first
    else:
        results = [one(c) for c in plan["calls"]]
    mismatch = next((r for r in results if r.get("mismatch")), None)
    if mismatch:
        return {"gap": {"code": EB.GAP_CONTRACT_MISMATCH, "message": f"{sid}: " + "; ".join(mismatch["mismatch"][:5])}}
    calls = [r["record"] for r in results if "record" in r]
    row_lists = [r["rows"] for r in results if "record" in r]
    failures = [r["failure"] for r in results if r.get("failure")]
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
    rows, dropped = EB.merge_rows_fair(row_lists, max_rows=max_rows)
    truncated = list(plan["truncated"]) + ([{"reason": "max_rows", "dropped": dropped}] if dropped else [])
    need_source = "context.hypotheses" if cfg.get("query_from") == "hypotheses" and (step.get("context") or {}).get("hypotheses") else \
        (str(cfg.get("source")) if step.get("_compiled_need") or cfg.get("source") else next((f"input.{k}" for k in EB.NEED_FIELDS if state.input.get(k)), None))
    output: dict[str, Any] = {"surface": EB.SURFACE_BOUNDARY, "mode": mode, "corpus_explorer": explorer, "needs": needs, "corpus_ids": corpus_ids,
                              "rows": rows, "calls": calls, "retrieval_completed": not failures, "evidence_contract": EB.PACKET_SCHEMA_VERSION,
                              "parallel_calls": width, "cache_hits": sum(1 for c in calls if c.get("cache") == "hit")}
    if need_source:
        output["need_source"] = need_source
        output.update(_seed_origin(state, need_source))
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
    need, need_source = _need(step, state, m)
    out = _orch_post("/retrieve/plan", {"signal": need, "corpus_ids": corpus_ids, "limit": 24, "explore": True,
                                        "scope": dict(EB.TRAIL_SCOPE)},      # K1: reference material only
                     user_agent=_ua(step, state))
    rows = out.get("evidence_rows") or out.get("rows") or _rows(out, corpus_ids)
    return {"output": {"queries": out.get("queries") or out.get("plan") or [], "rows": _trim_rows(rows), "need_source": need_source,
                       **_seed_origin(state, need_source)}, "evidence_refs": _refs_from_rows(rows)}


def _graph_legacy(step: dict[str, Any], state: RunState, m: Manifest, corpus_ids: list[str]) -> service.ExecOutcome:
    cfg = m.step(step["step_id"]).get("config") or {}
    out = _orch_post("/retrieve", {"query": _query_text(step, state, m), "corpus_ids": corpus_ids, "explore": True,
                                   "limit": int(cfg.get("max_facts", 20)), "scope": dict(EB.TRAIL_SCOPE)},   # K1
                     user_agent=_ua(step, state))
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
    if step["step_id"] == m.entry_step_id and isinstance(state.options.get("start_receipt"), dict):
        out["start_receipt"] = state.options["start_receipt"]        # PRODUCT-SEARCH-E2E: the start's scope + seed decisions, on the record
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


class TrailStoreMissing(RuntimeError):
    """Embedded mode without POLYMATH_TRAIL_STORE (bug hunt B-66)."""


def _embedded_trail() -> TC.TrailMCPClient:
    """POLYMATH_TRAIL_MODE=embedded (docs/migration/ADR-TRAIL-EMBEDDING.md): the SAME client, over an in-process transport that reaches
    TrailSignal's deterministic core under `governance/trail/` — no daemon, no network. Loaded by file path so this module never imports
    it by name; its audit store persists at POLYMATH_TRAIL_STORE (a file path). Unset is refused (bug hunt B-66): an in-memory store
    loses Trail's admitted evidence at every worker restart, and judge / qualify / score then run on nothing. `:memory:` only when
    asked for explicitly (tests)."""
    store_path = (os.environ.get("POLYMATH_TRAIL_STORE") or "").strip()
    if not store_path:
        raise TrailStoreMissing("POLYMATH_TRAIL_MODE=embedded needs POLYMATH_TRAIL_STORE (the audit store's file path; `:memory:` only when "
                                "asked for explicitly): an unset store would keep Trail's admitted evidence in memory and lose it at a restart")
    import importlib.util
    path = pathlib.Path(__file__).resolve().parents[2] / "governance" / "trail" / "embedded.py"
    spec = importlib.util.spec_from_file_location("polymath_governance_trail_embedded", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"embedded Trail core not found at {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    store = mod.SqliteResearchStore(store_path)
    return TC.TrailMCPClient("http://trail.embedded/mcp", "in-process", transport=mod.transport(mod.build_service(store=store)))


#: bug hunt B-67: a token minted from the daemon secret lives an hour; the cached client is rebuilt (re-minted) this long before it expires
TOKEN_REFRESH_S = 300


def trail() -> TC.TrailMCPClient:
    global _TRAIL
    if _TRAIL is None or TC.token_expires_within(_TRAIL.token, TOKEN_REFRESH_S):
        _TRAIL = _embedded_trail() if os.environ.get("POLYMATH_TRAIL_MODE", "daemon").strip().lower() == "embedded" else TC.TrailMCPClient.from_env()
    return _TRAIL


def _newest_output_with(state: RunState, key: str) -> dict[str, Any] | None:
    """The most recently accepted step output carrying `key` (acceptance order, not dict order — JSONB drops it). An output of a
    Trail operation that does not fill `key` is skipped: runs stored before the A-15 fix carry every unfilled envelope field."""
    for sid in reversed(state.output_order or tuple(state.outputs)):
        out = state.outputs.get(sid)
        if isinstance(out, dict) and key in out and TC.fills(out.get("operation_kind"), key):
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
    # ADR-069: a step that opted in sends the CLOSED extended wire (four fields + stated support + structured candidates) the re-pinned
    # core admits; every other step sends the four-field view exactly as before
    hyps = list((ctx.get("semantics") or {}).get("trail") or []) if cfg.get("hypotheses_from") == "context.semantics.trail" else list(ctx.get("hypotheses") or [])
    if cfg.get("hypotheses_from") == "context.semantics.trail" and not hyps:
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
        if cfg.get("gaps_from") == RG.GATE_ORIGIN:
            # bug hunt B-21: a stage compiled from TrailSignal's OWN gate gaps (the supply directive: the market qualification's open
            # gaps) sends exactly those — never every field-stage gap an agent wrote earlier in the run
            gate = next((o for o in reversed(_ordered_outputs(state)) if o.get("operation_kind") and TC.fills(o.get("operation_kind"), "open_gaps")
                         and isinstance(o.get("open_gaps"), list)), None)
            payload["knowledge_gaps"] = []
            payload["open_gaps"] = [RG.wire_gap(g) for g in (gate or {}).get("open_gaps") or [] if isinstance(g, dict)][:100]
            return payload
        # a step that opted in (`config.gaps_from: context.semantics.research_gaps`) sends the HARVESTED per-hypothesis gaps: ledger +
        # step + agent open gaps + bridge gaps, each owned and stably identified, Trail's gate gaps beside them (research_gaps.py)
        harvested = RG.trail_gap_payload(ctx.get("semantics")) if cfg.get("gaps_from") else None
        if harvested is not None:
            payload.update(harvested)
            return payload
        gaps = []
        for out in _ordered_outputs(state):
            gaps += [g for g in (out.get("knowledge_gaps") or []) if isinstance(g, dict)]
        # bug hunt B-21 / B-26: Trail's gap is CLOSED (extra="forbid"): never an agent's raw dict
        payload["knowledge_gaps"] = [RG.wire_gap(g) for g in gaps[-100:]]
        payload["open_gaps"] = [RG.wire_gap(g) for g in list((_newest_output_with(state, "open_gaps") or {}).get("open_gaps") or [])[:100] if isinstance(g, dict)]
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
        # bug hunt B-26: Trail's physical job is CLOSED (hypothesis_id, job, mechanism); an agent's extra key ended the run TRAIL_REFUSED
        payload["physical_jobs"] = [{k: j.get(k) for k in ("hypothesis_id", "job", "mechanism")}
                                    for j in list((_newest_output_with(state, "physical_jobs") or {}).get("physical_jobs") or [])[:100] if isinstance(j, dict)]
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
    try:
        client = trail()
    except TrailStoreMissing as exc:
        return {"gap": {"code": "TRAIL_STORE_MISSING", "message": str(exc)}}
    if not client.configured:
        return {"gap": {"code": "TRAIL_PRINCIPAL_MISSING", "message": "no Trail principal token/secret configured for Polymath (owner action O1)"}}
    cfg = spec.get("config") or {}
    principal = os.environ.get("POLYMATH_TRAIL_PRINCIPAL", "polymath")
    key = TC.identifier(state.run_id, step["step_id"], str(step["sequence"]))
    snap = (step.get("context") or {}).get("registry_snapshot") or {}
    payload = _payload_for(kind, step, state, cfg)
    if kind == "evidence.admit":
        # bug hunt B-05, owner decision 2026-09-26: a receipt over Trail's request ceiling is REFUSED at submit (the harness resubmits a
        # smaller one); one that still arrives too big ends typed here — nothing is ever trimmed or sent
        over = TC.admission_overflow(payload, key=key, run_ref=state.run_id, registry_snapshot_id=snap.get("snapshot_id"))
        if over:
            return {"gap": {"code": "RECEIPT_TOO_LARGE", "message": f"{kind}: the request would be {over['bytes']} bytes by TrailSignal's measure, over its "
                                                                   f"{over['limit_bytes']}-byte limit ({over['observations']} observations); nothing was trimmed or sent"}}
    req = TC.bounded_request(kind, payload, key=key, run_ref=state.run_id, registry_snapshot_id=snap.get("snapshot_id"))
    retries: list[str] = []
    while True:
        _renew_lease()                                                   # F7: a slow or retried Trail call never outlives the lease
        try:
            resp = client.operate(kind, req)
            break
        except TC.TrailToolError as exc:
            return {"gap": {"code": "TRAIL_REFUSED", "message": f"{kind}: {exc}"}}
        except (TC.TrailTransportError, TC.TrailProtocolError, TC.TrailUnreachable) as exc:
            # bug hunt B-30: a daemon restarting is retried with the SAME request (its idempotency key makes the replay safe), bounded
            transient = isinstance(exc, (TC.TrailUnreachable, TC.TrailInternalError)) or \
                (isinstance(exc, TC.TrailTransportError) and exc.status in TRANSIENT_STATUS)
            if transient and len(retries) < len(TRANSIENT_BACKOFF_S):
                log.warning("trail %s: %s; retry %d in %.0fs", kind, exc, len(retries) + 1, TRANSIENT_BACKOFF_S[len(retries)])
                time.sleep(TRANSIENT_BACKOFF_S[len(retries)])
                retries.append(f"{type(exc).__name__}: {exc}"[:200])
                continue
            raise RuntimeError(f"trail transport: {exc}") from exc          # typed STEP_EXECUTOR_ERROR (retryable by re-run)
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
    if retries:
        output["transport_retries"] = retries                                  # counted, never silent
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
        # Trail's ResearchResultV1 envelope always carries every field: the ones an operation does not fill arrive as null or as
        # an EMPTY tuple ([]). Keep only the fields this operation fills (TC.FIELDS_BY_OPERATION), so an operation's unfilled
        # `qualifications`/`open_gaps`/`redundancy_groups`/… never shadows a real value an earlier step produced (the step
        # context and the compiled result gather the NEWEST occurrence of each key; gap A-15). A filled empty list is kept.
        if k in ("priors", "registry_snapshot") or v is None or not TC.fills(kind, k):
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
_DOMAIN_RE = DOMAIN.DOMAIN_RE
DOMAIN_REQUEST_VERSION = DOMAIN.REQUEST_VERSION
DOMAIN_TIMEOUT_S = DOMAIN.TIMEOUT_S
DOMAIN_OUTPUT_MAX_BYTES = DOMAIN.OUTPUT_MAX_BYTES
RESERVED_DOMAIN_KEYS = DOMAIN.RESERVED_KEYS


def exec_domain(step: dict[str, Any], state: RunState, m: Manifest) -> service.ExecOutcome:
    """DOMAIN_OPERATION = one bounded, stateless computation by a domain's own code, through the shared runner
    (`polymath_shared.adapter.domain`: out of process, minimal environment, typed refusals, reserved keys). `{"ok": false, code,
    message}` is a typed gap carrying the domain's code; a crash, a timeout or a malformed response raises (DomainCrash, a
    RuntimeError) and the runtime records STEP_EXECUTOR_ERROR."""
    cfg = m.step(step["step_id"]).get("config") or {}
    domain, operation = str(cfg.get("domain") or ""), str(cfg.get("operation") or "")
    scope = {"input": state.input, "options": state.options, "outputs": state.outputs, "context": step.get("context") or {}}
    req = DOMAIN.request(domain=domain, operation=operation, run_id=state.run_id, step_id=step["step_id"], run_input=state.input,
                         scope=scope, config=cfg)
    _renew_lease()                                                       # F7: a slow domain computation never outlives the lease
    return DOMAIN.run(domain, operation, req, domains_dir=_DOMAINS_DIR, timeout_s=DOMAIN_TIMEOUT_S)


# ─────────────────────────────────────────────────────────── host prefetch (PRODUCT-SEARCH-E2E: a supply step's host lookups)
def _host_supplier_search(principal_id: str | None, args: dict[str, Any]) -> dict[str, Any]:
    """The supplier API read the host makes for a research step, as the run OWNER's principal (the owner: None)."""
    from polymath_shared.acquisition import supplier
    return supplier.search(principal_id=principal_id, query=str(args.get("query") or ""), source=str(args.get("source") or ""),
                           limit=args.get("limit"))


#: the HOST tools a manifest's prefetch lookups may name (an allow-list; a lookup's `args` are the domain's data, passed through)
HOST_TOOLS: dict[str, Any] = {"supplier_search": _host_supplier_search}
PREFETCH_MAX_LOOKUPS = 24


def _lookup_summary(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{k: r.get(k) for k in ("lookup_id", "intent_id", "concept_id", "channel", "tool")}
            | {"status": (r.get("result") or {}).get("status"), "items": len((r.get("result") or {}).get("items") or []),
               "fallback": bool((r.get("result") or {}).get("fallback"))} for r in results]


def exec_prefetch(unit: service.Unit, lookups: list[dict[str, Any]], cfg: dict[str, Any]) -> dict[str, Any]:
    """HOST_PREFETCH: run the step's lookups through HOST_TOOLS with the run owner's principal, OUTSIDE any transaction (the lease renewed
    per lookup), then hand the results to the manifest's domain builder (`config.host_prefetch.build`), which turns them into what the
    step carries beside it (a draft receipt, the fallback commands). A failed lookup is a result, never an exception."""
    started = service.now_iso()
    results = []
    for lk in lookups[:PREFETCH_MAX_LOOKUPS]:
        _renew_lease()
        tool = HOST_TOOLS.get(str(lk.get("tool") or ""))
        if tool is None:
            res: dict[str, Any] = {"status": "UNAVAILABLE", "limitations": [f"no host tool {lk.get('tool')!r} on this worker"]}
        else:
            try:
                res = dict(tool(unit.owner_principal_id, dict(lk.get("args") or {})) or {})
            except Exception as exc:  # noqa: BLE001 — a refused or failed read is the domain's to turn into a fallback
                res = {"status": "UNAVAILABLE", "error": {"type": type(exc).__name__, "code": getattr(exc, "code", None),
                                                          "message": str(getattr(exc, "message", None) or exc)[:500]},
                       "limitations": [f"the host read failed: {type(exc).__name__}"]}
        results.append({**lk, "result": res})
    completed = service.now_iso()
    build = dict(cfg.get("build") or {})
    domain, operation = str(build.get("domain") or ""), str(build.get("operation") or "")
    scope = {"input": unit.state.input, "options": unit.state.options, "outputs": unit.state.outputs, "context": {}}
    req = DOMAIN.request(domain=domain, operation=operation, run_id=unit.state.run_id, step_id=f"{(unit.spec or {}).get('step_id')}:prefetch",
                         run_input=unit.state.input, scope=scope, config=build)
    req["inputs"].update({"action": unit.action, "lookups": results, "started_at": started, "completed_at": completed})
    _renew_lease()
    out = DOMAIN.run(domain, operation, req, domains_dir=_DOMAINS_DIR, timeout_s=DOMAIN_TIMEOUT_S)
    if out.get("gap"):
        return {"error": f"{out['gap']['code']}: {out['gap']['message']}"[:1000], "summary": _lookup_summary(results)}
    produced = {k: v for k, v in (out.get("output") or {}).items() if not str(k).startswith("_")}
    return {**produced, "summary": _lookup_summary(results)}


EXECUTORS: dict[str, Any] = {
    "POLYMATH_RETRIEVE": exec_retrieve, "POLYMATH_COMPILE_PLAN": exec_compile_plan, "POLYMATH_GRAPH_EXPAND": exec_graph_expand,
    "VALIDATE": exec_validate, "BRANCH": exec_branch, "EXTERNAL_OPERATION": exec_external, "DOMAIN_OPERATION": exec_domain,
    service.HOST_PREFETCH: exec_prefetch,
}


# ─────────────────────────────────────────────────────────── loop
#: how long the loop waits after an iteration raised (a database outage, a failure that could not even be recorded) before claiming again
ERROR_BACKOFF_S = 10.0


def _transient(exc: BaseException) -> bool:
    """A database that is unreachable or busy (connection lost, pool exhausted, lock / deadlock) says nothing about the run: the loop
    backs off and the run is claimed again. So does an admitted manifest SET that does not load (a deploy error, bug hunt B-57): it
    breaks every adapter at once and is fixed by the next deploy. Anything else a step unit raises would raise again on every claim
    (bug hunt B-06)."""
    return isinstance(exc, (psycopg.OperationalError, psycopg.InterfaceError, ManifestInvalid))


def lease_seconds(lease_s: int | None) -> int:
    """F7: the lease must outlast the longest wait between two renewals — one HTTP call (HTTP_TIMEOUT_S) plus its backoff margin. A
    configured lease below that is raised to it (and said), never left to expire under a call that is still running."""
    want = int(lease_s if lease_s is not None else LEASE_S_DEFAULT)
    floor = int(HTTP_TIMEOUT_S) + LEASE_MARGIN_S
    if want < floor:
        log.warning("lease %ss is shorter than one call (%ss) plus margin (%ss): using %ss", want, int(HTTP_TIMEOUT_S), LEASE_MARGIN_S, floor)
    return max(want, floor)


def process_one(owner: str, lease_s: int, *, max_steps: int | None = None, crash_after: int | None = None) -> str | None:
    """Claim + drive one run. Returns the run_id worked on (None = nothing claimable). F7: each step unit is THREE short phases —
    `prepare` (issue / find the step, one transaction), the executor (OUTSIDE any transaction: the run's row lock is free, the lease is
    renewed before every call), `apply` (record the outcome, one transaction, only while this worker still holds the lease). A unit that
    raises is rolled back and, unless the database itself failed, its run ends `failed` with a typed STEP_RUNTIME_ERROR in a fresh
    transaction — a deterministic error is never re-claimed forever ahead of every healthy run (bug hunt B-06)."""
    lease_s = lease_seconds(lease_s)
    with tx() as conn:
        run_id = service.store.claim_run(conn, owner, lease_s)
    if not run_id:
        return None
    steps_done = 0
    try:
        while True:
            try:
                with tx() as conn:
                    if not service.store.renew_lease(conn, run_id, owner, lease_s):
                        log.warning("lease lost on %s; stopping", run_id)
                        return run_id
                    before_state = service.store.load_run(conn, run_id)[0]
                    before_row = service.store.current_step(conn, run_id)
                    unit = service.prepare(conn, run_id, EXECUTORS)
                    after_row = service.store.current_step(conn, run_id)
                state = unit.state
                if unit.kind != "done":
                    _LEASE.update(run_id=run_id, owner=owner, lease_s=lease_s)
                    try:
                        result = service.run_prefetch(EXECUTORS, unit) if unit.kind == "prefetch" else service.execute(EXECUTORS, unit)
                    finally:
                        _LEASE.clear()
                    with tx() as conn:
                        if not service.store.renew_lease(conn, run_id, owner, lease_s):
                            log.warning("lease lost on %s while its step executed; the outcome is dropped", run_id)
                            return run_id
                        state = (service.apply_prefetch(conn, run_id, unit, result) if unit.kind == "prefetch"
                                 else service.apply(conn, run_id, unit, result))
                        after_row = service.store.current_step(conn, run_id)
            except service.LeaseLost as exc:
                log.warning("run %s: %s; the outcome is dropped", run_id, exc)
                return run_id
            except Exception as exc:
                if _transient(exc):
                    raise
                log.exception("run %s: the step unit raised; recording a typed failure", run_id)
                with tx() as conn:
                    service.fail_run(conn, run_id, code="STEP_RUNTIME_ERROR", message=f"{type(exc).__name__}: {exc}")
                return run_id
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


def sweep_idle(last: list[float]) -> list[str]:
    """F8: at most every IDLE_SWEEP_S, end the runs idle on the agent past the bound (service.expire_idle). Never raises."""
    now = time.monotonic()
    if last and now - last[0] < IDLE_SWEEP_S:
        return []
    last[:] = [now]
    try:
        with tx() as conn:
            expired = service.expire_idle(conn)
        if expired:
            log.info("expired %d run(s) idle on the agent: %s", len(expired), ", ".join(r[:16] for r in expired))
        return expired
    except Exception:  # noqa: BLE001 — a sweep that failed is retried next time; it never takes the slot down
        log.exception("idle sweep failed")
        return []


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", action="store_true", help="drain claimable runs once, then exit")
    ap.add_argument("--max-steps", type=int, default=None, help="steps per claim before releasing (default: until the run waits/ends)")
    ap.add_argument("--lease-s", type=int, default=LEASE_S_DEFAULT)
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
    swept: list[float] = []
    while True:
        try:
            sweep_idle(swept)
            worked = process_one(args.owner, args.lease_s, max_steps=args.max_steps, crash_after=args.crash_after)
            with tx() as conn:
                heartbeat(conn, identity["worker_id"], processed_count=1 if worked else None)
        except Exception:
            # bug hunt B-06: one failed iteration (the database away, a failure that could not be recorded) never takes the supervised
            # slot down — an exit made the supervisor restart it, re-claim the same run and quarantine the slot after 5 exits
            if args.once:
                raise
            log.exception("adapter step iteration failed; backing off %.0fs", ERROR_BACKOFF_S)
            time.sleep(ERROR_BACKOFF_S)
            continue
        if worked is None:
            if args.once:
                return 0
            time.sleep(args.poll_s)
        elif args.once and args.max_steps is not None:
            return 0


if __name__ == "__main__":
    sys.exit(main())
