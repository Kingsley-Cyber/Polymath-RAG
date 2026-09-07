---
title: "WORK LOG — INTERACTIVE-RELIEF-V1: the judge stops timing out behind the re-projection; rewrites keep their evidence; answers get a length rule"
change_id: INTERACTIVE-RELIEF-V1
date: 2026-09-07
owner: governance (owner reports 2026-09-07 while testing by hand: "rerank_timeout … I HAVE this major error"; "corpus retrieval can sometimes not retrieve anything"; "it generates too much and too long"; "every query the model is injected a large amount of context")
last_reviewed: 2026-09-07
last_touched: 2026-09-07
status: implemented
register: 11.124
package: config/runtime_budget.yaml (embedder batch caps), .env (POLYMATH_CHAT_RERANK_DEADLINE_S=12, owner-held) + .env.example, orchestrator/orchestrator/api/ui.py (CARRY-ARTIFACT-V1, presentation-v2 length rule, POLYMATH_CHAT_MAX_TOKENS default 6000), tests/determinism/test_chat_{synthesis,runtime,generation_bound}.py
architecture_impact: "Fleet: the embedder's batch caps halve (8 texts / 16 k tokens → 4 / 8 k) so projection batches fit the 3.5 GiB Metal cap on the first try instead of failing and splitting; the chat judge's deadline is 12 s (env) while the corpus re-projection runs on the shared GPU. Chat: a transform / continue turn (retrieval skipped by the compiler) now keeps the previous answer's cited passages in the bundle — admitted without a relevance gate, capped at 16 — so a rewrite stays grounded and citable; the presentation contract (v2) states length limits per task and forbids padding and closing summaries; the output ceiling drops 16 000 → 6 000 tokens. Nothing under §3.23 changes; the re-projection itself is left to finish."
---

# WORK LOG — INTERACTIVE-RELIEF-V1

## Contract

While the owner tests by hand: the judge is not starved by background work, a follow-up that rewrites an answer keeps that answer's sources, and an answer is as long as the question warrants — not as long as the evidence allows.

## Changes

