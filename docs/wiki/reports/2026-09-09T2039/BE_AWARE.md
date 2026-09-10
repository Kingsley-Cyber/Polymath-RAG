---
owner: "@king"
last_reviewed: 2026-09-09
status: ACTIVE — architectural traps for the next session
---

# BE_AWARE — traps that will mislead a fresh agent (2026-09-09T2039)

Each trap is a place where the obvious reading of the repo is WRONG. Verify against runtime, not code presence.

## 1. code exists ≠ live · wired ≠ enabled · enabled ≠ production default  ← THE session's key finding

The `FINAL-RETRIEVAL-ROUTING-SYNTHESIS-V1` phases **P2–P8b are all "DONE (default-off)"** in the plan's own
ledger — and they are genuinely OFF at runtime. Verified 2026-09-09:

- `intent_policy_enabled()` → `POLYMATH_CHAT_INTENT_POLICY` in ("1","true","on"); **default off**
  ([orchestrator/orchestrator/api/chat_retrieval.py:141](../../../../orchestrator/orchestrator/api/chat_retrieval.py)).
- The flag is **unset** in `.env`, in the fleet/run scripts, in `settings.py`, and in the **running
  orchestrator process env (pid checked live)**. Same for `POLYMATH_CHAT_SYNTH_ROLES` and the additive-lane flags.
- Gate site: `_ip = _ip_on() and _plan.intent` → False → `default_budget()`, `graph_assist="off"`, no roles
  ([orchestrator/orchestrator/api/ui.py:2597](../../../../orchestrator/orchestrator/api/ui.py)).
- **Live receipt:** `/chat/stream` on a relational cinema query returned `intent=SYNTHESIS, graph_useful=True`
  but `mode HYBRID · counts {} · additive-lane counts NONE · evidence_roles None`. Intent is **classified,
  not routed.**

**Do not** report "the intent routing is implemented" as if it changes answers today. It does not. The chat
`⌖ intent` badge in the UI shows the compiler's classification, which is real but currently inert for routing.

## 2. INDEXING COMPLETE ≠ RETRIEVAL MIGRATED ≠ PRODUCTION DEFAULT ≠ LEGACY RETIRED

Four distinct states; only the first is true:

| State | Truth (2026-09-09) |
|---|---|
| INDEXING COMPLETE | **TRUE** for fresh docs — profile + atoms + parent-MAP + graph + projections mint on `/upload` (rag-canary 3/3 canary). Existing corpora (cinema) are NOT backfilled (forensic hold). |
| RETRIEVAL MIGRATED | **FALSE** — chat runs baseline HYBRID; the vNext routing lanes are flag-off (item 1). |
| PRODUCTION DEFAULT | **FALSE** — pMAP auto-mint is flag-gated (`POLYMATH_DOC_PARENT_MAP_ENABLED`), currently scoped to `rag-canary` only via a transient env. |
| LEGACY RETIRED | **FALSE** — legacy summaries + parent_enrichment + hybrid-retrieval-v1 paths all still present and in use. |

**Do not interpret "new code exists" as "old dependency is safe to delete."** The migration authority
(`RETRIEVAL-MIGRATION-DEPENDENCY-V1`) requires a zero-reader proof before retiring any producer/state.

## 3. Not all endpoints share one retrieval runtime

- `/chat` + `/chat/stream` → `run_chat` → `chat_retrieve_mode` (**chat-retrieval-v2**; intent policy exists here
  but is off).
- `/retrieve` → `fast_retrieve` / `hybrid_fast_retrieve` / `graph_retrieve` / `wildcard_retrieve`
  (**hybrid-retrieval-v1**; no intent policy at all).
- `/ask` → its own path (grounded-answer / hybrid-retrieval-v1).
- MCP → calls the app in-process (rebuild the mcp container to pick up app changes).

A change to `chat_retrieve_mode` does NOT change `/retrieve` or `/ask`. Verify the specific endpoint.

## 4. query_ready ≠ semantic (vNext) ready

`query_ready` is the legacy corpus retrieval-visibility flag. **vNext `vnext_ready`** = per-document
(`unresolved_eligible_parents == 0` AND profile vnext). A corpus can be `query_ready` on the legacy substrate
while individual docs are not `vnext_ready`. The CANONICAL-DOCUMENT-STATUS-V1 authority
(`shared/polymath_shared/document_status.py`) computes the per-doc rule; the UI RENDERS it, never recomputes.

## 5. limiter refusal ≠ HTTP 429 · lane selection ≠ HTTP dispatch

(register 11.185, the Groq control-plane repair.) A `LIMITER_REFUSED` dispatches **zero** provider HTTP —
it is NOT rate-limit consumption. `lane_counter` counts SELECTIONS, not HTTP dispatches. The Control Plane UI
(this session) renders these as **distinct** metrics — never conflate them when reasoning about quota.

## 6. Profile / Atoms / pMAP ROUTE; source children PROVE

Invariant §63/§64 of `FINAL-RETRIEVAL-ROUTING-SYNTHESIS-V1`: routing-inferred artifacts (document profiles,
profile atoms, resolution-lift terms, SEEALSO/BRIDGE/ANCHOR) are **never** factual evidence and never cited.
Only source child chunks + graph facts (with provenance) are evidence. Do not let an atom become a citation.

## 7. The chat `[S11]` citation tags render RAW (known UI bug, NOT fixed)

`compactCitations` ([frontend/src/components/MessageBubble.tsx:12](../../../../frontend/src/components/MessageBubble.tsx))
only compacts bracket contents of **12+ characters** — written for the old `[chunk_<hash>@…]` locator format.
The current CITATION-TAGS-V1 tags are short (`[S11]`, 3 chars) so they pass through raw and the legend is
ignored. The owner declined a fix this session ("nvm"). Leave as-is unless asked; the root cause is documented
so it is not re-investigated.

## 8. WILDCARD mode UI tooltip may be stale

`TopBar.tsx` labels WILDCARD "Stored knowledge objects", but `chat_retrieve_mode` defines WILDCARD =
`HYBRID ∥ divergent sweep`. Flagged this session; **owner did not confirm** it is wrong, so it was NOT changed.
Do not "fix" it without owner confirmation — it may describe intended atom-frontier behavior.

## 9. The fleet runs with TRANSIENT canary flags

The running orchestrator + supervisor hold `POLYMATH_DOC_PARENT_MAP_ENABLED=1`,
`POLYMATH_DOC_PARENT_MAP_CORPUS=rag-canary`, `POLYMATH_AUTOPILOT=1` in their process env. These **clear on a
normal restart** (`scripts/run_fleet_supervised.sh` without those vars). They scope pMAP auto-mint to
`rag-canary` ONLY — cinema is never re-mapped while scoped. A restart that drops the scope but keeps
`_ENABLED=1` with no `_CORPUS`/`_SINCE` would begin spending on every fresh doc — an owner decision.

## 10. Two pre-existing determinism failures are NOT regressions

`pytest tests/determinism` has 2 failures unrelated to any code this session:
- `test_fact_endpoint_eligibility::test_no_active_fact_has_a_pronoun_endpoint` — a `you` pronoun fact endpoint
  in the **cinema** corpus, created 2026-09-05 (forensic-hold data). Spawned as a background task.
- `test_chat_synthesis::…[brainrot_transform]` — a LIVE `/chat/stream` LLM-synthesis variance test.
The three suites covering this session's changes (`test_document_status`, `test_control_plane_status`,
`test_document_status_endpoint`) are 9/9 green. Do NOT weaken these gates to make them pass — record and route.
