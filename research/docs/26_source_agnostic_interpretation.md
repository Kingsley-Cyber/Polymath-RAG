# 26 — Source-agnostic interpretation, the three axes, and the eight canaries

Owner (2026-09-04): "Any corpus content — marketing book, psychology book,
novel, technical manual, transcript, philosophy, memoir — may generate
opportunity hypotheses. What changes by source is what authority the content
has, not whether it is allowed to participate in ideation."

docs/25 corrected the echo problem and overcorrected: it gave source types
fixed jobs (books → mechanisms, communities → nouns). That destroys the
agnostic property. This document restores it without giving the echo back.

## §1 The adapter is interpretation, not retrieval

Any retrieved passage → `latent_structures[]` (schema latent_structure.json),
typed by kind: ACTIVITY, ROUTINE, OBJECT, OBJECT_INTERACTION, BODY_STATE,
ENVIRONMENT, CONSTRAINT, FRICTION, DESIRE, TRADEOFF, ADAPTATION, WORKAROUND,
SOCIAL_DYNAMIC, IDENTITY_SIGNAL, TRANSITION, FAILURE_MODE, REPETITION,
COORDINATION_PROBLEM, ACCESS_PROBLEM, COMFORT_PROBLEM, STATUS_PROBLEM,
ATTENTION_PROBLEM, TRANSFERABLE_INVARIANT, CAUSAL_MECHANISM. Authority is
always LATENT_HYPOTHESIS. Most passages yield almost nothing. A sex-club scene
may yield `privacy under a constrained environment` or nothing at all — the
architecture decides, never a document-type blacklist. From a structure:
applicability outside the source → bridge hypothesis → possible human
situation → physical job → mechanism → product hypothesis.

## §2 Three judgments that are never collapsed

| axis | question | who decides | where it lives |
|---|---|---|---|
| retrieval relevance | is this passage potentially useful for THIS question? | θ classifies (`row_relevance`: LEXICAL_MATCH / SEMANTIC_MATCH / STRUCTURAL_ANALOGY / IRRELEVANT); the adapter adds a deterministic `lexical_overlap` + `relevance_hint` (`SINGLE_WORD_OVERLAP` = the lexical trap, `NO_LEXICAL_OVERLAP` = semantic retrieval, judge the structure) | rows, `data.row_relevance` |
| generative usefulness | can θ derive a transferable structure from it? | θ, at primitives | `latent_structures`, `evidence_refs` |
| evidentiary authority | what may this source ESTABLISH? | φ, docs/04 table + `can_establish` / `cannot_establish` on rows | verifiers, satisfaction, provenance |

φ enforces axis 1 with one law: a row classified IRRELEVANT can never back a
hop (`hop_refs`) or become a cross-domain analogy. A novel passage may be
relevance HIGH, generative HIGH, authority ZERO for demand. A supplier listing
may be relevance HIGH, generative MEDIUM, authority HIGH for availability and
ZERO for demand. Retrieval noise is solved by this gate, not by excluding
sources.

## §3 Nothing is stripped; everything named is recorded

`corpus_observations[]` (schema corpus_observation.json): OBSERVED_PRODUCT,
EXAMPLE, NAMED_POPULATION — with `evidence_refs`, `job_served`, `mechanism`,
`populations_sharing_job`, `evidentiary_authority: NONE_FOR_CURRENT_DEMAND`.
Rows tagged CORPUS_EXAMPLE carry the same record. A book that names
compression socks lets θ ask why the object was there, what job it served,
which other populations share the job, whether the field shows a different
implementation. The named product may win. The provenance law (docs/25 §7)
only forbids `book said X → therefore sell X`: a concept that is corpus-named
needs independent grounding; if it has it, it stands.

## §4 Both population directions

POPULATION → latent problem (docs/25): a named group is instantiated and its
frictions read out.
LATENT PROBLEM → population (new): a structure whose population is unknown
becomes a lead with `search_mode: LATENT` (source_lane LATENT); its channel
queries carry the structure's own language; the scout discovers WHO keeps
describing it and submits those communities with the `latent_structure_id`.
Named populations a structure proposes become ordinary NAMED leads citing the
same rows. There is no privileged starting ontology: book → mechanism →
population search → product; novel → lived interaction → invariant →
population search → product; comment → workaround → corpus analogy → product;
product → mechanism → alternate population → market.

## §5 What did not change

Simulation is never evidence. Same author or same thread is one voice. Leads
never establish demand. The docs/04 authority table. Registry mutation only
through maintenance and human approval.

## §6 The calibration proves bridge behaviour, never shelf composition

Cited share of the shelf and documents cited are DIAGNOSTICS, reported and
never gated. `tests/calibration_acceptance.py` evaluates nine canaries
(statuses PASS / FAIL / NOT_TRIGGERED / NOT_EVALUATED); the run passes when
every mandatory canary for the mode is PASS and no non-advisory canary is FAIL:

