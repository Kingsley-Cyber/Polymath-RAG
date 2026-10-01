# unit: shared/polymath_shared/chat_plan.py
anchor: shared/polymath_shared/chat_plan.py:1-1075

## purpose
Conversation-aware query compiler (CHAT-INTENT-PLAN-V1): one cheap, bounded LLM call turns (message, recent history) into a machine-readable plan — resolved_request, task type, retrieval need, and 1–4 typed search queries with exact terms preserved verbatim — shared/polymath_shared/chat_plan.py:4-7 [DERIVED]. The module itself is deterministic policy + validation; the only I/O is the injected `complete(system_prompt, user_prompt, max_tokens) -> (text, err)` — shared/polymath_shared/chat_plan.py:20-21 [DERIVED]. Consumed by orchestrator API routes and shared modules (FACTS.importers): orchestrator/orchestrator/api/deep_research.py, orchestrator/orchestrator/api/ui.py, shared/polymath_shared/bridge_integration.py, evidence_resolution.py, facets.py, wildcard_mapped.py — shared/polymath_shared/chat_plan.py:534-543 [DERIVED].

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| facets_enabled | def | (env=None) -> bool | shared/polymath_shared/chat_plan.py:112-115 | — |
| derive_role | def | (qtype: str) -> str | shared/polymath_shared/chat_plan.py:118-121 | — |
| default_reason | def | (qtype: str, role: str) -> str | shared/polymath_shared/chat_plan.py:124-129 | — |
| CompiledQuery | class | methods: `__post_init__` | shared/polymath_shared/chat_plan.py:159-197 | — |
| ChatPlan | class | methods: `to_dict`, `fallback` (property) | shared/polymath_shared/chat_plan.py:201-239 | — |
| task_classes | def | (text: str) -> set[str] | shared/polymath_shared/chat_plan.py:246-248 | — |
| exact_terms_from | def | (text: str) -> list[str] | shared/polymath_shared/chat_plan.py:251-263 | — |
| contract_enabled | def | (env=None) -> bool | shared/polymath_shared/chat_plan.py:280-282 | — |
| explicit_no_search | def | (message: str) -> bool | shared/polymath_shared/chat_plan.py:299-300 | — |
| is_smalltalk | def | (message: str) -> bool | shared/polymath_shared/chat_plan.py:303-304 | — |
| profile_matches_block | def | (matches) -> str | shared/polymath_shared/chat_plan.py:307-321 | — |
| fallback_plan | def | (message, *, reason, history_turns=0, wall_ms=0.0, model=None) -> ChatPlan | shared/polymath_shared/chat_plan.py:324-342 | — |
| compare_sides | def | (message: str) -> tuple[str, str] \| None | shared/polymath_shared/chat_plan.py:362-369 | — |
| references_corpus | def | (message: str) -> bool | shared/polymath_shared/chat_plan.py:376-378 | — |
| references_prior_artifact | def | (message: str, history) -> bool | shared/polymath_shared/chat_plan.py:381-390 | — |
| apply_corrections | def | (plan, message, history, corpus_ids=None) -> list[str] | shared/polymath_shared/chat_plan.py:434-500 | — |
| validate_plan | def | (raw: dict, message, *, contract=False, matches=None, facets=None) -> (ChatPlan \| None, str \| None) | shared/polymath_shared/chat_plan.py:503-652 | — |
| best_facet_for | def | (text, facets) -> facet \| None | shared/polymath_shared/chat_plan.py:663-672 | — |
| sync_facets | def | (plan) -> plan | shared/polymath_shared/chat_plan.py:720-761 | — |
| system_prompt | def | (contract, facets) -> str | shared/polymath_shared/chat_plan.py:893-894 | — |
| facets_block | def | (facets) -> str | shared/polymath_shared/chat_plan.py:897-903 | — |
| user_prompt | def | (message, history, corpus_ids, titles, matches, facets) -> str | shared/polymath_shared/chat_plan.py:918-934 | — |
| compile_plan | def | (message, history, corpus_ids, complete, budget_s, hard_budget_s, model, titles, matches, contract, facets) -> plan | shared/polymath_shared/chat_plan.py:956-1006 | — |
| plan_receipt | def | (plan) -> compact dict (§3.6 receipts / SSE) | shared/polymath_shared/chat_plan.py:1009-1028 | — |
| plan_for_evidence_route | def | (plan, override_rule) -> plan | shared/polymath_shared/chat_plan.py:1037-1058 | — |
| retrieval_text_for | def | (plan) -> str | shared/polymath_shared/chat_plan.py:1061-1074 | — |

Module imports: `polymath_shared.compiler_context` (+`titles_block`), `query_constraints` (`Constraint`, `detect_explicit_constraints`), `query_intent.intent_of_plan` — shared/polymath_shared/chat_plan.py:32-33 [DERIVED].

