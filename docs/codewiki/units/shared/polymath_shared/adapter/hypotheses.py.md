# unit: shared/polymath_shared/adapter/hypotheses.py
anchor: shared/polymath_shared/adapter/hypotheses.py:1-397

## purpose
Generic hypothesis ledger (ADR-0019 §3/§4): pure, deterministic functions over `HypothesisStateV1` / `HypothesisTransitionV1` dicts — persistence is the store's job. θ (connected agent) may GENERATE/REVISE/SPLIT; φ (TrailSignal verdict or closed VALIDATE rule) applies selective pressure (KILL, MERGE, WEAKEN, STRENGTHEN, CONTRADICT, PROMOTE). Every transition names ≥1 cause; every revision keeps its parents. — shared/polymath_shared/adapter/hypotheses.py:1-6 [DERIVED]

## public surface
| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| HypothesisRejected | class(ValueError) | (errors: list[str]) -> exc, `.errors` holds full list | shared/polymath_shared/adapter/hypotheses.py:17-20 | — |
| hypothesis_id | def | (run_id: str, step_id: str, ordinal: int\|str) -> str | shared/polymath_shared/adapter/hypotheses.py:55-56 | — |
| transition_id | def | (run_id: str, hid: str, sequence: int, ordinal: int) -> str | shared/polymath_shared/adapter/hypotheses.py:59-60 | — |
| generate | def | (run_id, step, proposals, *, registry_snapshot_id, recorded_at, max_hypotheses=8, parents=None, ordinal_base=0, known_origin_ids=None) -> (states, transitions) | shared/polymath_shared/adapter/hypotheses.py:192-221 | — |
| apply | def | (run_id, step, current, requests, *, actor, allowed_causes, recorded_at, registry_snapshot_id=None, max_hypotheses=8, known_origin_ids=None) -> (new_states, transitions) | shared/polymath_shared/adapter/hypotheses.py:225-369 | — |
| context_view | def | (current: hid -> latest state) -> list[{hypothesis_id, revision, status, statement}] | shared/polymath_shared/adapter/hypotheses.py:372-376 | — |
| lineage_intact | def | (states, transitions) -> list[str] (errors) | shared/polymath_shared/adapter/hypotheses.py:379-397 | — |

Module-level importers (per-symbol split not in FACTS): shared/polymath_shared/adapter/research_gaps.py, shared/polymath_shared/adapter/semantic_view.py, shared/polymath_shared/adapter/service.py — shared/polymath_shared/adapter/hypotheses.py (FACTS.importers) [DERIVED]

## contracts

**generate** — shared/polymath_shared/adapter/hypotheses.py:192-221
- in: proposals list of dicts (`statement`, `supporting_evidence_ids`, optional `trail_priors`, `knowledge_gaps`, origin fields).
- pre: `1 <= len(proposals) <= max_hypotheses` (199-200); non-empty `statement` per proposal (203-204); ≥1 citable cause — ids must be in `step.context.evidence_refs`, not `PRIOR_EVIDENCE_KINDS`, kind in `CITABLE_EVIDENCE_KINDS` (206, 82-91); priors must be `trail_prior` in context AND run records a `registry_snapshot_id` (207, 94-100); gap ids must match `TRAIL_IDENTIFIER` (213, 41-48); origin ids must exist in `known_origin_ids` when provided (212, 117-121).
- out: states all `revision: 0`, `status: "proposed"` (172, 175); GENERATE transitions, actor `"theta"`, reason `"THETA_GENERATED"` (217-218); ids = `hypothesis_id(run_id, step_id, ordinal_base + n)` (211).
- post: all-or-nothing — any accumulated error raises `HypothesisRejected`; output returned only when errors list is empty (219-221).

**apply** — shared/polymath_shared/adapter/hypotheses.py:225-369
- in: `current` = hypothesis_id → latest state; `requests` typed by `kind`; `allowed_causes` = id → kind.
- pre: `kind` in `TRANSITION_KINDS` and ≠ `GENERATE` (245-246); `hid` known (247-248); current status not in `ABSORBED_STATUSES` (249-250); actor `"theta"` limited to `THETA_KINDS` (251-252); actor ∈ `("theta", "phi", "runtime")` (253-254); ≥1 cause ref whose kind matches `allowed_causes` (256-262); `field_evidence_ids` must be admitted `field_evidence` (265-268); SPLIT: children required and `alive + len(children) <= max_hypotheses` (271-278); MERGE: target known, distinct, not absorbed (301-304); REVISE `changes` keys limited to `REVISABLE_FIELDS + REVISABLE_LIST_FIELDS`, else whole request refused (324-328); CONTRADICT needs contradictions with `evidence_ids` (355-359); REVISE contradictions must cite ids this step may cite (345-349).
- out: new status = `RESULTING_STATUS[kind]` (319); SPLIT mints children at revision 0 inheriting parent support/priors/field/origin (283-294), parent → `"split"` (297); MERGE: target takes union of support/field/contradictions + REVISE transition with reason `"MERGED_IN"` (306-313), source → `"merged"` (315-316); SPLIT child id ordinal = `f"{int(step['sequence'])}:{100 * (n + 1) + k}"` (283).
- post: all-or-nothing; `HypothesisRejected` on any error (367-368); returns `(list(new_states.values()), transitions)` (369).

