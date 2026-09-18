---
title: "WORK LOG — P5b-b: Profile Scout pre-plan wiring + B16 title-injection retirement"
change_id: PROFILE-SCOUT-P5B-WIRING
date: 2026-09-18
owner: librarian
last_reviewed: 2026-09-18
status: complete
architecture_impact: "Wires the Profile Scout into the compiler pre-plan and RETIRES the B16 title injection (_compiler_titles). ui.py gains _profile_scout (flag POLYMATH_PROFILE_SCOUT, default off, fail-open) + _scout_source_names; _compile_chat_plan calls the scout instead of _compiler_titles and feeds the nominated docs' source_names through the SAME compile_plan(titles=) channel (no planner signature change); the compiler receipt renames titles -> scout. Behaviour is INERT until POLYMATH_PROFILE_SCOUT=1 + a fleet bounce (live qual L1-L5)."
---

## Contract
Replace the retired B16 title injection with the Profile Scout as the sole pre-plan reconnaissance
(owner 2026-09-18). q0 stays authoritative; the scout informs, never gates; a scout miss/failure
degrades to no conditioning (fail-open). Bounded, observable, feature-governed. Acceptance: the
scout is default-off, fail-open, and feeds the existing compiler title channel; `_compiler_titles`
is gone; the compiler path is F-clean and inert until the flag is enabled.

## Changes
- `orchestrator/orchestrator/api/ui.py`:
  - RETIRED `_compiler_titles` (B16, register 11.122).
  - Added `_profile_scout(message, corpus_ids)` — flag `POLYMATH_PROFILE_SCOUT` (`os.environ`, default
    off); embeds q0 via `_embed_queries`, runs `profile_nominate` + `search_atoms` per corpus,
    normalizes with P5b-a helpers, `fuse_profile_scout_hits`, returns nominated docs' `source_name`s
    + receipt. Fail-open (any error → `[]`); never raises.
  - Added `_scout_source_names(doc_ids, corpora)` — order-preserving doc_id → source_name (parameterized read).
  - `_compile_chat_plan`: calls `_profile_scout` (was `_compiler_titles`), feeds `compile_plan(titles=...)`
    (unchanged signature), receipt `plan.compiler["scout"]` (3 sites) + reader renamed `titles`→`scout`.
- `scripts/legacy_dependency_census.py`: `compiler_title_context` marked RETIRED (symbols → `POLYMATH_PROFILE_SCOUT`/`_profile_scout`).

## Proof
`ast.parse(ui.py)` OK. `ruff --select F,E9` on ui.py: the 6 findings are ALL pre-existing ELITE debt
(1050/1075/1775-`offset`/2515/3099/3100) — NONE in the added functions (1671–1745); my code is
F-clean. `ruff --select S` added no findings. The pure normalization + fusion the wiring calls are
unit-proven (P5a 11/11, P5b-a +3). Flag-OFF path is a trivial early return (no I/O). **Live path
(flag-on) is L1–L5**: the worktree cannot import the `orchestrator` editable package (its `.pth`
finder resolves to the MAIN checkout), and it needs live Qdrant + a fleet bounce — so the flag-on
behaviour is qualified in the coordinated live window, not here.

## Rejected claims
- Change `compile_plan`'s signature to take a `PrePlanContext` (rejected for v1 — reused the existing `titles=` channel; smallest blast radius, no QUERY_PLANNER contract break).
- Gate B16 behind the flag instead of retiring it (rejected — owner: retire the title injection, no parallel title-based hint).
- Unit-test `_profile_scout` with heavy mocks (rejected — that proves mocks, not the real owner path; the pure parts are tested, the I/O path is L1–L5).

## Open contract gaps (impact dispositions)
- `PROFILE_SCOUT_WIRING`: **UPDATED** (now live in code, default-off). `PROFILE_SCOUT_INPUT`: **UPDATED** (normalization wired). Both need `paths` filled in the contract map + L1–L5 live proof.
- `QUERY_PLANNER`: **TESTED_UNCHANGED** — `compile_plan` signature + `titles=` channel unchanged.
- `RETRIEVAL_RECEIPT`: **UPDATED** — compiler receipt `titles`→`scout`; verify no frontend/consumer reads `compiler.titles` at integration.
- `CANDIDATE_ENGINE` / `ACCEPTANCE`: **NOT_AFFECTED** (pre-plan only).
- LIVE GATE: set `POLYMATH_PROFILE_SCOUT=1` in `.env`, bounce, run L1–L5 (scout conditions the compiler; miss ⇒ no regression). Multi-corpus rank restarts per corpus (single-corpus, the common case, is exact) — refine if needed.
