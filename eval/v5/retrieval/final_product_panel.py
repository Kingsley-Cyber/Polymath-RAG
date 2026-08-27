"""FINAL-PRODUCT-PANEL-V1: the Phase 11-16 measured qualification.

Runs the corrected public query plane end to end:
  - transcript-qual-v1 (fresh real transcript): VECTOR/HYBRID/GRAPH,
    /ask procedure+concept retrieval, corpus-map trace, grounded /chat,
    nonce + neighboring-topic abstention, GRAPH zero-vs-failure.
  - core-3-v1 (the real transcript corpus the SMART verification
    traced internally): the TRANSCRIPT FACT → Neo4j → public GRAPH →
    evidence-locator proof, now through HTTP.
  - release-books-v1 (FACT-heavy reference corpus): GRAPH at scale.

Latency: n runs per mode, nearest-rank p50/p95/max, warm (first call
per mode discarded as warmup). Output: JSON to stdout + saved file.
"""
from __future__ import annotations

import json
import statistics
import sys
import time
from pathlib import Path

import httpx

BASE = "http://127.0.0.1:7200"
OUT = Path(__file__).parent / "FINAL-PRODUCT-PANEL-RESULTS.json"
N = 6  # per timed probe (first discarded as warmup)

results: dict = {"panel": "final-product-panel-v1", "probes": []}


def probe(name: str, method: str, route: str, body: dict,
          check=None, timed: bool = True, n: int = N) -> dict:
    lat = []
    last = None
    runs = n if timed else 1
    for i in range(runs):
        t0 = time.perf_counter()
        r = httpx.post(f"{BASE}{route}", json=body, timeout=300) \
            if method == "POST" else httpx.get(f"{BASE}{route}",
                                               params=body, timeout=300)
        ms = (time.perf_counter() - t0) * 1000
        if i > 0 or runs == 1:
            lat.append(ms)
        last = r
    ok = last.status_code == 200
    detail = ""
    payload = None
    try:
        payload = last.json()
    except Exception:
        detail = last.text[:200]
    checked = None
    if ok and check and payload is not None:
        try:
            checked = bool(check(payload))
        except Exception as exc:
            checked = False
            detail = f"check raised {type(exc).__name__}: {exc}"
    entry = {
        "name": name, "route": route, "status": last.status_code,
        "http_ok": ok, "check": checked, "detail": detail,
    }
    if lat:
        ranked = sorted(lat)
        entry["latency_ms"] = {
            "n": len(lat),
            "p50": round(ranked[max(0, int(0.5 * len(ranked)) - 1)], 1),
            "p95": round(ranked[max(0, int(0.95 * len(ranked)) - 1)], 1),
            "max": round(ranked[-1], 1),
        }
    results["probes"].append(entry)
    flag = "ok " if (ok and checked is not False) else "FAIL"
    lat_s = f" p50={entry.get('latency_ms', {}).get('p50', '-')}ms" if lat else ""
    print(f"  [{flag}] {name:44s} HTTP {last.status_code}{lat_s} {detail}")
    return payload if payload is not None else {}


