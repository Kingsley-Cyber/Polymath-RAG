# unit: shared/polymath_shared/facets.py
anchor: shared/polymath_shared/facets.py:1-175

## purpose
The facet step of the chat query compiler (FACET-RETRIEVAL-V1 F1): `compile_facets` makes ONE bounded LLM call over only the message + recent conversation and names 1–5 facets (a part of the request answerable on its own), each with one search query and an aspect type — shared/polymath_shared/facets.py:1-15 [DERIVED]. Corpus-agnostic by construction: the prompt builder has no parameter for a corpus id, title list or profile match — shared/polymath_shared/facets.py:8-10, 70-74 [DERIVED]. Built to fix receipt `q_e09925df009649c6be872299` (2026-09-27), where one part of a request got no search — shared/polymath_shared/facets.py:3-6 [DERIVED]. `facet_coverage` is the post-retrieval verdict: a facet is covered when ≥ 1 of its queries returned final evidence whose judge score clears the floor — shared/polymath_shared/facets.py:14-15, 153-175 [DERIVED].

## public surface
| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| compile_facets | def | (message, history, complete, *, budget_s=FACET_BUDGET_S, model=None) -> dict | shared/polymath_shared/facets.py:117-146 | orchestrator/orchestrator/api/ui.py [INFERRED: importer listed at module level, per-symbol use not shown] |
| parse_facets | def | (raw: dict, message: str) -> (list[dict] \| None, str \| None) | shared/polymath_shared/facets.py:77-114 | — |
| facet_user_prompt | def | (message: str, history: Iterable) -> (str, int) | shared/polymath_shared/facets.py:70-74 | — |
| facet_coverage | def | (facets: Iterable[dict], final_detail: Iterable[dict], *, floor: float) -> dict | shared/polymath_shared/facets.py:153-175 | — |
| FACET_CONTRACT | const | "chat-facets-v1" | shared/polymath_shared/facets.py:37 | — |
| FACET_MAX_OUTPUT_TOKENS | const | int(env, default 400) | shared/polymath_shared/facets.py:39 | — |
| FACET_BUDGET_S | const | float(env, default 4.0) | shared/polymath_shared/facets.py:41 | — |
| FACET_SYSTEM_PROMPT | const | multi-line string, keys `resolved_request`, `facets[{id,name,query,type}]` | shared/polymath_shared/facets.py:49-67 | — |
| facets_enabled | re-export | imported from polymath_shared.chat_plan, listed in `__all__` | shared/polymath_shared/facets.py:34, 46-47 | — |

`__all__` = ["FACET_BUDGET_S", "FACET_CONTRACT", "FACET_MAX_OUTPUT_TOKENS", "FACET_SYSTEM_PROMPT", "compile_facets", "facet_coverage", "facet_user_prompt", "facets_enabled"] — shared/polymath_shared/facets.py:46-47 [DERIVED].

## contracts
**compile_facets** — shared/polymath_shared/facets.py:117-146 [DERIVED]
- in: `message`, `history`, injected `complete(system_prompt, user_prompt, max_tokens) -> (text, err)`.
- out: dict keys `{"contract", "facets": [...] | None, "fallback", "reason", "wall_ms", "model", "n", "resolved_request"}` plus `history_turns`; on success `n = len(facets)`, `fallback = False` — shared/polymath_shared/facets.py:119, 123-124, 145.
- pre: none enforced; prompt built from message + `_history_block(history)` — shared/polymath_shared/facets.py:122.
- post: never raises; every failure is a receipted `facets: None` with a `reason` — shared/polymath_shared/facets.py:119-120, 131-144.
- call made: `complete(FACET_SYSTEM_PROMPT, prompt, FACET_MAX_OUTPUT_TOKENS)` — shared/polymath_shared/facets.py:126.
- budget: if `wall_ms > budget_s * 1000` the result is discarded, reason `budget_exceeded:{int(wall_ms)}ms` — shared/polymath_shared/facets.py:134-136.

**parse_facets** — shared/polymath_shared/facets.py:77-114 [DERIVED]
- in: parsed JSON dict, message.
- out: `(facets, None)` or `(None, reason)`; reasons: `not_an_object`, `facets_missing`, `no_usable_facets` — shared/polymath_shared/facets.py:82-83, 85, 113.
- post: ids renumbered `f1…fn` in model order; facet without usable name dropped; empty/instruction-carrying query falls back to the name; duplicate lowercased queries folded; f1 forced `PRIMARY`, other types restricted to `FACET_TYPES` else `MECHANISM`; capped at `MAX_FACETS` — shared/polymath_shared/facets.py:78-81, 92-111.
- emitted facet shape: `{"id": "f<k>", "name", "query", "type"}` — shared/polymath_shared/facets.py:109.

