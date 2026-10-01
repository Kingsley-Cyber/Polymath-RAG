# unit: shared/polymath_shared/reasoning_policy.py
anchor: shared/polymath_shared/reasoning_policy.py:1-253

## purpose
Maps a semantic role (BRIDGE, STRUCTURED_COMPILER, REVIEWER, CHAT_SYNTHESIS) + model + API surface to concrete reasoning-budget request params, per provider family — shared/polymath_shared/reasoning_policy.py:1-19 [DERIVED]. Keeps reasoning ceiling and output budget separate so reasoning can never truncate the structured contract — shared/polymath_shared/reasoning_policy.py:4-8 [DERIVED]. Consumed by orchestrator api modules and the extraction httpx client — FACTS.importers [DERIVED]. EXTRACTION is deliberately not routed through it (contract-hash-locked, already off) — shared/polymath_shared/reasoning_policy.py:19 [DERIVED].

## public surface
| symbol | kind | signature (params -> return) | anchor | used by |
| RolePolicy | class | frozen dataclass (role, preferred_max_reasoning_tokens, fallback_effort, allow_reasoning_disable, target_output_tokens, hard_output_tokens) | shared/polymath_shared/reasoning_policy.py:40-46 | module-internal |
| policy_enabled | def | () -> bool | shared/polymath_shared/reasoning_policy.py:61-64 | gates apply_* |
| provider_family | def | (model: str) -> str | shared/polymath_shared/reasoning_policy.py:85-99 | apply_* / receipts |
| reasoning_params | def | (role: str, model: str, api_surface: str = S_LITELLM) -> dict | shared/polymath_shared/reasoning_policy.py:112-173 | apply_*; importers |
| ollama_think | def | (model: str) -> bool \| str | shared/polymath_shared/reasoning_policy.py:190-197 | chat synthesis caller |
| apply_litellm | def | (kwargs: dict, role: str, model: str) -> dict | shared/polymath_shared/reasoning_policy.py:200-234 | orchestrator/api/compare_review.py, deep_research.py, ui.py; llm_extraction/client.py (module importers) |
| apply_chat_completions | def | (payload: dict, role: str, model: str) -> dict | shared/polymath_shared/reasoning_policy.py:237-253 | llm_extraction/client.py (module importer) |

Internal: `_pol` (67-68), `_model_name` (79-82), `_env_int` (102-109), `_record` (176-187).

## contracts
**reasoning_params(role, model, api_surface=S_LITELLM)** — shared/polymath_shared/reasoning_policy.py:112-173
- in: role str; model str (litellm route prefix allowed, stripped via `_LITELLM_ROUTES` 74-82); surface one of `chat_completions`/`litellm`/`responses`/`ollama` (33-36, 112).
- out: `{"top_level": {...}, "extra_body": {...}, "max_output_tokens": int}` (113-114, 173); `max_output_tokens` is `None` when out_cap falsy (173).
- pre: unknown role silently falls back to `ROLE_POLICIES[STRUCTURED_COMPILER]` (67-68).
- post: numeric budget capped `min(budget, OWNER_MAX_REASONING_TOKENS)` (124-126); env hooks `POLYMATH_REASONING_MAX_{role}` / `POLYMATH_OUTPUT_MAX_{role}` (124, 127); never both `reasoning_effort` and `thinking_budget` in one bag (168-171).
- per family: qwen hybrid → `enable_thinking=False, preserve_thinking=False` (132-138); qwen thinking-only → `thinking_budget` only (139-142); deepseek → `extra["enable_thinking"]=False` + `extra["thinking"]={"type": "disabled"}` (144-150); glm → `thinking disabled` (151-152); gemini → `thinking_level=low` (153-154); claude → `extra["effort"]=fallback_effort` (155-156); openai → `top["reasoning_effort"]` (157-158); other → `reasoning_effort` only when `not allow_reasoning_disable` and surface != litellm (159-163); other+ollama → `top["think"]=False` (165-166).

**apply_litellm(kwargs, role, model)** — shared/polymath_shared/reasoning_policy.py:200-234
- in: `litellm.completion` kwargs dict, mutated in place.
- out: sanitized applied dict (role, provider, surface, top_level, extra_body, max_output_tokens) or `{}` when disabled (205-206, 230-234).
- pre: `policy_enabled()` else pure no-op, byte-identical to pre-RB (61-64, 205-206).
- post: `kwargs.update(top)`; extra merged into `kwargs["extra_body"]` (227-229); for `anthropic/` models `thinking` hoisted to top level and added to `allowed_openai_params` (214-226); receipt line appended (233).

