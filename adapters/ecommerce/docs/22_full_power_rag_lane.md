# 22 — The full-power RAG lane (the evidence boundary) and corpus names

Owner (2026-09-03): "for this workflow i want my full power rag system to be
used for my agent ideation … the rag shouldn't be changed it should use what
it already extracts."
Owner (2026-09-19/20, the evidence-boundary rule): agents get corpus knowledge
as EVIDENCE — `POST /chat/evidence` → `EvidencePacket`, NO synthesis. Submit the
ORIGINAL need; never pre-decompose it; never route agent work through a
Polymath answer. One reasoner per run: θ.

## §1 Ask the RAG for evidence, not for an answer (v2.2.0)

The corpus lane's native default is `--via evidence`. The run's ORIGINAL need
goes to Polymath's evidence boundary **once per corpus**:

```
POST /chat/evidence  {message: <the run's signal>, corpus_id, mode: "WILDCARD", corpus_explorer: true}
```

Polymath runs everything it has — query compilation, grounded expansion,
Corpus Explore, hybrid retrieval, rerank, graph and latent lanes, C4/C5
seating, CA4 grading — and stops BEFORE synthesis. The reply is an
`EvidencePacket` (`schema_version: evidence-packet-v1`, `synthesis_performed:
false`) and is consumed in two parts:

- **rows** → `corpus_evidence` (docs/18 rows, id space shared with the retrieve
  lanes). A packet row keeps the verbatim `text`, `utility_role`
  (DIRECT / COMPLEMENTARY / DIVERGENT / RELATED — why it was seated),
  `ca4_grade` (DIRECT / PARTIAL / RELATED — how it supports the ORIGINAL need;
  absent when ungraded), `c4_valid`, `origin` + `lineage` (which compiled query
  reached it), `provenance`, `doc_id`, and `packet_query_ids` (Polymath's own
  compiled-query ids). `query_ids` stays the skill's retrieval provenance (the
  need that asked). Tags: `evidence_packet`, `role:<…>`, `ca4:<…>`.
- **packets** → `corpus_packets`, one record per need and corpus:
  `{need, corpus, mode, n_evidence, row_ids, ca4_grades, utility_roles, origins,
  compiled_queries, corpus_explorer{requested, used, firing}, wall_ms,
  authority: CORPUS_EVIDENCE_PACKET}`. There is NO `answer` field and no
  abstention flag: an empty packet (`n_evidence == 0`) is the corpus not
  supporting the need, and the CA4 grade distribution says how well it did
  when it answered. A packet is evidence with roles and grades — θ reasons
  over it; nothing reasons before θ.

The EXPLORE plan rows still ride along for breadth (`lane: evidence+plan`);
a chunk both lanes return is ONE row (packet role/grade kept, the retrieve
lane's title / timecode / lanes / page-level source merged in, `query_ids`
unioned). The 3–5 compiled reformulations (docs/19) are NOT sent to the
evidence boundary — Polymath owns retrieval planning.

At `corpus_mechanisms` (docs/25 §6) each compiled friction / mechanism question
is a distinct need derived from field clusters, so it gets its own evidence
call (capped by `--max-evidence-calls`, default 12 = `lived_world.max_questions`;
what is skipped is recorded in `corpus_backend.evidence_truncated`), and the
per-question retrieve rides along (`lane: evidence+questions`).

**Fail closed.** A reply that is not `evidence-packet-v1`, that reports a
synthesis, or that does not satisfy `schemas/evidence_packet.json` (the
skill-dialect rendering of polymath-v4 `contracts/evidence/v1`, sha-pinned) is
never repaired, never partially consumed and never papered over by another
lane: no further request is sent and the adapter writes
`capability_failure{capability: "corpus_evidence_packet", blocked:
"EVIDENCE_CONTRACT_MISMATCH"}`. An UNREACHABLE evidence route is different — it
is recorded in `errors` and the row lanes still serve the run.

**No synthesis route exists in the adapter.** `ask_corpus`, `chat_question`
and `answer_record` are deleted; `_post` refuses any path outside
`{/chat/evidence, /retrieve, /retrieve/plan}` before any I/O. `--via plan` is
the rows-only rollback arm; `--generic` keeps the docs/18 control arm; the
retired `--via chat` is refused (exit 2). While a document scope is active the
evidence route — which cannot be scoped to documents — is skipped
(`corpus_backend.evidence_skipped`, docs/26 §8 policy B).

## §2 Corpus names

Corpus ids are immutable identity in Polymath; display names are the
owner's. A run identity may name corpora either way:
`polymath:Mark Builds Brands,ecom-meta-v1`. The adapter resolves names to
ids through `GET /corpora` (case-insensitive) and records
`corpus_backend.corpus_names`. New corpora created by the field-evidence
ingest take a minted id and the name you give (`--corpus-name`).

## §3 Receipt fields

`utilization.corpus.packets / packets_with_evidence / packet_rows /
rows_by_ca4_grade / rows_by_utility_role / polymath_evidence_calls /
polymath_chat_calls`; the report gains "Corpus evidence packets" (need, corpus,
grade / role / origin distribution, whether Corpus Explore fired) above the
utilization table. A LEGACY (< v2.2.0) state still loads: its `corpus_answers`
render as "What the corpus said — legacy synthesis, not evidence" and count as
`legacy_answers` / synthesis calls.

## §4 The request ledger — proving the nesting is gone

Every request the adapter sends is counted by route and timed
(`corpus_backend.calls`, `.timings_ms`, and the stderr note):
`polymath_chat_calls` (requests to anything outside the allow-list — 0 by
construction, and measured) and `polymath_evidence_calls`. Requests carry
`User-Agent: opportunity-research/<version> corpus_polymath run:<id>
node:<node>`, so Polymath's own query-receipt ledger attributes them: an
evidence call is `kind=chat, verdict=evidence_only`; a v2.2.0 run leaves no
other chat verdict and no `ask` receipt.

## History (superseded 2026-09-20, v2.2.0)

v2.1.x sent EVERY compiled reformulation to Polymath's answer route and stored
the synthesized replies as `corpus_answers` — a second reasoner nested inside
θ's reasoning (5 synthesis calls per corpus per visit; on the first live arm
14 of 15 sentence-form questions abstained). Removed by
GOVERNED-CONVERGENCE-V1 TG3.
