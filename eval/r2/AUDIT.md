# R2 Step-1 Audit: Current Synthesis Path (frozen trace)

Audited 2026-08-15 against HEAD `6fc5b67`. No implementation performed.

## Production path trace

`/chat` (orchestrator/orchestrator/api/chat.py)
→ retrieval result (LEGACY lanes / FAST / HYBRID / GRAPH)
→ `assemble_evidence_bundle` (shared/polymath_shared/evidence_assembly.py, v2)
→ `grounded_answer` (shared/polymath_shared/answer_synthesis.py, deterministic-template-v2)
→ final response.

## Recorded findings (R2 §1)

| Question | Finding |
|---|---|
| current synthesis algorithm | DETERMINISTIC TEMPLATES — `synthesize_claims` (one GRAPH claim per graph claim item; one TEXT passage claim per text item, verbatim excerpts via `_excerpt`) → `validate_claims` (typed lanes: graph token-surface grounding; text verbatim-containment) → `render_answer` (epistemic-prefixed graph sentences + `Relevant passage: "…" [n]` for text) |
| is a generative model used | NO. No LLM/generation client exists anywhere in the repository (no provider settings, no model pins, no sidecar for synthesis). |
| current answer contract | `contracts/answer/v2/chat_response.schema.json` (answer, citations, claims ledger, meta) — deterministic-template-v2 |
| current citation contract | citations reference bundle item ids (`bitem_*`), source doc ids, chunk locators; graph claims cite fact items; text claims cite passage items |
| current abstention condition | BOTH evidence lanes empty (no supported graph claims AND no supported text passages). D4/D4.1 remain frozen negative experiments: no support admission exists, so non-empty retrieval currently implies non-abstention (the D4 FAIL behavior). |
| how text evidence is rendered | verbatim excerpt passages with citations (TEXT lane claims) |
| how graph evidence is rendered | "Subject PREDICATE object [n]" sentences with epistemic prefixes + conflict notes (conflicts marked, never arbitrated) |
| does hierarchy survive into synthesis | NO — the EvidenceBundle v2 is FLAT (ordered items with lane/kind typing); the GRAPH mode's hierarchical structure (documents→sections→evidence) exists only in the /retrieve response and is flattened before the bundle |
| are summaries distinguishable from child evidence | PARTIALLY — items carry `text_kind` (document_summary / section_summary / child_chunk), but the TEXT lane validation treats them identically (verbatim passage containment), so summaries can pass as supporting text items (the D4.1 document-summary false-support finding applies) |
| can multiple documents be jointly reasoned over | NO — each claim is validated against its own support items; there is no composition/aggregation stage (COMPOSITION_REQUIRED category recorded in D4.1, unresolved) |
| can contradictions be represented | YES in the claims ledger (conflicts_with), rendered as a conflict note; never arbitrated |

## R2 §7 generation-model posture

- Pinned production synthesis model: NONE.
- Immutable generation contract: NONE (only the RESPONSE schema contracts/answer/v2 exists; no model/revision/provider/temperature contract).
- Provider alias usage: NONE.

**GENERATION MODEL CONTRACT = MISSING.**

Per R2 §7: STOP. Model selection requires a separate explicit decision;
no implementation is performed in this gate. The audit above is the
complete deliverable of R2 Step 1.
