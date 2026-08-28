#!/usr/bin/env python
"""SEMANTIC-LANE-LIVENESS-V1: opportunity-vs-capture census.

Answers the question an artifact count cannot: is a lane capturing the
evidence it is shown, or silently discarding most of it?

    procedure_artifacts = 12

tells you nothing on its own. It is 12 of 12 documents (100% of
documents produced one) AND 12 of 965 opportunities (1.24%), because
compile_procedure emits at most ONE artifact per document. Only the
opportunity ratio makes that visible.

Reads durable state only — no re-ingest, no extraction, no model calls.
Uses the compilers' own helpers so the counts cannot drift from what
production actually evaluates.

    python scripts/semantic_lane_census.py --corpus cysa-study-v1
    python scripts/semantic_lane_census.py --corpus cysa-study-v1 --backfill
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for p in (ROOT / "shared", ROOT / "workers", ROOT):
    sys.path.insert(0, str(p))

from polymath_shared.db import tx  # noqa: E402
from polymath_shared.knowledge_objects import concept as C  # noqa: E402
from polymath_shared.knowledge_objects import procedure as P  # noqa: E402

#: compile_concepts' default cap; equality means truncation.
CONCEPT_CAP = 10


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", required=True)
    ap.add_argument("--backfill", action="store_true",
                    help="write knowledge_lane_attempts rows for docs "
                         "ingested before the telemetry existed")
    args = ap.parse_args()

    from workers.summarizer import split_sentences

    totals = {"proc_opp": 0, "proc_art": 0, "conc_opp": 0, "conc_art": 0}
    rows_out = []
    with tx() as conn:
        docs = conn.execute(
            "SELECT doc_id, source_name FROM documents WHERE corpus_id=%s "
            "ORDER BY source_name", (args.corpus,)).fetchall()
        for doc_id, name in docs:
            text = "\n".join(r[0] for r in conn.execute(
                "SELECT text FROM chunks WHERE doc_id=%s AND tier='child' "
                "ORDER BY chunk_index", (doc_id,)).fetchall())
            po = P.count_opportunities(text)
            co = C.count_opportunities(split_sentences(text))
            pa = conn.execute(
                "SELECT count(*) FROM procedure_artifacts WHERE document_id=%s",
                (doc_id,)).fetchone()[0]
            ca = conn.execute(
                "SELECT count(*) FROM concept_artifacts WHERE document_id=%s",
                (doc_id,)).fetchone()[0]
            totals["proc_opp"] += po
            totals["proc_art"] += pa
            totals["conc_opp"] += co
            totals["conc_art"] += ca
            rows_out.append((doc_id, name, po, pa, co, ca))

        print(f"{'document':<36}{'proc_opp':>9}{'proc_art':>9}"
              f"{'conc_opp':>9}{'conc_art':>9}{'capped':>8}")
        for doc_id, name, po, pa, co, ca in rows_out:
            print(f"{(name or doc_id)[:35]:<36}{po:>9}{pa:>9}{co:>9}{ca:>9}"
                  f"{'YES' if ca >= CONCEPT_CAP else '':>8}")
        print(f"{'TOTAL':<36}{totals['proc_opp']:>9}{totals['proc_art']:>9}"
              f"{totals['conc_opp']:>9}{totals['conc_art']:>9}")

        def ratio(a: int, b: int) -> str:
            return f"{a}/{b} = {100.0 * a / b:.2f}%" if b else "no opportunity"

        print(f"\nPROCEDURE capture: {ratio(totals['proc_art'], totals['proc_opp'])}")
        print(f"CONCEPT   capture: {ratio(totals['conc_art'], totals['conc_opp'])}")

        if args.backfill:
            for doc_id, _name, po, pa, co, ca in rows_out:
                for lane, opp, acc, capped in (
                        ("procedure", po, pa, False),
                        ("concept", co, ca, ca >= CONCEPT_CAP)):
                    disposition = ("NO_OPPORTUNITY" if opp <= 0
                                   else "ACCEPTED" if acc > 0 else "GATED")
                    conn.execute(
                        """INSERT INTO knowledge_lane_attempts
                             (doc_id, corpus_id, lane, opportunities,
                              accepted, capped, disposition, bundle_hash)
                           VALUES (%s,%s,%s,%s,%s,%s,%s,'backfill')
                           ON CONFLICT (doc_id, lane) DO UPDATE SET
                             opportunities=EXCLUDED.opportunities,
                             accepted=EXCLUDED.accepted,
                             capped=EXCLUDED.capped,
                             disposition=EXCLUDED.disposition,
                             created_at=now()""",
                        (doc_id, args.corpus, lane, opp, acc, capped,
                         disposition))
            print(f"\nbackfilled knowledge_lane_attempts for {len(rows_out)} documents")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
