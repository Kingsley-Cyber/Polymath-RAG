---
change_id: CODE-RAG-E2E-AUDIT-ADMITTED
owner: "@king"
date: 2026-09-24
status: complete
status_note: "Documents only. Two owner questions stay open in CODE-RAG-IMPLEMENTATION-V1 §6: items 6 (a reference book shared across projects) and 7 (per-unit descriptions for code)."
architecture_impact: "Documents only: the external end-to-end audit stored verbatim, a reconciliation, design rule R11 (the owner's no-heading-curation rule for code), amendments to C1/C2/C3/C6/C7/K1/C9/C10, R7 amended, gap row C-28, C-26 narrowed."
last_reviewed: 2026-09-24
---

# External end-to-end audit of the code RAG plan: admitted and reconciled

## Contract
- The owner, 2026-09-24: "take a look at this analysis audit" (a file in the owner's ChatGPT/Codex project). In the same
  message: "pmap does a determinsitic parse and curations of docuemnts headings and subheading but for codes i dont want
  thats".
- Admission rule (bootstrap Step 0): a plan or review that lives only outside the repository is invisible to the next
  session.

## Changes
- `docs/code-knowledge-v1/ADDENDUM_2026-09-24_EXTERNAL_E2E_AUDIT.md`: a provenance header + the audit verbatim
  (diff-checked identical).
- `docs/wiki/reports/2026-09-24/CODE-RAG-E2E-AUDIT-RECONCILIATION.md`: a verdict per item (A1–A11), the owner's rule,
  and the narrowed C-26 question.
- `CODE-RAG-IMPLEMENTATION-V1.md`:
  - R11 (code never goes through the heading skeleton or its curation);
  - R7 amended (hash the exact context supplied, callee bodies included);
  - an "Amendments admitted 11.471" block binding C1, C2 / C3, C6 / C7, K1, §3, C9 / C10;
  - §6 items 6 (a shared reference book) and 7 (per-unit descriptions).
- Gap register:
  - C-28 new: intake computes the id from normalized bytes before materialization, so the planned passthrough comes
    too late;
  - C-26 narrowed.

## Proof
- A1, READ: `workers/workers/intake_worker.py:168-172` calls `normalize_document_bytes(raw, strip_bom, normalize_crlf)`
  and then `document_id(normalized)` / `sha256(normalized)` before `materialize` (`:186`); `identity.py:95` documents
  the NFC normalization.
- A2, READ: `intake_worker.py:221-231` raises on identical content already owned by another corpus (existing row C-26).
- The audit body in the repository equals the source file (`diff` exit 0 on everything after the 10-line header).
- Guards: agent_preflight 0 · repo_guard 0 · wiki_worm 0.

## Rejected claims
- "The audit's FAIL means the book RAG is broken": the audit itself says it judges only the (unbuilt) code path.
- "Admit DAX and M as V1 languages now": the owner's earlier word was "later"; they stay candidates (§6 item 4).
- "Install one of the listed code-RAG products": the audit rejects it too. The shortlist is study material, and
  GitNexus is noncommercial.

## Open contract gaps
- None (no code change). The amendments bind K1, C1, C2, C3, C6, C7, C9 and C10 when they are built.
- Owner questions: §6 item 6 (a shared book → multi-corpus queries) and item 7 (keep per-unit descriptions).
