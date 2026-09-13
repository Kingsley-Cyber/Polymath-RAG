---
title: "WORK LOG — Frontend V2 F2/F3 Chat + streaming, with the F5 lane inspector core"
change_id: FRONTEND-V2-PLAN
date: 2026-09-10
owner: governance
last_reviewed: 2026-09-10
status: complete (F2, F3, and the lane-state core of F5; browser-verified on a real turn)
register: 11.201
package: "frontend-v2/src/{screens/Chat.tsx, lib/chat.ts, components/LaneTable.tsx}"
architecture_impact: "frontend only. No backend contract changed; no retrieval, ranking or readiness policy reimplemented."
---

> **Ledger:** owner directive 2026-09-10 workstream B — continue F1 → F2 → F3 →. Register **11.201**.

## Contract

Requested outcome: Chat with corpus · Hybrid/Graph/Wildcard · intent · model · reasoning · streaming, and a
Query Inspector that shows backend truth with the five lane states distinguished.

- **Smallest acceptance:** a real question on `rag-canary` streams phases, renders a grounded answer, and the
  inspector distinguishes FIRED from SURVIVED RERANK from USED IN ANSWER.
- **Owner / public contract:** none changed.
- **Dependency edges:** `lib/chat.ts` → `lib/api.chatStream` → `POST /chat/stream`.
- **Verifier / rollback:** `npm run build` + a live browser turn; rollback = revert.

## Changes

- `src/lib/chat.ts` — turn state machine over the SSE frames (`phase*` → `answer` → `done`), with cancel.
- `src/screens/Chat.tsx` — controls and transcript. **VECTOR is not offered** (plan §2). Intent is a disabled
  "Auto (classified)" control with a tooltip stating there is no override contract — a real limitation shown as
  a limitation, not a fake selector.
- `src/components/LaneTable.tsx` — the five lane states.
- `src/App.tsx` — Chat wired into the shell.

## Proof

- `npm run build` (tsc strict + vite) **green**, 40 modules.
- **Live turn, browser-verified** on `rag-canary` ("what is the ZQX fact", HYBRID, backend-default model):
  phases streamed visibly in order — `scope › scope_ok › compile › retrieve › retrieve_done › assemble ›
  assemble_done › generate …` — then a grounded answer with `[S1]…[S11]` citations, badges
  `HYBRID · ⌖ EXACT · chat-retrieval-v2`, 29.3 s.
- **The inspector earns its place immediately.** Same turn:

  | lane | fired | entered union | survived rerank | used in answer |
  |---|---|---|---|---|
  | `global_dense_child` | 50 | 50 | 15 | 15 |
  | `hierarchical` | 24 | 24 | 13 | 13 |
  | `global_sparse_child` | 40 | 40 | 12 | 12 |
  | **`section_summary`** | **24** | — | **0** | **0** |
  | **`entity_card`** | **8** | — | **0** | **0** |

  Funnel: retrieved 51 · union 51 · pre_rerank 32 · post_rerank 32 · selected 15 · cited 13 · graph_facts 0.
  **32 candidates fired from two lanes and reached the answer in zero rows** — the plan's "a lane that FIRED
  did not thereby affect the answer" rendered rather than inferred.
- The derivation is documented, not guessed: FIRED = `lane_sizes`, ENTERED UNION = `funnel.lane_counts`,
  SURVIVED RERANK = `final_detail[].arrivals`, USED IN ANSWER = `legend[].tag` ∩ arrivals. The backend names one
  lane three ways (`hierarchical_children` / `hierarchical` / `HIERARCHICAL_ROUTE`); the alias map is written
  down in `LaneTable.tsx` and an unknown name is shown under its own key rather than dropped.

## Rejected claims

- **"Offer VECTOR as a mode."** REJECTED — plan §2: a backend primitive, not a public mode.
- **"Let the user pick an intent."** REJECTED — no override contract exists. Showing a live-looking selector
  that the backend ignores would be a fake control; it is rendered disabled with the reason.
- **"`arrivals` is the union."** REJECTED after checking a real receipt — `arrivals` has exactly 15 entries
  matching `selected`, so it is the FINAL selection's provenance. Union comes from `funnel.lane_counts`.
  Getting this backwards would have made every lane look like it survived.
- **"Show 0 for lanes the funnel doesn't report."** REJECTED — those render `—` (not reported), because 0 and
  unknown are different claims.

## Open contract gaps

- Evidence Inspector (F4) not built: the receipt carries `chunks`, `legend` and `final_detail` with
  `rerank_score`, so the data is present; the screen is not.
- The transcript renders answer text as pre-wrap, not markdown.
- Enter-to-send did not fire under synthetic key events in the automated check; the Send button is the verified
  path. Worth a real keyboard test in F12.
- No frontend test yet (F11). F6/F7 remain blocked on GAP-2/GAP-3.
