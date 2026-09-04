#!/usr/bin/env python3
"""Append a run's curated observations to registry/research_evidence.csv.

docs/19 §7: every real run grows the evidence ledger. Idempotent on
(run_id, observation_id); never rewrites existing rows; the CSV is a
maintenance input (registry review), never read back inside a run.

    python3 python/export_research_evidence.py --state run.json [--out registry/research_evidence.csv] [--all]

By default only observations on gaps that closed (`supported`) are exported;
`--all` exports every admitted observation.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys

COLUMNS = ["run_id", "observation_id", "gap_id", "gap_status", "platform", "source_family", "source",
           "author_key", "thread_key", "quote_ref", "problem", "workaround", "purchase_language",
           "evidence_roles", "freshness_class", "query_id", "query_used", "mechanism_id", "exported_at"]


def rows_for(state: dict, include_all: bool) -> list[dict]:
    d = state.get("data") or {}
    gaps = {g.get("id"): g for g in d.get("gaps") or [] if isinstance(g, dict)}
    mech_by_obs = {}
    for m in d.get("mechanisms") or []:
        for oid in m.get("supporting_observation_ids") or []:
            mech_by_obs.setdefault(oid, m.get("id"))
    out = []
    for o in d.get("observations") or []:
        if not isinstance(o, dict) or not o.get("id"):
            continue
        gap = gaps.get(o.get("gap_id")) or {}
        if not include_all and gap.get("status") != "supported":
            continue
        si = o.get("source_identity") or {}
        out.append({"run_id": state.get("run_id"), "observation_id": o["id"], "gap_id": o.get("gap_id"),
                    "gap_status": gap.get("status"), "platform": si.get("platform"), "source_family": si.get("source_family"),
                    "source": o.get("source"), "author_key": si.get("author_key"), "thread_key": si.get("thread_key"),
                    "quote_ref": o.get("quote_ref"), "problem": o.get("problem"), "workaround": o.get("workaround"),
                    "purchase_language": o.get("purchase_language"), "evidence_roles": "|".join(o.get("evidence_roles") or []),
                    "freshness_class": (o.get("freshness") or {}).get("class"), "query_id": o.get("query_id"),
                    "query_used": o.get("query_used"), "mechanism_id": mech_by_obs.get(o["id"]), "exported_at": state.get("updated_at")})
    return out


def export(state: dict, out_path: str, include_all: bool = False) -> dict:
    rows = rows_for(state, include_all)
    existing = set()
    if os.path.exists(out_path):
        with open(out_path, encoding="utf-8", newline="") as f:
            for r in csv.DictReader(f):
                existing.add((r.get("run_id"), r.get("observation_id")))
    fresh = [r for r in rows if (r["run_id"], r["observation_id"]) not in existing]
    write_header = not os.path.exists(out_path) or os.path.getsize(out_path) == 0
    if fresh:
        with open(out_path, "a", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=COLUMNS)
            if write_header:
                w.writeheader()
            for r in fresh:
                w.writerow({k: ("" if r.get(k) is None else r.get(k)) for k in COLUMNS})
    return {"ok": True, "out": out_path, "candidates": len(rows), "appended": len(fresh), "skipped_existing": len(rows) - len(fresh)}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--state", required=True)
    ap.add_argument("--out", default=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "registry", "research_evidence.csv"))
    ap.add_argument("--all", action="store_true", help="export every admitted observation, not only those on closed gaps")
    a = ap.parse_args()
    with open(a.state, encoding="utf-8") as f:
        state = json.load(f)
    print(json.dumps(export(state, a.out, a.all), indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
