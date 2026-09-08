---
title: "WORK LOG — vNext global-profile prompt (research-index surfaces, §18)"
change_id: DOCUMENT-SEMANTIC-INDEX-V1-PROFILE-PROMPT-VNEXT
date: 2026-09-07
owner: shared (deterministic prompt policy)
last_reviewed: 2026-09-07
last_touched: 2026-09-07
status: complete
register: 11.145
package: shared/polymath_shared/document_profile/profile_prompt_vnext.py, tests/determinism/test_profile_prompt_vnext.py, scripts/scaffold_polymath_v4.py
architecture_impact: "Adds the vNext global-profile request prompt as a NEW module that consumes the DocumentFingerprint (S5) and asks for the source-anchored fields (ONE/SUMMARY/TOPIC/TERM/Q) + routing fields (SEARCH/THEORY/CONCEPT/SEEALSO) + the research-index surfaces (LATENT-PATTERN/ANCHOR/RECALLQ/TENSION/BRIDGE/INVERSION/BOUNDARY). The LIVE prompt.py and compiler.py are UNTOUCHED (T1828 — until S8 switches the worker behind the quality canary); the tolerant compiler for the new tags is the S8 step. Tag vocabulary is imported from fingerprint (single source of truth). Pure policy; no I/O, no model; qualification is the owner-gated 500/1000/1500/2000 canary."
---

# WORK LOG — vNext global-profile prompt

## Contract

Plan §18 (global profile / profile-atom integration), §5-§6. The fingerprint (S5) is
the deterministic INPUT; this is the request that turns it into the vNext profile
(the "profile atoms" step of the /goal chain), parallel to `map_prompt.py` for the
parent-MAP scale. Build it additively so the profile scale's input→prompt path is
complete and ready for the S8 switch, without touching the live profile path.

Owner: `shared`. Public contract: `SYSTEM`, `build_vnext_profile_user_prompt(fp)`,
`build_vnext_profile_prompt(fp) -> (system, user)`, `output_fields()`. Rollback: delete
module + test. Verifier: `tests/determinism/test_profile_prompt_vnext.py`.

OUT of scope (locked/gated): the live `prompt.py`/`compiler.py` are untouched (T1828);
the tolerant compiler that PARSES the new research tags is S8 (needs the live compiler
unlocked); qualification is the 500/1000/1500/2000 canary (spend).

## Changes

- **`profile_prompt_vnext.py`** (new): `SYSTEM` states the two field kinds — source-
  anchored (must be defensible from the text) vs routing-inferred (hypotheses, NEVER
  cited as evidence, plan §18) — and adds per-field rules for the seven research-index
  tags. `build_vnext_profile_prompt(fingerprint)` renders the fingerprint's
  `render_block` into the request. `output_fields()` returns the full ordered label set
  from `fingerprint`'s constants (so prompt + the future compiler cannot drift).
- **test + scaffold**: 4 pins; two TREE lines; this work-log.

## Proof

```
.venv/bin/python -m pytest tests/determinism/test_profile_prompt_vnext.py -q  -> 4 passed
.venv/bin/python scripts/repo_guard.py        -> repo guard: ok
.venv/bin/python scripts/wiki_worm.py --check -> wiki: ok
```

Pins: the system message lists every source-anchored + routing-inferred label incl.
all seven research-index tags (hyphenated LATENT-PATTERN) and the "routing hypotheses …
never cited as evidence" contract; the user prompt consumes a real fingerprint block
(identity + coverage markers appear); `output_fields()` equals the fingerprint's
source-anchored + routing-inferred vocabulary and the two sets are disjoint;
deterministic; empty is safe.

## Rejected claims

- **Not** a change to the live profile: `prompt.py` and `compiler.py` are untouched; this
  is a separate versioned module (`doc-profile-vnext-v1`) used only by the gated S8 path.
- **Not** the tag parser: emitting the research tags in the request does not parse them;
  the tolerant compiler extension is S8 (the live compiler is locked until then).
- **Not** a qualified quality result: this pins the request CONTRACT; the 500/1000/1500/
  2000 canary that proves the added surfaces help is owner-gated (spend).

## Open contract gaps

- The S8 compiler extension (tolerant parse of the research tags + version bump) and the
  worker switch to `fingerprint` + `profile_prompt_vnext` are gated (canary + fleet).
- The combined global-profile + first-map fast-path prompt (§13.3) remains deferred.
