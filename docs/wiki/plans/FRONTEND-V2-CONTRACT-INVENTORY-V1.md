---
title: "FRONTEND-V2 F0 — backend contract inventory (measured live, not assumed)"
change_id: FRONTEND-V2-CONTRACT-INVENTORY-V1
owner: governance
date: 2026-09-10
last_reviewed: 2026-09-10
status: living (F0 complete; F1+ consume this)
architecture_impact: "none — inventory only. No endpoint added, changed or deprecated. Names the backend gaps that F4/F6/F7/F10 must close BEFORE those screens can be honest."
register: 11.195
---

# F0 — what the backend actually serves Frontend V2

Measured against the **live** orchestrator on `127.0.0.1:7200` at 2026-09-10T20:40, fleet bundle
`f0db5412e473820e`, after the cutover bounce. Every shape below was read off a real 200 response, never
inferred from source. `/openapi.json` = **39 routes**.

> **Rule this document exists to enforce:** V2 renders backend authorities; it never recomputes them
> (the 11.187 design law). Where the backend does not serve a concept, that is a GAP row here — not a
> licence for the UI to invent the number.

## 1. The readiness triad — the core requirement

The legacy `query_ready` boolean is **not** a readiness signal and V2 must never present it as one.
Measured proof, same instant, same corpus:

| corpus | legacy `query_ready` | SEMANTIC | VNEXT | per-doc truth |
|---|---|---|---|---|
| `rag-canary` | `true` | `SEMANTIC_COMPLETE` | `VNEXT_COMPLETE` | 10/10 `vnext_ready`; parents 50 eligible / 50 mapped / 0 unresolved |
| **`cinema`** | **`true`** | **`SEMANTIC_INCOMPLETE`** | **`VNEXT_INCOMPLETE`** | **14/67 `vnext_ready` — 53 BLOCKED**; parents 11,993 eligible / 1,449 mapped / **10,176 unresolved** |

`cinema.query_ready = true` while 53 of 67 documents are unmappable. That single row is the whole
argument for the triad.

| Concept | Authority | Field | Verified |
|---|---|---|---|
| **CONTROL READY** — "is the machinery healthy?" | `GET /health/pipeline` + `GET /control_plane?corpus_id=` + `GET /fleet` + `GET /ready` | `state`, `stalls_open`, `blocked_workers`, `queued_tickets`, `medic_actions_15m`; `summary{documents,semantic_ready,processing,blocked}`; `sidecars{embedder,reranker}` | yes — **no single `control_ready` verdict exists; V2 composes it (see GAP-1)** |
| **SEMANTIC READY** — "is the corpus's meaning built?" | `GET /semantic_readiness?corpus_id=` | `verdict` ∈ {`SEMANTIC_COMPLETE`,`SEMANTIC_INCOMPLETE`}, contract `semantic-readiness-v1`, `counts{documents,document_summaries,parent_summaries,corpus_map_rows,facts_accepted,procedures,concepts}`, `extraction`, `warnings`, `artifact_lane_failures` | yes |
| **VNEXT READY** — "can this document answer from source?" | same call → `vnext{}`, and per document `GET /documents/summary?corpus_id=` | `vnext.verdict`, `vnext.parents{eligible,mapped,excluded,unresolved}`, `vnext.pending[]` (e.g. `"unresolved_eligible_parents_10176_of_11993"`); per doc `vnext_ready`, `map_eligible/active/excluded/unresolved`, `profile_present`, `profile_vnext`, `parents`, `children`, `graph_entities`, `graph_relations` | yes |
| per-document diagnostic drawer | `GET /documents/{id}/status?detail=true` | ordered blockers + graph/profile/pMAP/projection sections (CANONICAL-DOCUMENT-STATUS-V1) | yes (11.187) |

## 2. Owner capability → contract map

| # | V2 capability | Served by | Status |
|---|---|---|---|
| 1 | query Polymath normally | `POST /chat/stream` (SSE: `phase`×N → `answer` → `done`) | **SERVED** |
| 2 | select Hybrid / Graph / Wildcard | `mode` on `/chat/stream`, `/chat`, `/retrieve` (`VECTOR\|HYBRID\|GRAPH\|ASK`, + WILDCARD) | **SERVED** |
| 3 | inspect retrieval behaviour | `answer.retrieval`: `engine`, `mode`, `lane_sizes` (per-lane funnel incl. `union`), `funnel`, `composition`, `aspects`, `weak_aspects`, `degraded`, `latency_ms` | **SERVED** |
| 4 | inspect selected source evidence | `answer.retrieval`: `chunks`, `used_evidence`, `legend`, `final_detail`; `POST /evidence`; `GET /documents/{id}/sections` | **SERVED** |
| 5 | see Profile / Atom / pMAP routing | `answer.retrieval.arrivals` = per-chunk lane provenance (`HIERARCHICAL_ROUTE`, `GLOBAL_DENSE_CHILD`, `GLOBAL_SPARSE_CHILD`, `SHADOW_DUALREAD`, `SEEALSO_FANOUT`, `GRAPH_DEST`, …) + `lane_sizes.{document_summary,section_summary,entity_card,latent_rescue,dualread,resolution_lift,seealso_fanout,graph_dest}` | **SERVED** |
| 6 | inspect graph contribution | `answer.retrieval`: `graph_fact_count`, `graph_seeds`, `graph_bounds`, `graph_degraded`; `GET /control_plane/predicates` | **SERVED** |
| 7 | compare retrieval styles | — | **GAP-2** |
| 8 | review an answer with another model | — | **GAP-3** |
| 9 | real Control / Semantic / vNext readiness | §1 | **SERVED** (composition caveat GAP-1) |

