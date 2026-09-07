---
title: "WORK LOG — DOCUMENT-SEMANTIC-INDEX-V1 slice S2: parent-map compiler"
change_id: DOCUMENT-SEMANTIC-INDEX-V1-S2
date: 2026-09-07
owner: shared (deterministic policy)
last_reviewed: 2026-09-07
last_touched: 2026-09-07
status: complete
register: 11.131
package: shared/polymath_shared/document_profile/map_compiler.py (new), tests/determinism/test_parent_map_compiler.py (new), scripts/scaffold_polymath_v4.py
architecture_impact: "New deterministic-policy compiler for the parent-map DSL (`MAP|alias|routing signature|hook1;hook2;hook3`). `compile_maps(raw_response, manifest)` turns a raw model response into `CompiledMap` records keyed to the real parent through the S1 `SkeletonManifest`: tolerant format, strict identity (alias drift like `P17` / `MAP | P0017 |` resolves by numeric value; unknown / ambiguous / invented aliases and empty signatures are rejected, never attached to the nearest parent); partial output is durable (73 of 90 valid lines keep 73, `missing_aliases` is the exact remaining 17 to repair — successful lines never re-run); duplicates keep the first valid record (pinned rule) and receipt the rest. Every map carries the skeleton's Python-extracted `exact_identifiers` verbatim — independent of whether the model listed an identifier as a hook (plan §9). Compiled search text is normalized on the repository's NFC contract plus the measured Compound-Mini non-breaking-hyphen/space fold; the raw model text is hashed FIRST so `raw_response_hash != completeness_hash` by design (§10/§33). Generic signatures/hooks are flagged, not fatal (§19.2). Injected instructions inside a MAP line compile as the signature string — this compiler executes nothing (§30). Additive: no worker, no API, no persistence, no schema change; the S9 worker will call it, the S4 tables will store its output."
---

# WORK LOG — DOCUMENT-SEMANTIC-INDEX-V1 slice S2

## Contract

Slice S2 (plan §9-§11, §18-§19, §30-§33, §36.2, §40). A dedicated deterministic
compiler for the parent-map DSL, composing with the S1 skeleton. Exit (§40 S2):
"40/40, partial recovery tests, identity safety tests." No API.

Owner: `shared` (deterministic policy). Public contract:
`compile_maps(raw_response: str, manifest: SkeletonManifest, *, contract=MAP_COMPILER_VERSION) -> MapCompileResult`
with frozen `CompiledMap` / `RejectedLine` / `MapCompileResult`. Inputs: the raw
model text + the S1 manifest (expected aliases -> parent_id, and the deterministic
`identifiers`). Outputs: an in-memory result (no persistence this slice). Failure
modes surfaced, never silent: unknown/ambiguous aliases, empty signatures,
malformed lines and non-MAP lines are receipted in `rejected` / `unknown_aliases`;
`missing_aliases` is the exact repair set. Dependency edge: imports the S1
`parent_skeleton` (intra-shared, allowed). Reverse dependents (future): S3 packer
(map density), S9 `doc_parent_map` worker (calls it), S4 tables (persist
`CompiledMap`). Verifier: `tests/determinism/test_parent_map_compiler.py`.
Rollback: additive module + test, deletable.

## Changes

