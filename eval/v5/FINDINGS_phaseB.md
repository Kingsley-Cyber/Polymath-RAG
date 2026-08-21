# Phase B — Ingest throughput closure (release-closure mission)

Corpus: perf-baseline-v1 (Sanders EPUB, doc_b07a1f1f…, 864 chunks,
6,116 slices). Every optimized run required and achieved
`semantically_identical: true` against the baseline snapshot (state hash
72b2b6fce43bf98f…, mentions 7,852, raw L1 9,375, hypotheses 11,908,
facts 392).

## Result

| stage | baseline s | optimized s | change |
|---|---|---|---|
| entity_pass (GLiNER p1) | 209.5 | 107.0 | 2.0x (transport batching, 864→27 calls) |
| admission | 307.3 | 51.5 | 6.0x (ADMISSION-IMPL-MEMO-V1) |
| rescue (GLiNER p2) | 162.4 | 137.9 | 1.2x (grouped /rescue) |
| persist_mentions | 7.0 | 0.4 | 17x (executemany) |
| syntax / evidence / compile | 18.1 | 16.5 | — |
| **extract total** | **709.4** | **315.4** | **2.25x** |

## What moved and why

- B1 profile overturned the 45-minute assumption: true baseline extract
  was 709 s with 99.3% attribution. Admission dominated (43%), inside it
  `find_document_definition` was 84% — a whole-document sentence re-split
  plus 289M regex searches (naive span×sentence×template scan).
- B2: the sidecar equivalence probe REJECTED model-level batching
  (kept bit-identical loop mode); /infer_batch gains are transport-only.
  b=32 optimal; POLYMATH_GLINER_BATCH default.
- ADMISSION-IMPL-MEMO-V1: sentence split cached per text, templates
  compiled per distinct term, same-engine re.I term prefilter, result
  memo. Contract string unchanged BECAUSE behavior is unchanged —
  licensed by test_concept_evidence_equivalence.py (verbatim naive
  reference, 34 cases) and the B8 identical-state run.
  authority_code_sha256 moved 3981fcff→fd68fc57 (pins updated).
- B4 MPS contention (64 chunks, b=32, 3 runs/lane): GLiNER alone
  8.9 chunks/s; +embedder 2.93 (3.04x slower); +embedder+reranker 1.8
  (4.96x). Reranker is query-time only → ingest-relevant contention is
  3.0x. Policy: keep concurrent scheduling; serializing stages idles the
  GPU and lowers whole-pipeline throughput.

## B9 acceptance

Provider compute in the optimized run: entity_pass 107 s + rescue
137.9 s = 244.9 s = 78% of extract. Observed extract (315.4 s) is within
1.29x of the pure provider floor; the remaining 22% is admission +
syntax + compile + persistence. Throughput is provider-bound as
required — no further engineering lever short of provider/model changes,
which are frozen. ACCEPTED.

## Defects found and fixed on the way (all committed)

1. type_reconciliation recorder wrote entity.text as proposed_surface
   while apply() installs slice text at the proposed offsets — 31
   inconsistent ledger rows on Sanders; broke settlement replay.
2. Frozen i4 wipe predates V5 evidence tables (no FK cascade):
   span_hypotheses/raw_*/sentence_slices survived every wipe;
   content-addressed ids masked it until row content changed.
   eval/v5/wipe_corpus_v5.py added (introspective doc_id-scoped wipe).
3. Shadow reconstruction's tr lane installed src.text at proposed
   offsets — same class as (1), eval side.
4. Fact-replay fidelity gap (398 vs 392, replay-permissive on 6
   frame-gate rejects): parse/evidence-anchor context is re-derived, and
   parse_sentence is environment-sensitive. Documented in
   KNOWN_LIMITATIONS #11; fix scoped to Phase F.
