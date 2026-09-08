---
owner: @king
last_reviewed: 2026-09-07
last_touched: 2026-09-07
status: accepted
---

# SESSION CONTINUATION — start here (2026-09-07T1828)

This is the newest handoff snapshot. The **living** bootstrap is still
`docs/wiki/plans/CONTINUITY-REPORT.md` (read it too); this folder snapshots the
state at HEAD and hands you the exact next move.

## The answers a fresh session needs, without chat history

- **What are we building?** A two-scale document semantic index: a global document
  profile (Scale A, live) + one compact deterministic-then-mapped routing signature
  per parent (Scale B — the parent MAP), plus a deterministic Vocabulary Bridge.
  Retrieval becomes document → parent map → child evidence. Plan of record:
  `docs/wiki/plans/DOCUMENT-SEMANTIC-INDEX-V1-PLAN.md`. Why this way: `BE-AWARE.md`
  (this folder).
- **Current HEAD:** `4fc931a` on `architecture/evidence-first-v5`; `main ==
  origin/main == this branch == ../polymath-v4-main == 4fc931a`. Worktree clean.
- **What landed:** S0–S4 + a corrective checkpoint + the Groq routing policy/decision
  core + a live map-contract canary. Registers 11.129–11.136. See WORK-CONDUCTED.md.
- **What was verified:** four CI checks green on every commit; guards green;
  migration 0054 idempotent on dev Postgres; the map contract proven LIVE on real
  documents (22/22 and 11/11 mapped, injection resisted).
- **What remains / blocked / dependencies:** UNFINISHED-WORK.md + DEPENDENCY-MAP.md
  (this folder). Nothing is code-blocked; the remaining slices are owner-gated for
  LLM spend / fleet wiring, and the FINAL retrieval plan is blocked on a missing file.
- **What must NOT be changed casually:** the chunker (frozen this phase), durable
  identity (`chunk_id`, never `chunk_index`), Postgres-as-truth vs
  Qdrant/Neo4j-as-projection, the summaries/`parent_enrichment` legacy readers (still
  live), and the Groq account-shared-budget invariant. See BE-AWARE.md §10–§11.

## Exact next executable slice: S5 — profile vNext + fingerprint

Buildable now (the QUALITY canary spends LLM quota → owner-gated for the
measurement only). Build the adaptive 500–2,000-token `DocumentFingerprint` as a
**new** `shared/polymath_shared/document_profile/fingerprint.py` (leave the live
profile compiler untouched until S8), with the six surfaces (identity, structure,
framing, coverage — largest share, synthesis, vocabulary), a full-structure scan
(no first-400 bias), plus the research-index tags. Unit-test it like S1–S3.

## Read these first (in this order)

```
AGENTS.md
docs/wiki/plans/CONTINUITY-REPORT.md
docs/wiki/reports/2026-09-07T1828/BE-AWARE.md        (this folder — how + why)
docs/wiki/reports/2026-09-07T1828/DEPENDENCY-MAP.md  (recursive edges)
docs/wiki/plans/DOCUMENT-SEMANTIC-INDEX-V1-PLAN.md §5-§6, §31, §40 (S5)
docs/wiki/plans/PLAN-AUTHORITY-REGISTER.md rows 11.125-11.136
shared/polymath_shared/document_profile/{context,compiler,prompt,parent_skeleton,map_compiler,map_batches,groq_router}.py
docs/wiki/plans/GROQ-ROUTING-POLICY-V1.md
```

## Run these first (establish truth + prove current state)

```bash
cd /Users/king/Documents/polymath-rebuild/polymath-v4
git status && git rev-parse --short HEAD          # expect clean, 4fc931a (or a later ff)
.venv/bin/python scripts/agent_preflight.py       # needs py>=3.11 (tomllib); mac python3 is 3.9
.venv/bin/python scripts/repo_guard.py
.venv/bin/python scripts/wiki_worm.py --check
# the map-production core (pure, no DB, no network):
.venv/bin/python -m pytest tests/determinism/test_parent_skeleton.py \
  tests/determinism/test_parent_map_compiler.py tests/determinism/test_map_batches.py \
  tests/determinism/test_groq_router.py -q          # ~55 pass, 1 skip (real-fixture)
# S4 durability (needs dev Postgres; skips cleanly without it):
set -a; . ./.env; set +a
.venv/bin/python -m pytest tests/determinism/test_document_parent_maps_store.py -q  # 5 pass
```

## How to continue without breaking migration safety

1. Never key durable identity on `chunk_index`; the S8/S9 parent-load query MUST
   select `chunk_id`.
2. Never make `doc_profile` blocking (QUERY_READY) until every corpus is backfilled
   (S14) AND the owner says go (S15) — flipping early makes unprofiled corpora
   un-serveable.
3. Never retire summaries / `parent_enrichment` / the §13 parent-semantic compiler —
   they are still read; S16 only MEASURES them for retirement.
4. Never wire Groq mini lanes or backfill at scale without S7's durable shared
   budget — concurrent workers would oversubscribe one account's 250 RPD.
5. Land through the branch → four green checks → ff `main` workflow; every new file
   gets a `scripts/scaffold_polymath_v4.py::TREE` line in the same commit.

## Read-only finding worth acting on (retrieval-side, NOT the chunker)

Child chunks are correctly sized (median ~108–140 tok, near the 128 design). The
only over-granular cohort is `region_role='stub'` OCR noise (~7.5% of children:
page numbers, running headers, "[No extractable text]", OCR-garbled lines,
concentrated in scanned PDFs). Cheapest fix is adding `stub` to the retrieval
`NOISY_ROLES` set (register 11.123 mechanism) — a one-line retrieval change, NOT a
chunker change. Do not modify the chunker.
