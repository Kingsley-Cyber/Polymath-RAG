---
change_id: COMPILER-CONTRACT-INPUT
owner: "@king"
date: 2026-09-23
status: complete
architecture_impact: "none — documents only. A proposed compiler specification the owner shared is admitted byte-identical as an input to the document-RAG plan, and assessed against the existing compiler. No code, flag, schema or data change."
last_reviewed: 2026-09-23
---

# Proposed "RAG compiler for grounded discovery" — admitted as input, assessed against the existing compiler

## Contract
Owner, 2026-09-23: "Concept idea alert for your input and honest opinion and way ahead for incorporation." The owner then
pasted a summary and the full specification. The file is saved outside the repository at
`~/.codex/.chatgpt-projects/g-p-6aa0db750e248191a904880fcd6f1c1c/rag-compiler-contract.md`. The owner has not decided on it.

## Changes
- NEW `docs/document-rag/inputs/2026-09-23-rag-compiler-contract.md`: byte-identical copy (sha256
  `ff71a2bff0fda2ff58c1d91fde4b2c6b0dc0b5b32bdab2b9701a5fb7d05f6e13`, `cmp` verified). It lives outside `docs/wiki/` so its
  bytes stay the owner's.
- `docs/wiki/reports/2026-09-23/ENRICHMENT-SURFACES-AUDIT.md` §14:
  - the assessment (adopt, adapted);
  - a field-by-field map to `ChatPlan` / `CompiledQuery`;
  - nine adaptations;
  - the risks.
- `docs/wiki/plans/CONTINUITY-REPORT.md`: the plan-of-record step now includes the compiler contract as its Part B.
- Register 11.419; scaffold `TREE` entries for the 2 new files.

## Proof
- READ: `shared/polymath_shared/chat_plan.py:119-175`, the `CompiledQuery` and `ChatPlan` fields.
- EXECUTED (read-only, $0) on the last 40 plans (3 days, 223 queries):
  - `retrieval_goal` filled 0 / 40;
  - `must_answer` 39 / 40;
  - `target` 137 / 223. It holds a doc id on bridges, e.g. `br0 … target: doc_2d63…`, and `profile_surface: TENSION`.
- EXECUTED, compiler lanes over 7 days (1,490 plans): primary gemma 1,344; backup lanes 146 (10%); deterministic fallback
  76 (5%).

## Rejected claims
- "The compiler contract needs a new service or framework": it extends the existing `ChatPlan` / `CompiledQuery`. The spec
  says the same.
- "The existing compiler already carries the learning need and each probe's purpose": `retrieval_goal` is never filled, and
  `target` is misused for doc ids on bridges.

## Open contract gaps
- None changed (documents only): NOT_AFFECTED.
- The owner decides whether to adopt the contract, and on report §14's adaptations. These include reversing B20 (no
  retrieval skip in the corpus-learning workflow) and merging the bridge compiler into the planning call.
