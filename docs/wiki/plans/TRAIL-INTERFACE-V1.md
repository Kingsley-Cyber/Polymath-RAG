---
title: "TRAIL-INTERFACE-V1 — a Research section in the Polymath web UI for watching and reading governed TrailSignal runs"
date: 2026-09-26
last_reviewed: 2026-09-26
status: "ACTIVE — plan of record (register 11.504); the owner agreed to every §8 recommendation on 2026-09-26"
owner: "@king"
scope: "Polymath only: two read-only orchestrator routes, one read-side fix (gap A-15), new frontend-v2 screens. Nothing inside TrailSignal (governance/trail stays byte-identical to its pin); no change to how runs reason or score."
---

# TRAIL-INTERFACE-V1

## 0. The owner's request (2026-09-26)
"i think the trail signal os needs a interface or design."

## 1. What exists
Read-only survey on 2026-09-26 of TrailSignal (worktree HR7 `494905a`, the copy embedded in Polymath) and Polymath `7e1918c2`.

- **TrailSignal has no screen at all.** It is MCP-first by design (ADR-015). The pieces:
  - the CLIs `niche-research`, `trail-signal-v2-daemon`, `trail-signal-v2-stdio`, `trail-signal-v2-worker`;
  - a legacy control API, and markdown templates.
- **Adding anything inside TrailSignal is heavy.** ADR-002 requires a new ADR for any new context or dependency edge. Every change also needs an owner-accepted ADR, a build-graph node, size ceilings and the governance check (`docs/AGENT_BUILD_CONTRACT.md`).
- **The records a person wants to see mostly live in Polymath.** Polymath runs TrailSignal embedded (`POLYMATH_TRAIL_MODE=embedded`). ADR-063 makes Polymath the owner of hypothesis state. Records by owner:

| Record | Owner and place |
|---|---|
| The run, its steps, its result | Polymath Postgres: `adapter_runs`, `adapter_steps`, `adapter_results` |
| Hypotheses and their transitions | `adapter_hypotheses`, `adapter_hypothesis_transitions` |
| Acquisitions and admitted evidence | `adapter_harness_actions`, `adapter_admitted_evidence` |
| TrailSignal's own operations and results (admit, judge, qualify, score, …) | the embedded store `~/PolymathRuntime/polymath-v4-trail-store.sqlite3` (`research_operations`, `research_results`) |
| Lived clusters (THIN / ANCHOR: 5 records, 2 threads, 3 voices), concept reality, the dossier renderer | Polymath's ecommerce adapter: `adapters/ecommerce/python/lived_world.py`, `product_reality.py`, `report.py` |

- **The routes today.**
  - `/adapter/list` and `/adapter/start`.
  - `/adapter/{id}/next|status|result` (GET) and `/adapter/{id}/submit|cancel` (POST). All are USER class in the web boundary, with the run-owner check in the route.
  - `status` gives the run state, the current step, steps issued/accepted, loops, harness actions, times, failure and gap — no stages, gates or clusters.
  - `result` (409 until the run ends) gives `output` (32 keys: `qualifications`, `trail_scores`, `score_refusals`, `evidence_admissions`, `lived_clusters`, `product_concepts`, `concept_reality`, `product_opportunity`, `unresolved_research_gaps`, `hypothesis_semantics`, …), `lineage`, `contradictions`, `unknowns`, `gap`. There is no single verdict field.
- **Missing.** No route lists runs (the adapter store has no list function), and no screen reads any of this.
- **A defect found on the way (gap A-15).**
  - The R7 run's `result.output.qualifications` is `[]`, while the embedded store holds that run's 2 `opportunity.qualify` results.
  - Cause: the step worker keeps empty lists (it skips only null), and `_gather` returns the newest occurrence of a key, so the score step's empty list hides the qualify results.
  - A gates screen built on today's result would show nothing.
