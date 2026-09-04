# 22 — The full-power RAG lane and corpus names

Owner (2026-09-03): "for this workflow i want my full power rag system to be
used for my agent ideation … the rag shouldn't be changed it should use what
it already extracts."

## §1 Ask the RAG, do not re-teach it

The corpus lane's native default is now `--via chat`: every compiled
reformulation (docs/19) is sent to Polymath's `/chat` with `evidence: true`
— asked as a SHORT concrete question built from the reformulation's strongest
terms (`asked_as`), because the answer-admission gate requires covered terms
and the first live arm abstained on 14 of 15 sentence-form questions — and
the EXPLORE rows of the same plan ride along for breadth (`lane: chat+plan`)
— hybrid retrieval, rerank, graph and latent lanes, answer admission and
synthesis with citations — and the reply is consumed in two parts:

- **rows**: the answer's own chunks, documents and attested facts as
  RETRIEVE-EVIDENCE-ROWS-V1 rows → `corpus_evidence` (deduped by id across
  reformulations and corpora, `query_ids` kept, can/cannot_establish stamped);
- **answers**: one `corpus_answers` record per question and corpus —
  `{question, corpus, mode, verdict, abstained, uncovered_terms, answer,
  citations: [row ids], authority: CORPUS_SYNTHESIS}`. A synthesis is a
  reading of evidence, never evidence: it can shape primitives and
  hypotheses, it never closes a gap. Abstentions are kept — a question the
  corpus cannot ground is a finding, and the rows still show what was retrieved.

`--via plan` keeps the row-only path (`/retrieve/plan`); `--generic` keeps
the docs/18 control arm. Nothing in Polymath's extraction changes for this
lane; the typed-claims experiment was reverted the same night.

## §2 Corpus names

Corpus ids are immutable identity in Polymath; display names are the
owner's. A run identity may name corpora either way:
`polymath:Mark Builds Brands,ecom-meta-v1`. The adapter resolves names to
ids through `GET /corpora` (case-insensitive) and records
`corpus_backend.corpus_names`. New corpora created by the field-evidence
ingest take a minted id and the name you give (`--corpus-name`).

## §3 Receipt fields added

`utilization.corpus.answers / answers_admitted / answer_citations`; the
report gains "What the corpus said" (question, answer or abstention,
citations, corpus) above the utilization table.
