---
title: "WORK LOG — Operational UI: Chat intent visibility + selector audit (frontend Slice 4)"
change_id: OPERATIONAL-UI-V1
date: 2026-09-09
owner: frontend (MessageBubble) — displays the compiler-DERIVED intent, adds no control
last_reviewed: 2026-09-09
status: complete (Slice 4 of the operational-UI frontend; acceptance gate + durability follow)
register: 11.187
package: frontend/src/components/MessageBubble.tsx, frontend/src/types.ts, frontend/src/app.css, frontend/dist/*, scripts/scaffold_polymath_v4.py
architecture_impact: "Frontend-only, minimal (§9). The Chat screen already carries the three SETTABLE selectors — Query Type (retrieval mode VECTOR/HYBRID/GRAPH/WILDCARD), Chat Model (synthesizer picker), Reasoning (mode dropdown, default 'none'). Intent is compiler-DERIVED and has NO request-override contract, so no Intent *selector* is added (that would be a non-functional control, §14); instead the derived intent is surfaced READ-ONLY as a badge on the answer, from the existing chat_plan receipt. No pipeline/architecture change."
---

> **Ledger:** operational-UI brief §9 (Chat — minimal selectors; reasoning default LOW, no auto-escalate) + register **11.187**. Minimal; no chat redesign.

## Contract

Keep Chat minimal. The settable axes get compact selectors; the compiler-DERIVED intent is shown but never
turned into a fake control; reasoning stays at its lightest default and is never auto-escalated (§9, §14).

## Changes

- **Selector audit (no change needed):** the TopBar already exposes Query Type (RETRIEVAL mode buttons),
  Chat Model (MODEL picker), and Reasoning (dropdown). Reasoning DEFAULT is `none` — the lightest mode, whose
  template is empty ("model answers directly") — and there is NO auto-escalation path in the codebase
  (`apply_reasoning` is a no-op for `none`; the mode changes only when the user picks it). §9's "reasoning
  DEFAULT LOW, do not auto-escalate" therefore holds structurally; nothing to change.
- **Intent — surfaced read-only, NOT a selector:** the chat request model has no `intent`/`query_type` override
  field. `plan.intent` is derived by the CHAT-QUERY-COMPILER (`intent_of_plan`) and already travels in the
  answer payload as `retrieval.chat_plan` (`plan_receipt`, compiler default `on`). Added `chat_plan` to the
  `Retrieval` type and an `IntentChip` in the answer meta-row (both the `chat` and `llm` answer paths) that
  renders `⌖ <intent>` with a tooltip naming the task/response type — a DISPLAY of the backend-derived value,
  shown only when the compiler returned one. New muted `.badge-intent` style (deliberately unlike the accent
  control badges, so it does not read as a control).
- Rebuilt dist; scaffold dist-hash declaration updated → `index-BoHx7tHd.js`/`index-EfNoNCOh.css`.

## Proof

- `npm run build` green. LIVE, browser-verified at :5173/ui on rag-canary: reasoning selector shows `none`
  (default); a real turn ("what do these documents describe and how do they relate?") streamed a grounded answer
  (cites [S11]–[S15]) and the meta-row rendered **HYBRID · ⌖ comparison · GENERATED · deepseek-v4-flash-0731 ·
  15 chunks** — the compiler classified the "how do they relate" question as COMPARISON, surfaced read-only
  (tooltip: "derived by the chat compiler … read-only, not a control. task GROUNDED_SYNTHESIS · response answer ·
  graph useful"). Zero console errors.
- `repo_guard` ok; `wiki_worm --check` ok.

## Rejected claims

- **No Intent control added** — intent is compiler-derived with no override contract; a selector would be
  non-functional. It is DISPLAYED, not chosen (§9 "if backend supports it" → it does not; §14).
- **Reasoning not auto-escalated** — grep confirms no escalation path; default `none` is the lightest mode.
- **No frontend inference** — the intent badge renders the backend `chat_plan.intent` verbatim; the UI computes
  nothing (§11, §14).

## Open contract gaps

- If the backend later adds an intent-OVERRIDE contract, the read-only badge can become a selector; until then a
  selector would be fiction.
- Slice 5 remains: the §13 acceptance checklist run against the live backend + durability close-out
  (CONTINUITY, register status → done, forensic hold reaffirmed).
