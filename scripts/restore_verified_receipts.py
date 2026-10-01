"""Owner repair for VERIFY-FULL-SCAN-V1: switch back ON the Qdrant receipts that the one-page
verification switched off for points that ARE in the store.

Until 2026-10-01 verification read ONE page of 100,000 points and switched off the receipt of every
point past it (cinema: 165,939 points; 65,939 routing and 28,739 chunk receipts off). The points are
still in the store; only the bookkeeping was lost, and the projector would re-embed all of them
(hours of embedder time) to write receipts back. A receipt is switched back on only when ALL hold:

  1. it is OFF, its state is the projected / superseded kind (never FAILED or PENDING), and the
     corpus still WANTS the entity (verification's own want sets: routing kinds + child chunks);
  2. its point is IN THE STORE, read to the end (the same scan verification now uses; a failed read
     restores nothing);
  3. its stored hash is the hash the projector writes TODAY for that entity, so the point was last
     written under the current projection contract (anything else is left for the projector).

Dry run by default (prints the counts per kind); --execute writes everything in one transaction.

    python scripts/restore_verified_receipts.py <corpus_id>            # dry run
    python scripts/restore_verified_receipts.py <corpus_id> --execute
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
for _sub in ("control", "workers", "shared"):
    sys.path.insert(0, str(ROOT / _sub))

import psycopg  # noqa: E402

from polymath_shared.projection_contracts import (  # noqa: E402
    KIND_CHUNK,
    PROJECTION_QDRANT,
    qdrant_collection_name,
    receipt_hash,
)

RESTORABLE_STATES = ("PROJECTED", "STALE")


def expected_hash(kind: str, entity_id: str) -> str:
    """The receipt hash the projector writes today (project_qdrant_worker: chunks under CONTRACT_VERSION,
    every routing kind — summaries, children, procedures, concepts, entity cards, latent — under
    ROUTING_CONTRACT_VERSION)."""
    from workers.project_qdrant_worker import CONTRACT_VERSION, ROUTING_CONTRACT_VERSION
    version = CONTRACT_VERSION if kind == KIND_CHUNK else ROUTING_CONTRACT_VERSION
    return receipt_hash(PROJECTION_QDRANT, kind, entity_id, version)


def _off_receipts(conn, kind: str, ids: list[str]) -> dict[str, str]:
    """entity_id -> stored hash of the switched-off receipts of `kind` among `ids`."""
    if not ids:
        return {}
    rows = conn.execute(
        """SELECT entity_id, receipt_hash FROM projection_receipts
            WHERE projection = %s AND entity_kind = %s AND NOT active
              AND state = ANY(%s) AND entity_id = ANY(%s)""",
        (PROJECTION_QDRANT, kind, list(RESTORABLE_STATES), ids)).fetchall()
    return {r[0]: r[1] for r in rows}


def plan(conn, corpus_id: str, client) -> tuple[dict[str, list[str]], dict[str, dict[str, int]]]:
    """(kind -> entity ids to switch back on, kind -> counts). Reads only; raises
    VerifyStoreUnreadable when the store cannot be read to its end."""
    import workers.verify_worker as VW
    from polymath_shared.embedding_contracts import NEURAL_EMBED_CONTRACT
    from polymath_shared.projection_want import desired_chunk_ids

    want = {k: set(v) for k, v in VW._desired_routing_ids(conn, corpus_id).items()}
    on = {k: set(v) for k, v in VW._routing_receipts(conn, corpus_id).items()}
    store: dict[str, set[str]] = {k: set() for k in want}
    for p in VW._scan_points(client, qdrant_collection_name(corpus_id, NEURAL_EMBED_CONTRACT.contract_id),
                             ["representation_kind", "summary_id", "chunk_id"]):
        kind = (p.payload or {}).get("representation_kind")
        if kind in store:
            store[kind].add(str(p.payload.get("summary_id") or p.payload.get("chunk_id")))

    run = conn.execute("SELECT run_id FROM runs WHERE corpus_id = %s ORDER BY run_id LIMIT 1",
                       (corpus_id,)).fetchone()
    want[KIND_CHUNK] = set(desired_chunk_ids(conn, run[0], "qdrant")) if run else set()   # corpus-wide
    on[KIND_CHUNK] = set(VW._receipt_chunk_ids(conn, corpus_id, "qdrant"))
    store[KIND_CHUNK] = {str(p.payload["chunk_id"]) for p in VW._scan_points(
        client, qdrant_collection_name(corpus_id, VW.active_contract().contract_id), ["chunk_id"])
        if p.payload and p.payload.get("chunk_id")}

    restore: dict[str, list[str]] = {}
    counts: dict[str, dict[str, int]] = {}
    for kind in sorted(want):
        off_in_store = sorted((want[kind] & store[kind]) - on[kind])
        stored = _off_receipts(conn, kind, off_in_store)
        restore[kind] = [e for e in off_in_store if stored.get(e) == expected_hash(kind, e)]
        counts[kind] = {"wanted": len(want[kind]), "on": len(want[kind] & on[kind]),
                        "off_but_in_store": len(off_in_store), "restorable": len(restore[kind]),
                        "left_for_projector": len(want[kind] - on[kind]) - len(restore[kind])}
    return restore, counts


def apply(conn, restore: dict[str, list[str]]) -> dict[str, int]:
    """Switch the planned receipts back on; each row re-checks off + restorable state + today's hash."""
    done: dict[str, int] = {}
    for kind, ids in restore.items():
        if not ids:
            continue
        done[kind] = conn.execute(
            """UPDATE projection_receipts pr
                  SET active = TRUE, state = 'PROJECTED', written_at = now(), updated_at = now()
                 FROM unnest(%s::text[], %s::text[]) AS w(entity_id, receipt_hash)
                WHERE pr.projection = %s AND pr.entity_kind = %s AND pr.entity_id = w.entity_id
                  AND pr.receipt_hash = w.receipt_hash AND NOT pr.active AND pr.state = ANY(%s)""",
            (ids, [expected_hash(kind, e) for e in ids], PROJECTION_QDRANT, kind,
             list(RESTORABLE_STATES))).rowcount
    return done


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("corpus_id")
    ap.add_argument("--execute", action="store_true", help="apply (default: dry-run print)")
    args = ap.parse_args()

    import workers.verify_worker as VW
    from polymath_shared.settings import get_settings
    from polymath_shared.stores import qdrant_client

    if not hasattr(VW, "_scan_points"):          # an older checkout's verify_worker won on the import path
        print(f"refused: {VW.__file__} predates VERIFY-FULL-SCAN-V1; run this script from a checkout that has it")
        return 2
    client = qdrant_client()
    try:
        with psycopg.connect(get_settings().postgres.dsn, connect_timeout=5) as conn:
            restore, counts = plan(conn, args.corpus_id, client)
            print(json.dumps({"corpus_id": args.corpus_id, "per_kind": counts,
                              "restorable": sum(len(v) for v in restore.values())}, indent=1))
            if not args.execute:
                print("dry run: nothing written (add --execute)")
                conn.rollback()
                return 0
            done = apply(conn, restore)
            conn.commit()
            print(json.dumps({"restored": done, "total": sum(done.values())}))
    finally:
        client.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