def main() -> int:
    QUAL = "transcript-qual-v1"
    CORE = "core-3-v1"
    BOOKS = "release-books-v1"

    print("== VECTOR / HYBRID / GRAPH on the fresh transcript ==")
    probe("vector_fast_andromeda", "POST", "/retrieve",
          {"query": "What is Andromeda?", "corpus_id": QUAL, "mode": "FAST"},
          check=lambda p: p["meta"]["mode"] == "FAST" and p["evidence"])
    probe("hybrid_andromeda", "POST", "/retrieve",
          {"query": "creative diversity testing campaign related media",
           "corpus_id": QUAL, "mode": "HYBRID"},
          check=lambda p: p["meta"]["mode"] == "HYBRID" and p["evidence"])
    g = probe("graph_andromeda_zero_ok", "POST", "/retrieve",
              {"query": "How is Andromeda related to Meta?",
               "corpus_id": QUAL, "mode": "GRAPH"},
              check=lambda p: p["meta"]["mode"] == "GRAPH"
              and "graph_fact_count" in p["meta"])
    results["qual_graph_fact_count"] = (g.get("meta") or {}).get("graph_fact_count")

    print("== /ask stored objects + corpus map ==")
    a = probe("ask_concept_andromeda", "POST", "/ask",
              {"question": "What is Andromeda?", "corpus_id": QUAL},
              check=lambda p: any(
                  c["name"].lower() == "andromeda"
                  for c in p["objects"]["concepts"]))
    results["ask_map_trace"] = (a.get("map") or {})
    probe("ask_procedure_setup", "POST", "/ask",
          {"question": "How do I set up the related media testing campaign?",
           "corpus_id": QUAL},
          check=lambda p: len(p["objects"]["procedures"]) >= 1)

    print("== grounded answers + abstention ==")
    probe("chat_supported_andromeda", "POST", "/chat",
          {"message": "What is the Andromeda update Facebook made?",
           "corpus_id": QUAL},
          check=lambda p: p["meta"]["abstained"] is False
          and p["meta"]["verdict"] == "supported" and p["citations"])
    probe("chat_nonce_abstains", "POST", "/chat",
          {"message": "what is the glorbofex spindle quotient",
           "corpus_id": QUAL},
          check=lambda p: p["meta"]["abstained"] is True
          and p["meta"]["verdict"] == "insufficient_evidence")
    probe("chat_neighbor_abstains", "POST", "/chat",
          {"message": "How much does Jon Loomer charge for consulting?",
           "corpus_id": QUAL},
          check=lambda p: p["meta"]["abstained"] is True)

    print("== transcript FACT → public GRAPH → evidence (core-3-v1) ==")
    g2 = probe("graph_core3_transcript_fact", "POST", "/retrieve",
               {"query": "how does unsloth relate to google colab fine-tuning",
                "corpus_id": CORE, "mode": "GRAPH"},
               check=lambda p: p["meta"]["graph_fact_count"] >= 1)
    facts = (g2.get("graph_relationships") or [])
    results["core3_graph_facts"] = facts[:5]
    ev = probe("evidence_core3_graph_bundle", "POST", "/evidence",
               {"query": "how does unsloth relate to google colab fine-tuning",
                "corpus_id": CORE, "mode": "GRAPH"},
               check=lambda p: p["meta"].get("mode") == "GRAPH"
               and p.get("evidence_bundle"))
    locators = [
        (i.get("source_span") or {}).get("locator")
        for i in (ev.get("evidence_bundle") or [])
        if i.get("kind") == "claim"
    ]
    results["core3_claim_locators"] = [l for l in locators if l][:5]
    probe("chat_core3_graph_grounded", "POST", "/chat",
          {"message": "how does unsloth relate to google colab fine-tuning",
           "corpus_id": CORE, "mode": "GRAPH"},
          check=lambda p: isinstance(p["meta"]["abstained"], bool))

    print("== FACT-heavy GRAPH at scale (release-books-v1) ==")
    probe("graph_books_scale", "POST", "/retrieve",
          {"query": "what influences persuasion and attitude change",
           "corpus_id": BOOKS, "mode": "GRAPH"},
          check=lambda p: p["meta"]["mode"] == "GRAPH")

    print("== semantic readiness ==")
    probe("semantic_readiness_qual", "GET", "/semantic_readiness",
          {"corpus_id": QUAL},
          check=lambda p: p["verdict"] in ("SEMANTIC_COMPLETE",
                                           "SEMANTIC_INCOMPLETE"),
          timed=False)

    failed = [p for p in results["probes"]
              if not p["http_ok"] or p["check"] is False]
    results["failed"] = [p["name"] for p in failed]
    OUT.write_text(json.dumps(results, indent=1))
    print(f"\n  => {'PASS' if not failed else 'FAIL'} "
          f"({len(results['probes']) - len(failed)}/{len(results['probes'])})"
          f"  results: {OUT}")
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
