# unit: shared/polymath_shared/adapter/hypotheses.py
anchor: shared/polymath_shared/adapter/hypotheses.py:1-403

## purpose
Generic hypothesis ledger (ADR-0019 §3/§4): pure, deterministic functions over `HypothesisStateV1` / `HypothesisTransitionV1` dicts; persistence is the store's job. θ (the connected agent) may GENERATE/REVISE/SPLIT; φ (a TrailSignal deterministic verdict or a closed VALIDATE rule) applies selective pressure (KILL, MERGE, WEAKEN, STRENGTHEN, CONTRADICT, PROMOTE). Every transition names ≥1 cause; every revision keeps its parents. — shared/polymath_shared/adapter/hypotheses.py:1-6 [DERIVED]

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `HypothesisRejected` | class (ValueError) | `(errors: list[str])` | hypotheses.py:17-20 | importers below (module-level) |
| `hypothesis_id` | def | `(run_id: str, step_id: str, ordinal: int \| str) -> str` | hypotheses.py:59-60 | research_gaps.py, semantic_view.py, service.py (FACTS.importers) |
| `transition_id` | def | `(run_id: str, hid: str, sequence: int, ordinal: int) -> str` | hypotheses.py:63-64 | same importers |
| `generate` | def | `(run_id, step, proposals, *, registry_snapshot_id, recorded_at, max_hypotheses=8, parents=None, ordinal_base=0, known_origin_ids=None) -> (states, transitions)` | hypotheses.py:196-225 | same importers |
| `apply` | def | `(run_id, step, current, requests, *, actor, allowed_causes, recorded_at, registry_snapshot_id=None, max_hypotheses=8, known_origin_ids=None) -> (states, transitions)` | hypotheses.py:229-375 | same importers |
| `context_view` | def | `(current: dict[str, dict]) -> list[dict]` | hypotheses.py:378-382 | same importers |
| `lineage_intact` | def | `(states, transitions) -> list[str]` | hypotheses.py:385-403 | same importers |

## contracts

### generate — hypotheses.py:196-225
- in: `proposals` list of dicts; `step["context"]["evidence_refs"]` is the citable universe. — :202, :210 [DERIVED]
- pre: `1 <= len(proposals) <= max_hypotheses` (default 8) else error `between 1 and {max_hypotheses} hypotheses are required (got {n})`. — :203-204 [DERIVED]
- pre: every proposal has non-empty `statement` else `hypothesis {n}: statement is required`. — :207-208 [DERIVED]
- pre: every `supporting_evidence_ids` entry must be in `evidence_refs`, not a `PRIOR_EVIDENCE_KINDS` kind, and of a `CITABLE_EVIDENCE_KINDS` kind; ≥1 citable cause required. — :210-214, :71-92 [DERIVED]
- pre: `trail_priors` entries need a `registry_record_id` that is a prior in context AND a non-null `registry_snapshot_id`. — :95-107 [DERIVED]
- pre: knowledge-gap ids must match `TRAIL_IDENTIFIER` (`^[A-Za-z0-9][A-Za-z0-9._:/-]{0,255}$`). — :45, :217 [DERIVED]
- out: states at `revision: 0`, `status: "proposed"`, ids `"hyp_" + sha256(run_id:step_id:ordinal)[:24]`; GENERATE transitions with hardcoded `actor="theta"`, `reason_code="THETA_GENERATED"`. — :176, :215, :221-222, :59-60 [DERIVED]
- post: any accumulated error → `HypothesisRejected(errors)`; nothing returned (all-or-nothing). — :223-224 [DERIVED]

### apply — hypotheses.py:229-375
- in: `current` = hypothesis_id → latest state; `requests` dicts with `kind`, `hypothesis_id`. — :229-233 [DERIVED]
- pre: `kind` in `TRANSITION_KINDS` and `!= "GENERATE"`; `hid` in `live`; status not in `ABSORBED_STATUSES` (`{"killed", "merged"}`); `actor` in `("theta", "phi", "runtime")`; θ only `THETA_KINDS`. — :249-258 [DERIVED]
- pre: every `cause_refs` entry: kind in `CAUSE_KINDS` AND `allowed_causes[id] == kind`; ≥1 cause required. `field_evidence_ids` must map to `"field_evidence"` in `allowed_causes`. — :260-271 [DERIVED]
- SPLIT: needs `children`; `alive + len(children) <= max_hypotheses` (alive = non-absorbed, B-49); child id = `hypothesis_id(run_id, step_id, f"{int(step['sequence'])}:{100 * (n + 1) + k}")` (B-20); refuses if child id already in ledger (`a SPLIT is applied once per issuance`); children inherit parent origin fields, support falls back to `prev["knowledge_support"]`, priors and field ids carry over; parent status → `"split"`. — :276-304 [DERIVED]
- MERGE: target must be live, non-absorbed, ≠ self; support/field/contradictions unioned into target; target gets a `"REVISE"` transition with `reason_code="MERGED_IN"` and status `"revised"` if it was `"proposed"`; source status → `"merged"`. — :306-322 [DERIVED]
- REVISE: unknown `changes` keys refused wholesale (`cannot be revised (revisable: ...); nothing of this revision was applied`); `assumptions`/`falsifiers` = list of non-empty strings (replace); `knowledge_gaps` UPSERT via `_merge_gaps`; `contradictions` only append with citable `evidence_ids`; origin fields via `_origin`. — :326-360 [DERIVED]
- gap A-09: a θ REVISE on a status in `PHI_VERDICT_STATUSES` keeps `prev["status"]` — θ never erases φ's verdict. — :324-325 [DERIVED]
- CONTRADICT: requires `contradictions` entries with `evidence_ids`. — :361-366 [DERIVED]
- out: `(list(new_states.values()), transitions)`; revision bumps once per hid per call; errors → `HypothesisRejected`. — :240-244, :373-375 [DERIVED]

