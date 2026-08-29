---
change_id: RECONCILE-LIVELOCK-FIX
owner: governance
date: 2026-08-27
status: implemented
architecture_impact: none (repair/measurement log)
---

# 2026-08-27 — Reconcile livelock diagnosed and fixed (cysa-study-v1)

Symptom: 12 runs of cysa-study-v1 stuck `reconciling` for 5.5 h;
fleet froze overnight ~3 h; user report "doesn't ingest files and
stalls". Full evidence, SQL, and the causal chain:
`STALL_DIAGNOSIS_2026-08-27.md` (repo root).

Root causes (all measured live, none hypothetical):

1. RECEIPT-GAP-REOPENS-TICKET-V1 reopened EVERY flagged run's
   projection ticket per tick while the desired state is corpus-scoped
   → 12 tickets × identical corpus-wide projection: 286k neo4j receipt
   writes over 14.6k distinct entities in one 15-min window; pending
   tickets starved behind the corpus receipt barrier; census.promote
   never fired (4 runs sat 12/12-done and unpromoted).
2. Lease keeper renewed + heartbeated indefinitely while a stage ran →
   a wedged stage was indistinguishable from a busy worker (no reaper,
   no autopilot help; AUTOPILOT-WORKLOAD-HYGIENE-V1's ready/leased-only
   demand made a frozen lane look served).
3. com.polymath.v5 launchd boot dead: TCC denies launchd exec under
   ~/Documents (exit 126) → no autonomous recovery.
4. Outbox re-arm rewrote already-armed rows every tick →
   outbox_events 206 MB over 204 live rows, sequence past 155M.
5. heartbeat() COALESCE bugs: processed_count pinned at 1;
   current_ticket unclearable.

Fixes (see diagnosis file "Fixes applied" for per-file detail):
scheduler reopen = one re-drive per (corpus, stage); outbox re-arm
no-op when already armed; project_neo4j receipt-current skip
(mirror of qdrant `_already_current`, batched); STAGE-DEADLINE-
WATCHDOG-V1 in worker_runtime (typed fail + process exit past
POLYMATH_STAGE_DEADLINE_S, default 4 h); autopilot `_open_work`
counts pending again (debris exclusion stays in the JOINs);
heartbeat delta counter + explicit-unset ticket sentinel; launchd
entry moved to ~/PolymathRuntime/bin/polymath-v5-boot.sh with a
single-instance guard.

Proof: compile OK; determinism+contracts failure set byte-identical
to pre-change tree (83 pre-existing failures, 969 passed, zero new);
reopen + DAG pin tests green; autopilot_demand_matrix PASS 5/5.
Live: fleet restarted 10:47 UTC on fixed code → all 12 runs promoted
`query_ready` by 10:49 UTC, zero open tickets, zero redundant
receipt writes (idempotent skip drained the tail in one pass).
VACUUM FULL outbox_events: 206 MB → 232 kB.

## Same-day follow-up — WAKE-ON-QUERY + corpus rename

User report: first query after idle returned `embedder_unavailable`.
Cause: the autopilot parks the embedder when ingest demand ends, and
the orchestrator middleware recorded the `last_query` wake signal
AFTER the handler ran — the first query's own failure was its wake
trigger. Fixes:

- `orchestrator/main.py`: activity signal written BEFORE the handler.
- `orchestrator/api/fast.py`: `_await_embedder` — the embed path
  blocks up to 60 s (`EMBED_WAKE_BUDGET_S`) polling `/ready` while the
  autopilot wakes a parked embedder (reconcile ≤15 s + ~20 s cold
  start); a genuinely dead sidecar still fails typed. Shared by
  FAST/HYBRID/GRAPH via the existing `_embed_query` import, and by the
  legacy lane in `api/retrieve.py`.

Corpus rename (display name only — corpus_id is immutable identity;
it keys FK chains and derived Qdrant collection names):

- `PATCH /corpora/{corpus_id}` with `{"name": ...}` (422 empty/>120
  chars, 404 unknown), `GET /corpora` now returns `name`.
- Frontend: name shown in the corpus picker and manager, ✎ rename
  button in CorporaView; dist rebuilt.

Verified live: rename round-trip + 404/422 paths; warm FAST query
HTTP 200 in 2 s post-restart.

## Same-day follow-up 2 — "retrieval is slow" + "this isn't synthesis"

Measured: FAST retrieval is 1.8–2.4 s warm; the perceived slowness was
(a) LLM time-to-first-token — kimi-k2.7-code:cloud 7.8 s vs
deepseek-v4-flash:cloud 3.6 s vs gemma4:31b 2.3 s (measured TTFT over
this corpus) — and (b) the ~20 s embedder cold start after idle.
Separately, NEW CHATS defaulted to synths[0] = the deterministic
stitcher ("Relevant passage: …"), which is audit output, not an answer.

