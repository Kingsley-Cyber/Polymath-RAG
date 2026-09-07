---
title: "POLYMATH NEXT PHASE — CODING AGENT START HERE"
date: 2026-09-07
status: "bootstrap hook"
last_reviewed: 2026-09-07
plan_of_record: "docs/wiki/plans/DOCUMENT-SEMANTIC-INDEX-V1-PLAN.md"
---

# CODING AGENT START HERE

You are continuing Polymath v4 document-semantic-index work.

Do not code from chat history.

## 1. Bootstrap repository truth

Read:

```text
AGENTS.md
docs/wiki/plans/CONTINUITY-REPORT.md
newest docs/wiki/reports/<date>/README.md
docs/wiki/reports/<date>/BE_AWARE.md
docs/wiki/reports/<date>/UNFINISHED_WORK.md
docs/wiki/reports/<date>/DEPENDENCY_MAP.md
docs/wiki/plans/PLAN-AUTHORITY-REGISTER.md
two newest docs/wiki/work-log entries
```

Then verify:

```bash
git status
git branch --show-current
git rev-parse HEAD

python3 scripts/agent_preflight.py
python3 scripts/repo_guard.py
python3 scripts/wiki_worm.py --check
```

Do not discard unknown dirty-worktree changes.

## 2. Read the authoritative next-phase plan

Read in full:

```text
docs/wiki/plans/DOCUMENT-SEMANTIC-INDEX-V1-PLAN.md
```

(Installed into the repository under `docs/wiki/plans/` on 2026-09-07 as slice S0;
the original Downloads artifact was `POLYMATH_NEXT_PHASE_IMPLEMENTATION_PLAN_FINAL_2026-09-07.md`.)

Do not continue from the older V1–V6 standalone design artifacts except for historical clarification.

## 3. Goal in one paragraph

Build a two-scale semantic index:

```text
ONE global document semantic profile
+
ONE compact semantic MAP per eligible parent
```

The global call uses a 500–2,000-token deterministic fingerprint and Groq Compound initially. It should also map as many parents as the measured completion/token envelope safely permits. Only overflow parents use token-packed Compound Mini calls. Every parent map is durable, partial output is preserved, and only unresolved aliases are retried. Postgres proves completeness; Qdrant is projection. Retrieval becomes document -> parent map -> child evidence, with a deterministic Vocabulary Bridge that lets limited user vocabulary discover specialist corpus terminology. Do not build Wildcard yet.

## 4. Measured Compound Mini facts you must not overwrite with guesses

Frozen 40-parent stress test:

```text
40 / 40 aliases
0 missing
0 invented
0 duplicate

prompt-injection resistant

CVE-2026-0217 preserved
AU21 preserved
021 preserved in signature

input:
5,428 tokens
135.7 tokens / parent

billed completion:
3,480 tokens
87.0 tokens / parent

visible MAP output:
~1,165 tokens
~29 tokens / parent

latency:
8.1 s

finish_reason:
stop

tools:
disabled
```

For capacity planning:

```text
use 87 billed completion tokens / parent
not 29 visible
```

40 is proven.

~60 parents/request is the first mapping-only target to canary.

Do not hard-code 60 forever.

## 5. Critical invariants

```text
DO NOT make one LLM call per parent.

DO NOT use MAP hooks as exact-identifier authority.
Python extracts exact identifiers separately.

DO NOT rerun successful parent MAP lines after partial output.

DO NOT hold one long DB transaction across many API calls.

DO NOT rerun semantic APIs because Qdrant failed.

DO NOT hard-filter all evidence to profile-nominated documents.

DO NOT build Wildcard yet.

DO NOT change chunk IDs or existing graph identity.

DO NOT use tools/web/code during document indexing.
```

## 6. Implementation order

Execute only in dependency order:

```text
S0 plan/hook admission
S1 deterministic ParentSkeleton
S2 parent MAP compiler
S3 token packer/capacity model
S4 SQL batch/map durability
S5 global fingerprint/profile VNext
S6 combined one-call canary
S7 shared Groq rate budget
S8 refactor doc_profile
S9 doc_parent_map worker
S10 project_doc_profile
S11 shadow verifier
S12 runtime profile/map lane
S13 Vocabulary Bridge
S14 quality gate/backfill
S15 QUERY_READY promotion — owner go
S16 old parent semantic ablation
```

Before each slice:

```text
re-read that slice in the master plan
admit it in the work-log
identify owner / contract / tests / rollback
```

## 7. Completion behavior

At session end:

```text
tests
repo guards
git diff/status
commit complete slices
update work-log
update PLAN-AUTHORITY-REGISTER
update CONTINUITY-REPORT
update current dated handoff/dependencies
leave clean continuation state
```

A coding agent that cannot state:

```text
what is complete
what is measured
what is unresolved
what the next dependency is
```

has not completed the handoff.
