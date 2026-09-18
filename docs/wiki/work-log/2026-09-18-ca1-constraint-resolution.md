---
change_id: CA1-CONSTRAINT-RESOLUTION
owner: constraint-aware-retrieval
date: 2026-09-18
status: complete
architecture_impact: "CONSTRAINT-AWARE-RETRIEVAL-V1 CA1. Adds deterministic SOURCE-identity resolution (resolve_constraint_targets) to query_constraints.py — a pure function that maps a CA0 SOURCE constraint to the corpus doc_id it names, by identity (exact/containment) with bounded Scout confirmation. No retrieval/fusion/rerank/evidence/synthesis change; externally visible ranking is UNCHANGED. Worktree constraint/aware-retrieval; UNMERGED (deploys with CA2+)."
last_reviewed: 2026-09-18
---

## Contract
CA1 answers only "what corpus document does this explicit constraint refer to?" — NOT "how much
ranking priority" (that is CA3). Deterministic IDENTITY resolution (never semantic search): a CA0
`SOURCE` constraint is resolved to a corpus `doc_id`, corpus-scoped, fail-open, preferring
UNRESOLVED over confidently-wrong. Resolution fills `resolved_targets` + identity `confidence` and
preserves `kind`/`value`/`strength`/`reason` (CA1 does not reinterpret the relationship).

## Changes
- `shared/polymath_shared/query_constraints.py`: `resolve_constraint_targets(constraints,
  source_index, *, scout_nominations=None, corpus_id=None) -> list[Constraint]`. `source_index` =
  `{doc_id: source_name}` for the ACTIVE corpus (caller supplies the corpus-scoped index; shared/
  does no I/O — resolution never touches a global universe). Deterministic identity score:
  exact normalized title/author/full = 1.0; author-name containment = 0.92; title fragment = 0.6.
  A UNIQUE match ≥ 0.9 resolves (confidence 0.95 exact / 0.85 containment); a UNIQUE weak (≥0.6)
  match resolves ONLY if a Scout nomination (top-3) confirms it (confidence 0.5); a TIE at the top
  tier resolves to NOTHING (Scout rank never breaks an identity tie). `replace()` preserves the
  other fields. Helpers `_source_identity` (parse `Author - Title (Year).ext`), `_norm`,
  `_identity_score`.
- NEW `tests/determinism/test_constraint_resolution.py` (17 tests); declared in scaffold TREE.
- `confidence` semantics: post-resolution it is the IDENTITY-resolution confidence (per the admitted
  D-spec). CA0's transient detection-confidence default is overwritten by CA1 in the live flow; CA0
  is not revisited (no contract defect — strength+reason still carry the detection signal).

## Proof
UNIT_PROVEN (executed path = this worktree). `pytest test_constraint_resolution.py` = 17/17:
Walter Murch → *In the Blink of an Eye* doc; Save the Cat → *Save the Cat* doc; Sidney Lumet →
*Making Movies* doc (real cinema docmap); "According to Murch" → surname resolves; HARD/SOFT/
EXPLORATORY strength preserved through resolution; exact title beats a title-mention; two
same-author docs → `[]` (and Scout picking one does NOT break the tie); a unique title amid the
same author resolves; missing source → `[]` no exception; a source not in the active index → `[]`
(corpus isolation); weak title-fragment identity resolves ONLY with Scout confirmation; non-SOURCE
constraint untouched; asdict/JSON + repeat-run determinism stable. CA0 (16) + subquery_provenance +
candidate_engine re-run green — no regression (CA1 adds functions; `chat_plan` unchanged since CA0).

## Rejected claims
- Embedding/nearest-document resolution (rejected — identity, not semantic search; the owner's
  distinction: "Scout topically promising" ≠ "this is the source the user named").
- Silently selecting the first result on ambiguity (rejected — ambiguous → `[]`).
- Scout rank breaking an identity tie (rejected — Scout confirms a single weak candidate only).
- Any retrieval/ranking behavior change (out of CA1 scope — CA3).

## Open contract gaps
- QUERY_PLANNER / SUBQUERY_PROVENANCE: **TESTED_UNCHANGED** — CA1 adds a standalone resolver; the
  plan/receipt is not yet enriched with resolved identity (that plumbing is CA2).
- CANDIDATE_ENGINE / RESOLUTION_STATE / RETRIEVAL_RECEIPT / PROFILE_YIELD_RECEIPT / ACCEPTANCE
  (transitive): **NOT_AFFECTED** — no call path from these into `resolve_constraint_targets` yet.
- CA2 (plumb the corpus-scoped `source_index` + `scout_nominations` from `ui.py`, populate
  `resolved_targets` on the live plan, surface in the receipt, ranking still a no-op): **DEFERRED**.
- Richer corpus metadata (structured title/author instead of parsing the source name): DEFERRED —
  the resolver takes `{doc_id: source_name}`; a structured index can extend it without a contract change.
