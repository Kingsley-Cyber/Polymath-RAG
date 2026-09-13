---
title: "WORK LOG — Chat-retrieval runtime audit: planned INTENT×FIELD×TECHNIQUE×BUDGET routing is built but flag-gated OFF"
change_id: CHAT-RETRIEVAL-RUNTIME-AUDIT
date: 2026-09-09
owner: governance (verification only — no code change)
last_reviewed: 2026-09-09
status: complete (verification; no runtime change made)
register: 11.187
package: (verification — reads orchestrator/orchestrator/api/chat_retrieval.py, ui.py, shared/polymath_shared/query_intent.py; no file modified)
architecture_impact: "None (read-only verification). Establishes the RUNTIME TRUTH that the FINAL-RETRIEVAL-ROUTING-SYNTHESIS-V1 intent policy (INTENT×FIELD×TECHNIQUE×BUDGET) is BUILT but flag-gated OFF on the live orchestrator: POLYMATH_CHAT_INTENT_POLICY is unset, so /chat classifies intent but routes baseline HYBRID. Recorded so the next session does not mistake code presence for live behavior."
---

> **Ledger:** verification against `FINAL-RETRIEVAL-ROUTING-SYNTHESIS-V1.md` (§4/§64 policy) + register **11.187**. No pipeline/architecture change; no runtime flag changed.

## Contract

Answer the owner's question — is the chat query actually routed the way `FINAL-RETRIEVAL-ROUTING-SYNTHESIS-V1`
plans (INTENT × FIELD × TECHNIQUE × BUDGET, converging through parent-MAP, DIRECT/PRECISION/RELATIONAL/LATENT
roles)? — from runtime evidence, not documentation.

## Changes

None (verification only). Findings:

- **Compiler front-half is ACTIVE:** `/chat/stream` runs the CHAT-QUERY-COMPILER (default `on`), classifying a
  canonical intent. Live: a relational cinema query returned `intent=SYNTHESIS`, `graph_useful=True`
  (`compiler_alt: mistral-small`, 2.4 s).
- **Routing back-half is OFF:** the intent→field→technique→budget policy is gated by
  `intent_policy_enabled()` → `POLYMATH_CHAT_INTENT_POLICY` (default off,
  `orchestrator/orchestrator/api/chat_retrieval.py:141`). At the gate site
  `orchestrator/orchestrator/api/ui.py:2597`, `_ip = _ip_on() and _plan.intent` → False ⇒ `default_budget()`,
  `graph_assist="off"`, `_pol=None`, no intent-selected latent kinds, no roles.
- **Flag is unset everywhere it could be set:** `.env`, fleet/run scripts, `settings.py`, and the **running
  orchestrator process env** — all lack `POLYMATH_CHAT_INTENT_POLICY` (and `POLYMATH_CHAT_SYNTH_ROLES`, the
  additive-lane flags).
- **Endpoint split:** `/chat` + `/chat/stream` → `run_chat`/`chat_retrieve_mode` (chat-retrieval-v2, intent
  policy present-but-off); `/retrieve` → `fast/hybrid_fast/graph/wildcard_retrieve` (hybrid-retrieval-v1, no
  intent policy); `/ask` → its own hybrid-retrieval-v1 path. They do NOT share a retrieval runtime.

## Proof

- Live `/chat/stream` receipt (cinema, HYBRID, "How are film editing and cinematography related?"):
  `intent=SYNTHESIS · graph_useful=True · mode=HYBRID · counts={} · additive-lane counts=NONE · evidence_roles=None`.
  Intent computed, not routed.
- Code + env: `intent_policy_enabled` default off; flag absent from `.env`/scripts/`settings.py`/process env.
- Matches the plan's own ledger: P2–P8b marked "DONE (default-off), flag-off byte-identical"; uplift rows
  D-10/D-11 GATED on parent-MAP coverage.

## Rejected claims

- **"The intent routing is live"** — REFUTED. It is built and tested but flag-off; chat runs baseline HYBRID.
- **"The `⌖ intent` chat badge means the answer was routed by intent"** — NO. The badge shows the compiler's
  classification; that intent is currently inert for routing.
- **"Changing `chat_retrieve_mode` changes /retrieve or /ask"** — NO. Different retrieval runtimes per endpoint.

## Open contract gaps

- The measurable uplift from enabling the policy is GATED on parent-MAP corpus coverage (cinema behind the
  forensic hold) — see UNFINISHED_WORK U-1. Enabling the flag routes; it does not lift until coverage fills.
- No live A/B (off vs on) was run this session (owner deferred). The next verification step is the throwaway
  `POLYMATH_CHAT_INTENT_POLICY` A/B on `rag-canary` (no running-default change, no spend).
