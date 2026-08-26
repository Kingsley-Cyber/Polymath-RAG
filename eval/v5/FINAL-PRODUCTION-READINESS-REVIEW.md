# FINAL PRODUCTION READINESS REVIEW — 2026-08-26

Mission: POLYMATH_FINAL_BUILD_REPAIR_AND_QUALIFICATION — repair the
P0 failures established by the 2026-08-26 SMART verification, qualify
one real modern transcript end to end, and issue GO / NO-GO.

Evidence labels: **CODE** (code verified) · **TEST** (test verified) ·
**LIVE** (live verified) · **MEASURED** · **INFERRED** · **NOT TESTED**.

## 1–2. Heads

- **START_HEAD** `f33a0ffc6ae19d25cc1881a338939d6292d92a2b` (clean)
- **FINAL_HEAD** the commit carrying this review (see `git log`);
  every repair commit is listed in §5.

## 3. P0 defects received (SMART verification baseline)

1. Query application cannot start (`ask_router` NameError; 7200/8743 down).
2. Required retrieval modes fail (`rerank_unavailable`; no query profile).
3. Knowledge Router suppresses eligible relational extraction.
4. Missing scope widens retrieval (41,831 rows / 77 corpora measured).
5. Unsupported questions return cited passages as "supported".
6. No complete current-pipeline mixed transcript demonstration.

## 4–5. Root causes and fixes (bounded commits)

