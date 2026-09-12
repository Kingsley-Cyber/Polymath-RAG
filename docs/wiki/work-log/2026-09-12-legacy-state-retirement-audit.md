---
title: "WORK LOG — deeper runtime/dependency proof for the 4 RETIRE_CANDIDATE state tables; found and fixed two real bugs in the audit's own static census"
change_id: LEGACY-STATE-RETIREMENT-AUDIT-V1
date: 2026-09-12
owner: king
last_reviewed: 2026-09-12
status: complete
register: 11.218
architecture_impact: "audit tooling correctness fix only (shared/polymath_shared/conformance/{discovery,evidence}.py) — narrower/more accurate static census, no change to any production read/write path. No schema deleted; claim_sets is documented as a fully-proven deletion candidate but NOT dropped (destructive schema deletion is an explicit owner-authorization gate this session does not have)."
---

> Executor session, execution authority `POLYMATH_EXECUTION_AUTHORITY_XML_FINALIZED.md`
> §11 retirement law ("Never call something dead without FILE:SYMBOL/dependency
> proof... Use both graph/dependency tooling AND direct FILE:SYMBOL inspection.
> Neither alone is sufficient"). Continuation of the same-session conformance
> assessment: `scripts/audit_polymath.py --no-spend` flagged 4 state tables
> RETIRE_CANDIDATE ("no static reader or writer found — needs runtime proof before
> removal"); this closes that named next action.

## Contract

Requested outcome: a definitive, FILE:SYMBOL-and-runtime-evidenced classification for
`claim_sets`, `entity_knowledge_refusals`, `knowledge_tier_facts`, and
`medic_deadlock_probe` — the audit's own static scan was not, by its own stated
standard, sufficient proof.

- **Smallest acceptance:** each of the 4 tables gets a verdict backed by BOTH a
  repo-wide grep (not just the audit's own git-grep, since that grep was suspected —
  and confirmed — to have blind spots) and live Postgres statistics; any bug found in
  the audit tool itself gets fixed and proven, not just noted.
- **Owner / public contract:** none — this is an internal governance/tooling
  correctness pass. `scripts/audit_polymath.py`'s output changes (fewer, more
  accurate RETIRE_CANDIDATE rows); no application endpoint changes.
- **Inputs/outputs/persistence:** read-only against Postgres and the repository; the
  two code changes affect only the audit's OWN discovery/evidence-gathering, not any
  production table.
- **Dependency edges:** `shared/polymath_shared/conformance/{discovery,evidence}.py`
  → consumed by `shared/polymath_shared/conformance/assess.py::assess_state` →
  `scripts/audit_polymath.py`. No other caller.
- **Verifier / rollback:** `tests/determinism/test_conformance_state_census.py` (2
  cases, against this repo's real content) + a live audit re-run (before/after
  classification diff, below). Rollback: revert both files; the census reverts to its
  prior (buggy) behavior.

## Changes

- **Investigation first, independent of the audit tool:** `rg -n "\b<table>\b" .`
  (repo-wide, no type/path restriction) for all 4 names, plus live Postgres row
  counts and `pg_stat_user_tables`/`pg_stat_reset`-lifetime insert/update/delete
  counts for the ambiguous ones. Found the audit's OWN static scan had two distinct
  bugs (below), not that the 4 tables were actually dead.
- `shared/polymath_shared/conformance/discovery.py::durable_tables` — added
  `AND table_type='BASE TABLE'` to the `information_schema.tables` query. Views were
  being audited as if they were durable state with their own storage; dropping a view
  reclaims nothing, its underlying table is the real state and is already audited on
  its own row.
- `shared/polymath_shared/conformance/evidence.py::reader_writer_census` — removed
  the `f.startswith(("docs/", "tests/"))` exclusion (and added `.md` to the tracked
  extensions, which that exclusion had made moot). The function's own docstring says
  "over-counting readers only DELAYS a retirement, while under-counting enables a
  wrong deletion" — excluding `tests/` directly contradicted that: a contract test
  asserting a symbol's presence is about the strongest non-runtime liveness signal
  there is, not noise to discard.
- `tests/determinism/test_conformance_state_census.py` — new file, 2 cases against
  this repo's REAL content (not a synthetic fixture, because the bug IS the mismatch
  against real known ground truth): `knowledge_tier_facts` now correctly shows the
  contract-test and doc readers; `claim_sets` still correctly shows zero readers AND
  zero writers (guards against the fix being too aggressive and inventing false
  positives).
- `scripts/scaffold_polymath_v4.py` — TREE declarations.

## Proof

