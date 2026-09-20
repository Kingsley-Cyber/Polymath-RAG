---
title: "GOVERNED-CONVERGENCE-V1 — connect the real product-research controller to the governed Polymath → Trail adapter path"
date: 2026-09-20
last_reviewed: 2026-09-20
status: "REFRAMED 2026-09-20 BY THE OWNER AS A MIGRATION / RECOVERY PROJECT — IMPLEMENTATION HALTED until the owner reviews the harvest map. Done and recorded: TG0–TG4 + RB5; TG5 R2a (first real run) = FAIL at `L_judge`; external review M1 (12 findings, register 11.361). Finding that reframed the work: the original `TRAIL_AGENT_AUTORESEARCH` controller already has working ecommerce intelligence (one complete real run: 5 concepts × 2 variations, 135 supplier candidates, 8 leads); the governed path duplicated its workflow, hypothesis lifecycle, research planning and evidence admission and lost its strongest capabilities; TG4 connected only the output (receipt) side. NEXT = owner review of `docs/wiki/reports/2026-09-20/ECOMMERCE-MIGRATION-HARVEST-MAP.md`. Nothing pushed. Trail untouched. Item 2D parked."
owner: "@king"
scope: "Converge two existing systems instead of building a third: the governed adapter path (lawful, never driven by a real agent or the real world) and the Hermes opportunity-research controller (works in the real world, ungoverned, nests Polymath synthesis). Trail remains exactly what ADR-063 says. First milestone: a Claude Code session drives ONE real governed product-discovery run and the existing renderer produces the HTML dossier."
---

> **Where things live (read this first in a fresh session).**
> Ground truth this plan rests on: `docs/wiki/reports/2026-09-20/TRAIL-GROUND-TRUTH-DOSSIER.md`.
> Repos: **polymath-v4** (this repo, branch `production`) · **skill** `/Users/king/Documents/polymath-rebuild/TRAIL_AGENT_AUTORESEARCH` (authoritative; its deployed copy is the UNTRACKED dir `/Users/king/.hermes/standalone/opportunity-research`) · **Hermes** `/Users/king/.hermes` (deployment only; never hand-edit `config.yaml` / `models.json`) · **Trail** authoritative tree = `/Users/king/trail-signal-os-worktrees/A41` == `origin/main` (`de64d84`); `/Users/king/trail-signal-os` local `main` is 114 commits STALE and dirty — never plan or run against it.
> Runtime: Polymath fleet = `scripts/boot_polymath.sh` (orchestrator :7200, MCP Server A :8930 = supervisor slot `mcp`, `adapter_step` worker slot). Trail stack = `/Users/king/Documents/polymath-rebuild/handoff-drafts/trail_stack_up.sh <A41 path>` (daemon :8767, Trail Postgres :15433, Temporal :7233; it `pkill`s any running daemon; LOCAL secrets in `~/.config/trail-signal/local.env`). The fleet does NOT survive a reboot (the `com.polymath.v5` autoboot fails).

# GOVERNED-CONVERGENCE-V1 — Plan of Record

