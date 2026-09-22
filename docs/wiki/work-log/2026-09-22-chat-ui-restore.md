---
change_id: CHAT-UI-RESTORE
owner: "@king"
date: 2026-09-22
status: complete
architecture_impact: "frontend-v2 presentation only (plus the dev-proxy list). No backend, contract or engine change in this slice."
last_reviewed: 2026-09-22
---

# Chat UI restore — the ELITE chat surface, recovered from the 2026-09-18 stash and committed

## Contract
Owner report 2026-09-22: "the old v2 streamed the reasoning and showed the steps and showed collapsable features, it also had fonts and tables
design for the output. this one shows raw asterisks … the default model is showing backend instead of provider … a frontend dropdown for intent
classifier, no fast retrieval selector". Root cause: the rich surface (`AnswerBody`, `ProcessRail`, streaming `chat.ts`, its CSS) was never
committed — it sat in `stash@{0}` ("PRE-LIBRARIAN-DEPLOY 2026-09-18: frontend-v2/ELITE stream …"). `frontend-v2/dist` is git-ignored, so the served
UI kept it only until the next rebuild from committed code (the GNN deploy rebuild of 2026-09-22 dropped it). Restore it without redesign, on top
of Codex's RAG-UI-INTEGRATION slice (`9823bbc`: five-mode selector, session-before-mount, `require_retrieval`).

## Changes
- `frontend-v2/src/components/ProcessRail.tsx` (from the stash, verbatim) — "Working · N steps" with a spinner on the active step, per-step detail (chunks, queries, items, model), the model's reasoning streaming in its own pane; collapses to "Worked for Ns · N steps" when the turn ends (click to reopen).
- `frontend-v2/src/components/AnswerBody.tsx` (from the stash; one change) — the answer through `react-markdown` + `remark-gfm` (headings, bold, lists, code, GFM tables — both packages were already dependencies), then a badge row: mode · intent (read-only) · verdict · model · ⛁ chunks (opens the evidence list) · latency. Change vs the stash: Query trace and Review stay visible as collapsed rows instead of hiding inside the evidence drawer (Codex's session test asserts the trace is reachable; it also keeps the receipt one click away).
- `frontend-v2/src/lib/chat.ts`, `frontend-v2/src/styles/app.css` (from the stash, verbatim — both unchanged on production since the stash base `557389d`) — `token` frames stream into the answer, `reasoning` frames into the rail, phases keep stage + label + raw data; answer provenance (model, verdict, abstained, uncovered terms); the `.md`, rail, badge and drawer styles.
- `frontend-v2/src/screens/Chat.tsx` — `TurnView` = ProcessRail + AnswerBody; the disabled one-option "Intent" dropdown removed (no override contract exists; intent is shown per answer as a read-only badge).
- `frontend-v2/src/components/ModelPicker.tsx` — with nothing picked, shows the catalog row the backend will use (`default: true`, the same rule as `_default_synthesizer`): provider label + model + "· default", instead of "backend default".
- `frontend-v2/src/lib/chatStore.ts` + `frontend-v2/src/App.tsx` — blank sessions are not persisted; "+ New chat" reuses an open blank (fixes the empty-session buildup in Codex's session-before-mount fix).
- `frontend-v2/vite.config.ts` — `/adapter` added to the dev-proxy list (the pre-existing `proxy-covers-backend` failure, identical on production).
- `frontend-v2/src/__tests__/chat-surface.test.tsx` — 6 tests pinning each reported defect.

## Proof
Frontend: vitest 12 / 12 (chat-surface 6, Codex's chat-session 3, retrieval-modes 2, proxy-covers-backend 1 — now passing), `tsc` clean, `vite build` ok
(bundle 289 KB → 451 KB: the markdown renderer is now actually used). Live, on a preview orchestrator started from this worktree (:7201, real cinema
stores, one real synthesizer call): selector FAST / HYBRID / GRAPH / WILDCARD / GNN, no Intent control, model "Alibaba Model Studio ·
deepseek-v4-flash-0731 · default"; a FAST turn streamed the rail (8 steps with detail) and the model's reasoning live, rendered headings / bold /
lists as Markdown with no raw asterisks, the badge row `FAST · ⌖ synthesis · GENERATED · deepseek-v4-flash-0731 · ⛁ 21 chunks · 85.5s`,
collapsed to "Worked for 86s · 8 steps", and the Query trace read "Executed mode: VECTOR (FAST)" with no drift warning. The sidebar title updated
mid-stream without losing the stream (the remount trap is gone).

## Rejected claims
- "Codex's change broke the UI" — refused: the rich surface was never committed; any rebuild from committed code drops it.
- "The Enter key does not submit" — refused: the browser automation's "Return" key name is not "Enter"; "Enter" submits.

## Open contract gaps
- Chat SSE frame contract (phase / reasoning / token / answer / done): TESTED_UNCHANGED — consumed as emitted.
- `/synthesizers` catalog (`default` flag): TESTED_UNCHANGED — read, not changed.
- Backend: NOT_AFFECTED by this slice (Codex's slice carries the `require_retrieval` / Compare changes and their dispositions).
- `stash@{0}` still holds `Polymath_librarian_architecture_checklist.md` and a `scripts/verify_final_state.py` change — not part of this slice; left in the stash.