- **Independent verification, before touching any code** (`rg`, no type restriction,
  whole repo):
  - `claim_sets`: **zero hits anywhere** outside its own `CREATE TABLE` in
    `stores/postgres/migrations/0026_identity_model.sql`. Live DB:
    `SELECT COUNT(*) = 0`; `pg_stat_user_tables`: `n_tup_ins=0, n_tup_upd=0,
    n_tup_del=0` — zero writes in this database's entire lifetime, not just
    currently-empty.
  - `entity_knowledge_refusals`: a **VIEW** (`stores/postgres/migrations/
    0022_entity_admission_decisions.sql`), `SELECT ... FROM entity_admission_decisions
    WHERE outcome='REJECT'` — the audit's "226,566 rows" was the view's live COMPUTED
    result over the real, actively-written `entity_admission_decisions` table, not
    226,566 rows of its own storage. Zero storage cost either way; nothing to retire.
  - `knowledge_tier_facts`: a **VIEW** (`stores/postgres/migrations/
    0021_knowledge_tiers.sql`) implementing the documented T2/T1 knowledge-tier
    contract over `fact_admission_decisions`. Referenced by
    `tests/contracts/test_admission_boundary.py` (asserts
    `"knowledge_tier_facts" in src`), `docs/SEMANTIC_CONTRACTS.md`,
    `docs/WAY_AHEAD.md`. Definitively NOT dead — the audit's RETIRE_CANDIDATE verdict
    for this one was a false positive, now fixed at the root cause.
  - `medic_deadlock_probe`: created and used ENTIRELY inside
    `tests/determinism/test_medic.py` (`CREATE TABLE IF NOT EXISTS` in the test body,
    not a migration) as a deadlock-handling test fixture. `pg_stat_user_tables`:
    `seq_scan=131, idx_scan=115` — actively exercised (by this session's own repeated
    test runs). Not production legacy at all; test infrastructure that happens to
    leave an empty table in the schema between runs.
- **Live audit re-run after the fix** (`scripts/audit_polymath.py --no-spend`):
  state-level RETIRE_CANDIDATE rows dropped from 4 to 1. `entity_knowledge_refusals`
  and `knowledge_tier_facts` no longer appear at all (correctly excluded as views).
  `medic_deadlock_probe` reclassified `RETIRE_CANDIDATE` → `LEGACY_REQUIRED` with
  `static_readers` correctly naming `tests/determinism/test_medic.py`. `claim_sets`
  remains the sole, now doubly-confirmed `RETIRE_CANDIDATE`.
- **New tests: 2 passed**, run against this repo's actual current content (not
  mocked) — `tests/determinism/test_conformance_state_census.py`. Existing
  `test_conformance_agnostic.py`: 12 passed, unaffected.
- Guards: `agent_preflight` ok · `repo_guard` ok · `wiki_worm --check` ok.
- Fence: `shared/polymath_shared/conformance/{discovery,evidence}.py` are inside the
  HASH-FENCE-V2 fingerprinted dirs — 0 claimable/leased tickets at edit time; a
  controlled `boot_polymath.sh`-equivalent bounce follows this commit. The
  `conformance` PACKAGE does have one live production import
  (`workers/workers/doc_parent_map_stage_worker.py` imports
  `polymath_shared.conformance.attempts.attempt_context`) — but `discovery.py` and
  `evidence.py`, the two files actually edited here, are not: `rg -n
  "conformance\.(discovery|evidence)"` across `workers/ control/ orchestrator/`
  returns nothing, and `attempts.py` itself does not import either sibling module, so
  there is no transitive path either. No production behavior is affected by this
  change.

## Rejected claims

- **"claim_sets should just be dropped now — the proof is complete."** REJECTED —
  correct that the proof is as complete as static+runtime evidence can make it
  (0 references anywhere, 0 writes in the database's lifetime), but DELETE STATE/
  SCHEMA is an explicit owner-authorization gate under this execution authority
  regardless of proof strength ("destructive production data/schema deletion or
  mutation"). Documented as ready-for-approval, not executed.
- **"The docs/ exclusion should stay even though tests/ goes."** REJECTED for
  consistency with the function's own stated philosophy — a stale doc mention is a
  weaker signal than a contract-test assertion, but the function's own docstring
  treats over-counting as strictly safe ("only DELAYS a retirement"); there is no
  principled reason to keep one blind spot while fixing the other when the stated
  design tolerates the false-positive cost either way.
- **"medic_deadlock_probe's empty leftover table is itself a bug worth fixing."**
  REJECTED as out of scope for this slice — it is a real, minor test-hygiene
  observation (the test never drops its own scratch table), but fixing
  `test_medic.py`'s fixture teardown is unrelated to the audit-tool correctness bug
  this slice targets, and touching a working, currently-passing test for a cosmetic
  schema-tidiness reason is not worth the risk here.

## Open contract gaps

- `claim_sets` deletion itself remains owner-gated, fully documented and ready for a
  go/no-go decision whenever the owner wants it.
- The remaining 12 RETIRE_CANDIDATE rows from the corrected audit (all disabled
  provider LANES in `config/cloud_providers.json`, not state tables) were not
  individually re-investigated this slice — they are config entries, not code/schema,
  and the audit's own note ("disabled in config; superseded unless a rollback needs
  it") is not clearly a safe-to-delete verdict without checking each one's specific
  rollback relevance; left for a future slice if the owner wants config cleanup.