> **Execution ledger.** TG0 ✅ R0 PASS (11.352) · TG1 ✅ (11.353) · TG2a + TG2b ✅ (11.354) · deploy + R1 PASS + boundary proof (11.355) — work-log `docs/wiki/work-log/2026-09-20-governed-convergence-tg0-tg2.md`, evidence `eval/governed_convergence/`. TG3 ✅ skill v2.2.0 `438d92d`, 580 checks + doctor, live acceptance PASS (11.356; work-log `2026-09-20-governed-convergence-tg3`). RB5 ✅ EvidencePacket text = bounded verbatim excerpt ≤ 900 chars + `text_truncated` / `text_chars`, presentation only, 96-row fixed sample with 0 non-text differences (11.357; work-log `2026-09-20-evidence-packet-text-excerpt`). TG4 ✅ skill v2.3.0 `076922d` (`adapter_receipt.py`, `governed_run.py`, governed report model), 609 checks + doctor, Polymath's own `validate_receipt` accepts the skill-built receipt, mirrored to Hermes with parity true; Server A deprecation leads + `CONNECTORS.md` corrected — committed, NOT running until the next bounce (11.358; work-log `2026-09-20-governed-convergence-tg4`). TG5 **R2a RUN 2026-09-20 (11.360): FAIL by the owner's rubric** — cinema mechanical smoke, run `adr_d96032aef165a999774bd4bbabb37b1d`: `adapter_start` / `adapter_submit` over Server B live, 7 agent answers accepted, the TG4 harness segment 3 / 3 LIVE_PATH_PROVEN, Trail admitted 8 / rejected 7 (`STALE_BEYOND_POLICY`) and judged twice, then terminal gap `PHI_VERDICT_INVALID` at `L_judge`: an admission that admits nothing is not an allowed cause (`store.admission_ids`, Polymath adapter defect D1 — NOT fixed). Qualification and score never ran. TG6 record = `eval/governed_convergence/GC1-FIRST-REAL-RUN-2026-09-20.json` (work-log `2026-09-20-governed-convergence-tg5-r2a`). A re-run, and the D1 fix, each need the owner's word. TG7–TG8 NOT STARTED. External review M1: 12 failure-mode findings reproduced on an isolated branch (11.361). **2026-09-20 REFRAME (11.362): migration / recovery — harvest the original controller's ecommerce intelligence under the adapter spine; harvest map = `docs/wiki/reports/2026-09-20/ECOMMERCE-MIGRATION-HARVEST-MAP.md`; implementation HALTED pending owner review.** Run the Trail stack script with **zsh** (under `bash` it silently skips compose / health / migrations).

## Product direction and migration reframe (owner, 2026-09-20 — AUTHORITATIVE; supersedes the framing below where they differ)
**Goal.** Niche-informed product ideation for ecommerce. The system should help develop the judgment an experienced niche seller
has: understand the customer's activity, identify recurring friction and workarounds, explain why a product would help,
investigate existing alternatives, and assess actual products and suppliers such as Alibaba or CJdropshipping.
**Roles.** Polymath supplies corpus knowledge. The agent develops hypotheses. The harness investigates customers, products and
supply. Trail determines what the evidence supports, including qualification, scores, refusals and unresolved questions.
**Scope.** The ecommerce path must work end to end first. Future adapters (for example corpus-informed Substack topics and
articles) may reuse hypothesis generation, evidence handling and workflow state — they are NOT built now, and no speculative
abstraction is added for them.
**Earlier instructions, re-read.** "Ignore any reference of ecom" applied to the cinema MECHANICAL smoke run (R2a), not to the
product's purpose. The `ecom-meta-v1` corpus stays dropped from this plan (register 11.359) until the owner names a corpus.
**Unconfirmed.** A detailed dossier specification (sections A–M, authority labels, registry trace) reached the session inside a
tool result and was never confirmed by the owner. It is NOT adopted. Only the direction above is authoritative.
**Reframe.** This is a migration / recovery project: **harvest behaviour, not architecture.** Keep the controller's proven
ecommerce intelligence, Polymath's evidence-only boundary, Trail's deterministic authority and the existing renderer; delete
duplicate glue only after the unified path proves itself. One owner per authority — adapter: run state, ledger, the only caller
of Trail · controller library: niche interpretation, population discovery, research and channel planning, hypothesis structure
checks, concepts + variations, product-reality and sourcing procedures, parsers, the mechanism × supplier join · host harness:
live-world execution · Trail: admission, freshness, independence, judgement, qualification, score / refusal, registry data ·
the controller's renderer: the dossier. The controller's 28-node state machine, its score, its admission rules, its hypothesis
authority and its Trail registry mirror are NOT migrated.
**Names (owner, 2026-09-20).** Trail Signal OS = the deterministic judge, NOT the ecommerce adapter. `TRAIL_AGENT_AUTORESEARCH` = the
ecommerce discovery engine. The adapter id `trail.product_discovery` is conceptually `ecommerce.product_discovery`: the governed
composition wrapper around AutoResearch, with Trail as CHECKPOINTS (judge · admit · qualify · score) at meaningful boundaries — not a
second research implementation, and not a node-by-node port. Delete nothing until AutoResearch is shown connected to the EvidencePacket
and to Trail's checkpoints with its behaviour intact (harvest map §10 lists the boundaries and the verified constraints).
**Harvest map (the first deliverable, docs only):** `docs/wiki/reports/2026-09-20/ECOMMERCE-MIGRATION-HARVEST-MAP.md` — all 28
governed steps mapped to existing controller capabilities, all 28 controller nodes mapped to a future owner, dependency facts
per harvest target, acquisition tools, parity fixtures and invariants, duplicates with deletion preconditions, a four-layer
order (A extraction · B thin library boundary · C governed connection · D retirement after parity).
**HALT.** No implementation — including the defined M1-04 containment, D1 and Item 2D — until the owner has reviewed the map.

