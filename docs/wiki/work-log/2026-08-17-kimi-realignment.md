---
change_id: kimi-architecture-realignment-v1
owner: worker
date: 2026-08-17
status: in-progress
architecture_impact: realigns-candidate-generation-to-kimi-ud-role-binding
last_reviewed: 2026-08-17
---

# KIMI-ARCHITECTURE-REALIGNMENT-V1

## Contract

Realign extraction to the original Kimi two-pass GLiNER + deterministic
predicate compiler architecture per ADR-0016. The core change:
candidate arguments derive from the UD dependency tree (not left×right
positional pairing), PropBank ARG0/ARG1 roles are assigned to
endpoints, and type compatibility runs AFTER structural candidates
exist. Production default stays legacy_v1 until separately qualified.

## §0 Baseline (frozen at start)

HEAD: 1b4dc96. Tree clean. Suite: 296 passed / 53 skipped.
I4 baseline (legacy_v1 + rescue-D): TP=12 FP=5 FN=14 P=.706 R=.462.
Model: urchade/gliner_medium-v2.1 @ 40ec4193, threshold 0.5.

## §0a KIMI-REALIGNMENT-COMPLETION-V1 authorization

New directive received 2026-08-17: finish the Kimi extraction architecture
end-to-end. Authorized scope: complete PropBank role assignment, make
VN/PB/FN/SemLink active compiler inputs, role-based direction,
active/passive equivalence, coordination, type-precheck position,
full signature validation, dev test matrix, performance/microbench,
frozen I4 comparison, and decision branch. Hard freeze list from the
directive is respected (model, thresholds, signatures, I4 gold/scorer,
retrieval, etc.). Production default stays legacy_v1 unless quality bars
and sealed I5 explicitly authorize promotion.

## Changes

(in progress)

## Changes

- workers/workers/kimi_candidates.py: UD-anchored candidate generation
  (trigger head → syntactic dependents → entity mapping → structural
  argument candidates), type precheck AFTER structural candidates,
  bounded linear recall fallback, binding_source discipline.
- workers/workers/extract_worker.py: dispatch to kimi_v1 or legacy_v1
  via POLYMATH_RELATION_PIPELINE env (default legacy_v1).
- tests/determinism/test_kimi_candidates.py: 6 tests (UD binding,
  structural candidate before type check, no explosion, fallback,
  token mapping, dispatch).
- eval/kimi_realignment_v1/REPORT.md: full measurement report.

## Proof

- 6 unit tests green; full suite 296+6=302 passed / 53 skipped.
- Frozen I4: legacy TP=12/FP=5/FN=14 P=.706 R=.462 → kimi TP=11/FP=5/
  FN=15 P=.688 R=.423. No P/R improvement (quality blocked on model
  typing), but diagnostic honesty improved: key sentence now shows
  TYPE_PRECHECK_IMPOSSIBLE with structural context instead of the
  misleading SUBJECT_ENDPOINT_UNAVAILABLE. No FP regression. No
  explosion. All safety gates held.
- Frozen evidence restored byte-identically (d26a1c37...).

## Rejected claims

- No claim that kimi_v1 improves extraction quality: it does not on
  frozen I4. The architecture is correct; the remaining bottleneck
  is the frozen model's type classification.
- Not claiming the Kimi invariants are all PASS: architecture wiring
  is in place, but full qualification against frozen I4 and the complete
  dev matrix is pending.

## Open contract gaps (remaining)

- LexicalSemanticEvidence object (Phase 8) not yet created as a single
  normalized compiler input; role/voice/VN/FN/SemLink data currently
  lives on RelationCandidate fields.
- Development test matrix (Phase 16) partially covered by unit tests;
  full fixture matrix not yet executed.
- QUALITY-PROBE-001 full causal trace partially demonstrated; remaining
  blocker is the frozen type/signature semantics, not architecture.
- I4 frozen comparison (Phase 21) requires live services and is queued.
- I5 remains not authorized.

## In-progress completion work

