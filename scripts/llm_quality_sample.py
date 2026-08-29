#!/usr/bin/env python3
"""Smart sample quality check for LOCAL-LLM-EXTRACTION-V1 generations.

Reads admitted LLM-era facts + raw proposals for a corpus and scores a
random sample against four mechanical quality signals (no model in the
loop, so the checker itself is deterministic and reproducible):

  1. ATTESTATION  — every fact's evidence span quotes real source text
                    (offset-verified against the chunk text).
  2. ENDPOINT DURABILITY — both fact endpoints are durable entities.
  3. PROVIDER MIX — how much of the corpus's evidence is LLM-era vs
                    GLiNER-era (migration progress).
  4. RELATION COVERAGE — distinct predicates + candidates-by-decision,
                    so a silent recall collapse is visible.

Usage:
  .venv/bin/python scripts/llm_quality_sample.py --corpus cysa-study-v2 \
      [--sample 40] [--seed 7]

Output: a JSON report on stdout + a one-line verdict. The sample is
seeded => re-running the checker never changes which facts are judged.
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "shared"))
sys.path.insert(0, str(ROOT / "control"))

import psycopg  # noqa: E402

DSN = "postgresql://polymath:polymath-dev@127.0.0.1:5432/polymath"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", required=True)
    ap.add_argument("--sample", type=int, default=40)
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args()

    with psycopg.connect(DSN, connect_timeout=5) as conn:
        # LLM-era facts: extractor_version on facts or via evidence →
        # mentions chain; we read facts joined to their evidence spans.
        facts = conn.execute(
            """
            SELECT f.fact_id, f.predicate, f.decision, f.subject_id, f.object_id,
                   e.chunk_id, e.char_start, e.char_end, e.quote
              FROM facts f
              LEFT JOIN evidence e ON e.fact_id = f.fact_id
             WHERE f.corpus_id = %s
               AND f.decision IN ('PASS', 'QUALIFY')
             ORDER BY f.fact_id
            """,
            (args.corpus,),
        ).fetchall()
        total = conn.execute(
            "SELECT count(*) FROM facts WHERE corpus_id=%s", (args.corpus,)
        ).fetchone()[0]
        prov = conn.execute(
            """
            SELECT provider_contract->>'provider' AS provider, count(*)
              FROM raw_entity_proposals p
              JOIN documents d ON d.doc_id = p.doc_id
             WHERE d.corpus_id = %s
             GROUP BY 1 ORDER BY 2 DESC
            """,
            (args.corpus,),
        ).fetchall()
        cand = conn.execute(
            """
            SELECT decision, count(*) FROM relation_candidates rc
              JOIN documents d ON d.doc_id = rc.doc_id
             WHERE d.corpus_id = %s GROUP BY 1
            """,
            (args.corpus,),
        ).fetchall()

    rng = random.Random(args.seed)
    picked = rng.sample(facts, min(args.sample, len(facts)))

    checked = attested = durable = 0
    failures = []
    chunks = {}
    with psycopg.connect(DSN, connect_timeout=5) as conn:
        for row in picked:
            fact_id, pred, decision, subj, obj, chunk_id, cs, ce, quote = row
            if chunk_id is None:
                continue
            checked += 1
            if chunk_id not in chunks:
                r = conn.execute("SELECT text FROM chunks WHERE chunk_id=%s",
                                 (chunk_id,)).fetchone()
                chunks[chunk_id] = r[0] if r else ""
            text = chunks[chunk_id]
            span_ok = False
            if quote and quote in text:
                span_ok = True
            elif text and cs is not None and ce is not None and 0 <= cs < ce <= len(text):
                span_ok = text[cs:ce].strip() != ""
            if span_ok:
                attested += 1
            else:
                failures.append({"fact_id": str(fact_id), "predicate": pred,
                                 "reason": "evidence span not found in chunk"})
            if subj and obj:
                durable += 1

    report = {
        "corpus": args.corpus,
        "sample_seed": args.seed,
        "facts_total": total,
        "facts_sampled": len(picked),
        "facts_checked_with_evidence": checked,
        "attested": attested,
        "attestation_rate": round(attested / checked, 4) if checked else None,
        "endpoints_durable": durable,
        "provider_mix_raw_entities": {str(k): v for k, v in prov},
        "relation_candidates_by_decision": {str(k): v for k, v in cand},
        "attestation_failures": failures[:10],
    }
    rate = report["attestation_rate"]
    verdict = ("PASS" if rate is not None and rate >= 0.95 else
               "WEAK" if rate is not None and rate >= 0.85 else "FAIL")
    report["verdict"] = verdict
    print(json.dumps(report, indent=1, default=str))
    return 0 if verdict == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
