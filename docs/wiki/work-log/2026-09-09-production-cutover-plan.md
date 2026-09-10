---
title: "WORK LOG — Production RAG migration cutover plan materialized via bidirectional archaeology; every retirement step gates on U-2"
change_id: PRODUCTION-RAG-MIGRATION-CUTOVER-V1
date: 2026-09-09
owner: governance
last_reviewed: 2026-09-09
status: complete (planning slice — plan materialized; no code/default/state changed)
register: 11.190
package: "docs/wiki/plans/PRODUCTION-RAG-MIGRATION-CUTOVER-V1.md"
architecture_impact: "None (planning + archaeology). Produces the cutover/retirement execution authority around the frozen final retrieval engine, with a per-component disposition matrix and a dependency-closure gate. No retrieval architecture change, no ranking/composition change, no default flip, no producer stop, no retirement. Establishes that the final engine is already the default legacy-state-free production runtime and that every remaining cutover step is transitively gated on U-2."
---

> **Ledger:** owner /goal 2026-09-09 (production cutover + retirement). Authorities consolidated:
> `FINAL-RETRIEVAL-ROUTING-SYNTHESIS-V1.md` (query-time) + `RETRIEVAL-MIGRATION-DEPENDENCY-V1.md` (retirement
> S-slices). Register **11.190**. No code, default, producer, or state changed.

## Contract

Requested outcome: produce the smallest dependency-ordered execution plan for everything still preventing the
final retrieval architecture from being the sole normal production architecture, disposition each legacy
component (KEEP / MIGRATE READER / STOP WRITER / RETIRE / DELETE-LATER) with FILE:SYMBOL evidence, and begin the
first non-owner-gated phase. Do NOT reopen retrieval design; respect the cinema forensic hold; do not change
ranking/composition.

- **Smallest acceptance:** a materialized cutover authority with the endpoint→engine map, a disposition matrix,
  the dependency-ordered phases, and a closure gate whose non-zero categories each carry a named blocker.
- **Owner / public contract:** governance. Public surface = `PRODUCTION-RAG-MIGRATION-CUTOVER-V1.md`.
- **Inputs / persistence:** FILE:SYMBOL grep + `legacy_dependency_census --runtime-only` + `graphify-out/`; output
  = one plan doc + ledger rows; NO runtime/state change.
- **Verifier / rollback:** the plan is self-verifying against HEAD (`bbe956d`); rollback = delete the doc + rows.

## Changes

Docs only — no runtime code:

- `docs/wiki/plans/PRODUCTION-RAG-MIGRATION-CUTOVER-V1.md` — the cutover authority (execution_authority: true;
  dependency_closure: PARTIAL with named blockers).
- `docs/wiki/plans/PLAN-AUTHORITY-REGISTER.md` — register row **11.190**.
- `docs/wiki/plans/CONTINUITY-REPORT.md` — cutover plan marked MATERIALIZED; next action = U-2 owner gate.
- `scripts/scaffold_polymath_v4.py` — declared the new files in `TREE`.

## Proof

Archaeology findings (FILE:SYMBOL-verified against HEAD `bbe956d`):

- **Final engine is already the default + legacy-state-free.** `chat_retrieval_flag()` defaults `v2`
  (`chat_retrieval.py:107`); `/chat`+`/chat/stream` run `chat_retrieve_v2` for all modes (`ui.py:2522`). The final
  modules read NONE of `parent_enrichment`/`retrieval_summaries`/`parent_summaries`/`summary_jobs`/
  `document_summaries` (grep empty).
- **Endpoint→engine map complete** (§3): `/chat`=final; `/retrieve`,`/ask`,`evidence`,`graph`,`wildcard`,MCP
  `retrieve`=v1 (KEPT lower-level contracts, not Chat bypasses to migrate).
- **Live legacy producers:** `auto_enrich_on_chunks` (`scheduler.py:235`) re-mints `parent_enrichment`; the
  summary worker writes the legacy summary tables. Both are STOP-WRITER targets — gated.
- **Master blocker:** every step past "readers use the final engine" is transitively gated on **U-2** (cinema
  forensic hold → coverage → S14 cutover → S16 reader-migration / S15+S17 producer-stop / D-14 retirement); the
  `INTENT_POLICY` default flip needs U-1 uplift which also needs coverage (U-2).
- Feature-flag inventory (§5): v2/vNext/router ON; `INTENT_POLICY` OFF (owner-gated), `SYNTH_ROLES` OFF (owner
  review), `DOC_PARENT_MAP_ENABLED` OFF (spend-gated).

Guards: `agent_preflight` ok · `repo_guard` ok · `wiki_worm --check` ok.

## Rejected claims

- **"A replacement exists, so the legacy component is obsolete now."** REJECTED — each component is dispositioned
  with its live readers + a gate; e.g. `routing_*` summary lanes are FINAL (KEEP), and `parent_enrichment` is
  still bridged by `map_trigger` into the final pMAP (MIGRATE, not delete-now).
- **"The cutover can proceed now that the final engine is default."** REJECTED — reader-migration/producer-stop/
  retirement are all gated on U-2; no safe non-owner-gated retirement step exists at HEAD.
- **"/retrieve and /ask must migrate to the final engine."** REJECTED — they are KEPT raw-evidence / lower-level
  contracts (MCP `retrieve` uses `/retrieve` deliberately); reader migration is DELETE-LATER, not a Chat bypass.

## Open contract gaps

- The whole cutover past phase 1 is **U-2-gated** (owner-authorized bounded Groq forensic probe → bounded canary
  → owner review → resumption → coverage → cutover). **Do NOT resume cinema pMAP backfill to obtain coverage.**
- `POLYMATH_CHAT_SYNTH_ROLES` default-enable is the first candidate default-flip but is a live presentation
  change → owner review (not taken here).
- The 102 unclassified runtime census symbols + 72 genuine legacy readers resolve at the coverage+cutover pass
  (S16), not before.
- No U-2 work started here; no producer stopped; no retirement performed.
