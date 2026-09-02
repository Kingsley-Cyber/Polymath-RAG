"""ENRICH-IDENTITY-V2 one-time re-key: parent_enrichments.input_hash was
computed WITH the lane name + model inside it, so every pin-group change
re-sharded parents onto other lanes, minted new identities, and the
summaries worker re-enriched the whole corpus (measured 2026-09-02: 1,309
rows in one day for a 1,374-parent corpus; a new upload queued behind a
full re-enrichment of nine finished books). The identity is now
(source_hash, prompt_hash, compiler contract + output bounds) — the lane
is provenance (provider/model columns), not identity.

    .venv/bin/python scripts/migrate_enrichment_identity.py            # dry run
    .venv/bin/python scripts/migrate_enrichment_identity.py --execute

Idempotent: rows already carrying the lane-free hash are untouched. Rows
locked by a running worker transaction are SKIPPED (SKIP LOCKED) and
reported — re-run until `locked_skipped` is 0. Never deletes; READY rows
keep their enrichment_id (the projector's key). Batched: one UPDATE per
500 rows, `lock_timeout` 5 s.
"""
from __future__ import annotations

import argparse
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "shared"))

import psycopg  # noqa: E402

from polymath_shared.identity import content_hash  # noqa: E402
from polymath_shared.latent.contract import (  # noqa: E402
    COMPILER_CONTRACT,
    PRODUCTION_BOUNDS,
    QUALIFICATION_BOUNDS,
)
from polymath_shared.latent.prompt import prompt_hash  # noqa: E402
from polymath_shared.settings import get_settings  # noqa: E402


def contract_id(max_tokens: int) -> str:
    # MUST match polymath_shared.latent.runtime.enrichment_contract_id
    return f"{COMPILER_CONTRACT}|tokens={int(max_tokens)}"


def lane_free_hash(source_hash: str, max_tokens: int) -> str:
    # MUST match polymath_shared.latent.runtime.input_hash_for
    return content_hash({"source": source_hash, "prompt": prompt_hash(),
                         "model": contract_id(max_tokens)})


def rekey(conn, *, max_tokens: int, execute: bool, batch: int = 500) -> dict:
    rows = conn.execute(
        "SELECT enrichment_id, source_hash, input_hash, status FROM parent_enrichments"
    ).fetchall()
    todo: list[tuple[str, str, str]] = []      # (new_hash, enrichment_id, status)
    same = 0
    for eid, sh, ih, status in rows:
        new = lane_free_hash(sh, max_tokens)
        if new == ih:
            same += 1
        else:
            todo.append((new, eid, status))
    changed = {"READY": 0, "INVALID": 0, "STALE": 0}
    locked_skipped = 0
    if execute:
        conn.execute("SET LOCAL lock_timeout = '5s'")
        for i in range(0, len(todo), batch):
            chunk = todo[i:i + batch]
            ids = [eid for _, eid, _ in chunk]
            # take only rows no worker transaction is holding
            free = {r[0] for r in conn.execute(
                "SELECT enrichment_id FROM parent_enrichments WHERE enrichment_id = ANY(%s) "
                "FOR UPDATE SKIP LOCKED", (ids,)).fetchall()}
            locked_skipped += len(ids) - len(free)
            values = [(new, eid) for new, eid, _ in chunk if eid in free]
            if values:
                conn.execute(
                    "UPDATE parent_enrichments AS p SET input_hash = v.new_hash "
                    "FROM (SELECT unnest(%s::text[]) AS new_hash, unnest(%s::text[]) AS eid) v "
                    "WHERE p.enrichment_id = v.eid",
                    ([v[0] for v in values], [v[1] for v in values]))
            for new, eid, status in chunk:
                if eid in free:
                    changed[status] = changed.get(status, 0) + 1
    else:
        for _, _, status in todo:
            changed[status] = changed.get(status, 0) + 1
    return {"rows": len(rows), "already_lane_free": same, "rekeyed": changed,
            "locked_skipped": locked_skipped, "executed": execute}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--execute", action="store_true")
    args = ap.parse_args()
    w = get_settings().worker
    bounds = PRODUCTION_BOUNDS if getattr(w, "enrichment_profile", "qualification") == "production" \
        else QUALIFICATION_BOUNDS
    with psycopg.connect(get_settings().postgres.dsn, autocommit=False) as conn:
        out = rekey(conn, max_tokens=bounds.max_tokens, execute=args.execute)
        if args.execute:
            conn.commit()
        else:
            conn.rollback()
    print(f"enrichment identity re-key ({'EXECUTED' if args.execute else 'dry run'}; "
          f"profile={getattr(w, 'enrichment_profile', 'qualification')} tokens={bounds.max_tokens}): {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
