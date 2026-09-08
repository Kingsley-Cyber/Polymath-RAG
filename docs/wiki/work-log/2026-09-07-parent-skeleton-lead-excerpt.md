---
title: "WORK LOG — ParentSkeleton v2: lead_excerpt framing for headingless parents"
change_id: DOCUMENT-SEMANTIC-INDEX-V1-LEAD-EXCERPT
date: 2026-09-07
owner: shared (deterministic policy)
last_reviewed: 2026-09-07
last_touched: 2026-09-07
status: complete
register: 11.137
package: shared/polymath_shared/document_profile/parent_skeleton.py, shared/polymath_shared/document_profile/map_batches.py, tests/determinism/test_parent_skeleton.py, scripts/scaffold_polymath_v4.py
architecture_impact: "Adds ONE deterministic orientation signal to the parent-map input: ParentSkeleton.lead_excerpt = the first 2 substantive sentences of the parent, emitted ONLY when heading_path is empty (flat / transcript windows). For a structured parent the heading already fills the framing slot, so lead_excerpt stays empty and nothing changes. For a headingless parent, select_salient_excerpt (the strongest sentence ANYWHERE) can miss the window's opening orientation; lead_excerpt supplies it. No transcript classifier, no VTT/Docling, no new dependency, no worker/stage, and — deliberately — NO chunker change, NO materializer change, and NO map_compiler change (the MAP output line is unchanged). SKELETON_BUILDER_VERSION bumps parent-skeleton-v1 -> v2 and lead_excerpt enters skeleton_hash, which propagates into batch_hash via manifest_hash (the S3 correction) — the derived MAP input changed, so its identity changes, exactly as the contract/hash system is designed for. Nothing is persisted yet (S9 not built), so there is no backfill cost."
---

# WORK LOG — ParentSkeleton v2: lead_excerpt

## Contract

Owner-directed fix (2026-09-07) BEFORE the MAP/profile backfill: fill the framing
slot for headingless (flat / transcript) parents, where the only cue Groq gets
today is a salient sentence chosen from anywhere in an ~850-word window — losing
the window's opening orientation. The smallest repo-native fix: one deterministic
field, `lead_excerpt`, reusing existing helpers.

Owner: `shared`. Public-contract change: `ParentSkeleton` gains `lead_excerpt`;
`SKELETON_BUILDER_VERSION` -> `parent-skeleton-v2`. Rollback: revert (nothing
persisted). Verifier: `tests/determinism/test_parent_skeleton.py`.

Explicitly OUT of scope (locked, per the owner): no chunker change, no materializer
change, no transcript detection, no new dependency, no map_compiler change.

## Changes

- **`parent_skeleton.py`**:
  - `select_lead_excerpt(text)` — first `LEAD_EXCERPT_SENTENCES` (2) substantive
    sentences, filtered by the existing `_sentences` / `_is_boilerplate` /
    `MIN_SENTENCE_WORDS`, truncated to `LEAD_EXCERPT_MAX_WORDS` (50) via
    `_truncate_words`. No new heuristic (no filler-word stripping).
  - `ParentSkeleton.lead_excerpt` field + `to_dict` key.
  - Populated in `build_parent_skeletons`: `select_lead_excerpt(text) if not
    heading_path else ""`.
  - `_skeleton_hash` now binds `lead_excerpt` (after `region_role`,
    before `salient_excerpt`); `SKELETON_BUILDER_VERSION` -> `parent-skeleton-v2`.
- **`map_batches.py`**: `skeleton_prompt_tokens` includes `lead_excerpt` — empty
  for structured parents (no change), ~30-50 words on a headingless parent, so the
  measured density envelope stays intact (bounded, not a per-paragraph blow-up).
- **test + scaffold**: a `lead_excerpt` pin; this work-log declared.

## Proof

```
.venv/bin/python -m pytest tests/determinism/test_parent_skeleton.py \
  tests/determinism/test_parent_map_compiler.py tests/determinism/test_map_batches.py \
  tests/determinism/test_groq_router.py -q     -> 60 passed, 1 skipped
.venv/bin/python scripts/repo_guard.py         -> repo guard: ok
.venv/bin/python scripts/wiki_worm.py --check  -> wiki: ok
.venv/bin/python scripts/agent_preflight.py    -> preflight: ok
```

Pin: a parent WITH a heading has `lead_excerpt == ""`; a headingless parent's
`lead_excerpt` is its opening framing (bounded, `startswith` the first sentence,
distinct from the salient excerpt), and appears in `to_dict`.

Real demonstration (the owner's essay body with its `#` heading stripped = a
headingless window): LEAD = "Every new technology splits people into two factions…
The preservationists arrive first…" while SALIENT = "**Three: the off-grid
floor.** Keep enough of the old way…". Before v2, Groq's only framing was the
mid-document salient sentence (criterion 3); now it also sees the window's opening
thesis. Structured parents (heading present) are byte-for-byte unchanged.

## Rejected claims

- **Not** transcript-awareness: no format detection, no speaker/timecode parsing;
  `lead_excerpt` fires purely on "heading_path is empty". A well-headed doc is
  untouched.
- **Not** first-two-sentences-per-paragraph: that would inflate the prompt (~+9k
  tokens across 60 parents) and change the measured capacity; this is the first two
  sentences OF THE PARENT (~+30-50 words).
- **Not** a corpus rebuild: no maps are persisted yet (S9 unbuilt); the v2 hash is
  the contract working as designed, not a migration.

## Open contract gaps

- The key_terms weakness on single-parent documents (TF·IDF has no df signal → generic
  terms like "new/old/way"; "you" is an unlisted stop term) is SEPARATE and untouched
  here — a possible later tune, not this fix.
- Under-segmentation of docs whose logical structure is **bold** inline (e.g. the
  essay's four "**One:/Two:**" criteria are one parent) is a boundary problem, not a
  framing one — it belongs upstream (materializer / a bold-lead-in detector) and is
  not addressed by lead_excerpt.
- Next remains S5 (profile vNext + fingerprint); the MAP skeleton input is now v2.
