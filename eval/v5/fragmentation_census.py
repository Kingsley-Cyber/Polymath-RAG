"""Phase C — identity-fragmentation impact census (release closure).

Read-only. For a corpus, finds every normalized durable surface holding
more than one entity id, and emits per-case evidence for adjudication
into the mission's three buckets:

  LEGITIMATE_CONTEXT_DISTINCTION  the ids denote different referents
                                  (Apple company vs fruit) — correct
  TRUE_REFERENT_FRAGMENTATION     one referent, forked id — recall cost
  UNCERTAIN                       evidence insufficient

The script does NOT classify; it gathers what classification needs:
core types per id, admission classes, mention contexts (up to 3 per
id), fact participation per id, and cross-document spread. Buckets are
assigned by the evaluator (heuristic pre-labels are marked as such).

Pre-label heuristic (marked `prelabel`, never authoritative):
  - ids differ in core_type            -> LEGITIMATE_CONTEXT_DISTINCTION
    (row-51 homonym guard working as designed)
  - same core_type, same doc           -> TRUE_REFERENT_FRAGMENTATION
  - same core_type, different docs     -> UNCERTAIN
"""

from __future__ import annotations

import argparse
import json
import os
import sys

import psycopg

DSN = os.environ.get(
    "POLYMATH_PG_DSN",
    "postgresql://polymath:polymath-dev@127.0.0.1:5432/polymath")


def census(corpus: str, context_chars: int = 90) -> dict:
    conn = psycopg.connect(DSN)
    rows = conn.execute(
        """SELECT e.normalized_surface,
                  array_agg(DISTINCT m.entity_id) AS ids
             FROM mentions m JOIN entities e ON e.entity_id = m.entity_id
            WHERE m.corpus_id = %s AND m.entity_id IS NOT NULL
            GROUP BY e.normalized_surface
           HAVING COUNT(DISTINCT m.entity_id) > 1
            ORDER BY e.normalized_surface""", (corpus,)).fetchall()

    durable_total = conn.execute(
        """SELECT COUNT(DISTINCT e.normalized_surface)
             FROM mentions m JOIN entities e ON e.entity_id = m.entity_id
            WHERE m.corpus_id = %s""", (corpus,)).fetchone()[0]

    cases = []
    for surface, ids in rows:
        per_id = []
        for eid in ids:
            core, adm = conn.execute(
                "SELECT core_type, admission_class FROM entities WHERE entity_id=%s",
                (eid,)).fetchone()
            docs = [r[0] for r in conn.execute(
                """SELECT DISTINCT doc_id FROM mentions
                    WHERE entity_id=%s AND corpus_id=%s""",
                (eid, corpus)).fetchall()]
            ctxs = []
            for cid, s, e in conn.execute(
                    """SELECT chunk_id, char_start, char_end FROM mentions
                        WHERE entity_id=%s AND corpus_id=%s LIMIT 3""",
                    (eid, corpus)).fetchall():
                text = conn.execute(
                    "SELECT text FROM chunks WHERE chunk_id=%s",
                    (cid,)).fetchone()[0]
                lo = max(0, s - context_chars)
                hi = min(len(text), e + context_chars)
                ctxs.append(text[lo:hi].replace("\n", " "))
            facts = conn.execute(
                "SELECT COUNT(*) FROM facts WHERE subject_id=%s OR object_id=%s",
                (eid, eid)).fetchone()[0]
            per_id.append({"entity_id": eid, "core_type": core,
                           "admission_class": adm, "docs": docs,
                           "fact_count": facts, "contexts": ctxs})
        types = {p["core_type"] for p in per_id}
        all_docs = {d for p in per_id for d in p["docs"]}
        same_doc = any(
            len(set(a["docs"]) & set(b["docs"])) > 0
            for i, a in enumerate(per_id) for b in per_id[i + 1:])
        if len(types) > 1:
            prelabel = "LEGITIMATE_CONTEXT_DISTINCTION"
        elif same_doc:
            prelabel = "TRUE_REFERENT_FRAGMENTATION"
        else:
            prelabel = "UNCERTAIN"
        cases.append({"surface": surface, "ids": len(ids),
                      "prelabel": prelabel, "doc_spread": len(all_docs),
                      "per_id": per_id})

    from collections import Counter
    return {
        "corpus": corpus,
        "durable_surfaces": durable_total,
        "fragmented_surfaces": len(cases),
        "fragmentation_rate": round(len(cases) / durable_total, 4)
        if durable_total else None,
        "prelabel_counts": dict(Counter(c["prelabel"] for c in cases)),
        "facts_on_fragmented_ids": sum(
            p["fact_count"] for c in cases for p in c["per_id"]),
        "cases": cases,
    }


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", required=True)
    ap.add_argument("--out")
    a = ap.parse_args()
    out = census(a.corpus)
    blob = json.dumps(out, indent=1)
    if a.out:
        with open(a.out, "w") as f:
            f.write(blob)
        summary = {k: v for k, v in out.items() if k != "cases"}
        print(json.dumps(summary, indent=1))
    else:
        print(blob)
    sys.exit(0)