| Commit | Repair | Root cause |
|---|---|---|
| 938b852 | QUERY-PLANE-BOOTSTRAP-V1 | `main.py` registered `ask_router` without importing it; no app-level test existed. + latent missing `json` import in ask.py. **TEST/LIVE** |
| 44e4c6e | QUERY-SCOPE-EVERYWHERE-V1 | /retrieve /evidence /chat had `corpus_id=None → fetch everything` branches; deleted; one shared resolver; single-corpus modes 422 on wider scope. Adversarial two-corpus regression incl. a Neo4j-projected allowlist fact in B. **TEST/LIVE** |
| 706baaa | EXTRACTION-ELIGIBILITY-V1 | `_evidence_spans` returned `[]` for the whole document when the router primary disabled the lane. Now: deprioritized documents still run the cheap trigger localization; chunks with local evidence take the identical discovery path; procedure/concept compilers always evaluate (self-gating); router verdict recorded as metadata. Admission untouched. Six-case A–F matrix incl. adversarial all-disabled classifier. **TEST/LIVE/MEASURED** |
| 7ad9418 | ANSWER-ADMISSION-V1 | Synthesizer proposed a "supported" claim from every retrieved passage (excerpt⊂passage is trivially verbatim). Gate 1: passage must share ≥1 query content term. Gate 2: union of supporting surfaces must cover EVERY query content term or verdict=insufficient_evidence (withheld claims stay in the ledger). No similarity thresholds — existing tokens()/substring conventions. **TEST/LIVE** |
| 61dae8d | VOCABULARY-GUARD-TEST-SYNC | The 2 reproducible failures were STALE TESTS: the min-support=2 guard shipped deliberately (f267d0e, hardened b94db70) after the tests froze. Tests re-express original intent under the guard; guard now pinned. **CODE/TEST** (same class fixed in D6 fixture, 4b8027e) |
| 456a52c | FAILURE-TRANSPARENCY-V1 + SEMANTIC-READINESS-V1 | `_neo4j_expand` swallowed exceptions into `[]`; now typed `GraphBackendUnavailable` → 502 `graph_backend_unavailable` (zero stays `[]`). `semantic_completion()` view: SEMANTIC_COMPLETE / INCOMPLETE / FAILED from durable state only; `query_ready` untouched; exposed at GET /semantic_readiness. Failure-injection regressions. **TEST/LIVE** |
| 4b8027e | CORPUS-MAP-PLANNING-V1 | Map was built, never read. Scoped deterministic planner over corpus_summaries + concept_families/aliases; expansion terms feed /ask lanes against the same stored objects; traced neighborhoods with map-row provenance; scope only narrows. Also fixed: /ask confidence bonus admitted EVERY stored object for any query (candidacy now requires a term match). Map builder now feeds persisted procedures (REQ-007). Behavioral-delta regression (map absent→missing; present→found via alias bridge; out-of-scope map contributes nothing). **TEST/LIVE** |
| 8f55055 + 6e9976b | TRANSCRIPT-REGISTER-V1 | Compilers didn't recognize spoken register: conversational-lead stripping before the imperative test ("So click…", "Okay, so let's run…"); copula-definition patterns the concept module's docstring always claimed (gerund-copula w/ nominalization-head guard, stands-for, appositive which-is, is-a) + name guards (pronouns, enumeration, clause fragments, spoken futures). Fixed latent IndexError (refers-to pattern has no desc group — reachable from real text). Measured on the unaltered finetune transcript: 0→6 steps, 0→4 genuine concepts. Discovery register only; admission untouched. **TEST/MEASURED** |
| c588da1 | AUTHORITY-PIN-REFRESH | 3 stale semantic-authority hash pins (moved by committed 9d0fce4/266aa81; bundle integrity READY at current hash). **CODE/TEST** |
| dd6427c | CROSS-CORPUS-CONTENT-COLLISION | `ON CONFLICT (doc_id) DO NOTHING` silently minted a query_ready run over an EMPTY corpus when content already belonged to another corpus (measured live). Now a typed, durable refusal. **TEST/LIVE/MEASURED** |
| 957c1e4 | RECEIPT-GAP-REOPENS-TICKET-V1 | Census re-armed projection events for post-summary receipt gaps, but claims require a `ready` ticket and nothing re-opened `done` — re-drives permanently unclaimable (measured: run stuck `degraded`, all workers polling idle). schedule_gaps re-opens exactly the flagged (run, stage) pairs. **TEST/LIVE/MEASURED** |
| f283ecb | ARTIFACT-LANE-VERIFY-V1 | Verifier + census omitted routing_procedure/routing_concept — active receipts over an empty store were undetectable and never re-driven (measured: 3 stale receipts, 0 points). Both now cover artifact kinds; loop closes with the reopen fix. **TEST/LIVE/MEASURED** |
| 9966b7f | PRODUCT-READINESS-GATE-V1 + FINAL-PRODUCT-PANEL-V1 | Product gate separate from the worker fence; measured qualification panel. **LIVE** |
| df30415 | /ask punctuation term bug ("Andromeda?" matched nothing) + RERANK-BATCHING-V1 (single batch OOM'd 3 GiB MPS pool on books corpus). **TEST/LIVE/MEASURED** |
| dcdce71 | RERANK-SURFACE-BOUND-V1: batch pads to longest passage; one 77,125-char chunk (corpus p99=1,245) forced the same 1.87 GiB alloc at any batch size; scoring surface bounded to 4,000 chars, candidates untouched. **TEST/LIVE/MEASURED** |

## 6. Router eligibility architecture

`classify_document` remains the deterministic document profiler; its
`disabled` tier is now a PRIORITY signal recorded as metadata. FACT
discovery: deprioritized documents run per-chunk lexical trigger
localization; local evidence → the identical discovery path (the
expensive GLiNER evidence pass is skipped only for chunks with no
local evidence — the cost optimization the router is allowed to be).
PROCEDURE/CONCEPT: compilers are the local-evidence detectors and
always evaluate. Predicate Compiler v2, E1–E7, F1–F8: untouched.
**LIVE evidence**: fresh transcript extraction audit shows
`routing_disabled=['scientific_predicate']` AND 54/34 relation
candidates minted and adjudicated.

## 7. Real transcript used

`transcript-qual-v1` ← *"Alex Hormozi's NEW Facebook Ads Strategy
(Andromeda Breakdown)"* (Dr. Matt, YouTube PPCFvIdNwTg, 15,851 B,
`source_format: youtube_auto_transcript`, unaltered, never previously
ingested). Pre-registered qualifying passages (verbatim):

- Procedural: "So, make sure that you have related media off for this
  testing campaign." / "So, make sure related media is off."
- Conceptual: "…Andromeda, which is the new update Facebook made." /
  "Jon Loomer … OG in the … Facebook advertising space."
- Relational: "From a high-level overview, Andromeda is Meta's new
  retrieval engine." / "Facebook has developed a technology that…"

A second real transcript (49,459 B meta-ads tutorial) was ingested
into `transcript-final-v1` with the same outcome shape (PROCEDURE=1,
CONCEPTS=2, FACT=0 with fully-traced rejections).

## 8. FACT / PROCEDURE / CONCEPT yield (transcript-qual-v1) — MEASURED

- chunks 14 child + 4 parent · sentences ~230 · mentions 232
- relation candidate discovery **ran under a deprioritizing router**:
  34 candidates (ACCEPT 2 / QUALIFY 5 / REJECT 26 / UNSUPPORTED 1)
