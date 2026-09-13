---
title: "WORK LOG — /retrieve HYBRID reader migration onto the final core (POLYMATH_RETRIEVE_ENGINE, default v2, v1 rollback)"
change_id: RETRIEVE-ENGINE-MIGRATION-V1
date: 2026-09-10
owner: governance
last_reviewed: 2026-09-10
status: complete (reader migration; U-2-independent; v1 rollback flag; no legacy state touched)
register: 11.191
package: "orchestrator/orchestrator/api/retrieve.py + tests/determinism/test_retrieve_engine_migration.py + docs/wiki/experiments/retrieve-engine-migration-2026-09-10/"
architecture_impact: "MIGRATE LEGACY READER (not DELETE STATE). /retrieve single-corpus HYBRID now rides the final chat_retrieve_mode core by default, behind POLYMATH_RETRIEVE_ENGINE (v1 rollback). Response contract byte-shape-identical (parity-proven). No summary/enrichment state touched; FAST/GRAPH/WILDCARD/legacy paths unchanged. Advances the steady-state 'one retrieval core, many surfaces'. Independent of U-2 (final core runs coverage-free)."
---

> **Ledger:** owner /goal 2026-09-10 (MIGRATE READER ≠ DELETE STATE). Cutover authority
> `PRODUCTION-RAG-MIGRATION-CUTOVER-V1.md` §10. Register **11.191**. No legacy state deleted, no producer
> stopped, no provider spend.

## Contract

Requested outcome: migrate the runtime-reachable legacy retrieval surfaces onto the already-qualified final core
where provably safe and independent of cinema coverage/U-2, preserving each public contract.

- **Smallest acceptance:** `/retrieve` HYBRID returns the final core's evidence with the SAME public response
  shape, works on legacy (non-vNext) corpora without error, and is reversible via a flag.
- **Owner / public contract:** `/retrieve` (and MCP `retrieve`, whose default mode is HYBRID) — response shape
  unchanged.
- **Inputs/outputs/persistence:** reads the final core (local sidecars); no state written; a flag selects engine.
- **Dependency edges:** `orchestrator/api/retrieve.py` → `orchestrator/api/chat_retrieval.chat_retrieve_mode`
  (local import, no cycle). Reverse dependents: MCP `retrieve`, evidence rows consumers.
- **Verifier / rollback:** `tests/determinism/test_retrieve_engine_migration.py`; rollback
  `POLYMATH_RETRIEVE_ENGINE=v1` (zero code change).

## Changes

- `orchestrator/orchestrator/api/retrieve.py` — `retrieve_engine_flag()` (`POLYMATH_RETRIEVE_ENGINE`, default
  `v2`, values v1|v2) + MODE_HYBRID single-corpus routes to `chat_retrieve_mode("HYBRID")` when `v2` and not
  `utility`; `latent` maps to the final latent lane via the budget; v1 (`hybrid_fast_retrieve`) is the rollback.
  FAST (multi-corpus), GRAPH, WILDCARD, and the default/LEGACY (`retrieval_summaries`) path are UNCHANGED.
- `tests/determinism/test_retrieve_engine_migration.py` — flag-contract guard (5 cases, provider-free).
- `docs/wiki/experiments/retrieve-engine-migration-2026-09-10/` — parity evidence (README + `parity-result.json`).
- `docs/wiki/plans/PRODUCTION-RAG-MIGRATION-CUTOVER-V1.md` §10 — HYBRID marked MIGRATED; GRAPH/WILDCARD corrected
  to PENDING PARITY (v1 GRAPH returns a different nested shape).
- `docs/wiki/plans/PLAN-AUTHORITY-REGISTER.md` — register **11.191**; scaffold `TREE` declarations.

## Proof

- **Parity A/B (read-only, local, no spend):** v1 `hybrid_fast_retrieve` vs final `chat_retrieve_mode("HYBRID")`
  on `rag-canary` (covered), `ecom-meta-v1` (legacy, query_ready+enabled), `cinema` (legacy, partial). Identical
  public-contract keys (`evidence/meta/query/selected_documents/selected_sections/trace`) on both engines across
  ALL three; v2 non-empty, no error → shape-safe + **coverage-independent**. v2 returns 15 rows vs v1's 10
  (richer default, not a regression). `migration_safe=True`. Evidence: `parity-result.json`.
- Contract guard: **5 passed** (default v2, v1 rollback, junk→v2, env override, final entrypoint importable).
- Import check: `retrieve.py` + `chat_retrieval.py` import cleanly (local import avoids the existing
  chat_retrieval→retrieve cycle).
- Guards: `agent_preflight` ok · `repo_guard` ok · `wiki_worm --check` ok.
- Open runs = 0 at edit time (fence-safe). The running orchestrator serves the change only after its next
  restart; the code default is `v2`.

## Rejected claims

- **"GRAPH and WILDCARD can migrate now too."** REJECTED (this slice) — v1 `graph_retrieve` returns a NESTED
  documents/sections shape (evidence.py:80-92) unlike the final flat shape; WILDCARD unproven. They stay on v1
  pending their own parity proof.
- **"Reader migration must wait for U-2."** REJECTED — the final core runs coverage-free (base lanes standard,
  additive flag-off), proven on legacy corpora.
- **"This deletes legacy state."** REJECTED — no summary/enrichment table or producer is touched; `retrieval_summaries`
  and the legacy path are intact (DELETE STATE remains U-2/cutover-gated).

## Open contract gaps

- `/retrieve` GRAPH / WILDCARD migration: needs a shape-parity proof (or an adapter) — v1 GRAPH's nested output
  differs from the final flat shape.
- `evidence.py` HYBRID (single) is the same shape-safe pattern (consumes flat `fast["evidence"]`) — deferred to a
  follow-up; GRAPH/FAST there stay v1.
- `/ask` = distinct composite → migrate later.
- The default-flip takes effect on the next orchestrator restart; a live post-restart `/retrieve` spot-check
  should confirm parity in production before the v1 path is retired (DELETE STATE, U-2-gated).
