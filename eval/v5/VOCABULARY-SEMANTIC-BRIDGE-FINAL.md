# VOCABULARY SEMANTIC BRIDGE — REPAIR + PRODUCTION QUALIFICATION (V1)

Date: 2026-08-28 · Branch `architecture/evidence-first-v5`

**Outcome in one line: the contract regression is REAL and is now repaired
and pinned; the family-assembly SEMANTICS fail qualification, so
production backfill is NO-GO.**

---

## HEADLINE

Two independent defects were found, not one.

1. **Contract regression (REPAIRED).** The vocabulary layer produced zero
   families because a refactor dropped the support identity from the
   caller's rows. Fixed, tested, callsite-pinned, mutation-verified.
2. **Semantic mechanism failure (NOT repairable by contract fix).** With
   the contract repaired the layer *runs*, and what it produces is wrong:
   it merges concepts on **co-occurrence**, which it cannot distinguish
   from **synonymy**. 6 of 7 adversarial cases are wrong merges, and on
   real production data it collapses 10,688 concepts into 3 families —
   one containing 10,060 members.

The layer was validated at **24 parent summaries**. Production is
**1,775 parent neighbourhoods**. Single-linkage union over shared support
does not survive that change of scale.

---

## REQUIRED OUTPUT

```
START_HEAD:   5ddf708d8dc80d44a9e4d03b468f207b7eff8ee9
FINAL_HEAD:   (see git log; commit 1 = 273ac62)
TREE_CLEAN:   YES

ROOT_CAUSE:
  EXPECTED    each concept's support keyed on the PARENT EVIDENCE
              NEIGHBOURHOOD (one parent chunk = one independent support)
  ACTUAL      builder read `p.get("parent_id") or ps.get("artifact_id")`;
              production rows carried neither -> sid = None for EVERY row
  CONSEQUENCE all 1,775 parent neighbourhoods collapsed onto one shared
              sentinel support identity
  GUARD       independent_support_count >= 2 (precision guard)
  RESULT      the single collapsed family scored support 1 and was
              silently rejected -> 0 families, 0 aliases, NO ERROR

REGRESSION_COMMIT:              dff12ef (2026-08-24)
                                "P2 SUMMARY-WORKER-FLEET-V1 ... DB-driven assembly"
PREVIOUS_WORKING_VALIDATION:    f267d0e (2026-08-23) "corpus mapping validation:
                                multi-doc waterfall (4 docs/24 parent summaries)
                                — lineage TRUE, spread weighting TRUE,
                                contamination cases PASS; vocabulary
                                min-support guard=2 shipped"
                                (built in 98fb0da, guard tightened in b94db70)

OLD_PRODUCTION_ROW_CONTRACT:    {"payload": {"parent_id": ..., "concepts": [...]}}
CURRENT_BROKEN_ROW_CONTRACT:    {"summary_id","entities","concepts","summary"}
FINAL_ROW_CONTRACT:             {"summary_id","support_id","entities","concepts","summary"}
SUPPORT_IDENTITY:               parent_id (parent evidence neighbourhood)
                                — explicitly NOT summary_id

PARENT_SUMMARIES_TOTAL:         3,015 (cysa-study-v1)
PARENT_SUMMARIES_WITH_CONCEPTS: 3,012
DISTINCT_CONCEPTS:              10,688

BEFORE (production, cysa-study-v1):
  concept_families:   0
  concept_vocabulary: 0
  concept_aliases:    0

CANARY_AFTER (vocab-canary-v1, 2 docs through the REAL pipeline):
  concept_families:   1
  concept_vocabulary: 0     <-- see FINDING 3
  concept_aliases:    8

MIN_SUPPORT_2:                  PASS (preserved, never lowered)
DUPLICATE_SUPPORT_GUARD:        PASS (two summaries of one parent -> support 1)
DERIVED_SUMMARY_SUPPORT_GUARD:  PASS (parent + its document summary -> support 1)

FAMILY_QUALITY (hard-negative panel, 7 cases):
  good:         1
  questionable: 0
  wrong_merge:  6

SCALE (real cysa-study-v1 parent summaries):
  100  parents /   506 concepts /   128k pairs /  0.0s / 5 families
  250  parents /  1144 concepts /   654k pairs /  0.2s / 4 families
  500  parents /  2176 concepts /  2.37M pairs /  0.8s / 3 families
  1000 parents /  4061 concepts /  8.25M pairs /  3.5s / 2 families
  2000 parents /  7520 concepts / 28.28M pairs / 13.9s / 3 families
  3015 parents / 10688 concepts / 57.12M pairs / 31.2s / 3 families
  peak RSS 53 -> 65 MB

SCALING_VERDICT: FAIL — quadratic in distinct concepts (time tracks
  pair count exactly), and semantically ANTI-SCALING: family count FALLS
  as evidence grows (5 -> 4 -> 3 -> 2). A healthy vocabulary layer yields
  MORE families with more data.

ASK_BEFORE (cysa-study-v1, 0 families):  related_concepts: 0
ASK_AFTER  (vocab-canary-v1, 1 family):  related_concepts: 0   <-- FINDING 3

SEMANTIC_BRIDGE_EXAMPLES: see FINDING 2 (only 1 of 7 correct)

SUMMARY_ROUTING:      PASS (panel below; unchanged by this work)
ABSTENTION:           PASS
EVIDENCE_GROUNDING:   PASS (no vocabulary output became citation evidence)

CHILD_BOILERPLATE_DEFECT: OBSERVED (pre-existing, out of scope — examples below)

REACH_P2:        REJECTED / UNCHANGED (file untouched, no production imports added)
FAST_CHANGED:    NO
HYBRID_CHANGED:  NO
GRAPH_CHANGED:   NO

FAST_FUTURE_EVAL:   NO_CHANGE (see PHASE 12)
HYBRID_FUTURE_EVAL: NO_CHANGE
GRAPH_FUTURE_EVAL:  NO_CHANGE

CANARY_GATE:          FAIL (semantic contamination gate)
PRODUCTION_BACKFILL:  NOT_RUN (blocked by gate)
PRODUCTION_COUNTS_AFTER: unchanged — families 0 / vocabulary 0 / aliases 0

PRODUCTION_GO: NO
```

