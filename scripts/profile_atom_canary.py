#!/usr/bin/env python
"""PROFILE-ATOM-CANARY-V1 — persist + project + reconcile the Profile Atom lane (R4).

FINAL-RETRIEVAL-ROUTING-SYNTHESIS-V1 R4 / §34: lift the document-profile atoms into their own
durable rows (`document_profile_atoms`) and project each as one dense point in the contract-
named atom collection, then verify the §14 reconciliation (Postgres active == Qdrant points).
Controlled + bounded to one corpus; additive (no other store touched). Atoms are routing/
expansion units, NEVER factual evidence.

    .venv/bin/python scripts/profile_atom_canary.py --corpus cinema --project \
        --out docs/wiki/experiments/profile-atom-2026-09-08.json
    .venv/bin/python scripts/profile_atom_canary.py --corpus cinema --purge-only
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for _p in (ROOT / "shared", ROOT / "orchestrator", ROOT / "scripts", ROOT):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from polymath_shared.db import tx  # noqa: E402
from polymath_shared.document_profile import compiler as C  # noqa: E402
from polymath_shared.document_profile import profile_atom as PA  # noqa: E402
from polymath_shared.document_profile import profile_atom_projection as PAP  # noqa: E402


def _compiled_profiles(corpus_id: str, limit: int | None):
    """Latest compiled doc_profile per doc for the corpus → (doc_id, compiled dict)."""
    out = {}
    with tx() as conn:
        rows = conn.execute(
            "SELECT a.payload FROM artifacts a JOIN runs r ON r.run_id=a.run_id "
            "WHERE r.corpus_id=%s AND a.stage='doc_profile' ORDER BY a.created_at DESC", (corpus_id,)
        ).fetchall()
    for row in rows:
        pl = row[0] if isinstance(row[0], dict) else json.loads(row[0])
        dp = (pl.get("doc_profile") or {})
        comp = dp.get("compiled") or {}
        doc_id = dp.get("doc_id") or comp.get("doc_id")
        if doc_id and doc_id not in out and comp:
            out[doc_id] = comp
        if limit and len(out) >= limit:
            break
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", default="cinema")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--project", action="store_true", help="embed + project atoms to Qdrant")
    ap.add_argument("--purge-only", action="store_true", help="delete the corpus's projected atom points and exit")
    ap.add_argument("--out", default="")
    args = ap.parse_args(argv)

    from orchestrator.api.fast import _embed_queries  # noqa: E402
    from polymath_shared.embedding_contracts import active_contract  # noqa: E402
    from polymath_shared.settings import get_settings  # noqa: E402
    from qdrant_client import QdrantClient  # noqa: E402

    ct = active_contract()
    client = QdrantClient(url=get_settings().stores.qdrant_url, timeout=90)

    if args.purge_only:
        removed = PAP.purge(client, ct.contract_id, args.corpus)
        print(f"[profile-atom] purged {removed} points for {args.corpus}")
        client.close()
        return 0

    profile_contract = C.SCHEMA_VERSION
    compiled = _compiled_profiles(args.corpus, args.limit or None)
    if not compiled:
        print(f"no compiled doc_profiles for corpus {args.corpus}", file=sys.stderr)
        return 1

    # 1. extract + persist atoms (Postgres authority).
    kinds = Counter()
    total = 0
    with tx() as conn:
        for doc_id, comp in compiled.items():
            atoms = PA.extract_atoms(comp, doc_id=doc_id, corpus_id=args.corpus, profile_contract=profile_contract)
            PA.persist_atoms(conn, doc_id=doc_id, profile_contract=profile_contract, atoms=atoms)
            for a in atoms:
                kinds[a.kind] += 1
            total += len(atoms)
    print(f"[profile-atom] {len(compiled)} docs → {total} active atoms; by kind: {dict(kinds)}")

    receipt = {"corpus": args.corpus, "docs": len(compiled), "atoms": total,
               "by_kind": dict(kinds), "profile_contract": profile_contract}

    # 2. project (embed each atom text once) + reconcile.
    if args.project:
        # §14: the atom collection is a rebuildable cache of the ACTIVE rows. A regen that
        # SUPERSEDES atoms (fewer/different) leaves the old points behind, so purge the corpus's
        # points first and rebuild from the active set — otherwise reconcile (active == projected)
        # fails on the stale accumulation.
        PAP.purge(client, ct.contract_id, args.corpus)
        with tx() as conn:
            atoms = PA.active_atoms(conn, corpus_id=args.corpus)
        proj = PAP.project_atoms(client, embed=_embed_queries, embedding_contract_id=ct.contract_id,
                                 dim=ct.dimension, atoms=atoms)
        with tx() as conn:
            rec = PAP.reconcile(conn, client, corpus_id=args.corpus, embedding_contract_id=ct.contract_id)
        receipt.update({"projected_points": proj["points"], "collection": proj["collection"], "reconcile": rec})
        print(f"[profile-atom] projected {proj['points']} points → reconcile: {rec['reconciled']} "
              f"(active={rec['active_atoms']} == projected={rec['projected_points']})")

    print(json.dumps(receipt, indent=2, default=str))
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(json.dumps(receipt, indent=2, default=str))
        print(f"[profile-atom] wrote {args.out}")
    client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
