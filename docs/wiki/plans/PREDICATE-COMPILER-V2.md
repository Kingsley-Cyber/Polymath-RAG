---
change_id: PREDICATE-COMPILER-V2
owner: governance
date: 2026-08-23
status: reference
architecture_impact: none (documentation; front matter added 2026-08-29 governance cleanup)
last_reviewed: 2026-08-29
---

# PREDICATE COMPILER V2 — semantic compilation architecture

Status: implemented this slice · Owner directive 2026-08-23 ·
Supersedes verb-dictionary scaling; keeps scientific ontology as final
semantic authority.

## The mistake v1 was heading toward

    verb surface ──> predicate            (manual dictionary)

v1 compiled ONLY literal rule-pack trigger surfaces. TEST.md matched
3 of 203 surfaces → zero anchors → zero facts. Scaling that design
means authoring every scientific verb forever.

## v2 architecture

    surface language
        |
    lexical semantics      (VerbNet 3.3 / PropBank / FrameNet 1.7 /
        |                   SemLink 2.0 — vendored, curated via
        |                   resource_index.yaml)
    semantic frame         (authored SCIENTIFIC event family:
        |                   training_event, evaluation_event, ...)
    typed argument roles   (UD/surface frames + admission classes)
        |
    signature validation   (subject/object CORE types + patterns,
        |                   negative examples FAIL CLOSED)
    scientific predicate   (the knowledge-graph vocabulary)
        |
    existing fact admission gates (F1-F8, unchanged)

## What is authored vs inherited

- AUTHORED (this repo): the scientific predicate ontology — which
  relation FAMILIES matter to a researcher, their type signatures,
  their negative examples.
- INHERITED (lexical resources): how language realizes each family —
  VerbNet class members / PropBank rolesets / FrameNet frames cited
  per realization with provenance; authored extensions marked
  `provenance: authored-extension` (never silently attributed).

## Integration points (no system replaced)

| Layer | Change |
|---|---|
| `evidence_proposer` | new FRAME lane: after compiled-trigger lanes miss, consults ontology frame realizations; emits EvidenceSpan with `trigger_lexical_class="FRAME"`, `trigger_match_source="frame:<id>"`. Deterministic; no neural similarity. |
| `rulepack/compiler.py` | FRAME-classed spans resolve frame + typed arguments -> predicate AT COMPILE TIME (types decide trained_on vs trained_with). No valid mapping -> UNSUPPORTED (fail-closed). |
| `candidates` binding | compound-head tie-breaker: generic scientific head nouns never win a slot over the compound's entity head. |
| admission, ledger, projection | UNCHANGED |

## Failure policy (owner)

No unrestricted verb lists, no embedding similarity, no LLM extraction,
no fuzzy guessing. A sentence must prove: entity types + semantic
frame + dependency relationship. Precision > recall.
