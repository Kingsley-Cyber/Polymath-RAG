# unit: shared/polymath_shared/latent/compiler.py
anchor: shared/polymath_shared/latent/compiler.py:1-512

## purpose
Transport-agnostic "parent-enrichment-v1" compiler: turns `ParentInput` (a parent plus ordered child chunks) into gated `CompiledParent` records through caller-supplied `complete` LLM lanes; never imports a client itself (docstring compiler.py:1-9). Strategies: single-parent, semantic failover, minimal escape, microbatch, and the combined hard-case ladder. Consumed by `shared/polymath_shared/latent/_small-modules` and `workers/workers/summary_worker_impl.py` (FACTS.importers).

## public surface
| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| ParentInput | dataclass | parent_id: str; children: list[tuple[str, int, str]] | 27-30 | — |
| CompiledParent | dataclass | 12 fields; contract default `"parent-enrichment-v1"`, prompt_version default `""` | 34-48 | — |
| call_budget | def | (bounds, n_parents: int) -> int | 51-54 | — |
| compile_parents | def | (complete, parents, bounds, input_token_ceiling) -> list[CompiledParent] | 69-120 | — |
| compile_with_semantic_failover | def | (complete_primary, complete_fallback, parents, bounds, input_token_ceiling) -> tuple[list[CompiledParent], int] | 123-169 | — |
| compile_minimal_parents | def | (complete, parents, bounds, input_token_ceiling) -> list[CompiledParent] | 175-226 | — |
| compile_with_hard_case_escape | def | (complete_primary, complete_fallback, complete_escape, parents, bounds, input_token_ceiling) -> tuple[list[CompiledParent], int, int, int] | 229-276 | — |
| compile_parents_microbatched | def | (complete, parents, bounds, input_token_ceiling, max_per_call=8, on_compiled=None, max_concurrency=1) -> list[CompiledParent] | 279-464 | — |
| compile_microbatched_with_hard_case | def | (complete_primary, complete_fallback, complete_escape, parents, bounds, input_token_ceiling, max_per_call=8, on_compiled=None, max_concurrency=1) -> tuple[list[CompiledParent], int, int, int] | 467-512 | — |
| MINIMAL_CONTRACT | const | `"parent-enrichment-minimal-v1"` | 172 | — |

Module imported by `shared/polymath_shared/latent/_small-modules` and `workers/workers/summary_worker_impl.py`; per-symbol usage not in FACTS.

## contracts
**compile_parents** — 69-120
- in: `complete(items) -> [(id, raw_text, error_class|None)]` (docstring 4-5); items are `(parent_id, SYSTEM_PROMPT, user, call_budget(bounds, 1))` (99).
- pre: none on the caller; per-parent `_estimate_tokens(SYSTEM_PROMPT + user) > input_token_ceiling` is checked BEFORE any call and yields a durable skip `ENRICH_INPUT_OVER_CEILING` (87-94, docstring 7-9).
- out: exactly one CompiledParent per parent, input order (120).
- post: statuses ∈ {READY, INVALID}; gate via `sanitize_enrichment(raw, refs, bounds)` (108-109); transport-missing rows swept to `ENRICH_NO_RESPONSE` (117-119).

**call_budget** — 51-54
- out: `min(int(bounds.max_tokens * max(1, n_parents) * 1.3) + 300, 8000)`.

**compile_with_semantic_failover** — 123-169
- in: two lanes; `complete_fallback is None` allowed → returns `(compiled, 0)` (146-147).
- out: `(compiled, semantic_failovers)` (138-139, 169).
- post: EXACTLY ONE cross-lane retry, only when error_class ∉ `SEMANTIC_FAILOVER_INELIGIBLE` (134-136, 149-152); still-failed keeps fallback disposition with detail `primary=<err>; fallback=<err>` (164-167).

**compile_minimal_parents** — 175-226
- out: CompiledParent with `contract=MINIMAL_CONTRACT`, `prompt_version=MINIMAL_PROMPT_VERSION` (201-202); output budget `min(bounds.max_tokens, 400)` (209); own gate `sanitize_minimal_enrichment` (217).

**compile_with_hard_case_escape** — 229-276
- out: `(compiled, semantic_failovers, hard_recovered, hard_terminal)` (245, 275-276).
- post: `complete_escape is None` → `(compiled, failovers, 0, 0)` (253-254); escape-rejected rows become terminal `ENRICH_HARD_CASE` with detail suffixed `escape=<err>` (270-274); over-ceiling rows never reach the escape (244-245, 256-259).

