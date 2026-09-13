---
title: "WORK LOG — COGNITIVE-ADAPTER-TRAIL-E2E-V1 E7 (part 1): substack.article_development on the SAME runtime — authored, runtime-neutrality pinned, run LIVE end to end with real retrieval"
change_id: COGNITIVE-ADAPTER-TRAIL-E2E-V1-E7
date: 2026-09-13
owner: king
last_reviewed: 2026-09-13
status: complete
register: 11.262
architecture_impact: "Adds the admitted manifest config/adapters/substack.article_development.json (claim/mechanism/tension/evidence/counterargument/analogy/implication/narrative role/article — no Trail ontology, no EXTERNAL_OPERATION). Worker VALIDATE gains closed `require` path checks over accepted outputs; the query-source fallback covers seed_idea and any first string field. No runtime branch on an adapter id (pinned by test). E7's official-MCP-client run follows the production switch."
---

> Plan §9 / §11 E7: "implement one materially different adapter using the same runtime … proves the runtime is a reusable
> cognitive substrate rather than Trail-specific code generalized in name only."

## Contract
Same closed step vocabulary, same contracts, same substrate — different semantics. The runtime must contain no adapter-name
conditional; the manifest alone carries the workflow; a connected agent answers typed AGENT_REASON steps citing only supplied
evidence; VALIDATE and the bounded BRANCH loop behave; the result validates `AdapterResultV1` with lineage.

## Changes
- **`config/adapters/substack.article_development.json`** — expand (COMPILE_PLAN) → retrieve (EXPLORE) → graph → `thesis`
  (AGENT_REASON: 2-4 theses with claim/mechanism/tension/counterargument + citations) → `stress` (VALIDATE require
  `theses[].counterargument`, `theses[].supporting_evidence_ids`) → `gap_check` (BRANCH: unknowns + audience + loop budget →
  `gap_retrieve`, else `narrative`) → `gap_retrieve` (targeted RETRIEVE → narrative) → `narrative` (AGENT_REASON: analogy,
  implications, sections with narrative_role incl. counterargument) → `draft` (AGENT_REASON: article with citation markers) →
  `cite_check` (VALIDATE require `article.citation_ids`) → `compile`. Budgets 24 steps / 4 agent / 1 loop / 0 external.
- **`workers/adapter_step_worker.py`**: `exec_validate` closed `require` paths (`a.b`, `list[].field` = every element) → typed
  `VALIDATION_FAILED` gap; `_query_text` honours `config.source`, then seed_idea/question/seed/query/signal/topic/problem, then the
  first string field. Every knowledge step in every manifest now sets `config.source` explicitly.
- **Tests**: `tests/determinism/test_adapter_runtime_neutrality.py` (runtime files never mention an adapter id or domain vocabulary;
  both workload adapters share the closed vocabulary and differ in semantics; substack imports no Trail ontology);
  `tests/integration/test_adapter_substack_live.py` (LIVE: real retrieval on `cinema`, the harness plays the agent for three steps).

## Proof
- **Live run (this commit)**: `substack.article_development` completed on the substrate — expand/retrieve/graph supplied ≥3 evidence
  refs; thesis submitted (2 theses, cited); stress VALIDATE passed; gap loop taken exactly once (`branch_loops == 1`) into
  `gap_retrieve`; narrative and draft submitted; cite_check passed; `adapter_result` = `completed`, article citation ids ⊆ lineage
  `polymath_evidence_ids`, unknowns preserved (`how much is lost on small screens`), 0 external operations, ≥ 9 step receipts.
- **Fail-closed evidence found on the way**: the first live attempt ended `failed` with a typed `STEP_EXECUTOR_ERROR` at `graph`
  ("no query text in input") — no guess, no partial result — which is the designed behaviour; the fix is a manifest `source` + a
  broader fallback, both tested.
- 30 green: neutrality 2 + pure 12 + contract 15 + live 1; guards green.

## Rejected claims
- **"A second adapter proves scalability only if it also touches Trail"** — REJECTED: plan §9 requires the opposite (no Trail import).
- **"Loop back to the thesis step for evidence gaps"** — REJECTED (measured): the loop re-issued the agent step; a dedicated
  targeted-retrieval step that continues to `narrative` is the correct shape.
- **"VALIDATE needs code"** — REJECTED: closed `require` paths over accepted outputs are enough for both adapters; anything richer is a
  manifest/schema concern, not a plugin.

## Open contract gaps
- The official-MCP-client run (Hermes or the `mcp` client connected ONLY to Polymath) waits for the production switch + bounce
  (the live orchestrator/MCP still run pre-E2 code); the harness-as-agent run above exercised the same service path in-process.