## Context

The discovery pass (`docs/wiki/reports/2026-09-20/TRAIL-GROUND-TRUTH-DOSSIER.md`) established that "Trail product research" already exists twice, and the two halves have never touched:

| | PATH A — governed | PATH B — real-world |
|---|---|---|
| What | agent → Polymath adapter `trail.product_discovery` → Trail v2's seven deterministic ops | Hermes → opportunity-research controller → Reddit / Exa / Alibaba → Polymath `/chat` → HTML report |
| Good | governance, typed admission, LAW-1 score, lineage, restart-safe | real products (3–6 concepts, ≤8 leads), real web evidence, diversity, contradictions, purchase language, **a real HTML dossier** |
| Bad | **never driven by a real agent or real harness** (fixtures + scripted Python only); the agent gets evidence IDS, not text; JSON-only output; no products | never calls Trail; own score; different evidence contract; **nested Polymath synthesis** (`CORPUS_SYNTHESIS`) |

**Goal:** move the useful real-world behaviour of PATH B behind PATH A, without moving reasoning or retrieval into Trail. Reuse the controller's acquisition stack as the harness executor and its renderer as the dossier. Build no new research system and no new HTML system.

**Owner decisions (locked):** keep ADR-063, zero Trail changes before the first real run · Trail correctness fixes come AFTER the first real E2E, evidenced by it, unless the run physically cannot complete · the skill's git repo is authoritative, the Hermes copy is deployment · Claude Code and Codex reach the adapter through seven thin proxies on MCP Server B (no credential) · Claude Code is the first real harness, Hermes repeats second · no Reddit/web/product evidence is ingested into Polymath in v1 · corpus isolation (Item 2) is a prerequisite only for any second corpus, not for this work.

**First milestone (the acceptance test):** Claude Code → `adapter_start` → readable Polymath evidence → real agent hypotheses → real harness research → `HarnessResearchReceiptV1` → Trail admit → judge → product reality → supplier research → qualify ×2 → score → governed result → **self-contained HTML dossier from the existing renderer.** Not "all APIs return 200".

## Target shape

```text
        Claude Code / Codex (Server B stdio)        Hermes (Server A http)
                         └────────── adapter_* tools ──────────┘
                                          │
                           POLYMATH cognitive adapter  (composition root)
             ┌────────────────────────────┼─────────────────────────────┐
     knowledge steps                AGENT_REASON                  HARNESS_ACTION
  /chat/evidence → EvidencePacket   the agent reasons ONCE        skill acquisition stack
  text + role + CA4 + provenance    over READABLE evidence        (Reddit · Exa/forums · retailers · suppliers)
             │                                                          │ adapter_receipt.py
             │                                                 HarnessResearchReceiptV1
             └──────────────► TRAIL v2 (unchanged): admit · judge · qualify · score
                                          │
                                   AdapterResultV1 + local run journal
                                          │
                              skill report layer (existing renderer) → HTML DOSSIER
```