**compile_parents_microbatched** — 279-464
- defaults: `max_per_call=8`, `on_compiled=None`, `max_concurrency=1` (284-286); default 1 preserves qualified sequential behavior (305).
- post: batch buffer flushed when `len(buf) >= max_per_call or buf_est + est > input_token_ceiling` (345-346); split ladder 8→4→2→1 on transport error or dead envelope (288-291, 393-402, 428-435); ladder floor `len(batch) == 1` delegates to `compile_parents` (370-376); one-shot doubled re-ask `min(max_tokens * 2, 8000)` only when `envelope_dead and _looks_truncated(raw, max_tokens) and max_tokens < 8000` (409-413); `on_compiled` fired per batch the moment items gate (354-367); returned list keeps input order regardless of completion order (303-304, 464).

**compile_microbatched_with_hard_case** — 467-512
- out: `(compiled, failovers, recovered, hard_term)` (511-512).
- post: microbatch pass on `complete_primary` (486-489); repair ladder invoked as `compile_with_hard_case_escape(complete_fallback or complete_primary, complete_fallback, complete_escape, retry, ...)` (497-500); `max_concurrency` applies to the microbatch pass only (482-483).

## effect surface
- Postgres tables: none read, none written (FACTS.tables_read/tables_written empty) — compiler.py:1-512 [DERIVED]
- Qdrant / files / subprocess / env flags: none — compiler.py:1-512 [DERIVED]
- Network: LLM completion via caller-injected `complete` callables — compiler.py:102, 156, 211, 387, 418-419 [DERIVED]
- Threads: `ThreadPoolExecutor(max_workers=min(max_concurrency, len(batches)))` — compiler.py:453-457 [DERIVED]
- Callback: caller's `on_compiled(CompiledParent)` per parent at gate time — compiler.py:364 [DERIVED]
- Logging: logger `"polymath.enrich.compiler"` (14); warnings tagged error_code `ENRICH_BATCH_SPLIT` (396-398, 429-431), `ENRICH_BATCH_TRUNCATED` (414-417); per-batch info line (447-450) [DERIVED]
- Internal deps (top-level 18-23; lazy inside functions at 65, 140-142, 184-188, 247-249, 306-310, 484): `polymath_shared.latent.contract`, `.gate`, `.prompt`, `polymath_shared.llm_extraction.client.estimate_input_tokens` [DERIVED]

## invariants
INVARIANT: call_budget(bounds, n) ≤ 8000 — compiler.py:54 [DERIVED]
  fails-if: the doubling guard `max_tokens < 8000` (409) no longer bounds retry output; re-ask can exceed provider cap.
INVARIANT: packed batch input estimate ≤ input_token_ceiling — compiler.py:345-346 [DERIVED]
  fails-if: whole-batch call goes out over ceiling, defeating the pre-call durable-skip law (7-9).
INVARIANT: len(returned) == len(parents) and input order — compiler.py:120, 275, 464, 511 [DERIVED]
  fails-if: caller persists dropped or reordered parents.
INVARIANT: cross-lane retries per parent ≤ 1 — compiler.py:134-136, 155-156 [DERIVED]
  fails-if: model-repair loop the docstring explicitly bans (135-136).
INVARIANT: minimal escape budget == min(bounds.max_tokens, 400) ≤ 400 — compiler.py:209 [DERIVED]
  fails-if: escape stops being the tight-budget MINIMAL contract (187-189).
INVARIANT: _looks_truncated fires at len(raw) ≥ 2 * max_tokens — compiler.py:61 [DERIVED]
  fails-if: truncated envelope splits instead of doubling; each half re-issues the same shortfall (410-412).
INVARIANT: each parent belongs to exactly one batch → out[] writes disjoint — compiler.py:300-302, 340-352 [DERIVED]
  fails-if: concurrent batches (455-457) race on out[], losing results.
INVARIANT: terminal status set == {READY, INVALID} — compiler.py:36, 117-119, 223-225, 461-463 [DERIVED]
  fails-if: a PENDING row leaks to the caller and is treated as final.