- **PROCEDURE = 1** (persisted + routing_procedure receipt + point)
- **CONCEPT = 2** ("Andromeda", "Jon Loomer"; persisted + receipts + points)
- **FACT = 0 admitted; 7 rejected, every rejection typed**:
  `F3_ENDPOINTS: ENDPOINT_SUBJ_NOT_DURABLE ×5 / OBJ ×2`; compiler
  rejections e.g. `('Andromeda','Meta')` = "type_violation: no
  signature accepts (Technology → Organization)".

**Boundary trace (outcome taxonomy D — admission rejection, not
wiring):** "Andromeda is Meta's new retrieval engine" WAS discovered,
correctly entity-typed, and refused by the frozen predicate type
signatures (the possessive-copula reading Andromeda→developed_by→Meta
has no signature). Every other candidate pairs a spoken-register
pronoun ("you", "I") — F3 durability refuses them exactly as designed
(the pre-enforcement era admitted "you founded openai" from the same
register; the enforced gates now refuse that noise). NO EDGE > WRONG
EDGE upheld. **This is the single unmet gate — see §21.**

## 9. Transcript → Graph proof — LIVE, public plane

Corpus `core-3-v1` (the real fine-tuning transcript the SMART
verification traced internally; TEST_ONLY then, public now):

`POST /retrieve {mode: GRAPH, corpus_id: core-3-v1}` returned
`fact_35b8adc3…` (`anseloff —founded→ google collab`, transcript-
derived) through the qualified hop-1 expansion; `POST /evidence
{mode: GRAPH}` resolved it to the exact source locator
`chunk:chunk_74598cee…@15142:15894`; `POST /chat {mode: GRAPH}`
produced the grounded citation. Note honestly: that fact is a
pre-enforcement-era ledger row (decision QUALIFY) — the current
enforced gates would not re-admit its class, which is consistent with
the measured ~38% wrong-edge baseline that motivated enforcement.

FACT-heavy graph at scale: `release-books-v1` GRAPH via HTTP —
**PASS**, p50 4,575 ms (7,934 facts corpus; latency attributable to
graph capability + legacy full-corpus lexical lane).

## 10. Corpus Map proof — LIVE + TEST

- Builder now consumes persisted procedures (**CODE/TEST**).
- Live `/ask` trace on the fresh transcript: `map.consulted=true`, 3
  neighborhoods with map-row provenance (`sum_4290f9bf…`) matched via
  "Andromeda".
- Behavioral delta regression: alias bridge "RAG" → "retrieval
  augmented generation" finds the stored concept only when the map
  exists; an out-of-scope corpus with identical map rows contributes
  nothing. **TEST**

## 11. Scope isolation — TEST + LIVE

Adversarial two-corpus probe (B holds the verbatim answer AND a
projected allowlist graph fact): scope A surfaces zero B documents /
chunks / facts / graph edges; missing scope = typed 422 on all four
routes; unknown scope = typed 404; multi-corpus scope on single-corpus
modes = typed 422. Live probes confirm on the running product.

## 12. Abstention proof — TEST + LIVE

8-case deterministic suite (nonce, sharpened partial-overlap nonce,
neighboring-topic, paraphrase, relationship…). Live: nonce
`/chat` → `verdict=insufficient_evidence, abstained=true`;
neighboring-topic ("How much does Jon Loomer charge for consulting?")
→ abstains, with the corpus containing related Jon Loomer content.

## 13–15. VECTOR / HYBRID / GRAPH — LIVE + MEASURED

All through HTTP on the fresh transcript corpus (n=5 warm):

| probe | p50 ms | p95 ms | max ms |
|---|---:|---:|---:|
| VECTOR (FAST) | 1,347 | 1,354 | 1,355 |
| HYBRID | 1,148 | 1,167 | 1,175 |
| GRAPH (valid zero relationships) | 1,563 | 1,570 | 1,575 |
| /ask (stored objects) | 10 | 12 | 13 |
| /chat grounded | 3,367 | 3,384 | 3,390 |
| /chat abstain (nonce / neighbor) | 3,366 / 3,372 | — | — |
| GRAPH core-3-v1 (transcript fact) | 2,074 | 2,086 | 2,090 |
| /evidence GRAPH bundle | 2,126 | 2,133 | 2,144 |
| GRAPH release-books-v1 | 4,576 | 4,666 | 10,391 |