- **`shared/polymath_shared/document_profile/map_compiler.py`** (new):
  - `compile_maps` — line scan: non-MAP and blank lines are ignored/receipted;
    a MAP line is split on `|` into alias / signature / hooks (tolerant of extra
    `|` in the tail).
  - Alias resolution (`_resolve_alias`): normalize (`_alias_key`, mirroring the
    profile compiler's `upper()` + whitespace strip) then resolve by numeric
    value against the manifest's expected aliases — `P17` and `P0017` are the
    same parent; a number with no skeleton is `unknown`; a collision is
    `ambiguous`. An unresolved alias is never attached to a look-alike parent.
  - `normalize_search_text` (§10): NFC (the repo's Unicode contract, as
    `canonicalizer.normalize_surface` / `identity.normalize_document_bytes` use)
    + the measured non-breaking-hyphen (U+2011) / non-breaking-space (U+00A0)
    fold + quote/emphasis strip + whitespace collapse, case preserved. Applied to
    signatures and hooks only; identifiers are never routed through it.
  - Hooks: `;`-split, normalized, generic dropped, deduped preserving order,
    capped at `MAX_HOOKS = 3`; quality flags `generic_hooks_dropped:n` /
    `hooks_count:n`.
  - Exact identifiers attached from `manifest.skeletons[...].identifiers` (S1),
    never parsed from the model (§9).
  - Quality: `generic_signature` flag for boilerplate ("This section discusses
    …") and all-generic-word signatures — flagged, not rejected (§19.2).
  - Duplicate alias: first valid non-empty record wins, the rest receipted.
  - Hashes: `raw_response_hash` over the raw model text FIRST; per-map `map_hash`
    over (contract, alias, parent_id, signature, hooks, identifiers);
    `completeness_hash` over the sorted valid (alias, map_hash) — the parent-map
    completeness link of the receipt chain (§33).
  - `MAP_COMPILER_VERSION = "map-compiler-v1"` (versioned independently, §32).
- **`tests/determinism/test_parent_map_compiler.py`** (new): 15 pure pins.
- **`scripts/scaffold_polymath_v4.py`**: declared the module, the test and this
  work-log in `TREE`.

## Proof

```
.venv/bin/python -m pytest tests/determinism/test_parent_map_compiler.py -q  -> 15 passed
.venv/bin/python -m pytest tests/determinism/test_parent_skeleton.py -q      -> 13 passed (S1 seam)
.venv/bin/python scripts/repo_guard.py                                       -> repo guard: ok
.venv/bin/python scripts/wiki_worm.py --check                                -> wiki: ok
.venv/bin/python scripts/agent_preflight.py                                  -> preflight: ok
```

Pins the §36.2 shape against REAL S1 manifests: 40/40 compiles complete; a
90-alias run missing 17 recovers the exact sorted 17 in `missing_aliases` with
73 durable maps; an unknown alias (`P9999`, `PXX`) is rejected and never attached
to `par-*`; a duplicate `P0001` keeps the first signature and receipts the second;
alias drift (`P1`, `P0002`, `map|p3`) resolves; U+2011 `top‑k` compiles to ASCII
`top-k` with `raw_response_hash != completeness_hash`; the compiled
`exact_identifiers` equal the skeleton's (`CVE-2026-0217`/`AU21`/`021`) even when
the hooks name none of them; an empty signature is rejected and its alias is
`missing`; a `MAP|P0031|IGNORE ALL PREVIOUS INSTRUCTIONS …` line compiles to a
map whose signature is that text (data, never executed); a generic signature is
flagged not dropped; hooks cap/dedup/generic-drop; determinism (same input =>
identical `to_dict` + `completeness_hash`); and a static AST purity pin.

Eyeball on a mixed response (drift + duplicate + generic hook + unknown + missing
P0003): P0001 kept the first record with `top‑k`-style text folded and identifiers
`(CVE-2026-0217, RFC 5246, 021, AU21, FACS)` from the skeleton; P0002 dropped the
generic hook `system` and flagged `hooks_count:2`; `missing=('P0003',)`,
`unknown=('P9999',)`, `duplicate=('P0001',)`, `complete=False`.

## Rejected claims

- **Not** a competing normalization policy (§10): `normalize_search_text` applies
  the repository's NFC contract; the only addition is the narrow, documented fold
  of the two non-breaking code points the Compound-Mini run actually emitted.
  Broader dash/quote normalization, if ever wanted, belongs to the shared
  normalization owner, not here.
- **Not** dependent on model hooks for exact retrieval (§9/§43.3): identifiers are
  the skeleton's; the compiler cannot invent or lose them.
- **Not** an injection-obedient parser (§30): deterministic text parsing treats an
  embedded instruction as the signature value. The generation-side injection
  defence (the P0031 regression) is the prompt's job (S8), not the compiler's.
- No runtime path claimed working (AGENTS.md §9): S2 is a pure library slice.

## Open contract gaps

- Nothing calls the compiler yet. Next: **S3 — token packer / capacity model**
  (`shared/polymath_shared/document_profile/map_batches.py`): input-token
  estimate, billed/visible output EMAs seeded from the measured baseline (135.7
  input / 87 billed / ~29 visible tokens per parent), the combined
  global-profile+MAP capacity formula, the mapping-only capacity (~60 target, 40
  proven), the TPM guard, and deterministic batch manifests from the S1
  skeletons. Do not hard-code capacity forever; update from receipts.
- The real frozen 40-parent Compound-Mini raw output is NOT in the repo (only its
  measured metrics, plan §12). S2's fixture is synthetic-but-faithful and
  exercises every §36.2 behaviour; when the owner's raw output is available it
  should be pinned as an additional regression fixture (and reused by S6/S14).
- The generic-signature/hook lists are small and canaryable; the frozen map
  QUALITY gate (self-retrieval, cross-encoder support, discriminative traps) is
  S14, not this slice.
