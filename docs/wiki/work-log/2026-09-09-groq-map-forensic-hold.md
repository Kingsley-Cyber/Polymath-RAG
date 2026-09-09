---
title: "WORK LOG — Cinema Parent-MAP backfill STOPPED; Groq RPD-exhaustion DISPUTED; forensic-audit handoff"
change_id: GROQ-MAP-FORENSIC-HOLD-V1
date: 2026-09-09
owner: governance (continuity/handoff; no code behavior changed)
last_reviewed: 2026-09-09
last_touched: 2026-09-09
status: complete
register: 11.184
package: docs/wiki/reports/2026-09-08/START-HERE.md, docs/wiki/reports/2026-09-08/GROQ-FORENSIC-AUDIT.md, docs/wiki/reports/2026-09-08/CONTINUATION_REPORT.md, docs/wiki/reports/2026-09-08/BE_AWARE.md, docs/wiki/reports/2026-09-08/UNFINISHED_WORK.md, docs/wiki/reports/2026-09-08/DEPENDENCY_MAP.md, docs/wiki/plans/RETRIEVAL-MIGRATION-DEPENDENCY-V1.md, docs/wiki/plans/CONTINUITY-REPORT.md, docs/wiki/plans/PLAN-AUTHORITY-REGISTER.md, AGENTS.md
architecture_impact: "None. Continuity/handoff only — no code, schema, contract, or default changed. Records an owner directive (2026-09-08/09) that STOPS the cinema parent-MAP backfill and DISPUTES the prior session's conclusion that a +0-parent / 0-errored_docs pass proved the six Groq accounts had exhausted daily RPD. That conclusion is downgraded from proven provider fact to unverified inference in the migration ledger (S12), CONTINUITY-REPORT, and PLAN-AUTHORITY-REGISTER (11.178 corrected + new 11.184). A forensic-audit handoff is installed under docs/wiki/reports/2026-09-08/ for a zero-context next session. Frozen architecture reaffirmed: ParentSkeleton -> plaintext MAP DSL -> deterministic map_compiler -> durable maps -> projection; no JSON object mode / function-calling for parent MAPs; no compiler bypass; chunker + parent boundaries untouched; strict parent identity preserved. No provider quota spent during this handoff."
---

> **Ledger rows:** `RETRIEVAL-MIGRATION-DEPENDENCY-V1.md` **S12** (forensic hold) + `PLAN-AUTHORITY-REGISTER.md` **11.184**. The dated handoff `docs/wiki/reports/2026-09-08/START-HERE.md` is the zero-context entry point.

## Contract

Bound to an owner directive (2026-09-08/09): **STOP** the cinema parent-MAP backfill and prepare a
zero-context forensic-audit handoff. This is continuity/handoff only — **no code, schema, contract, or
default is changed**. The frozen architecture is reaffirmed and must hold for the next session:
`ParentSkeleton → plaintext MAP DSL → deterministic map_compiler → durable parent maps → projection`;
**no** JSON object mode / schema / function-calling for parent MAPs; **no** compiler bypass; the
**chunker and parent boundaries are untouched**; strict parent identity preserved; no autonomous
QUERY_READY flip / legacy retirement / cutover / deletion. No provider quota is spent during this
handoff.

## Changes

- **Cinema parent-MAP backfill STOPPED** (a running backfill this session was killed; no lingering
  process). The next session is a **forensic audit**, not a backfill and not a code-patch session.
- **Migration ledger** `RETRIEVAL-MIGRATION-DEPENDENCY-V1.md` **S12**: the "capacity-paused" / four-part
  "capacity gate" / "purely CAPACITY-gated" wording rewritten to a four-part **FORENSIC HOLD**; the
  RPD-exhaustion conclusion downgraded to disputed inference; historical narrative (+703 advance, both
  backfill fixes) preserved.
- **CONTINUITY-REPORT.md** (lines ~45, ~106): the two "purely capacity-gated / RPD, multi-session /
  resume ..." assertions corrected to the forensic hold; coverage refreshed to ≈1254/11,993.
- **PLAN-AUTHORITY-REGISTER.md**: 11.178's "purely capacity-gated" outcome corrected + new **11.184**
  recording the forensic hold as a status correction.
- **Dated handoff** `docs/wiki/reports/2026-09-08/`: added `START-HERE.md`, `GROQ-FORENSIC-AUDIT.md`,
  `CONTINUATION_REPORT.md`, `BE_AWARE.md`, `UNFINISHED_WORK.md`, `DEPENDENCY_MAP.md`; a FORENSIC-HOLD
  banner prepended to the existing `README.md`.
- **AGENTS.md** "Current Repository State" now points item `00` at the 2026-09-08 forensic-hold handoff as
  the newest.

## Proof

- Guards green with `.venv/bin/python`: `agent_preflight` ok, `repo_guard` ok, `wiki_worm --check` ok
  (after declaring the new files in `scaffold_polymath_v4.py` TREE and using the required work-log
  sections).
- Cinema coverage verified live at handoff: `document_parent_maps` active distinct parents ≈**1254** /
  `parent_summaries` active distinct parents **11,993** (**≈1254/11,993**, ~9.9%).
- No provider quota spent during the handoff (the stopped re-run only re-projected already-mapped docs
  before it was killed).

## Rejected claims

- **REJECTED as proven fact:** "a `+0`-parent / `0`-errored_docs backfill pass proved the six Groq
  accounts had exhausted daily RPD." Downgraded to unverified inference — never reconciled against Groq
  rate-limit headers, limiter admission (`LIMITER_REFUSED` ≠ provider consumption), HTTP dispatch counts,
  `MappingOutcome.errors`, retry behavior, compiler yield, or persisted maps. A `+0/0-errors` pass is
  equally consistent with local limiter refusal, hidden compiler/mapping failures, or lane accounting
  that counts endpoint selections rather than HTTP dispatches.
- **NOT assumed:** the six-account × daily-RPD topology (`6×250` / `6×500`) — must be established from
  provider header truth.

## Open contract gaps

- **F1 — Groq Parent-MAP forensic audit** is the next session's principal task. Targets A–I
  (`docs/wiki/reports/2026-09-08/GROQ-FORENSIC-AUDIT.md`): request-limit headers vs RPM bucket;
  success-response header preservation; local `day_count` charge point; `LIMITER_REFUSED` = zero
  consumption; hidden `MappingOutcome.errors` while `errored_docs=0`; retry waste under `max_attempts=3`;
  `lane_counter` selections vs HTTP dispatches; account/family capacity topology; MAP batch reliability
  15/20/30/40/60 under the DSL + compiler. Acceptance gate → bounded canary → owner review → backfill.
- **UNKNOWN (next session to verify):** exact Groq per-account daily request quota; whether success
  responses preserve rate-limit headers to the limiter; whether `MappingOutcome.errors` can be non-zero
  while `errored_docs=0` — an incidental `mapped=N/N` + `complete=False` discrepancy (e.g. Anatomy for
  Sculptors 71/71) was observed on the stopped re-run but not audited.
- Coverage-gated downstream (U-COV, D-10, D-11, P5 doc-branch, P7 §39) stays blocked until F1's gate +
  bounded canary + owner-approved backfill. Legacy retirement (S13–S18) remains owner-gated.