## determinism & idempotency
determinism: NONDETERMINISTIC (concurrency: ThreadPoolExecutor 453-457; network: injected `complete` LLM calls 387, 418-419; output order still input order by construction 303-304, 464) — compiler.py:453-457 [DERIVED]
idempotency: SAFE (no module-level mutable state; no table/file writes; durable effects delegated to the caller's `on_compiled` at 364 — re-running re-fires that callback) — compiler.py:354-367 [DERIVED]

## failure behaviour
- `except Exception: pass` around `on_compiled(out[p.parent_id])` — compiler.py:363-366 (FACTS.fallbacks line 365). Persistence failures are swallowed; the compile continues; a READY parent whose persist threw is indistinguishable at this seam from a persisted one.
- No `raise` anywhere in the unit; every lane/gate/transport failure becomes a typed `CompiledParent.error_class` — compiler.py:1-512 [DERIVED]
- error_class values produced: `ENRICH_INPUT_OVER_CEILING` (91, 204, 331; pre-call durable skip per 7-9), `ENRICH_NO_RESPONSE` (119, 225, 389, 463), terminal `ENRICH_HARD_CASE` (272), gate classes from sanitize_enrichment / sanitize_minimal_enrichment / sanitize_microbatch (108-109, 217, 405) e.g. `ENRICH_UNPARSEABLE` (407, 425), transport error class passthrough from `complete` (104-106, 214-215).
- Log error_code tags: `ENRICH_BATCH_SPLIT` (398, 431), `ENRICH_BATCH_TRUNCATED` (417).

## dumb-code flags
- Literal `8000` in three places: 54, 409, 413 — cap duplicated, not a named constant.
- `1.3` and `300` in call_budget (54), explained only in its docstring (52-53).
- Truncation check is `len(raw) >= 2 * max_tokens` (61) but the ENRICH-BUDGET-V2 comment says "raw already ~3 chars per budgeted token" (385) — numbers disagree.
- Magic `400` minimal budget (209).
- `hard_rec` bound at 497 and never used; `recovered` recomputed at 509-510 with different semantics (all READY among retry, not escape recoveries).
- Full-contract name `"parent-enrichment-v1"` exists only as the dataclass default (47); the minimal counterpart got `MINIMAL_CONTRACT` (172) — asymmetric.
- `raw, err = "", "ENRICH_NO_RESPONSE"` then take-first-row-and-`break` (389-392): extra rows from `complete` silently dropped.
- PENDING→`ENRICH_NO_RESPONSE` sweep duplicated three times: 117-119, 223-225, 461-463.
- Lane-detail merge formats diverge: `"primary=…; fallback=…"` (165-167), `"…; escape=…"` (273-274), `"microbatch=…; …"` (506-507).

## refactor notes
- Importers `shared/polymath_shared/latent/_small-modules` and `workers/workers/summary_worker_impl.py` (FACTS.importers) — signature or field changes to the compile_* family, ParentInput, or CompiledParent ripple into both.
- The `complete` seam shape — items `(parent_id, system, user, max_tokens)`, returns `[(id, raw, err)]` — is assumed at 102, 211, 387, 418 and mirrors `LLMExtractionClient.complete_batched` (4-5); one seam change hits every lane at once.
- error_class strings are matched against `SEMANTIC_FAILOVER_INELIGIBLE` from gate (152, 258-259, 491-494) and persisted verbatim in `contract`/`error_class`/`detail` (45-47, 251-252) — renaming any class splits the taxonomy across gate and compiler.
- The per-batch `_emit`/`on_compiled` seam (354-367) exists because "four bounces each threw away a whole document's compiled-but-unpersisted work" (357-359) — do not batch or defer it.
- Split-ladder correctness rests on the `len(batch) == 1` floor delegating to `compile_parents` (370-376); the single-parent path is the proven baseline (291-293).
- `compile_microbatched_with_hard_case` routes the repair ladder's primary lane as `complete_fallback or complete_primary` (498) — the microbatch lane is deliberately not the first retry lane.

## VERIFY
```verify
grep -Fq 'min(int(bounds.max_tokens * max(1, n_parents) * 1.3) + 300, 8000)' shared/polymath_shared/latent/compiler.py
grep -Fq 'return len(raw) >= 2 * max_tokens' shared/polymath_shared/latent/compiler.py
grep -Fq 'MINIMAL_CONTRACT = "parent-enrichment-minimal-v1"' shared/polymath_shared/latent/compiler.py
grep -Fq 'min(bounds.max_tokens, 400)' shared/polymath_shared/latent/compiler.py
grep -Fq 'max_per_call: int = 8' shared/polymath_shared/latent/compiler.py
test "$(grep -c -F 'ENRICH_NO_RESPONSE' shared/polymath_shared/latent/compiler.py)" -ge 4
! grep -Fq 'import requests' shared/polymath_shared/latent/compiler.py
```
