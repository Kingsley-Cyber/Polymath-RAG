#!/usr/bin/env python
"""ATOM-REPAIR-V1 — restore the base-profile atoms beside the vNext atoms (owner 2026-09-24: "go ahead with the atom repair";
decision D4: base atoms ALONGSIDE the vNext atoms, deduplicated, projection only — no LLM call).

What went wrong: on 2026-09-08 the vNext research-index profile (ONE item per kind) was persisted through a whole-document
supersession, which deactivated every base (v3.2) atom — ~10 theories / concepts / seealso per book — while the global profile
point kept the richer v3.2 profile. Cinema: 609 atoms active (1 per kind per book), 1,844 base atoms inactive.

This script re-derives BOTH families from each book's own compiled `doc_profile` artifacts (the latest base and the latest
vNext artifact) and persists them family-scoped (`profile_atom.persist_atoms(source="family:compiled_hash")`), so neither
family can supersede the other again. It then projects the missing atom points in the collection's QUERY embedding mode (the
mode of the live points) and reconciles Postgres active rows == Qdrant points.

Dry run by default: counts only, nothing written. `--execute` refuses without `--backup-dir`, writes the backup there first
(every atom row of the corpus + the corpus's atom points WITH vectors), then repairs. `--restore <dir>` puts both stores back.

    .venv/bin/python scripts/repair_profile_atoms.py --corpus cinema
    .venv/bin/python scripts/repair_profile_atoms.py --corpus cinema --execute --backup-dir ~/PolymathBackups/atom-repair-2026-09-24 \\
        --out docs/wiki/experiments/atom-repair-2026-09-24/receipt.json
    .venv/bin/python scripts/repair_profile_atoms.py --corpus cinema --restore ~/PolymathBackups/atom-repair-2026-09-24
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
for _p in (ROOT / "shared", ROOT):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from polymath_shared.document_profile import profile_atom as PA


def family_profiles(rows) -> dict[str, dict[str, dict]]:
    """Pure. `rows` = (artifact_id, created_at, payload) of `doc_profile` artifacts, OLDEST first. Returns
    {doc_id: {"base" | "vnext": {"compiled", "compiled_hash", "artifact_id", "prompt_version"}}} — the LATEST artifact of each
    family per document (a later artifact of the same family replaces an earlier one)."""
    out: dict[str, dict[str, dict]] = {}
    for artifact_id, _created, payload in rows:
        pl = payload if isinstance(payload, dict) else json.loads(payload)
        dp = pl.get("doc_profile") or {}
        comp = dp.get("compiled") or {}
        doc_id = dp.get("doc_id") or comp.get("doc_id")
        if not doc_id or not comp:
            continue
        fam = "vnext" if dp.get("vnext") else "base"
        out.setdefault(doc_id, {})[fam] = {"compiled": comp, "compiled_hash": dp.get("compiled_hash") or "",
                                           "artifact_id": artifact_id, "prompt_version": dp.get("prompt_version")}
    return out


def plan(profiles: dict[str, dict[str, dict]], *, corpus_id: str, profile_contract: str) -> dict[str, list[tuple[str, list]]]:
    """Pure. Per document, the family-scoped persists to run: [(source, atoms)], vNext first (it retags the untagged live rows),
    then base. Atoms are `profile_atom.extract_atoms` of that family's compiled profile (deduped by content id within the
    family; identical text across families shares one row)."""
    out: dict[str, list[tuple[str, list]]] = {}
    for doc_id, fams in sorted(profiles.items()):
        steps = []
        for fam in ("vnext", "base"):
            f = fams.get(fam)
            if not f:
                continue
            atoms = PA.extract_atoms(f["compiled"], doc_id=doc_id, corpus_id=corpus_id, profile_contract=profile_contract)
            steps.append((PA.source_tag(fam, f["compiled_hash"]), atoms))
        if steps:
            out[doc_id] = steps
    return out


def _embed_query_mode(texts: list[str]) -> list[list[float]]:
    """The collection's mode (query), background priority (live chat outranks it on the device), ≤ the sidecar's batch cap."""
    from polymath_shared.clients import EmbedderClient
    size = max(1, int(os.environ.get("POLYMATH_MAX_BATCH_TEXTS", "8")))
    client = EmbedderClient()
    try:
        out: list[list[float]] = []
        for i in range(0, len(texts), size):
            out.extend(list(v) for v in client.embed(texts[i:i + size], "query")["vectors"])
        return out
    finally:
        client.close()


def _atom_rows(conn, corpus_id: str) -> list[dict]:
    cols = ("atom_id", "doc_id", "corpus_id", "profile_contract", "atom_kind", "atom_text", "ordinal", "source_profile_hash",
            "active", "created_at", "updated_at")
    rows = conn.execute(f"SELECT {', '.join(cols)} FROM document_profile_atoms WHERE corpus_id=%s ORDER BY atom_id",
                        (corpus_id,)).fetchall()
    return [dict(zip(cols, r)) for r in rows]


def _corpus_points(client, collection: str, corpus_id: str, *, with_vectors: bool) -> list:
    from qdrant_client.http import models as qm
    flt = qm.Filter(must=[qm.FieldCondition(key="corpus_id", match=qm.MatchValue(value=corpus_id))])
    out, offset = [], None
    while True:
        pts, offset = client.scroll(collection, scroll_filter=flt, limit=256, offset=offset,
                                    with_payload=True, with_vectors=with_vectors)
        out.extend(pts)
        if offset is None:
            return out


def _summary(rows: list[dict]) -> dict:
    act = Counter(r["atom_kind"] for r in rows if r["active"])
    ina = Counter(r["atom_kind"] for r in rows if not r["active"])
    return {"active": sum(act.values()), "inactive": sum(ina.values()), "active_by_kind": dict(sorted(act.items())),
            "inactive_by_kind": dict(sorted(ina.items())),
            "active_docs": len({r["doc_id"] for r in rows if r["active"]})}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", default="cinema")
    ap.add_argument("--execute", action="store_true")
    ap.add_argument("--backup-dir", type=Path)
    ap.add_argument("--restore", type=Path)
    ap.add_argument("--out", type=Path)
    args = ap.parse_args(argv)

    from polymath_shared.db import tx
    from polymath_shared.document_profile import compiler as C
    from polymath_shared.document_profile import profile_atom_projection as PAP
    from polymath_shared.embedding_contracts import active_contract
    from polymath_shared.settings import get_settings
    from qdrant_client import QdrantClient
    from qdrant_client.http import models as qm

    ct = active_contract()
    collection = PAP.collection_name(ct.contract_id)
    client = QdrantClient(url=get_settings().stores.qdrant_url, timeout=120)

    if args.restore:
        return _restore(args, client, collection, tx, qm)

    with tx() as conn:
        before_rows = _atom_rows(conn, args.corpus)
        art = conn.execute("SELECT a.artifact_id, a.created_at, a.payload FROM artifacts a JOIN runs r ON r.run_id=a.run_id "
                           "WHERE r.corpus_id=%s AND a.stage='doc_profile' AND a.payload ? 'doc_profile' "
                           "ORDER BY a.created_at, a.artifact_id", (args.corpus,)).fetchall()
    profiles = family_profiles(art)
    steps = plan(profiles, corpus_id=args.corpus, profile_contract=C.SCHEMA_VERSION)
    by_id = {r["atom_id"]: r for r in before_rows}
    target = {a.atom_id: (src, a) for doc_steps in steps.values() for src, atoms in doc_steps for a in atoms}
    active_now = {r["atom_id"] for r in before_rows if r["active"]}
    vnext_ids = {a.atom_id for doc_steps in steps.values() for src, atoms in doc_steps if src.startswith("vnext:") for a in atoms}
    report = {
        "corpus": args.corpus, "profile_contract": C.SCHEMA_VERSION, "collection": collection,
        "docs": len(profiles), "docs_with_base": sum(1 for f in profiles.values() if "base" in f),
        "docs_with_vnext": sum(1 for f in profiles.values() if "vnext" in f),
        "before": _summary(before_rows),
        "target_atoms": len(target), "target_by_kind": dict(sorted(Counter(a.kind for _, a in target.values()).items())),
        "reactivate": sum(1 for aid in target if aid in by_id and not by_id[aid]["active"]),
        "new_rows": sum(1 for aid in target if aid not in by_id),
        "already_active": sum(1 for aid in target if aid in active_now),
        "would_deactivate": len(active_now - set(target)),
        "live_equals_vnext": active_now == vnext_ids,
    }
    print(json.dumps(report, indent=1, default=str))
    if not args.execute:
        print("DRY RUN — nothing written. Re-run with --execute --backup-dir <dir>.")
        return 0
    if not args.backup_dir:
        print("refusing: --execute needs --backup-dir (the rollback source)", file=sys.stderr)
        return 2

    # 1. backup — every atom row of the corpus + its points with vectors
    args.backup_dir.mkdir(parents=True, exist_ok=True)
    pts = _corpus_points(client, collection, args.corpus, with_vectors=True)
    with (args.backup_dir / "atom_rows.jsonl").open("w") as f:
        for r in before_rows:
            f.write(json.dumps(r, default=str) + "\n")
    with (args.backup_dir / "atom_points.jsonl").open("w") as f:
        for p in pts:
            vec = p.vector.get(PAP.VECTOR_NAME) if isinstance(p.vector, dict) else p.vector
            f.write(json.dumps({"id": str(p.id), "vector": list(vec or []), "payload": p.payload}) + "\n")
    (args.backup_dir / "manifest.json").write_text(json.dumps(
        {"corpus": args.corpus, "collection": collection, "rows": len(before_rows), "points": len(pts),
         "taken_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}, indent=1))
    print(f"backup: {len(before_rows)} rows, {len(pts)} points → {args.backup_dir}")

    # 2. family-scoped persist, one transaction per document
    t0 = time.perf_counter()
    for doc_id, doc_steps in steps.items():
        with tx() as conn:
            for src, atoms in doc_steps:
                PA.persist_atoms(conn, doc_id=doc_id, profile_contract=C.SCHEMA_VERSION, atoms=atoms, source=src)
    persist_s = round(time.perf_counter() - t0, 1)

    # 3. projection — the points the active set lacks (query mode), and no point for an inactive atom
    with tx() as conn:
        active = PA.active_atoms(conn, corpus_id=args.corpus)
    have = {str(p.id) for p in _corpus_points(client, collection, args.corpus, with_vectors=False)}
    want = {PAP.point_id(a.atom_id): a for a in active}
    missing = [a for pid, a in want.items() if pid not in have]
    orphans = sorted(have - set(want))
    t1 = time.perf_counter()
    proj = PAP.project_atoms(client, embed=_embed_query_mode, embedding_contract_id=ct.contract_id, dim=ct.dimension,
                             atoms=missing) if missing else {"points": 0}
    if orphans:
        client.delete(collection_name=collection, points_selector=qm.PointIdsList(points=orphans), wait=True)
    project_s = round(time.perf_counter() - t1, 1)

    with tx() as conn:
        after_rows = _atom_rows(conn, args.corpus)
        rec = PAP.reconcile(conn, client, corpus_id=args.corpus, embedding_contract_id=ct.contract_id)
    receipt = {**report, "after": _summary(after_rows), "projected_new_points": proj["points"], "deleted_orphans": len(orphans),
               "reconcile": rec, "persist_s": persist_s, "project_s": project_s,
               "sources": dict(Counter((r["source_profile_hash"] or "untagged").split(":", 1)[0]
                                       for r in after_rows if r["active"])),
               "backup_dir": str(args.backup_dir)}
    print(json.dumps({k: receipt[k] for k in ("after", "projected_new_points", "deleted_orphans", "reconcile", "sources",
                                               "persist_s", "project_s")}, indent=1, default=str))
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(receipt, indent=1, default=str))
    client.close()
    return 0 if rec.get("reconciled") else 1


def _restore(args, client, collection: str, tx, qm) -> int:
    """Put both stores back exactly as the backup recorded them: every backed-up row's active flag / ordinal / source,
    rows the repair added are removed, and the corpus's points are replaced by the backed-up points."""
    rows = [json.loads(line) for line in (args.restore / "atom_rows.jsonl").read_text().splitlines() if line.strip()]
    pts = [json.loads(line) for line in (args.restore / "atom_points.jsonl").read_text().splitlines() if line.strip()]
    keep = {r["atom_id"] for r in rows}
    with tx() as conn:
        now_ids = {r[0] for r in conn.execute("SELECT atom_id FROM document_profile_atoms WHERE corpus_id=%s",
                                              (args.corpus,)).fetchall()}
        added = sorted(now_ids - keep)
        if added:
            conn.execute("DELETE FROM document_profile_atoms WHERE atom_id = ANY(%s)", (added,))
        for r in rows:
            conn.execute("UPDATE document_profile_atoms SET active=%s, ordinal=%s, source_profile_hash=%s, updated_at=now() "
                         "WHERE atom_id=%s", (r["active"], r["ordinal"], r["source_profile_hash"], r["atom_id"]))
    client.delete(collection_name=collection, points_selector=qm.FilterSelector(filter=qm.Filter(must=[
        qm.FieldCondition(key="corpus_id", match=qm.MatchValue(value=args.corpus))])), wait=True)
    for i in range(0, len(pts), 256):
        client.upsert(collection_name=collection, wait=True, points=[
            qm.PointStruct(id=p["id"], vector={"atom": p["vector"]}, payload=p["payload"]) for p in pts[i:i + 256]])
    print(f"restored {len(rows)} rows ({len(added)} added rows removed) and {len(pts)} points")
    return 0


if __name__ == "__main__":
    sys.exit(main())