- shared/polymath_shared/rulepack/role_assignment.py: new module
  for PropBank role inventory, voice-aware ARG0/ARG1 assignment, and
  VN/FN/SemLink compatibility checks.
- shared/polymath_shared/rulepack/compiler.py: role-based direction
  wired into `_oriented_pair`; `compile_relation_kimi()` uses VN/PB/FN/
  SemLink as converging predicate-selection evidence.
- shared/polymath_shared/contracts.py: RelationCandidate.assigned_roles
  and semlink_mapping fields added.
- workers/workers/candidates.py: `_lookup_for` returns PropBank argument
  inventory and SemLink mapping for typed triggers (e.g., "found"
  -> establish.01).
- workers/workers/kimi_candidates.py: UD argument discovery fixed for
  passive agents; type precheck now considers both orientations to let
  role-based inversion pass; assigns PropBank roles; records VN/FN/
  SemLink checks per candidate.
- workers/workers/extract_worker.py: dispatches to `compile_relation_kimi`
  when POLYMATH_RELATION_PIPELINE=kimi_v1.
- tests/determinism/test_kimi_role_direction.py: active/passive
  equivalence + role-based direction tests.
- scripts/scaffold_polymath_v4.py: declared role_assignment.py and
  test_kimi_role_direction.py in TREE.

## Phase 5 — observability realignment (plan Phase 5 / directive Phase 16, 17, 28)

Implements the plan's Phase 5 vocabulary. Prerequisite for qualification
criterion #14 ("observability explains every terminal outcome") and for
the Phase 6 QUALITY-PROBE rerun, which cannot be read without it.

### Changes

- `shared/polymath_shared/observability.py`: registered the kimi_v1
  vocabularies `UD_BINDING` (4 codes), `ROLE` (6), `TYPE_PRECHECK` (4);
  `ALL_CODES` 61 -> 77. Added `STEP_CODES` = non-terminal step outcomes,
  and `binding_discipline()` mapping `BindingSource` mechanisms to the
  directive Phase 17 tiers (UD_PRIMARY / SAFE_FALLBACK / BOUNDED_RECALL).
  `FIRST_LOSS_STAGES` gained `ud_binding`, `role_assignment`,
  `type_precheck`.
- `workers/workers/extract_worker.py`: `_STAGE_BY_CODE` /
  `_EVENT_TYPE_BY_STAGE` route each code to its owning stage; step events
  get their own event types (`binding` / `role` / `type_precheck`) so
  summary mode drops them and the first-loss funnel never counts them.
  Every event naming a `binding_source` also carries its discipline tier.
- `workers/workers/kimi_candidates.py`: emits UD_SUBJECT_BOUND /
  UD_OBJECT_BOUND / UD_OBLIQUE_BOUND / UD_NO_ARGUMENT_IN_SLOT at the UD
  step (before any recall net), TYPE_PRECHECK_PASS/FAIL per pair, and
  ROLE_ARG{0,1,2}_ASSIGNED / ROLE_NO_ROLESET / ROLE_ORIENTATION_INCOMPLETE
  per assigned role.

### Defects found and fixed while wiring

- `trig_head` was assigned only inside `if tokens:` but read
  unconditionally when building `LexicalSemanticEvidence`. Because Python
  loop variables outlive their block, a trigger in a token-less sentence
  did not raise — it silently reused the PREVIOUS sentence's head token.
  Now reset to `None` per evidence and reused rather than recomputed.
- `binding_source` was a bare `str` on three paths and a `BindingSource`
  enum on two others; the two recall branches had identical if/else arms.
  Normalized to the enum throughout.
- `TYPE_PRECHECK_IMPOSSIBLE` was emitted but never registered in
  `ALL_CODES`. Renamed on emission to the plan-specified
  `TYPE_PRECHECK_FAIL`; the old code stays registered so trace rows
  recorded before this gate still validate.

### Proof

- Suite 321 passed / 53 skipped (was 302/53). 14 new tests in
  `tests/determinism/test_kimi_observability_phase5.py`.
- Observer neutrality: candidate fingerprint byte-identical with observer
  attached vs `None` (`4f53cda18c2baa0c`). Off mode records nothing.