## Slices (ordered; each is independently reversible)

### TG0 — Operational baseline (no code)
Everything is down since the 06:20 reboot except the Docker stores. Boot: `scripts/boot_polymath.sh` (one supervisor) → verify one bundle, `/ready`, slots `mcp` (:8930) and `adapter_step` registered, live flags from the LIVE `.env`. Trail: `handoff-drafts/trail_stack_up.sh /Users/king/trail-signal-os-worktrees/A41` (authoritative tree, never the stale local `main`) → daemon on :8767. Preflight = the existing fixture acceptance run must pass unchanged: `scripts/adapter_mcp_acceptance.py --adapter trail.product_discovery --corpus cinema --harness receipts --harness-receipts tests/fixtures/harness_receipts` (R0, $0 external). Out of scope here, logged to backlog: the failing `com.polymath.v5` autoboot and the firing ledger living in `/private/tmp`.

### TG1 — Polymath: adapter tools on Server B (repo `polymath-v4`, worktree)
- `mcp_server/polymath_mcp.py`: seven thin tools `adapter_list / adapter_start / adapter_next / adapter_submit / adapter_status / adapter_result / adapter_cancel`, each a plain proxy to the existing `/adapter/*` routes (`orchestrator/orchestrator/api/adapter.py:36-120`) — same parameter names and docstring semantics as Server A (`orchestrator/orchestrator/mcp_server.py:411-468`). Nothing clever.
- Parity test (new, `tests/contracts/test_mcp_adapter_parity.py`): both servers register the same seven names with the same parameter sets; both canonical trios still present. Extend `orchestrator/orchestrator/api/capabilities.py` `MCP_TOOLS` note for Server B.
- Codex: one `[mcp_servers.polymath]` stdio entry in `~/.codex/config.toml` — **owner adds it, or I add it on your word** (it is your config file). Claude Code picks the tools up through its existing project registration.

