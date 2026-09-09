---
owner: "@king"
last_reviewed: 2026-09-09
status: FORENSIC HOLD — session handoff (zero-context entry point)
architecture_impact: none (continuity/handoff only; no code behavior changed)
supersedes_for_operating_state: docs/wiki/reports/2026-09-08/README.md
---

# START HERE — Groq Parent-MAP Forensic Audit handoff (2026-09-08/09)

You are a **fresh session with zero context** from the conversation that produced this file.
Trust the repository, not chat history. This file is the entry point for the CURRENT operating
state. The sibling `README.md` is the earlier routing/synthesis phase snapshot — still valid for
that phase, but the **operating state below overrides it**.

## The one thing that matters right now

```text
CINEMA PARENT-MAP BACKFILL = STOPPED (owner directive 2026-09-08/09)
```

The previous session concluded that a backfill pass returning **+0 new parents / 0 errored_docs**
PROVED the six Groq accounts had exhausted their **daily RPD**. **That conclusion is DISPUTED.**
It was never reconciled end-to-end against provider truth. Your job is a **forensic audit**, not a
backfill and not a code patch.

- Cinema parent-MAP coverage: **≈1254 / 11,993** parents (verify live — query below).
- Do **NOT** resume the backfill because a quota window reset.
- Do **NOT** spend provider quota merely to gather evidence.
- Do **NOT** start with a code patch. Reconstruct the evidence chain first.

Full directive + investigation targets + acceptance gate: **`GROQ-FORENSIC-AUDIT.md`** (next to this).

## Your first-run sequence (do these in order)

1. Read `AGENTS.md` (§0 Mandatory Bootstrap).
2. Read this file, then `GROQ-FORENSIC-AUDIT.md`, `CONTINUATION_REPORT.md`, `BE_AWARE.md`,
   `UNFINISHED_WORK.md`, `DEPENDENCY_MAP.md` (all in this folder).
3. Read `docs/wiki/plans/CONTINUITY-REPORT.md` (living bootstrap).
4. Read `docs/wiki/plans/RETRIEVAL-MIGRATION-DEPENDENCY-V1.md` — **S12 row** (the forensic hold) + the
   retirement gates S13–S18.
5. Read the Groq routing authority: register `11.134` (GROQ-ROUTING-POLICY-V1), `11.177`
   (BACKFILL-SPREAD-V1), `11.178` (map-batches-v2), and `11.184` (this FORENSIC HOLD).
6. Verify repo truth:
   ```bash
   git status --short && git branch --show-current && git rev-parse HEAD
   ```
7. Run the guards with the repo interpreter (`.venv/bin/python`; the Mac `python3` is 3.9, no `tomllib`):
   ```bash
   PYTHONPATH=shared .venv/bin/python scripts/agent_preflight.py
   PYTHONPATH=shared .venv/bin/python scripts/repo_guard.py
   PYTHONPATH=shared .venv/bin/python scripts/wiki_worm.py --check
   ```
8. Confirm cinema backfill is still STOPPED (no `parent_map_backfill` process; do not start one):
   ```bash
   pgrep -fl parent_map_backfill || echo "stopped (good)"
   ```
9. Trace the actual Parent-MAP request path end to end, reading code (not prose):
   `scripts/parent_map_backfill.py` → `workers/workers/doc_parent_map_worker.py` →
   `shared/polymath_shared/document_profile/map_batches.py` / `map_prompt.py` / `map_compiler.py` →
   `shared/polymath_shared/llm_extraction/client.py` (`complete_one`) →
   `shared/polymath_shared/llm_extraction/limiter.py` (AIMD, RPD, headers) →
   `shared/polymath_shared/llm_extraction/state_store.py` (persisted limiter state) →
   persistence (`document_parent_maps`).
10. **Begin the forensic audit from evidence.** Produce the initial conservation-chain evidence table
    (`GROQ-FORENSIC-AUDIT.md` §Acceptance gate) BEFORE proposing any change.

```text
DO NOT START WITH A CODE PATCH.
```

## Verify coverage live (read-only, no provider spend)

```bash
PYTHONPATH=shared .venv/bin/python - <<'PY'
from polymath_shared import db
with db.tx() as c:
    tot=c.execute("SELECT COUNT(DISTINCT parent_id) FROM parent_summaries WHERE corpus_id='cinema' AND superseded_at IS NULL").fetchone()[0]
    cov=c.execute("SELECT COUNT(DISTINCT parent_id) FROM document_parent_maps WHERE corpus_id='cinema' AND active").fetchone()[0]
    print(f"cinema parent-MAP coverage: {cov}/{tot} = {100.0*cov/tot:.1f}%")
PY
```

## Cold-read answers (so you don't have to guess history)

- **Current repository state:** branch `architecture/evidence-first-v5`, `origin/main` == HEAD (see
  `git rev-parse HEAD`); worktree clean at handoff. Guards green. Retrieval/routing/synthesis phase
  (P0–P13) is largely qualified live; the open work is data-coverage-gated and now under forensic hold.
- **Why is cinema stopped?** Owner directive. The RPD-exhaustion conclusion is disputed; provider quota
  consumption was never reconciled end-to-end. No resume until the audit passes its gate.
- **What is disputed?** "+0 parents / 0 errored_docs ⇒ six Groq accounts exhausted daily RPD."
- **What must I investigate?** See `GROQ-FORENSIC-AUDIT.md` targets A–I (headers, response headers, local
  RPD charge point, `LIMITER_REFUSED`, hidden `MappingOutcome.errors`, retry waste, lane accounting,
  account/family topology, MAP batch reliability 15/20/30/40/60).
- **Which files are involved?** See `CONTINUATION_REPORT.md` §Code surfaces.
- **What architecture cannot I change?** ParentSkeleton → plaintext MAP DSL → deterministic
  `map_compiler` → durable parent maps → projection. No JSON object mode, no function-calling for MAPs,
  no compiler bypass, no chunker/parent-boundary changes, no weakening strict parent identity. See
  `BE_AWARE.md`.
- **What constitutes provider quota consumption?** ONLY an actual HTTP request dispatched to Groq that the
  provider accepted/counted. A local `LIMITER_REFUSED` (limiter did not admit) is ZERO provider
  consumption and must never be recorded as such.
- **What is the acceptance gate?** `GROQ-FORENSIC-AUDIT.md` §Acceptance gate (provider RPD truth
  observable + reconciled; refusal/error accounting correct; retry waste quantified; batch sizes
  benchmarked) → bounded canary → owner review.
- **Exact first action:** step 1 above (read `AGENTS.md`), then build the evidence table. Not a patch.
- **What am I forbidden from doing?** Resuming cinema backfill, waiting for/relying on a quota reset,
  spending quota to gather evidence, JSON mode, compiler bypass, chunker edits, autonomous QUERY_READY
  flip, disabling legacy producers/readers, deleting legacy state, cutover.
