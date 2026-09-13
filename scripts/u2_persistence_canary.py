#!/usr/bin/env python
"""U-2 PERSISTENCE CANARY — prove the WHOLE pMAP chain, not just the provider call.

The 11.192 forensic probe deliberately persisted nothing, so it could not close the
owner's accounting question:

    provider response -> MappingOutcome -> compiler -> durable pMAP -> projection

This instrument does. It runs ONE bounded document through the REAL production path
(mint a doc_parent_map ticket; the supervised stage worker claims it) and reconciles
the full invariant:

    requested -> dispatched -> provider outcome -> compiled/excluded/error
              -> persisted -> projected

BOUNDED BY CONSTRUCTION:
  * one document, named on the command line (default: the 5-parent cinema document)
  * it is NOT a backfill — exactly one ticket is minted, for one run
  * POLYMATH_DOC_PARENT_MAP_CORPUS is NOT touched: auto-mint stays scoped to rag-canary
  * --dry-run captures the before-state and mints nothing

Usage:
    .venv/bin/python scripts/u2_persistence_canary.py --dry-run
    .venv/bin/python scripts/u2_persistence_canary.py --execute [--timeout 600]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "shared"))

import psycopg  # noqa: E402
import urllib.request  # noqa: E402

DEFAULT_DOC = "doc_6a5301e0043db44f"
QDRANT = os.environ.get("POLYMATH_QDRANT_URL", "http://127.0.0.1:6334")


def dsn() -> str:
    return os.environ["POLYMATH_PG_DSN"]


def _q(conn, sql, args=()):
    return conn.execute(sql, args).fetchall()


def resolve(conn, doc_prefix: str) -> dict:
    rows = _q(conn, "SELECT doc_id, corpus_id, source_name, source_parent_count "
                    "FROM documents WHERE doc_id LIKE %s", (doc_prefix + "%",))
    if len(rows) != 1:
        raise SystemExit(f"doc prefix {doc_prefix!r} matched {len(rows)} documents")
    doc_id, corpus_id, source_name, parents = rows[0]
    runs = _q(conn, "SELECT run_id, status FROM runs WHERE corpus_id=%s "
                    "AND metadata->>'source_name'=%s ORDER BY created_at", (corpus_id, source_name))
    if not runs:
        raise SystemExit(f"no run found for {source_name!r}")
    return {"doc_id": doc_id, "corpus_id": corpus_id, "source_name": source_name,
            "source_parent_count": parents, "run_id": runs[-1][0], "run_status": runs[-1][1]}


def qdrant_points(doc_id: str) -> dict:
    """Projection receipts: how many parent-map points exist for this document."""
    out: dict = {"collections": {}, "total": 0, "error": None}
    try:
        with urllib.request.urlopen(f"{QDRANT}/collections", timeout=10) as r:
            cols = [c["name"] for c in json.load(r)["result"]["collections"]
                    if "parent_map" in c["name"]]
        for col in cols:
            body = json.dumps({"filter": {"must": [{"key": "doc_id", "match": {"value": doc_id}}]},
                               "exact": True}).encode()
            req = urllib.request.Request(f"{QDRANT}/collections/{col}/points/count", data=body,
                                         headers={"content-type": "application/json"})
            with urllib.request.urlopen(req, timeout=15) as r:
                n = json.load(r)["result"]["count"]
            out["collections"][col] = n
            out["total"] += n
    except Exception as exc:  # noqa: BLE001
        out["error"] = f"{type(exc).__name__}: {exc}"
    return out


def limiter_state(conn, lanes: list[str]) -> dict:
    keys = [f"llm_cloud[{l}]" for l in lanes]
    rows = _q(conn, "SELECT key, state FROM llm_controller_state WHERE key = ANY(%s)", (keys,))
    out = {}
    for key, state in rows:
        name = key[len("llm_cloud["):-1] if key.startswith("llm_cloud[") else key
        s = state if isinstance(state, dict) else {}
        out[name] = {"day_count": s.get("day_count"), "effective": s.get("effective"),
                     "ceiling": s.get("ceiling"), "decreases": s.get("decreases"),
                     "increases": s.get("increases")}
    return out


def pmap_lanes() -> list[str]:
    cfg = json.loads(Path("config/cloud_providers.json").read_text())
    return list((cfg.get("stage_pins") or {}).get("doc_parent_map") or [])


def snapshot(conn, tgt: dict, lanes: list[str]) -> dict:
    doc_id = tgt["doc_id"]
    maps = _q(conn, "SELECT map_id, parent_id, map_contract, provider, model, active "
                    "FROM document_parent_maps WHERE doc_id=%s ORDER BY parent_id", (doc_id,))
    batches = _q(conn, "SELECT batch_id, status, expected_count, valid_count, attempt_count, "
                       "raw_response_hash, provider, model, last_error "
                       "FROM document_parent_map_batches WHERE doc_id=%s ORDER BY ordinal", (doc_id,))
    tickets = _q(conn, "SELECT ticket_id, status, attempt, last_error_note FROM stage_tickets "
                       "WHERE run_id=%s AND stage='doc_parent_map'", (tgt["run_id"],))
    arts = _q(conn, "SELECT a.payload->'doc_parent_map' FROM artifacts a "
                    "WHERE a.run_id=%s AND a.stage='doc_parent_map'", (tgt["run_id"],))
    return {
        "at": datetime.now(timezone.utc).isoformat(),
        "maps_active": sum(1 for m in maps if m[5]),
        "maps_total": len(maps),
        "map_ids": sorted(m[0] for m in maps),
        "mapped_parent_ids": sorted(m[1] for m in maps if m[5]),
        "batches": [dict(zip(["batch_id", "status", "expected_count", "valid_count",
                              "attempt_count", "raw_response_hash", "provider", "model",
                              "last_error"], b)) for b in batches],
        "tickets": [dict(zip(["ticket_id", "status", "attempt", "last_error_note"], t)) for t in tickets],
        "artifacts": [a[0] for a in arts],
        "projection": qdrant_points(doc_id),
        "limiter": limiter_state(conn, lanes),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--doc", default=DEFAULT_DOC)
    ap.add_argument("--execute", action="store_true", help="mint the ticket (otherwise dry-run)")
    ap.add_argument("--timeout", type=int, default=600)
    ap.add_argument("--out", default="docs/wiki/experiments/u2-persistence-canary-2026-09-10")
    a = ap.parse_args()

    conn = psycopg.connect(dsn(), autocommit=True)
    lanes = pmap_lanes()
    tgt = resolve(conn, a.doc)
    print(f"TARGET  {tgt['doc_id'][:24]}  corpus={tgt['corpus_id']}  parents={tgt['source_parent_count']}")
    print(f"        run={tgt['run_id'][:28]}  status={tgt['run_status']}")
    print(f"        pMAP pin: {lanes}")

    before = snapshot(conn, tgt, lanes)
    print(f"BEFORE  maps_active={before['maps_active']} batches={len(before['batches'])} "
          f"tickets={len(before['tickets'])} projected={before['projection']['total']}")
    for ln, st in sorted(before["limiter"].items()):
        print(f"        limiter {ln:24} day_count={st['day_count']}")

    report = {"contract": "u2-persistence-canary-v1", "target": tgt, "pmap_pin": lanes,
              "before": before, "executed": bool(a.execute)}
    outdir = Path(a.out); outdir.mkdir(parents=True, exist_ok=True)

    if not a.execute:
        (outdir / "before.json").write_text(json.dumps(report, indent=2, default=str) + "\n")
        print("\nDRY RUN — nothing minted. Before-state written.")
        return 0

    # ── mint ONE ticket through the production mint path ────────────────────
    from polymath_shared.document_profile.map_trigger import mint_doc_parent_map
    with psycopg.connect(dsn()) as w:
        with w.cursor() as cur:
            minted = mint_doc_parent_map(cur, corpus_id=tgt["corpus_id"], run_id=tgt["run_id"])
        w.commit()
    print(f"\nMINTED  ticket={minted['ticket_id'][:28]} (ONE ticket, one run — not a backfill)")
    report["minted"] = minted

    # ── wait for the supervised worker to finish it ─────────────────────────
    t0 = time.time()
    last = None
    while time.time() - t0 < a.timeout:
        rows = _q(conn, "SELECT status, attempt, last_error_note FROM stage_tickets "
                        "WHERE ticket_id=%s", (minted["ticket_id"],))
        st = rows[0] if rows else None
        if st and st[0] != last:
            print(f"  [{time.time()-t0:6.1f}s] ticket status={st[0]} attempt={st[1]}"
                  + (f" err={str(st[2])[:60]}" if st[2] else ""))
            last = st[0]
        if st and st[0] in ("done", "failed"):
            break
        time.sleep(3)
    report["wall_s"] = round(time.time() - t0, 1)

    after = snapshot(conn, tgt, lanes)
    report["after"] = after
    print(f"\nAFTER   maps_active={after['maps_active']} batches={len(after['batches'])} "
          f"projected={after['projection']['total']}  ({report['wall_s']}s)")

    report["reconciliation"] = reconcile(before, after, tgt)
    (outdir / "canary-result.json").write_text(json.dumps(report, indent=2, default=str) + "\n")
    print("\n" + json.dumps(report["reconciliation"], indent=2, default=str))
    return 0 if report["reconciliation"]["reconciles"] else 1


def reconcile(before: dict, after: dict, tgt: dict) -> dict:
    art = (after["artifacts"] or [None])[-1] or {}
    new_batches = [b for b in after["batches"]
                   if b["batch_id"] not in {x["batch_id"] for x in before["batches"]}]
    requested = sum(b["expected_count"] or 0 for b in new_batches)
    returned = sum(b["valid_count"] or 0 for b in new_batches)
    dispatched = art.get("http_dispatches")
    persisted_delta = after["maps_active"] - before["maps_active"]
    projected_delta = (after["projection"]["total"] or 0) - (before["projection"]["total"] or 0)
    limiter_delta = {
        ln: (after["limiter"].get(ln, {}).get("day_count") or 0)
            - (before["limiter"].get(ln, {}).get("day_count") or 0)
        for ln in set(before["limiter"]) | set(after["limiter"])
    }
    accounted = sum(int(art.get(k) or 0) for k in
                    ("compiler_complete", "compiler_partial", "compiler_invalid",
                     "empty_completions", "http_failures", "http_429"))
    checks = {
        "requested_equals_eligible": requested == (art.get("eligible_parents") or requested),
        "returned_equals_persisted": returned == persisted_delta,
        "persisted_equals_projected": persisted_delta == projected_delta,
        "dispatch_fully_accounted": dispatched is not None and dispatched == accounted,
        "limiter_matches_dispatch": sum(limiter_delta.values()) == (dispatched or 0),
        "no_unresolved_left": (art.get("parents_mapped") or 0) == (art.get("eligible_parents") or -1),
    }
    return {
        "requested_parents": requested,
        "eligible_parents": art.get("eligible_parents"),
        "excluded_parents": art.get("excluded_parents"),
        "http_dispatches": dispatched,
        "limiter_refusals": art.get("limiter_refusals"),
        "http_429": art.get("http_429"),
        "http_failures": art.get("http_failures"),
        "empty_completions": art.get("empty_completions"),
        "compiler_complete": art.get("compiler_complete"),
        "compiler_partial": art.get("compiler_partial"),
        "compiler_invalid": art.get("compiler_invalid"),
        "maps_returned": returned,
        "maps_persisted_delta": persisted_delta,
        "maps_projected_delta": projected_delta,
        "parents_mapped": art.get("parents_mapped"),
        "errors": art.get("errors"),
        "provider": (new_batches[0]["provider"] if new_batches else None),
        "model": (new_batches[0]["model"] if new_batches else None),
        "attempts": sum(b["attempt_count"] or 0 for b in new_batches),
        "limiter_day_count_delta": limiter_delta,
        "new_map_ids": sorted(set(after["map_ids"]) - set(before["map_ids"])),
        "checks": checks,
        "reconciles": all(checks.values()),
    }


if __name__ == "__main__":
    raise SystemExit(main())
