---
owner: @king
last_reviewed: 2026-09-07
last_touched: 2026-09-07
status: accepted
---

# WORK CONDUCTED — 2026-09-07 (session ending 18:28 MDT / 2026-09-08T0028Z)

Continuation of the DOCUMENT-SEMANTIC-INDEX-V1 phase. All work landed on `main`
through the protected-branch → four-green-checks → fast-forward workflow. Canonical
detail lives in the register rows and work-logs named below; this file is the
narrative index.

## Commits (fa49448 → HEAD), in order

| SHA | Slice / change | Register | Work-log |
|---|---|---|---|
| 6549398 | S0 — admit the next-phase plan + hook bootstrap | 11.129 | 2026-09-07-document-semantic-index-admission |
| 6203159 | S1 — deterministic `ParentSkeleton` | 11.130 | 2026-09-07-parent-skeleton |
| 1e22d28 | S2 — parent-map compiler | 11.131 | 2026-09-07-parent-map-compiler |
| ea09d97 | S3 — token packer / capacity model | 11.132 | 2026-09-07-map-batches |
| b030117 | Corrective checkpoint — 5 durable-contract fixes | 11.133 | 2026-09-07-map-contract-corrections |
| 8b3af46 | Groq routing policy + decision core (S7a) | 11.134 | 2026-09-07-groq-routing-policy |
| 26f3e73 | S4 — parent-map SQL durability (migration 0054) | 11.135 | 2026-09-07-parent-map-sql |
| 4fc931a | Live Groq map-contract canary + identifier fix | 11.136 | 2026-09-07-live-map-contract-canary |

## What each delivered (pure `shared/` + one migration + docs — no fleet wiring)

- **S0–S3 — the deterministic map-production core.** `shared/polymath_shared/document_profile/`:
  `parent_skeleton.py` (alias + salient extractive sentence + TF·IDF key terms +
  DETERMINISTIC exact identifiers per eligible parent; furniture accounted for via
  `document_region`), `map_compiler.py` (tolerant `MAP|…` DSL → strict-identity
  records, exact partial recovery, identifiers from the skeleton, injection-as-data),
  `map_batches.py` (measured density EMA, ~60-parent cap, combined-call formula, TPM
  guard, deterministic batch manifests). ~40 determinism pins.
- **Corrective checkpoint (11.133)** — BEFORE S4 could persist the contracts:
  source-bound `batch_hash` (no cross-document collision), `token_feasible_rpm`
  boundary fix, durable identity = parent `chunk_id` (never `chunk_index`),
  `map_completeness_hash` binds manifest+expected+valid+missing, real-fixture hook.
- **Groq routing (11.134)** — `GROQ-ROUTING-POLICY-V1.md` (account = capacity domain;
  both models share one account budget; capacity-aware selection; no round-robin /
  key-burning; tools disabled) + pure `groq_router.choose` decision core (13 pins).
  **No live wiring.**
- **S4 (11.135)** — migration `0054_document_parent_maps.sql`:
  `document_parent_map_batches` / `document_parent_maps` (one-active-map partial
  unique index) / `document_parent_exclusions`, keyed on the corrected contracts.
  Applied + verified on dev Postgres; idempotent; 5 durability pins. **No worker.**
- **Live canary (11.136)** — real cinema parents → S1 → map prompt → live
  `groq/compound-mini` → S2 compile. Two docs mapped 22/22 and 11/11 complete;
  parent_id = durable chunk_id; deterministic identifiers attached; injection (P0031)
  resisted; identifier rule tightened to ≥3 digits from a finding. Probes were
  scratchpad-only (no repo/fleet change).

## Verified this session

- All eight commits: four CI checks green each; `main` fast-forwarded to each.
- `agent_preflight` / `repo_guard` / `wiki_worm --check` green on the final tree.
- S4 migration idempotent on dev Postgres; the three parent-map tables live.
- Groq: key valid, `groq/compound` + `groq/compound-mini` confirmed as exact ids;
  the map contract works end to end on real documents.
- Fleet healthy after every `shared/` edit (auto-heal; one bundle hash).
- Corpus analysis (read-only): child chunks median ~108–140 tok (near the 128
  design), NOT too granular; the only granular cohort is `region_role='stub'` OCR
  noise (~7.5%). No chunker change made (owner NON-NEGOTIABLE).

## Not done — deliberately (see UNFINISHED-WORK.md / DEPENDENCY-MAP.md)

- **S5** profile vNext + fingerprint (next; first slice that spends LLM quota).
- **S6–S16** parent-map generation → projection → runtime lane → backfill →
  QUERY_READY flip (owner-gated for spend / fleet).
- **S7 live wiring** + **Part 4 reindex canary** — touch fleet config + Groq spend.
- **FINAL retrieval plan** — the file
  `POLYMATH_FINAL_RETRIEVAL_ROUTING_SYNTHESIS_IMPLEMENTATION_PLAN_2026-09-07.md` was
  NOT present in `~/Downloads`; admit it when supplied (same flow as S0).