---

## FINDING 1 — the contract regression (REPAIRED)

Reproduced at HEAD using the worker's exact assembly path: **0 families**
from 3,015 parents / 10,688 concepts in 47.3 s. Supplying only the
missing support identity, families appear. Root cause table above.

**Support identity was proved, not assumed.** The tempting one-line fix —
swapping `parent_id` for the `summary_id` the caller already had — is
**wrong**: 3,016 `parent_summaries` rows cover only **1,775 distinct
`parent_id`s** (1,241 parents carry two summary rows under the same
contract version). Keying support on `summary_id` would let one evidence
neighbourhood corroborate itself and clear the `>=2` guard — the exact
failure that guard exists to prevent. Pinned by
`test_f2_summary_id_is_not_accepted_as_support_identity`.

Repair: explicit `support_id` in the worker's SELECT/assembly; explicit
`_support_identity()` in the builder that raises typed
`MissingSupportIdentity` rather than collapsing. `min_support = 2`
untouched.

**Test blind spot closed.** The historical suite fed the pre-refactor
payload shape, so it stayed green while production was dead — the exact
trap `AGENTS.md` records ("entry-point wiring drift ... pin call sites").
New suite pins the current production shape (matrix A–G) plus a
**callsite pin** that reads the worker source. The pin was
**mutation-tested**: reintroducing the original refactor makes it fail,
restoring makes it pass.

## FINDING 2 — the family mechanism fails qualification (BLOCKING)

`build_concept_families` joins two terms into one family when their
support sets intersect — i.e. when they appear in the same parent. That
is **co-occurrence**, and the layer uses it as a proxy for **synonymy**.
At 24 summaries the two coincide often enough to look correct. At corpus
scale they do not.

**Canary (real pipeline, 2 documents, 15 children, 5 parents):** one
family, canonical `"centralized logging security"`, aliases:

```
EDR, SIEM, Detection Case, Response Scenario,
"Detection Engineering Handbook ## Endpoint Telemetry",
"Incident Response Field Guide ## The", "Response Lifecycle The",
"Tooling During Response Endpoint"
```