### TG2 — Polymath: the agent can READ the evidence, then the evidence boundary (same worktree, same bounce as TG1)
Two steps, deliberately separate so the hard bug fix does not depend on the slower surface.
- **TG2a — readable evidence (fixes "ids, not text").** `shared/polymath_shared/adapter/service.py:132-139` `next_step` returns a sibling key beside the step: `{"kind":"step","step":…,"status":…,"evidence":{"rows":[…],"receipts":[…]}}`, hydrated from the rows already stored in `state.outputs` for exactly the ids in `context.evidence_refs` (cap 60 rows × 600 chars, graded rows first). The `next_step` response is not schema-validated, so this needs no wire-schema change. Works on the legacy `/retrieve` surface immediately.
- **TG2b — evidence-boundary surface, opt-in per step.** NEW pure `shared/polymath_shared/adapter/evidence_boundary.py` (`ALLOWED_ORCH_PATHS = {/chat/evidence, /retrieve, /retrieve/plan}`, `plan_calls`, `request_body` → exactly `{message, corpus_id, mode, corpus_explorer}`, `check_response` fail-closed, `rows_from_packet`, `merge_rows`, `refs_from_rows`, `hydrate`). `workers/workers/adapter_step_worker.py`: `_orch_post` gains the path allow-list + typed `OrchUnavailable`/`OrchRejected`; new `exec_evidence`; `exec_retrieve`/`exec_graph_expand` dispatch on `config.surface`. Manifest `config/adapters/trail.product_discovery.json` → `adapter_version 2.2.0`, `retrieval_policy_version 2.0.0` (workflow stays 2.0.0, still 28 steps): `B_retrieve`/`F_retrieve` = `surface: evidence_boundary, mode: WILDCARD, corpus_explorer: true`; `B_graph`/`F_graph` = `mode: GRAPH` unioned with the legacy graph-fact rows (the packet carries no graph facts). The explore step receives the ORIGINAL need (`input.seed`, or one call per live hypothesis), never `B_plan`'s reformulations; `B_plan`/`F_plan` stay as the cheap find lane (removing a step id breaks in-flight runs).
  - Rules baked in: every chat mode needs ONE corpus → bounded per-corpus fan-out (`max_calls` 3, skipped corpora recorded in `output.truncated`); `schema_version != "evidence-packet-v1"` or `synthesis_performed != false` → terminal gap `EVIDENCE_CONTRACT_MISMATCH`, never a fallback; unreachable → `fallback: retrieve` with `degraded: true`, else per-step `on_unavailable: gap | continue` (a gap is always terminal, so `continue` reports through `unknowns[]`, never through `knowledge_gaps`, which is forwarded to Trail); empty evidence = success with `retrieval_completed: true`.
  - Additive wire change: `contracts/adapter/v1/adapter_step.schema.json:65-100` — four OPTIONAL ref properties `utility_role`, `ca4_grade`, `c4_valid`, `origin` (Trail does not mirror this schema). NEW `contracts/evidence/v1/evidence_packet.schema.json` validated consumer-side. `architecture/contract-dependencies.yaml` gains `EVIDENCE_PACKET`, `EVIDENCE_BOUNDARY_API`, `ADAPTER_RUNTIME`, `MCP_SURFACE` so `scripts/contract_impact.py` stops being blind here.
  - Result visibility for the report + TG6: the manifest's `X_compile.config.include` gains the three evidence admissions (admitted AND rejected with reason codes) — verify `_compile_result` (`service.py:552-603`) can gather all occurrences of a key; if it only gathers the newest, add the smallest generic "collect all" include form.
  - Kill switch: `POLYMATH_ADAPTER_KNOWLEDGE_SURFACE=retrieve` forces the legacy surface (records `degraded_reasons: ["surface_forced_by_env"]`); default surface in code stays legacy; the other two manifests are untouched.
- Proof: unit (shared/contracts/config — worktree-provable): packet contract test, `evidence_boundary` determinism + fail-closed + hydrate caps, AST scan proving the worker and the new module contain no `/chat`, `/chat/stream`, `/ask` literal, manifest identity + 28 steps. Live-only (workers/orchestrator — after merge + ONE bounce, drain in-flight runs first): R1 = the fixture acceptance run again on the new surface; NEW read-only `scripts/adapter_evidence_boundary_proof.py --run-id` asserting every boundary call's query receipt has `verdict = evidence_only` (correlated by a `User-Agent: polymath-adapter-step/<run>/<step>/<seq>` header), every packet validates, ≥1 issued ref carries `utility_role`, and the `adapter_next` payload carries evidence TEXT.
- Known cost: ~8 boundary calls per run ≈ +3–4 min; the executor runs inside the run-row transaction, so `adapter_cancel`/`adapter_submit` can block up to ~105 s.

