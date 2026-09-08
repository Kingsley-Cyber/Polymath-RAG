#!/usr/bin/env python
"""PROFILE-VNEXT-SELFRETRIEVAL-CANARY-V1 — the S8 self-retrieval qualification gate.

RETRIEVAL-MIGRATION-DEPENDENCY-V1 / DOCUMENT-SEMANTIC-INDEX-V1 S8: before flipping the
reversible `POLYMATH_DOC_PROFILE_VNEXT` flag globally, prove the vNext (fingerprint +
profile_prompt_vnext) profile self-retrieves AT LEAST AS WELL as the current
lean-context profile — the existing gate (cinema top-1 85.8%, top-3 99.5%).

Evaluation-only + reversible: it generates vNext profiles (owner-authorized Groq spend)
through the EXISTING doc_profile pool, projects them to a SEPARATE canary Qdrant
collection (`polymath_document_profiles_<contract>_vnextcanary`), measures self-retrieval
there (same competitor set as production), and DELETES the canary collection at the end
(`--keep` to inspect). It never touches the production profile collection, the live
worker, chunks, or authoritative state.

    .venv/bin/python scripts/profile_vnext_selfretrieval_canary.py --corpus cinema \
        --per-doc 3 --baseline-top1 0.858 --out docs/wiki/experiments/profile-vnext-selfretrieval-2026-09-07.json
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for _p in (ROOT / "shared", ROOT / "workers", ROOT / "orchestrator", ROOT / "scripts", ROOT):
    sys.path.insert(0, str(_p))

from polymath_shared.db import tx  # noqa: E402


def _load(corpus_id, limit):
    with tx() as conn:
        docs = conn.execute(
            "SELECT doc_id, corpus_id, source_name, media_type, frontmatter, content_hash "
            "FROM documents WHERE corpus_id=%s ORDER BY source_name" + (f" LIMIT {int(limit)}" if limit else ""),
            (corpus_id,)).fetchall()
        out = []
        for d in docs:
            parents = [
                {"chunk_index": r[0], "char_start": r[1], "char_end": r[2], "heading_path": r[3],
                 "text": r[4], "region_role": r[5]}
                for r in conn.execute(
                    "SELECT chunk_index, char_start, char_end, heading_path, text, region_role FROM chunks "
                    "WHERE doc_id=%s AND tier='parent' ORDER BY chunk_index", (d[0],)).fetchall()]
            names = {d[0]: d[2]}
            out.append(({"doc_id": d[0], "corpus_id": d[1], "source_name": d[2], "media_type": d[3],
                         "frontmatter": d[4] or {}, "content_hash": d[5]}, parents, names))
        return out


def _self_retrieval(client, coll, corpus_id, probes_by_doc, embed_queries, rrf_rank, per_doc):
    per = []
    for doc_id, (name, probes) in probes_by_doc.items():
        probes = probes[:per_doc * 2]
        if not probes:
            continue
        vecs = embed_queries(probes)
        ranks = []
        for v in vecs:
            order = rrf_rank(client, coll, list(v), corpus_id)
            ranks.append(order.index(doc_id) + 1 if doc_id in order else None)
        per.append({"doc": name[:40], "probes": len(probes), "ranks": ranks,
                    "top1": sum(1 for r in ranks if r == 1), "top3": sum(1 for r in ranks if r and r <= 3)})
    total = sum(d["probes"] for d in per) or 1
    return {"documents": len(per), "probes": total,
            "top1_rate": round(sum(d["top1"] for d in per) / total, 3),
            "top3_rate": round(sum(d["top3"] for d in per) / total, 3),
            "median_rank": statistics.median([r for d in per for r in d["ranks"] if r]) if per else None}, per


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", default="cinema")
    ap.add_argument("--limit", type=int, default=0, help="cap docs (0 = whole corpus, the fair competitor set)")
    ap.add_argument("--per-doc", type=int, default=3)
    ap.add_argument("--baseline-top1", type=float, default=0.858)
    ap.add_argument("--tolerance", type=float, default=0.03, help="vNext top1 must be >= baseline - tolerance")
    ap.add_argument("--pace-s", type=float, default=1.0)
    ap.add_argument("--keep", action="store_true")
    ap.add_argument("--out", default=None)
    args = ap.parse_args(argv)

    import workers.doc_profile_worker as W
    from document_profile_gate import rrf_rank
    from orchestrator.api.fast import _embed_queries
    from polymath_shared.document_profile import compiler as C
    from polymath_shared.document_profile import fingerprint as FP
    from polymath_shared.document_profile import profile_prompt_vnext as PP
    from polymath_shared.document_profile import projection as PJ
    from polymath_shared.embedding_contracts import active_contract
    from polymath_shared.settings import get_settings
    from qdrant_client import QdrantClient

    ct = active_contract()
    prod_coll = PJ.collection_name(ct.contract_id)
    canary_contract = f"{ct.contract_id}_vnextcanary"
    canary_coll = PJ.collection_name(canary_contract)
    client = QdrantClient(url=get_settings().stores.qdrant_url, timeout=90)
    embed = lambda texts: W._embed_texts(texts)  # noqa: E731  (the doc_profile embedder path)

    cohort = _load(args.corpus, args.limit)
    if not cohort:
        print(f"no docs in corpus {args.corpus}", file=sys.stderr)
        return 1
    print(f"[canary] {len(cohort)} docs; generating + projecting vNext profiles to {canary_coll}")

    vnext_probes, errors = {}, []
    for document, parents, names in cohort:
        doc_id = document["doc_id"]
        fp = FP.build_fingerprint(document, parents)
        system, user = PP.build_vnext_profile_prompt(fp)
        raw, err, rec = W._pool_complete(system, user, 2400, run_key=f"vnext-qual-{doc_id[:8]}")
        if err or not (raw or "").strip():
            errors.append({"doc": document["source_name"], "error": err})
            continue
        result = C.compile_llm_output(raw, source_text="\n".join(p.get("text") or "" for p in parents), grounding_mode="warn")
        emitted = C.emit(result.record, doc_id)
        try:
            PJ.project_profile(client, embed=embed, embedding_contract_id=canary_contract, dim=ct.dimension,
                               doc_id=doc_id, corpus_id=document["corpus_id"], title=fp.title,
                               representations=emitted["representations"],
                               payload_extra={"source_name": document["source_name"]},
                               source_doc_hash=document.get("content_hash") or "", schema_version=C.SCHEMA_VERSION,
                               prompt_version=PP.PROFILE_VNEXT_PROMPT_VERSION, compiled_hash=W._sha(emitted["artifact"]))
        except Exception as exc:  # noqa: BLE001
            errors.append({"doc": document["source_name"], "error": f"project:{type(exc).__name__}:{exc}"[:160]})
            continue
        rec2 = result.record
        vnext_probes[doc_id] = (names[doc_id], (rec2.questions or [])[:args.per_doc] + (rec2.searches or [])[:args.per_doc])
        time.sleep(args.pace_s)

    # baseline: the CURRENT profiles' own Q/SEARCH vs the PRODUCTION collection (same doc set)
    base_probes = {}
    with tx() as conn:
        for document, _p, names in cohort:
            doc_id = document["doc_id"]
            row = conn.execute("""SELECT a.payload FROM artifacts a JOIN runs r ON r.run_id=a.run_id
                                  WHERE r.corpus_id=%s AND a.stage='doc_profile'
                                  AND a.payload->'doc_profile'->>'doc_id'=%s ORDER BY a.created_at DESC LIMIT 1""",
                               (args.corpus, doc_id)).fetchone()
            if not row:
                continue
            comp = ((row[0] if isinstance(row[0], dict) else json.loads(row[0])).get("doc_profile") or {}).get("compiled") or {}
            base_probes[doc_id] = (names[doc_id], (comp.get("questions") or [])[:args.per_doc] + (comp.get("searches") or [])[:args.per_doc])

    vnext_summary, vnext_per = _self_retrieval(client, canary_coll, args.corpus, vnext_probes, _embed_queries, rrf_rank, args.per_doc)
    base_summary, _ = _self_retrieval(client, prod_coll, args.corpus, base_probes, _embed_queries, rrf_rank, args.per_doc)

    passed = vnext_summary["top1_rate"] >= (base_summary["top1_rate"] - args.tolerance) \
        and vnext_summary["top1_rate"] >= (args.baseline_top1 - args.tolerance)
    verdict = {
        "gate": "profile-vnext-selfretrieval-v1", "corpus": args.corpus, "docs_projected": len(vnext_probes),
        "errors": errors, "recorded_baseline_top1": args.baseline_top1, "tolerance": args.tolerance,
        "baseline_same_cohort": base_summary, "vnext": vnext_summary, "PASS": bool(passed),
    }
    print(json.dumps(verdict, indent=1, ensure_ascii=False))
    if args.out:
        Path(args.out).write_text(json.dumps({"verdict": verdict, "vnext_per_doc": vnext_per}, indent=1, ensure_ascii=False))
        print("evidence ->", args.out)

    if not args.keep:
        try:
            client.delete_collection(canary_coll)
            print(f"[canary] deleted {canary_coll}")
        except Exception as exc:  # noqa: BLE001
            print(f"[canary] could not delete {canary_coll}: {exc}", file=sys.stderr)
    client.close()
    return 0 if passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
