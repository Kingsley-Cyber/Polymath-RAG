# unit: orchestrator/orchestrator/api/compare_review.py
anchor: orchestrator/orchestrator/api/compare_review.py:1-259

## purpose
Evaluation-only API module with two POST endpoints: `/compare` runs ONE question across several retrieval modes (retrieval only, no synthesis) inside one request; `/review` has a second model judge an EXISTING answer against the evidence it cited (orchestrator/orchestrator/api/compare_review.py:180-200). Neither endpoint is on the chat path and neither changes retrieval, ranking or readiness policy (orchestrator/orchestrator/api/compare_review.py:185-187). Module router is imported by `orchestrator/orchestrator/main.py` (FACTS.importers; router at orchestrator/orchestrator/api/compare_review.py:213).

## public surface
| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| compare | function, route `POST /compare` | `(req: CompareRequest) -> dict` | orchestrator/orchestrator/api/compare_review.py:57-100 | orchestrator/orchestrator/main.py (router import) |
| review | function, route `POST /review` | `(req: ReviewRequest) -> dict` | orchestrator/orchestrator/api/compare_review.py:160-194 | orchestrator/orchestrator/main.py (router import) |
| CompareRequest | pydantic model | `message: str; corpus_id: str; modes: list[str]; scope: Optional[dict] = None` | orchestrator/orchestrator/api/compare_review.py:40-45 | — |
| ReviewRequest | pydantic model | `question: str; answer: str; citations: list[str]; evidence: list[dict]; retrieval_meta: dict; reviewer: Optional[str] = None` | orchestrator/orchestrator/api/compare_review.py:48-54 | — |

Private helpers (not imported elsewhere per FACTS): `_slim` (103-141), `_run_reviewer` (197-244), `_parse_json` (247-258).

## contracts

### compare(req)
- in: `CompareRequest`; `modes` defaults to all of `COMPARABLE_MODES` via `default_factory=lambda: list(COMPARABLE_MODES)` (orchestrator/orchestrator/api/compare_review.py:43); `scope: Optional[dict] = None` = same knowledge-role scope for every arm (orchestrator/orchestrator/api/compare_review.py:44-45).
- pre: corpus must pass `require_corpus(req.corpus_id)` (orchestrator/orchestrator/api/compare_review.py:65); every uppercased, deduped mode must be in `COMPARABLE_MODES` else `422 "not comparable: {bad}; allowed {list(COMPARABLE_MODES)}"` (orchestrator/orchestrator/api/compare_review.py:67-71); non-empty mode list else `422 "no modes requested"` (orchestrator/orchestrator/api/compare_review.py:72-73).
- out: `echo_scope({"contract": "compare-retrieval-v1", "corpus_id", "question", "arms": [...]}, req.scope)` (orchestrator/orchestrator/api/compare_review.py:99-100); each arm is `{mode, ok, latency_ms, retrieval}` or `{mode, ok: False, latency_ms, error}` (orchestrator/orchestrator/api/compare_review.py:89-98).
- post: one arm per requested mode, arms run SEQUENTIALLY (deliberate: shared GPU reranker lane; parallel measured p50 12s -> 31s, 2026-09-05) (orchestrator/orchestrator/api/compare_review.py:61-63, 81); each arm calls `chat_retrieve_mode(mode, req.message, req.corpus_id, **scope_kwargs(role_scope))` with NO other knobs forwarded so arms differ only by mode (orchestrator/orchestrator/api/compare_review.py:84-87).

### review(req)
- in: `ReviewRequest`; `reviewer: Optional[str] = None` -> backend default synthesizer (orchestrator/orchestrator/api/compare_review.py:54).
- pre: `req.answer.strip()` non-empty else `422 "nothing to review: empty answer"` (orchestrator/orchestrator/api/compare_review.py:163-164).
- out: `{"contract": "answer-review-v1", "reviewer": req.reviewer or "backend-default", "review": parsed, "parse_error": ..., "raw": None if parsed else str(raw)[:2000]}` (orchestrator/orchestrator/api/compare_review.py:192-194).
- post: reviewer prompt demands STRICT JSON with keys `grounding, correctness, completeness, citation_support, retrieval_adequacy` (0-5 each), `unsupported_claims`, `missing_evidence`, `verdict` in `SUPPORTED | PARTIALLY_SUPPORTED | UNSUPPORTED` (orchestrator/orchestrator/api/compare_review.py:148-157) — but `_parse_json` only extracts the outermost `{...}` and validates nothing (orchestrator/orchestrator/api/compare_review.py:252-256); callers must tolerate missing/extra keys. [DERIVED for both halves]

