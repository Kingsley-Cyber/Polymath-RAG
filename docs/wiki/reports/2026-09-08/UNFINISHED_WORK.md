---
owner: "@king"
last_reviewed: 2026-09-09
status: FORENSIC HOLD — open items
architecture_impact: none
---

# UNFINISHED WORK — 2026-09-08/09

Ordered by what the next session should touch first. See `DEPENDENCY_MAP.md` for prerequisites.

## Principal task

- **F1 — Groq Parent-MAP forensic audit.** Reconstruct the conservation chain, answer investigation
  targets A–I, satisfy the acceptance gate. Evidence-first; no code patch until the evidence table
  exists. Full spec: `GROQ-FORENSIC-AUDIT.md`. **Blocks: everything below that needs coverage.**

## Coverage-gated (blocked on F1 → bounded canary → owner-approved backfill)

- **U-COV — cinema parent-MAP coverage to `unresolved==0`.** ≈1254/11,993 now. Only after F1's gate +
  bounded canary + owner review. Resumable/idempotent via `parent_map_backfill.py --corpus cinema
  --project --concurrency 6` — but **not** to be run before the gate.
- **D-10 — formal HYBRID answer-quality uplift number.** Retrieval-side value + P8b synthesis
  presentation are already qualified live (register 11.179/11.181; ON wins 4/5 blind judge). A
  statistically-tight number needs a larger relational fixture + human/larger-model rubric + chat-model
  capacity. Partially coverage-gated (richer parent-MAP reach adds winning candidates).
- **D-11 — GRAPH-mode answer-quality uplift.** Needs Neo4j density + parent-MAP coverage to surface
  winning RELATIONAL candidates downstream.
- **P5 document branch / P7 §39 localization.** The doc→parent-MAP reach of the fan-out / graph-dest
  lanes scales with coverage (the TERM/global-child branches are already coverage-independent and
  qualified).

## Implementable now (routing code slices, NOT coverage-gated) — deferred by the forensic hold, not blocked

These are genuinely unblocked code slices; the owner has redirected priority to the audit, so they wait.
Do not start them instead of the audit.

- **D-5 / P5 BRIDGE/ANCHOR fan-out (§20–§22).** The SEEALSO term-branch is done + qualified (lane G,
  `SEEALSO_FANOUT`, register 11.172/11.179). BRIDGE/ANCHOR/TENSION fan-out over the generated atoms
  (BRIDGE 54, ANCHOR 67 on cinema) is the next code slice, coverage-free like SEEALSO. Surface:
  `shared/polymath_shared/candidate_engine.py` lane G + the injected `fanout_search` + `query_intent.py`
  policy (`RELATIONSHIP`/`EXPLORATORY` already set `seealso_fanout=True`).
- **D-8b deterministic `/ask` role presentation.** The LLM chat path presents by role (`_grounded_messages`,
  register 11.174). The deterministic `grounded_answer` (`answer_synthesis.py`, the load-bearing claim
  path) presenting by role is a separate careful change, still deferred.
- **P12 Wildcard atom-frontier.** Atoms exist (data gate cleared, register 11.169); add an atom-frontier
  source to `divergent_sweep` (`shared/polymath_shared/divergent.py`). Explicitly lowest-value / highest-
  complexity routing slice.

## Session hygiene carried in this handoff

- SiliconFlow graph-extraction lanes (3 accounts, Qwen3-8B) are ACTIVE + concurrency-tuned + live on the
  fleet (register 11.182/11.183, commits a1b94ae/b0000dd, on main). Not related to the forensic hold;
  MAPs remain Groq-pinned.
