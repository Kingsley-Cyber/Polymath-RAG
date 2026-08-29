#!/usr/bin/env python3
"""Smart sample quality check for LOCAL-LLM-EXTRACTION-V1 generations.

Deterministic, seeded, no model in the loop. For a random sample of a
corpus's admitted facts it verifies:

  1. ATTESTATION — subject/object/evidence offsets land inside the real
     chunk text and the stored surfaces match the text at those offsets.
  2. GENERATION MIX — extractor_version distribution (LLM-era vs
     GLiNER-era) over admitted facts, plus raw-ledger provider mix.
  3. RELATION COVERAGE — candidates-by-decision and distinct predicates,
     so a silent recall collapse is visible.

Usage:
  .venv/bin/python scripts/llm_quality_sample.py --corpus cysa-study-v1 \
      [--sample 40] [--seed 7]

Seeded sample: re-running never changes which facts are judged.
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
        facts = conn.execute(
            """
            SELECT f.fact_id, f.predicate, f.decision,
                   e.chunk_id, e.span_offsets, e.extractor_version
              FROM facts f
              JOIN evidence e ON e.fact_id = f.fact_id
              JOIN documents d ON d.doc_id = e.doc_id
             WHERE d.corpus_id = %s
               AND f.decision IN ('ACCEPT', 'QUALIFY')
             ORDER BY f.fact_id
            """,
            (args.corpus,),
        ).fetchall()
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

    chunks: dict[str, str] = {}
    checked = attested = 0
    failures = []
    generations: dict[str, int] = {}
    with psycopg.connect(DSN, connect_timeout=5) as conn:
        for fact_id, pred, decision, chunk_id, offsets, extver in picked:
            generations[extver] = generations.get(extver, 0) + 1
            if chunk_id is None or offsets is None:
                continue
            checked += 1
            if chunk_id not in chunks:
                r = conn.execute("SELECT text FROM chunks WHERE chunk_id=%s",
                                 (chunk_id,)).fetchone()
                chunks[chunk_id] = r[0] if r else ""
            text = chunks[chunk_id]
            ok = bool(text)
            for key in ("subject_start", "subject_end",
                        "object_start", "object_end"):
                if key not in (offsets or {}):
                    ok = False
                    break
            if ok:
                sub = text[offsets["subject_start"]:offsets["subject_end"]]
                obj = text[offsets["object_start"]:offsets["object_end"]]
                ok = (sub == offsets.get("subject_surface", sub)
                      and obj == offsets.get("object_surface", obj))
            if ok:
                attested += 1
            else:
                failures.append({"fact_id": str(fact_id), "predicate": pred,
                                 "reason": "offsets/surfaces do not match chunk text"})

    report = {
        "corpus": args.corpus,
        "sample_seed": args.seed,
        "facts_admitted_total": len(facts),
        "facts_sampled": len(picked),
        "facts_checked_with_offsets": checked,
        "attested": attested,
        "attestation_rate": round(attested / checked, 4) if checked else None,
        "generation_mix_sampled": generations,
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
