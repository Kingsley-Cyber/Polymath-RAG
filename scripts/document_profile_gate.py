#!/usr/bin/env python3
"""DOCUMENT-PROFILE-V1 gate — self-retrieval: for every profiled document, do its OWN generated questions and searches
retrieve it first through the profile collection (prefetch identity / theme / questions / searches / title → RRF)?
Also: where a named question lands (default: the owner's punch question) and which books its profile lane would
nominate. Read-only; needs the embedder sidecar and Qdrant.

  .venv/bin/python scripts/document_profile_gate.py --corpus cinema [--per-doc 3] [--question "..."] [--tag gate1]
Writes docs/wiki/experiments/document-profile-gate-<tag>.json
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for p in (ROOT / "shared", ROOT / "orchestrator", ROOT):
    sys.path.insert(0, str(p))

from polymath_shared.db import tx  # noqa: E402

PUNCH = ("What do the screen-combat and fight-choreography books say about making a punch read as real on camera: "
         "camera angle, distance to the strike, the reaction, and the timing between contact and response?")


def rrf_rank(client, coll, vec, corpus_id: str, k: int = 40) -> list[str]:
    from qdrant_client.http import models as qm
    flt = qm.Filter(must=[qm.FieldCondition(key="corpus_id", match=qm.MatchValue(value=corpus_id))])
    pre = [qm.Prefetch(query=vec, using=s, limit=k, filter=flt) for s in ("identity", "theme", "title")]
    pre += [qm.Prefetch(query=[vec], using=s, limit=k, filter=flt) for s in ("questions", "searches")]     # multivector: one-row matrix
    res = client.query_points(coll, prefetch=pre, query=qm.FusionQuery(fusion=qm.Fusion.RRF), limit=k, with_payload=["doc_id"])
    return [p.payload.get("doc_id") for p in res.points]


def main() -> int:
    ap = argparse.ArgumentParser(); ap.add_argument("--corpus", required=True); ap.add_argument("--per-doc", type=int, default=3)
    ap.add_argument("--question", default=PUNCH); ap.add_argument("--tag", default="gate")
    a = ap.parse_args()
    from orchestrator.api.fast import _embed_queries
    from polymath_shared.document_profile.projection import collection_name
    from polymath_shared.embedding_contracts import active_contract
    from polymath_shared.settings import get_settings
    from qdrant_client import QdrantClient
    coll = collection_name(active_contract().contract_id)
    client = QdrantClient(url=get_settings().stores.qdrant_url, timeout=60)
    with tx() as conn:
        names = dict(conn.execute("SELECT doc_id, source_name FROM documents WHERE corpus_id=%s", (a.corpus,)).fetchall())
        rows = conn.execute("""SELECT r.run_id, a.payload FROM artifacts a JOIN runs r ON r.run_id=a.run_id
                               WHERE r.corpus_id=%s AND a.stage='doc_profile'""", (a.corpus,)).fetchall()
    per_doc = []
    for _rid, payload in rows:
        p = payload if isinstance(payload, dict) else json.loads(payload)
        dp = p.get("doc_profile") or {}
        comp = dp.get("compiled") or {}
        # the artifact carries doc_id (worker ≥ rag-compiler-v3.1); older artifacts resolve through the projection point
        target = dp.get("doc_id")
        if not target:
            pid = (p.get("doc_profile_qdrant") or {}).get("point_id")
            pts = client.retrieve(coll, ids=[pid], with_payload=["doc_id"]) if pid else []
            target = pts[0].payload.get("doc_id") if pts else None
        if not target or target not in names:
            continue
        probes = (comp.get("questions") or [])[: a.per_doc] + (comp.get("searches") or [])[: a.per_doc]
        if not probes:
            continue
        vecs = _embed_queries(probes)
        ranks = []
        for v in vecs:
            order = rrf_rank(client, coll, list(v), a.corpus)
            ranks.append(order.index(target) + 1 if target in order else None)
        per_doc.append({"doc": names[target][:40], "doc_id": target, "probes": len(probes), "ranks": ranks,
                        "top1": sum(1 for r in ranks if r == 1), "top3": sum(1 for r in ranks if r and r <= 3)})
    total = sum(d["probes"] for d in per_doc) or 1
    summary = {"documents": len(per_doc), "probes": total,
               "self_top1_rate": round(sum(d["top1"] for d in per_doc) / total, 3),
               "self_top3_rate": round(sum(d["top3"] for d in per_doc) / total, 3),
               "median_rank": statistics.median([r for d in per_doc for r in d["ranks"] if r]) if per_doc else None}
    qv = list(_embed_queries([a.question])[0])
    top = rrf_rank(client, coll, qv, a.corpus, k=15)
    summary["question"] = a.question[:120]; summary["question_top15"] = [names.get(d, d)[:36] for d in top]
    out = ROOT / "docs/wiki/experiments" / f"document-profile-gate-{a.tag}.json"
    out.write_text(json.dumps({"summary": summary, "per_doc": per_doc}, indent=1, ensure_ascii=False))
    print(json.dumps(summary, indent=1, ensure_ascii=False)); print("wrote", out)
    client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
