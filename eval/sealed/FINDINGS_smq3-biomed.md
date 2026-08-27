# SMQ3 — sealed biomedical qualification (Phase D, release closure)

Set: smq3-biomed — "A Circumplex Model of Affect" (Posner/Russell/
Peterson-style review; 93 KB markdown, OCR-mangled punctuation).
Sealed at v4-semantic-freeze-37-g9f888c4 (re-seal after Phase B
engineering closure; original seal 7f018ee; authority fd68fc57).
Run replay: DETERMINISTIC. Stamp recorded (facts_count 12,
canonical_count 6, canonical_hash 0222460d…).

## Verdict: QUALIFIED WITH KNOWN LIMITATIONS

## The Phase D question: hedged/causal biomedical language

**PASS.** The document argues extensively about neural systems
*causing*, *modulating*, and *underlying* affect — all of it hedged
academic prose. The pipeline produced **zero causal predicates**. Every
hedged causal claim abstained; the abstention inventory shows the
expected CONTEXT_REQUIRED wall ("tension and energy", "valence and
arousal", pronouns). No false causal edge exists. This is exactly the
`no edge > wrong edge` posture the freeze demands.

## Release-significant finding: citation-region wrong edges

Of the 2 ACCEPT canonical facts, at least one is a **wrong edge**:

- `alias_of(nakamura, nomoto)` — source is a reference-list author
  string: "Nakamura, H., Tanaka, A., Nomoto, Y., Ueno, Y., & Nakayama,
  Y. ~2000!". Two different cited authors asserted to be the same
  person. False identity claim.
- `associated_with(dsm-iv, doyle & faraone)` — also citation soup
  ("~Pliszka, 1998; Sasson, Chopra, Harrari…"); weak predicate, weak
  harm, same root cause.

Root cause: bibliography text is grammatically alien (comma-separated
surname/initial runs, OCR tilde-bang year markers) and the alias/
association rules fire on its punctuation shapes. The predicate
ontology and compiler are frozen; no fix inside this mission.

**Future gate: CITATION-REGION-SUPPRESSION-V1** — LAYOUT-EVIDENCE-V1
already persists layout at intake; a gate can classify reference-list
regions from layout evidence and suppress relation candidacy there
(candidacy, not evidence: mentions and retrieval must survive).

## Invariant adjudication

1. `no identity fragmentation` FAIL (2): "circumplex model" ×2,
   "lazarus" ×2 — the known row-51 fragmentation class
   (KNOWN_LIMITATIONS #1); wrong-merge count remains 0.
2. `no orphaned semantic rows` FAIL (1,091): the check is GLOBAL, not
   corpus-scoped. smq3's own entities have **0 orphans**; the 1,091 are
   residue of the deliberate wipe policy (entities/facts persist across
   corpus wipes because ids are content-addressed and shared). Harness
   scoping artifact, not an smq3 defect.
3. `every fact has exact-span evidence` PASSES on `span_offsets IS
   NULL` but these evidence rows carry `[]` (empty, non-null) —
   the invariant is weaker than its name. Harness gap, recorded.

## Numbers

- 2 canonical ACCEPT facts projected 2/2 with eligible endpoints
- 12 fact-evidence rows; canonical rows 6 (incl. non-ACCEPT decisions)
- Fragmented surfaces: 2; wrong merges: 0; orphans attributable: 0
