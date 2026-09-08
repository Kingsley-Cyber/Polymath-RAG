#!/usr/bin/env python
"""PARENT-MAP-PROJECTION-CANARY-V1 — the step-4 projection reconciliation gate.

RETRIEVAL-MIGRATION-DEPENDENCY-V1 §9.2/§14, DOCUMENT-SEMANTIC-INDEX-V1 S10/step 4:
project the ACTIVE maps of a controlled cohort (written by parent_map_canary) to the
contract-scoped parent-map Qdrant collection, then verify:

  * Postgres authoritative active-map count == projected point count (per doc + total);
  * purge/rebuild handling (delete a doc's points -> 0 -> re-project -> restored).

Reuses `parent_map_projection` (the deterministic contract) + the embedder + Qdrant. It
writes to the ADDITIVE contract-named collection `polymath_document_parent_maps_<contract>`
only (never the chunk/profile/summary collections). Owner-authorized Qdrant projection;
bounded to the cohort. `--purge-only` removes the cohort's points (rollback).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for _p in (ROOT / "shared", ROOT / "workers", ROOT):
    sys.path.insert(0, str(_p))

from polymath_shared.db import tx  # noqa: E402


def _cohort(corpus_id, n):
    with tx() as conn:
        docs = conn.execute("SELECT doc_id, corpus_id, source_name FROM documents WHERE corpus_id=%s "
                            "ORDER BY source_name LIMIT %s", (corpus_id, n)).fetchall()
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


def _active_maps(conn, doc_id, contract):
    from polymath_shared.document_profile.map_compiler import CompiledMap
    rows = conn.execute(
        "SELECT alias, parent_id, routing_signature, semantic_hooks, exact_identifiers, map_hash, quality_flags "
        "FROM document_parent_maps WHERE doc_id=%s AND map_contract=%s AND active ORDER BY alias",
        (doc_id, contract)).fetchall()
    maps = []
    for a, pid, sig, hooks, idents, mh, qf in rows:
        maps.append(CompiledMap(alias=a, parent_id=pid, routing_signature=sig,
                                semantic_hooks=tuple(hooks or []), exact_identifiers=tuple(idents or []),
                                map_hash=mh, quality_flags=tuple(qf or [])))
    return maps


def _projected_count(client, coll, doc_id):
    from qdrant_client.http import models as qm
    if not client.collection_exists(coll):
        return 0
    return client.count(coll, count_filter=qm.Filter(
        must=[qm.FieldCondition(key="doc_id", match=qm.MatchValue(value=doc_id))]), exact=True).count


def _purge(client, coll, doc_id):
    from qdrant_client.http import models as qm
    if client.collection_exists(coll):
        client.delete(coll, points_selector=qm.FilterSelector(filter=qm.Filter(
            must=[qm.FieldCondition(key="doc_id", match=qm.MatchValue(value=doc_id))])), wait=True)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", default="cinema")
    ap.add_argument("--docs", type=int, default=3)
    ap.add_argument("--purge-only", action="store_true")
    ap.add_argument("--out", default=None)
    args = ap.parse_args(argv)

    import workers.doc_profile_worker as W
    from polymath_shared.document_profile import map_compiler
    from polymath_shared.document_profile import parent_map_projection as PMP
    from polymath_shared.document_profile.parent_skeleton import build_parent_skeletons
    from polymath_shared.embedding_contracts import active_contract
    from polymath_shared.settings import get_settings
    from qdrant_client import QdrantClient

    contract = map_compiler.MAP_COMPILER_VERSION
    ct = active_contract()
    coll = PMP.collection_name(ct.contract_id)
    client = QdrantClient(url=get_settings().stores.qdrant_url, timeout=90)
    cohort = _cohort(args.corpus, args.docs)
    if not cohort:
        print(f"no docs in {args.corpus}", file=sys.stderr)
        return 1

    if args.purge_only:
        for doc_id, *_ in cohort:
            _purge(client, coll, doc_id)
        print(f"[canary] purged {len(cohort)} docs from {coll}")
        client.close()
        return 0

    report = {"gate": "parent-map-projection-canary-v1", "collection": coll, "contract": contract, "docs": []}
    all_ok = True
    for doc_id, corpus_id, name, parents in cohort:
        with tx() as conn:
            maps = _active_maps(conn, doc_id, contract)
        if not maps:
            report["docs"].append({"doc": name[:44], "active_maps": 0, "skipped": "no active maps (run parent_map_canary first)"})
            continue
        manifest = build_parent_skeletons(parents)
        receipt = PMP.project_parent_maps(client, embed=lambda t: W._embed_texts(t),
                                          embedding_contract_id=ct.contract_id, dim=ct.dimension,
                                          doc_id=doc_id, corpus_id=corpus_id, maps=maps, manifest=manifest,
                                          map_contract=contract)
        projected = _projected_count(client, coll, doc_id)
        recon = PMP.reconcile(active_map_count=len(maps), projected_point_count=projected)
        # purge/rebuild: delete -> 0 -> re-project -> restored
        _purge(client, coll, doc_id)
        after_purge = _projected_count(client, coll, doc_id)
        PMP.project_parent_maps(client, embed=lambda t: W._embed_texts(t), embedding_contract_id=ct.contract_id,
                                dim=ct.dimension, doc_id=doc_id, corpus_id=corpus_id, maps=maps, manifest=manifest,
                                map_contract=contract)
        rebuilt = _projected_count(client, coll, doc_id)
        doc_ok = recon["ok"] and after_purge == 0 and rebuilt == len(maps)
        all_ok = all_ok and doc_ok
        report["docs"].append({"doc": name[:44], "active_maps": len(maps), "projected_points": projected,
                               "reconcile_ok": recon["ok"], "purged_to": after_purge, "rebuilt_to": rebuilt,
                               "points_written": receipt["points"], "ok": doc_ok})
        print(f"  {name[:44]:44} maps={len(maps)} projected={projected} reconcile={recon['ok']} "
              f"purge->{after_purge} rebuild->{rebuilt} ok={doc_ok}")

    report["PASS"] = bool(all_ok)
    print(json.dumps({k: report[k] for k in ("gate", "collection", "PASS")}, indent=1))
    if args.out:
        Path(args.out).write_text(json.dumps(report, indent=1, ensure_ascii=False))
        print("evidence ->", args.out)
    client.close()
    return 0 if all_ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