| # | canary | pass when | class |
|---|---|---|---|
| 1 | corpus_independence | ≥1 kept concept not explicitly named by any source passage (`corpus_named` false — the run's rows, plus the corpus-wide **CorpusPresenceReceipt** from `corpus_polymath.py --presence` when audited) | mandatory |
| 2 | heterogeneous_source_reasoning | **SOURCE_AGNOSTIC_CALIBRATION only** (`--calibration-mode`, explicit): a configured heterogeneous row (`--heterogeneous-docs`) fed a valid latent structure or a valid hypothesis hop — generation, never survival; the hypothesis may die. STANDARD runs report NOT_EVALUATED: any source MAY generate, no source MUST | mandatory in the dedicated mode |
| 3 | noun_echo_resistance | a corpus-named concept without independent grounding was refused (echo verdict) | conditional: NOT_TRIGGERED when θ proposed no echo |
| 4 | legitimate_corpus_overlap_survival | a concept that overlaps the corpus (corpus-named OR example overlap — both counts exposed) WITH ≥3 voices from ≥2 communities kept its leads | conditional |
| 5a | open_field_population_discovery | an OPEN_FIELD community outside the seed set was instantiated with real records | mandatory |
| 5b | latent_population_resolution | a LATENT lead whose `latent_structure_id` is an admitted latent structure is INSTANTIATED with admitted field records whose `lead_id` points back to it — OPEN_FIELD never satisfies it | advisory in STANDARD, mandatory in SOURCE_AGNOSTIC_CALIBRATION |
| 6 | field_originated_opportunity | ≥1 kept concept is field-originated (`field_origin` ∈ {FIELD_NAMED, WORKAROUND_DERIVED} AND not corpus-named) AND its hypothesis cites corpus rows | mandatory |
| 7 | irrelevant_source_rejection | a configured KNOWN trap row (`--trap-text`) was retrieved, classified IRRELEVANT and referenced by nothing | mandatory |
| 8 | hypothesis_death | ≥1 corpus-derived hypothesis (hops cite corpus rows) ended REJECTED BECAUSE of field evidence (contradicting observation on its gap, or a challenge / evaluation citing admitted field refs) | mandatory |

The run passes when every mandatory canary for the mode is PASS and no
non-advisory canary is FAIL. Every concept carries a receipt with
`corpus_named`, `corpus_example_overlap` and `field_origin` exposed separately.

**Field origin (deterministic, `provenance.field_origin`)** — FIELD_NAMED: a
participant explicitly named it (a `products_named` entry equal to the concept
phrase, a ≥2-token entry contained in it, a concept bigram inside an entry, or
the concept phrase in the participant's own words). WORKAROUND_DERIVED: the
concept's form factor maps onto a real admitted workaround (a shared bigram or
≥2 shared content terms) with no claim the participant named the product.
NOT_FIELD_ORIGINATED otherwise — one generic shared token never establishes
lineage, and only records with valid field provenance (author identity and a
recoverable quote) count.

**Corpus presence (`CorpusPresenceReceipt`)** — "not named in the retrieved rows"
is not "not named in the corpus". `corpus_polymath.py --presence --state run.json`
asks the backend, with existing calls only (`GET /documents` for
`documents_checked`, `POST /retrieve` for the concept's normalized phrase, whose
default lane includes the corpus-wide in-memory lexical scan), and writes one
receipt per final concept: `exact_phrase_hits`, `normalized_multi_token_hits`,
`observed_product_hits`, `example_hits`, `document_hits`, `named`,
`method_version`. Presence answers NAMING only; its evidentiary authority for
current demand is NONE (Law 3). `calibration_acceptance.py --presence FILE`
consumes it; `provenance.lineage` consumes `data.corpus_presence` when present.

A canary that dies in the field still counts for the generative adapter
(canary 2): the test is whether the bridge was built, not whether it survived.

## §7 Heterogeneous shelves are the real test

After the first run, add deliberately different documents — a novel, a
technical manual, a field manual, a biography, an anthropology text, a design
book, a sports book, a history — and ask whether the same interpretation
architecture pulls useful latent structure from all of them. Ten similar
business books test almost nothing.

## §8 Document scope and the unscoped answer path (policy B)

`controller.py init --document-id <id>` (repeatable) or `corpus_polymath.py
--document-id <id>` restricts the corpus lanes to a subset of documents.
The adapter threads `document_ids` into `POST /retrieve` and `POST
/retrieve/plan` (DOCUMENT-SCOPED-RETRIEVE-V1, applied at the stores before
`limit`). `/chat` cannot be scoped, so while a scope is active the adapter
never calls it: rows come from retrieve/plan only and θ interprets locally
(`corpus_backend.chat_skipped` records the decision). A backend that does not
advertise `contracts.document_ids` gets `document_scope_warning` — the scope
is then a request, not a guarantee. Forced document diversity is still not a
metric; the scope exists for deliberate experiments (one book, one shelf).

**Fail closed.** A scope is a guarantee. If the backend does not advertise
`capabilities.contracts.document_ids`, `corpus_polymath.py` issues no request at
all and writes `capability_failure {capability: document_scoped_corpus_retrieval,
blocked: BLOCKED_CAPABILITY_UNAVAILABLE}`; the controller records it as a
coverage deficit. `--generic` does not bypass the check. Never continue
unscoped, never drop the scope, never a warning alone.


## §9 Fail-closed lineage (senior review, 2026-09-04)

Unclassified rows may sit in the retrieval context and be read. They can never
become lineage: a latent structure's or corpus observation's `evidence_refs`,
a primitive's `evidence_refs`, a hypothesis hop, or a structural analogy must
name rows that exist and are classified in `row_relevance` as anything but
IRRELEVANT. `hypothesize` may classify the rows it is about to cite by
submitting `row_relevance` in the same payload (the map merges). Canary 6
uses `corpus_named`, never token overlap with the whole corpus; canary 8
requires a field cause (contradicting observation, or a challenge/evaluation
that cites admitted field evidence); canary 7 requires a configured trap text
that was retrieved, classified IRRELEVANT and referenced by nothing.

