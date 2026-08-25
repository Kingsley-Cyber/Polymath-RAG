"""G1 QUALIFICATION: hash-embed-v1 vs neural-embed-v1, same queries.

Behavioral qualification for the owner's G1 cutover decision. Each
query carries a WEAK expected-source label (a source_name substring) —
enough to measure whether a mode finds the right BOOK, not enough to
claim sentence-level accuracy. Verdict rule (agreed with owner):
neural must materially beat hash on SEMANTIC classes while never
losing exact-match classes.

Usage:
  .venv/bin/python eval/v5/retrieval/compare_hash_neural.py \
      --corpus release-books-v1
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "shared"))
sys.path.insert(0, str(ROOT / "eval" / "v5" / "retrieval"))

DSN = "postgresql://polymath:polymath-dev@127.0.0.1:5432/polymath"

# (id, class, query, weak_expected_source_substring)
QUERIES = [
    ("q01", "semantic", "keeping services reliable when everything is "
     "on fire and customers are angry", "site_reliability"),
    ("q02", "semantic", "how organizations decide what software to buy "
     "and how that shapes their architecture", "fundamentals_of_software"),
    ("q03", "semantic", "convincing people to change their minds without "
     "authority", "influence_psychology"),
    ("q04", "semantic", "designing systems that keep working when parts "
     "of them fail randomly", "release_it"),
    ("q05", "identifier", "Splunk deployment on AWS", "splunk"),
    ("q06", "identifier", "Wazuh security monitoring", "wazuh"),
    ("q07", "procedure", "malware analysis practical steps", "malware"),
    ("q08", "exact_fact", "enterprise integration patterns messaging",
     "enterprise_integration"),
    ("q09", "broad", "data engineering pipelines", "data_engineering"),
    ("q10", "no_answer", "the mating habits of Antarctic penguins", ""),
]

SEMANTIC = {q[0] for q in QUERIES if q[1] == "semantic"}


def run(contract_short: str, corpus: str, k: int):
    from three_mode_benchmark import Bench
    b = Bench(corpus, contract_short, k)
    b.setup()
    out = {}
    for qid, cls, query, _ in QUERIES:
        t0 = time.perf_counter()
        hits = b.dense(query, ["routing_child", "child_chunk"], k)
        out[qid] = {
            "latency_ms": round((time.perf_counter() - t0) * 1000, 1),
            # top-k doc ids in rank order (dense lane only — this is a
            # VECTOR-quality comparison, fusion is out of scope here)
            "doc_rank": [h["doc"] for h in hits],
            "top_texts": [h["text"][:120] for h in hits[:3]],
        }
    b.close()
    return out


def docs_with_sources(conn) -> dict[str, str]:
    return {r[0]: r[1] for r in conn.execute(
        "SELECT doc_id, source_name FROM documents").fetchall()}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", default="release-books-v1")
    ap.add_argument("--k", type=int, default=10)
    args = ap.parse_args()

    import psycopg
    conn = psycopg.connect(DSN, connect_timeout=10)
    src = docs_with_sources(conn)

    results = {"hash": run("hash-embed-v1", args.corpus, args.k),
               "neural": run("neural-embed-v1", args.corpus, args.k)}

    score = {"hash": {}, "neural": {}}
    detail_lines = ["| query | class | expect | hash hit@k | "
                    "neural hit@k |", "|---|---|---|---|---|"]
    for qid, cls, query, expect in QUERIES:
        row_cells = [qid, cls, expect or "—"]
        for prov in ("hash", "neural"):
            hit = False
            if expect:
                for doc_id in results[prov][qid]["doc_rank"]:
                    if expect.lower() in (src.get(doc_id) or "").lower():
                        hit = True
                        break
            score[prov][qid] = hit
            row_cells.append("✓" if hit else "✗")
        detail_lines.append("| " + " | ".join(row_cells) + " |")

    sem_h = sum(1 for q in SEMANTIC if score["hash"].get(q))
    sem_n = sum(1 for q in SEMANTIC if score["neural"].get(q))
    n_sem = len(SEMANTIC)
    ident = [q[0] for q in QUERIES if q[1] in ("identifier", "procedure",
                                               "exact_fact")]
    id_h = sum(1 for q in ident if score["hash"].get(q))
    id_n = sum(1 for q in ident if score["neural"].get(q))
    n_id = len(ident)

    verdict_ok = sem_n > sem_h and id_n >= id_h

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    report = {
        "corpus": args.corpus, "captured_at": stamp, "k": args.k,
        "verdict": {
            "hash_semantic": f"{sem_h}/{n_sem}",
            "neural_semantic": f"{sem_n}/{n_sem}",
            "hash_exact": f"{id_h}/{n_id}",
            "neural_exact": f"{id_n}/{n_id}",
            "qualified": verdict_ok,
        },
        "results": results,
    }

    outdir = ROOT / "eval" / "v5" / "retrieval"
    jpath = outdir / f"G1-HASH-VS-NEURAL-{stamp}.json"
    jpath.write_text(json.dumps(report, indent=1))

    lines = [
        "# G1 QUALIFICATION: HASH vs NEURAL (behavioral)", "",
        f"- corpus: `{args.corpus}` · k={args.k} · captured {stamp}",
        "",
        "| provider | semantic hit | identifier/exact hit |",
        "|---|---|---|",
        f"| hash-embed-v1 | {sem_h}/{n_sem} | {id_h}/{n_id} |",
        f"| neural-embed-v1 | **{sem_n}/{n_sem}** | {id_n}/{n_id} |",
        "",
        *detail_lines,
        "",
        f"VERDICT: {'NEURAL CUTOVER QUALIFIED' if verdict_ok else 'NOT QUALIFIED'} "
        "(rule: neural materially beats hash on semantic classes while "
        "never losing identifier/exact classes)",
    ]
    (outdir / "G1-HASH-VS-NEURAL.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines[-6:-2]))
    print(f"VERDICT: {'QUALIFIED' if verdict_ok else 'NOT QUALIFIED'}")
    print(f"written: {jpath}")
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
