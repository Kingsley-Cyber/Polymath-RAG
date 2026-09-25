---
change_id: OWNER-NOTE-8-CODE-PMAP
owner: "@king"
date: 2026-09-24
status: complete
architecture_impact: "Documents only: owner note 8 stored verbatim; design rule R12 and the code pMAP contract in CODE-RAG-IMPLEMENTATION-V1; §6 item 7 answered."
last_reviewed: 2026-09-24
---

# Owner note 8: code units from the deterministic parser, code pMAP from complete bodies

## Contract
- The owner, 2026-09-24: "you need to ensure that the codes identifies all proper functions in respect to the code type.
  i thinks it should use the same logic used to create th determinisitc graph."
- In the same message: a pasted design ("generate code pMAP from the complete code bodies…"), carried forward by the owner
  as the decision for the plan, and "i decide for all your deficiencies found to be resolved".

## Changes
- `docs/code-knowledge-v1/ADDENDUM_2026-09-24_OWNER_NOTE_8_CODE_PMAP.md`: the owner's words + the pasted design, verbatim.
- `CODE-RAG-IMPLEMENTATION-V1.md`:
  - R12: one parser pass per file produces the symbol table that is BOTH the code graph's nodes and the enrichment's unit
    list (per-language unit types listed); no second unit detector; names locate, bodies establish behaviour;
  - the "Code pMAP contract": full-body requests (whole file when it fits the lane's limits, else every section with its
    resolved dependencies; syntax-boundary splits), upward rollups with source links, missing external references
    named, the 400 KB Power Apps hierarchy;
  - DAX / M unit shapes recorded, still candidates;
  - §6 item 7 answered yes.

## Proof
- Documents only; guards agent_preflight 0 · repo_guard 0 · wiki_worm 0.
- The note and R12 agree with R2 (structure from parsers only), R11 (no heading curation for code) and the external
  audit's full-source requirement (11.471).

## Rejected claims
- "Detect code units separately for enrichment": R12 forbids a second detector. The graph's parser output is the unit list,
  so coverage has one truth.
- "Describe a unit from its name": the note forbids it ("reading their bodies establishes what they do").

## Open contract gaps
- None (no code change). R12 and the contract bind C2 / C3 (the symbol table), C4 / C5a / C5b (per-language units) and
  C6 / C7 (full-body requests, rollups) when those slices are built.