- **The one rendered example.** The R7 dossier (outside the repo) has these sections, each with an authority badge (TRAIL DETERMINATION, AGENT INFERENCE, …): opportunity thesis, governed run, TrailSignal's record per hypothesis, populations, lived clusters, lived situations, transduction, reasoning bridge, product reality per concept, registry coordinates, field observations (admitted / rejected), what the field said, product directions, corpus evidence, supplier leads, unresolved, research audit.

## 2. Decision proposed: a "Research" section in the Polymath web UI
- **Build it in `frontend-v2`, reading Polymath's routes. Build nothing in TrailSignal.** Polymath already owns the run records, the sign-in (friends included) and the web boundary. TrailSignal keeps its MCP surface and its governance untouched.
- **Rules the interface keeps.**
  1. It **observes**. Agents still submit the reasoning; the score is TrailSignal's alone (LAW 1). The UI never computes a verdict of its own; it labels what each record is and who decided it.
  2. **Field text is untrusted web text.** It renders as plain text only (never HTML), long quotes fold, and links open with `rel="noopener noreferrer"`.
  3. **Friends see only runs they own** (`owner_principal_id`). The owner sees every run, plus the registry tab.
  4. **No live pushes.** A running run is polled every 5 s (the web boundary refuses proxied websockets anyway).

