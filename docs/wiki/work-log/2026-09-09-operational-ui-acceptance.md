---
title: "WORK LOG — Operational UI: acceptance test against the live backend + graph-relations consistency fix (Slice 5)"
change_id: OPERATIONAL-UI-V1
date: 2026-09-09
owner: governance (acceptance) + shared (document_status relations parity)
last_reviewed: 2026-09-09
status: complete (Slice 5 — operational-UI acceptance; OPERATIONAL-UI-V1 done)
register: 11.187
package: shared/polymath_shared/document_status.py, docs/wiki/plans/CONTINUITY-REPORT.md, docs/wiki/plans/PLAN-AUTHORITY-REGISTER.md
architecture_impact: "Acceptance slice. One backend consistency FIX found by the acceptance test: the document-status DETAIL graph block omitted `relations` (the Files-summary path reads it), so the row's Graph column and the drawer disagreed for the same document. Added `relations` from the SAME extract-stats artifact — one authority, matching numbers. No other code change; no pipeline/architecture change."
---

> **Ledger:** operational-UI brief §13 (acceptance test against the real backend) + §14 (must-not list) + register **11.187**. No pipeline/architecture change.

## Contract

Prove the operational UI against the REAL backend end-to-end (not a mockup), and confirm the §14 prohibitions
hold. Any inconsistency between the two document-health authorities (Files summary vs detail drawer) is a defect.

## Changes

- **`document_status.py` (fix)**: the `detail=True` graph block exposed `entities` but not `relations`, while the
  Files-list summary (`corpus_document_summaries`) reads BOTH from the extract-stats artifact. The drawer showed
  `relations —` while the row's Graph column showed `16/5` for the same document. Added `"relations":
  st.get("relations")` to the detail graph block — same artifact, one authority, matching numbers.
- **Durability**: CONTINUITY-REPORT new checkpoint (OPERATIONAL-UI-V1 done); register 11.187 → done.

## Proof — §13 acceptance checklist (LIVE, orchestrator :7200 via the :5173 UI, corpus rag-canary + cinema)

| # | Requirement | Result |
|---|---|---|
| 1 | Files row shows File/Type/Size/Added/Parents/pMAP/Graph/Profile/Ready | PASS — all nine columns render (rag-canary) |
| 2 | A healthy doc reads healthy | PASS — 5/5 pMAP green, 16/5 graph, ✓ profile, ✓ ready |
| 3 | An under-mapped doc LOOKS unhealthy | PASS — cinema 53/67 docs render RED (`st-failed`), e.g. 1319 eligible / 0 mapped / 1316 unresolved |
| 4 | Document drawer: DOCUMENT/GRAPH/PROFILE/PMAP/PROJECTIONS/READINESS with exact counts | PASS — all six sections; e.g. entities 16 · relations 5 · facts 5 · pMAP 5/5 100% · projections all ✓ · vNext ready ✓ |
| 5 | Drawer count parity with the row (one authority) | PASS after fix — drawer `relations 5` == row Graph `16/5` |
| 6 | Control Plane summary: Documents/Semantic Ready/Processing/Blocked | PASS — 10/10/0/0 |
| 7 | Exactly the four functional pools; parent_enrichment NOT a 5th | PASS — GRAPH_EXTRACTION/DOCUMENT_PROFILE/PMAP/CHAT; parent_enrichment labelled legacy bridge |
| 8 | Pool card: queued/processing/retry/failed + healthy lanes | PASS — per pool; CHAT shown as a latency pool |
| 9 | LOCAL limiter refused DISTINCT from ACTUAL HTTP 429 | PASS — separate metrics ("limiter refused 0" / "HTTP 429 0") |
| 10 | pMAP valid-maps/request efficiency + model-qualified batch (15) not a global cap | PASS — 5.56 maps/request; lanes show `batch 15`; tooltip names target 60 |
| 11 | GRAPH_EXTRACTION predicate drill-down | PASS — ACTS_ON 16 … IS_A 1 |
| 12 | Model → account/key lanes, VIEW-ONLY | PASS — model-grouped, capacity + live AIMD limiter |
| 13 | NEVER render an API-key value | PASS — only `*_API_KEY_*` env NAMES on the page (planted-sentinel test + DOM scan) |
| 14 | Chat selectors: Query Type / Chat Model / Reasoning | PASS — RETRIEVAL modes / MODEL picker / REASONING dropdown |
| 15 | Reasoning default LOW, no auto-escalate | PASS — default `none`; no escalation path in code |
| 16 | Intent surfaced from the backend, not inferred/faked | PASS — read-only `⌖ comparison` badge from `chat_plan.intent`; no Intent control (no override contract) |

Performance (§12): `/documents/summary` rag-canary 12 ms / cinema 67 docs 620 ms; `/control_plane` 29 ms;
drill-downs on demand. No per-render corpus scan; no N+1.

Offline gate: the three suites DIRECTLY covering this change —
`test_document_status`, `test_control_plane_status`, `test_document_status_endpoint` — are **9/9 green**
(incl. the relations parity). The full `pytest tests/determinism` run has **2 PRE-EXISTING failures unrelated to
this change and unaffected by it**, both live/data-dependent (not hermetic units):
`test_fact_endpoint_eligibility::test_no_active_fact_has_a_pronoun_endpoint` fails on a `you` fact endpoint that
lives in the **cinema** corpus, created **2026-09-05** (four days before this work; forensic-hold data I must not
touch); and `test_chat_synthesis::…[brainrot_transform]` is a LIVE `/chat/stream` LLM-synthesis variance test.
Neither reads or depends on the document-status / control-plane / frontend surface this change touches. `repo_guard`
+ `wiki_worm --check` ok.

## Rejected claims

- **Not a mockup** — every number above is the live backend rendered through the shipped UI.
- **No secret exposed** (§14) — the ONLY key-shaped strings anywhere are env NAMES.
- **No frontend status math** (§11, §14) — the readiness/intent/limiter numbers are backend values; the drawer
  and the row now read the SAME relation count from the SAME artifact.
- **pMAP 15 is not treated as a global limit** (§14) — it is the per-lane qualified batch; the architectural
  target 60 is named in the efficiency tooltip.

## Open contract gaps

- `cross_lane_recoveries` (§4) still has no backend counter; surfaced when the control plane exposes it.
- Owner-gated remainders (unchanged by this UI work): production pMAP enable (spend), the Groq forensic-hold
  probe + cinema reconciliation, the Phase B doc_profile DAG cutover.
