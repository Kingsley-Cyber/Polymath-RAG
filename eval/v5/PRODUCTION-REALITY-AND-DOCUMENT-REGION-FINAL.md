# PRODUCTION REALITY GATES + DOCUMENT REGION — FINAL

Date: 2026-08-28 · Branch `architecture/evidence-first-v5`

**Both objectives met. `PRODUCTION_GO: YES`, with scope limits stated
explicitly below rather than implied.**

---

## REQUIRED OUTPUT

```
START_HEAD:  199702e
FINAL_HEAD:  (commits 6902557 document-region, + production-reality)
TREE_CLEAN:  YES

REGION_DECISION: BACKFILL   (re-ingest proved unnecessary)

REGION_TAXONOMY:
  body / front_matter / marketing / toc / index / bibliography /
  ocr_noise / unknown
  APPENDIX deliberately NOT a suppressed role (measured decision).
  CODE / TABLE / OUTPUT / CAPTION deliberately NOT introduced.

BOILERPLATE_BEFORE (query: "what are all the domains and subdomains of CySA+"):
  author_bio_rank:      #1  (post-rerank; cosine 0.5955)
  correct_answer_rank:  #7  (post-rerank; cosine 0.4894)

BOILERPLATE_AFTER:
  author_bio_rank:      ABSENT from the ranked set, in BOTH FAST and
                        HYBRID (reappears only as an appended
                        NEIGHBOR_EXPANSION neighbour, which is a
                        contiguity claim, not a ranking claim)
  correct_answer_rank:  present (rank 9 of 24)

METADATA_QUERY: PASS
  "who wrote this book and what are their credentials" -> 1 front_matter
  "what does this book cover and who wrote it"         -> 2 front_matter
  demotion is lifted entirely for document-metadata questions.

TECHNICAL_CONTENT_FALSE_SUPPRESSION: 0
  13 adversarial negatives pinned; "what is a SIEM" returns 0 demoted
  regions; 96.0% of the corpus classifies BODY.

SUMMARY_ROUTING:        PASS  (8-query panel, no regression)
CROSS_DOCUMENT_BREADTH: PASS  (max_documents unchanged by depth profile)
ABSTENTION:             PASS  (negative control still refuses)

PRODUCTION_REALITY_GATES:
  component:   existing determinism suites (unchanged)
  callsite:    vocabulary worker pin (mutation-tested), document-region
               contract, depth/metadata plan pins
  live_effect: lane_liveness evaluated on EVERY production query and
               returned in meta.liveness

CRITICAL_LANES_INVENTORIED: 9 retrieval lanes instrumented
  document_summary_routing, section_summary_routing, global_child,
  global_child_rescue, lexical, reranker, neighbor_expansion,
  region_demotion, graph_hop1

CALLSITE_PINS_ADDED: 3 areas
  summaries-worker -> vocabulary adapter (prior commit, mutation-tested)
  document-region classifier contract + corpus behaviour
  depth/metadata plan selection

MUTATION_TESTS: PASS
  the vocabulary callsite pin fails when the exact historical refactor
  is reintroduced, and passes when restored.

LIVENESS_SENTINELS (measured on live production routes):
  FACT:                  not instrumented (see SCOPE)
  PROCEDURE:             not instrumented (see SCOPE)
  CONCEPT:               not instrumented (see SCOPE)
  DOC_ROUTING:           LIVE
  SECTION_ROUTING:       LIVE
  GLOBAL_CHILD_RESCUE:   LIVE   <-- was structurally dead (0 of 10)
  LEXICAL:               LIVE
  GRAPH:                 NO_OPPORTUNITY / LIVE by query (correct)
  ABSTENTION:            PASS (panel)
  BOILERPLATE:           LIVE (region_demotion contributing)

HISTORICAL_FAILURE_SIMULATION: PASS
  8 chaos cases + 5 correct-zero cases; every historical failure class
  makes a gate fire, and every legitimate zero stays silent.

DEPTH_POLICY: PASS  (14-case intent matrix + metadata escape hatch)

FULL_TEST_SUITE: 1056 passed / 83 failed / 13 skipped — failure set
  BYTE-IDENTICAL to the pre-change baseline (zero regressions).

PRODUCTION_GO: YES
```

---

## PART I — DOCUMENT REGION

### Phase A — re-ingest was NOT required

`REGION_BACKFILL_POSSIBLE`. Classification consumes only `chunks.text`,
which is durable and immutable. Nothing was re-chunked, re-embedded or
re-extracted; no FACT/PROCEDURE/CONCEPT artifact was regenerated,
because none of their contracts depend on document role. Migration 0037
adds nullable columns; `is_noisy(NULL)` is False, so an un-backfilled
corpus is untouched.

### Why content, not position — and why that mattered

v3.3 classifies by heading path. That does not transfer:

- `heading_path` is populated for **0 of 7,085** children (legacy_v1
  never writes it; only the flagged-off semantic_v2 does);
