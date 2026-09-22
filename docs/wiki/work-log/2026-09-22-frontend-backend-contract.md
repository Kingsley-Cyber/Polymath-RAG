---
change_id: FRONTEND-BACKEND-CONTRACT-V1
owner: "@king"
date: 2026-09-22
status: complete
architecture_impact: "A live, source-derived contract check between frontend-v2 and the orchestrator, plus the three mismatches it found: /retrieve GNN fell through to the legacy lane path (fixed in retrieve.py), the control-plane CHAT pool omitted two lane counters (fixed in control_plane_status.py), and the CompareArm type mis-declared two unread fields (fixed in contracts.ts)."
last_reviewed: 2026-09-22
---

# Frontend ↔ backend contract — made checkable, checked live, three gaps closed

## Contract
Owner, 2026-09-22: "ensure the frontend backend contract is real and live and works." Real = every call the UI makes is a route the
backend serves, every field it sends is one the backend reads, every field it reads is one the backend sends with that type; live =
checked against the running orchestrator through the UI's own client code; works = the five chat modes, Compare, Review and the model
test answer end to end.

## Changes
- `frontend-v2/src/__tests__/live-contract.test.ts` (new) — reads the contract from the UI's own sources with the TypeScript compiler
  (every call in `lib/api.ts` with its method, path, query params, body fields and response type; the body `Chat.tsx` builds; every
  interface in `lib/contracts.ts`) and checks it against the live backend through the real client (`api.*`, `runTurn`). FREE tier
  (read-only; skips when no backend answers): routes + methods exist in the live OpenAPI; every sent body field / query param is declared
  (an undeclared one would be silently dropped); every read-only endpoint's live JSON conforms to its TypeScript type; `/compare` runs
  all five modes, each arm its own, GNN lane only on GNN; `/retrieve` GNN reaches the GNN route. PAID tier (`POLYMATH_LIVE_CHAT=1`):
  the Chat screen's exact request for FAST / HYBRID / GRAPH / WILDCARD / GNN through `runTurn` (steps, answer, model, receipt conforms
  to `RetrievalReceipt`, executed mode, evidence > 0 for a small-talk-phrased question = `require_retrieval` honoured, Evidence-panel rows
  resolve via `chunkIdOf`), Review on a real answer, the Models screen's model test.
- `orchestrator/orchestrator/api/retrieve.py` — a GNN branch: `/retrieve` `mode: "GNN"` → `chat_retrieve_mode("GNN")`; v1 / utility →
  422 `gnn_requires_v2`. Before: GNN passed `validate_mode` (it joined `EXPOSED_MODES` in GNN-RETRIEVAL-V1) and fell through to the
  legacy lane path — legacy output answering a GNN request. `tests/determinism/test_retrieve_gnn_routing.py` (new, 4) fails on the old
  code with "the legacy lane path must never run for a GNN request".
- `shared/polymath_shared/control_plane_status.py` — the CHAT pool is built by the same `pool()` helper as every pool, so its `lanes`
  carries `credential_absent` / `disabled` like the others (it was hand-built with three of the five counters).
- `frontend-v2/src/lib/contracts.ts` — `CompareArm.retrieval.funnel_lanes` is lane → chunk ids and `latency_ms` is the per-stage timing
  map (the backend's intentional shape); the type had declared counts / a number. No screen reads either field, so nothing rendered wrong.

## Proof
Before the fix, the live check against production `b3c4bc1` on :7200 FAILED exactly these three (and nothing else): `api.controlPlane
.pools.CHAT.lanes.credential_absent` / `.disabled` missing; `api.compare.arms[*].retrieval.funnel_lanes` / `.latency_ms` type mismatch;
`api.retrieve` (GNN) returned the legacy shape (no `meta` / `evidence` / `trace`). Static checks passed: all 27 client calls are real
routes; every sent field and query parameter is declared. After the fix, on a preview orchestrator started from this worktree (:7201):
free tier 5 / 5. Backend: 58 related tests passed (imports resolve in this worktree); frontend: tsc clean, offline suite 12 / 12.
Deployed-state proof (both tiers on :7200 after merge + bounce) is recorded in the register row.

## Rejected claims
- "The UI showed wrong values" — refused: no screen reads the mis-typed fields; the types were wrong for the NEXT screen that would.
- "Mutating endpoints were exercised" — refused: upload, delete corpus / document, enrich, save / delete provider are checked
  statically only (route + method + every sent field declared); running them would change the corpus or the configuration.

## Open contract gaps
- `/retrieve` (RETRIEVAL_RECEIPT consumers, MCP): UPDATED — GNN now a real branch.
- Control-plane status (`control-plane-status-v1`): UPDATED additively — two counters added to CHAT.
- CompareArm type: UPDATED to mirror the backend; the `/compare` response is unchanged.
- The chat SSE frames (phase / reasoning / token / answer / error / done): TESTED_UNCHANGED — emitted and handled 1 : 1.
