"""E5B part 2 — consolidated qualification evidence (frozen)."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

routing = json.loads((ROOT / "eval" / "e5b" / "routing_ab.json").read_text())
coverage = json.loads((ROOT / "eval" / "e5b" / "coverage_ab.json").read_text())
retention = json.loads((ROOT / "eval" / "e5b" / "retention.json").read_text())
zero = json.loads((ROOT / "eval" / "e5b" / "zero_delta.json").read_text())

qs = routing["query_level"]
reg_doc = [q for q in qs if q["candidate_doc_rank"] > q["baseline_doc_rank"]]
imp_doc = [q for q in qs if q["candidate_doc_rank"] < q["baseline_doc_rank"]]
unch_doc = [q for q in qs if q["candidate_doc_rank"] == q["baseline_doc_rank"]]
reg_sec = [q for q in qs if q["candidate_sec_rank"] > q["baseline_sec_rank"]]
imp_sec = [q for q in qs if q["candidate_sec_rank"] < q["baseline_sec_rank"]]
unch_sec = [q for q in qs if q["candidate_sec_rank"] == q["baseline_sec_rank"]]

psych = retention["gold_ranks"]
psych_ok = sum(1 for v in psych.values() if v["status"] == "GENERATED_AND_ADMITTED")
psych_budgeted = sum(1 for v in psych.values() if v["status"] == "GENERATED_BUT_BUDGETED_OUT")
psych_other = 13 - psych_ok - psych_budgeted

out = {
    "gate": "E5B part 2 — routing qualification",
    "base_commit": "ba363ec",
    "in_summary_text": {
        "present_in_ba363ec": True,
        "behavior": "6th component of the deterministic ranking tuple: +1 when "
                    "normalized concept is a substring of the normalized chunk-summary "
                    "concat (document_inventory) or the section_summary argument "
                    "(section_inventory). Used exactly as committed; weight/order/semantics "
                    "unchanged.",
    },
    "contracts": {
        "concept": "concept-inventory-v1",
        "routing": "routing-concept-enriched-v1",
        "embedding": {
            "model": "Qwen/Qwen3-Embedding-0.6B",
            "revision": "97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3",
            "collections": routing["e5b_collections"],
        },
    },
    "stack": {
        "postgres": "up (127.0.0.1:5432)",
        "qdrant": "up (127.0.0.1:6334, prod collections untouched)",
        "neo4j": "up (127.0.0.1:7475/7688)",
        "redis": "up (recreated to apply host port mapping)",
        "embedder": "ready (pin verified via /sidecars)",
        "gliner": "ready",
        "reranker": "ready",
        "orchestrator": "up (:7200, /ready true)",
        "control": "up (ticking)",
        "workers": "8/8 up",
    },
    "frozen_artifact_discrepancy": {
        "queries_file": "eval/r1b/queries.json (git-frozen at 1c75735)",
        "raw_sha256": routing["queries_sha256"],
        "recorded_sha_in_r1b_result": "0ec1b8724f7fbd712a2de660bbcbddf41905bb6a7bde595ef5b893cb40f9c83b",
        "note": "The sha recorded in eval/r1b/result.json does not match any natural "
                "hashing of the committed queries file; it is a hardcoded constant in "
                "eval/r1b/measure.py (stale label). The git-frozen file is authoritative: "
                "this harness reproduces the frozen R1B baseline exactly (doc R@1 0.882, "
                "sec R@1 0.882, MRR 0.910/0.897), validating measurement fidelity.",
    },
    "psychology": {
        "gold": 13,
        "generated_and_admitted": psych_ok,
        "generated_but_budgeted_out": psych_budgeted,
        "not_generated_or_filtered": psych_other,
        "gold_rank_table": {g: {"rank": v["rank"], "status": v["status"]}
                            for g, v in psych.items()},
    },
    "document_routing": routing["doc"],
    "section_routing": routing["sec"],
    "r1a_coverage": coverage["aggregate"],
    "query_deltas": {
        "doc": {"improved": len(imp_doc), "unchanged": len(unch_doc),
                "regressed": len(reg_doc),
                "regressed_queries": [
                    {"query_id": q["query_id"], "gold_doc": q["gold_doc"],
                     "baseline_rank": q["baseline_doc_rank"],
                     "candidate_rank": q["candidate_doc_rank"]} for q in reg_doc],
                "improved_queries": [
                    {"query_id": q["query_id"], "gold_doc": q["gold_doc"],
                     "baseline_rank": q["baseline_doc_rank"],
                     "candidate_rank": q["candidate_doc_rank"]} for q in imp_doc]},
        "sec": {"improved": len(imp_sec), "unchanged": len(unch_sec),
                "regressed": len(reg_sec),
                "regressed_queries": [
                    {"query_id": q["query_id"], "gold_doc": q["gold_doc"],
                     "baseline_rank": q["baseline_sec_rank"],
                     "candidate_rank": q["candidate_sec_rank"]} for q in reg_sec],
                "improved_queries": [
                    {"query_id": q["query_id"], "gold_doc": q["gold_doc"],
                     "baseline_rank": q["baseline_sec_rank"],
                     "candidate_rank": q["candidate_sec_rank"]} for q in imp_sec]},
    },
    "regression_observation": {
        "p1_sectionled_2": "psych/retrieval_practice.md doc 1->3, sec 1->3. The "
                          "iso/memory_note.txt concept list ('stores calibration history', "
                          "'system stores calibration') absorbs the literal query term "
                          "'calibration' and outranks the gold doc.",
        "p1_cross_1": "psych/metacognitive_monitoring.md doc 2->3, sec 2->3. "
                      "psych/working_memory.txt and iso/memory_note.txt (both with "
                      "'memory' concept lists) outrank the gold doc.",
    },
    "zero_delta": zero,
    "determinism": routing["determinism"],
    "performance": {
        "concept_extraction_ms_per_doc": round(
            routing["build"]["extraction_ms_total"] / routing["build"]["docs"], 2),
        "representation_size": {
            "baseline_chars": routing["build"]["chars_baseline"],
            "enriched_chars": routing["build"]["chars_enriched"],
            "delta_pct": round(
                (routing["build"]["chars_enriched"] - routing["build"]["chars_baseline"])
                / routing["build"]["chars_baseline"] * 100, 1),
        },
        "embedding_latency": {
            "baseline_ms": routing["build"]["embed_ms_baseline"],
            "enriched_ms": routing["build"]["embed_ms_enriched"],
        },
        "search_latency_ms": routing["search_latency_ms"],
    },
    "verdict": "REJECT",
    "verdict_reasoning": [
        "Primary doc/sec R@1 regresses 0.882 -> 0.853 (one query each; the two real "
        "regressions are BOTH psychology queries that ranked 1-2 in baseline, the "
        "domain the lane was meant to help).",
        "R1A coverage is unchanged (0.870/0.778/0.889 -> identical); criterion 7 "
        "(meaningful coverage improvement) not met.",
        "Decision rule: 'If routing does not improve or regresses: REJECT E5B "
        "representation even though candidate extraction itself works.'",
        "Part 1 discovery results (13/13 candidates vs GLiNER 2/13) remain valid as "
        "extraction evidence; they do not qualify the routing representation.",
    ],
    "e5c_hypotheses_recorded_only": [
        "admission floor: require occurrence_count >= 2 for routing-representation concepts",
        "summary-co-occurrence gate: admit only concepts present in the doc/section summary",
        "corpus-level frequency normalization (IDF-style)",
        "single-child/short-document budget reduction (tiny docs fill budget with fragments)",
    ],
    "next": "STOP. No production integration, no tuning, no reruns.",
}
(ROOT / "eval" / "e5b" / "evidence_p2.json").write_text(json.dumps(out, indent=2))
print("wrote eval/e5b/evidence_p2.json")
