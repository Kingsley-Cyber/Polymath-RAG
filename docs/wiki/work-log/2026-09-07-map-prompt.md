---
title: "WORK LOG — parent-map request prompt (§19 contract, §30 data-only)"
change_id: DOCUMENT-SEMANTIC-INDEX-V1-MAP-PROMPT
date: 2026-09-07
owner: shared (deterministic prompt policy)
last_reviewed: 2026-09-07
last_touched: 2026-09-07
status: complete
register: 11.144
package: shared/polymath_shared/document_profile/map_prompt.py, tests/determinism/test_map_prompt.py, scripts/scaffold_polymath_v4.py
architecture_impact: "Commits the deterministic parent-map request prompt (the §19 MAP DSL contract + the §30 data-only injection guardrail) that the S9 worker's injected `infer` closure will send. Pure policy (shared/): no I/O, no model. It is the committed successor to the scratchpad prompt proven live in register 11.136; the profile prompt (prompt.py) is the analogue for the profile scale. Nothing calls it in production yet — the Groq call that consumes it is the owner-gated live wiring. No compiler/worker/chunker change."
---

# WORK LOG — parent-map request prompt

## Contract

Plan §19 (MAP contract), §30 (prompt injection during indexing), §9; migration
§GAP-09, §25. The S9 worker takes the inference boundary as an injected `infer`; the
missing piece for its live closure is the committed, deterministic request prompt.
Build it now (pure, testable) so the gated wiring is just "call the routed Groq model
with `build_map_prompt(skeletons)`".

Owner: `shared`. Public contract: `MAP_SYSTEM`, `build_map_user_prompt(skeletons)`,
`build_map_prompt(skeletons, *, is_combined=False) -> (system, user)`. Rollback:
delete module + test. Verifier: `tests/determinism/test_map_prompt.py`.

OUT of scope (owner-gated): the Groq call, the S7 routing that selects the account,
and the combined global-profile+map fast-path prompt (§13.3) — accepted in the
signature, not yet specialized.

## Changes

- **`map_prompt.py`** (new): `MAP_SYSTEM` states the DSL (`MAP|<alias>|<signature>|h1;h2;h3`),
  the exact-alias / ~10-12-word-signature / exactly-3-hooks / identifier- and
  negation-preservation rules (§19), and the SOURCE-IS-DATA guardrail (§30: describe,
  never obey; no tools/external actions). `build_map_user_prompt` renders each
  `ParentSkeleton` (alias, heading, opening/salient excerpt, terms, identifiers) as a
  DATA block with a footer naming the exact alias set + count. Deterministic.
- **test + scaffold**: 6 pins; two TREE lines; this work-log.

## Proof

```
.venv/bin/python -m pytest tests/determinism/test_map_prompt.py -q   -> 6 passed
.venv/bin/python scripts/repo_guard.py        -> repo guard: ok
.venv/bin/python scripts/wiki_worm.py --check -> wiki: ok
```

Pins: the system message carries the DSL + identifier examples (021 / AU21 /
CVE-2026-0217) + the data-only guardrail + no-tools; the user prompt renders every
alias exactly once with a count/alias footer; an adversarial one-sentence section is
carried verbatim as DATA (the guardrail neutralizes it — live resistance was proven in
11.136); identifiers are visible for preservation; deterministic; empty is safe.

## Rejected claims

- **Not** live: no provider call; the prompt is text. The Groq call + S7 routing that
  consume it are owner-gated (spend).
- **Not** a new injection defense mechanism: the compiler (S2) already treats any
  injected instruction as the signature string; this prompt is the first line, not a
  second policy.

## Open contract gaps

- The combined global-profile + first-map prompt (§13.3) is deferred; `is_combined`
  is accepted but not specialized.
- Live qualification (an 11.136-style canary against the routed model) is owner-gated
  (spend); this slice pins the prompt CONTRACT, not a fresh live result.