- **GPU relief.** `config/runtime_budget.yaml` `sidecar_embedder.max_batch_texts` 8 → 4, `max_batch_tokens` 16384 → 8192 (the supervisor exports the budget into the sidecar's env at every spawn; applied by recycling the embedder slot). `.env` `POLYMATH_CHAT_RERANK_DEADLINE_S=12` (the supervisor overlays `.env` on every respawn; applied by respawning the orchestrator). Documented in `.env.example`.
- **CARRY-ARTIFACT-V1** (`ui.py`): the carry block no longer requires a retrieval turn. On a skipped turn `_admit_carry` runs with a unit scorer, floor 0 and `_CARRY_ARTIFACT_CAP` (16, env `POLYMATH_CARRY_ARTIFACT_CAP`); receipt `carry.mode = artifact | judged`; phase line "Carried evidence: N of M kept for the rewrite".
- **presentation-v2** (`ui.py`): a length rule at the head of the contract — factual ≤ ~200 words (1–3 paragraphs), explanation / comparison ≤ ~450 (3–6), build / rewrite / create = the artifact plus at most two framing paragraphs; longer only when asked; never restate the question, never pad, never a closing summary or unrequested next steps. `_PRESENTATION_CONTRACT = "presentation-v2"` in every receipt. `_chat_max_tokens()` default 16 000 → 6 000.
- Tests: contract pins updated (v2, length rules present, ceiling 6 000); `test_carry_artifact_mode_keeps_the_previous_answers_evidence_without_a_relevance_gate`; the runtime frame sequence and route-parity pins now expect the `carry` phase and carried evidence ids on a no-retrieval turn.

## Proof

**The judge timeouts, traced (05:2x UTC, owner testing).** Last 40 UI turns: `rerank_timeout` on 8, `embed_deadline` on 10; retrieve phase 13–34 s on the bad turns against 3–8 s on the good ones. Sidecar logs: the embedder (`:8742`, Qwen3-Embedding-0.6B under a 3.5 GiB Metal cap) logged 309 `mps oom … splitting` events in the hour (3,394 since 08-30), 8 → 4+4 → 2+2, each failed attempt ≈ 5 s of device time; the only client connected to it was `project_qdrant_worker`. The reranker's lease log shows the interactive class working ("background rerank batch yielded to interactive work; queued 4702 ms") — the queue wait is the in-flight background batch. The load is a corpus-wide re-projection: 24 `project_qdrant` tickets for 24 cinema books ready since 2026-09-05 plus one leased (Making Meaning with Machines, 1,246 children), 63 cinema runs `reconciling`; the leased ticket had been failing "transient" since the embedder was unreachable at 04:42 (it restarted at 04:57). RAM is not the constraint (68 % free); Metal memory is. The control plane assigns workers by open tickets (FLEET-AUTOPILOT-V1); there is no lane-pause lever and holding tickets by hand is a status sweep the medic law forbids — so the fix is to stop the embedder wasting attempts, not to pause the lane. Also found: each edit under `shared/` earlier in the hour fence-restarted worker slots at 05:14 and 05:18 while the owner was testing.

**"Sometimes retrieves nothing."** 97 / 97 receipts in the last four hours are `ok`. Every zero-evidence turn was a follow-up the compiler classified TRANSFORM_USER_CONTENT or CONTINUE_PRIOR_ARTIFACT ("turn it into a prompt for a 5 sec video…", "PUT THE PROMPT IN XML AND YAML", "so what's the final prompt??"): retrieval skipped by rule, and — the defect — the carried evidence dropped by the condition `if req.carry_context and not _skip_retrieval`, with the judged path's relevance floor (0.25 against "put the prompt in XML") set to reject it anyway. The rewritten artifact was built from conversation text alone; the owner's next message was "DID YOU USE THE CORPUS ?" (answered as a full GROUNDED_SYNTHESIS in 80 s).

**"Generates too much."** Owner turns: 33 s, 52 s, 80 s, 179 s of generation (the 179 s CREATE ≈ 3,500 words); tonight's probe answers on the fixtures ran 260–390 words p50, up to ~700. The contract had paragraph rules but no total-length rule; the ceiling was 16 000 tokens.

**"Injected a large amount of context" — measured.** Standing instructions per turn: 17,037 characters ≈ 4,300 tokens — grounding 2,670, the v3.3 style layer **10,921**, presentation 2,926, study layer + authority + date 520. Evidence: 15 rows of child passages at a 73-word median ≈ 6,500 characters ≈ 1,600 tokens (the 2,000-character row cap almost never binds). So the model reads roughly 2.5 characters of instruction for every character of evidence; the owner's instinct is right, and the bulk is the style layer, not the chunks. Left for the next item (LEAN-PROMPT): trim the style layer to what the grounding and presentation contracts do not already say, measured on the ten-question loop (precision, tags, words).

**State at commit.** The code half (CARRY-ARTIFACT-V1, presentation-v2, the 6 000 ceiling) and the config half (embedder batch caps 4 / 8 k in `runtime_budget.yaml`) are committed; unit suites green (36: synthesis, generation bound, receipts, runtime, hygiene, modes). Neither is LIVE yet: the owner is testing by hand and asked for no respawns, so the orchestrator still runs the previous code and the embedder keeps its old caps until its next spawn (the supervisor exports the budget at every spawn). The owner's "go" window is: set `POLYMATH_CHAT_RERANK_DEADLINE_S=12` in `.env`, recycle the embedder slot, respawn the orchestrator (`scratchpad/go_window.sh`, about one minute). The after-measurement — judge timeouts on the next 40 UI turns, generation seconds per task type, carried evidence on rewrite turns — is recorded here when the window has run.

## Rejected claims

- "Pause the re-projection" — no lever exists that is not a ticket sweep; and the work is legitimate (09-05 runs finishing).
- "Raise the judge deadline only" — hides the cause; the batch caps remove the wasted device time, the deadline is the margin while the lane drains.
- "Force retrieval on every follow-up" — no: "put this in XML" should not search; it should keep what it is rewriting. That is what CARRY-ARTIFACT-V1 does.
- "Cut the ceiling to 2 000" — a CREATE artifact legitimately needs more; the length rule is the lever, 6 000 the backstop.

## Open contract gaps

- The length rule is unmeasured on a loop (owner stopped tonight's measurement to test by hand); the receipt carries `presentation-v2`, so the owner's own turns are the measurement until the ten-question loop runs.
- The judge deadline is a temporary margin; return to 8 s when the projection backlog has drained (24 tickets).
- LEAN-PROMPT (the 10.9 k-character style layer) is the next item, not this one.
- The `funnel-probe` / `DID YOU USE THE CORPUS ?` shape — a question about the turn itself — still compiles as GROUNDED_SYNTHESIS; answering such meta-questions from the receipt is a small separate item.
