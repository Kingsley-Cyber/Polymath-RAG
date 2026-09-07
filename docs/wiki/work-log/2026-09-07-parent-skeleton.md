---
title: "WORK LOG — DOCUMENT-SEMANTIC-INDEX-V1 slice S1: deterministic ParentSkeleton"
change_id: DOCUMENT-SEMANTIC-INDEX-V1-S1
date: 2026-09-07
owner: shared (deterministic policy)
last_reviewed: 2026-09-07
last_touched: 2026-09-07
status: complete
register: 11.130
package: shared/polymath_shared/document_profile/parent_skeleton.py (new), tests/determinism/test_parent_skeleton.py (new), scripts/scaffold_polymath_v4.py
architecture_impact: "New deterministic-policy module in shared/: the parent-map LLM's per-parent input is now produced by CPU-only Python (re / Counter / math.log), not a summary model and not a local LLM. `build_parent_skeletons(parents)` returns a `SkeletonManifest` of one `ParentSkeleton` per retrieval-eligible parent (alias P0001 mapped to the real parent_id in the manifest — opaque ids never enter the prompt), plus explicit `ExcludedParent` records for furniture/noise (the region-role authority `document_region.is_noisy` decides eligibility; no competing furniture policy is introduced) and empty parents. Each skeleton carries a salient extractive sentence (not first-30-words), 3-5 TF x IDF key terms, and — critically — exact identifiers extracted DETERMINISTICALLY from source (CVE/RFC/version/code/acronym/zero-padded), independent of any model hook (plan §9). text_hash and skeleton_hash give content identity; a manifest_hash binds the alias->parent_id map. Additive: no worker, no API call, no persistence, no schema, no chunk/graph identity change; nothing consumes it yet (S2 map compiler and S9 map worker will)."
---

# WORK LOG — DOCUMENT-SEMANTIC-INDEX-V1 slice S1

## Contract

Slice S1 of the plan of record (`docs/wiki/plans/DOCUMENT-SEMANTIC-INDEX-V1-PLAN.md`
§7-§10, §36.1, §40). Give every retrieval-eligible parent one deterministic,
CPU-cheap `ParentSkeleton` — the compact thing the parent-map LLM will see —
without a summary model, a local LLM, an API call, or scikit-learn. Exit
criterion (§40 S1): "1,000-parent fixture deterministic and cheap." Rollback:
remove the additive module + test (nothing depends on them yet).

Owner: `shared` (deterministic policy). Public contract:
`build_parent_skeletons(parents: Sequence[Mapping]) -> SkeletonManifest` and the
frozen dataclasses `ParentSkeleton` / `ExcludedParent` / `SkeletonManifest`.
Inputs: the repository's parent rows (as `context.py` consumes them — `text`,
`heading_path`, `region_role`, an identity/order field), any order. Outputs: an
in-memory manifest (no persistence in this slice). Failure modes: an empty or
noise-only document yields an empty skeleton set with every parent accounted for
in `excluded` (never dropped silently). Dependency edges: imports the region-role
authority `polymath_shared.document_region` (intra-shared, allowed). Reverse
dependents (future): S2 map compiler (aliases + identifiers), S3 packer (skeleton
sizes), S9 `doc_parent_map` worker (persists the manifest). Verifier:
`tests/determinism/test_parent_skeleton.py`. Rollback boundary: additive module,
deletable.

## Changes

- **`shared/polymath_shared/document_profile/parent_skeleton.py`** (new):
  - `build_parent_skeletons(parents)` — splits eligible from furniture/empty,
    orders eligible deterministically by `(source_position, id)` so alias
    assignment is stable regardless of the caller's order, computes sparse
    document-frequency statistics over the eligible set, and emits one
    `ParentSkeleton` per eligible parent + `ExcludedParent` records for the rest.
  - `extract_identifiers` (§8.1/§9): most-specific-first regexes (CVE, RFC,
    dotted version, letter+digit code such as AU21 / CS0-003, zero-padded code
    such as 021, acronym) with **span masking** — each match is blanked (same
    length, positions preserved) before the next, less-specific pattern runs, so
    a generic rule can never re-extract a substring already claimed (`0217` /
    `2026` inside `CVE-2026-0217`); all-caps stop words ("THE") are filtered.
    Canonical form, first-seen order, deduplicated. Independent of model hooks.
  - `select_key_terms` (§8.3): TF x IDF + heading-overlap bonus + rare-identifier
    bonus, generic stop terms rejected, deterministic tie-break (score desc, term
    asc), 3-5 terms.
  - `select_salient_excerpt` (§8.4): highest-scoring source sentence (key-term +
    heading + identifier signal), NOT the blind first-30-words; boilerplate and
    tiny fragments discarded; tie broken by earliest position; truncated to a 30-
    word ceiling; deterministic fallback to a bounded leading slice for list-only
    parents.
  - `idf` = `log((N+1)/(df+1)) + 1` (§8.2). `text_hash` = sha256 of normalized
    text; `skeleton_hash` = sha256 of the derived skeleton (heading/role/excerpt/
    key-terms/identifiers/builder-version — excludes alias/ordinal/position so
    identical content hashes identically and re-aliasing does not churn it);
    `manifest_hash` binds `alias -> parent_id -> skeleton_hash`.
  - `SKELETON_BUILDER_VERSION = "parent-skeleton-v1"` (§32, versioned
    independently of the map prompt / compiler).