## 3. Screens
### 3.1 Research (the runs list)
- **Columns.** Title (from the run's input), adapter (Product research / Legacy discovery), status, current step, started, finished, who ran it (owner view), and the outcome in words.
  - Outcome examples: "TrailSignal refused all 6 scores", "2 scored", "Waiting for your agent".
- **Filters.** Status, adapter, mine / everyone (owner).

### 3.2 A run
| Section | Shows | Source |
|---|---|---|
| Header | title, status, adapter and versions (details), times, agent; **Cancel** for the run's owner while it runs | status + run row |
| Progress | the manifest's steps as a vertical timeline: done · current · waiting for your agent · waiting for acquisition · failed · skipped; loops as "round 2"; harness actions | status + `adapter_steps` |
| Outcome | TrailSignal's scores or refusals, each reason in plain words; the opportunity; unresolved gaps; contradictions | `trail_scores`, `score_refusals`, `product_opportunity`, `unresolved_research_gaps`, `contradictions` |
| Gates | hypothesis × stage × gate: minimum, observed, passed, and "what would pass" (the open gaps) | the qualify results (after A-15 is fixed) |
| Evidence | admitted vs rejected, by role, source class, platform and independence group; a table of observations (source, role, freshness, polarity, limitations); rejection reasons | `evidence_admissions`, `adapter_admitted_evidence`, harness actions |
| Lived world | clusters with their counts against the ANCHOR threshold; situations | `lived_clusters` |
| Concepts | each concept, its reality status (e.g. "an existing product contests it"), the existing products | `product_concepts`, `concept_reality` |
| Report | the full dossier and a download | `report.py`, rendered on the server |
| Registry (owner) | snapshot id and hash, priors, territories | run lineage |

Refusal reasons are written for people, for example:
- HARD_GATE_UNMET → "A required check wasn't met."
- NO_ADMITTED_EVIDENCE → "No evidence passed admission."

Each gate cell reads like "1 of 3 platforms".

### 3.3 Look
- The same tokens and pieces as FRONTEND-REFRESH-V1. Nothing Trail-specific in CSS.
- Authority always carries a word, with color second: **Trail decided** (accent) · **Agent's reasoning** (neutral outline) · **Field evidence** (teal outline) · **Polymath evidence** (gray).
- Gate cells: a pass/fail dot plus the count. Clicking a cell lists its evidence and its open gap.

## 4. Backend changes (small, read-only)
1. **A-15 fix, on the read side.** Past runs (R7) must show their gates too. For a key a later operation did not produce, keep the newest NON-EMPTY value, or gather per operation kind.
   - A test: a qualify step followed by a score step keeps the qualifications.
   - A worker-side guard, so new runs never store the shadowing empty list.
2. **`GET /adapter/runs`** (`status`, `adapter_id`, `limit`, `before` cursor): the owner gets every run, a principal gets its own. It needs a new `list_runs` in the adapter store (index on `(owner_principal_id, created_at)` if the plan shows a sequential scan).
3. **`GET /adapter/{id}/view`**: one typed read model (header, progress, outcome, gates, evidence summary, clusters, concepts, opportunity, report availability), assembled from the tables and the result, with the owner check.
   - One contract is easier to test than exposing raw step outputs.
   - It is declared wherever the repo's contract map requires (`architecture/contract-dependencies.yaml`).
4. **`GET /adapter/{id}/report`**: the dossier HTML from `report.py`, sanitized and sent with a strict CSP (no scripts). The owner check applies.
5. **Wiring.** Each new route gets a line in the web boundary's policy table (USER class, ownership inside the route) and a case in `test_web_boundary.py`, which fails on any unclassified route. The live contract check covers the new `api.ts` calls.

The orchestrator changes need a bounce after merge; the frontend only needs `npm run build`.

## 5. Slices
| Slice | What | Proof |
|---|---|---|
| **T0** — DONE 11.505 | A-15 read-side fix + worker guard (and the whole unfilled-field class) | A unit test (qualify then score keeps qualifications); R7's result read back shows 2 qualifications (Mission: check, $0). |
| **T1** — DONE 11.512 | `GET /adapter/runs`, `GET /adapter/{id}/view` | Contract tests: owner vs friend visibility, a friend gets 404 for another's run, boundary classification, view model against the R7 run (read-only). |
| **T2** — DONE 11.515 | Runs list + run header + progress (polling, cancel) | vitest (list states, polling stops at a terminal status, Cancel only for the owner of the run); screenshots at 3 widths. |
| **T3** — DONE 11.515 | Outcome, gates, evidence | vitest (refusal wording per reason code; gate cell text; field text rendered as text, never HTML). |
| **T4** — DONE 11.515 (opportunity: unresolved questions only) | Lived world, concepts, opportunity | vitest against a fixture built from R7's shapes (no field quotes in the repo). |
| **T5** | Report route + tab; registry tab (owner) | A CSP header test; a sanitizer test (a script in a receipt is rendered as text); an owner-only test. |
| **T6** *(optional)* | Start a run from the web, then "hand it to your agent": copy the run id and a ready prompt, since agent steps need a connected agent | Only if the owner wants it (§8). |

Order: T0 and T1 can run alongside the frontend refresh; T2–T5 come after its U1–U3, so the new screens are built once, on the new pieces.

## 6. Tests and fixtures
- Fixtures are built from the R7 run's SHAPES with synthetic text. Field evidence (quotes, comments) never enters the repository.
- No live run is needed to build or test any slice. A new governed run stays the owner's word.

## 7. Found on the way (not in scope)
- The TrailSignal graft index (`~/trail-signal-os-worktrees/_graft_trail`) is at `c46d646`, 24 commits behind HR7. Refresh it when TrailSignal work resumes.
- A standalone `trail-signal-v2-daemon` (127.0.0.1:8767) still runs from the older A41 worktree. Its latest log line is a 401 invalid_token: something local calls it with a bad token. Polymath does not use it (embedded mode). Whether it should keep running is the owner's call.

## 8. Owner decisions
**DECIDED 2026-09-26** (the owner: "i agree please fix it all"): a Research section in the Polymath web UI, named "Research"; watch and read only in v1; friends see only their own runs; the report rendered on the server; A-15 fixed first (T0).

1. **Where:** a Research section in the Polymath web UI (recommended), or a separate TrailSignal app (needs ADRs and a build-graph node in TrailSignal).
2. **Name in the nav:** "Research" (recommended), "Signals" or "Trail".
3. **Scope of v1:** watch and read only (recommended); starting runs from the web (T6) later.
4. **Friends:** see only their own runs (recommended).
5. **Report:** render the existing dossier on the server (recommended, reuses `report.py`), or rebuild it in React.
6. **Fix A-15 first** (recommended; without it the gates screen is empty).