## contracts

**validate_plan** — shared/polymath_shared/chat_plan.py:503-652
- in: `raw` JSON dict from the LLM, `message`, flags `contract` (S4 v2), `matches` (scout profile items), `facets` ([{id,name,query,type}]).
- out: `(plan, None)` or `(None, reason)`; never raises — shared/polymath_shared/chat_plan.py:505 [DERIVED].
- pre: `raw` must be a dict else reason `"not_an_object"` — shared/polymath_shared/chat_plan.py:514-515 [DERIVED].
- post: `resolved_request` ≥ 8 chars else `"resolved_request_missing"` — shared/polymath_shared/chat_plan.py:519-521 [DERIVED]; `task_type` must be in TASK_TYPES, a QUERY type in the slot is remapped via `QUERY_TYPE_AS_TASK` (fix recorded) instead of discarded — shared/polymath_shared/chat_plan.py:524-527, 73-77 [DERIVED]; facets truncated to `[:MAX_FACETS]` — shared/polymath_shared/chat_plan.py:516 [DERIVED].
- D2: explicit "don't search" forces `retrieval_required=False`; `GENERAL_CONVERSATION` on a non-smalltalk message is retyped `GROUNDED_QA`/`corpus_grounded` — shared/polymath_shared/chat_plan.py:539-547 [DERIVED]; grounded tasks force `rr = True` — shared/polymath_shared/chat_plan.py:544-545 [DERIVED].

**apply_corrections** — shared/polymath_shared/chat_plan.py:434-500
- in: mutable `ChatPlan`, message, history, corpus_ids.
- out: list of fix strings; every applied rule recorded in `plan.compiler['corrections']` — shared/polymath_shared/chat_plan.py:450 [DERIVED].
- rule C: corpus-id token absent from the conversation is stripped from every query; trailing/leading function words trimmed; a query is never emptied — shared/polymath_shared/chat_plan.py:403-431 [DERIVED].
- rule D: a two-sided compare with one-sided coverage is rebuilt as q0 PRIMARY = side a, q1 COMPARISON = side b, kept aspects capped at `MAX_QUERIES_FACETS if plan.facets else MAX_QUERIES` — shared/polymath_shared/chat_plan.py:453-479 [DERIVED].
- rule A: explicit corpus reference forces retrieval and forbids NO_RETRIEVAL_TASKS (→ `CREATE_FROM_KNOWLEDGE` if task class ∈ {create, rewrite, continue, convert}, else `GROUNDED_SYNTHESIS`) — shared/polymath_shared/chat_plan.py:480-492 [DERIVED].
- rule B: "final version/prompt" + assistant turn + no corpus ref → `CONTINUE_PRIOR_ARTIFACT`, `queries=[]`, `retrieval_required=False`, `response_type="artifact"` — shared/polymath_shared/chat_plan.py:493-499 [DERIVED].

**fallback_plan** — shared/polymath_shared/chat_plan.py:324-342
- in: raw message, reason, history_turns, wall_ms, model.
- out: deterministic v1 plan — `GROUNDED_QA`, `corpus_grounded`, `retrieval_required=True`, single q0 `PRIMARY` = cleaned message; `compiler={"fallback": True, "reason":…, "model":…, "wall_ms":…, "history_turns":…}` — shared/polymath_shared/chat_plan.py:328-337 [DERIVED]; `intent` and `explicit_constraints` set deterministically — shared/polymath_shared/chat_plan.py:338-339 [DERIVED]; with facets on, `sync_facets` derives one facet = q0 — shared/polymath_shared/chat_plan.py:340-341 [DERIVED].

**compile_plan** — shared/polymath_shared/chat_plan.py:956-1006
- in: message, history, corpus_ids, injected `complete` LLM call, budget_s, hard_budget_s, model, titles, matches, contract, facets.
- post: budgets `COMPILER_BUDGET_S` 2.5 s soft / `COMPILER_HARD_BUDGET_S` 8.0 s hard (give up → fallback) — shared/polymath_shared/chat_plan.py:48-49 [DERIVED]; fallback rate is a receipted number (law 3) — shared/polymath_shared/chat_plan.py:15-17 [DERIVED].

**sync_facets** — shared/polymath_shared/chat_plan.py:720-761 — pure, idempotent; a plan without facets gets DERIVED ones, one per USER query in query order — FACTS doc / shared/polymath_shared/chat_plan.py:720 [DERIVED].

**plan_receipt / plan_for_evidence_route / retrieval_text_for** — shared/polymath_shared/chat_plan.py:1009-1028, 1037-1058, 1061-1074 — receipt compact form for query receipts/SSE; evidence route forces retrieval via `EVIDENCE_ROUTE_OVERRIDE = "evidence_route:retrieval_required"` — shared/polymath_shared/chat_plan.py:1034 [DERIVED].

