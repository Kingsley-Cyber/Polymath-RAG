# Source-agnostic interpretation (primitives) — docs/07, docs/19, docs/26

Do NOT think about products yet. Read the corpus rows as a reader of ANY
source — marketing book, psychology paper, novel, technical manual,
transcript, memoir — and extract the reusable latent structure, or honestly
declare there is none. Most passages yield almost nothing. That is correct.

Submit one object `primitives`:

  generative_signal: true|false   ← false is a GOOD outcome for most passages
  drivers[], behaviors[], adaptations[], constraints[], frictions[],
  workarounds[], physical_interactions[], physical_jobs[], latent_values[],
  transferable_invariants[], unresolved_questions[],
  shared_predicates[]   ← registry vocabulary where it fits
                          (carry/access/retain/separate/protect/set-up/clean/repair/attach)
  evidence_refs: {"behaviors": [row ids], "frictions": [...], ...}
  inferred: ["…"]        ← items you INFER from the population, no row behind them;
                          the bridge places them AFTER its evidence boundary, the field tests them

## Latent structures (docs/26 §1 — the actual adapter)
`latent_structures[]` (schema latent_structure.json): every structure a passage
exposes, typed by `kind` ∈ ACTIVITY, ROUTINE, OBJECT, OBJECT_INTERACTION,
BODY_STATE, ENVIRONMENT, CONSTRAINT, FRICTION, DESIRE, TRADEOFF, ADAPTATION,
WORKAROUND, SOCIAL_DYNAMIC, IDENTITY_SIGNAL, TRANSITION, FAILURE_MODE,
REPETITION, COORDINATION_PROBLEM, ACCESS_PROBLEM, COMFORT_PROBLEM,
STATUS_PROBLEM, ATTENTION_PROBLEM, TRANSFERABLE_INVARIANT, CAUSAL_MECHANISM.
Each: `id, kind, text, evidence_refs (row ids), applicability_outside_source
(where else this could hold), possible_populations[] (who might live it — a
lead, never a fact), shared_predicates[], physical_job, authority:
LATENT_HYPOTHESIS`. A sex-club scene in a novel may be useless, or it may
expose `privacy under a constrained environment`, `rapid access without
visible signalling`, `personal-item storage during a social activity` — write
the structure, not the scene. A structure with no population is fine: the
field lane will search for WHO experiences it.

## Corpus observations (docs/26 §3 — recorded, never stripped)
`corpus_observations[]` (schema corpus_observation.json): products, brands and
populations the rows NAME — `kind` OBSERVED_PRODUCT | EXAMPLE |
NAMED_POPULATION, `name, evidence_refs, job_served, mechanism,
populations_sharing_job, evidentiary_authority: NONE_FOR_CURRENT_DEMAND`. A
book that mentions compression socks lets you ask why the object was there
and what job it served; it never lets you conclude compression socks are an
opportunity. The named product may still win if the field grounds it.

## Row relevance (docs/26 §2 — axis 1, your call, φ's law)
`row_relevance: {row_id: LEXICAL_MATCH | SEMANTIC_MATCH | STRUCTURAL_ANALOGY |
IRRELEVANT}` for every row you looked at. Question-level rows carry
`lexical_overlap` and a hint: `SINGLE_WORD_OVERLAP` (one shared word such as
"hold" — the lexical trap) or `NO_LEXICAL_OVERLAP` (reached by embedding or
rerank only — judge the structure, not the words). A row you mark IRRELEVANT
can never back a hop or an analogy afterwards; not marking noise means it
stays in play.

## Population leads (docs/25 §1)
`population_leads[]`: populations, activities or contexts the rows name or
imply — `{name, why, evidence_refs, activities, contexts, frictions}`. Places
to look for the field lane, never demand.

Rules: reason about the PEOPLE and the physical world the passage contains,
not only its topic. Typed rows (`typed:friction` …) and rows tagged
`field_evidence` are the strongest rows a primitive can cite; cite rows —
primitives without a row are opinions. Frictions use registry family names
when they genuinely match; transferable invariants are the bridge fuel.
`generative_signal: false` only when no meaningful latent structure,
interaction, constraint, behavior, mechanism, transferable invariant or other
searchable opportunity primitive can be extracted.
A named population is never required — a structure with no population becomes
a population search (LATENT PROBLEM → population). Never force ecommerce out
of pure ideas; never refuse a leap because the document did not spell it out.