## effect surface
- Postgres tables: none read, none written (FACTS.tables_read / tables_written empty).
- Retrieval engine: invoked indirectly per arm via `chat_retrieve_mode` (orchestrator/orchestrator/api/compare_review.py:75, 87).
- Network: `litellm.completion(**kwargs)` to the reviewer model, `timeout=180` (orchestrator/orchestrator/api/compare_review.py:214, 239); credentials via `_litellm_credentials(name)` from `orchestrator.api.ui` (orchestrator/orchestrator/api/compare_review.py:202, 215).
- Files / subprocesses: none.
- Env flags: none read in this file; provider credentials delegated to `orchestrator.api.ui._litellm_credentials` (orchestrator/orchestrator/api/compare_review.py:202).
- Logs: `logging.getLogger("polymath.reasoning").info("reasoning_policy %s", ...)` on policy overlay (orchestrator/orchestrator/api/compare_review.py:235-236).

## invariants
INVARIANT: COMPARABLE_MODES == `("FAST", "HYBRID", "GRAPH", "WILDCARD", "GNN")` — orchestrator/orchestrator/api/compare_review.py:37 [DERIVED]
  fails-if: any requested mode outside the tuple is refused with 422 (67-71); VECTOR is deliberately excluded as a backend primitive (36).
INVARIANT: number of arms == number of deduped requested modes — orchestrator/orchestrator/api/compare_review.py:67, 81 [DERIVED]
  fails-if: a silently dropped mode would hide a lane from the comparison.
INVARIANT: one `role_scope` computed once and shared by every arm — orchestrator/orchestrator/api/compare_review.py:78-79 [DERIVED]
  fails-if: per-arm scopes would confound "mode changed" with "scope changed".
INVARIANT: len(rows) <= 30 — orchestrator/orchestrator/api/compare_review.py:140 [DERIVED]
  fails-if: unbounded evidence payload in the compare response.
INVARIANT: passages shown <= 12, passage text <= 600 chars, source label <= 120 chars — orchestrator/orchestrator/api/compare_review.py:171-175, 182 [DERIVED]
  fails-if: oversized prompt pushed the reviewer past its window; it returned prose instead of JSON (seen in F12) (166-169).
INVARIANT: error/detail strings <= 300 chars (arm error and 502 detail) — orchestrator/orchestrator/api/compare_review.py:98, 189 [DERIVED]
INVARIANT: max_tokens == 4000 (>= 2000 floor; reasoning models return EMPTY below it) and temperature == 0 — orchestrator/orchestrator/api/compare_review.py:200-201, 214 [DERIVED]
  fails-if: tight token bound yields an empty reviewer completion (241-243).

## determinism & idempotency
determinism: NONDETERMINISTIC (clock: `time.time` at orchestrator/orchestrator/api/compare_review.py:82, 92, 97 per FACTS.nondeterminism; network: `litellm.completion` at orchestrator/orchestrator/api/compare_review.py:239; downstream retrieval via `chat_retrieve_mode` at orchestrator/orchestrator/api/compare_review.py:87)
idempotency: SAFE — no tables written, no files mutated (FACTS effect lists empty); both endpoints are read-only evaluation surfaces that "neither change retrieval, ranking or readiness policy" (orchestrator/orchestrator/api/compare_review.py:185-187). Re-running `/review` costs a fresh LLM call but mutates no state.

