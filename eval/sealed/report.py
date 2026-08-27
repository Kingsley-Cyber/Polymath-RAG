#!/usr/bin/env python3
"""SEALED-MULTIDOMAIN-QUALIFICATION-V1 — the report.

MEASUREMENT ONLY. This module imports no admission authority, decides
nothing, and produces no patch. Its output is evidence for a human verdict.

WHY THIS IS NOT AN I4-STYLE SCORE
---------------------------------
The sealed documents have no gold. Precision and recall cannot be computed,
and the attribution waterfalls (endpoint coverage, canonical FP) require gold
to run at all. Reporting a P/R number here would be fabricating a denominator.

So the report splits into two things that ARE knowable:

  1. INVARIANTS      checkable without gold, and violations are release
                     blockers on their own terms
  2. INVENTORY       every durable identity, concept, abstention and fact,
                     each with the evidence that produced it, laid out for
                     adjudication by the evaluator

The evaluator supplies the judgement. The harness supplies the evidence and
refuses to pretend it can supply both.

FAILURE CLASSIFICATION
----------------------
Every finding is placed in exactly one layer, because "the graph is wrong"
is not actionable and, historically, is what led to a rule being added
instead of a cause being found:

    A extraction · B admission · C canonicalization
    D relation   · E retrieval · F infrastructure
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

LAYERS = ("A_extraction", "B_admission", "C_canonicalization",
          "D_relation", "E_retrieval", "F_infrastructure")


def _rows(conn, sql, params=()):
    return conn.execute(sql, params).fetchall()


# --------------------------------------------------------------- invariants
def invariants(conn, corpus: str) -> list[dict]:
    """Gold-free properties. A violation is a release blocker by itself."""
    out: list[dict] = []

    def check(name, layer, sql, params, ok_if_zero=True, detail_sql=None):
        n = _rows(conn, sql, params)[0][0]
        rec = {"invariant": name, "layer": layer, "count": n,
               "status": "PASS" if (n == 0) == ok_if_zero else "FAIL"}
        if rec["status"] == "FAIL" and detail_sql:
            rec["examples"] = [list(map(str, r))
                               for r in _rows(conn, detail_sql, params)[:5]]
        out.append(rec)

    check("every mention carries admission-harbor-v2", "B_admission",
          """SELECT COUNT(*) FROM mentions WHERE corpus_id=%s
              AND semantic_contract IS DISTINCT FROM 'admission-harbor-v2'""",
          (corpus,))
    check("no durable id from a non-v2 admission", "B_admission",
          """SELECT COUNT(*) FROM mentions WHERE corpus_id=%s AND entity_id IS NOT NULL
              AND semantic_contract IS DISTINCT FROM 'admission-harbor-v2'""",
          (corpus,))
    # NOTE: a fact with a MENTION_ONLY endpoint is PARKED, not defective —
    # it stays in Postgres and is never projected. An earlier draft of this
    # check counted parked facts as violations and failed on a known-good
    # corpus; the meaningful invariant is graph-side, below.
    check("entity id prefix agrees with admission class", "C_canonicalization",
          r"""SELECT COUNT(*) FROM entities e
                JOIN mentions m ON m.entity_id=e.entity_id
               WHERE m.corpus_id=%s AND (
                 (e.entity_id LIKE 'ent\_%%'  AND e.admission_class<>'GLOBAL') OR
                 (e.entity_id LIKE 'entc\_%%' AND e.admission_class<>'CORPUS_SCOPED') OR
                 (e.entity_id LIKE 'entd\_%%' AND e.admission_class<>'DOCUMENT_SCOPED'))""",
          (corpus,))
    check("no identity fragmentation (one surface, one id)", "C_canonicalization",
          """SELECT COUNT(*) FROM (
                SELECT normalized_surface FROM mentions
                 WHERE corpus_id=%s AND entity_id IS NOT NULL
                 GROUP BY 1 HAVING COUNT(DISTINCT entity_id)>1) t""", (corpus,),
          detail_sql="""SELECT normalized_surface, COUNT(DISTINCT entity_id)
                          FROM mentions WHERE corpus_id=%s AND entity_id IS NOT NULL
                         GROUP BY 1 HAVING COUNT(DISTINCT entity_id)>1""")
    check("every fact has exact-span evidence", "D_relation",
          """SELECT COUNT(*) FROM facts f
               JOIN evidence ev ON ev.fact_id=f.fact_id
               JOIN documents d ON d.doc_id=ev.doc_id
              WHERE d.corpus_id=%s AND ev.span_offsets IS NULL""", (corpus,))
    check("no orphaned semantic rows", "F_infrastructure",
          """SELECT COUNT(*) FROM entities e
              WHERE NOT EXISTS (SELECT 1 FROM mentions m WHERE m.entity_id=e.entity_id)
                AND NOT EXISTS (SELECT 1 FROM facts f
                                 WHERE f.subject_id=e.entity_id
                                    OR f.object_id=e.entity_id)""", ())
    out.append(_graph_invariant(conn, corpus))
    return out


def _graph_invariant(conn, corpus: str) -> dict:
    """Every PROJECTED relationship must have two eligible endpoints.

    This is the check that parked facts are irrelevant to: parking is the
    designed outcome for an ineligible endpoint, so the question is not
    "does an ineligible fact exist" but "did one reach the graph".
    """
    rec = {"invariant": "no projected relationship has an ineligible endpoint",
           "layer": "D_relation"}
    eligible = {r[0] for r in _rows(conn, """
        SELECT f.fact_id FROM facts f
          JOIN evidence ev ON ev.fact_id=f.fact_id
          JOIN documents d ON d.doc_id=ev.doc_id
          JOIN entities s ON s.entity_id=f.subject_id
          JOIN entities o ON o.entity_id=f.object_id
         WHERE d.corpus_id=%s
           AND s.admission_class IS DISTINCT FROM 'MENTION_ONLY'
           AND o.admission_class IS DISTINCT FROM 'MENTION_ONLY'""", (corpus,))}
    corpus_facts = {r[0] for r in _rows(conn, """
        SELECT f.fact_id FROM facts f
          JOIN evidence ev ON ev.fact_id=f.fact_id
          JOIN documents d ON d.doc_id=ev.doc_id
         WHERE d.corpus_id=%s""", (corpus,))}
    try:
        from workers.project_neo4j_worker import _driver
        driver = _driver()
        try:
            with driver.session() as s:
                projected = {r["id"] for r in
                             s.run("MATCH ()-[r]->() RETURN r.fact_id AS id") if r["id"]}
        finally:
            driver.close()
    except Exception as exc:
        rec.update(status="SKIP", count=0, note=f"Neo4j unreachable: {str(exc)[:70]}")
        return rec
    leaked = sorted((projected & corpus_facts) - eligible)
    missing = sorted(eligible - projected)
    rec.update(status="PASS" if not leaked else "FAIL", count=len(leaked),
               projected=len(projected & corpus_facts), eligible=len(eligible),
               not_yet_projected=len(missing))
    if leaked:
        rec["examples"] = leaked[:5]
    return rec


# ---------------------------------------------------------------- inventory
def inventory(conn, corpus: str) -> dict:
    per_doc = {}
    for src, in _rows(conn, "SELECT source_name FROM documents WHERE corpus_id=%s "
                            "ORDER BY source_name", (corpus,)):
        anchors = dict(_rows(conn, """SELECT COALESCE(anchor_kind,'(none)'), COUNT(*)
             FROM mentions m JOIN documents d ON d.doc_id=m.doc_id
            WHERE m.corpus_id=%s AND d.source_name=%s GROUP BY 1""", (corpus, src)))
        n, elig = _rows(conn, """SELECT COUNT(*), COUNT(entity_id)
             FROM mentions m JOIN documents d ON d.doc_id=m.doc_id
            WHERE m.corpus_id=%s AND d.source_name=%s""", (corpus, src))[0]
        per_doc[src] = {"mentions": n, "graph_eligible": elig,
                        "abstention_rate": round(1 - elig / n, 3) if n else None,
                        "anchor_kinds": dict(sorted(anchors.items()))}

    identities = [
        {"surface": r[0], "core_type": r[1], "scope": r[2], "evidence": r[3][:110]}
        for r in _rows(conn, """SELECT DISTINCT surface, core_type, admission_class,
                                       admission_reason
                                  FROM mentions WHERE corpus_id=%s
                                   AND anchor_kind='IDENTITY' AND entity_id IS NOT NULL
                                 ORDER BY surface""", (corpus,))]
    concepts = [
        {"surface": r[0], "scope": r[1], "evidence": r[2][:140]}
        for r in _rows(conn, """SELECT DISTINCT surface, admission_class, admission_reason
                                  FROM mentions WHERE corpus_id=%s AND anchor_kind='CONCEPT'
                                 ORDER BY surface""", (corpus,))]
    abstentions = [
        {"surface": r[0], "anchor": r[1], "status": r[2], "why": r[3][:110]}
        for r in _rows(conn, """SELECT DISTINCT surface, anchor_kind, decision_status,
                                       admission_reason
                                  FROM mentions WHERE corpus_id=%s AND entity_id IS NULL
                                 ORDER BY anchor_kind, surface""", (corpus,))]
    facts = [
        {"predicate": r[0], "subject": r[1], "object": r[2], "doc": r[3].split("/")[-1],
         "decision": r[4]}
        for r in _rows(conn, """SELECT f.predicate, s.normalized_surface,
                                       o.normalized_surface, d.source_name, f.decision
                                  FROM facts f
                                  JOIN evidence ev ON ev.fact_id=f.fact_id
                                  JOIN documents d ON d.doc_id=ev.doc_id
                                  JOIN entities s ON s.entity_id=f.subject_id
                                  JOIN entities o ON o.entity_id=f.object_id
                                 WHERE d.corpus_id=%s
                                   AND s.admission_class IS DISTINCT FROM 'MENTION_ONLY'
                                   AND o.admission_class IS DISTINCT FROM 'MENTION_ONLY'
                                 ORDER BY d.source_name, f.predicate""", (corpus,))]
    return {"per_document": per_doc, "durable_identities": identities,
            "concepts": concepts, "abstentions": abstentions,
            "canonical_facts": facts}


def main() -> int:
    import psycopg

    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", required=True)
    ap.add_argument("--set", help="sealed set name; verified if given")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    seal_status = "NOT CHECKED (no --set given)"
    if args.set:
        import subprocess
        rc = subprocess.run([sys.executable, str(HERE / "seal.py"), "verify",
                             "--set", args.set], capture_output=True, text=True)
        seal_status = "SEALED" if rc.returncode == 0 else "BROKEN"

    with psycopg.connect(DSN) as conn:
        inv = invariants(conn, args.corpus)
        body = inventory(conn, args.corpus)

    failed = [i for i in inv if i["status"] == "FAIL"]
    report = {
        "contract": "sealed-multidomain-qualification-v1",
        "corpus": args.corpus,
        "seal_status": seal_status,
        "invariants": inv,
        "invariant_failures": len(failed),
        "failure_layers": sorted({i["layer"] for i in failed}),
        "summary": {
            "documents": len(body["per_document"]),
            "durable_identities": len(body["durable_identities"]),
            "concepts": len(body["concepts"]),
            "abstentions": len(body["abstentions"]),
            "canonical_facts": len(body["canonical_facts"]),
        },
        **body,
        "verdict": None,
        "verdict_note": (
            "The harness does NOT set the verdict. Invariant failures are "
            "release blockers; the inventory requires adjudication by the "
            "evaluator. Choose QUALIFIED / QUALIFIED WITH KNOWN LIMITATIONS / "
            "REJECTED FOR RELEASE."),
    }
    text = json.dumps(report, indent=1, sort_keys=False) + "\n"
    if args.out:
        pathlib.Path(args.out).write_text(text)
        print(json.dumps({"written": args.out, "seal": seal_status,
                          "invariant_failures": len(failed),
                          **report["summary"]}, indent=1))
    else:
        print(text)
    return 2 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
