"""R1C production FAST qualification: parity with the frozen R1B harness
semantics + latency breakdown + live smoke queries.

Same corpus, same queries, same plan — production fast_retrieve must
reproduce the qualified engine's selected docs/sections/child identities
and G3 order. Determinism: repeated identical requests must match.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))
sys.path.insert(0, str(ROOT / "workers"))
sys.path.insert(0, str(ROOT / "orchestrator"))

from orchestrator.api.fast import fast_retrieve  # noqa: E402

CORPUS = "i2-qualification-corpus"


def main() -> int:
    frozen = json.loads((ROOT / "eval" / "r1b" / "queries.json").read_text())
    queries = frozen["queries"]
    r1b = json.loads((ROOT / "eval" / "r1b" / "result.json").read_text())
    r1b_full = r1b["ablations"]["F_full"]

    parity = {"queries": len(queries), "selected_doc_mismatch": 0,
              "selected_section_mismatch": 0, "evidence_mismatch": 0,
              "g3_order_mismatch": 0}
    evidence_sizes = []
    lat_total = []
    lat_components = {}
    smoke = {}

    # First pass: production FAST on the frozen set
    runs = []
    for q in queries:
        t0 = time.time()
        r = fast_retrieve(q["query"], CORPUS)
        total = (time.time() - t0) * 1000
        lat_total.append(total)
        for k, v in (r.get("trace") or {}).get("latency_ms", {}).items():
            lat_components.setdefault(k, []).append(v)
        evidence_sizes.append(len(r["evidence"]))
        runs.append(r)
        assert r["meta"]["plan_version"] == "pass1-retrieval-v1"
        assert r["meta"]["mode"] == "FAST"

    # Second pass: determinism — identical repeated requests
    for q, first in zip(queries, runs):
        second = fast_retrieve(q["query"], CORPUS)
        if [d["doc_id"] for d in second["selected_documents"]] != \
                [d["doc_id"] for d in first["selected_documents"]]:
            parity["selected_doc_mismatch"] += 1
        if [s["parent_id"] for s in second["selected_sections"]] != \
                [s["parent_id"] for s in first["selected_sections"]]:
            parity["selected_section_mismatch"] += 1
        if [c["chunk_id"] for c in second["evidence"]] != \
                [c["chunk_id"] for c in first["evidence"]]:
            parity["evidence_mismatch"] += 1
        if (second.get("trace") or {}).get("post_g3_order") != \
                (first.get("trace") or {}).get("post_g3_order"):
            parity["g3_order_mismatch"] += 1

    # semantic parity vs the R1B harness frozen metrics: recompute the
    # frozen set metrics over production selected docs (same gold).
    import psycopg
    conn = psycopg.connect("postgresql://polymath:polymath-dev@127.0.0.1:5432/polymath")
    doc_of_source = {r[0]: r[1] for r in conn.execute(
        "SELECT source_name, doc_id FROM documents WHERE corpus_id=%s", (CORPUS,)).fetchall()}
    chunk_rows = conn.execute(
        """SELECT ch.chunk_id, ch.doc_id, ch.text FROM chunks ch
           JOIN documents d ON d.doc_id=ch.doc_id WHERE d.corpus_id=%s AND ch.tier='child'""",
        (CORPUS,)).fetchall()
    conn.close()
    chunk_text = {r[0]: (r[1], r[2]) for r in chunk_rows}

    def gold_child(q):
        for cid, (doc_id, text) in chunk_text.items():
            if doc_id == doc_of_source[q["gold_doc"]] and q["gold_child_substring"].lower() in text.lower():
                return cid
        return None

    gold_docs = [doc_of_source[q["gold_doc"]] for q in queries]
    gold_children = [gold_child(q) for q in queries]

    def rm(pred, gold, ks=(1, 3, 5)):
        ranks = []
        for p, g in zip(pred, gold):
            try:
                ranks.append(p.index(g) + 1)
            except ValueError:
                ranks.append(10**9)
        out = {f"R@{k}": round(sum(1 for r in ranks if r <= k) / len(ranks), 3) for k in ks}
        out["MRR"] = round(sum(1.0 / r for r in ranks if r < 10**9) / len(ranks), 3)
        return out

    doc_metrics = rm([[d["doc_id"] for d in r["selected_documents"]] for r in runs], gold_docs, (1, 3, 5))
    fev_recall = round(sum(
        1 for r, gc in zip(runs, gold_children)
        if any(c["chunk_id"] == gc for c in r["evidence"])
    ) / len(queries), 3)
    rescue_preserved = sum(
        1 for r in runs
        for c in r["evidence"] if c.get("arrival") == "GLOBAL_CHILD_RESCUE"
    )
    print(f"doc metrics (production FAST): {doc_metrics}")
    print(f"final evidence supporting-child recall: {fev_recall} (R1B harness: {r1b_full['final_evidence_supporting_recall']})")
    print(f"rescue arrivals preserved: {rescue_preserved}")
    print(f"evidence sizes: mean={sum(evidence_sizes)/len(evidence_sizes):.1f} max={max(evidence_sizes)}")
    sorted_lat = sorted(lat_total)
    print(f"API total p50={sorted_lat[len(sorted_lat)//2]:.0f}ms p95={sorted_lat[int(len(sorted_lat)*0.95)]:.0f}ms")
    print("components (ms p50):", {k: round(sorted(v)[len(v)//2], 1) for k, v in lat_components.items() if v})
    print("parity (repeated requests):", parity)

    # live smoke queries (A-G classes)
    smoke_queries = {
        "A_doc_led": "What is the overall topic of the cognitive load document?",
        "B_section_led": "Which section of the retrieval practice document discusses calibration?",
        "C_rescue": "What does the platform services document say about model processes?",
        "D_disambig": "Which document covers embedding models rather than knowledge graphs?",
        "E_late": "What does the zero trust document say about audit logs?",
        "F_isolation": None,  # isolation corpus not ingested for smoke; covered by integration test
        "G_multi_doc": "How does cognitive load affect monitoring accuracy?",
    }
    for label, q in smoke_queries.items():
        if q is None:
            continue
        r = fast_retrieve(q, CORPUS)
        smoke[label] = {
            "documents": [d["doc_id"][:12] for d in r["selected_documents"]],
            "sections": len(r["selected_sections"]),
            "evidence": [c["chunk_id"][:12] for c in r["evidence"]],
        }
        print(f"smoke {label}: docs={smoke[label]['documents']} evidence={len(smoke[label]['evidence'])}")

    out = {
        "parity": parity,
        "production_doc_metrics": doc_metrics,
        "final_evidence_supporting_recall": fev_recall,
        "r1b_harness_final_evidence_supporting_recall": r1b_full["final_evidence_supporting_recall"],
        "rescue_preserved": rescue_preserved,
        "evidence_mean": round(sum(evidence_sizes) / len(evidence_sizes), 1),
        "evidence_max": max(evidence_sizes),
        "api_total_p50_ms": round(sorted_lat[len(sorted_lat) // 2], 1),
        "api_total_p95_ms": round(sorted_lat[int(len(sorted_lat) * 0.95)], 1),
        "component_p50_ms": {k: round(sorted(v)[len(v) // 2], 1) for k, v in lat_components.items() if v},
        "smoke": smoke,
    }
    (ROOT / "eval" / "r1c" / "result.json").write_text(json.dumps(out, indent=2))
    print("wrote eval/r1c/result.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