### TG3 — Skill (repo `TRAIL_AGENT_AUTORESEARCH`): evidence-only corpus lane
`python/corpus_polymath.py`: delete `ask_corpus` (`:125-131`), `chat_question`, `answer_record` (`:156-164`); add `explore_corpus()` → `POST /chat/evidence {message, corpus_id, mode:"WILDCARD", corpus_explorer:true}` + `rows_from_packet()` (docs/18 rows + role, grade, origin, provenance, query ids) + fail-closed packet validation (`capability_failure{capability:"corpus_evidence_packet"}`); `--via evidence|plan`, default `evidence`, lane keyed on `/capabilities` `contracts["evidence-packet"]` (already advertised). Node `corpus` = ONE call per corpus with the ORIGINAL signal (not the 3–5 reformulations); node `corpus_mechanisms` = one call per compiled mechanism question, capped (these are distinct needs derived from field clusters, not rewordings). Payload key `corpus_answers` → `corpus_packets` (`authority: "CORPUS_EVIDENCE_PACKET"`, no `answer` field); "abstained" is replaced by `n_evidence == 0` + the CA4 grade distribution. Readers updated to tolerate legacy state: `graph/control_graph.yaml:30,41,112`, `models.py:147`, `memory.py:452`, `provenance.py:416-419`, `utilization.py:44-46`, `report.py:76,415-419` (section becomes "Corpus evidence packets"; legacy answers render as "legacy synthesis, not evidence"), `lived_world.py:645`. Docs `docs/22` §1/§3, `docs/18` note, `SKILL.md:195,205,301-315`. Tests: `tests/run_all.py` §17 stub serves `/chat/evidence`; asserts no POST to `/chat`, no `CORPUS_SYNTHESIS` string, rows carry `utility_role` + `ca4_grade`, wrong schema version → `capability_failure`. Version 2.2.0 + `WORKLOG.md`. Rollback: `--via plan` stays; git revert + re-mirror.

### TG4 — Skill: the real harness executor, the report bridge, then mirror to Hermes
- NEW `python/adapter_receipt.py` (+ CLI): `build_receipt(action, observations|field_records|supplier_candidates, harness_id, started_at, completed_at, tool_trace)` → a valid `HarnessResearchReceiptV1`. NEW `schemas/harness_receipt.schema.json` = byte copy of `polymath-v4/contracts/adapter/v1/harness_receipt.schema.json` with its sha recorded (test fails on drift). What is genuinely missing today and gets added: a per-source **`retrieved_at`** and **`published_at_if_known`** captured at harvest time (the skill records only a freshness class); tool-trace rows bound to the action's `search_intent_id`; observations tagged with the adapter's `hyp_…` ids; a static role map (skill `FRICTION_EVIDENCE…` → Trail `friction, workaround, behavior, demand, competition, seasonality, operations, risk, contradiction, price, supply`); a static source-class map (→ `community_discussion, video_platform, social_trend, marketplace_listing, retailer, supplier_listing, …`); bounds (excerpt ≤ 600, claim ≤ 2000, action budget clamps); numeric price/MOQ carried as `metric_if_present{name,value,unit}`. **No score field anywhere**; `qualify.py`/`evaluator.py`/`evidence_score` are standalone-mode only and never surface in adapter mode.
- NEW `python/governed_run.py`: a local RUN JOURNAL (`state/<run_id>.governed.json`) — every issued step with its readable evidence, every submission, every receipt, the final `AdapterResultV1`. NEW `report.build_model_from_governed(journal)` feeding the EXISTING `report.render`: verdict = Trail's record (scores shown verbatim with coverage gaps, refusals with their reason — never re-ranked, never blended with `evidence_score`); hypotheses + Trail verdicts → Reasoning Bridge / Held & Rejected; receipt observations → quotes with source URLs, split **admitted vs rejected-with-reason-code**; product-reality and supplier observations → Product Directions / Qualified Leads (price, MOQ, URL); Polymath packets → "Corpus evidence packets" with role + CA4; limitations + open gaps → Unresolved; lineage → Research Audit.
- `SKILL.md`: new top section "Governed entrypoint — Polymath adapter `trail.product_discovery`": drive `adapter_start → adapter_next → … → adapter_result`; at AGENT_REASON reason over `evidence.rows` and cite only ids from `context.evidence_refs`; at HARNESS_ACTION run the skill's acquisition commands inside the action's intents and budget, then `adapter_receipt.py`, then `adapter_submit kind=receipt`; never compute a score or a qualification; relay typed gaps verbatim; the standalone controller remains as `--mode standalone`.
- Tests: receipt validates against the schema copy; every observation's source is listed; no key matches `score|rank|weight`; `hypothesis_ids ⊆ action.hypothesis_ids`; deterministic; structurally equal to the Polymath fixtures; governed ReportModel renders from a fixture journal. Gate: `python3 tests/run_all.py` (≥ 555 + new checks) and `python/controller.py doctor`. Commit locally in the skill repo, then mirror to `~/.hermes/standalone/opportunity-research` with `tests/mirror_check.py` repointed (reference = the git repo, deployed = the Hermes dir).
- Hermes skills that teach the forbidden pattern (tracked files in HERMES-KING, edited as text, never `config.yaml`/`models.json`): `productivity/ecommerce-niche-discovery` multi-query pattern → one `polymath_explore`; `mlops/polymath` v3.3 tool list → the v4 canonical trio. Polymath-side text: Server A's `ask`/`retrieve`/`compile_plan`/`retrieve_evidence` get the same "DEPRECATED — use …" lead sentence Server B already has, and `mcp_server/CONNECTORS.md` is corrected (Hermes uses Server A; the example calls `polymath_explore`). Doing this changes Server A's tool schema, so Hermes needs one MCP reload.

