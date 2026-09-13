---
title: "WORK LOG — /evidence GRAPH + HYBRID reader migration onto the final core (closes the RETIRE_CANDIDATE from RETRIEVE-GRAPH-WILDCARD-MIGRATION-V1)"
change_id: EVIDENCE-ENGINE-MIGRATION-V1
date: 2026-09-12
owner: king
last_reviewed: 2026-09-12
status: complete
register: 11.217
architecture_impact: "MIGRATE LEGACY READER. orchestrator/api/evidence.py's GRAPH and HYBRID branches now source their assemble_evidence_bundle inputs from the final chat_retrieve_mode core by default (same POLYMATH_RETRIEVE_ENGINE flag as /retrieve), rebuilding the same graph_facts/child_evidence/document_summaries/section_summaries shape from the engine's flat output instead of walking v1 GRAPH's nested shape. FAST stays v1 (multi-corpus, structural). No change to assemble_evidence_bundle itself, no schema change, graph_retrieve/hybrid_fast_retrieve untouched and fully reachable via rollback."
---

> Executor session, continuation of RETRIEVE-GRAPH-WILDCARD-MIGRATION-V1 (11.213),
> whose own work-log named `orchestrator/api/evidence.py` as "the one genuine
> RETIRE_CANDIDATE found... deferred because it walks v1's nested shape as an
> input-extraction pattern, not a pass-through." This closes that deferral.

## Contract

Requested outcome: `/evidence` GRAPH and HYBRID modes source their evidence-bundle
inputs from the final retrieval core by default, with the identical rollback
mechanism `/retrieve` already uses, and zero change to `assemble_evidence_bundle`'s
own contract or output shape.

- **Smallest acceptance:** `POST /evidence` with `mode=GRAPH` or `mode=HYBRID` returns
  the same `{query, evidence_bundle, meta}` contract, populated from real resolved
  facts/entities/documents/chunks, on both the default (v2) and rollback (v1) engine.
- **Owner / public contract:** `POST /evidence` — response shape (`evidence_bundle`
  item shape, `meta.mode`) unchanged.
- **Inputs/outputs/persistence:** reads the final core or the v1 engines (flag-gated,
  identical to `/retrieve`); no state written.
- **Dependency edges:** `orchestrator/api/evidence.py` gains the same
  `chat_retrieve_mode` edge `/retrieve` already has (11.191/11.213), plus a new shared
  helper `_section_summaries_from_parent_ids` used by both its HYBRID and (v2) GRAPH
  branches — extracted from the HYBRID branch's own pre-existing inline query, not new
  logic.
- **Verifier / rollback:** `tests/determinism/test_evidence_engine_routing.py` (5
  cases) + live HTTP verification (below). Rollback: `POLYMATH_RETRIEVE_ENGINE=v1`,
  identical to every other reader this pattern has migrated.

## Changes

