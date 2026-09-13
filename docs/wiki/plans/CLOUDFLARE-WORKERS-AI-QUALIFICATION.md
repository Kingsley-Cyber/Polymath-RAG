---
change_id: CLOUDFLARE-WORKERS-AI-V1
date: 2026-09-13
last_reviewed: 2026-09-13
status: qualified PROMOTE (both functions) — kept enabled:false in the commit; activate = enabled:true + fleet bounce; 5/6 lanes also await account ids
architecture_impact: "Adds Cloudflare Workers AI as a supplemental provider family (6 lanes) over the EXISTING lane/pool/limiter abstraction. No existing provider changed; Parent-MAP untouched. Live only after a fleet bounce (shared/ changed)."
---

# Cloudflare Workers AI — qualification (CLOUDFLARE-WORKERS-AI-V1)

Model `@cf/qwen/qwen3-30b-a3b-fp8` on the OpenAI-compatible endpoint
`https://api.cloudflare.com/client/v4/accounts/<ACCOUNT_ID>/ai/v1/chat/completions`. All six
tokens verify `active`; the account id is a per-lane env secret (`CLOUDFLARE_ACCOUNT_ID_n`).
**No token or account id appears in any committed file** (env-variable NAMES only). Every
number below is a live measurement against the one account id supplied so far (token 2) —
qualification is model+contract, which is account-independent; the other five accounts add
CAPACITY, not a different verdict.

## Distinct-account check
Workers-AI-scoped tokens cannot enumerate their own account (`GET /accounts` → empty; only
`/user/tokens/verify` works), so five of six account ids must come from the owner. Of the ids
present, **1 of 6** is set; a duplicate-account check runs at load time and in the canary — it
cannot yet fire on a single id. **Provide `CLOUDFLARE_ACCOUNT_ID_{1,3,4,5,6}` to activate the
remaining lanes**; if any two match, those two share ONE free daily allocation (reported then).

## Model behaviour finding (decisive)
`@cf/qwen/qwen3-30b-a3b-fp8` is a reasoning model. On the OpenAI-compat endpoint it returns a
separate `reasoning`/`reasoning_content` field and, at small `max_tokens`, spends the whole
budget thinking and returns EMPTY `content` (`finish_reason=length`). The **Cloudflare-supported
disable method is Qwen's own documented `/no_think` soft switch** appended to the prompt —
measured: `reasoning_effort`, `enable_thinking`, `chat_template_kwargs.enable_thinking`, and
`reasoning:{effort:none}` are all IGNORED or blank the output; only `/no_think` cleanly disables
thinking (0 reasoning tokens, valid output). It is a prompt STRING, not a fabricated parameter,
carried per-lane as `think_suffix`.

## GRAPH EXTRACTION
| field | value |
| --- | --- |
| model | @cf/qwen/qwen3-30b-a3b-fp8 (lanes cloudflare1–4, dedicated:false) |
| test cases | 3 real cinema neighborhoods, production prompt + schema + sanitize gate |
| request wrapper | production `LLMExtractionClient` (`_extract_prompt`, the path the batched call falls back to) |
| valid extraction % | **100%** (3/3) — schema-valid AND sanitize-valid, both reasoning modes |
| entity yield | thinking-on 22 · /no_think 79 (skewed) |
| relationship yield | **thinking-on 23 · /no_think 8** |
| compiler validity | 100% (0 `SANITIZE_*` on the per-neighborhood path) |
| empty responses | 0 |
| mean / p95 latency | thinking-on 7.8 / 9.4 s · /no_think 7.5 / 13.7 s |
| usage | out-tokens ~1.4k/call (thinking-on); one /no_think call truncated at the 2500 cap |
| response_format | `json_object` ACCEPTED (returns the contract object) |
| **promotion decision** | **PROMOTE, thinking ON** — reasoning materially improves RELATION yield (23 vs 8) and avoids the entity-only truncation; `/no_think` is entity-heavy/relation-poor here, so extraction lanes keep reasoning on (`think_suffix: null`). |

