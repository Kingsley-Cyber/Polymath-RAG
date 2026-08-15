"""R1F GRAPH mode qualification: HYBRID parity, qualified hop1 wiring,
authorization, SPO preservation, bounds, determinism, isolation,
latency. Frozen R1D query set over the frozen I2 corpus.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))
sys.path.insert(0, str(ROOT / "orchestrator"))

import psycopg  # noqa: E402

from orchestrator.api.graph import graph_retrieve  # noqa: E402
from orchestrator.api.hybrid import hybrid_fast_retrieve  # noqa: E402

DSN = "postgresql://polymath:polymath-dev@127.0.0.1:5432/polymath"
CORPUS = "i2-qualification-corpus"


def main():
    frozen = json.loads((ROOT / "eval" / "r1d" / "queries.json").read_text())
    queries = frozen["queries"]

    conn = psycopg.connect(DSN)
    corpus_facts = {r[0] for r in conn.execute("""
        SELECT DISTINCT ev.fact_id FROM evidence ev
          JOIN documents d ON d.doc_id = ev.doc_id WHERE d.corpus_id = %s""",
        (CORPUS,)).fetchall()}
    fact_orientation = {r[0]: (r[1], r[2]) for r in conn.execute("""
        SELECT DISTINCT f.fact_id, f.subject_id, f.object_id FROM facts f
          JOIN evidence ev ON ev.fact_id = f.fact_id
          JOIN documents d ON d.doc_id = ev.doc_id WHERE d.corpus_id = %s""",
        (CORPUS,)).fetchall()}
    corpus_docs = {r[0] for r in conn.execute(
        "SELECT doc_id FROM documents WHERE corpus_id=%s", (CORPUS,)).fetchall()}
    conn.close()

    parity_mismatches = {"docs": 0, "sections": 0, "evidence": 0}
    fact_checks = {"authorized": True, "spo": True, "bounds": True}
    total_facts = 0
    lat_pass1, lat_graph, lat_total = [], [], []

    for q in queries:
        h = hybrid_fast_retrieve(q["query"], CORPUS)
        g = graph_retrieve(q["query"], CORPUS)

        # HYBRID parity: the GRAPH Pass-1 must reproduce HYBRID exactly
        # (identical SETS; document grouping is presentation order)
        if [d["doc_id"] for d in g["documents"]] != \
                [d["doc_id"] for d in h["selected_documents"]]:
            parity_mismatches["docs"] += 1
        g_sections = sorted(s["parent_id"] for d in g["documents"] for s in d["sections"])
        if g_sections != sorted(s["parent_id"] for s in h["selected_sections"]):
            parity_mismatches["sections"] += 1
        g_evidence = sorted(
            [c["chunk_id"] for d in g["documents"]
             for s in d["sections"] for c in s["evidence"]]
            + [c["chunk_id"] for d in g["documents"] for c in d["rescue_evidence"]]
            + [c["chunk_id"] for c in g.get("unassigned_rescue_evidence", [])]
        )
        if g_evidence != sorted(c["chunk_id"] for c in h["evidence"]):
            parity_mismatches["evidence"] += 1

        # graph lane checks
        facts = g["graph_relationships"]
        total_facts += len(facts)
        if len(facts) > 20:
            fact_checks["bounds"] = False
        if len(g["trace"]["graph_seed_surfaces"]) > 8:
            fact_checks["bounds"] = False
        for f in facts:
            if f["fact_id"] not in corpus_facts:
                fact_checks["authorized"] = False
            subj, obj = fact_orientation.get(f["fact_id"], (None, None))
            if subj != f["subject_id"] or obj != f["object_id"]:
                fact_checks["spo"] = False
        lat_pass1.append(g["trace"]["latency_ms"]["pass1"])
        lat_graph.append(g["trace"]["latency_ms"]["graph"])
        lat_total.append(g["trace"]["latency_ms"]["total"])

    # determinism + isolation on a fixed query
    q = "What does zero trust abandon?"
    g1 = graph_retrieve(q, CORPUS)
    g2 = graph_retrieve(q, CORPUS)
    deterministic = (
        [d["doc_id"] for d in g1["documents"]] == [d["doc_id"] for d in g2["documents"]]
        and g1["graph_relationships"] == g2["graph_relationships"]
    )
    iso_leaks = sum(
        1 for f in g1["graph_relationships"] if f["fact_id"] not in corpus_facts
    )

    def p(xs, pct):
        s = sorted(xs)
        return round(s[int(len(s) * pct)], 1)

    out = {
        "queries": len(queries),
        "parity": parity_mismatches,
        "graph_facts_total": total_facts,
        "graph_checks": fact_checks,
        "deterministic": deterministic,
        "iso_leaks": iso_leaks,
        "latency_ms": {
            "pass1_p50": p(lat_pass1, 0.5), "pass1_p95": p(lat_pass1, 0.95),
            "graph_p50": p(lat_graph, 0.5), "graph_p95": p(lat_graph, 0.95),
            "total_p50": p(lat_total, 0.5), "total_p95": p(lat_total, 0.95),
        },
    }
    print(json.dumps(out, indent=1))
    (ROOT / "eval" / "r1f" / "result.json").write_text(json.dumps(out, indent=2))
    print("wrote eval/r1f/result.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
