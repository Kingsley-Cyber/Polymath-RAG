---
change_id: FLEET-MEMORY-REBALANCE-V1
owner: "@king"
date: 2026-09-22
status: complete
architecture_impact: "Runtime topology + budget: the local Qwen3.5-4B extraction sidecar (:8755) leaves the supervised fleet, the autopilot's extract lane and the runtime budget; its memory goes to the query path — reranker MPS cap 3.5 → 6.0 GB, embedder 3.5 → 4.5 GB with 8 texts per device batch (token bound unchanged). Extraction routing is unchanged (CLOUD-FIRST-V1 already sent every document to cloud)."
last_reviewed: 2026-09-22
---

# Fleet memory rebalance — retire the idle 4B extractor, raise the reranker and embedder caps

## Contract
Owner, 2026-09-22: "increase memory ceilings for embedder and reranker; remove the local SLM Qwen model and give its memory to
the reranker and embedding model — but first tell me if that helps the OOM issues and whether it causes issues when new
ingestions are added." After the answer: "what about reranker 6, and embedder 4.5", then "go ahead".

Findings before the change (read-only):
- The "local Qwen" is `local_extractor` (:8755), `mlx-community/Qwen3.5-4B-MLX-4bit`, an EXTRACTION model. It is not
  in the chat synthesizer catalog (0 of 23 entries). It held 2.76 GB (physical footprint) while idle and 11.5 GB of the
  29 GB budget, 43% of the committed 26.65 GB.
- The OOMs are the reranker's own cap, not host pressure (62% free). `sidecar_reranker.log` has 184 events since 09-20,
  all "rerank batch OOM at ~33 pairs; retrying at 32 → 16". The embedder log has 0.
- Ingestion does not use it. `CLOUD_MIN_BYTES = 0` (CLOUD-FIRST-V1, 2026-09-02: the 4B lane quarantined 76–89% of
  small books against 0–5% on cloud), not raised in `.env` or any worker env. Every extraction artifact on record
  (81, 09-05 → 09-21) has `lane_decision.lane = cloud`, spread over ~14 endpoints. The 4B server logged 0
  `/v1` requests since the last boot, only readiness probes.

## Changes
- `control/control/process_supervisor.py`: the `local_extractor` FLEET entry is removed. It stays as a commented rollback
  line. The running supervisor has no profile / `POLYMATH_FLEET_ONLY` / autopilot, so FLEET is what it starts.
- `control/control/fleet_autopilot.py`: the extract lane no longer lists `local_extractor`.
- `config/runtime_budget.yaml`: the `local_extractor` spec and its two profile entries (extraction, serve) are removed,
  with a retirement note giving the rollback values. `sidecar_reranker.mps_gb` 3.5 → 6.0. `sidecar_embedder.mps_gb`
  3.5 → 4.5 and `max_batch_texts` 4 → 8; `max_batch_tokens` stays 8192.
- `tests/determinism/test_no_legacy_sidecars.py`: new guard test. The 4B is absent from FLEET, the autopilot and every
  budget profile; the new caps are pinned; the default plan and every profile fit.
- Kept: the sidecar code, the model files on disk, the extraction model config, `llm_local_extract_url` and the
  `POLYMATH_EXTRACT_AFFINITY=local` worker. Under a 0 B floor, that worker sends every document to cloud anyway.

## Proof
- Budget (`runtime_budget.plan()` on this tree): committed 26.65 → 18.65 GB of the 28.5 GB ceiling. Profiles: serve 19.55,
  extraction 10.6, retrieval 17.45; all fit. Exported limits: embedder `PYTORCH_MPS_HIGH_WATERMARK_RATIO` 0.1803
  (4.5 GB), 8 texts / 8192 tokens; reranker 0.2404 (6 GB).
- Tests: `test_no_legacy_sidecars`, `test_mps_budget_fidelity`, `test_fleet_autopilot_demand`, `test_cp21_supervisor`,
  `test_supervisor_env_overlay`, `test_supervisor_readiness`, `test_client_resilience`, `test_enrich_budget_v2` and
  `test_json_mask` all pass (68 tests, offline).
- Deployed proof (after the bounce) is in the register row: port 8755 closed, the new caps in the sidecar env, and the
  reranker log checked for OOMs.

## Rejected claims
- "Removing the 4B fixes the OOMs": it does not by itself. The fix is the reranker's larger cap; the retirement frees the
  budget for it and returns ~2.76 GB of real memory.
- "6 GB holds every judged set in one pass": that is an estimate (~70 MB per 384-token pair, from the 33-pair failure at
  3.5 GB). The halving retry stays as the safety net; if OOM lines persist on large turns, the next step is 7 GB.
- "Nothing is lost": local extraction when every cloud lane is down. That fallback was already off in practice
  (a 0 B floor), and re-enabling it now needs the rollback plus a raised `POLYMATH_CLOUD_MIN_BYTES`.

## Open contract gaps
- Runtime budget (`config/runtime_budget.yaml`): UPDATED.
- Supervisor FLEET / autopilot lanes: UPDATED (the 4B slot is removed).
- Extraction lane policy (CLOUD-FIRST-V1): TESTED_UNCHANGED (all 81 recorded decisions were cloud).
- Chat synthesizer catalog: NOT_AFFECTED (the 4B was never in it).
