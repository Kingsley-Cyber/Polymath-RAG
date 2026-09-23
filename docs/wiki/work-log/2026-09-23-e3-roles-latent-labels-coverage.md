---
change_id: DOCUMENT-RAG-E3-ROLES-LATENT-LABELS-COVERAGE
owner: "@king"
date: 2026-09-23
status: complete
architecture_impact: "orchestrator code on branch fix/document-rag-s0-rest (NOT merged, NOT live). The chat path keeps each evidence row's retrieval role and WLK2C latent seat + lineage, so role-aware synthesis (POLYMATH_CHAT_SYNTH_ROLES, on in the live .env) finally receives them. Exploration probes are no longer presented as user aspects in the coverage block. Prompt-content change only; no retrieval or ranking change."
last_reviewed: 2026-09-23
---

# E3: roles and latent labels reach synthesis; coverage lines skip exploration probes

## Contract
Plan of record `docs/wiki/plans/DOCUMENT-RAG-COMPLETION-V1.md` §9 (S3 / E3) and Part E; owner kickoff 2026-09-23: "E3 (roles and
latent labels reach synthesis; coverage lines)". This fixes ENRICHMENT-SURFACES-AUDIT defects 5 and 6:
- the evidence rows were rebuilt with only chunk / doc / parent ids (`ui.py:3583` area), so `bundle["evidence_roles"]` was
  always `{}` and the WLK2C seat labels were lost;
- `_coverage_lines` listed PROFILE / BRIDGE probes as aspects and told the model "NO EVIDENCE RETRIEVED: say so explicitly"
  about see-also text.

## Changes
- `orchestrator/orchestrator/api/ui.py`:
  - NEW `_evidence_rows`, which keeps `role`, `latent_role` and `latent_lineage`; the chat path uses it;
  - NEW `bundle["evidence_latent"]` = `{chunk_id: {"seat", "via"}}`, where "via" is the bridge query that seated the chunk;
  - `_grounded_messages` labels a latent row as `(LATENT · COMPLEMENTARY via: <bridge>)` when role-aware synthesis is on;
    it stays byte-identical when the flag is off;
  - NEW `_EXPLORATION_ORIGINS` (PROFILE + BRIDGE + CORPUS_EXPLORE) and `_exploration_query_ids`;
  - `_coverage_lines(coverage, skip_ids=…)` skips those probes, and emits no header when nothing is left;
  - `_request_block` passes the plan's probe ids.
- `tests/determinism/test_chat_synthesis.py`, 3 tests added (none edited):
  - the rows keep the role and the latent seat;
  - the latent seat and its bridge are shown to the model (flag-gated);
  - coverage lines skip exploration probes.

## Proof
- **Red first:** all 3 failed on `f74871d` (AttributeError: `_evidence_rows` / `_exploration_query_ids` missing; no latent
  label). All pass after the change.
- **test_chat_synthesis:** 15 passed, including the existing P8b role test, which is unchanged.
- **Related suites combined** (test_chat_evidence_route, test_chat_hygiene, test_chat_modes, test_chat_runtime,
  test_evidence_resolution, test_latent_selection, test_synthesis_attempt_telemetry; no fleet DB): 107 passed, 3 failed.
  - Two are the known pre-existing failures (the WILDCARD timing test; compiler-on-both-routes).
  - The third, `test_synthesis_attempt_telemetry::test_the_bound_retry_records_BOTH_attempts`, hit a Postgres auth error
    inside the combined no-`.env` run. The file alone passes on this branch (21 / 21), and the test passes alone on the base.
  - PENDING: the same combined run on the unmodified base (`f74871d`) was still running when the session closed. The next
    session reruns it. If the telemetry test fails there too, it is order / environment dependent (no `.env`), not E3.
- Proof level: UNIT_PROVEN. A live turn with a seated latent chunk must show the label in the prompt after merge + bounce.

## Rejected claims
- "Role-aware synthesis is live": the flag was on, but the roles map was always empty. It now receives data.
- "Coverage lines must list every compiled query": only the user's aspects. Exploration probes route; they are not claims the
  answer must cover.

## Open contract gaps
- The synthesis prompt contract (roles, latent labels, coverage): UPDATED (tests added).
- Contract impact: `scripts/contract_impact.py` at commit time (the pre-commit hook output is recorded in the register row).
- BLOCKED: merge + bounce, on the owner's word.
