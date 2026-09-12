---
title: "WORK LOG — root-caused and fixed 2 of 3 pre-existing test failures (both a recurring .env-operational-override-vs-test-isolation pattern); root-caused the 3rd precisely and confirmed it requires live production DATA mutation, a genuine §1 owner gate, not a code bug"
change_id: PRE-EXISTING-TEST-FAILURE-ROOT-CAUSE-AND-FIXES-V1
date: 2026-09-12
owner: king
last_reviewed: 2026-09-12
status: complete
register: 11.226
architecture_impact: "two narrow test-only fixes (zero product code changed): pin an ambient .env-configured operational override explicitly in each affected test, matching an already-established pattern elsewhere in the same files. The third failure's root cause is fully traced but not acted on — fixing it means mutating live facts/entities rows, which is an explicit owner gate."
---

> Direct response to a Stop-hook rejection arguing that attributing 3 pre-existing test
> failures as "unrelated" was not the same as actually trying to fix what's fixable. This
> slice does that: investigates all 3 to genuine root cause rather than stopping at "not
> caused by my commits," and fixes the two that turn out to be safely, narrowly fixable.

## Contract

Requested outcome: for each of the 3 pre-existing failures named in 11.225's aggregate
run, determine genuine root cause (not just "unrelated to my diff") and fix whatever is
safely, narrowly fixable without touching frozen retrieval/extraction architecture or
mutating live production data without authorization.

- **Smallest acceptance:** each failure's root cause is traced to a specific mechanism;
  fixes are applied only where safe (test-only, zero product-code/data change); anything
  requiring data mutation or architecture change is named precisely, not hand-waved.
- **Verifier / rollback:** the fixed tests themselves, re-run repeatedly; both fixes are
  test-file-only edits, trivially revertible.

## Changes

### 1. `test_document_profile_stage.py::test_worker_writes_the_profile_and_projection_artifacts_with_the_receipt_chain` — FIXED

