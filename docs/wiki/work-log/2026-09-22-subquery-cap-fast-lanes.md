---
change_id: SUBQUERY-CAP-FAST-LANES-V1
owner: "@king"
date: 2026-09-22
status: complete
architecture_impact: "Retrieval budget: the typed-subquery cap goes 3 → 10 (env knob POLYMATH_CHAT_MAX_SUBQUERIES), which lets the PROFILE and BRIDGE subqueries search and so switches the live WLK2C bridge pass back on. FAST / VECTOR run lanes A + B on the primary and its subqueries only: no dual-read, latent, resolution lift, see-also fan-out, graph destination, and no WLK2C bridge re-judging (the explicit ✨ still wins the latent lane)."
last_reviewed: 2026-09-22
---

# Subquery cap 3 → 10; FAST runs no depth pass

## Contract
Owner, 2026-09-22: "we need to change the cap increase it to 10. and fix 3" (FAST was not lighter than HYBRID), and on
the reranker: "I thought we fixed it with a smart design where my subqueries survive."

Found before the change (read-only):
- The design is live, not missing: WLK2C-RETRIEVAL-LINEAGE-V1 (registers 11.315–11.326) and LATENT-QUERY-FUSION-V2
  (11.327–11.332), with flags `POLYMATH_CHAT_BRIDGE_COMPILER` / `_LATENT_SELECTION` / `_LATENT_FUSION` = 1 in the running
  orchestrator. The pieces: ranked lanes per (query, lane) fused by origin weight, top 5 per query kept through the union
  cut, and a second pass that grades the bridge pool (bridge↔q0 once, chunk↔its bridge) and re-seats the evidence
  (`latent_selection` → `latent_portfolio`).
- The cap starved it. The plan lists user aspects, then Profile Scout expansions, then bridges;
  `chat_retrieve_v2` kept the first 3 non-primary subqueries. On the owner's three turns that was q1, q2, p0, so
  p1 and all bridges br0–br3 never searched. The latent pool only admits candidates found by a bridge, so it
  was empty and the bridge pass never ran.
- FAST: `apply_intent_policy` switched dual-read, latent and resolution lift on in every mode except GNN. FAST was HYBRID
  minus the sparse lane, and measured slower than HYBRID.

## Changes
- `shared/polymath_shared/candidate_engine.py`: `CandidateBudget.max_subqueries` 3 → 10. The embedder accepts ≤ 32 texts
  per request and batches on the device, so 1 + 10 is still one embedding round trip.
- `orchestrator/orchestrator/api/chat_retrieval.py`: `max_subqueries` joins the env knobs (`POLYMATH_CHAT_MAX_SUBQUERIES`,
  the rollback). `_fast_budget` turns off the depth lanes for VECTOR / FAST inside `chat_retrieve_mode`, the one place
  every caller (chat, /compare, /retrieve, MCP) goes through. `keep_latent` preserves the explicit ✨.
- `orchestrator/orchestrator/api/ui.py`: the chat path passes `keep_latent=bool(req.latent)`. `_apply_latent_selection(...,
  mode=)` returns before any reranker call for FAST.
- Tests: `test_chat_modes.py` gets 3 new cases (all 8 subqueries of a live-shaped plan are embedded and searched; the env
  knob restores 3; FAST / VECTOR get no depth lane while HYBRID keeps them, and ✨ still wins).
  `test_latent_selection.py` gets 1 (FAST skips the bridge pass, leaving evidence untouched with no reranker call;
  HYBRID / GRAPH / WILDCARD grade the bridge candidate `COMPLEMENTARY_ELIGIBLE`).
- `docs/wiki/experiments/subquery-cap-fast-2026-09-22/`: the replay harness and its 30 result rows.

## Proof
Replay of the owner's three frozen plans (`query_receipts` q_be4b06b788 / q_7eab052201 / q_bdd1abd51e). Each plan ran
in-process through each tree's engine, then the bridge pass, against the live Qdrant, embedder and reranker. No LLM. Two
interleaved reps.