- Trace on `John founded Acme.` — UD_SUBJECT_BOUND[John] ->
  UD_OBJECT_BOUND[Acme] -> TYPE_PRECHECK_PASS(forward) ->
  CANDIDATE_CREATED -> ARG0=John(nsubj), ARG1=Acme(dobj).
- Trace on `Acme was founded by John.` — ARG0=John(agent),
  ARG1=Acme(nsubj:pass): the by-agent supplies ARG0, not the surface
  subject. A first cut derived `syntactic_path` from the role label
  alone and mislabelled every passive; `_role_path()` now resolves the
  path from the entity that actually filled the role, pinned by
  `test_passive_voice_role_paths_are_not_mislabelled_by_role_order`.
- `make guards`: preflight ok, repo guard ok, wiki ok.

### Rejected claims

- No claim that Phase 5 changes extraction quality. It is observability
  only; P/R on frozen I4 are untouched by construction (neutrality proof
  above). Production default remains legacy_v1.
- No claim that criterion #14 is now satisfied. The vocabulary exists and
  every code the kimi_v1 lane emits has an owning stage, but "explains
  every terminal outcome" is only demonstrable against a real corpus —
  that is the Phase 6 QUALITY-PROBE rerun, not yet run.

### Follow-on

- The QUALITY-PROBE narrative in `eval/kimi_realignment_v1/REPORT.md`
  cites `TYPE_PRECHECK_IMPOSSIBLE` for the key sentence. That code is no
  longer emitted; the probe must be re-run and the report updated to the
  Phase 5 vocabulary before Phase 6 conclusions are quoted.

## Phase 6 (partial) — frozen I4 with rescue ON + spaCy, four arms

Authorized 2026-08-18: re-measure frozen I4 with the rescue lane enabled
and the syntax provider live. Frozen artifacts unchanged (freeze gate
verified 11 files before the first arm). No production default changed.

### Results

| arm | pack | pipeline | rescue | TP | FP | FN | P | R |
|---|---|---|---|---|---|---|---|---|
| I4 acceptance (documented) | 1.2.0 | legacy_v1 | off | 10 | 10 | 16 | 0.500 | 0.385 |
| A1 reproduction | 1.2.0 | legacy_v1 | on | 12 | 6 | 14 | 0.667 | 0.462 |
| A2 baseline | 1.3.0 | legacy_v1 | on | 12 | 5 | 14 | 0.706 | 0.462 |
| A3 kimi | 1.3.0 | kimi_v1 | on | 11 | 5 | 15 | 0.688 | 0.423 |

A1 reproduces I4R-C exactly; A2 reproduces the I4R combined closeout
exactly (TP 12 / FP 5 / FN 14, provenance 16/16). The harness is sound.
A3 reproduced twice, deterministic. Entity tiers constant across all
arms (raw 0.818 / mention 0.818 / referential 1.000 / graph 1.000).
Envelope 7/8 and must-not 18/18 held in every arm.

### What the Phase 5 trace shows (A3, 691 events)

- **Binding discipline: UD_PRIMARY 55.4% / BOUNDED_RECALL 43.2% /
  SAFE_FALLBACK 1.4%.** With spaCy fully live, 43% of bindings still
  fall through to the linear recall net — the realigned lane drives only
  half its own traffic.
- **UD slot fill 133 bound vs 145 UD_NO_ARGUMENT_IN_SLOT** (47.8%): the
  tree fails to fill a slot more often than it fills one.
- **PropBank engagement: 38 candidates, 25 ROLE_NO_ROLESET**, 11 ARG0,
  7 ARG1, 0 ARG2. Roles fire on ~29% of candidates — directive invariant
  I5 ("rolesets must be operational, not decorative") is measurably NOT
  satisfied, and is now measurable for the first time.
- **Terminal loss: argument_binding 60 (SUBJ 47 / OBJ 13), type_precheck
  25.** Argument binding is ~70% of terminal loss; the type check is not
  the dominant killer.

### Defect found and fixed during the run