Model + mode pickers: `GET /synthesizers` (14 offered, e.g. `litellm:anthropic/deepseek-v4-flash-0731`,
`litellm:anthropic/glm-5.2`), `GET /reasoning_modes` (10 modes, default `none`), `GET /capabilities`
(`endpoints`, `contracts{retrieve-evidence-rows,corpus-plan,chat-evidence,explore,document_ids}`).

## 3. Gaps V2 cannot paper over

| # | Gap | Why it matters | Owner decision needed? |
|---|---|---|---|
| **GAP-1** | No single **CONTROL READY** verdict. V2 must compose 4 calls, and composition is recomputation — the thing 11.187's design law forbids. | Two screens composing it differently will disagree. | Backend: add a `control_ready` verdict to `/control_plane` (one authority). |
| **GAP-2** | No retrieval-comparison contract. Comparing HYBRID vs GRAPH vs WILDCARD means N independent `/chat/stream` calls diffed client-side — N synthesis spends, N rerank passes, and **no shared retrieval seed**, so differences confound mode with run-to-run variance. | F6 is dishonest without it. | Backend: a compare contract that runs N modes over ONE compiled plan and returns N receipts, synthesis optional. |
| **GAP-3** | No answer-review contract. `synthesizer` lets model B *re-answer*; nothing lets model B *review* answer A against the evidence A actually cited. | F7 as specified cannot be built read-only on today's API. | Backend: a review contract (answer + evidence + reviewer model → verdict/critique), no retrieval re-run. |
| **GAP-4** | `control_plane.summary.processing` counts runs in `('intake','reconciling','degraded')` with **no age qualifier**. Live now: cinema shows `processing: 64` — those 64 runs last moved **2026-09-07**. | V2 would render 64 documents as actively processing. That is a lie on the primary health screen. | Backend: age-qualify, or split `processing` into `in_flight` vs `stalled/dormant`. |
| **GAP-5** | `/documents/summary` is corpus-scoped and unpaginated (cinema: 67 docs, 600 ms). | Fine now; F8 must not assume it stays cheap at 10× the corpus. | Watch; no action. |
| **GAP-6** | `/health/pipeline` reports `state: DEGRADED` with `stalls_open: 282` on a **completely idle** fleet (`queued_tickets: 0`, `blocked_workers: 0`, `live_workers: 13`, `medic_actions_15m: []`). The 282 decompose exactly into the dormant backlog: `PENDING_ON_PREDECESSOR×221` + `PENDING_ADVANCE_BLOCKED×32` + `RUN_SETTLED_NOT_PROMOTED×29`. Found live by F1 on 2026-09-10. | **CONTROL READY can never read green** until the dormant backlog is dispositioned, so the primary health verdict is pinned to DEGRADED by history rather than by anything happening now. Same class as GAP-4: a health counter with no age/dormancy qualifier. | Backend: exclude dormant runs from stall counting, or split `stalls_open` into `active` vs `dormant`. |

## 4. Non-negotiables for F1+

- **Greenfield.** The existing `frontend/` (ChatView, FilesView, ControlPlaneView, FleetView, CorporaView,
  MessageBubble, ModelPicker, ModelsView, PhaseStream, Sidebar, TopBar) is NOT modified except to keep it
  runnable. V2 is a separate application.
- **Reference corpus = `rag-canary`** (the only `VNEXT_COMPLETE` corpus). **`cinema` is the honesty fixture** —
  every readiness surface must render its 53 blocked documents as blocked, never green.
- `POLYMATH_CHAT_INTENT_POLICY` and `POLYMATH_CHAT_SYNTH_ROLES` are **OFF**. V2 may DISPLAY the classified
  intent (`answer.retrieval.chat_plan`) and any returned evidence roles; it must not imply they are routing.
- No screen recomputes a backend number. If a number is not served, it is a GAP row above, not UI arithmetic.

## 5. Status

**F0 COMPLETE.** F1 (shell / navigation / design system) is BLOCKED on the approved greenfield design —
no such document exists in this repository or in `~/Downloads` (searched 2026-09-10). The phase list
F0–F12 and the capability list in §2 come from the owner's 2026-09-10 directive, which is sufficient
for F0 but not for F1's visual/IA decisions.
