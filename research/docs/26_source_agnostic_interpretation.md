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
never gated. `tests/calibration_acceptance.py` evaluates eight canaries
(statuses PASS / FAIL / NOT_TRIGGERED / NOT_EVALUATED); the run passes when
every mandatory canary is PASS and nothing is FAIL:

| # | canary | pass when | class |
|---|---|---|---|
| 1 | corpus_independence | ≥1 kept concept not explicitly named by any source passage (`corpus_named` false) | mandatory |
| 2 | heterogeneous_source_reasoning | ≥1 hypothesis or latent structure cites a row from a configured non-business document (`--heterogeneous-docs`) | evaluated when configured |
| 3 | noun_echo_resistance | a corpus-named concept without independent grounding was refused (echo verdict) | conditional: NOT_TRIGGERED when θ proposed no echo |
| 4 | legitimate_echo_survival | a corpus-named concept WITH ≥3 voices from ≥2 communities kept its leads | conditional |
| 5 | latent_population_discovery | an OPEN_FIELD or LATENT-derived community outside the seed set was instantiated with real records | mandatory |
| 6 | field_originated_opportunity | ≥1 kept concept is field-originated AND its hypothesis cites corpus rows (deepened by the corpus) | mandatory |
| 7 | irrelevant_source_rejection | ≥1 retrieved row classified IRRELEVANT rather than forced into an analogy | mandatory |
| 8 | hypothesis_death | ≥1 corpus-derived hypothesis (hops cite corpus rows) ended REJECTED after meeting field evidence | mandatory |

A canary that dies in the field still counts for the generative adapter
(canary 2): the test is whether the bridge was built, not whether it survived.

## §7 Heterogeneous shelves are the real test

After the first run, add deliberately different documents — a novel, a
technical manual, a field manual, a biography, an anthropology text, a design
book, a sports book, a history — and ask whether the same interpretation
architecture pulls useful latent structure from all of them. Ten similar
business books test almost nothing.
