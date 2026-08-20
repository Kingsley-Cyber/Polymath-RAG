#!/usr/bin/env python3
"""CANONICAL IDENTITY SCORE — the second S5 metric.

The historical surface score (`verify_i4.py`, frozen and untouched) compares
endpoint SURFACES. It preserves comparability across the whole programme, but
it is blind in one direction that now matters: if two surface variants of one
referent converge onto a single canonical identity, a surface score cannot
see the convergence, and if an identity fragments, it cannot see that either.

This scores the same gold by PREDICATE + CANONICAL ENDPOINT IDENTITY:

    gold surface -> mention -> entity_id -> canonical_id
    fact endpoint            -> entity_id -> canonical_id

so a fact counts as correct when it connects the right REFERENTS, however
each mention happened to be worded.

Neither metric supersedes the other. The surface score keeps the programme
comparable; this one is the only one that can observe identity behaviour.
"""
from __future__ import annotations

import json
import os
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).parent
DSN = os.environ.get("POLYMATH_PG_DSN",
                     "postgresql://polymath:polymath-dev@127.0.0.1:5432/polymath")


def norm(s: str) -> str:
    import unicodedata
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", s)).strip().lower()


def _canonical_map(conn, corpus: str) -> dict[str, str]:
    """entity_id -> canonical_id, falling back to the entity itself.

    An entity with no canonical membership IS its own canonical identity;
    treating it as unresolved would silently drop every entity the
    canonicalizer had no reason to merge.
    """
    return {r[0]: r[1] for r in conn.execute(
        "SELECT local_entity_id, canonical_id FROM canonical_memberships "
        "WHERE corpus_id=%s AND decision='SAME_ENTITY'", (corpus,)).fetchall()}


def score(conn, corpus: str) -> dict:
    gold = json.loads((HERE / "gold" / "fact_gold.json").read_text())
    canon = _canonical_map(conn, corpus)

    def canonical(eid: str | None) -> str | None:
        return canon.get(eid, eid) if eid else None

    # surface -> canonical identity, per document
    surf_to_canon: dict[tuple[str, str], set[str]] = {}
    for src, nsurf, eid in conn.execute(
        """SELECT d.source_name, m.normalized_surface, m.entity_id
             FROM mentions m JOIN documents d ON d.doc_id = m.doc_id
            WHERE m.corpus_id = %s AND m.entity_id IS NOT NULL""",
            (corpus,)).fetchall():
        surf_to_canon.setdefault((src, norm(nsurf)), set()).add(canonical(eid))

    produced = []
    for pred, s_id, o_id, src in conn.execute(
        """SELECT f.predicate, f.subject_id, f.object_id, d.source_name
             FROM facts f
             JOIN evidence ev ON ev.fact_id = f.fact_id
             JOIN documents d ON d.doc_id = ev.doc_id
            WHERE d.corpus_id = %s""", (corpus,)).fetchall():
        produced.append((pred, canonical(s_id), canonical(o_id), src))

    tp = fn = 0
    unresolvable = []
    fn_details = []
    matched = set()
    for g in gold["supported_positive"]["facts"]:
        doc = g["doc"]
        src_key = next((k for k in surf_to_canon if k[0].endswith(doc)), None)
        subj = {c for (s, n), ids in surf_to_canon.items()
                if s.endswith(doc) and n == norm(g["subject"]) for c in ids}
        obj = {c for (s, n), ids in surf_to_canon.items()
               if s.endswith(doc) and n == norm(g["object"]) for c in ids}
        if not subj or not obj:
            # the gold endpoint never earned a durable identity — a real
            # outcome, recorded separately so it is not silently a miss
            unresolvable.append({"fact": g.get("fact_id"), "predicate": g["predicate"],
                                 "subject_resolved": bool(subj),
                                 "object_resolved": bool(obj)})
            fn += 1
            continue
        hit = [p for p in produced
               if p[0] == g["predicate"] and p[1] in subj and p[2] in obj
               and p[3].endswith(doc)]
        if hit:
            tp += 1
            matched.add((hit[0][0], hit[0][1], hit[0][2], hit[0][3]))
        else:
            fn += 1
            fn_details.append({"fact": g.get("fact_id"), "predicate": g["predicate"],
                               "subject": g["subject"], "object": g["object"]})

    fp = len([p for p in produced if p not in matched])
    prec = tp / (tp + fp) if tp + fp else 0.0
    rec = tp / (tp + fn) if tp + fn else 0.0
    return {
        "corpus": corpus, "metric": "canonical-identity",
        "gold": len(gold["supported_positive"]["facts"]),
        "tp": tp, "fp": fp, "fn": fn,
        "precision": round(prec, 3), "recall": round(rec, 3),
        "f1": round(2 * prec * rec / (prec + rec), 3) if prec + rec else 0.0,
        "gold_endpoints_without_durable_identity": len(unresolvable),
        "unresolvable": unresolvable[:8],
        "fn_details": fn_details[:8],
    }


def main() -> int:
    import argparse

    import psycopg
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", default="i4-fresh-acceptance-v1")
    args = ap.parse_args()
    with psycopg.connect(DSN) as conn:
        print(json.dumps(score(conn, args.corpus), indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
