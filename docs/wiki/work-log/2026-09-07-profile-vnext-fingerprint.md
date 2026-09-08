---
title: "WORK LOG — profile vNext DocumentFingerprint (slice S5 / GAP-04)"
change_id: DOCUMENT-SEMANTIC-INDEX-V1-S5-FINGERPRINT
date: 2026-09-07
owner: shared (deterministic policy)
last_reviewed: 2026-09-07
last_touched: 2026-09-07
status: complete
register: 11.139
package: shared/polymath_shared/document_profile/fingerprint.py, tests/determinism/test_document_fingerprint.py, scripts/scaffold_polymath_v4.py
architecture_impact: "Adds the deterministic vNext global-profile INPUT (DocumentFingerprint) as a NEW pure shared/ module. It is the successor to context.py's lean-context-v1 block: adaptive 500-2000 tokens, six surfaces with coverage largest and full-structure (no first-400 bias), and a SELF-SUFFICIENT source-derived vocabulary that removes the vNext profile's NEED for document_summaries.major_concepts (closes GAP-04). Nothing consumes it yet: the live doc-profile prompt/compiler/worker are untouched (the switch is the S8 refactor, gated behind the 500/1000/1500/2000 quality canary). No worker/API/prompt/compiler/persistence/schema/chunker change; no provider spend."
---

# WORK LOG — profile vNext DocumentFingerprint

## Contract

Plan of record §5-§6/§18/§31 slice S5; migration authority
`RETRIEVAL-MIGRATION-DEPENDENCY-V1.md` §18 (global profile integration), §S7 (global
profile vNext independence), GAP-04 (`doc_profile` upstream legacy-summary input).
The exact next dependency in the /goal chain (contracts → durable state → **profile
vNext**).

Build the deterministic vNext fingerprint so the global profile:
1. is ADAPTIVE 500-2,000 tokens (2,000 a ceiling, never padding);
2. does a FULL-STRUCTURE scan with no first-400 bias (coverage across the whole doc);
3. is SELF-SUFFICIENT — derives its vocabulary from the source, so it no longer needs
   the legacy `document_summaries.major_concepts` input (GAP-04). This slice makes the
   reader-drop SAFE; the drop itself is the S8 worker refactor.

Owner: `shared`. Public contract: a NEW module `fingerprint.py`
(`build_fingerprint(document, parents, *, budget_tokens, allocation, extra_terms)` →
`DocumentFingerprint`). Rollback: delete the module + test (nothing imports it).
Verifier: `tests/determinism/test_document_fingerprint.py`.

Explicitly OUT of scope (locked per the T1828 handoff + migration law "additive
first"): the live `prompt.py` / `compiler.py` / `doc_profile_worker.py` are UNTOUCHED;
no research-tag OUTPUT wiring, no 500/1000/1500/2000 quality canary (spends provider
quota → owner-gated); no chunker/materializer change; no persistence/schema.

## Changes

- **`fingerprint.py`** (new, pure `shared/`):
  - `DocumentFingerprint` (six surfaces + `render_block` / `to_dict` / `input_hash` /
    `used_total`), `FINGERPRINT_BUILDER_VERSION = "fingerprint-v1"`.
  - `build_fingerprint(...)`: identity (title/frontmatter/format), structure
    (full-document heading stride, reuses `context.structure_lines` + `_stride_select`),
    framing (opening orientation of the first eligible parent — its
    `select_lead_excerpt`), synthesis (closing content of the last, tail-trimmed),
    **coverage** (even-stride salient excerpts across ALL eligible parents; computed
    LAST and given the budget the other five leave unused → largest surface AND total
    ≤ budget), vocabulary (`_select_vocabulary`: cross-parent TF·IDF key terms + exact
    identifiers, identifiers capped to half so they never crowd out concepts).
  - Reuses `context.py` (`est_tokens`/`clean_title`/`_trim_tokens`/`structure_lines`/
    `_stride_select`) and `parent_skeleton.py` (`normalize_whitespace`/
    `extract_identifiers`/`document_frequency`/`select_key_terms`/
    `select_salient_excerpt`/`select_lead_excerpt`/`_word_tokens`/`_heading_tokens`/
    `_normalize_heading`/`_source_position`) and `document_region.is_noisy` — no
    parallel infrastructure. Requires NO `chunk_id` (document-scale routing input;
    durable parent identity is the per-parent MAP's concern, repo S9).
  - Exports the vNext OUTPUT-contract vocabulary (`SOURCE_ANCHORED_FIELDS`,
    `ROUTING_INFERRED_FIELDS`, `RESEARCH_INDEX_TAGS`) as the single version-pinned
    source of truth for the future (owner-gated) prompt/compiler change.
- **test + scaffold**: 17 determinism pins; two TREE lines; this work-log.

## Proof

```
.venv/bin/python -m pytest tests/determinism/test_document_fingerprint.py -q   -> 17 passed
.venv/bin/python -m pytest tests/determinism/ -q                               -> (full suite; see run)
.venv/bin/python scripts/repo_guard.py        -> repo guard: ok
.venv/bin/python scripts/wiki_worm.py --check -> wiki: ok
.venv/bin/python scripts/agent_preflight.py   -> preflight: ok
```

Pins of note: `used_total <= budget` at every budget incl. clamp of 100/9000;
coverage is the max surface; the first, ~75% and LAST section markers all appear at
2,000 (a 1,000-parent doc reaches `ZZMARK999` in < 5 s) — the no-first-400-bias
proof; vocabulary is non-empty and source-derived with NO `extra_terms`/major_concepts
input (GAP-04); `CVE-2026-0217` / `021` / `AU21` survive into the vocabulary; a tiny
one-parent doc yields `used_total < 200` (adaptive, not padded); reordering the
parents yields an identical `to_dict` (order-independent); AST purity (only stdlib +
`polymath_shared`).

## Rejected claims

- **Not** a replacement for `context.py`: the live profile still uses
  `lean-context-v1`; the fingerprint is additive and consumed only when S8 switches
  the worker behind the qualification canary.
- **Not** the OUTPUT contract: the research-index tags are declared here as constants
  but NOT wired into the live prompt/compiler — that change needs the paid canary to
  qualify and is owner-gated.
- **Not** GAP-04's closure in the worker: the fingerprint removes the NEED for
  `major_concepts`; the actual read at `doc_profile_worker.py:102` is dropped in S8.
- **Not** a durable-identity consumer: the fingerprint keys nothing on `chunk_id`
  (§3 durable-identity rule is a per-parent-MAP concern, not a document input).

## Open contract gaps

- S5's quality gate ("global profile quality ≥ current gate, no late-structure bias")
  needs the 500/1000/1500/2000 canary on real documents — provider spend, owner-gated.
  The deterministic no-first-400-bias property is proven; the SEMANTIC quality plateau
  is not yet measured.
- The vNext OUTPUT contract (research tags in prompt/compiler with tolerant parsing +
  version bumps) is the next additive slice; qualification is canary-gated.
- The `key_terms` weakness on single-parent documents (noted in the ParentSkeleton v2
  log — TF·IDF has no df signal) carries into a one-parent fingerprint's vocabulary;
  unchanged here, a possible later tune.
