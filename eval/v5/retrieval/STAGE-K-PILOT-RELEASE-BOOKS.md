# STAGE-K PILOT — release-books-v1 (real corpus, MEASURED)

Date: 2026-08-25 · HEAD at measurement: `a1076f4` · fence PASS 13/13.
Corpus: 25 real user books (cybersecurity/SRE/data-eng/persuasion),
ingested end-to-end under the neural embedding contract.

## 1. Inventory (Postgres authoritative)

| object | count |
|---|---|
| documents | 25 |
| child chunks | 15,205 |
| parent chunks | 3,811 |
| section summaries | 3,596 |
| document summaries | 22 ⚠️ (3 missing) |
| canonical facts | 7,934 |
| procedure artifacts | 0 ⚠️ |
| concept artifacts | 0 ⚠️ |

## 2. Measured gaps (with root causes)

1. **Document summaries 22/25** — missing for 3 docs whose runs never
   finished (the documented corrupt-source/duplicate trio era);
   summary_jobs table is empty for this corpus (predates the summaries
   worker). New corpora mint jobs automatically; old-state redrive is a
   separate admitted slice.
2. **Procedure/concept artifacts zero** — extraction of these lanes
   shipped AFTER this corpus was extracted (migration 0033). Frozen
   extraction is not retroactively re-run on a 25-book corpus inside an
   overnight window; any NEW corpus gets both lanes automatically.
   Forward-path validation happens naturally during the next fresh
   ingest.
3. **`/ask` cross-corpus fallback leak (product decision needed)**:
   with no `corpus_id`, the FACT/PROCEDURE/CONCEPT routes fall back to
   searching ALL corpora and returned the only artifacts in the system,
   from TEST corpora `p1-genre-probe-v1/v2`. Responses still report
   `grounded=True` (they carry document_ids) — grounding is technically
   true but provenance is foreign to the user's expected scope.
   Options for owner: (a) strict scoping — no corpus ⇒ no fallback;
   (b) fallback restricted to query_ready corpora; (c) keep and expose
   corpus_id per object in the response. NOT changed unilaterally.

## 3. Live /ask grounding checks (stored-objects route)

| question | route | grounded | latency | returned |
|---|---|---|---|---|
| What benchmark evaluated the Orion model? | FACT_QUERY | true | 104 ms | 8 facts |
| How do I install Splunk on AWS? | PROCEDURE_QUERY | true⚠️ | 17 ms | 1 procedure (test corpus — see §2.3) |
| What makes distributed systems hard to release? | CONCEPT_QUERY | true⚠️ | 5 ms | 6 concepts (test corpus) |
| Who wrote about propaganda in 1928? | CONCEPT_QUERY | true⚠️ | 3 ms | 6 concepts (test corpus) |

## 4. Dense retrieval under G1 neural authority

Reference: `eval/v5/retrieval/G1-HASH-VS-NEURAL.md` (neural 6/9 vs
hash 0/9 weak-labeled) and
`eval/v5/retrieval/THREE-MODE-BENCHMARK-V1.md` (VECTOR ≈0.6 s,
HYBRID ≈0.9–1.9 s, GRAPH ≈0.95 s incl. embed round trip; exact
procedure hit verbatim; typed graph facts).

## 5. Verdict

**PILOT QUALIFIES THE PIPELINE, EXPOSES TWO PRODUCT DECISIONS.**
Ingestion→facts→summaries→dense/graph retrieval works end-to-end on
real material under the production neural default. Blocking-quality
items before calling retrieval "production": resolve /ask corpus
scoping (§2.3) and populate artifact lanes via a fresh ingest (§2.2).