### context_view — hypotheses.py:378-382
- in: hypothesis_id → latest state; out: `{hypothesis_id, revision, status, statement}` for non-absorbed hypotheses, in the store's iteration order. — :378-382 [DERIVED]

### lineage_intact — hypotheses.py:385-403
- in: states + transitions; out: list of error strings. Checks: every transition has ≥1 cause_ref; every state revision has a producing transition; GENERATE-transition parents appear in the state's `parent_hypothesis_ids`. — :388-401 [DERIVED]

## effect surface
- Postgres tables: none (FACTS `tables_read: []`, `tables_written: []`). — FACTS [DERIVED]
- Qdrant / files / network / subprocess / env flags: none; only imports `hashlib`, `re`, `typing.Any`. — hypotheses.py:9-11 [DERIVED]
- Persistence is explicitly the store's job. — hypotheses.py:2 [DERIVED]

## invariants
- INVARIANT: hypothesis_id length = `"hyp_" + 24 hex chars` — hypotheses.py:59-60 [DERIVED]
  fails-if: stored ids or ledger lookups keyed on the 24-char hash break.
- INVARIANT: transition_id = `"hxt_" + 24 hex chars` — hypotheses.py:63-64 [DERIVED]
  fails-if: transition dedup/collision checks in the store stop matching.
- INVARIANT: actor ∈ `{"theta", "phi", "runtime"}` — hypotheses.py:258 [DERIVED]
  fails-if: unknown actor requests are rejected, so a new actor name must be added here first.
- INVARIANT: statuses `"killed"`/`"merged"` accept no further transitions — hypotheses.py:27, :253 [DERIVED]
  fails-if: absorbed hypotheses re-entering the ledger would break `context_view` liveness assumptions (:381).
- INVARIANT: every transition carries ≥1 `cause_refs` — hypotheses.py:265-266, :392-393 [DERIVED]
  fails-if: `lineage_intact` reports `no cause`; ancestry evidence guarantee (:5) violated.
- INVARIANT: `alive + len(children) <= max_hypotheses` (default 8) for SPLIT — hypotheses.py:280-282 [DERIVED]
  fails-if: ledger exceeds the bounded context issued to steps.
- INVARIANT: `contradictions` list only grows (append + dedup, never replace) — hypotheses.py:358, :366 [DERIVED]
  fails-if: dropped contradictions lose the record of what changed a hypothesis (:4-5).
- INVARIANT: gap identity preserved across REVISE (UPSERT by `gap_id` or normalised question; nothing deleted) — hypotheses.py:130-162 [DERIVED]
  fails-if: gap ids churn and downstream Trail gap compilation loses continuity.
- INVARIANT: θ REVISE leaves any status in `PHI_VERDICT_STATUSES` unchanged — hypotheses.py:28-31, :324-325 [DERIVED]
  fails-if: θ overwrites φ's verdict, reopening gap A-09.
- INVARIANT: priors (`PRIOR_EVIDENCE_KINDS`) are attachable but never citable as evidence — hypotheses.py:79-81, :99-100 [DERIVED]
  fails-if: registry coordinates pollute the evidence chain.

## determinism & idempotency
determinism: DETERMINISTIC — pure dict functions; ids are sha256 of caller-supplied parts (:55-64); `recorded_at` is a parameter, no clock/random/uuid/db/env read anywhere in the module. [DERIVED]
idempotency: SAFE — identical inputs return identical outputs (pure, caller dicts not mutated — `live = dict(current)` :237, `gaps = [dict(g) ...]` :133). Re-applying a SPLIT against an updated ledger is explicitly refused by the existing-child-id check (:288-289). [INFERRED: purity implies output stability; the SPLIT guard is the visible re-entry defense]

