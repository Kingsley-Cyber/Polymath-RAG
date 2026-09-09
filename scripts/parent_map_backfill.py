#!/usr/bin/env python
"""PARENT-MAP-BACKFILL-V1 — routed generation + projection for a corpus (step 5).

RETRIEVAL-MIGRATION-DEPENDENCY-V1 step 5 "controlled backfill". For each live document
of a corpus, generate its parent maps through the six compound-mini accounts and project
them to the contract-scoped Qdrant collection. Lane selection is explicit ROUND-ROBIN
across the six distinct-account endpoints (BACKFILL-SPREAD-V1): `route_groq`'s capacity
view is blind for these lanes in a dedicated backfill process (unregistered limiter lanes
→ every account tied → lexical-first pin), so round-robin gives every account ~1/6 of the
load while each endpoint keeps its own AIMD limiter for per-account backoff. Idempotent +
resumable: a doc already fully mapped re-infers NOTHING (§36.5), and projection upserts by
point id. Owner-authorized controlled backfill (after the step 1-4 E2E gates passed);
bounded by `--limit`.

    POLYMATH_GROQ_ROUTER=1 .venv/bin/python scripts/parent_map_backfill.py --corpus cinema --limit 8 --project
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for _p in (ROOT / "shared", ROOT / "workers", ROOT):
    sys.path.insert(0, str(_p))

from polymath_shared.db import tx  # noqa: E402


def _cohort(corpus_id, limit):
    with tx() as conn:
        docs = conn.execute("SELECT doc_id, corpus_id, source_name FROM documents WHERE corpus_id=%s "
                            "ORDER BY source_name" + (f" LIMIT {int(limit)}" if limit else ""),
                            (corpus_id,)).fetchall()
        out = []
        for d in docs:
            parents = [
                {"chunk_id": r[0], "chunk_index": r[1], "char_start": r[2], "heading_path": r[3],
                 "text": r[4], "region_role": r[5]}
                for r in conn.execute(
                    "SELECT chunk_id, chunk_index, char_start, heading_path, text, region_role FROM chunks "
                    "WHERE doc_id=%s AND tier='parent' ORDER BY chunk_index", (d[0],)).fetchall()]
            out.append((d[0], d[1], d[2], parents))
        return out


def _routed_infer(lane_selected, dispatch):
    """Round-robin infer closure. Records LANE SELECTION (at pick time) and
    PROVIDER HTTP DISPATCH (only when the request actually reached the network)
    as SEPARATE counters — a selection is not a dispatch (GROQ-MAP-CONTROL-
    PLANE-REPAIR-V1). Raises MapInferError carrying the refusal gate / dispatch
    fact so the worker accounts a local refusal (0 HTTP) apart from a provider
    fault."""
    import itertools
    import threading
    from polymath_shared.llm_extraction.client import LLMExtractionClient
    from polymath_shared.llm_extraction.pool import cloud_endpoints, stage_pin
    from polymath_shared.document_profile.map_prompt import build_map_prompt
    from workers.doc_parent_map_worker import MapInferError
    pin = stage_pin("doc_parent_map") or []
    eps = {e.name: e for e in cloud_endpoints() if e.name in pin}
    ep_names = [n for n in pin if n in eps]              # ordered; only endpoints that exist
    # ROUND-ROBIN across the six distinct-account endpoints (BACKFILL-SPREAD-V1). `route()`'s
    # capacity view is BLIND for these map lanes in a dedicated backfill process: the limiter
    # lanes it reads (`REGISTRY.get_lane`) are unregistered until first use, so every account
    # looks tied at full budget and the only spread is a 6 s reservation that expires during a
    # real multi-second map call — collapsing to a lexical-first pin (measured 2026-09-08:
    # 649/657 calls on map_groq1 while 55 fresh docs mapped 0/0-error). Explicit round-robin
    # gives every account ~1/6 of the load; each endpoint keeps its own AIMD limiter
    # (`limiter_key=map_groqN`, six distinct API keys) for real per-account backoff.
    _rr = itertools.count()
    _rr_lock = threading.Lock()

    def infer(skeletons, is_combined=False, grounding=None):
        if not ep_names:
            raise RuntimeError("no active doc_parent_map lane")
        with _rr_lock:
            lane = ep_names[next(_rr) % len(ep_names)]
            lane_selected[lane] += 1                 # SELECTION (pre-dispatch)
        ep = eps[lane]
        client = LLMExtractionClient("cloud", url=ep.url, model=ep.model, limiter_key=ep.limiter_key,
                                     api_key=ep.api_key, cloud_opts=ep.cloud_opts, timeout_s=90.0, max_attempts=1)
        client.endpoint_name = ep.name
        system, user = build_map_prompt(skeletons, grounding=grounding, is_combined=is_combined)
        raw, err = client.complete_one(user, system_prompt=system, max_tokens=2400)
        dispatched = getattr(client, "_last_http_dispatched", False)
        if dispatched:
            with _rr_lock:
                dispatch[lane] += 1              # actual HTTP request that left the box
        if err:
            raise MapInferError(err, reason=getattr(client, "_last_refusal_reason", None),
                                dispatched=dispatched)
        return raw
    return infer


def summarize(corpus, rows, lane_selected, dispatch, *, concurrency, wall_s) -> dict:
    """Pure conservation summary (unit-testable). `+0 parents / 0 errored_docs`
    can no longer read as a clean provider run: limiter refusals (0 HTTP), HTTP
    faults, empty/invalid completions and per-doc internal errors are each
    surfaced, and PASS requires BOTH every doc complete AND zero internal
    failures (GROQ-MAP-CONTROL-PLANE-REPAIR-V1)."""
    def agg(k):
        return sum(int(r.get(k) or 0) for r in rows)
    complete_docs = sum(1 for r in rows if r.get("complete"))
    escaped = sum(1 for r in rows if r.get("error"))
    internal = sum(1 for r in rows if (
        r.get("errors_n") or r.get("limiter_refusals") or r.get("http_failures")
        or r.get("http_429") or r.get("compiler_invalid") or r.get("empty_completions")))
    return {
        "gate": "parent-map-backfill-v1", "corpus": corpus, "docs": len(rows),
        "complete_docs": complete_docs,
        "errored_docs": escaped,                       # run_document_mapping RAISED
        "documents_with_internal_errors": internal,    # refusals/HTTP/empty/invalid/errors
        "eligible_parents": agg("eligible"),
        "parents_already_mapped": agg("already_mapped"),
        "parents_newly_mapped": agg("newly_mapped"),
        "maps_persisted": agg("newly_mapped"),
        "unresolved_parents": agg("unresolved"),
        "batches_done": agg("batches_done"),
        "batches_partial": agg("batches_partial"),
        "attempts_used": agg("attempts_used"),
        "limiter_refusals": agg("limiter_refusals"),
        "http_dispatches": agg("http_dispatches"),
        "http_429": agg("http_429"),
        "http_failures": agg("http_failures"),
        "empty_completions": agg("empty_completions"),
        "compiler_complete": agg("compiler_complete"),
        "compiler_partial": agg("compiler_partial"),
        "compiler_invalid": agg("compiler_invalid"),
        "concurrency": concurrency, "wall_s": round(wall_s, 1),
        "lane_selection": dict(lane_selected),          # endpoint picks (NOT dispatches)
        "provider_http_dispatch": dict(dispatch),       # requests that left the box
        "distinct_accounts_selected": len({l.replace("map_groq", "") for l in lane_selected}),
        "distinct_accounts_dispatched": len({l.replace("map_groq", "") for l in dispatch}),
        "PASS": complete_docs == len(rows) and internal == 0,
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", default="cinema")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--project", action="store_true", help="also project maps to Qdrant + reconcile")
    ap.add_argument("--concurrency", type=int, default=6,
                    help="docs mapped in parallel (one per Groq account). route_groq CONCURRENCY-SPREAD-V1 "
                         "(2026-09-08) rotates a simultaneous burst across the six accounts, so 6-way spreads "
                         "the load one-per-account. 1 = sequential.")
    ap.add_argument("--out", default=None)
    args = ap.parse_args(argv)

    from workers.doc_parent_map_worker import run_document_mapping
    from polymath_shared.document_profile import map_compiler
    from polymath_shared.document_profile.parent_skeleton import build_parent_skeletons
    contract = map_compiler.MAP_COMPILER_VERSION
    lane_selected: Counter = Counter()      # endpoint SELECTIONS (pre-dispatch)
    dispatch: Counter = Counter()           # actual provider HTTP dispatches
    infer = _routed_infer(lane_selected, dispatch)

    client = dim = ct = coll = None
    if args.project:
        import workers.doc_profile_worker as W
        from polymath_shared.document_profile import parent_map_projection as PMP
        from polymath_shared.embedding_contracts import active_contract
        from polymath_shared.settings import get_settings
        from qdrant_client import QdrantClient
        ct = active_contract(); dim = ct.dimension; coll = PMP.collection_name(ct.contract_id)
        client = QdrantClient(url=get_settings().stores.qdrant_url, timeout=90)

    cohort = _cohort(args.corpus, args.limit)
    concurrency = max(1, int(args.concurrency))
    print(f"[backfill] {args.corpus}: {len(cohort)} docs; router={os.environ.get('POLYMATH_GROQ_ROUTER','0')}; concurrency={concurrency}")
    # Projection helpers imported once (thread-safe); each doc is independent (own tx() pool
    # connection), route_groq spreads Groq calls across the six accounts, the qdrant client +
    # embedder handle concurrent requests. run_document_mapping is idempotent, so a killed run
    # resumes with zero re-work.
    import workers.doc_profile_worker as W
    from polymath_shared.document_profile import parent_map_projection as PMP
    from polymath_shared.document_profile.map_compiler import CompiledMap
    from concurrent.futures import ThreadPoolExecutor, as_completed
    import threading
    print_lock = threading.Lock()
    t0 = time.time()

    def _process_one(doc) -> dict:
        doc_id, corpus_id, name, parents = doc
        try:
            out = run_document_mapping(tx, run_id=f"map-backfill-{doc_id[:8]}", doc_id=doc_id, corpus_id=corpus_id,
                                       parents=parents, infer=infer, provider="groq", model="groq/compound-mini")
        except Exception as exc:  # noqa: BLE001 — one doc's failure never kills the batch; resumable next run
            with print_lock:
                print(f"  {name[:44]:44} ERROR {type(exc).__name__}: {str(exc)[:70]}")
            return {"doc": name[:44], "error": f"{type(exc).__name__}: {str(exc)[:120]}", "complete": False}
        proj = None
        if args.project and out.parents_mapped:
            with tx() as conn:
                mrows = conn.execute("SELECT alias, parent_id, routing_signature, semantic_hooks, exact_identifiers, "
                                     "map_hash, quality_flags FROM document_parent_maps WHERE doc_id=%s AND map_contract=%s "
                                     "AND active ORDER BY alias", (doc_id, contract)).fetchall()
            maps = [CompiledMap(alias=r[0], parent_id=r[1], routing_signature=r[2], semantic_hooks=tuple(r[3] or []),
                                exact_identifiers=tuple(r[4] or []), map_hash=r[5], quality_flags=tuple(r[6] or []))
                    for r in mrows]
            manifest = build_parent_skeletons(parents)
            rc = PMP.project_parent_maps(client, embed=lambda t: W._embed_texts(t), embedding_contract_id=ct.contract_id,
                                         dim=dim, doc_id=doc_id, corpus_id=corpus_id, maps=maps, manifest=manifest,
                                         map_contract=contract)
            proj = rc["points"]
        doc_ok = out.complete and not out.unresolved_parent_ids
        with print_lock:
            print(f"  {name[:44]:44} mapped={out.parents_mapped}/{out.eligible_parents} "
                  f"new={out.parents_newly_mapped} dispatch={out.http_dispatches} "
                  f"refused={out.limiter_refusals} empty={out.empty_completions} "
                  f"complete={doc_ok} projected={proj}")
        return {"doc": name[:44], "eligible": out.eligible_parents, "mapped": out.parents_mapped,
                "already_mapped": out.parents_already_mapped, "newly_mapped": out.parents_newly_mapped,
                "complete": doc_ok, "unresolved": len(out.unresolved_parent_ids),
                "batches_done": out.batches_done, "batches_partial": out.batches_partial,
                "attempts_used": out.attempts_used, "errors_n": len(out.errors),
                "limiter_refusals": out.limiter_refusals, "http_dispatches": out.http_dispatches,
                "http_429": out.http_429, "http_failures": out.http_failures,
                "empty_completions": out.empty_completions,
                "compiler_complete": out.compiler_complete, "compiler_partial": out.compiler_partial,
                "compiler_invalid": out.compiler_invalid,
                "refusal_reasons": list(out.refusal_reasons), "projected": proj}

    rows: list = []
    with ThreadPoolExecutor(max_workers=concurrency, thread_name_prefix="pm-backfill") as ex:
        for f in as_completed([ex.submit(_process_one, d) for d in cohort]):
            rows.append(f.result())
    summary = summarize(args.corpus, rows, lane_selected, dispatch,
                        concurrency=concurrency, wall_s=time.time() - t0)
    print(json.dumps(summary, indent=1))
    if args.out:
        Path(args.out).write_text(json.dumps({"summary": summary, "docs": rows}, indent=1, ensure_ascii=False))
        print("evidence ->", args.out)
    if client is not None:
        client.close()
    return 0 if summary["PASS"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
