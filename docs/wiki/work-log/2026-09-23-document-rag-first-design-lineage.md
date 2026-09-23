---
change_id: DOCUMENT-RAG-FIRST-DESIGN-LINEAGE
owner: "@king"
date: 2026-09-23
status: complete
architecture_impact: "none — documents and one read-only probe. Records the owner's sequencing decision (document RAG before CODE-KNOWLEDGE-V1) and where the owner's retrieval idea is already written, built and contradicted. No code, flag, schema or data change."
last_reviewed: 2026-09-23
---

# Document RAG before code RAG — and what the repository already says about the owner's idea

## Contract
Owner, 2026-09-23: "Essentially, before we work on code RAG, we must complete document RAG."
- Alongside the pMAP, the structure extraction's conditional ranking and the document-level extractions should power
  document- and domain-level synthesis with different ideas.
- "However, the reranker number shouldn't be the final determinator."
- "Each skeleton such as questions, searches, concepts, theories, etc. should be treated as modular conditional bridges and
  rankings. I don't think I designed and solidified the idea… I'm not sure."
- Outside GNN, the idea: when I submit a query, subqueries allow bridges and document routing, chunk / document routing
  retrieval and synthesis.
- "WILDCARD was supposed to be the poster-child retrieval layer that fully empowers and embodies this."
- It was made to abstract a document so much that domain-level synthesis and bridges allow latent chunks related to the
  query to win and be retrieved.
- "Can you confirm this?"

Then, same turn: "We have to be careful selecting concepts and theories as hydrations to be fed, because they can also be more powerful if used as abstraction bridging and routing for relevant chunks from other documents and / or chunks. Essentially I don't know how to design this where they can be used to find real document chunks relevant to my query, unless they are used as subqueries for sparse and dense? Ensure to update the notes."

## Changes
- `docs/wiki/reports/2026-09-23/ENRICHMENT-SURFACES-AUDIT.md` §10:
  - claim-by-claim design lineage with file:line anchors in FINAL, ELITE, WLK2A and LQF-V2;
  - what is built;
  - what contradicts the idea;
  - the WILDCARD finding and the verdict;
  - the sequencing.
- Report §11: the rule (concepts / theories are routers to real chunks; their text reaches synthesis only as a labelled derived principle bound to a real chunk). Also a design sketch, a PROPOSAL for the owner to confirm:
  - select a few items per turn through the unused concept / theory multivectors;
  - route each through three doors: global child search, home document's pMAP, neighbour documents' concepts;
  - judge with the two-hop value plus a q0-groundedness floor;
  - feed the same items to the bridge compiler.
- NEW `docs/wiki/experiments/enrichment-surfaces-2026-09-23/wildcard_probe.py` / `.json`: WILDCARD replays of real turns, plus
  the atom-frontier calls run directly.
- `docs/wiki/plans/CONTINUITY-REPORT.md`: the Active Mission is now document RAG completion; CODE-KNOWLEDGE-V1 is parked
  behind it. Next Action, Do Not Do and the unpushed count are updated.
- Register 11.417; scaffold `TREE` entries for the 3 new files.

## Proof
- READ, anchors re-read at `6de1d01` (code unchanged since `7eb767d`):
  - FINAL: l.39 "cross-encoder = final judge", l.190 (§1.2), l.451 (§7), l.1768 (§40), l.1829 (§41), l.2244 (§51);
  - ELITE: l.190 (§6), l.214 (WildcardValue), l.243, l.245 (§7);
  - WLK2A: l.76, l.88, l.96;
  - LQF-V2: l.21-24;
  - `chat_retrieval.py:907-920` (the atom frontier inside `except: pass`).
- EXECUTED (read-only, $0, no LLM): `wildcard_probe.py` on the 4 latest WILDCARD turns that retrieved:
  - 55–59 latent candidates → 3 verified bridges each;
  - all 12 bridges come from the `abstraction` / `transfer` channels;
  - the direct atom frontier yields 12 atoms → 16 parents per turn, with no error.
- EXECUTED: 127 of 1,508 turns carry `retrieval_skipped = true` (receipts, 7 days).
- Guards: see the commit.

## Rejected claims
- "The owner never designed this": most of it is written, in four owner-authorized plans. What is missing is the
  consolidation, and the amendment of FINAL's "cross-encoder = final judge" law.
- "WILDCARD's atom frontier is broken": it runs and nominates 16 parents per turn. It loses every bridge slot to the latent
  points. Its failures would be invisible (bare `except: pass`, no receipt key), but none occurred in the probe.
- "The replay's embedder 422 is a live bug": that turn's compiler skipped retrieval (empty plan). The probe now excludes
  such turns.

## Open contract gaps
- None changed (documents and a read-only probe): NOT_AFFECTED.
- Document RAG completion: its plan of record is to be written first, and it needs the owner's confirmation of the design
  (report §10 verdict). It amends FINAL's governing law, so it is an owner decision, not an agent one.
- CODE-KNOWLEDGE-V1: DEFERRED by the owner's sequencing, behind document RAG completion.
