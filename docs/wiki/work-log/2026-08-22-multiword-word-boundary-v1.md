---
change_id: multiword-word-boundary-v1
owner: worker
date: 2026-08-22
status: complete
architecture_impact: matcher-correctness-no-policy-change
last_reviewed: 2026-08-22
---

# MULTIWORD-WORD-BOUNDARY-V1: stop substring trigger matches

## Contract

Phase 1 step 6 shadow comparison (predicate compiler repair) surfaced
the licensing question from NEXT_SESSION.md: `skill --similar_to-->
users` survived the VerbNet repair. Data answered it:

- All ACCEPT similar_to candidates carry `trigger_lemma=like`
  (`trigger_surface=like`, source arm `multiword`) — authored pack
  entry, not VerbNet inheritance. Compiler repair held.
- The matched evidence text is "**Unlike** the action phase…". The
  bare `like` entry in
  `shared/polymath_shared/rulepack/core-predicates-v1.3.0.yaml:538`
  matched inside `unlike` because every multiword match site used raw
  substring containment with no word boundary.
- Endpoints (`skill`, `reputation`, `followers`, `users`) were bound
  from elsewhere in the chunk across that false trigger.
- F3 refused all four in shadow (ENDPOINT_SUBJ_NOT_DURABLE), but only
  because those surfaces are not durable — refusal by luck, not by
  correctness.

## Changes

Word-boundary matching (`(?<!\w)` / `(?!\w)`) at all three sites,
verbs/nouns arms unchanged (already `\b`-bounded):

1. `workers/workers/evidence_proposer.py` — propose_evidence multiword
   finditer (localization)
2. `workers/workers/evidence_proposer.py` — localize_trigger multiword
   containment check
3. `shared/polymath_shared/rulepack/compiler.py::_trigger_matches` —
   typed and untyped multiword validation paths

No rule-pack content change. Bare `like` remains declared; whether it
should license similar_to at all is a separate recall-policy decision
(mission Phase 2 registry question), not smuggled into a matcher fix.

## Proof

- New regression tests: `unlike`/`likely`/`dislike` must not license
  `like`; genuine "like"/"similar to" still fire; typed-arm path
  agrees with untyped path.
- Full suite green before change: 828 passed, 68 skipped (HEAD 8e78657).
  After change + regressions: **832 passed, 68 skipped**.
- core-3-v1 A/B, identical reset SQL both legs, fresh worker processes
  each leg (first post-fix attempt against pre-edit workers reproduced
  the old result exactly — stale code; fleet torn down to one
  supervisor and rebooted before measuring):

  ```
                    pre-fix   post-fix
  candidates         112        98
  ACCEPT              19        16
  QUALIFY              9         8
  REJECT              84        74
  similar_to cands      4         0
  F3 refusals          22        18
  ```

  Removed: skill/reputation/followers --similar_to--> users (ACCEPT,
  trigger `like` inside "Unlike") and heuristics -> intended habitual
  behavior (QUALIFY, same mechanism). No legitimate candidate lost.

## Rejected claims

- "The multiword arm carries like as a verb sense." — the corpus hit
  was the token `unlike`; no verb-sense licensing occurred.
- "Removing like from the pack fixes this." — it fixes one instance of
  the class; the substring defect would mis-fire on any short phrase
  embedded in a longer word (aka in quaka-like tokens, per in
  superper, part of in counterpart office).

## Open contract gaps

- Bare single-word entries inside multiword lists are structurally
  ambiguous (preposition vs predicate). Registry-level review of
  `like` deferred to Phase 2 registry hardening with recall data.