**facet_coverage** — shared/polymath_shared/facets.py:153-175 [DERIVED]
- in: facets (each may carry `query_ids`), `final_detail` rows (each with `query_ids`, optional `rerank_score`), keyword `floor`.
- out: `{"covered": [fid...], "uncovered": [fid...], "judge": "live" | "unjudged"}` — shared/polymath_shared/facets.py:175.
- post: COVERED when a row sharing a query_id has `_sig(rerank_score) >= floor`; if the judge never scored (`judged` False), a facet with any final evidence counts covered and verdict is `judge: unjudged` — shared/polymath_shared/facets.py:154-156, 158, 170-173.

**facet_user_prompt** — shared/polymath_shared/facets.py:70-74 [DERIVED]
- out: `("RECENT CONVERSATION:\n{hist}\n\nCURRENT MESSAGE:\n{message}\n\nJSON:", n_history_turns)`; no corpus/title/profile parameter exists — shared/polymath_shared/facets.py:71-74.

## effect surface
- env read: `POLYMATH_CHAT_FACETS_MAX_TOKENS` = `'400'` — shared/polymath_shared/facets.py:39; `POLYMATH_CHAT_FACETS_BUDGET_S` = `'4.0'` — shared/polymath_shared/facets.py:41.
- network: only via the injected `complete` callable (the single LLM call) — shared/polymath_shared/facets.py:17, 126; module docstring claims the only I/O is that callable — shared/polymath_shared/facets.py:17.
- Postgres tables read/written: none (FACTS `tables_read`/`tables_written` empty) — shared/polymath_shared/facets.py:118-119.
- imports from `polymath_shared.chat_plan`: `MAX_FACETS`, `QUERY_TYPES`, `_clean_query`, `_has_instruction_tokens`, `_history_block`, `_parse_json_object`, `_short`, `facets_enabled` — shared/polymath_shared/facets.py:26-35.

## invariants
INVARIANT: number of returned facets `<= MAX_FACETS` (from chat_plan; loop breaks at `len(out) >= MAX_FACETS`) — shared/polymath_shared/facets.py:110-111 [DERIVED]
  fails-if: a verbose model output could grow the plan's query set beyond chat_plan's cap.
INVARIANT: first facet type `== "PRIMARY"` (`if not out: qtype = "PRIMARY"`) — shared/polymath_shared/facets.py:105-106 [DERIVED]
  fails-if: downstream consumers keying on f1-as-core would treat a non-core facet as the request's core.
INVARIANT: facet ids match `f{len(out)+1}` for k = 1..n, no gaps — shared/polymath_shared/facets.py:109 [DERIVED]
  fails-if: `query_ids`/coverage joins on facet id would miss dropped facets.
INVARIANT: `"BRIDGE"` and `"ADJACENT"` excluded from `FACET_TYPES` (built from `QUERY_TYPES`) — shared/polymath_shared/facets.py:43-44 [DERIVED]
  fails-if: parse would accept bridge/adjacent as facet aspect types, contradicting the design note.
INVARIANT: `_sig` input clamped to `[-30.0, 30.0]` before `math.exp` — shared/polymath_shared/facets.py:149-150 [DERIVED]
  fails-if: `math.exp` overflow on extreme rerank logits.
INVARIANT: every non-PRIMARY facet type ∈ `FACET_TYPES` or is replaced by `"MECHANISM"` — shared/polymath_shared/facets.py:107-108 [DERIVED]
  fails-if: unknown model-invented type strings leak into plan receipts.
INVARIANT: dedupe key is `query.lower()` across facets — shared/polymath_shared/facets.py:100-103 [DERIVED]
  fails-if: synonym-split facets (the anti-pattern the prompt bans at line 66) survive parsing.

## determinism & idempotency
determinism: NONDETERMINISTIC (`time.perf_counter` at shared/polymath_shared/facets.py:121 and :129 feeds `wall_ms` and the budget verdict; the LLM call itself is nondeterministic via injected `complete` — shared/polymath_shared/facets.py:126)
idempotency: SAFE (no writes; tables_read/tables_written empty, pure functions besides the injected call and clock — shared/polymath_shared/facets.py:17)