## DOCUMENT PROFILE
| field | value |
| --- | --- |
| model | @cf/qwen/qwen3-30b-a3b-fp8 (lanes cloudflare_summary1–2, dedicated:true, pinned to `doc_profile`) |
| test documents | 3 real cinema documents, production fingerprint + `profile_prompt_vnext` + `compile_llm_output` |
| mode | **TEXT** (`structured:"text"`, `json_mode:false`) — the profile is TAGGED LINES, not a JSON object |
| valid profile % | **100%** (3/3) `ok=True`, both reasoning modes |
| empty responses | 0 |
| mean latency | thinking-on 5.4 s · **/no_think 0.7 s** |
| quality (compiler) | thinking-on 0.85–0.87 · **/no_think 0.82–0.94** |
| fields populated | thinking-on 14–18 · **/no_think 17–36** |
| **promotion decision** | **PROMOTE, `/no_think`** — reasoning does NOT help profiles: `/no_think` is faster, richer (more fields), and equal-or-higher quality. First canary FALSE-negatived on a harness bug (forced `json_mode` → the model returned a JSON error blob); corrected to text mode, it passes. |

## Quota / error handling (`cloudflare_errors.py` + `limiter.park_provider_day`)
- **3036 (daily free allocation exhausted)** → `DAILY_FREE_QUOTA_EXHAUSTED`: park the account
  until the next UTC reset via the provider-RPD-exhausted gate — `admit()` then refuses BEFORE
  dispatch (0 HTTP, 0 quota), never a retry-loop; other lanes/providers continue; resumes on reset.
- **3040 (out of capacity)** → `OUT_OF_CAPACITY`: transient, bounded AIMD backoff (NOT a day park).
- Bare 429 with no code → treated as transient capacity (bounded backoff), never a day-long park.
- Six lanes = six ISOLATED limiter families (`cloudflare_acct_1..6`) — usage never combined globally.

## URL correctness
`url_template` = `…/accounts/{account_id}/ai`; the client appends `/v1/chat/completions` → final
`…/accounts/<id>/ai/v1/chat/completions` (path exactly once). Contract-tested
(`test_final_cloudflare_openai_url_is_correct`); no `…/ai/v1/v1/…` or doubled suffix.

## Integration fix
Cloudflare returns **HTTP 400** for the LOCAL-only `/infer_batch` route (others 404), so the
batched-extraction pre-flight fell through instead of falling back. `_infer_batch_call` now
treats 400/404/405 alike as "no batch endpoint → per-neighborhood `/v1/chat/completions`".
(Residual: the cloud path still spends one 400 pre-flight per batch before falling back — a
follow-up could skip `/infer_batch` for cloud lanes entirely.)

## Final architecture
```
GRAPH EXTRACTION   existing local/gemini/openrouter/nvidia/siliconflow ring  +  cloudflare1..4 (thinking ON)
DOCUMENT PROFILE   profile_groq1 + profile_fallback_openrouter               +  cloudflare_summary1..2 (/no_think)
PARENT-MAP         UNCHANGED
```

## Residual risks
1. **Sample size n=3** per contract — the schema/compiler PASS is unambiguous, but yield-parity
   vs the primary is not established. Recommend a broader confirmation (≥20 docs) before leaning on
   these lanes for volume.
2. **5/6 lanes parked** — only cloudflare2 has an account id; the rest activate when their
   `CLOUDFLARE_ACCOUNT_ID_n` is set.
3. **Parked in the commit (`enabled:false`), verdict PROMOTE.** `cloud_providers.json` is read LIVE but
   `client.py` loads at boot — enabling now would make the running OLD-code fleet route to cloudflare2 and fail
   the unhandled 400 until a bounce. So activation is a COORDINATED step: flip `enabled:true` AND run
   `scripts/boot_polymath.sh` together (the files are not bundle members, so the fleet is not quarantined meanwhile).
4. **Free-tier neurons** — thinking-on extraction spends more reasoning tokens against the daily
   free allocation; the 3036 park handles exhaustion, but per-day request counts will be modest.