## effect surface
- Postgres tables read/written: none (FACTS.tables_read/tables_written empty).
- Qdrant / files / subprocesses: none visible.
- Network: none in-module; the only I/O is the injected `complete(...)` LLM call — shared/polymath_shared/chat_plan.py:20-21 [DERIVED].
- Clock: `time.perf_counter` at shared/polymath_shared/chat_plan.py:978 and :985 (inside compile_plan) [DERIVED].
- Env flags (name = default):

| flag | default | anchor |
|---|---|---|
| POLYMATH_CHAT_COMPILER_MAX_TOKENS_V2 | `'1100'` | shared/polymath_shared/chat_plan.py:42 |
| POLYMATH_CHAT_COMPILER_BUDGET_S | `'2.5'` | shared/polymath_shared/chat_plan.py:48 |
| POLYMATH_CHAT_COMPILER_HARD_BUDGET_S | `'8.0'` | shared/polymath_shared/chat_plan.py:49 |
| POLYMATH_CHAT_COMPILER_MAX_TOKENS | `'600'` | shared/polymath_shared/chat_plan.py:50 |
| POLYMATH_CHAT_COMPILER_HISTORY_TURNS | `'8'` | shared/polymath_shared/chat_plan.py:51 |
| POLYMATH_CHAT_COMPILER_CONTRACT | `'0'` | shared/polymath_shared/chat_plan.py:282 |
| POLYMATH_CHAT_FACETS | `'1'` | shared/polymath_shared/chat_plan.py:114 |

## invariants
INVARIANT: MAX_QUERIES_FACETS = MAX_FACETS + ADJACENT_MAX = 5 + 1 = 6 — shared/polymath_shared/chat_plan.py:106-107 [DERIVED]
  fails-if: facet plans capped wrong in apply_corrections' rebuild — shared/polymath_shared/chat_plan.py:471-474.
INVARIANT: len(resolved_request) ≥ 8, else the whole plan is rejected — shared/polymath_shared/chat_plan.py:520-521 [DERIVED]
  fails-if: valid short resolved requests fall to fallback.
INVARIANT: len(exact_terms) ≤ 12 per plan — shared/polymath_shared/chat_plan.py:261-262 [DERIVED]
  fails-if: sparse-term lists grow past the contract shape.
INVARIANT: query word count ≤ MAX_QUERY_WORDS = 32 — shared/polymath_shared/chat_plan.py:54, 266-269 [DERIVED]
  fails-if: long queries silently truncated by `_clean_query`.
INVARIANT: origin ∉ ORIGIN_TYPES ⇒ coerced to `"USER"` — shared/polymath_shared/chat_plan.py:194-195 [DERIVED]
  fails-if: a lane's chunks wrongly pulled into CA4's answerability set — shared/polymath_shared/chat_plan.py:87-90.
INVARIANT: COMPILER_HARD_BUDGET_S (8.0) > COMPILER_BUDGET_S (2.5); comment: backup lanes plan in 3.5–5.3 s — shared/polymath_shared/chat_plan.py:48-49 [DERIVED]
  fails-if: hard budget under ~5.3 s would race the backup lanes.
INVARIANT: COMPILER_MAX_OUTPUT_TOKENS_V2 (1100) > COMPILER_MAX_OUTPUT_TOKENS (600); v2 ≈ +400 output tokens measured — shared/polymath_shared/chat_plan.py:41-42, 50 [DERIVED]
  fails-if: v2 fields truncated → contract validation failures.
INVARIANT: POLYMATH_CHAT_FACETS default on ("1") while POLYMATH_CHAT_COMPILER_CONTRACT default off ("0") — shared/polymath_shared/chat_plan.py:114, 282 [DERIVED]
  fails-if: receipts/tests assuming facet fields always present.
INVARIANT: compare sides each ≥ 3 chars and `a.lower() != b.lower()` else no split — shared/polymath_shared/chat_plan.py:367-368 [DERIVED]
  fails-if: degenerate sides produce empty/duplicate queries.
INVARIANT: HISTORY_CHARS_PER_TURN = 1500, HISTORY_TURNS default 8 — shared/polymath_shared/chat_plan.py:51-52 [DERIVED]
  fails-if: prompt-size regressions in `user_prompt` history block.