**Root cause, traced precisely**: `doc_profile_worker.py::process_event` branches on
`_vnext_enabled()` — reading `POLYMATH_DOC_PROFILE_VNEXT` from the environment. This
repo's `.env` ships `POLYMATH_DOC_PROFILE_VNEXT=1` (confirmed: an intentional, already-
sanctioned production toggle — the code's own docstring calls flipping it "a config
change, never a re-ingest"). This test exercises the STANDARD (non-vnext) path
specifically and asserts on its exact prompt shape (`"TITLE:\n..."`, `THEORY:` in the
system prompt) and `prompt_version == "doc-profile-v3.2"` — but never pins the env var
itself, so it silently inherited the ambient `1` and ran the VNEXT branch instead
(`fingerprint.py`'s `"IDENTITY:\n.../STRUCTURE:\n..."` format), failing every assertion
written for the other path. The SIBLING test two functions below
(`test_worker_vnext_path_uses_fingerprint_and_carries_research_tags`) already
demonstrates the correct pattern — it explicitly does
`monkeypatch.setenv("POLYMATH_DOC_PROFILE_VNEXT", "1")` for ITS OWN requirement; the
failing test needed the mirror-image `monkeypatch.delenv(..., raising=False)`.

**Fix**: added `monkeypatch.delenv("POLYMATH_DOC_PROFILE_VNEXT", raising=False)` as the
first line of the test body, with a comment naming exactly why. Zero product code
touched — `doc_profile_worker.py`, `prompt.py`, `context.py`, `fingerprint.py` are all
confirmed correct as-is (this session's earlier git-log cross-check already established
zero commits touched any of them).

**Proof**: `test_document_profile_stage.py` full file, 10/10 pass (was 9/10).

### 2. `test_chat_retrieval_v2.py::test_route_one_embedding_per_distinct_text_one_judge_call_and_lane_c_starts_before_the_embedding_returns` — FIXED

**Root cause, traced precisely, in two layers**:
- Re-running the test in ISOLATION (not the full suite) first got PAST its own timing
  assertion (`sparse_starts` before `embed_returned_at`) that had originally failed under
  the full suite's heavy concurrent load — confirming that specific line genuinely is
  load-sensitive, matching this session's own earlier documented finding ("Full
  determinism suite erratic stalls... isolated runs of the 'stuck' files passed
  instantly"). Not itself acted on further since it passed once load-isolated and is a
  pre-existing, load-dependent assertion unrelated to any code this session touched.
- The isolated run then failed at a DIFFERENT, fully deterministic assertion:
  `out["meta"]["deadlines"]["rerank_deadline_s"] == 8.0`, actual `12.0`. Traced to
  `candidate_engine.py:230`'s code default (`rerank_deadline_s: float = 8.0`, confirmed
  unchanged and correct) being overridden at runtime by `.env`'s
  `POLYMATH_CHAT_RERANK_DEADLINE_S=12` via `chat_retrieval.py`'s `_FLOAT_KNOBS`
  mechanism — the SAME recurring pattern as fix #1: a live, intentional, `.env`-
  configured operational tuning value (very plausibly a deliberate response to reranker
  latency, matching this session's own memory of reranker timeout/GPU-contention issues)
  that a test didn't isolate itself from.

**Fix**: passed an explicit `budget=ce.CandidateBudget(lane_deadline_s=3.0,
rerank_deadline_s=8.0)` into the harness's `run()` call, matching the EXACT pattern the
very next test in the same file
(`test_route_rerank_deadline_falls_back_to_fusion_order_with_a_receipt_and_never_hangs`)
already uses for the identical reason. Zero product code touched.

**Proof**: fixed test re-run 3x in isolation, all pass (confirming the timing assertion
is stable once not competing with the rest of the suite for CPU); full
`test_chat_retrieval_v2.py` file, 11/11 pass (was 10/11).

### 3. `test_fact_endpoint_eligibility.py::test_no_active_fact_has_a_pronoun_endpoint` — ROOT CAUSE FOUND, genuinely owner-gated, NOT fixed

**Root cause, traced precisely, NOT hand-waved**:
- `is_unresolved_pronoun()` (`entity_admission.py:58-83`) already correctly includes
  `"you"` in `CLOSED_CLASS_PRONOUNS` — the DETECTION logic has no gap.
- `_classify()` (`entity_admission.py:144`) already calls `is_unresolved_pronoun(surface)`
  as its VERY FIRST check, with an explicit historical comment: "Decided FIRST so no
  later branch... can promote it — three `they` entities had reached CORPUS_SCOPED that
  way" — proving this exact class of bug was already found and fixed once before, and
  the ADMISSION LOGIC is confirmed correct today.
- The live offending rows are NOT a code-path gap: `SELECT entity_id, created_at FROM
  entities WHERE normalized_surface='you'` returns multiple `mention_...`-prefixed rows,
  **all dated 2026-08-21** — three weeks before this session, predating whatever version
  of `_classify` currently enforces the pronoun-first rule (the test's own docstring
  independently corroborates this pattern: "The first version of this test hardcoded 12
  surfaces while CLOSED_CLASS_PRONOUNS held 29, so it reported GREEN while `i` and `it`
  were live fact endpoints" — i.e., this specific failure mode, stale pre-fix data never
  retroactively cleaned, has happened before in this project's history).

**Why this is NOT fixed here**: closing this gate for real means either (a) deleting or
re-classifying the stale `mention_...` rows and any `facts` referencing them, or (b) a
backfill re-running current `_classify` logic against historical entities and updating
`decision` accordingly — both are **mutations of live, already-serving production data**
(the `facts`/`entities` tables retrieval reads from), which is explicitly and
unambiguously one of the six named owner gates in §1: "destructive production data/
schema deletion or mutation." This is not a code bug requiring a fix — the code is
proven correct — it is stale historical DATA requiring an authorized cleanup/backfill,
structurally identical in kind (though not in table) to the already-identified
`claim_sets` situation: fully investigated, precisely understood, correctly left
untouched pending explicit authorization.

## Proof

- Both fixes verified individually and via their full containing test files (10/10 and
  11/11, both up from N-1/N).
- Third failure's root cause traced with FILE:SYMBOL:LINE precision (`entity_admission.py:58`,
  `:150`, live `entities` table query) rather than left at "confirmed unrelated" —
  the investigation itself is the deliverable here even though no code changed for it.
- Guards: `agent_preflight` ok · `repo_guard` ok · `wiki_worm --check` ok.
- **Full `tests/determinism/` suite re-run live after both fixes, real exit code**:
  2,161 tests, exit code 1, pytest's complete failure listing now names **exactly one**
  — `test_fact_endpoint_eligibility.py::test_no_active_fact_has_a_pronoun_endpoint`, the
  one confirmed to require live production data mutation. **2,160/2,161 passed** (up
  from 2,158/2,161 before this slice). Both fixes hold across the full suite, not just
  their own files.

## Rejected claims

- **"Add 'you' (again) to CLOSED_CLASS_PRONOUNS — maybe it's still missing somewhere."**
  REJECTED after direct inspection — it is already present and already the first check
  `_classify` runs. Re-adding it would be a no-op that doesn't address the actual
  historical-data root cause.
- **"Delete/reclassify the stale `mention_...` 'you' rows now — it's obviously a bug."**
  REJECTED — the CODE is not buggy; the DATA is stale, and mutating live production facts/
  entities tables without authorization is exactly the class of action §1 reserves for
  the owner, regardless of how confident the diagnosis is. Confidence in a diagnosis is
  not the same as authorization to act on production data.
- **"These are flaky/environmental, not worth fixing."** REJECTED for two of the three —
  investigation showed #1 and #2 were NOT flaky at all once traced to root cause; they
  were deterministic, safely fixable test-isolation gaps. Only part of #2 (the timing
  sub-assertion) was genuinely load-sensitive, and it passed cleanly once isolated from
  the rest of the suite's contention.

## Open contract gaps

- The stale `mention_...`-prefixed pronoun-surfaced entities (and any `facts` rows
  referencing them) remain live in production, `decision <> 'REJECT'`, until an owner-
  authorized data cleanup/backfill runs. Recommend, for the owner's future action: a
  bounded, `--dry-run`-by-default backfill script (matching this session's own
  established pattern) that re-runs current `_classify()` against existing `entities`
  rows and reports/corrects any `decision` that no longer matches current logic — the
  SAME shape as `scripts/backfill_extract_projection.py`/`backfill_document_chunk_summary.py`
  built this session, just scoped to entity re-classification instead. Not built here,
  since building it without owner sign-off on whether/when to run the mutating half
  would front-run the same authorization gate it's meant to respect.
