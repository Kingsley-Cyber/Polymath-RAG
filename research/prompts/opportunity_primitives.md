# Opportunity Primitive Extraction (primitives)
Do NOT think about products yet. From the corpus evidence, extract only the
reusable intermediate primitives — or honestly declare there are none.
Submit `primitives` (one object):
  generative_signal: true|false   ← false is a GOOD outcome for most passages
  drivers[], behaviors[], adaptations[], constraints[], frictions[],
  workarounds[], physical_interactions[], physical_jobs[], latent_values[],
  transferable_invariants[], unresolved_questions[],
  shared_predicates[]   ← use registry vocabulary where it fits
                          (carry/access/retain/separate/protect/set-up/clean/repair/attach)
Typed rows first: corpus rows tagged `typed:friction`, `typed:behavior`,
`typed:workaround`, `typed:purchase_language` are lived claims the extractor
already labelled from a verbatim quote — sort them into the matching
primitive before mining untyped passages, and cite them. Rows tagged
`field_evidence` are past community observations with an author and a
thread; they are the strongest corpus rows a primitive can cite.
Cite rows: add `evidence_refs: {"behaviors": [row ids], "frictions": [...], ...}` using the
`id` of the corpus_evidence rows each primitive came from (docs/19) — primitives
without a row behind them are opinions.
Rules: reason about the PEOPLE the passage is about, not only its topic. A
transcript about creators using Substack says nothing about microphones — but
it is about creators, and creators record, talk to camera, edit alone, work
from cafés, carry their kit. Their physical day is where products live. So:
identify the population, then state what they physically do, hold, carry,
wear, set up, wait for, and where it breaks. Items you INFER from the
population rather than read in a row go in the same lists but are named in
`inferred: ["…"]` and carry no `evidence_refs` — the bridge hypothesis must
then place them AFTER its evidence boundary, and the web lane tests them.
`generative_signal: false` only when no human population or activity can be
identified at all (pure ideas, no people). Never force ecommerce out of pure
ideas; never refuse a leap just because the document did not spell it out.
Frictions should use registry friction-family names when they genuinely match
(e.g. occupied_hand, movement_restriction) — that unlocks cross-domain transfer.
Transferable invariants are the bridge fuel: "a tool should interfere as little
as possible with the activity it enables" — no invariant, no cross-domain leap.

## Population leads (docs/25 §1)
Also submit `primitives.population_leads[]`: every population, activity or
context the rows NAME or clearly imply ("shift workers", "new parents",
"weekend club runners", "people who inject weekly") as
`{name, why, evidence_refs: [row ids], activities: [], contexts: [], frictions: []}`.
These are PLACES TO LOOK for the field lane — leads, never demand. A book that
mentions a population nominates it; only real records can instantiate it.
Name populations outside the one the signal itself describes whenever the
rows support it: that is where non-obvious products come from.

