# E5 — Deterministic Concept Candidate Layer: Analysis

Frozen 2026-08-15. Analysis only; no production changes.

## Question

Can a deterministic concept candidate layer increase abstract-domain
recall WITHOUT degrading graph precision?

## Architecture grounding

The real goal is not "extract every noun." It is: durable identities
in the knowledge graph stay trustworthy, while retrieval still
understands broad concepts. The architecture ALREADY separates these
two concerns:

- GRAPH trustworthiness = GLiNER proposals + entity admission
  (GLOBAL/CORPUS_SCOPED/DOCUMENT_SCOPED/MENTION_ONLY) + the E3B
  binding gates. Only admitted spans become durable identities.
- Retrieval understanding = deterministic summaries (R1A
  retrieval-summary-v2) + child evidence + graph facts. Summaries
  ROUTE; children PROVE (R1A).

E4 established that GLiNER medium-v2.1 misses 10/13 lowercase
abstract psychology constructs at EVERY threshold and label schema —
a DISCOVERY limitation. A concept layer's natural sink is therefore
NOT the graph (abstract concepts are exactly the MENTION_ONLY-class
surface admission already parks), but the RETRIEVAL representations:
document/section summaries and the routing profile's concept
inventory.

## Measurement (frozen docs, deterministic prototype)

- The document text literally contains 12/13 gold strings
  ("working-memory" is hyphenated in the source — a boundary form
  GLiNER also misses).
- A 20-line deterministic noun-phrase extractor (content-token
  runs, ≥2 tokens, stopword-separated) recovers 6/13 EXACT vs
  GLiNER's 2/13 at the frozen 0.5 threshold, with NO model.
- The naive extractor proposes 90 phrases; non-gold proposals are
  verb phrases and overlong spans ("assign high confidence",
  "attempt retrieve", "automatically eliminate metacognition") —
  i.e., the precision lever is a noun-head grammar + frequency +
  the existing generic-head guard, all deterministic and measurable.

## Precision-impact analysis (graph)

The layer is OUTSIDE the extraction path by construction:

- It never creates entities, facts, admission decisions, or
  canonicalization inputs. The graph only ever receives compiler
  facts from GLiNER proposals under the frozen admission + binding
  gates.
- Therefore graph precision impact is STRUCTURALLY ZERO: no new
  nodes/edges can originate from the layer. This is not a claim that
  needs empirical graph re-qualification; it follows from the sink
  being retrieval-only.

## Precision-impact analysis (retrieval)

The real risk moves to the summaries: concept-inventory noise can
dilute routing embeddings (R1A showed shallow summaries hurt
routing; R1E showed naive concept expansion adds no reach value).
The mitigations are the ones already measured in this repository:

1. Bounded budget per summary (the R1A contract already caps
   sentences/chars; a concept inventory inherits the same
   discipline).
2. Generic-head guard (reuse the frozen GENERIC_HEAD vocabulary —
   no new blacklist).
3. Provenance-bound admission (which chunk produced each concept,
   like retrieval-summary-v2 provenance).
4. Versioned identity (summary_id-style content hashing).
5. Frozen qualification BEFORE promotion: R1B routing set (doc
   routing R@1 0.882 must not regress), the R1A coverage fixture
   (concept coverage must improve), and the metacognition routing
   controls.

## R1E relationship (not a contradiction)

R1E REJECTED ConceptState for PASS-2 corpus-reach expansion queries:
profile-derived concepts added zero complementary-document recall.
That finding does NOT transfer to this layer: the sink differs. Here
the sink is the PASS-1 routing summary itself — the representation
whose shallowness R1A measured directly. Enriching summaries with
missed abstract terms is exactly the R1A-documented gap; R1E was
about generating NEW queries from concepts.

## Verdict

YES — architecturally safe by structural separation (graph precision
untouched by construction) and demonstrably recall-positive at the
concept level (6/13 vs 2/13 with a 20-line deterministic prototype,
12/13 strings present in text). The open qualification is SUMMARY
PRECISION (routing regression + coverage improvement), which is
fully measurable with existing frozen sets before any promotion.
Recommendation: authorize E5B — a bounded, provenance-bound,
generic-guarded concept inventory inside retrieval-summary-v2, with
the R1B/R1A frozen sets as the promotion gate. No model, no
threshold changes, no graph-path changes.
