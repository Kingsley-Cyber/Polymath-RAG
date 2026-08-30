# CLAUDE.md — how to work in polymath-v4

Governance and file-ownership rules live in `AGENTS.md` (read it). This file
is the working style the owner expects, distilled from the 2026-08-29/30
sessions. Start every session with
`docs/wiki/plans/CONTINUITY-PACKET-<latest>.md`.

## Way of working
1. **Measure before you touch.** Read the code path AND the live state (DB,
   logs, receipts, `/ready`) before changing anything; quote `path:line`
   and numbers. If a claim can't be measured, say so.
2. **Lead with the decision**, one screen, tables over prose. Depth goes in
   repo files (work-log, plan, register), not chat.
3. **Completion means shipped**: implemented + tested + fleet restarted +
   committed + merged, or say exactly which part is missing.
4. **Owner decides**: production writes (purges, ticket re-queues, deletes,
   corpus changes), design deviations, and anything irreversible wait for an
   explicit go. Record every deviation in `PLAN-AUTHORITY-REGISTER.md`
   (never delete lines) and every mutating change in the work-log
   (Contract / Changes / Proof / Rejected claims / Open gaps).
5. **Design docs are ingested one file per pass**; notes go to
   `docs/wiki/plans/*-DESIGN-NOTES.md` before the next file is opened.
6. **Reuse the repo's own contracts** (ontology, identity helpers, receipts,
   stage transactions, `representation_kind`, injected-callable seams)
   instead of inventing parallel ones. The predicate/entity vocabulary is
   `shared/polymath_shared/llm_extraction/ontology.py` — 17 predicates +
   `RELATED_TO`, enforced at prompt and gate.

## Operating rules (learned the hard way)
- Workers self-quarantine on ANY mtime change under `shared/polymath_shared`,
  `workers/workers`, `control/control` (`.py/.yaml`). No edits there while an
  ingest runs; restart the fleet after every commit that touches them
  (`pgrep -f "workers\.[a-z_]*_worker" | xargs kill -TERM;
  pgrep -f project_neo4j | xargs kill -TERM`). `control.main` caches census
  verdicts — restart it if completed runs sit at `reconciling`.
- Merge `main` from the worktree `../polymath-v4-main`; never `git checkout`
  in the live tree. Commit messages end with the Co-Authored-By /
  Claude-Session trailers; never push without asking unless the owner
  already said "push and merge".
- Extraction: `llm_live` on both lanes; byte rule floor 300 KB (set 450 KB)
  is a PRIVACY rule (≤ threshold never leaves the machine); generation is
  LOCKED (plan §1.6): `max_tokens=2500` per neighborhood,
  `repetition_penalty=1.15`, ctx 400, thinking off, temperature 0.
  The gate is the only authority; gated relations become facts
  (`workers/llm_direct.py`).
- Extraction coverage is MANDATORY (EXTRACTION-COVERAGE-V1): the extract
  artifact's `llm_extraction.stats.neighborhoods_*` + `neighborhood_dispositions`
  are the accounting; the census refuses `query_ready` on `dropped`/`unaccounted`
  (run → `degraded`, reasons in `runs.metadata.degraded_reasons`, visible in
  `/semantic_readiness.extraction`). Never "fix" a degraded run by hand —
  re-ingest the document. `chunks.region_role` (REGION-ROLE-V1) decides
  what is sent to the LLM and what becomes a routing summary.
- Controllers persist in `llm_controller_state`; receipts carry
  `limiter_effective`, `batch_tokens_cap`, `finish_reason` — read them
  before guessing at throughput or truncation.
- Memory: keep an eye on `curl :8755/ready` (MLX active/cache/peak) and
  `vm_stat`; the batched server is capped (1 GB cache / 12 GB).
- Tests: pure suites run with `--noconftest -p no:cacheprovider`; DB suites
  roll back. Guards: `scripts/repo_guard.py`, `scripts/agent_preflight.py`,
  `scripts/wiki_worm.py --check` must pass before a commit.
- UI validation: the owner drives `http://127.0.0.1:7200/ui/`; observe via
  `/private/tmp/polymath_fleet/orchestrator.log` and the DB, confirm the
  backend code path for each action.

## Priorities the owner has set (2026-08-30)
Base e2e validation first (UI, MCP, query, ingestion, extraction) → GLiNER +
spaCy full retirement → embed-early DAG, job-level completion + lane assist,
supervised lifecycle (plan §9) → latent transfer layer (plan phases A–E).
The three-layer graph design is rejected; v3.3 `tier_chunker` is the
canonical chunker (swap = re-ingest).
