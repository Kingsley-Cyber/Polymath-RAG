---
change_id: TRAIL-AUDIT-ADMITTED
owner: "@king"
date: 2026-09-25
status: complete
status_note: "Documents only. Five owner questions and the order (A-track before or after K1) are open in the reconciliation."
architecture_impact: "Documents only: the external Trail Signal holistic audit stored verbatim, a reconciliation, gap rows A-01..A-08, a CONTINUITY pointer."
last_reviewed: 2026-09-25
---

# External Trail Signal holistic audit: admitted and reconciled

## Contract
- The owner, 2026-09-25, handed over the path of an external audit in the owner's ChatGPT/Codex project
  (`TRAIL-SIGNAL-HOLISTIC-AUDIT-AND-IMPLEMENTATION-BRIDGE.md`).
- Admission rule (bootstrap Step 0): a review that lives only outside the repository is invisible to the next session.

## Changes
- `docs/wiki/reports/2026-09-25/TRAIL-SIGNAL-HOLISTIC-AUDIT.md`: front matter, a provenance note, then the audit verbatim
  (`diff` against the source: identical).
- `docs/wiki/reports/2026-09-25/TRAIL-SIGNAL-AUDIT-RECONCILIATION.md`: a verdict per finding (REQ-01..REQ-17), a proposed
  order, five owner questions.
- `GAP-REGISTER-LLM-BACKEND-AND-CODE-RAG.md`: new section A (adapter workflow), rows A-01..A-08.
- CONTINUITY: the audit and its order proposal in Active Mission / Next Action.

## Proof
- Eleven findings re-checked by reading the code at `0e2451e4` and confirmed (file:line in the reconciliation):
  - REQ-01: the API is the only production `service.start` caller; the control tick has no discovery path;
  - REQ-02: the worker leaves HARNESS_ACTION to the host;
  - REQ-03 / REQ-12 / REQ-13: the maintenance creator has no production caller;
  - REQ-04: `C_lineage_route` ignores `generative_signal`; `signal_gate` is standalone only;
  - REQ-05: geography / freshness never reach Trail (`geography=None` × 3);
  - REQ-07: gaps are re-offered across origins, and `M_loop` exits on Trail gaps only;
  - REQ-08: `_cited_ids` checks `*_ids` keys only;
  - REQ-10: no `knowledge_role` anywhere (K-01 / K-02);
  - REQ-17: the older adapter lacks `context.semantics.trail`.
- Guards: agent_preflight 0 · repo_guard 0 · wiki_worm 0.

## Rejected claims
- "The FAIL means the RAG or the governed workflow is broken": the audit judges the full autonomous vision; the saved real
  run (`adr_c994b32a…`) completed with a governed refusal.
- "Start the automation now": the audit itself says it authorizes nothing; the autonomy mandate is the owner's.
- "Replace pMAP / the RAG": the audit rejects it too.

## Open contract gaps
- None changed (no code). Gap rows A-01..A-08 are OPEN; T-01 and K-01 / K-02 already owned their findings.