- STUDY-DEFAULT: /synthesizers now puts the preferred LLM first
  (POLYMATH_DEFAULT_SYNTHESIZER, default ollama:deepseek-v4-flash:cloud)
  so new chats generate real answers; deterministic stays listed as
  "audit quotes".
- _LLM_SYSTEM rewritten: synthesize-don't-list — direct answer first,
  instructor-style explanation organized by the concept's logic,
  evidence woven across chunks, citations at sentence/paragraph ends,
  optional "for the exam" note. Grounding + abstention + artifact
  rules unchanged. Verified live (SIEM question): coherent taught
  answer with end-of-sentence citations.
- UI-PRESENCE-WARMTH: frontend pulses GET /ui_pulse every 60 s while
  the tab is visible; fleet_autopilot keeps sidecar_embedder resident
  while the pulse is fresh (embedder only — reranker stays query-gated
  for the memory ceiling). First query of a session no longer pays the
  cold start. Cold-path measured earlier: parked embedder → HTTP 200
  in 9 s via the wake-and-wait (was an instant 502).
- Frontend answer rendering: LLM answers render as markdown
  (react-markdown + remark-gfm, new deps) and raw ~80-char
  [chunk_…@a:b] locators compact to [n] tied to the ⛁ evidence
  panel's numbering ([fact]/[ref] when unmatched); full locators
  remain in copy output and the panel.
- autopilot_demand_matrix re-run after the fleet_autopilot edit: PASS
  5/5.

## Same-day follow-up 3 — deterministic stitcher removed; all lanes verified

- Owner request: deterministic-template-v3 removed from /synthesizers
  (execution path kept for explicit API callers; /chat contract path
  untouched). Request defaults now resolve to _PREFERRED_DEFAULT;
  frontend remaps saved chats off the removed id and falls back to
  synths[0]/server default. /synthesizers falls back to a stub entry
  when model daemons are unreachable.
- Retrieval verification matrix (live, cysa-study-v1):
  FAST 200/3.4 s (pass1-retrieval-v1, 10 evidence, 5 docs);
  HYBRID 200/3.5 s (hybrid-retrieval-v1, 10 evidence);
  GRAPH 200/3.8 s (graph-retrieval-v1; 6 facts incl. nmap—uses→tcp syn
  on an entity-naming query; 0 facts on a query matching no seed
  surfaces is correct lane behavior — store holds 4,116 entities /
  554 eligible-fact edges);
  ASK: procedures lane 5 hits, concepts lane 1 hit;
  default-synthesizer chat (no field) → deepseek LLM answer.

## Same-day follow-up 4 — dedupe guard, v3.3 style + reasoning layer port