## failure behaviour
- `HypothesisRejected(ValueError)`: raised by `generate` (:223-224) and `apply` (:373-375) with the full accumulated `errors` list on `.errors`; message is `"; ".join(errors[:5])` — only the first 5 errors surface in `str(exc)`. — :17-20 [DERIVED]
- Batches are all-or-nothing: any error rejects the whole call, no partial states/transitions returned. — :223-224, :373-374 [DERIVED]
- `assert_valid("hypothesis_state", st)` at :219, :297, :314, :370 and `assert_valid("hypothesis_transition", t)` at :191 delegate schema validation to `contracts` (its exception type is not visible here). [DERIVED]

## dumb-code flags
- Unused import: `HYPOTHESIS_STATUSES` imported from `.contracts` but never referenced in the module body. — hypotheses.py:13 [DERIVED]
- Dead map entries: `RESULTING_STATUS` keys `"GENERATE"`, `"SPLIT"`, `"MERGE"` are never read — `apply` refuses `GENERATE` (:249) and the SPLIT/MERGE branches hardcode `"split"` (:301) / `"merged"` (:319); `generate` hardcodes `"proposed"` (:222). Only the `RESULTING_STATUS[kind]` lookup at :323 runs, for REVISE/KILL/WEAKEN/STRENGTHEN/CONTRADICT/PROMOTE. [INFERRED: from the control-flow branches]
- Doc/body mismatch: `lineage_intact` docstring promises "every child names its parent" and "a split/merge parent appears in its children's parent lists" (:386-387) but the body implements only the no-cause, revision-produced and GENERATE-parent checks (:388-401). — hypotheses.py:385-403 [DERIVED]
- Magic numbers: hash truncation `[:24]` (:60, :64); SPLIT ordinal `100 * (n + 1) + k` (:287); gap id slice `hid[4:12]` (:158, :160, :174); error message truncation `errors[:5]` (:19).
- Duplicated default: `max_hypotheses: int = 8` appears in both `generate` (:197) and `apply` (:231) — change one without the other and the cap disagrees between creation and SPLIT.
- `norm = lambda q: ...` with `# noqa: E731` inline. — :137 [DERIVED]
- MERGE emits kind `"REVISE"` + `reason_code="MERGED_IN"` for the surviving target (:315-317) — kind does not match operation name; consumers filtering transitions on kind will not see MERGE on the target.
- `generate` hardcodes `actor="theta"` (:221) regardless of caller.

## refactor notes
- Importers `shared/polymath_shared/adapter/research_gaps.py`, `semantic_view.py`, `service.py` (FACTS.importers) break on any rename of `generate`, `apply`, `context_view`, `lineage_intact`, `HypothesisRejected`. — FACTS [DERIVED]
- ID formats are persistence/wire-visible: `"hyp_"` ids (:60), `"hxt_"` ids (:64), `gap_{hid[4:12]}_{n}` (:160). Gap ids cross TrailSignal's closed wire (`ResearchKnowledgeGapV1.gap_id`); `TRAIL_IDENTIFIER` (:44-45) must keep matching Trail's rules or B-22 returns.
- SPLIT child ordinal scheme `f"{int(step['sequence'])}:{100 * (n + 1) + k}"` (:287) is the issuance-uniqueness contract (B-20); changing it re-mints child ids and reopens the dropped-second-revision bug.
- φ-only statuses list `PHI_VERDICT_STATUSES` (:31) and `RESULTING_STATUS` (:25-26) encode the A-09 actor split; touching them changes who may move which status.
- `max_hypotheses` default 8 is duplicated (:197, :231); a change must update both (or their callers override).

## VERIFY
```verify
grep -Fq 'THETA_KINDS = frozenset({"GENERATE", "REVISE", "SPLIT"})' shared/polymath_shared/adapter/hypotheses.py
grep -Fq 'ABSORBED_STATUSES = frozenset({"killed", "merged"})' shared/polymath_shared/adapter/hypotheses.py
grep -Fq 'TRAIL_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,255}$")' shared/polymath_shared/adapter/hypotheses.py
test "$(grep -c -F 'max_hypotheses: int = 8' shared/polymath_shared/adapter/hypotheses.py)" -ge 2
test "$(grep -c -F 'raise HypothesisRejected' shared/polymath_shared/adapter/hypotheses.py)" -ge 2
grep -Fq 'changes["status"] = prev["status"]' shared/polymath_shared/adapter/hypotheses.py
grep -Fq 'return "hyp_" + _h(run_id, step_id, ordinal)[:24]' shared/polymath_shared/adapter/hypotheses.py
test "$(grep -c -F 'HYPOTHESIS_STATUSES' shared/polymath_shared/adapter/hypotheses.py)" -ge 1
```
