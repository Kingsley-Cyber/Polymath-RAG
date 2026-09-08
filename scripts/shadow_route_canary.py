#!/usr/bin/env python
"""SHADOW-ROUTE-CANARY-V1 — the S8 shadow-phase measurement (RETRIEVAL-MIGRATION §17).

Runs the vNext semantic routing path (global profile → ONE filtered parent-map search →
child deepening) as a SHADOW over the mapped cohort and records its coverage against the
CURRENT child lane — with **no production rank effect**. It reads only: the profile /
parent-map projections, the routing collection, and the production compiled profiles for
probe questions. It writes nothing but the evidence JSON. Nothing in the live query path,
ranking, or `QUERY_READY` is touched.

Method (per probe query, self-anchored at document level):

  * probe = a mapped doc's OWN compiled `questions`/`searches` (production-faithful);
    the source doc is the doc-level gold.
  * profile step  → `rrf_rank` over the profile collection → `profile_doc_candidates`
                    (the SAME nominator the self-retrieval gate qualified).
  * map step      → ONE parent-map search filtered to the nominated docs (§17 perf rule).
  * child step    → dense child search localized to the resolved parents.
  * final (baseline) = a plain dense child search restricted to the SOURCE doc — the
                    localization target the map path must cover.
  * receipt       = §17 fields + latency; metrics = nomination hit, parent-resolve rate,
                    `overlap_with_final`, and the MISS reasons (`degraded`).

    POLYMATH_GROQ_ROUTER=1 .venv/bin/python scripts/shadow_route_canary.py --corpus cinema \
        --per-doc 3 --out docs/wiki/experiments/shadow-route-2026-09-07.json

Exit non-zero only on a harness/infra failure (no probes ran) — the shadow RECORDS
coverage/misses, it does not gate on them (S8 gate is "no production rank effect", which
is structural here).
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for _p in (ROOT / "shared", ROOT / "orchestrator", ROOT / "scripts", ROOT):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from polymath_shared.db import tx  # noqa: E402
from polymath_shared.document_profile import parent_map_projection as PMP  # noqa: E402
from polymath_shared.document_profile import projection as PJ  # noqa: E402
from polymath_shared.document_profile.shadow_route import (  # noqa: E402
    doc_nomination_hit,
    overlap_with_final,
    shadow_route,
)


def _mapped_cohort(corpus_id: str, limit: int | None) -> list[tuple[str, str]]:
    with tx() as conn:
        rows = conn.execute(
            "SELECT d.doc_id, d.source_name FROM document_parent_maps m "
            "JOIN documents d ON d.doc_id=m.doc_id "
            "WHERE m.active AND d.corpus_id=%s GROUP BY d.doc_id, d.source_name "
            "ORDER BY count(*) DESC" + (f" LIMIT {int(limit)}" if limit else ""),
            (corpus_id,),
        ).fetchall()
    return [(r[0], r[1]) for r in rows]


def _probes(corpus_id: str, doc_id: str, per_doc: int) -> list[str]:
    with tx() as conn:
        row = conn.execute(
            "SELECT a.payload FROM artifacts a JOIN runs r ON r.run_id=a.run_id "
            "WHERE r.corpus_id=%s AND a.stage='doc_profile' "
            "AND a.payload->'doc_profile'->>'doc_id'=%s ORDER BY a.created_at DESC LIMIT 1",
            (corpus_id, doc_id),
        ).fetchone()
    if not row:
        return []
    payload = row[0] if isinstance(row[0], dict) else json.loads(row[0])
    comp = ((payload.get("doc_profile") or {}).get("compiled")) or {}
    return (comp.get("questions") or [])[:per_doc] + (comp.get("searches") or [])[:per_doc]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", default="cinema")
    ap.add_argument("--per-doc", type=int, default=3, help="questions + searches per mapped doc")
    ap.add_argument("--limit", type=int, default=0, help="cap mapped docs (0 = all)")
    ap.add_argument("--k-docs", type=int, default=8)
    ap.add_argument("--k-parents", type=int, default=24)
    ap.add_argument("--k-children", type=int, default=40)
    ap.add_argument("--final-k", type=int, default=20, help="current dense-child top-K in the source doc")
    ap.add_argument("--out", default="")
    args = ap.parse_args(argv)

    from document_profile_gate import rrf_rank  # noqa: E402  (the qualified profile nominator)
    from orchestrator.api.fast import _embed_queries  # noqa: E402
    from polymath_shared.embedding_contracts import active_contract  # noqa: E402
    from polymath_shared.projection_contracts import qdrant_collection_name  # noqa: E402
    from polymath_shared.settings import get_settings  # noqa: E402
    from qdrant_client import QdrantClient  # noqa: E402
    from qdrant_client.http import models as qm  # noqa: E402

    ct = active_contract()
    profile_coll = PJ.collection_name(ct.contract_id)
    map_coll = PMP.collection_name(ct.contract_id)
    routing_coll = qdrant_collection_name(args.corpus, ct.contract_id)
    client = QdrantClient(url=get_settings().stores.qdrant_url, timeout=90)

    def profile_search(vec, k):
        return [{"doc_id": d} for d in rrf_rank(client, profile_coll, vec, args.corpus, k)]

    def map_search(vec, doc_ids, k):
        flt = qm.Filter(must=[qm.FieldCondition(key="doc_id", match=qm.MatchAny(any=list(doc_ids)))])
        res = client.query_points(map_coll, query=vec, using=PMP.VECTOR_NAME, query_filter=flt,
                                  limit=k, with_payload=["doc_id", "parent_id", "alias"])
        return [{"doc_id": p.payload.get("doc_id"), "parent_id": p.payload.get("parent_id"),
                 "alias": p.payload.get("alias"), "score": p.score} for p in res.points]

    def child_search(vec, pairs, k):
        parent_ids = [p for _d, p in pairs if p]
        if not parent_ids:
            return []
        flt = qm.Filter(must=[
            qm.FieldCondition(key="representation_kind", match=qm.MatchValue(value="routing_child")),
            qm.FieldCondition(key="parent_id", match=qm.MatchAny(any=parent_ids)),
        ])
        res = client.query_points(routing_coll, query=vec, query_filter=flt, limit=k,
                                  with_payload=["chunk_id", "doc_id", "parent_id"])
        return [{"chunk_id": p.payload.get("chunk_id"), "doc_id": p.payload.get("doc_id"),
                 "parent_id": p.payload.get("parent_id"), "score": p.score} for p in res.points]

    def final_children_in_doc(vec, doc_id, k):
        flt = qm.Filter(must=[
            qm.FieldCondition(key="representation_kind", match=qm.MatchValue(value="routing_child")),
            qm.FieldCondition(key="doc_id", match=qm.MatchValue(value=doc_id)),
        ])
        res = client.query_points(routing_coll, query=vec, query_filter=flt, limit=k,
                                  with_payload=["chunk_id"])
        return [p.payload.get("chunk_id") for p in res.points if p.payload.get("chunk_id")]

    cohort = _mapped_cohort(args.corpus, args.limit or None)
    if not cohort:
        print(f"no mapped docs in corpus {args.corpus}", file=sys.stderr)
        return 1
    print(f"[shadow] {len(cohort)} mapped docs; probing profile->map->child vs current child lane")

    per_doc_rows, per_probe = [], []
    ran = 0
    for doc_id, source_name in cohort:
        probes = _probes(args.corpus, doc_id, args.per_doc)
        if not probes:
            per_doc_rows.append({"doc": source_name[:44], "probes": 0, "note": "no compiled profile"})
            continue
        vecs = _embed_queries(probes)
        nom, resolved_hits, overlaps, latencies, miss = 0, 0, [], [], {}
        for q, vec in zip(probes, vecs):
            r = shadow_route(list(vec), profile_search=profile_search, map_search=map_search,
                             child_search=child_search, k_docs=args.k_docs,
                             k_parents=args.k_parents, k_children=args.k_children)
            nom_hit = doc_nomination_hit(r.profile_doc_candidates, [doc_id])
            resolved_in_doc = any(m.get("doc_id") == doc_id for m in r.parent_map_candidates
                                  if m.get("parent_id") in set(r.resolved_parent_ids))
            final = final_children_in_doc(list(vec), doc_id, args.final_k)
            ov = overlap_with_final(r.shadow_child_candidates, final)
            nom += int(nom_hit)
            resolved_hits += int(resolved_in_doc)
            if final:
                overlaps.append(ov)
            latencies.append(r.latency_ms["total"])
            for d in r.degraded:
                miss[d] = miss.get(d, 0) + 1
            per_probe.append({
                "doc": source_name[:44], "q": q[:70], "nominated": nom_hit,
                "resolved_in_doc": resolved_in_doc, "resolved_parents": len(r.resolved_parent_ids),
                "shadow_children": len(r.shadow_child_candidates), "final_children": len(final),
                "overlap_with_final": ov, "latency_ms": r.latency_ms["total"], "degraded": list(r.degraded),
            })
            ran += 1
        per_doc_rows.append({
            "doc": source_name[:44], "probes": len(probes),
            "nomination_rate": round(nom / len(probes), 3),
            "parent_resolve_rate": round(resolved_hits / len(probes), 3),
            "mean_overlap_with_final": round(statistics.mean(overlaps), 3) if overlaps else None,
            "median_latency_ms": round(statistics.median(latencies), 1) if latencies else None,
            "misses": miss,
        })
        print(f"  {source_name[:44]:<44} nom={nom}/{len(probes)} resolve={resolved_hits}/{len(probes)} "
              f"overlap={round(statistics.mean(overlaps),3) if overlaps else None}")

    scored = [d for d in per_doc_rows if d.get("probes")]
    all_overlaps = [p["overlap_with_final"] for p in per_probe if p["final_children"]]
    summary = {
        "corpus": args.corpus, "mapped_docs": len(cohort), "docs_probed": len(scored),
        "total_probes": ran,
        "nomination_rate": round(sum(d["nomination_rate"] * d["probes"] for d in scored) / ran, 3) if ran else None,
        "parent_resolve_rate": round(sum(d["parent_resolve_rate"] * d["probes"] for d in scored) / ran, 3) if ran else None,
        "mean_overlap_with_final": round(statistics.mean(all_overlaps), 3) if all_overlaps else None,
        "median_latency_ms": round(statistics.median([p["latency_ms"] for p in per_probe]), 1) if per_probe else None,
        "no_production_rank_effect": True,
        "collections": {"profile": profile_coll, "parent_map": map_coll, "routing": routing_coll},
        "params": {"k_docs": args.k_docs, "k_parents": args.k_parents, "k_children": args.k_children,
                   "final_k": args.final_k, "per_doc": args.per_doc},
    }
    out = {"summary": summary, "per_doc": per_doc_rows, "per_probe": per_probe,
           "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S")}
    print("\n[shadow] summary:", json.dumps(summary, indent=2))
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(json.dumps(out, indent=2))
        print(f"[shadow] wrote {args.out}")
    client.close()
    return 0 if ran else 1


if __name__ == "__main__":
    raise SystemExit(main())
