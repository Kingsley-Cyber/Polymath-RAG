# POLYMATH-FACT-ADMISSION-V1 — implementation + qualification

## VERDICT: **FAIL** — do not cut over

The mechanism works and improves precision substantially, but it does
not reach the mandated bar. Per the directive's cutover rule ("only
after the shadow candidate passes qualification"), production canonical
facts and the Neo4j projection are **untouched**.

| metric | required | measured | |
|---|---|---|---|
| WRONG | ≤ 5% | **25%** | FAIL |
| SUPPORTED | ≥ 90% | **44%** | FAIL |
| UNEXPLAINED | 0 | **0** | PASS |
| wrong direction | 0 | 2 of 32 (6%) | FAIL |
| pronoun/ineligible endpoints | 0 | **0** | PASS |
| bibliography/index/heading/caption relations | 0 | **0** | PASS |
| modal → asserted | 0 | **0** | PASS |
| acquired/developed frame misfires | 0 | **0** | PASS |

## Before / after

Measured on the existing L4 ledger of `release-books-v1`
(25 books, no re-ingestion — total harness runtime **10.2 s**).

| | before | after |
|---|---|---|
| candidates examined | 8,744 | 8,744 |
| graph-pool facts (both endpoints durable) | 1,521 | — |
| **admitted canonical facts** | 1,521 | **298** (19.6%) |
| qualified (evidence, not asserted) | — | 147 |
| rejected | — | 1,334 |
| documents represented | 24 | 22 |
| deterministic precision sample | n=24 | n=32 |
| — SUPPORTED | 29% | **44%** |
| — QUESTIONABLE | 33% | **31%** |
| — WRONG | 38% | **25%** |

Direction of travel is right — a third of the wrong edges eliminated and
80% of the volume shed — but 25% is five times the bar.

## Per-gate rejection census (graph pool)

| gate | reason | n |
|---|---|---|
| F8_SUPPORT | BINDING_NOT_WITNESSED | 469 |
| F7_DIRECTION | DIRECTION_UNLICENSED | 151 |
| F7_DIRECTION | DIRECTION_UNWITNESSED | 118 |
| F3_ENDPOINTS | ENDPOINT_SUBJ_PRONOMINAL | 115 |
| F2_REGION | REGION_CAPTION | 88 |
| F6_SIGNATURE | SIGNATURE | 76 |
| F2_REGION | REGION_INDEX | 72 |
| F4_ASSERTION | MODALITY | 51 |
| F1_PROVENANCE | MISSING_INPUT | 50 |
| F4_ASSERTION | CONTRASTIVE | 43 |
| F4_ASSERTION | IRREALIS | 34 |
| F5_PREDICATE | PRED_FRAME | 28 |
| F8_SUPPORT | BINDING_COPULA_COMPLEMENT | 24 |
| F7_DIRECTION | DIRECTION_PASSIVE_AMBIGUOUS | 6 |
| F3_ENDPOINTS | ENDPOINT_OBJ_PRONOMINAL | 5 |
| F2_REGION | REGION_CODE / BIBLIOGRAPHY | 4 |

QUALIFY (durable evidence, never projected): SPECULATIVE 60,
ATTRIBUTED 29, BINDING_NO_COMPLEMENT 18, SPAN_SUPPORT 16,
MODALITY_DEONTIC 15, CROSS_SENTENCE 9.

The single largest gate is **F8 binding** — 469 candidates whose two
endpoints were never dependency arguments of their own trigger. That is
the co-occurrence class, and it was invisible before this pass.

## Root cause found in the frozen rule pack (report-only, not patched)

`evidence.verbs` in core-predicates was **auto-expanded from VerbNet
classes without sense disambiguation**. `obtain-13.5.2` inserted `make`,
`source`, `receive`, `select` into `acquired`; `use-105.1` inserted
`work` into `uses`; a communication class inserted `collaborate` into
`similar_to`. This is the mechanism behind the forensic report's
"predicate misfire" class. F5 now treats class-inherited triggers as
weaker evidence than declared ones and requires PropBank/FrameNet sense
agreement, failing closed when the predicate declares no sense
inventory to test against.

## Remaining false-positive mechanisms (from the n=32 sample, 8 wrong)