- `orchestrator/orchestrator/api/evidence.py`:
  - New module-level `_section_summaries_from_parent_ids(parent_ids)` — the section
    (parent-chunk) TEXT-summary presentation join, extracted verbatim from the
    pre-existing HYBRID/FAST branch's inline query so the new GRAPH-v2 branch can
    reuse it instead of duplicating the SQL.
  - GRAPH branch: gated on `retrieve_engine_flag()` (imported from `.retrieve`,
    matching `/retrieve`'s own gate exactly — no separate flag invented). Default
    (`v2`) calls `chat_retrieve_mode("GRAPH", query, cid, **_kw)` (same `latent`→
    `budget.latent_enabled` forwarding pattern as `/retrieve`) and rebuilds
    `graph_facts`/`child_evidence`/`document_summaries`/`section_summaries` from its
    FLAT `evidence`/`selected_documents`/`selected_sections`/`graph_relationships` —
    `child_evidence` now includes `parent_id` (missing from the old v1-derived version;
    `assemble_evidence_bundle`'s own docstring documents `child_evidence rows:
    {chunk_id, doc_id, parent_id, ...}` as the full contract, so this is a strict
    completeness improvement, not a new field being invented). `v1` rollback keeps the
    exact original `graph_retrieve` + nested-walk code, byte-for-byte unchanged.
  - HYBRID branch (within `mode in (MODE_FAST, MODE_HYBRID)`): FAST is completely
    unchanged (always v1, multi-corpus). HYBRID gains the identical `retrieve_engine_
    flag()` gate; both its v1 (`hybrid_fast_retrieve`) and v2 (`chat_retrieve_mode`)
    outputs are ALREADY the same flat shape (parity-proven by 11.191), so the
    downstream extraction code is now shared/unconditional — only which function
    produced `fast` differs.
- `tests/determinism/test_evidence_engine_routing.py` — new file, 5 cases (provider-
  free, monkeypatched `tx`/`resolve_http_scope`/`chat_retrieve_mode`/`graph_retrieve`/
  `hybrid_fast_retrieve`/`fast_retrieve`/`assemble_evidence_bundle`): GRAPH default-v2
  extracts from the flat shape, GRAPH v1-rollback extracts from the nested shape
  (both asserted against the EXACT `graph_facts`/`child_evidence`/`document_summaries`
  values passed to `assemble_evidence_bundle`, not just "didn't crash"), HYBRID
  default-v2 and v1-rollback, FAST unaffected.
- `scripts/scaffold_polymath_v4.py` — TREE declarations.

## Proof

- **Live HTTP smoke test** (`rag-canary`, default v2 engine, real fleet): `POST
  /evidence mode=GRAPH` → `200`, `meta.mode: GRAPH`, `evidence_bundle` 31 real,
  resolved entries (inspected several: real `claim_candidate` text, resolved
  `fact_id`/`entity_ids.subject_id`/`object_id` — e.g. `"canary labs unit 59622
  ACTS_ON kiln firing program"`, fully resolved, not placeholder data). `POST
  /evidence mode=HYBRID` → `200`, `meta.mode: HYBRID`, `evidence_bundle` 24 entries.
  Both prove the migrated extraction code produces a genuinely correct, fully-resolved
  bundle end-to-end, not just a non-crashing response.
- **Contract guard: 5 passed** (`test_evidence_engine_routing.py`), asserting exact
  `graph_facts`/`child_evidence`/`document_summaries` values reaching
  `assemble_evidence_bundle` for both engines and both modes — not just "no exception."
- Import/syntax check: `evidence.py` compiles; the new `retrieve_engine_flag` import
  reuses the exact symbol `/retrieve` already exports (no new flag/config invented).
- Guards: `agent_preflight` ok · `repo_guard` ok · `wiki_worm --check` ok.
- Fence: `orchestrator/orchestrator/api/*` sits outside the HASH-FENCE-V2 fingerprinted
  dirs (`shared/polymath_shared`, `workers/workers`, `control/control`) — no fleet
  bounce required; a surgical orchestrator-only restart (the pattern established
  earlier this session for `main.py`) makes it live.

## Rejected claims

- **"child_evidence's new parent_id field changes the bundle's output contract."**
  REJECTED — `assemble_evidence_bundle`'s own docstring already documents
  `child_evidence rows: {chunk_id, doc_id, parent_id, text, contract_ids}` as the
  intended input shape; the old v1-GRAPH-derived `child_evidence` (missing
  `parent_id`) was already short of that documented contract. Adding it completes an
  existing gap, it does not add a new field the function doesn't already expect.
- **"HYBRID's extraction code needs its own v1/v2 branch too, mirroring GRAPH's."**
  REJECTED — unnecessary: v1 `hybrid_fast_retrieve` and v2 `chat_retrieve_mode
  ("HYBRID")` already return the identical flat shape (11.191's own parity proof), so
  branching the extraction code would be duplicated logic with no behavioral
  difference — only the engine-selection `if` needs to exist, which it does.
- **"FAST should get the same engine-flag treatment for consistency."** REJECTED — FAST
  is structurally multi-corpus; the final core is single-corpus by design
  (`corpus_required`), identical reasoning to `/retrieve`'s own FAST handling
  (11.213). Nothing changed for FAST here, deliberately.

## Open contract gaps

- None specific to this slice. The broader `/retrieve` FAST / `/ask` / MCP
  classification from 11.213 is unchanged and still accurate — `/evidence` was the
  one item that classification named as still open, and it is now closed.