- recoverable `document_layout` headings are **5,130 page markers** to
  **2,138 semantic** ones, and text recovery is lossy where a heading
  straddles a chunk boundary.

Decisively, **position is the wrong signal here**. The author biography
and the CS0-003 objectives map sit in the SAME front-matter region of
the same book and resolve to the same copyright heading. A
position-based classifier would have suppressed the correct answer.
Content separates them: one is a person's credentials, the other is a
numbered objectives list.

### Precision (Phase C)

Every rule requires structural evidence — line-shape ratios, anchored
headings — never bare token occurrence. 13 adversarial negatives are
pinned and all classify BODY.

**The adversarial suite caught two real bugs before they shipped:**
"Preface attacks manipulate the leading bytes..." was being suppressed
as front matter (the heading regex lacked an end anchor), and index
entries were mislabelled TOC (a bare trailing number satisfied the TOC
rule).

**A third was caught on live data**: the marketing rule fired on the
OBJECTIVES-MAP chunk itself, which opens "...dramatically increase your
chances of passing". A positive-content override now lets enumerated
structure outrank every boilerplate rule — packaging does not determine
role when a chunk demonstrably carries content. Pinned both directions:
the same marketing prose *without* structure is still demoted.

### Corpus result

7,085 children → **96.0% body**, 4.0% demoted (253 ocr_noise, 15
marketing, 14 front_matter). Conservative by design.

### Retrieval policy — demotion, never deletion

Everything stays stored, embedded and indexed. Demotion applies where
candidates compete **globally**, in both engines.

**Lane-level demotion alone was insufficient and the measurement proved
it**: per-section deepening admits only `max_children_per_section`
candidates, so the biography was taken regardless of its order within
its section — still rank 2. Applying demotion at the global pre-cut in
`pass1` fixed FAST but not HYBRID, which performs its own cut; the
biography returned at rank 2 there until the same demotion was added to
`hybrid`. Both now exclude it.

---

## PART II — PRODUCTION REALITY GATES

### The three-level model

A feature is live only when REAL INPUT → REAL CALLSITE → OPPORTUNITY →
OBSERVABLE EFFECT. Component tests answer only the first question, which
is exactly how six capabilities in this repo were dead while green.

### Conditional liveness, not `count == 0`

Each promoted lane declares `opportunity(trace)` and
`contributed(trace)`:

| verdict | meaning |
|---|---|
| NO_OPPORTUNITY | zero is uninformative — no chance to act |
| LIVE | had an opportunity and acted |
| SUSPECT | had an opportunity and produced nothing — the dead-feature signal |
| DISABLED | not enabled for this query/mode |

Rejected or unqualified mechanisms (R1E reach, the vocabulary family
layer) are deliberately **not** registered: they are supposed to produce
zero and must never generate alerts.

Every production query now returns `meta.liveness` and logs
`lane_suspect` when a promoted lane goes quiet. Measured live:
`global_child_rescue` reports **LIVE** — the lane that delivered 0 of 10
chunks before this week's repair.

### Chaos matrix (Phase I)

Eight historical failure classes each make a gate fire: rescue
configured-but-dead, a lane omitted from the union, Postgres-written /
Qdrant-missing summaries, a lost `representation_kind` filter, a
reranker that runs without scoring, neighbour expansion that never
expands, region demotion that stops demoting, and graph seeds that
traverse nothing. Five **correct-zero** cases assert silence, so the
signal cannot become noise.

---

## SCOPE — what this mission did NOT cover

Stated plainly rather than implied by omission:

- **Ingestion lanes are not instrumented.** FACT, PROCEDURE, CONCEPT,
  intake, profile, extract and the projection workers have no liveness
  predicates yet. The 9 instrumented lanes are all retrieval-side. This
  is the largest remaining gap: PROCEDURE yield in particular looks
  thin (12 artifacts across 11 books) and nothing currently detects it.
- **No persistent sealed sentinel corpus.** Validation ran real queries
  through the production HTTP routes, but no committed fixture replays
  a known FACT/PROCEDURE/CONCEPT opportunity on a schedule.
- **No periodic health surface.** Liveness is per-query today
  (`meta.liveness` + a warning log). There is no aggregate
  `last_success_at` / rolling-window endpoint.
- **Region classification is corpus-shaped.** The rules were tuned and
  measured on `cysa-study-v1` (technical books). A corpus of papers or
  transcripts would need its adversarial set re-run before trusting the
  4% demotion rate.

## Reproduction

```bash
.venv/bin/python -m pytest tests/determinism/test_document_region.py \
    tests/determinism/test_production_reality.py \
    tests/determinism/test_depth_policy.py -q

POLYMATH_PG_DSN=... .venv/bin/python scripts/backfill_document_regions.py \
    --corpus cysa-study-v1          # dry run; --apply to write
```