- **`tests/determinism/test_parent_skeleton.py`** (new): 13 pure pins.
- **`scripts/scaffold_polymath_v4.py`**: declared the module, the test, and this
  work-log in `TREE`.

## Proof

```
.venv/bin/python -m pytest tests/determinism/test_parent_skeleton.py -q   -> 13 passed
.venv/bin/python scripts/repo_guard.py                                    -> repo guard: ok
.venv/bin/python scripts/wiki_worm.py --check                             -> wiki: ok
.venv/bin/python scripts/agent_preflight.py                               -> preflight: ok
```

The suite pins the §36.1 acceptance shape: one deterministic skeleton per
eligible parent; furniture (toc / front_matter / marketing / index /
bibliography) excluded and accounted (eligible + excluded == input), never
dropped; unknown/absent role stays eligible; exact identifiers preserved with
zero-padding and casing (`CVE-2026-0217`, `AU21`, `021`, `FACS`, `RFC 5246`,
`3.11.15`) and no CVE substrings leaked (`0217`/`2026` absent); same input =>
identical skeleton_hash / manifest_hash / full to_dict; excerpt bounded to <= 30
words and not the boilerplate first sentence; key terms <= 5 with no stop terms;
alias assignment stable under input reordering; 1 / 80 / 1000-parent fixtures
build (1000 deterministic and < 5 s); and a static AST pin that the module
imports only stdlib + `document_region` (no model / network / heavy-ML — the
"no LLM" contract enforced mechanically).

Eyeball on the technical-manual fixture (not just assertions): identifiers
`('CVE-2026-0217','TLS','RFC 5246','3.11.15','021','AU21','FACS')`; key terms
`('tls','au21','cve-2026-0217','facs','control')`; excerpt "Exam objective 021
maps to control family AU21 in the FACS mapping." — a real information-rich
source sentence, not the opening.

## Rejected claims

- **Not** a per-parent summary and **not** one LLM call per parent — this stage
  makes zero API calls; the map LLM (S2+) consumes packed skeletons.
- **Not** a competing furniture/region policy — eligibility defers to
  `document_region.is_noisy` (the single region-role owner); this module only
  reads roles and records exclusion reasons.
- Exact identifiers are **not** left to the model's hook selection (plan §9 /
  §43.3): they are a deterministic `identifiers[]` field. The measured Compound
  Mini nuance (021 survived the signature but not the semantic hooks) is exactly
  what this separation defends against.
- No completion claim on a runtime path (AGENTS.md §9): S1 is a pure library
  slice; there is no wired owner or durable outcome yet, by design.

## Open contract gaps

- Nothing consumes the manifest yet. Next: **S2 — map compiler**
  (`shared/polymath_shared/document_profile/map_compiler.py` +
  `tests/determinism/test_parent_map_compiler.py`): parse the `MAP|alias|sig|hooks`
  DSL, tolerant format / strict identity, partial recovery, duplicate/unknown
  handling, Unicode normalization reuse (§10 — find the existing normalization
  owner, do not add a competing policy), and attach the deterministic
  `exact_identifiers[]` from this skeleton. Pin the frozen 40-parent Mini output
  as the fixture.
- The salient-excerpt and key-term heuristics are canaryable (bounds are module
  constants); the frozen quality gate for maps is S6/S14, not this slice.
- `skeleton_hash` deliberately excludes position; if a later stage needs a
  positional receipt it should hash the manifest (which includes alias), not the
  skeleton.
