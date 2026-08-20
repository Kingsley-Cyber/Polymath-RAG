#!/usr/bin/env python3
"""S6B — CANONICAL-FP ATTRIBUTION. Diagnostic only; writes nothing.

The canonical-identity score reported 6 false positives. "6 FPs" is not
actionable: a wrong predicate, a wrong argument pair and an over-merged
identity are three different defects in three different components. This
places each one in a closed bucket so the dominant mechanism — if there is
one — is visible rather than assumed.

UNEXPLAINED must be zero, for the same reason as S6A: a catch-all bucket
lets a real defect hide inside a plausible summary.
"""
from __future__ import annotations

import json
import os
import pathlib
import re

HERE = pathlib.Path(__file__).parent
DSN = os.environ.get("POLYMATH_PG_DSN",
                     "postgresql://polymath:polymath-dev@127.0.0.1:5432/polymath")

BUCKETS = ("WRONG_PREDICATE", "WRONG_ARGUMENT_PAIR", "WRONG_DIRECTION",
           "WRONG_CANONICAL_IDENTITY", "OVERMERGE", "UNSUPPORTED_FACT",
           "UNEXPLAINED")


def norm(s: str) -> str:
    import unicodedata
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", s)).strip().lower()


def main() -> int:
    import argparse

    import psycopg
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", default="i4-fresh-acceptance-v1")
    args = ap.parse_args()

    import importlib.util as _ilu

    spec = _ilu.spec_from_file_location("cis", HERE / "canonical_identity_score.py")
    CIS = _ilu.module_from_spec(spec)
    spec.loader.exec_module(CIS)

    gold = json.loads((HERE / "gold" / "fact_gold.json").read_text())
    with psycopg.connect(DSN) as conn:
        canon = CIS._canonical_map(conn, args.corpus)

        def c_of(e):
            return canon.get(e, e) if e else None

        # canonical identity -> the surfaces that reached it
        surfaces: dict[str, set] = {}
        gold_surface_to_canon: dict[tuple, set] = {}
        for src, nsurf, eid in conn.execute(
            """SELECT d.source_name, m.normalized_surface, m.entity_id
                 FROM mentions m JOIN documents d ON d.doc_id=m.doc_id
                WHERE m.corpus_id=%s AND m.entity_id IS NOT NULL""",
                (args.corpus,)).fetchall():
            surfaces.setdefault(c_of(eid), set()).add(nsurf)
            gold_surface_to_canon.setdefault((src, norm(nsurf)), set()).add(c_of(eid))

        produced = []
        for fid, pred, s_id, o_id, src in conn.execute(
            """SELECT f.fact_id, f.predicate, f.subject_id, f.object_id, d.source_name
                 FROM facts f JOIN evidence ev ON ev.fact_id=f.fact_id
                 JOIN documents d ON d.doc_id=ev.doc_id WHERE d.corpus_id=%s""",
                (args.corpus,)).fetchall():
            produced.append({"fact_id": fid, "predicate": pred,
                             "subj": c_of(s_id), "obj": c_of(o_id), "doc": src})

    def canon_for(doc_tail, surface):
        return {c for (s, n), ids in gold_surface_to_canon.items()
                if s.endswith(doc_tail) and n == norm(surface) for c in ids}

    golds = []
    for g in gold["supported_positive"]["facts"]:
        golds.append({"predicate": g["predicate"], "doc": g["doc"],
                      "subj": canon_for(g["doc"], g["subject"]),
                      "obj": canon_for(g["doc"], g["object"]),
                      "s_txt": g["subject"], "o_txt": g["object"]})

    matched, results = set(), []
    for g in golds:
        for p in produced:
            if (p["predicate"] == g["predicate"] and p["doc"].endswith(g["doc"])
                    and p["subj"] in g["subj"] and p["obj"] in g["obj"]):
                matched.add(p["fact_id"])
                break

    counts = {b: 0 for b in BUCKETS}
    for p in produced:
        if p["fact_id"] in matched:
            continue
        same_doc = [g for g in golds if p["doc"].endswith(g["doc"])]
        bucket, why = "UNSUPPORTED_FACT", "no gold relation between these referents"
        for g in same_doc:
            if p["subj"] in g["obj"] and p["obj"] in g["subj"] and p["predicate"] == g["predicate"]:
                bucket, why = "WRONG_DIRECTION", f"gold is {g['s_txt']} -> {g['o_txt']}"
                break
            if p["subj"] in g["subj"] and p["obj"] in g["obj"]:
                bucket, why = "WRONG_PREDICATE", f"gold predicate is {g['predicate']}"
                break
            if p["predicate"] == g["predicate"] and (p["subj"] in g["subj"] or p["obj"] in g["obj"]):
                # Distinguish "the binder chose the wrong argument" from "the
                # binder chose the RIGHT referent but its identity does not
                # match the gold's extent". Only the first implicates binding;
                # the second is the endpoint-identity problem S6A measured,
                # and conflating them would manufacture a binding defect.
                p_surfs = surfaces.get(p["subj"], set()) | surfaces.get(p["obj"], set())
                same_referent = any(
                    norm(t) in ps or ps in norm(t)
                    for ps in p_surfs for t in (g["s_txt"], g["o_txt"]))
                if same_referent:
                    bucket = "WRONG_CANONICAL_IDENTITY"
                    why = (f"same referent, different extent: produced "
                           f"{sorted(p_surfs)[:2]} vs gold {g['s_txt']!r}/{g['o_txt']!r}")
                else:
                    bucket = "WRONG_ARGUMENT_PAIR"
                    why = f"gold pairs {g['s_txt']} -> {g['o_txt']}"
                break
        if bucket == "UNSUPPORTED_FACT":
            merged = [c for c in (p["subj"], p["obj"]) if len(surfaces.get(c, ())) > 1]
            if merged:
                bucket = "OVERMERGE"
                why = f"endpoint identity covers {sorted(surfaces[merged[0]])[:4]}"
        counts[bucket] += 1
        results.append({"fact_id": p["fact_id"][:18], "predicate": p["predicate"],
                        "doc": p["doc"].split("/")[-1], "bucket": bucket,
                        "subject": sorted(surfaces.get(p["subj"], {"?"}))[:2],
                        "object": sorted(surfaces.get(p["obj"], {"?"}))[:2],
                        "why": why})

    print(json.dumps({"corpus": args.corpus, "produced": len(produced),
                      "matched": len(matched), "false_positives": len(results),
                      "attribution": {k: v for k, v in counts.items() if v},
                      "unexplained": counts["UNEXPLAINED"]}, indent=1))
    print("\n--- false positives ---")
    for r in sorted(results, key=lambda x: x["bucket"]):
        print(f"  [{r['bucket']:<24}] {r['predicate']:<14} "
              f"{str(r['subject'])[:30]:<32} -> {str(r['object'])[:28]:<30} {r['why'][:44]}")
    return 1 if counts["UNEXPLAINED"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