**context_view** — shared/polymath_shared/adapter/hypotheses.py:372-376
- out: only hypotheses whose status ∉ `ABSORBED_STATUSES`, projected to `{hypothesis_id, revision, status, statement}`, in store/generation order — never id-hash order (373-376).

**lineage_intact** — shared/polymath_shared/adapter/hypotheses.py:379-397
- out: error strings for: transition with empty `cause_refs` (386-387); state revision no transition's `to_revision` reaches (390-392); GENERATE transition parent absent from state's `parent_hypothesis_ids` (393-396).

## effect surface
- Postgres tables read/written: none — persistence is the store's job — shared/polymath_shared/adapter/hypotheses.py:3 [DERIVED]; FACTS `tables_read`/`tables_written` = `[]` [DERIVED]
- Files / network / subprocess / env flags: none — only imports are `hashlib`, `re`, `typing.Any` and `.contracts` — shared/polymath_shared/adapter/hypotheses.py:9-14 [DERIVED]

## invariants
INVARIANT: len(hypothesis_id) = len("hyp_") + 24 hex = 28 — shared/polymath_shared/adapter/hypotheses.py:56 [DERIVED]
  fails-if: stored ids or cross-references of a different length break id matching in the store.
INVARIANT: len(transition_id) = len("hxt_") + 24 = 28 — shared/polymath_shared/adapter/hypotheses.py:60 [DERIVED]
  fails-if: same as above for transition records.
INVARIANT: keys(RESULTING_STATUS) = THETA_KINDS ∪ PHI_KINDS = 9 kinds (GENERATE, REVISE, SPLIT, MERGE, WEAKEN, STRENGTHEN, CONTRADICT, KILL, PROMOTE) — shared/polymath_shared/adapter/hypotheses.py:23-26 [DERIVED]
  fails-if: a kind without a resulting status raises KeyError at line 319.
INVARIANT: ABSORBED_STATUSES = {"killed", "merged"} ⊆ values(RESULTING_STATUS) — shared/polymath_shared/adapter/hypotheses.py:25-27 [DERIVED]
  fails-if: absorbed hypotheses could transition again (guard 249-250 would pass wrongly).
INVARIANT: 1 ≤ len(proposals) ≤ max_hypotheses in generate — shared/polymath_shared/adapter/hypotheses.py:199-200 [DERIVED]
  fails-if: empty batch or over-cap batch rejected.
INVARIANT: alive + len(children) ≤ max_hypotheses for SPLIT (B-49: counts only non-absorbed) — shared/polymath_shared/adapter/hypotheses.py:275-278 [DERIVED]
  fails-if: ledger could grow past the cap via splits.
INVARIANT: every emitted transition has ≥1 `cause_refs` entry — shared/polymath_shared/adapter/hypotheses.py:261-262, 386-387 [DERIVED]
  fails-if: lineage_intact reports "no cause".