**EDR and SIEM are declared aliases of one another.** This is exactly the
behaviour the mission forbids ("vocabulary may NOT turn EDR into
unrelated concepts merely because words overlap").

**Hard-negative panel — 6 of 7 wrong:**

| case | result | verdict |
|---|---|---|
| IR acronym collision | `incident response` ← alias `infrared spectroscopy` | WRONG_MERGE |
| java homonym | canonical `coffee bean`, aliases `java`, `programming language` | WRONG_MERGE |
| org vs product | `microsoft` ← aliases `microsoft word`, `microsoft sentinel` | WRONG_MERGE |
| distinct tech co-occurring | `edr` ← alias `siem` | WRONG_MERGE |
| front-matter junk | `about the author` ← alias `siem` | WRONG_MERGE |
| heading fragments | `## page 12` ← alias `chapter 3` | WRONG_MERGE |
| genuine alias pair | `edr` ← alias `endpoint detection and response` | GOOD |

**Why no threshold fixes this.** The one correct case and the EDR/SIEM
failure are *structurally identical* to the algorithm: two terms sharing
two parents. There is no lexical, morphological or distributional signal
in the mechanism to separate them. This is a representational
deficiency, not a tuning problem — which is why, per the mission's
PRECISION_RULE, no compensating heuristics were added.

**Production-scale confirmation.** With the contract repaired, real data
yields 3 families: sizes 11, 13, and **10,060 members** (support 1,684,
canonical `"nan nan"`). Merge drivers are hub concepts appearing across
the corpus — `kql` (110 parents), `microsoft sentinel` (98), `figure`
(91, junk), `tcp` (83) — which chain everything via transitive closure.

## FINDING 3 — a SECOND producer/consumer gap (ASK cannot light up)

Even with families populated, `ASK.related_concepts` stayed **0** on the
canary. Cause: `run_vocabulary_ticket` writes `concept_families`
(`canonical_name`), `concept_aliases`, `concept_support` and
`summary_artifacts` — but never `definition`, and never
`concept_vocabulary` at all. The consumer
(`orchestrator/api/ask.py::_concept_graph`) matches **only** on
`definition`:

```python
words = set(_norm(definition or "").split())
if lowered & words or any(_norm(n) in _norm(definition or "") ...)
```

`definition` is NULL for every row, so the predicate can never match.
Backfilling would therefore *not* have restored ASK behaviour. This is an
independent defect and is left unrepaired: repairing it only matters if
FINDING 2 is resolved first.

## PHASE 9 — SUMMARY ROUTING (PASS, unchanged)

| query type | evidence | docs |
|---|---|---|
| exact lookup | 10 | 5 |
| paraphrase | 10 | 5 |
| enumeration | 24 | 5 (depth profile, prior commit) |
| comparison | 10 | 5 |
| cross-document | 10 | 5 |
| unsupported | 10 | 5 |

Abstention verified end-to-end: the unsupported query answers *"The
corpus does **not** discuss Kubernetes admission controllers at all"* and
correctly notes the only incidental mentions. No routing regression.

## PHASE 10 — CHILD BOILERPLATE (separate defect, OBSERVED)

Not addressed here, per scope. Representative: for
*"what are all the domains and subdomains of CySA+"* the author-biography
chunk (`chunk_b4edbc93…`, "Chris Crayton, MCSE, CISSP…") ranks above the
objectives map, and the cross-encoder promotes it to #1 while demoting the
correct chunk to #7. ~6% of children are pure boilerplate (253 OCR
placeholders, 98 bio/front-matter, 87 nav apparatus, 43 marketing). A
score floor cannot fix it — the bio scores 0.5955 vs the answer's 0.4894.
Correct remedy is ingest-side classification (v3.3 `chunk_kind`), which
requires a re-ingest.

## PHASE 11 — REACH / R1E

`shared/polymath_shared/reach.py` **untouched**; no production imports
added. Historical verdict stands: *"R1E: Pass-2 corpus reach
qualification — REJECT (insufficient complementarity)"*.

`R1E_REQUALIFICATION_WORTH_TESTING: NO` — R1E's concept arm scored
identically to its query-only arm, and the concept substrate that would
feed a requalification is exactly the mechanism that just failed
qualification. Revisit only if a sound concept layer exists.

## PHASE 12 — FAST / HYBRID / GRAPH

All three: **NO_CHANGE**, and **not** eval candidates at this time.

Wiring a layer that aliases `EDR`→`SIEM` and `incident response`→
`infrared spectroscopy` into query normalization would inject false
expansions directly into routing. GRAPH additionally must not derive
canonical identity from alias membership. Revisit only if the merge
mechanism is replaced.

## PHASE 16 — WHAT THE VOCABULARY LAYER IS FOR

**Not yet answerable from evidence.** The intended doctrine —

```
VOCABULARY NORMALIZES → SUMMARIES ROUTE →
ARTIFACTS REPRESENT → CHILDREN PROVE → GRAPH CONNECTS
```

— is **not proven** and must not be documented as such. What is proven:
the summary layer routes correctly on its own (document-summary lane put
both CySA books on top at 0.52/0.46 against 0.31 for the nearest
unrelated book), and the vocabulary layer as built cannot supply
trustworthy normalization.

The unmet need is real and unchanged: nothing maps user vocabulary
("subdomains", "EDR") onto corpus vocabulary ("objectives", "endpoint
detection and response"). Meeting it requires a mechanism whose merge
criterion is *term relatedness*, not *co-occurrence*.

## RECOMMENDATION

1. **Keep** the contract repair and its pins (done). The layer is now
   honest: it runs, and its output can be judged.
2. **Do not backfill** production. `VOCABULARY_BACKFILL_NO_GO`.
3. Treat the merge criterion as an **owner-level design decision** — it
   changes what the layer *means*, which is outside a regression repair.
   Cheapest credible direction: restrict families to
   morphological/acronym-expansion relationships (`EDR` ↔ `endpoint
   detection and response`, the one case that passed), which is
   deterministic and needs no embeddings.
4. If that lands, fix FINDING 3 (`definition` / `concept_vocabulary`)
   before re-testing ASK.

## REPRODUCTION

```bash
# contract regression + repair
.venv/bin/python -m pytest tests/determinism/test_vocabulary_production_contract.py -q

# scale + anti-scaling family collapse (needs POLYMATH_PG_DSN)
#   see eval scratch: bench over parent_summaries at 100..3015

# hard-negative panel
#   7 adversarial cases; 6 wrong merges
```

Canary corpus `vocab-canary-v1` (2 synthetic-but-real documents) was left
in place as reproducible evidence; delete when no longer needed.