DUPLICATE-DOCUMENT-GUARD-V1 (owner request — "flag it and stop it and
let the user know"):

- Layer 1 (upload, instant): /upload refuses 409 `duplicate_document`
  when the raw sha256 matches documents.source_hash in the corpus —
  catches byte-identical files under any name. Verified live.
- Layer 2 (intake, format-independent): the intake worker refuses
  (typed `DUPLICATE_DOCUMENT`, names the existing document) when the
  corpus already holds the same normalized bytes (doc_id) OR the same
  extracted text (materialization.normalized_text_sha256) — catches
  the same document in a different container format. Verified live
  with a CRLF byte-variant.
- REPLAY EXEMPTION (measured on first activation): the run's own
  (doc_id, source_name) is never a duplicate — without it the guard
  failed every intake replay against its own first attempt (3 retries
  → terminal failure on a healthy ingest). Fixed + re-verified.
- /documents runs now carry `error` (failed receipt error, ticket note
  fallback); FilesView renders it. Known nit: a duplicate refusal still
  burns the standard 3 retries before terminal — bounded, but a
  non-retryable typed failure class would be cleaner.

v3.3 → v4 style + reasoning port (owner request — "exact"):

- `orchestrator/api/polymath_style.py`: POLYMATH_SYSTEM_PROMPT ported
  VERBATIM from v3.3 chat_orchestrator (the visual-typography answer
  grammar: bold thesis → table/ASCII map → reasoning bridge → caveats,
  KVP rundowns, h2/h3, →/✓/✗ palette, display contract, "smart
  friend" voice).
- `orchestrator/api/reasoning.py`: the v3.3 reasoning layer ported
  VERBATIM (13 curated modes + 40 raw blend templates,
  apply_reasoning at the exact v3.3 composition point — prepended to
  the user prompt after RAG context). Prompt-only port; v3.3's two
  pipeline modes act as prompt-only here.
- System prompt = grounding core (evidence/citations/abstention/
  artifacts, overrides on conflict) + style layer + date block.
  GET /reasoning_modes serves the dropdown; StreamChatRequest gains
  `reasoning` + `reasoning_blend`; TopBar has a Reasoning picker,
  persisted per chat. _ollama_generate now uses the SHARED prompt
  builder (it had drifted into an inline duplicate).
- Verified live: compare-question answer opens with a bold thesis,
  fenced ASCII data-flow map, h2 sections (deepseek, graph_reason).

## Same-day follow-up 5 — reasoning stream + reranker wake

REASONING-STREAM-V1 (owner request — visible thinking keeps the wait
alive):

- Ollama chat requests carry `think: true` (one-shot fallback without
  it for models that reject thinking); `message.thinking` tokens and
  LiteLLM `delta.reasoning_content` yield `{"reasoning": ...}` pieces,
  forwarded as a new `reasoning` SSE event — never part of the
  recorded answer.
- UI: thinking streams live into the PhaseStream reasoning trail
  (mono pane, auto-follow, cursor; collapses with the trail when the
  answer lands, reviewable after). Verified live: deepseek-v4-flash
  emitted 231 reasoning events (3.5k chars) ahead of 104 answer
  tokens; answer stayed clean and opened bold-thesis.

rerank_unavailable fix (measured: first HYBRID/FAST query after idle →
`ConnectError 61` on :8743):

- fleet_autopilot: ui_active now wakes sidecar_reranker under the SAME
  memory guard as query-grace (never beside GLiNER; budget gate still
  drops it first when over ceiling).
- rerank.apply_rerank: `_await_reranker` blocks up to
  POLYMATH_RERANK_WAKE_BUDGET_S (default 90 s; reconcile ≤15 s +
  ~60 s cold start) polling /ready before the typed failure; skipped
  when a test client_factory is injected. Verified: reranker wakes
  from a ui_pulse; HYBRID retrieve 200.

## Same-day follow-up 6 — NEVER-ERROR-ON-A-COLD-MODEL

Owner rule: "when not in use I don't mind the memory-smart config, but
when I query I don't want an error from embedding or reranker — I don't
mind waiting on cold, getting an error is dumb."

The wake-waits (follow-ups 2 and 5) covered the ordinary cold path but
left one guaranteed failure: while extraction runs, GLiNER holds the
memory ceiling and the autopilot will NEVER wake the reranker, so a
query waited the full budget and still threw. Fixed by splitting the
two sidecars by their actual role:

- **Embedder = hard dependency** (no vector, no retrieval): it can only
  wait. Budget raised to 150 s, env-tunable
  (POLYMATH_EMBED_WAKE_BUDGET_S).
- **Reranker = reordering only** (it can neither add nor drop
  candidates, so fusion order is a complete, correct answer): it now
  DEGRADES instead of failing. All five call sites converted —
  fast/hybrid/graph via the shared `_rerank_children`, plus
  retrieve.py, chat.py, evidence.py. `error_code: rerank_unavailable`
  is gone from every query path.
- **No pointless waiting**: `_await_reranker` reads the supervisor
  state file; when the reranker is parked AND GLiNER is alive, it
  raises immediately rather than burning the 90 s budget and the
  client's 6 s retry backoff (measured: 6.1 s → 0.03 s).
- **Never silent**: degradation is recorded per request (ContextVar),
  surfaced as `meta.degraded` / `retrieval.degraded`, logged
  `rerank_degraded`, and rendered in the UI as
  "⚠ reranker unavailable — results ordered by RRF fusion (same
  candidate set, same recall)".

Verified: dead-port reranker → no exception, candidates preserved,
degradation carries the original error text; simulated extraction →
0.03 s degrade; live FAST/HYBRID/GRAPH after restart → 10 evidence
items each, `degraded: []`. Full determinism+contracts run: 83 failed /
969 passed — failure set BYTE-IDENTICAL to the pre-change baseline
captured this morning (zero regressions across the entire day's work).

Open items for the owner:

- One-time TCC grant: give /bin/bash Full Disk Access (or approve the
  prompt) so launchd cold-boot works; until then boot from a user
  shell, disowned (launcher exits 0 when a supervisor already runs).
- `census_probe_rollback` / corpus `census-probe` leaked into the
  live DB by the pre-existing failing test_incremental_census (the
  suite runs against the production DSN); delete when convenient.
- 83 pre-existing test failures on this branch (5 more collect-error
  files need live sidecars); untouched by this work.
- Changes are uncommitted on `architecture/evidence-first-v5`.


## Contract

Diagnose and fix the cysa-study-v1 reconciling livelock without changing extraction semantics.

## Changes

RECEIPT-GAP-REOPENS-TICKET-V1 corpus-scoping; lease-keeper wedge detection; outbox re-arm idempotency; launchd boot recovery documented (TCC-blocked).

## Proof

12 stuck runs converged; census promotion resumed; causal chain measured live in STALL_DIAGNOSIS_2026-08-27.md.

## Rejected claims

No semantic-layer change was made or claimed; the freeze was respected.

## Open contract gaps

Boot recovery remains launchd-hostile under ~/Documents (TCC); revisit with a detached supervisor.