**apply_chat_completions(payload, role, model)** — shared/polymath_shared/reasoning_policy.py:237-253
- in: OpenAI-compat `/v1/chat/completions` payload dict, mutated in place; chat-COMPILER stage only, never document extraction (238-239).
- out: applied dict or `{}` when disabled (241-242, 253).
- post: `top_level` + `extra_body` flattened into payload TOP level (raw httpx, no SDK unpacks extra_body) (244-248); receipt appended (252).

**ollama_think(model)** — shared/polymath_shared/reasoning_policy.py:190-197
- in: model name; env `POLYMATH_CHAT_THINK` in ("1","on","true") turns thinking on (194).
- out: `"high"`/`"low"` for gpt-oss (195-196); bool for everything else (197).

**policy_enabled()** — shared/polymath_shared/reasoning_policy.py:61-64
- true iff `POLYMATH_REASONING_POLICY == "1"`; default `"0"` = off (64).

## effect surface
- env read: `POLYMATH_REASONING_POLICY = '0'` — shared/polymath_shared/reasoning_policy.py:64 [DERIVED]
- env read: `POLYMATH_REASONING_RECEIPT = '/private/tmp/polymath_fleet/reasoning_policy.jsonl'` — shared/polymath_shared/reasoning_policy.py:182 [DERIVED]
- env read: `POLYMATH_CHAT_THINK = 'off'` — shared/polymath_shared/reasoning_policy.py:194 [DERIVED]
- env read (dynamic): `POLYMATH_REASONING_MAX_{role}`, `POLYMATH_OUTPUT_MAX_{role}` — shared/polymath_shared/reasoning_policy.py:124,127 [DERIVED]
- file write: append JSONL receipt line `{"ts": <time.time()>, **applied}` to the receipt path — shared/polymath_shared/reasoning_policy.py:180-185 [DERIVED]; FACTS.collections tags `polymath_fleet` (line 183), which in SOURCE is the receipt directory
- Postgres tables read/written: none — FACTS.tables_read/tables_written [DERIVED]
- no network, subprocess, or DB access of its own; module self-describes as pure adapter — shared/polymath_shared/reasoning_policy.py:1 [DERIVED]

## invariants
INVARIANT: max `preferred_max_reasoning_tokens` in ROLE_POLICIES (100) == `OWNER_MAX_REASONING_TOKENS` (100) — shared/polymath_shared/reasoning_policy.py:51,54-56 [DERIVED]
  fails-if: owner ceiling changes but dict literals keep 100 → roles exceed owner rule without env override.
INVARIANT: post-override budget ≤ 100 (`min(int(budget), OWNER_MAX_REASONING_TOKENS)`) — shared/polymath_shared/reasoning_policy.py:124-126 [DERIVED]
  fails-if: env override could push reasoning past the owner ceiling.
INVARIANT: `hard_output_tokens` > `target_output_tokens` for every role (350>300, 500>350, 200>150, 6000>2000) — shared/polymath_shared/reasoning_policy.py:54-57 [DERIVED]
  fails-if: hard cap below target truncates bridge/compiler JSON.
INVARIANT: per bag, `reasoning_effort` and `thinking_budget` never coexist (pop `reasoning_effort`) — shared/polymath_shared/reasoning_policy.py:168-171 [DERIVED]
  fails-if: invalid combo rejected by provider (Qwen doc note, line 13).
INVARIANT: policy off ⇒ `apply_litellm`/`apply_chat_completions` return `{}` and mutate nothing — shared/polymath_shared/reasoning_policy.py:205-206,241-242 [DERIVED]
  fails-if: default traffic stops being byte-identical to pre-RB behaviour (62-63).
INVARIANT: `_record` never raises (`except Exception: pass`) — shared/polymath_shared/reasoning_policy.py:179-187 [DERIVED]
  fails-if: a receipt-path failure would otherwise kill the LLM call itself.

## determinism & idempotency
determinism: NONDETERMINISTIC (env reads at 64, 124, 127, 182, 194; receipt timestamp `_t.time()` at 185) — pure for fixed env
idempotency: SAFE for payload content (dict.update of the same overlay is stable) but each enabled apply_* call appends one more receipt line (184-185, 233, 252) — repeated calls grow the JSONL

