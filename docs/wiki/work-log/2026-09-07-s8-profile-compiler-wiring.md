---
title: "WORK LOG — S8 profile/compiler wiring (reversible vNext flag)"
change_id: DOCUMENT-SEMANTIC-INDEX-V1-S8-WIRING
date: 2026-09-07
owner: worker + shared (live doc_profile stage; compiler extension)
last_reviewed: 2026-09-07
last_touched: 2026-09-07
status: complete
register: 11.147
package: shared/polymath_shared/document_profile/compiler.py, workers/workers/doc_profile_worker.py, tests/determinism/test_document_profile_stage.py, tests/determinism/test_document_profile_compiler.py
architecture_impact: "S8 crosses the profile/compiler wiring gate REVERSIBLY. (1) The compiler now recognizes the 7 vNext research-index tags (LATENT-PATTERN/ANCHOR/RECALLQ/TENSION/BRIDGE/INVERSION/BOUNDARY) additively — a v3.x profile that never emits them compiles byte-identically (no contract drift; COMPILER_VERSION unchanged). (2) The doc_profile worker gains a vNext path behind the rollback switch POLYMATH_DOC_PROFILE_VNEXT (plan §28 profile_generation): when set it builds the fingerprint (budget 500) + profile_prompt_vnext and DROPS the document_summaries.major_concepts read (GAP-04); default OFF = byte-identical live path (contract() identical), so flipping back is a config change, never a re-ingest. Base surfaces still project unchanged; research tags land in the artifact (not yet projected). No schema/chunker change."
---

# WORK LOG — S8 profile/compiler wiring

## Contract

Owner /goal (2026-09-07): after the S5 canary, "continue into S8 profile/compiler
wiring." Plan §S8 / §18 / GAP-04. Wire the vNext fingerprint + profile prompt +
research-tag parsing into live profile generation — REVERSIBLY (plan §28 mandates a
`profile_generation` rollback switch) and without a blind cutover or mass-backfill.

Owner: `worker` + `shared`. Public contract: `compiler` recognizes the research tags;
`doc_profile_worker` honours `POLYMATH_DOC_PROFILE_VNEXT`. Rollback: unset the env var
(the flag-off path is byte-identical). Verifier: `test_document_profile_stage.py`
(both paths) + `test_document_profile_compiler.py` (research tags + backward-compat).

OUT of scope (further gates): flipping the flag ON in production (the owner's
controlled cutover, after a self-retrieval qualification); projecting the research-tag
surfaces to a new Qdrant collection; the combined global-profile+map fast path.

## Changes

- **`compiler.py`** (additive, backward-compatible): 7 research tags added to
  `TAG_ALIASES` (canonical `LATENTPATTERN` — hyphen-free internal token so `normalize`'s
  canonical rewrite does not re-break the `_TAG_LINE` hyphen-split; the prompt label
  stays `LATENT-PATTERN`), 7 `Record` list fields, `_LIST_ATTR` entries, the dedup loop,
  and `semantic_artifact` (research fields emitted ONLY when present → v3.x artifacts
  byte-identical). A line-start `LATENT-PATTERN` → `LATENTPATTERN` normalization handles
  the internal hyphen. Research tags are never required for validity, never capped, never
  scored (not in `TARGET_COUNTS`). `COMPILER_VERSION` unchanged (superset for v3.x inputs).
- **`doc_profile_worker.py`**: `_vnext_enabled()` (the `POLYMATH_DOC_PROFILE_VNEXT`
  rollback switch); `contract()` returns a DISTINCT hash when on (vNext prompt/builder/
  budget markers), identical when off; `process_event` branches — vNext builds the
  fingerprint + `profile_prompt_vnext` and passes `want_terms=False` (GAP-04: no
  `major_concepts` read); the profile_record records the active versions + `vnext`.
- **tests**: a vNext stage pin (fingerprint prompt used, research tags in the artifact,
  base surfaces project) + a compiler research-tag + backward-compat pin.

## Proof

```
set -a; . ./.env; set +a
.venv/bin/python -m pytest tests/determinism/test_document_profile_stage.py -q          -> 10 passed (9 legacy + 1 vNext)
.venv/bin/python -m pytest tests/determinism/test_document_profile_compiler.py -q       -> 11 passed
.venv/bin/python -m pytest tests/determinism/test_document_profile_{context,projection}.py \
   tests/determinism/test_{document_fingerprint,profile_prompt_vnext,compiler_context}.py -q  -> all pass (60 total)
.venv/bin/python scripts/repo_guard.py / agent_preflight.py -> ok
```

`contract()` OFF vs ON differ (`3d8bfeef…` vs `6138c084…`); flag-OFF is byte-identical
to the pre-S8 live stage. The vNext stage pin runs the full path against Postgres with a
fake pool/embedder/Qdrant: fingerprint prompt used, `vnext=True`,
`prompt_version=doc-profile-vnext-v1`, the artifact carries `latent_pattern`/`anchor`/
`boundary`, and the base surfaces still project. The S5 canary (11.146) already proved
the vNext generation LIVE on `groq/compound`.

## Rejected claims

- **Not** a live cutover: the flag defaults OFF; production profile generation is
  unchanged until the owner sets `POLYMATH_DOC_PROFILE_VNEXT` (a reversible config change,
  after a self-retrieval qualification). This is the plan §28 rollback switch, not
  dormant infra — the path is wired, canary-proven, and one env var from live.
- **Not** a contract drift for existing corpora: flag-OFF `contract()` and the compiled
  artifact are byte-identical; existing profiles are untouched.
- **Not** a projection of the research surfaces: they are in the artifact only; projecting
  them (a new collection) is a later gated step.

## Open contract gaps

- Flipping the flag ON for production is the owner's controlled cutover; it should be
  preceded by a self-retrieval qualification of vNext-generated profiles vs the current
  gate (top-1 85.8%) — project + query, the S8/projection step.
- The research-tag surfaces are not yet projected to Qdrant (artifact-only routing hints).
- GAP-04's reader is now SKIPPED on the vNext path; the legacy `major_concepts` writer
  and its other readers remain (retirement is S15-S18, after the census classification).
