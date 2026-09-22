---
title: "INTEGRATION_GATE: PASS · safe_to_bounce: true"
last_reviewed: 2026-09-21
kind: gate_verdict
gate_version: 1.0.1
---

# INTEGRATION_GATE: PASS · safe_to_bounce: true

gate_version `1.0.0` · gate_commit `8a66934a94b1a12ba66360e06f5dd894d52394f9` · phase `integration` · **overall PASS**

| id | check | status | facts |
|---|---|---|---|
| I1 | production contains the restoration tip | PASS | `{"tip": "a7b9f08"}` |
| I2 | Trail pin == the accepted HR6 commit | PASS | `{"expected": "829a0abf853fdb0c3589c4162177beb8c836c515", "pinned": "829a0abf853fdb0c3589c4162177beb8c836c515"}` |
| I3 | every embedded Trail file equals its pinned sha256 (and the commit's blob when the Trail worktree is given) | PASS | `{"blob_checked": true, "blob_mismatch": [], "files": 30, "sha_mismatch": []}` |
| I4 | manifest adapter_version == expected and every Trail step opts in to the extended wire | PASS | `{"adapter_version": "0.6.0", "opted_in": true, "trail_steps": 12}` |
| I5 | receipt contract: contract and engine copy byte-equal; hypothesis_relations in the receipt and the admission contract | PASS | `{"byte_equal": true, "relation_field": true}` |
| I6 | working tree clean | PASS | `{"dirty": []}` |
| I7 | no stale generated contract copy under adapters/ecommerce/schemas | PASS | `{"stale": []}` |
| I8 | the three previously untestable call sites pass on this checkout (never skipped) | PASS | `{"exit": 0, "passed": 4}` |
| I9 | focused adapter suites pass (DB-free) | PASS | `{"exit": 0, "passed": 122, "suites": ["tests/determinism/test_adapter_semantic_view.py", "tests/determinism/test_adapter_research_fidelity.py", "tests/determinism/test_adapter_product_reality.py", "tests/determinism/test_adapter_dossier_fidelity.py", "tests/determinism/test_chat_evidence_route.py", ` |
| I10 | engine suite passes (adapters/ecommerce, Hermes venv, temp loop db) | PASS | `{"exit": 0, "ratio": null, "tail": ["ALL 609 CHECKS PASSED"]}` |
| I11 | repository guards 0 / 0 / 0 / READY | PASS | `{"agent_preflight": {"exit": 0, "tail": ["preflight: ok"]}, "bundle_integrity": {"exit": 0, "tail": ["  READY"]}, "repo_guard": {"exit": 0, "tail": ["repo guard: ok"]}, "wiki_worm": {"exit": 0, "tail": ["wiki: ok"]}}` |
| I12 | embedded Trail parity (sha pins + recorded envelopes replay) | PASS | `{"exit": 0, "passed": 7, "suites": ["tests/contracts/test_trail_core_embedding.py", "tests/determinism/test_trail_core_recorded_equivalence.py"]}` |
| I13 | 0 open adapter runs, 0 leased tickets | PASS | `{"leased_tickets": 0, "open_runs": 0}` |
