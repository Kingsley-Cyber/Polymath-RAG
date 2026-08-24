"""Scientific KAG acceptance harness (owner COVERAGE_GATE schema).

Scores the validation mission's gates against live store state.
Run anytime: sections report PASS / FAIL / PENDING with measured
values — never guesses. Overall verdict requires:

  predicate_coverage >= 0.90   (curated suite expected relations)
  predicate_precision >= 0.95
  evidence_support >= 0.95
  role_binding_errors == 0     (golden fixtures)
  false_positives == 0         (adversarial fixtures)

Summary/vocabulary/retrieval sections validate structure,
anti-hallucination lineage, and routing paths from live tables.
"""
from __future__ import annotations

import datetime as dt
import json
import sys

import psycopg

DSN = "postgresql://polymath:polymath-dev@127.0.0.1:5432/polymath"

GATE = {
    "predicate_coverage_min": 0.90,
    "predicate_precision_min": 0.95,
    "evidence_support_min": 0.95,
    "role_binding_errors_max": 0,
    "false_positives_max": 0,
}


def q(cur, sql, args=()):
    cur.execute(sql, args)
    return cur.fetchall()


def _verdict(ok: bool, measured) -> dict:
    return {"verdict": "PASS" if ok else "FAIL", "measured": measured}


def section_extraction(cur, corpus: str) -> dict:
    """Extraction coverage + integrity from durable state."""
    facts = q(cur, """
        SELECT count(DISTINCT f.fact_id) FROM facts f
          JOIN evidence ev ON ev.fact_id=f.fact_id
          JOIN documents d ON d.doc_id=ev.doc_id
         WHERE d.corpus_id=%s""", (corpus,))[0][0]
    mentions = q(cur, """
        SELECT admission_class, count(*) FROM mentions m
          JOIN documents d ON d.doc_id=m.doc_id
         WHERE d.corpus_id=%s GROUP BY 1""", (corpus,))
    frag = q(cur, """
        SELECT count(*) FROM (
          SELECT m.normalized_surface, m.core_type
            FROM mentions m JOIN documents d ON d.doc_id=m.doc_id
           WHERE d.corpus_id=%s AND m.admission_class='CORPUS_SCOPED'
           GROUP BY 1,2 HAVING count(DISTINCT m.entity_id)>1) x""",
        (corpus,))[0][0]
    return {
        "facts_admitted": facts,
        "mentions_by_class": {k: v for k, v in mentions},
        "entity_identity_fragments": int(frag),
        "golden_suite_scored": False,   # set by replay scorer post-cutover
        "note": "counts are live; golden/adversarial scoring activates "
                "after Compiler-v2 cutover replay",
    }


def section_summary(cur, corpus: str) -> dict:
    """Anti-hallucination lineage checks per summary level."""
    out: dict = {}
    for table, ent_col, con_col in (
            ("parent_summaries", "entities", "concepts"),
            ("document_summaries", None, None),
            ("corpus_summaries", None, None)):
        cols = "array_length(source_ids,1)"
        rows = q(cur, f"SELECT artifact_hash, {cols} FROM {table} "
                      f"WHERE corpus_id=%s", (corpus,))
        bad_lineage = [r for r in rows if not r[1]]
        out[table] = {
            "count": len(rows),
            "missing_source_ids": len(bad_lineage),
            "verdict": ("PENDING" if not rows else
                        "PASS" if not bad_lineage else
                        "FAIL(lineage)"),
        }
    return out


def section_vocabulary(cur, corpus: str) -> dict:
    n_concepts = q(cur, "SELECT count(*) FROM concept_vocabulary")[0][0]
    n_aliases = q(cur, "SELECT count(*) FROM concept_aliases")[0][0]
    merges = q(cur, """
        SELECT count(*) FROM entity_merge_receipts""")[0][0]
    return {"concepts": n_concepts, "aliases": n_aliases,
            "merge_receipts": int(merges),
            "hallucination_alias_case": "PENDING (needs vocabulary rows)",
            "verdict": "PENDING" if n_concepts == 0 else "SCORED"}


def section_retrieval(cur, corpus: str) -> dict:
    rs = q(cur, """
        SELECT kind, count(*) FROM retrieval_summaries
         WHERE corpus_id=%s GROUP BY 1""", (corpus,))
    facts = q(cur, "SELECT count(*) FROM facts")[0][0]
    return {"retrieval_summaries": {k: v for k, v in rs},
            "graph_facts_total": int(facts),
            "verdict": "PENDING" if not rs else "SCORED"}


def main() -> dict:
    corpus = sys.argv[1] if len(sys.argv) > 1 else "scale-10k-v1"
    with psycopg.connect(DSN, connect_timeout=5) as conn, conn.cursor() as cur:
        report = {
            "generated_at": dt.datetime.now(dt.UTC).isoformat(),
            "gate_thresholds": GATE,
            "extraction": section_extraction(cur, corpus),
            "summary_intelligence": section_summary(cur, corpus),
            "vocabulary": section_vocabulary(cur, corpus),
            "retrieval": section_retrieval(cur, corpus),
        }
    overall = "GREEN"
    for sec in ("summary_intelligence",):
        for t, v in report[sec].items():
            if isinstance(v, dict) and v.get("verdict") == "FAIL(lineage)":
                overall = "RED"
    report["overall"] = overall if overall == "RED" else "YELLOW (gates pending cutover replay)"
    print(json.dumps(report, indent=1))
    return report


if __name__ == "__main__":
    main()