## failure behaviour
- `_record`: `except Exception: pass` — all receipt-write failures swallowed; caller still receives the applied dict — shared/polymath_shared/reasoning_policy.py:186-187 [DERIVED]
- `_env_int`: `ValueError` swallowed → returns `default`; a non-numeric env override is silently ignored — shared/polymath_shared/reasoning_policy.py:104-109 [DERIVED]
- `_pol`: unknown role never errors, silently becomes STRUCTURED_COMPILER policy — shared/polymath_shared/reasoning_policy.py:67-68 [DERIVED]
- no error codes raised anywhere in the module — SOURCE [DERIVED]

## dumb-code flags
- literal `100` repeated in ROLE_POLICIES (BRIDGE/STRUCTURED_COMPILER/REVIEWER) duplicates `OWNER_MAX_REASONING_TOKENS = 100` — shared/polymath_shared/reasoning_policy.py:51,54-56 [DERIVED]
- `{"type": "disabled"}` literal appears 3× (deepseek, glm, anthropic-transport rewrite) — shared/polymath_shared/reasoning_policy.py:150,152,220 [DERIVED]
- CHAT_SYNTHESIS declares `preferred_max_reasoning_tokens=None` ("low/adaptive", 42, 57) but the thinking-only-Qwen path forces a numeric `thinking_budget = budget or OWNER_MAX_REASONING_TOKENS` = 100 — shared/polymath_shared/reasoning_policy.py:141 [DERIVED]
- `S_RESPONSES` constant defined (35) but `reasoning_params` has no branch keyed to it; only a comment mentions the Responses API — shared/polymath_shared/reasoning_policy.py:35,143 [DERIVED]
- doc says Claude "manual min 1024" while code sends only `effort` — the 1024 exists only as a comment literal, never in code — shared/polymath_shared/reasoning_policy.py:15,155-156 [DERIVED]

## refactor notes
- Signature/return-shape changes to `reasoning_params`, `apply_litellm`, `apply_chat_completions`, `ollama_think` hit all four importers: orchestrator/orchestrator/api/compare_review.py, deep_research.py, ui.py, shared/polymath_shared/llm_extraction/client.py — FACTS.importers [DERIVED]
- Do not remove the `policy_enabled()` gate: default-off no-op is the byte-identical-compatibility promise for every importer — shared/polymath_shared/reasoning_policy.py:61-64,205-206,241-242 [DERIVED]
- The `anthropic/` branch (thinking hoisted top-level + `allowed_openai_params`) fixes litellm not merging extra_body on that route; reverting placement re-enables full-length thinking on DeepSeek-via-Anthropic — shared/polymath_shared/reasoning_policy.py:209-226 [DERIVED]
- `apply_chat_completions` must flatten extra_body into the payload top level (raw httpx); SDK-style nesting reintroduces the ignored-field bug class — shared/polymath_shared/reasoning_policy.py:244-248 [DERIVED]
- Receipt record shape `{ts, role, provider, surface, top_level, extra_body, max_output_tokens}` is the Slice-2 wire proof; changing keys breaks auditability of actual outgoing params — shared/polymath_shared/reasoning_policy.py:177-178,230-233,249-252 [INFERRED: doc says the receipt exists to prove actual params per live call]
- Qwen switch names (`enable_thinking`, `thinking_budget`, `preserve_thinking`) are DashScope OpenAI-compat fields; renaming them breaks Alibaba surfaces — shared/polymath_shared/reasoning_policy.py:12-13,132-142,215-219 [DERIVED]

## VERIFY
```verify
grep -Fq 'OWNER_MAX_REASONING_TOKENS = 100' shared/polymath_shared/reasoning_policy.py
grep -Fq 'return os.environ.get("POLYMATH_REASONING_POLICY", "0") == "1"' shared/polymath_shared/reasoning_policy.py
grep -Fq 'CHAT_SYNTHESIS:      RolePolicy(CHAT_SYNTHESIS, None, "low", False, 2000, 6000),' shared/polymath_shared/reasoning_policy.py
grep -Fq 'if "reasoning_effort" in bag and "thinking_budget" in bag:' shared/polymath_shared/reasoning_policy.py
grep -Fq '"/private/tmp/polymath_fleet/reasoning_policy.jsonl")' shared/polymath_shared/reasoning_policy.py
test "$(grep -c -F '{"type": "disabled"}' shared/polymath_shared/reasoning_policy.py)" -ge 3
```
