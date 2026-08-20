#!/usr/bin/env python3
"""ADMISSION CENSUS REGRESSION — the dimension that was missing.

    A fact-level P/R metric cannot certify the entity-admission layer.

Row 53 proved it. A defect that parked 42 of 55 graph-eligible identities
left the I4 fact score completely unmoved at P=.750, because that score
compares endpoint SURFACES and never asks how many identities exist or what
kind they are. Every admission unit test stayed green too: each rule was
individually correct, and the composition was wrong.

This census makes catastrophic shifts LOUD. It is a tripwire, not a target —
it exists to force a decision when the shape of admission changes, and rules
must never be adjusted to satisfy it.

    python eval/census/verify_census.py --corpus i4-fresh-acceptance-v1
    python eval/census/verify_census.py --corpus ... --freeze   # re-baseline
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import sys

HERE = pathlib.Path(__file__).parent
DSN = os.environ.get("POLYMATH_PG_DSN",
                     "postgresql://polymath:polymath-dev@127.0.0.1:5432/polymath")


def census(conn, corpus: str) -> dict:
    def one(sql, params=(corpus,)):
        return conn.execute(sql, params).fetchone()[0]

    per_doc = {}
    for doc, src in conn.execute(
        "SELECT doc_id, source_name FROM documents WHERE corpus_id=%s ORDER BY source_name",
        (corpus,)).fetchall():
        anchors = dict(conn.execute(
            """SELECT COALESCE(anchor_kind,'(none)'), COUNT(*) FROM mentions
                WHERE corpus_id=%s AND doc_id=%s GROUP BY 1""", (corpus, doc)).fetchall())
        per_doc[src] = {
            "mentions": one("""SELECT COUNT(*) FROM mentions WHERE corpus_id=%s
                                AND doc_id=%s""", (corpus, doc)),
            "graph_eligible": one("""SELECT COUNT(*) FROM mentions WHERE corpus_id=%s
                                      AND doc_id=%s AND entity_id IS NOT NULL""", (corpus, doc)),
            "anchor_kinds": {k: v for k, v in sorted(anchors.items())},
        }

    return {
        "corpus": corpus,
        "totals": {
            "mentions": one("SELECT COUNT(*) FROM mentions WHERE corpus_id=%s"),
            "graph_eligible": one("""SELECT COUNT(*) FROM mentions
                WHERE corpus_id=%s AND entity_id IS NOT NULL"""),
            "distinct_entities": one("""SELECT COUNT(DISTINCT entity_id) FROM mentions
                WHERE corpus_id=%s AND entity_id IS NOT NULL"""),
            "canonical_entities": one("""SELECT COUNT(*) FROM canonical_entities
                WHERE corpus_id=%s"""),
            "canonical_facts": one("""SELECT COUNT(*) FROM facts f
                JOIN evidence ev ON ev.fact_id=f.fact_id
                JOIN documents d ON d.doc_id=ev.doc_id
                JOIN entities s ON s.entity_id=f.subject_id
                JOIN entities o ON o.entity_id=f.object_id
                WHERE d.corpus_id=%s
                  AND s.admission_class IS DISTINCT FROM 'MENTION_ONLY'
                  AND o.admission_class IS DISTINCT FROM 'MENTION_ONLY'"""),
        },
        "per_document": per_doc,
    }


def compare(expected: dict, actual: dict) -> list[str]:
    """Report every divergence. No tolerance band: a census that drifts
    quietly is a census that certifies nothing."""
    out: list[str] = []
    for k, want in expected["totals"].items():
        got = actual["totals"].get(k)
        if got != want:
            out.append(f"totals.{k}: expected {want}, got {got}")
    for src, want in expected["per_document"].items():
        got = actual["per_document"].get(src)
        if got is None:
            out.append(f"{src}: document missing")
            continue
        for k in ("mentions", "graph_eligible"):
            if got[k] != want[k]:
                out.append(f"{src}.{k}: expected {want[k]}, got {got[k]}")
        if got["anchor_kinds"] != want["anchor_kinds"]:
            out.append(f"{src}.anchor_kinds: expected {want['anchor_kinds']}, "
                       f"got {got['anchor_kinds']}")
    for src in set(actual["per_document"]) - set(expected["per_document"]):
        out.append(f"{src}: unexpected document")
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", required=True)
    ap.add_argument("--freeze", action="store_true",
                    help="re-baseline; use only with an explicit ruling")
    args = ap.parse_args()

    import psycopg
    with psycopg.connect(DSN) as conn:
        actual = census(conn, args.corpus)

    path = HERE / f"census_{args.corpus}.json"
    if args.freeze:
        path.write_text(json.dumps(actual, indent=1, sort_keys=True) + "\n")
        print(json.dumps({"frozen": str(path), "totals": actual["totals"]}))
        return 0

    if not path.exists():
        print(json.dumps({"error": f"no frozen census at {path}; "
                                   "run with --freeze after a ruling"}))
        return 2

    diffs = compare(json.loads(path.read_text()), actual)
    print(json.dumps({"corpus": args.corpus, "totals": actual["totals"],
                      "divergences": diffs}, indent=1))
    if diffs:
        print("\nCENSUS REGRESSION — the shape of admission changed.", file=sys.stderr)
        print("This is a tripwire, not a target: investigate the cause, and "
              "re-baseline only on an explicit ruling.", file=sys.stderr)
    return 1 if diffs else 0


if __name__ == "__main__":
    raise SystemExit(main())