### TG5 — The first real governed run (Claude Code as agent + harness)
One run, R2. Seed chosen with you beforehand; the corpus is the current corpus, `cinema`. The session answers each AGENT_REASON step by reasoning over the readable evidence, and executes each HARNESS_ACTION with the skill's commands: `opencli reddit …` (**read-only, through your logged-in Chrome session — the same thing your controller already does**), Exa via `mcporter`, direct reads of forum / retailer / manufacturer pages. Per-action query cap for this first run: ≤ 12 (the action budgets allow 24/24/16). Every step lands in the run journal; the HTML dossier is rendered at the end and sent to you. Verified by `adapter_evidence_boundary_proof.py`, by the journal, and by reading `adapter_admitted_evidence` / `adapter_harness_actions` for the run.

**Owner directions 2026-09-20.** (1) With the TG4 word: `cinema` may be used ONLY for an integration / mechanical real-agent smoke run; a cinema-backed run is never read as a product-discovery quality result. The first real governed run happens against Trail AS-IS; what it shows scopes the later owner-approved Trail governance slice (TG7). (2) Later the same day: **"DELETE ECOM META ITS NOT PART OF MY CURRENT CORPUS. DROP IT FROM PLAN."** — `ecom-meta-v1` is not a TG5 input, is not proposed as a corpus, and no re-ingest of it is planned (register 11.359). No product corpus is named by this plan; a product-discovery-quality R2 has no corpus until the owner names one. The standing finish-line rule is unchanged and generic: no SECOND corpus of any kind before Item 2 (corpus isolation).

**Known real-world frictions — measure them, do not tune around them:**
- Trail gives ALL of Reddit one independence group and a 14-day freshness window; the controller's best run was 146 Reddit observations from year-wide searches. Expect `SINGLE_INDEPENDENCE_GROUP` weakening and `STALE_BEYOND_POLICY` rejections. The run therefore deliberately includes forums (per-domain groups, 365-day window) and retailers.
- A source URL must route to an enabled registry row or it is `SOURCE_UNREGISTERED`; the claimed role must be one that source supports (Reddit cannot support `demand`); `supply` only in the supply stage; the supply gate's `risk_review` can only be satisfied from a manufacturer site.
- Honesty rules: never omit a known publish date to read as fresh; never re-submit a rejected observation with a different role; rejections are findings and appear in the dossier.

### TG6 — Record what the run actually cost (evidence, no code)
One artifact (`eval/governed_convergence/GC1-FIRST-REAL-RUN-<date>.json` in polymath-v4): admission table by reason code; hypotheses weakened by `knowledge_support_count = 0`; prices/MOQs lost because `metric_if_present` is discarded; gates never evaluated at qualification; the permanently empty `content` axis; registry frictions (Reddit grouping/freshness, missing source rows); adapter defects met on the way (no step lease, terminal-only gaps, empty `qualifications[]` / `query_receipt_ids`). This is the empirical basis for TG7 — nothing in Trail is touched to make the run look better.