GRAPH mode distinguishes `graph_fact_count: 0` (valid zero — the
fresh transcript) from typed `graph_backend_unavailable` 502
(failure-injection test). BM25: the Python lexical lane measured
bounded at this scale — BM25 remains a recorded future scale
optimization, per the measure-first rule. Evidence bundles: the
existing deterministic assembly is the synthesis input on every path
(no rebuild).

## 16. Ingestion timings (transcript-qual-v1) — MEASURED

intake 10.2 s · extract 16.7 s · profile <1 s · projections seconds ·
summaries (parent→document→corpus→vocabulary) complete at T+145 s.
Full receipt convergence was initially blocked by the two discovered
wiring defects (§5: 957c1e4, f283ecb); after the fixes the reopen
cycle converges within control-tick cadence (minutes). Historical
comparison: prior transcript runs 289–374 s to query_ready.

## 17. Query latency

See §13 table. No unexplained multi-minute operation; no full-world
scans (scope-bounded SQL everywhere); repeated warm queries stable.

## 18. Isolated deterministic suite — TEST

27-file architecture-critical suite (router, eligibility, scope, app
bootstrap, answer admission/synthesis, evidence assembly/bundle,
vocabulary, artifacts, DAG contract, scheduler/census/claims + the new
reopen regression, embedding contracts, hybrid, fact admission, bundle
fence, chunker, rerank): **240 passed × 2 identical runs**, each
against a freshly created schema-clone database
(`polymath_accept_iso`), hard-coded DSNs redirected without editing
tests.

## 19. Failure transparency — TEST + LIVE

- Neo4j outage → typed 502 (injection test); valid zero stays `[]`.
- Artifact-lane exception → durable `artifacts_error` →
  `SEMANTIC_FAILED`, never zero yield (injection test).
- Reranker OOM during the panel surfaced as typed 502
  `rerank_unavailable` — the loud path demonstrated itself live —
  then was root-caused and fixed (df30415, dcdce71).
- Cross-corpus silent empty ingest → typed refusal (dd6427c).
- Stale receipts over an empty store → verifier clears → census
  re-drives (f283ecb + 957c1e4).

## 20. Remaining limitations

1. **Transcript FACT register (owner decision — §21).**
2. One content = one corpus (content-addressed doc identity). Now a
   typed refusal instead of a silent empty ingest; cross-corpus reuse
   would need an owner-level identity decision.
3. Periodic drift-detection cadence: verify runs per-run, not on a
   timer; store-vs-receipt drift in a quiet corpus is detected on the
   next ingest/verify, not immediately.
4. release-books-v1 backfills (3 legacy doc summaries; artifact lanes
   predate 0033) — unchanged, explicitly waived for this review.
5. Corpus-map dominant_concepts inherit doc-summary noise (e.g.
   heading fragments); planner matches are still provenance-traced.
6. `transcript-final-v1` retains its first (empty) pre-fix run as
   deliberate measured evidence.
7. Book-corpus chunking outlier (77 KB child chunk) — the reranker now
   bounds it; the chunker root cause is unexamined (NOT TESTED).

## 21. GO / NO-GO

**NO-GO (one gate), everything else GO.**

The single unmet FINAL-GATE item: *"FACT > 0 where qualifying relation
exists"* on the fresh transcript, and therefore *"fresh-transcript
FACT powers Graph retrieval"*. Candidate discovery, eligibility,
admission, projection, public GRAPH, and evidence resolution are all
proven working (§8–9). What blocks the gate is a **product-semantic
decision, not a wiring defect**: the frozen Predicate Compiler's type
signatures have no frame for the spoken-register relations real
transcripts contain (measured: "Andromeda is Meta's new retrieval
engine" → Technology→Organization refused; every available local
transcript was swept — none carries written-register named-entity
relations that the enforced gates admit, and the gates are RIGHT to
refuse what they refuse). Per the mission's own stop rule ("changing
Predicate Compiler semantics" requires the owner), the options are:

  A. Owner authorizes a qualified possessive/appositive-copula frame
     (e.g. `X is Y's <artifact>` → `developed_by`) with its own
     signature, shadow qualification, and precision bar; or
  B. Owner supplies/approves a transcript of written technical
     register (e.g. a scripted AI-news/lecture transcript naming
     entity pairs declaratively) for the fresh-ingest qualification.

Either closes the last gate; nothing else is blocked on it.
