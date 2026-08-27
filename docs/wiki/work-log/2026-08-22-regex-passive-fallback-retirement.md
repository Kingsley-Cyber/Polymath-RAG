---
change_id: regex-passive-fallback-retirement
owner: worker
date: 2026-08-22
status: complete
architecture_impact: removes-fabricated-syntax-from-production
last_reviewed: 2026-08-22
---

# PREDICATE-COMPILER-V2 SLICE 2b: regex passive fallback retired

## Contract

Owner policy decision: REMOVE_FROM_PRODUCTION. "A parser failure is not
permission to invent syntax." Production behavior is now: spaCy parse
unavailable -> `parse_sentence` returns None -> no predicate candidate;
evidence survives untouched.

Discovery while retiring it: the worker venv cannot load
en_core_web_sm (the model lives in the sidecar), so production
sentence-level parse records had been produced by the regex fallback
all along; token-level UD always came from the sidecar. kimi_v2 never
reads the sentence parse record for structure — only `sl.parse["voice"]`
for orientation, which degrades to surface order under F7 when absent.

## Changes

- `workers/workers/syntax.py`: without a loadable parser,
  `parse_sentence` returns None unless
  `POLYMATH_SYNTAX_REGEX_DIAGNOSTIC=1`; `parser_identity` reports
  ("none", "predicate-v2-no-parse"). The frozen regex parser remains
  reachable in diagnostic mode only.
- `tests/determinism/test_q1r_v110_revision.py`: Q1R locks now pin the
  diagnostic mode explicitly (env + forced parser failure) so they test
  the frozen diagnostic artifact hermetically on any host.
- New lock: production default fabricates no syntax.

Not touched: sidecar 8744, kimi_v1/v2 generators, gates, GLiNER,
admission, retrieval.

## Proof

- Full suite green after change: 847 passed, 68 skipped (HEAD 7ec79a7).
- New production-default lock passes with parser forced down.

## Rejected claims

- "Keep the fallback until kimi_v2 ships." — kimi_v2 shipped in slice 2
  and does not consume fabricated parses; keeping a fabrication path in
  production contradicts the decision record.

## Open contract gaps

- Slice 3 frozen stress suite; shadow A/B; corpus validations; gates.