### TG7 — Trail correctness slice (ONLY on your word, ADR accepted by YOU)
Scoped by TG6. Executed from a fresh worktree off `origin/main`, through Trail's own gate (agentctl task, build-run completion bundle, contract + schema regeneration, governor green locally — Trail CI is red for environment reasons and is not the signal). `knowledge_support_count` is a registered wire-contract change with a matching Polymath payload change; registry-row edits change the snapshot hash and force callers to re-run `registry.project`. Moved ahead of TG5 only if the first run physically cannot complete.

### TG8 — Hermes repeats the run (the day-to-day path)
Hermes reloads MCP, drives the same seed through Server A using the mirrored skill, producing the same journal + dossier. Only after it passes: the opt-in routing text in `~/.hermes/orchestrator/graphs.yaml:76-88` ("product/market research → the skill's governed entrypoint"), standalone mode kept.

### After this plan (named, not scheduled)
Product-portfolio hardening on the governed path (several `product_opportunities`, the evidence target expressed as **≥4 refs, target 5, ≥2 independence groups, ≤2 units per thread, a contradiction when one exists** — never a raw chunk count) · source expansion (YouTube comments, Amazon reviews, X; TikTok/Instagram comments only if actually reachable) · the adapter's missing step lease · final real-world acceptance. Backlog already recorded in polymath-v4: B19 compiler provider reliability, B20 toggle-vs-routing; Item 2 (coverage + corpus isolation) stays the prerequisite for any second corpus.

## Governance per repo
- **polymath-v4** — worktree; AGENTS §4 (work-log, register rows from 11.351, scaffold `TREE`, `contract_impact` dispositions); `shared/`+`contracts/`+`config/` unit-provable in the worktree, `workers/`/`orchestrator/`/`mcp_server/` live-only after merge + ONE bounce; guards 0; narrow commits; **local tag only, no push of any ref without your word.**
- **TRAIL_AGENT_AUTORESEARCH** — its own `WORKLOG.md`, version bump, `run_all.py` + `doctor` green, local commit, then mirror; no push.
- **~/.hermes (HERMES-KING)** — deployment target; text edits to skills only; never hand-edit `config.yaml` / `models.json`; no commit there unless you ask (it already has 269 dirty files).
- **trail-signal-os** — untouched until TG7.

## Live-run budget (staged)
R0 fixture baseline → R1 fixture run on the evidence surface → **R2 the one real Claude Code run** → R3 the Hermes repeat. Any further real run, or any widening of the per-action query cap, needs your word first.

## Verification (end to end)
1. Unit gates green in both repos (polymath determinism/contract suites; skill `run_all.py` + `doctor`).
2. R1: fixture run completes on the evidence surface; proof script passes; `adapter_next` shows evidence text with roles and grades.
3. R2: `completed` (or an honest typed gap) with `lineage.harness_ids = ["claude-code"]`, real URLs, ≥1 admitted observation per stage, rejection reasons recorded, Trail score or typed refusal present, **zero synthesis receipts** in the run window, and an HTML dossier whose every quote traces to a receipt observation.
4. A/B parity test green; Codex/Claude Code list the seven adapter tools.
5. R3: Hermes reproduces R2's shape.

## Do not
Move reasoning, retrieval, scraping or a Polymath client into Trail · touch Trail before TG7 · ingest field evidence into Polymath · build a second HTML/report system · let the skill's `evidence_score` or any LLM rank, blend with or replace a Trail score · pre-decompose queries into `polymath_explore` · tune Trail's registry, gates or freshness to make a run pass · hand-edit Hermes `config.yaml` · enter or print any credential · push any ref.
