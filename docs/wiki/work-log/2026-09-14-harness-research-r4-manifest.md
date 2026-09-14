---
title: "WORK LOG — HARNESS-RESEARCH-MIGRATION-V1 R4: trail.product_discovery 2.0.0 on the harness-executed loop; the Trail-owned acquisition path removed; bounded Trail operations; dead-code guard"
change_id: HARNESS-RESEARCH-MIGRATION-V1-R4
date: 2026-09-14
owner: king
last_reviewed: 2026-09-14
status: complete
register: 11.268
architecture_impact: "The reference adapter is re-shaped to the owner loop (28 steps: θ hypotheses → Trail priors → φ filter → mechanisms → gaps → AGENT_RESEARCH → admission → re-reason → judge → bounded loop through reasoning → physical jobs → territory → PRODUCT_REALITY_CHECK → market delta → SUPPLIER_RESEARCH → supply → score → interpret → compile). `trail_client` speaks only Trail's seven bounded synchronous operations (+ generic operation.get/command); the worker's discover/scrape/extract executors, the acquisition builders, paging and the `trail_record` evidence kind are removed; migration 0063 records output acceptance order (JSONB drops dict order). No new process, route, tool or slot; the fleet needs ONE bounce at merge (worker changed)."
---

## Contract
Plan §2, §6 (Polymath side), §7 rows P3/P4/P5/P7/P8/P9/P15/P16/P17, §9 tests C(Polymath side), H, J. Cutover of the manifest and the
connector: the product-discovery adapter no longer requires any Trail-owned live-web acquisition; every Trail call is a bounded
synchronous deterministic operation whose immutable result becomes step output + a TERMINAL receipt; HARNESS_ACTION steps hand
research to the host harness. Until Trail HR3 is WORKING every Trail step is `availability: planned` (node HR3) and a live run ends
honestly at `D_project` with `TRAIL_CAPABILITY_PLANNED` — proven by test.

## Changes
- `config/adapters/trail.product_discovery.json` → 2.0.0 (adapter/workflow/output-schema 2.0.0; `evidence_roles` declared; budgets incl.
  `max_harness_actions` 6, `max_hypotheses` 8; `contracts/adapter/v1/adapter_manifest.example.json` = the same manifest; examples aligned).
- `shared/polymath_shared/adapter/trail_client.py`: `BOUNDED_OPERATIONS`, `POLYMATH_CAPABILITIES` (JWT claims), `bounded_request`,
  `bounded_receipt`, `TrailMCPClient.operate`; removed `discovery_request/crawl_request/batch_request/extraction_request/page_request/page_all/outputs_of/submit/page`.
- `workers/workers/adapter_step_worker.py`: `exec_external` = one bounded operation (payload assembled from generic engine state; result →
  registry snapshot + `trail_prior` refs / directives / admission projections / φ verdicts / qualifications / score record); `query_from: hypotheses`;
  removed `_exec_discover`, `_exec_acquire_extract`, `_hypothesis_queries`, `_leads_from_prior`, `_poll_receipt` and the acquisition gap codes.
- `stores/postgres/migrations/0063_adapter_output_order.sql` + `RunState.output_order` (transitions/store/service/worker use acceptance order).
- `contracts/adapter/v1/adapter_step.schema.json`: `trail_record` retired from the evidence kinds; `CITABLE_EVIDENCE_KINDS` likewise.
- Tests: `tests/determinism/test_adapter_product_discovery_loop.py` (stub daemon for the seven ops; the full 2.0.0 loop on Postgres with two harness
  identities, 4 harness actions, 14 bounded ops, hypotheses weakened/revised/strengthened with lineage; the ACTIVE config's honest planned gap),
  `tests/determinism/test_trail_client.py` (rewritten), `tests/contracts/test_retired_paths.py` (J + H), pure walk rewritten for 2.0.0;
  `tests/determinism/test_adapter_trail_connector.py` deleted (its stub-acquisition subject is retired).

## Proof
- 78 adapter tests green (`PYTHONPATH=shared:workers:orchestrator:control .venv/bin/python -m pytest -q` over the 11 adapter suites).
- §12 dead-reference audit: zero hits for the retired symbols outside append-only history (guarded by `test_retired_paths.py`).
- Migration 0063 applied twice to the store (replay-safe).
- Found and fixed while proving the loop: (1) `accept_submission` refused a different payload for a step id re-entered through a bounded loop
  (removed — a re-issued step is a new issuance); (2) "newest step output" was derived from dict order that Postgres JSONB does not keep, so the
  second admission bound to the wrong harness action (fixed by `output_order`).

## Rejected claims
- That a live `awaiting_harness` restart test can run now: the production manifest ends at the first planned Trail operation until HR3; the
  Postgres-level pause/claim proof (R2) stands; the live extension is R5.
- That Trail's generic discover/crawl/scrape/extract are deleted: they remain Trail platform tools; only the adapter's dependency on them is gone.

## Open contract gaps
- Trail HR3 must honour the bounded-operation wire pinned by the stub (`request` envelope with `operation_kind`, `run_ref`, `registry_snapshot_id`,
  `payload`; response `operation_id`, `operation_kind`, `status_revision`, `registry_snapshot`, `result`).
- R5: live acceptance with a real harness; `research/` + `research_*` removal; the live restart test for `awaiting_harness`.