INVARIANT: every cited gap_id matches `^[A-Za-z0-9][A-Za-z0-9._:/-]{0,255}$` (B-22: refuse what Trail's wire refuses) — shared/polymath_shared/adapter/hypotheses.py:40-48 [DERIVED]
  fails-if: gap id stored verbatim is rejected later at gaps.compile on the Trail wire.
INVARIANT: trail_priors entries exist only when registry_snapshot_id is set — shared/polymath_shared/adapter/hypotheses.py:98-100 [DERIVED]
  fails-if: prior coordinate dangles without a snapshot reference.
INVARIANT: revision increments by 1 only on the first touch of a hid per apply call (`0 if hid in new_states else 1`) — shared/polymath_shared/adapter/hypotheses.py:238 [DERIVED]
  fails-if: multiple transitions on one hid in a single apply share one revision number; lineage_intact still passes (membership check only, 390-392).

## determinism & idempotency
determinism: DETERMINISTIC — ids are sha256 over inputs (`_h`, 51-52); `recorded_at` is injected by the caller (192, 225); no clock/random/uuid/db/env reads (imports 9-14) — shared/polymath_shared/adapter/hypotheses.py:9-14, 51-56 [DERIVED]
idempotency: generate SAFE (same run_id/step_id/ordinal → same hypothesis_id, 55-56); apply UNSAFE for blind replay — `bump` re-increments revisions (236-239) and a replayed SPLIT is explicitly refused via child-id collision ("a SPLIT is applied once per issuance", 283-285) — shared/polymath_shared/adapter/hypotheses.py:236-239, 283-285 [DERIVED]

## failure behaviour
- generate and apply accumulate all validation errors, then raise `HypothesisRejected(errors)` — batch is all-or-nothing, no partial state escapes — shared/polymath_shared/adapter/hypotheses.py:219-220, 367-368 [DERIVED]
- Exception message joins only the first 5 errors (`"; ".join(errors[:5])`); full list on `.errors` — shared/polymath_shared/adapter/hypotheses.py:19-20 [DERIVED]
- `assert_valid("hypothesis_state" / "hypothesis_transition")` raises on schema violation (behaviour defined in contracts) — shared/polymath_shared/adapter/hypotheses.py:187, 215, 293, 310, 364 [DERIVED]
- No try/except, no fallbacks — nothing is swallowed — shared/polymath_shared/adapter/hypotheses.py:1-397 [DERIVED]

## dumb-code flags
- `HYPOTHESIS_STATUSES` imported but never referenced in the body — shared/polymath_shared/adapter/hypotheses.py:13-14 [DERIVED]
- `[:24]` hash truncation duplicated at id minters — shared/polymath_shared/adapter/hypotheses.py:56, 60 [DERIVED]
- gap-id slice `hid[4:12]` duplicated in three minters — shared/polymath_shared/adapter/hypotheses.py:154, 156, 170 [DERIVED]
- Child ordinal formula `100 * (n + 1) + k` silently caps at 100 children per request slot n — shared/polymath_shared/adapter/hypotheses.py:283 [DERIVED]
- Default `max_hypotheses: int = 8` duplicated in generate and apply; B-49 comment says the SPLIT cap must count alive "as generate's headroom does", so the two defaults must stay equal — shared/polymath_shared/adapter/hypotheses.py:193, 227, 275-278 [DERIVED]
- Differing defaults: knowledge_support `evidence_role` = `"background"` vs gap `evidence_role` = `"behavior"` — shared/polymath_shared/adapter/hypotheses.py:85, 157, 171 [DERIVED]
- MERGE target status expression written twice (once in the transition record, once mutating `t2` after) — shared/polymath_shared/adapter/hypotheses.py:313-314 [DERIVED]
- `norm` lambda with `# noqa: E731` — shared/polymath_shared/adapter/hypotheses.py:133 [DERIVED]

## refactor notes
- Ids are content-addressed: `hypothesis_id` = `"hyp_" + sha256(run_id, step_id, ordinal)[:24]`, `transition_id` = `"hxt_" + sha256(run_id, hid, sequence, ordinal)[:24]` — changing prefix/hash length breaks every stored id — shared/polymath_shared/adapter/hypotheses.py:55-60 [DERIVED]
- `TRANSITION_KINDS`, `CITABLE_EVIDENCE_KINDS`, `PRIOR_EVIDENCE_KINDS`, `ORIGIN_ID_FIELDS` (aliased `ORIGIN_FIELDS`) come from `.contracts`; renaming here desyncs from the wire schemas — shared/polymath_shared/adapter/hypotheses.py:13-14, 38 [DERIVED]
- `TRAIL_IDENTIFIER` mirrors TrailSignal's `ResearchKnowledgeGapV1.gap_id` wire rules — loosening it re-opens B-22 — shared/polymath_shared/adapter/hypotheses.py:40-48 [DERIVED]
- SPLIT child ids embed `step["sequence"]` (B-20) and the store relies on the `cid in live` collision refusal for once-per-issuance semantics — shared/polymath_shared/adapter/hypotheses.py:281-285 [DERIVED]
- `context_view` ordering is the store's dict order (generation order, "never the run-id-dependent hash order"); callers depend on it — shared/polymath_shared/adapter/hypotheses.py:373-376 [DERIVED]
- Blast radius: research_gaps.py, semantic_view.py, service.py import this module (FACTS.importers); `lineage_intact` is used by tests + store as the invariant check — shared/polymath_shared/adapter/hypotheses.py:380-381 [DERIVED]

## VERIFY
```verify
grep -Fq 'THETA_KINDS = frozenset({"GENERATE", "REVISE", "SPLIT"})' shared/polymath_shared/adapter/hypotheses.py
grep -Fq 'ABSORBED_STATUSES = frozenset({"killed", "merged"})' shared/polymath_shared/adapter/hypotheses.py
grep -Fq 'return "hyp_" + _h(run_id, step_id, ordinal)[:24]' shared/polymath_shared/adapter/hypotheses.py
grep -Fq 'raise HypothesisRejected(errors)' shared/polymath_shared/adapter/hypotheses.py
test "$(grep -c -F 'max_hypotheses: int = 8' shared/polymath_shared/adapter/hypotheses.py)" -ge 2
grep -Eq '100 \* \(n \+ 1\) \+ k' shared/polymath_shared/adapter/hypotheses.py
grep -Fq 'TRAIL_IDENTIFIER = re.compile' shared/polymath_shared/adapter/hypotheses.py
! grep -Fq 'import random' shared/polymath_shared/adapter/hypotheses.py
```