| # | mechanism | example | layer |
|---|---|---|---|
| 1 | complex-clause direction | `depends_on(ip, b/ip)` — "To support IP, IP addresses are needed, which is why B/IP was…" | relation |
| 2 | predicate misfire surviving sense check | `similar_to(google, norad)` — "Google collaborated with NORAD" | relation |
| 3 | wrong pair among several entities | `created(rebecca wirfs-brock, ddd)` — she wrote *Object Design*, not DDD | relation |
| 4 | list enumeration read as relation | `depends_on(schema registry, heavyweight framework)` — comma list of components | relation |
| 5 | agentless passive fragment | `owns(spamcop, cisco)` — "SpamCop Currently owned by Cisco Systems" parses without an agent dep | relation |
| 6 | caption-adjacent binding | `created(ggg, quanta)` — figure caption text inside a body chunk | relation |
| 7 | **entity extent** | `employs(prc, pavlov)` — "employed Pavlovian conditioning"; entity extracted as the person | **upstream (entity)** |
| 8 | **entity quality** | `located_in(figure 4-7, location)` — "Figure 4-7" admitted as a durable Document | **upstream (entity)** |

6 of 8 are relation-layer and reachable by further gates; 2 of 8
originate in entity admission and cannot be fixed here. This confirms
the predicted risk that endpoint quality, not relation logic, becomes
the binding constraint — and it is why further FactAdmission iterations
alone cannot reach 5%.

## Recall cost (graph pool → admitted, by predicate)

| predicate | before | after | kept |
|---|---|---|---|
| uses | 489 | 128 | 26% |
| part_of | 263 | 36 | 14% |
| similar_to | 251 | 56 | 22% |
| founded | 113 | 9 | 8% |
| associated_with | 95 | 27 | 28% |
| acquired | 80 | 2 | 2% |
| stated_in | 78 | 8 | 10% |
| **instance_of** | 71 | **0** | **0%** |
| developed | 69 | 8 | 12% |
| created | 66 | 13 | 20% |
| depends_on | 59 | 19 | 32% |
| **is_a** | 56 | **0** | **0%** |
| located_in | 32 | 15 | 47% |
| member_of / has_role / owns / alias_of | 77 | 24 | 31% |

**The taxonomy backbone is destroyed**: `is_a` and `instance_of` both go
to zero, 127 facts. Cause is the copula-complement binding rule
(F8): it correctly kills `instance_of(soc support, intelligence)` from
"SOC support is one of the primary customers of an intelligence
program", but 24 further rejections and 18 qualifies in that class are
not individually verified, and a predicate falling to exactly zero is a
gate defect signature, not a semantic result. **Named follow-up:
COPULA-COMPLEMENT-BINDING-V2.**

## Runtime

Whole shadow pass over 8,744 candidates: **10.2 s** wall
(4,303 unique sentences parsed, batched at 512). Region classification
is computed once per chunk and cached; gates are pure functions over a
prebuilt context record. No document is rescanned — the 289M-regex
failure mode is not repeated. FactAdmission is not a throughput risk.

## Release recommendation

1. **Do not cut over.** 25% wrong is better than 38% but is not a
   trustworthy graph, and the taxonomy loss would make the projected
   graph both wrong *and* thin.
2. **Keep the code, unwired.** The gate chain, policy, shadow harness
   and 54-test development suite are committed and green; the shadow
   pass is a 10-second loop for the next iteration.
3. **Next iteration, in order:** (a) COPULA-COMPLEMENT-BINDING-V2 to
   recover the taxonomy predicates; (b) coordination/list-enumeration
   gate; (c) multi-entity clause binding (which pair does the trigger
   actually relate); (d) agentless-passive orientation.
4. **Then, separately, an entity-admission gate** — mechanisms 7 and 8
   are entity defects (extent and figure/document entities) and bound
   the achievable precision no matter how good relation admission gets.
   The pronoun leak is already recorded:
   `find_document_definition` matched definitional templates on "We"/
   "You"/"They", minting CORPUS_SCOPED identities
   (ENTITY-ADMISSION-PRONOUN-CONCEPT-LEAK). F3 blocks them at the graph
   boundary; the nodes still exist.
5. The measured target remains achievable in principle — nothing here
   required an unacceptable semantic assumption — but it is **two more
   gated iterations plus one entity gate away**, not one.