## failure behaviour
- compare per-arm `except Exception` (orchestrator/orchestrator/api/compare_review.py:95): SWALLOWED into the arm as `{"ok": False, "error": f"{type(exc).__name__}: {exc}"[:300]}`; HTTP stays 200 and the other arms survive (orchestrator/orchestrator/api/compare_review.py:96-98). Caller sees per-arm `ok`/`error`, never a whole-request failure.
- review reviewer failure (orchestrator/orchestrator/api/compare_review.py:187): re-raised as `HTTPException(status_code=502, detail=f"reviewer unavailable: ..."[:300])` (orchestrator/orchestrator/api/compare_review.py:188-189). An empty reviewer completion raises `RuntimeError(f"reviewer {name!r} returned an empty completion")` (orchestrator/orchestrator/api/compare_review.py:243) and surfaces as this 502.
- `_run_reviewer` reasoning-policy overlay `except Exception: pass` (orchestrator/orchestrator/api/compare_review.py:237-238): SWALLOWED silently; the reviewer runs without the policy overlay. Caller sees no signal.
- `_parse_json` `except Exception` (orchestrator/orchestrator/api/compare_review.py:257): SWALLOWED into `return (None, f"{type(exc).__name__}: {exc}")`; `/review` then returns HTTP 200 with `review=null`, `parse_error` set, and `raw` truncated to 2000 (orchestrator/orchestrator/api/compare_review.py:191-194).
- 422s raised: `not comparable: {bad}` (70-71), `no modes requested` (72-73), `nothing to review: empty answer` (163-164).

## dumb-code flags
- Magic truncation/cap numbers with no named constants: `300` (98, 189), `2000` (194), `600` (174), `120` (175), `12` (171), `30` (140), `4000`/`180` (214). [DERIVED]
- `ReviewRequest.retrieval_meta` is declared (orchestrator/orchestrator/api/compare_review.py:53) but never read anywhere in `review()` — dead input field. [DERIVED]
- `latency_ms` reported twice per arm: outer wall clock `int((time.time() - t0) * 1000)` (92, 97) AND `trace.get("latency_ms")` inside `_slim` (129); the two can disagree since the outer one wraps the whole call. [INFERRED — both values visible; disagreement follows from different measurement points.]
- `REVIEW_SYSTEM` demands "exactly these keys" (148) but nothing in code checks keys or the verdict enum after parsing (252-256). [DERIVED]
- `modes` default re-copies the `COMPARABLE_MODES` tuple into a fresh list on every request via `default_factory=lambda: list(COMPARABLE_MODES)` (43). [DERIVED]

## refactor notes
- Router is mounted by `orchestrator/orchestrator/main.py` (FACTS.importers; `router = APIRouter()` at orchestrator/orchestrator/api/compare_review.py:213) — changing the paths `/compare` or `/review` breaks the app.
- Depends on underscore-private helpers of sibling modules: `orchestrator.api.retrieve._role_scope_or_422` (orchestrator/orchestrator/api/compare_review.py:76) and `orchestrator.api.ui._default_synthesizer` / `_litellm_credentials` (orchestrator/orchestrator/api/compare_review.py:202) — renaming those breaks this file.
- The "no knobs forwarded" rule means `chat_retrieve_mode` must keep receiving only `mode, message, corpus_id, **scope_kwargs(role_scope)`; adding forwarded parameters destroys the mode-only comparison (orchestrator/orchestrator/api/compare_review.py:84-87).
- Response shape is a versioned contract: `"compare-retrieval-v1"` (99), `"answer-review-v1"` (192), and every `_slim` key (117-140) are consumed by the comparison UI — renaming keys breaks arm diffs.
- The deepseek-v4 `thinking` disable must stay in `extra_body`, not a top-level kwarg: litellm rejects top-level `thinking` for that route ("anthropic does not support parameters: ['thinking']") (orchestrator/orchestrator/api/compare_review.py:220-227).
- Sequential arm execution is deliberate (shared GPU reranker lane; parallel degraded p50 12s -> 31s) — parallelizing invalidates every `latency_ms` (orchestrator/orchestrator/api/compare_review.py:61-63).

## VERIFY
```verify
grep -Fq 'COMPARABLE_MODES = ("FAST", "HYBRID", "GRAPH", "WILDCARD", "GNN")' orchestrator/orchestrator/api/compare_review.py
grep -Fq '@router.post("/compare")' orchestrator/orchestrator/api/compare_review.py
grep -Fq '@router.post("/review")' orchestrator/orchestrator/api/compare_review.py
grep -Fq 'temperature=0, max_tokens=4000, timeout=180' orchestrator/orchestrator/api/compare_review.py
grep -Fq 'req.evidence[:12]' orchestrator/orchestrator/api/compare_review.py
! grep -Fq 'thinking=' orchestrator/orchestrator/api/compare_review.py
test "$(grep -c -F 'latency_ms' orchestrator/orchestrator/api/compare_review.py)" -ge 3
```
