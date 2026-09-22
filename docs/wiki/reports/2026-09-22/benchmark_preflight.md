---
title: "BENCHMARK_PREFLIGHT: PASS"
last_reviewed: 2026-09-21
kind: gate_verdict
gate_version: 1.0.1
---

# BENCHMARK_PREFLIGHT: PASS

gate_version `1.0.1` · gate_commit `2167569619537cec95e2d263877b90a1e1a17d43` · phase `benchmark-preflight` · **overall PASS**

| id | check | status | facts |
|---|---|---|---|
| B0 | manifest names this gate version and a seed policy | PASS | `{"manifest_gate_version": "1.0.1"}` |
| B1 | the seed is the manifest's pinned seed (normalised sha256) | PASS | `{"expected": "aa08dc88d58b39dc612ca8b833db5c7857ed21b736c7335098f700afd1f3d420", "seed_sha256": "aa08dc88d58b39dc612ca8b833db5c7857ed21b736c7335098f700afd1f3d420"}` |
| B2 | the seed names no market / population / product category / desired product / consumer problem / niche term | PASS | `{"forbidden_terms_found": []}` |
| B3 | required stages and allowed terminal states declared | PASS | `{"allowed_terminal_states": ["SCORED", "HARD_GATE_UNMET", "NO_DEFENSIBLE_BRIDGE", "MARKET_ALREADY_SOLVED", "SUPPLY_UNPROVEN", "LAWFUL_REFUSAL"], "required_stages": ["T1", "T2", "T3", "T4", "T5", "T6", "T7", "T8", "T9", "T10", "T11"]}` |