INVARIANT: MAX_PROFILE_MATCHES = 8 = bridge_integration.MAX_CONCEPTS (admission's concept window) — shared/polymath_shared/chat_plan.py:46 [DERIVED]
  fails-if: compiler emits more bridges than admission can consider.

## determinism & idempotency
determinism: NONDETERMINISTIC (clock `time.perf_counter` at shared/polymath_shared/chat_plan.py:978, :985; env-flag reads at :42, :48-51, :114, :282) — everything else is documented deterministic policy + validation — shared/polymath_shared/chat_plan.py:20-21 [DERIVED]
idempotency: SAFE (no external writes; `sync_facets` documented "Pure, idempotent" — shared/polymath_shared/chat_plan.py:720; mutation is confined to the in-memory plan passed in) [DERIVED]

## failure behaviour
- Exception → `pass` (SWALLOWED) at shared/polymath_shared/chat_plan.py:944, inside `_parse_json_object` (937-953) — caller continues past the failed block [DERIVED].
- Exception → `return None` (SWALLOWED) at shared/polymath_shared/chat_plan.py:951, same function — JSON parse yields None [DERIVED].
- Exception → handled by assignment at shared/polymath_shared/chat_plan.py:983, inside `compile_plan` (956-1006) — the run assigns the fallback path rather than propagating [INFERRED: handler kind "assign" + law 3 fallback].
- `validate_plan` never raises; it returns `(None, reason)` — shared/polymath_shared/chat_plan.py:505 [DERIVED]. Reasons seen: `"not_an_object"` :515, `"resolved_request_missing"` :521, `f"task_type_invalid:{task[:24]}"` :527.
- A query that is empty or carries instruction tokens is silently dropped from the plan (no error) — shared/polymath_shared/chat_plan.py:555-556 [DERIVED].

## dumb-code flags
- Magic `12` duplicated: docstring "≤ 12" and loop break `if len(out) >= 12` — shared/polymath_shared/chat_plan.py:253, 261 [DERIVED].
- Hardcoded acronym blocklist `("I", "A", "OK", "AI", "TV", "US", "UK", "PM", "AM", "THE", "AND")` in `exact_terms_from` — shared/polymath_shared/chat_plan.py:257 [DERIVED].
- Two stopword lists with overlapping members: `_CONTENT_STOP` :355 vs `_TRAILING_FUNCTION_WORDS` :393 [DERIVED].
- Measured-numbers comment baked in (30 of 85 fallbacks in 14 days; 3,741 receipts, 2026-09-24) justifying `QUERY_TYPE_AS_TASK` — shared/polymath_shared/chat_plan.py:67-72 [DERIVED].
- `ADJACENT_MAX = 1` and derived cap `MAX_QUERIES_FACETS` — magic seat counts — shared/polymath_shared/chat_plan.py:63, 107 [DERIVED].
- `FACET_EXTRA_OUTPUT_TOKENS = 160` from a "measured shape" — shared/polymath_shared/chat_plan.py:109 [DERIVED].

## refactor notes
- Blast radius: 8 importers (orchestrator api `ui.py` + `deep_research.py`; shared `bridge_integration.py`, `evidence_resolution.py`, `facets.py`, `wildcard_mapped.py`, `_small-modules-2/3`) — shared/polymath_shared/chat_plan.py:534-542 [DERIVED]; any ChatPlan/CompiledQuery field rename reaches all of them.
- `ORIGIN_TYPES` must gain any new origin before use, else `__post_init__` coerces it to `"USER"` and corrupts CA4 answerability — shared/polymath_shared/chat_plan.py:87-91, 194-195 [DERIVED].
- Receipt/SSE field names are protocol: `_V2_QUERY_FIELDS = ["expected_contribution", "evidence_requirement"]`, `facet_id`, `compiler` keys — shared/polymath_shared/chat_plan.py:1009-1031 [DERIVED].
- `EVIDENCE_ROUTE_OVERRIDE = "evidence_route:retrieval_required"` is a string contract matched by evidence-route callers — shared/polymath_shared/chat_plan.py:1034, 1037-1058 [DERIVED].
- `POLYMATH_CHAT_FACETS=0` must restore the pre-facet compiler byte for byte — any facet change needs flag-off parity — shared/polymath_shared/chat_plan.py:105 [DERIVED].
- Laws 1–4 each have a regression in tests/determinism/test_chat_compiler.py — behavior changes must update those tests — shared/polymath_shared/chat_plan.py:9 [DERIVED].

## VERIFY
```verify
grep -Fq 'MAX_QUERIES = 4' shared/polymath_shared/chat_plan.py
grep -Fq 'CONTRACT = "chat-intent-plan-v1"' shared/polymath_shared/chat_plan.py
grep -Fq 'q0: authoritative user query' shared/polymath_shared/chat_plan.py
grep -Fq 'POLYMATH_CHAT_COMPILER_HARD_BUDGET_S' shared/polymath_shared/chat_plan.py
! grep -Fq 'chat-intent-plan-v3' shared/polymath_shared/chat_plan.py
test "$(grep -c -F 'time.perf_counter' shared/polymath_shared/chat_plan.py)" -ge 2
```