| | production (cap 3) | new (cap 10) |
|---|---|---|
| subqueries searched | 3 of 8 (q1, q2, p0) | 8 of 8 |
| bridge pool / bridge pass | 0 / never ran | 22–45 candidates graded |
| FAST retrieval, cold → warm | 6.9–7.9 s → 5.1–5.7 s | 3.1–3.5 s → 1.7–1.8 s |
| HYBRID retrieval, cold → warm | 5.3 s → 5.1–5.3 s | 6.6 s → 5.4–5.6 s |
| lane timeouts | 0 / 12 | 0 / 18 |

- The bridge pass now costs 3.7–6.2 s cold per HYBRID / GRAPH / WILDCARD turn: one reranker call for all bridge↔q0 pairs,
  plus one per bridge. With a warm reranker memo it costs 0.2–0.3 s. FAST skips it.
- Final evidence after the bridge pass (HYBRID, cap 10): direct 5 / 4 / 6 and complementary 10 / 11 / 9 of 15 seats.
  Every DIRECT q0 chunk kept its seat (rule A). The q0 rows below DIRECT were replaced by bridge candidates that passed
  both links. The portfolio has no complementary cap (`complementary_cap=None`).
- Determinism: the 26 test files that import the engine, chat retrieval, the chat path, intent, fusion or latent
  selection, run offline (`-k "not test_live_"`) on both trees. Production fails 2 before this change
  (`test_chat_modes::test_wildcard_sweep_overlaps…` timing, `test_chat_runtime::test_compiler_on_drives…`); the worktree
  fails the same 2. A third worktree-only failure, `test_synthesis_attempt_telemetry::test_the_bound_retry_records_BOTH_attempts`,
  is environmental: the test reads `llm_providers` from the real database (`_litellm_credentials` → `db.tx()`), and a
  worktree has no `.env`, so `settings.py` falls back to the default DSN and the pool times out on
  "password authentication failed". With the repo `.env` loaded the same pair passes in the worktree (2 / 2).
  A first comparison run did not deselect `test_live_*`; it sent 10 live chat turns to :7200 (9 generated) before it
  was stopped.
- Proof level: UNIT_PROVEN; REPLAY_PROVEN against the live stores. DEPLOYED after the merge and bounce.
  LIVE_PATH_PROVEN needs a real chat turn.

## Rejected claims
- "Conditional reranking was never built" (said to the owner earlier today): wrong. It is live; the cap starved it.
- "The owner's full conditional-rerank design is live": not all of it. Missing pieces:
  - per-lane k scaled by lane quality;
  - a γ blend (today both links must pass);
  - conditional judging for USER and PROFILE subqueries (only BRIDGE / CORPUS_EXPLORE lineage get it);
  - guaranteed judged or final seats for lane winners beyond the top-5 union floor;
  - an unconditional q0 top-k floor;
  - the three metrics (local-winner survival, chain precision, q0 groundedness).
- "FAST is retrieval-only now": P10 EVIDENCE-RESOLUTION's one bounded second round still runs in FAST when a need is
  unsupported. That is its own design (modes FAST + HYBRID).

## Open contract gaps
- `CandidateBudget.max_subqueries`: UPDATED (default 10, env knob).
- `chat_retrieve_mode` VECTOR / FAST: UPDATED (depth lanes off; `keep_latent`); /compare and /retrieve FAST follow it.
- WLK2C `_apply_latent_selection`: UPDATED (FAST skip).
- GNN: TESTED_UNCHANGED.
- Bridge-pass latency (3.7–6.2 s cold): DEFERRED. It is 1 + n_bridges sequential reranker calls; batching them is a
  follow-up.
- Evidence composition (up to ~10 of 15 seats complementary): DEFERRED to the owner. The q0 top-k floor from the
  owner's design would bound it.
