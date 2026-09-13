---
change_id: RETRIEVE-GRAPH-WILDCARD-MIGRATION-V1
date: 2026-09-12
last_reviewed: 2026-09-12
status: evidence (frozen)
architecture_impact: none (read-only shape/behavior measurement backing the /retrieve GRAPH+WILDCARD reader migration)
---

# `/retrieve` GRAPH + WILDCARD reader-migration evidence (v1 → final core)

Backs `RETRIEVE-GRAPH-WILDCARD-MIGRATION-V1` (register 11.213), the direct continuation of
`RETRIEVE-ENGINE-MIGRATION-V1` (register 11.191, HYBRID). That slice left GRAPH/WILDCARD on v1
specifically because "v1 `graph_retrieve` returns a different nested shape" and WILDCARD was
"unproven" — this evidence closes both gaps. Machine-readable results: `parity-result.json`.

## Method (read-only, local sidecars, no external spend)

For the same corpus/query set as 11.191 (`rag-canary`, `ecom-meta-v1`, `cinema`), call v1
(`graph_retrieve` / `wildcard_retrieve`) and v2 (`chat_retrieve_mode("GRAPH"|"WILDCARD", ...)`)
directly and compare top-level keys, evidence/fact/bridge counts, and error status. No HTTP layer,
no mutation.

## Result — GRAPH: shape CHANGES by design, not a parity claim

| Corpus | v1 keys | v2 keys | v1 docs | v2 evidence | graph facts (v1/v2) |
|---|---|---|---|---|---|
| `rag-canary` | documents·graph_relationships·meta·query·trace·unassigned_rescue_evidence | evidence·graph_relationships·meta·query·selected_documents·selected_sections·trace | 5 | 15 | 10 / 10 |
| `ecom-meta-v1` | (same as above) | (same as above) | 5 | 15 | 9 / 12 |
| `cinema` | (same as above) | (same as above) | 5 | 15 | 20 / 20 |

Unlike HYBRID, GRAPH's v1 shape is **genuinely nested** (`documents[].sections[].evidence`) while the
final engine is flat — no adapter reproduces the nested shape (see "Rejected: a compatibility
adapter" below). `graph_relationships` — the one lane a caller cannot get any other way — is present
on **both** engines, on every corpus, with the identical per-item shape (`fact_id, predicate,
subject_id, subject, object_id, object`). Fact-count deltas on `ecom-meta-v1` (9 vs 12) mirror the
already-accepted 11.191 finding (v2's HYBRID base returns a richer evidence set — 15 rows vs v1's
10 — which reseeds the hop-1 expansion differently); this is a downstream consequence of richer
evidence, not a defect.

## Result — WILDCARD: shape is NEAR-IDENTICAL, not merely "compatible"

| Corpus | v1 keys | v2 keys | keys only in v1 | bridges (v1/v2) |
|---|---|---|---|---|
| `rag-canary` | entity_card_lane·evidence·meta·query·selected_documents·selected_sections·trace·wildcard | evidence·meta·query·selected_documents·selected_sections·trace·wildcard | entity_card_lane | 3 / 3 |
| `ecom-meta-v1` | (same) | (same) | entity_card_lane | 3 / 3 |
| `cinema` | (same) | (same) | entity_card_lane | 3 / 3 |

v2's key set is a **strict subset** of v1's. The one field v1 carries that v2 does not,
`entity_card_lane`, has zero readers anywhere in the repository (`rg -n "entity_card_lane"` matches
only its own assignment in `orchestrator/api/fast.py`) — nothing depends on it. The `wildcard` bridge
lane — the actual product of WILDCARD mode — matches exactly (3/3) on every corpus.

**Both engines succeeded, non-empty, zero errors, on all three corpora for both modes.**
`migration_safe = True`.

## Why no nested-shape compatibility adapter (rejected)

Section 8's adapter law is permissive ("a response adapter MAY group flat evidence into
documents/sections"), not mandatory, and only worth building for a shape a real reader needs.
Direct inspection of every current `/retrieve` GRAPH/WILDCARD caller found none that needs v1's
nested shape:

- **`/chat`** (`orchestrator/api/ui.py`) already calls `chat_retrieve_mode("GRAPH"|"WILDCARD", ...)`
  directly by default (`_v2_mode`) — the flat shape is already the live production shape for chat.
- **`/compare`** (`compare_review.py:78`) already calls `chat_retrieve_mode` directly for all three
  comparable modes, and its own docstring calls that output *"the `/retrieve` contract"*.
- **Frontend V2** (`frontend-v2/src/lib/contracts.ts::RetrieveResponse`) is already typed for the
  flat shape (`evidence/meta/query/selected_documents/selected_sections/trace`) — it was written
  for the shape this migration produces, not v1's.
- **MCP `retrieve`** (`orchestrator/mcp_server.py`) reads `out.get("evidence") or out.get("hits")` —
  against today's v1 GRAPH response (no top-level `evidence` key) this silently returns nothing.
  This migration *fixes* a live MCP defect for `mode=GRAPH`, it does not risk one.
- **`eval/r2a/harness.py`** imports `graph_retrieve` directly (bypasses `/retrieve` and this
  dispatch entirely) — unaffected either way.
- **`eval/i4/verify_i4.py`**, **`eval/historical/i3_5doc/verify_i3.py`** already read
  `body.get("documents") or body.get("selected_documents") or []` — written defensively for
  either shape.
- No test in `tests/` asserts the nested shape for a `/retrieve` GRAPH/WILDCARD response body.

Building an adapter nobody reads would be exactly the kind of unrequested abstraction the
migration's own non-goals warn against. `POLYMATH_RETRIEVE_ENGINE=v1` remains the rollback if a
real nested-shape reader is ever found.

## Scope / what did NOT change

- `/retrieve` FAST (multi-corpus) and the default/LEGACY path (`retrieval_summaries`) — untouched,
  same as 11.191.
- `/ask`, MCP `retrieve`/`retrieve_evidence` — untouched call sites; MCP's shape-agnostic read means
  it now gets real evidence for `mode=GRAPH` where it silently got none before, with zero code
  change on the MCP side.
- `parent_enrichment` — still consumed by WILDCARD's latent frontier either engine
  (`latent/projection.py` → `_retrieve_wildcard`); this migration does not touch that dependency.

## Rollback

`POLYMATH_RETRIEVE_ENGINE=v1` restores `graph_retrieve`/`wildcard_retrieve` for both modes with zero
code change, identical to the HYBRID rollback. The running orchestrator serves the change only
after its next restart (the code default is `v2`).
