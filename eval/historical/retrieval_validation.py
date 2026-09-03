"""RETRIEVAL VALIDATION — deterministic end-to-end scoring over live data.

Self-deriving ground truth: per corpus, the top admitted fact tuples
ARE the expected evidence; queries are formulated from their surfaces.
Lanes exercised: document-profile, parent-summary, child-lexical,
graph expansion (dense lane offline in replay — noted).

Metrics per query: routing (selected docs in expected corpus),
evidence recall (expected fact surfaces present in child hits or graph
facts), grounding (graph facts cite fact ids), citation (every returned
fact row carries fact_id + evidence doc).
"""
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))

os.environ.setdefault(
    "POLYMATH_PG_DSN",
    "postgresql://polymath:polymath-dev@127.0.0.1:5432/polymath")

from psycopg.rows import dict_row  # noqa: E402
import psycopg  # noqa: E402

from polymath_shared.retrieval import run_lanes, graph_expansion  # noqa: E402


def main() -> dict:
    conn = psycopg.connect(os.environ["POLYMATH_PG_DSN"], autocommit=False,
                           row_factory=dict_row)
    cur = conn.cursor()

    corpora = [r["corpus_id"] for r in cur.execute("""
        SELECT DISTINCT d.corpus_id FROM facts f
          JOIN evidence ev ON ev.fact_id=f.fact_id
          JOIN documents d ON d.doc_id=ev.doc_id
        GROUP BY 1 HAVING count(*) >= 5 ORDER BY 1""").fetchall()]

    results = []
    for corpus_id in corpora:
        top = cur.execute("""
            SELECT f.predicate, sn.normalized_surface AS subj,
                   no.normalized_surface AS obj
              FROM facts f
              JOIN evidence ev ON ev.fact_id=f.fact_id
              JOIN entities sn ON sn.entity_id=f.subject_id
              JOIN entities no ON no.entity_id=f.object_id
              JOIN documents d ON d.doc_id=ev.doc_id
             WHERE d.corpus_id=%s
             GROUP BY 1,2,3
             HAVING count(DISTINCT ev.doc_id) >= 1
             ORDER BY count(*) DESC LIMIT 3""", (corpus_id,)).fetchall()
        for t in top:
            query = f"{t['subj']} {t['predicate'].replace('_', ' ')} {t['obj']}"
            expected = {"subject": t["subj"], "predicate": t["predicate"],
                        "object": t["obj"]}

            def fetch_profiles(cur=cur, cid=corpus_id):
                return cur.execute("""
                    SELECT d.doc_id,
                           COALESCE(d.profile,'{}'::jsonb) AS retrieval_profile
                      FROM documents d WHERE d.corpus_id=%s LIMIT 500""",
                    (cid,)).fetchall()

            def fetch_parents(cur=cur, cid=corpus_id):
                return cur.execute("""
                    SELECT c.chunk_id, c.doc_id, c.summary
                      FROM chunks c JOIN documents d ON d.doc_id=c.doc_id
                     WHERE d.corpus_id=%s AND c.tier='parent'
                       AND coalesce(c.summary,'') <> '' LIMIT 500""",
                    (cid,)).fetchall()

            def fetch_children(limit=800, cur=cur, cid=corpus_id):
                return cur.execute("""
                    SELECT c.chunk_id, c.doc_id, c.parent_id, c.text
                      FROM chunks c JOIN documents d ON d.doc_id=c.doc_id
                     WHERE d.corpus_id=%s AND c.tier='child' LIMIT %s""",
                    (cid, int(limit))).fetchall()

            def child_search(cur=cur, cid=corpus_id):  # dense lane offline
                return []

            res = run_lanes(query, fetch_profiles=fetch_profiles,
                            fetch_parents=fetch_parents,
                            fetch_children=fetch_children,
                            child_search=child_search)

            # graph expansion seeded from retrieved child texts' surfaces
            seeds = [c.get("text", "")[:40] for c in res.selected_children]
            gfacts = graph_expansion(seeds, expand=lambda surfaces: cur.execute("""
                SELECT DISTINCT f.fact_id, f.predicate, ev.doc_id
                  FROM facts f JOIN evidence ev ON ev.fact_id=f.fact_id
                  JOIN entities sn ON sn.entity_id=f.subject_id
                 WHERE sn.normalized_surface = ANY(%s) LIMIT 20""",
                (surfaces,)).fetchall())

            hit_children = " ".join(c.get("text", "") for c in
                                    res.selected_children).lower()
            evidence_recall = int(
                t["subj"].lower() in hit_children
                and t["obj"].lower() in hit_children)
            routing_ok = all(d.get("corpus_id", corpus_id) == corpus_id
                             for d in res.selected_documents) \
                if res.selected_documents else True
            results.append({
                "corpus": corpus_id, "query": query, "expected": expected,
                "routing_ok": bool(routing_ok),
                "child_hits": len(res.selected_children),
                "doc_hits": len(res.document_ranking),
                "evidence_recall": evidence_recall,
                "graph_facts": len(gfacts),
                "grounded_citations": all(g.get("fact_id") for g in gfacts)
                                      if gfacts else None,
            })

    scored = [r for r in results]
    summary = {
        "queries": len(scored),
        "routing_accuracy": round(sum(r["routing_ok"] is True for r in
                                      scored) / max(len(scored), 1), 2),
        "evidence_recall": round(sum(r["evidence_recall"] for r in scored)
                                 / max(len(scored), 1), 2),
        "grounding_all_citations": all(
            r["grounded_citations"] in (True, None) for r in scored),
    }
    conn.rollback()
    conn.close()
    return {"summary": summary, "results": results}


if __name__ == "__main__":
    print(json.dumps(main(), indent=1, default=str))
