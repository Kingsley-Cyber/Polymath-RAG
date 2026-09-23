---
change_id: DOCUMENT-RAG-PLAN-ADMITTED
owner: "@king"
date: 2026-09-23
status: complete
architecture_impact: "none — documents only. Admits DOCUMENT-RAG-COMPLETION-V1 as the plan of record and records the owner's decisions D1–D8. It amends FINAL l.39 / §47, WLK2C non-displacement and ELITE §6 rule 1 for chat document RAG; code follows in slices S0–S9."
last_reviewed: 2026-09-23
---

# DOCUMENT-RAG-COMPLETION-V1 admitted; owner decisions D1–D8 answered

## Contract
Owner, 2026-09-23: "Tell me which needs a plan first so you can create it, but give me the prompt and ask me the decisions you
need for the plan." The owner answered the four questions:
- D1: adopt grounded learning value.
- Approvals: always retrieve for corpus questions (D2); switch off the resolution lift (D3); merge bridge planning (D5).
- D4, atoms alongside, was paused: "Defer until the implementation shows that existing profile routes cannot supply the
  required concepts. Running old and new atoms together also needs correct deduplication."
- D6: measure first, then set.
- D8: one hop only.
- D7 follows the owner's standing rule (5–8 live turns first).

## Changes
- NEW `docs/wiki/plans/DOCUMENT-RAG-COMPLETION-V1.md`:
  - Part A: the governing law, with the amendment table;
  - Part B: the compiler contract;
  - Part C: retrieval execution;
  - Part D: path-aware admission;
  - Part E: the synthesis contract;
  - Part F: measurement and acceptance;
  - slices S0–S9 and a Do Not Do list.
- `docs/wiki/plans/CONTINUITY-REPORT.md`: the CURRENT header names the plan; the decisions are marked answered; the plan
  section is marked admitted.
- Register 11.421; a scaffold `TREE` entry for this work-log.

## Proof
- The plan cites the audit (`docs/wiki/reports/2026-09-23/ENRICHMENT-SURFACES-AUDIT.md` §5, §9–§15) and the input spec
  (`docs/document-rag/inputs/2026-09-23-rag-compiler-contract.md`). Every behavioural claim in it is anchored there.
- The owner's answers were recorded from the decision form in this session.

## Rejected claims
- "Re-project the v3.2 atoms now": paused by the owner (D4). The profile multivectors already store those items as vectors,
  so S6 measures whether they suffice first.
- "The plan settles the judge implementation": it names two candidates and chooses by evidence in S7.

## Open contract gaps
- None changed (documents only): NOT_AFFECTED.
- The amended laws take effect slice by slice, behind flags. Flag defaults flip only on the owner's word (S9).