`extraction_contracts()` omitted the relation pipeline, so legacy_v1 and
kimi_v1 runs of the same corpus at the same rule pack produced
byte-identical envelopes. Because `trace_event_id` is a content hash and
the insert is ON CONFLICT DO NOTHING, **the second arm's events were
silently dropped** — A3's first run recorded 0 FACT_ACCEPTED and 1
compiler event in the table while its own stage artifact showed 23
FACT_ACCEPTED. An A/B was unreadable from the trace table.
Compounding it, `flush()` returned `len(rows)` (attempted) rather than
the inserted count, so the artifact over-reported what it had written.
Both fixed; `relation_pipeline` is now an envelope contract field and
`flush()` returns `cur.rowcount`. Pinned by
`test_envelope_distinguishes_extraction_arms`. A3 re-run after the fix
produced identical scores and a complete 691-event trace.

### Rejected claims

- No claim that rescue+spaCy should become the production default. This
  is one frozen holdout; P 0.706 remains far below the 0.95 bar.
- No claim that kimi_v1 is ready. It is 1 TP behind legacy_v1 on the
  same config, and the trace shows why it cannot yet be judged on
  architecture: it is not the mechanism in play 43% of the time.
- Entity `wrong_type` moved 5 -> 4 between the two A3 runs; scores were
  identical. Not investigated, recorded as observed.

## Phase 6 (cont.) — A5: semantic_v2 chunker (single-variable vs A2)

Arms A1-A4 all ran `chunker=legacy_v1` (production default), leaving the
FN waterfall's class B (markdown header-merged sentences, 4/14 FN)
untouched. A5 changes ONLY the chunker.

| arm | chunker | TP | FP | FN | P | R | envelope | entity raw |
|---|---|---|---|---|---|---|---|---|
| A2 baseline | legacy_v1 | 12 | 5 | 14 | 0.706 | 0.462 | 7/8 | 0.818 |
| A5 | semantic_v2 | 14 | 11 | 12 | 0.560 | **0.538** | **6/8** | 0.855 |

The heading fix delivered its predicted recall: +2 TP, FN 14 -> 12,
entity discovery 0.818 -> 0.855, provenance 25/25. **But precision
collapsed 0.706 -> 0.560 (FP 5 -> 11) and the out-of-envelope gate
REGRESSED 7/8 -> 6/8** (new violation B07: "the company employs two new
surgeons"). must-not held 18/18.

### Every FP is an identity failure, not a relation failure

All 11 FPs classified by hand from `fp_details`:

- **4 are paired FN+FP on the SAME fact**, differing only in span
  identity: `uses northvale health network -> carechart emr platform`
  vs gold `CareChart EMR`; `developed crestline -> ...` vs
  `Crestline Automation`; `depends_on mentor engine -> ...` vs
  `Mentor assessment engine`; `located_in the company -> raleigh` vs
  `Brightpath Learning`.
- **3 more are boundary contractions** of the same class
  (`crestline`, `corval`).
- **2 are unresolved definite descriptions** (`the company`).
- **2 are generic plurals/heads** (`regional dispatchers`,
  `container platform`) — both envelope violations.

**Zero FPs are a wrong predicate or a wrong direction.** The relational
layer is producing correct structure; the failures are span boundary and
referential resolution — i.e. entity admission, not relation extraction.

### Estimated headroom (arithmetic, not measured)

Resolving the 4 paired boundary/identity cases alone would give
TP 18 / FP 7 / FN 8 -> P 0.720, R 0.692 — R essentially at the 0.70 bar.
Also abstaining on the definite-description and generic-plural surfaces
would reach roughly P 0.857 at the same recall. Neither is measured; both
require a gate that can express "the relation is right, the span identity
is not", which no current outcome class encodes.

### Rejected claims

- **semantic_v2 is NOT qualified by this run.** It trades precision for
  recall and regresses a safety gate (envelope 7/8 -> 6/8). Production
  default stays legacy_v1; no promotion is implied or requested.
- The headroom figures above are arithmetic on the observed FP/FN sets,
  not a measured configuration.