## failure behaviour
- Broad handler: `except Exception` around `complete(...)` swallows every transport error; `text, err = "", f"{type(exc).__name__}"` — only the exception class name survives, the message is dropped — shared/polymath_shared/facets.py:126-128 [DERIVED]. Caller then sees `facets: None`, `fallback: True`, `reason = "transport:{err}"` — shared/polymath_shared/facets.py:132-133; the plan derives its facets from the compiled queries instead — shared/polymath_shared/facets.py:12-13 [DERIVED].
- Reason codes produced: `transport:{ExceptionName}` (:132), `budget_exceeded:{int}ms` (:135), `invalid_json` (:139), `invalid_facets:{subreason}` (:143) — shared/polymath_shared/facets.py:132-143 [DERIVED].
- No error codes raised; the module never raises out of `compile_facets` — shared/polymath_shared/facets.py:119-120 [DERIVED].
- Unjudged turn: no `rerank_score` in any row → evidence-carrying facets still covered, `judge: "unjudged"`, never a floor verdict — shared/polymath_shared/facets.py:155-156, 158, 170-173 [DERIVED].

## dumb-code flags
- `parse_facets(raw, message)` — `message` is never used in the body — shared/polymath_shared/facets.py:77-114 [DERIVED].
- Budget is enforced only after the call completes: `complete` runs to finish, then `wall_ms > budget_s * 1000` discards the result — the wall time is spent either way; "never waits" (comment at :40) means "never blocks the turn on the result", not cancellation — shared/polymath_shared/facets.py:126, 129, 134-136 [DERIVED].
- Magic clamp `30.0` / `-30.0` in `_sig`, unexplained — shared/polymath_shared/facets.py:150 [DERIVED].
- Literal `400` appears twice with unrelated meanings: output-token default `"400"` (:39) and `_short(raw.get("resolved_request"), 400)` char cap (:145) — shared/polymath_shared/facets.py:39, 145 [DERIVED].
- Comment says measured output ≈ 180 tokens but default headroom is 400 — shared/polymath_shared/facets.py:38-39 [DERIVED].
- `rec["model"] = model` records only the caller-passed name, default `None`; nothing fills in the actual model used by `complete` — shared/polymath_shared/facets.py:118, 123, 126 [DERIVED].
- Silent default `"MECHANISM"` for any unknown/`PRIMARY`-on-non-first type — shared/polymath_shared/facets.py:107-108 [DERIVED].

## refactor notes
- Importer blast radius: `orchestrator/orchestrator/api/ui.py` imports this module (FACTS.importers); changing `__all__` or signatures breaks it — shared/polymath_shared/facets.py:46-47 [INFERRED: per-symbol usage not shown in FACTS].
- Eight names are imported from `polymath_shared.chat_plan`, five of them private helpers (`_clean_query`, `_has_instruction_tokens`, `_history_block`, `_parse_json_object`, `_short`) — renaming those breaks this module at import time — shared/polymath_shared/facets.py:26-35 [DERIVED].
- `FACET_CONTRACT = "chat-facets-v1"` is a versioned contract string stamped into every receipt; changing it invalidates consumers that check the contract field — shared/polymath_shared/facets.py:37, 123 [INFERRED: receipts carry it, consumers unspecified].
- `facet_coverage` joins facets to evidence via `query_ids` on both sides and scores via `rerank_score` sigmoid vs `floor`; renaming those row keys breaks the verdict — shared/polymath_shared/facets.py:154-173 [DERIVED].
- The fallback contract is behavioral: every failure must keep returning `facets: None` with a `reason` so the plan can derive facets from compiled queries — do not convert to raising — shared/polymath_shared/facets.py:12-13, 119-120 [DERIVED].

## VERIFY
```verify
grep -Fq 'FACET_CONTRACT = "chat-facets-v1"' shared/polymath_shared/facets.py
grep -Fq 'MAX_FACET_NAME_CHARS = 80' shared/polymath_shared/facets.py
grep -Fq 'budget_exceeded:' shared/polymath_shared/facets.py
grep -Fq 'return 1.0 / (1.0 + math.exp(-max(-30.0, min(30.0, float(x)))))' shared/polymath_shared/facets.py
test "$(grep -c -F 'rec[' shared/polymath_shared/facets.py)" -ge 4
grep -Eq 'qtype = .PRIMARY.' shared/polymath_shared/facets.py
! grep -Fq 'qdrant' shared/polymath_shared/facets.py
```
