# unit: shared/polymath_shared/acquisition/_small-modules
anchor: shared/polymath_shared/acquisition/__init__.py:1-7

## purpose
Research-acquisition package: Polymath reads permitted web pages FOR a connected harness (AUTORESEARCH-SOURCES-AND-HARNESS-V1, slice R8); `service` holds the contract/policy, `opencli` is the host-browser backend — shared/polymath_shared/acquisition/__init__.py:1-4 [DERIVED].
This unit holds the package docstring, `challenge` (names verification walls, never solves one) and `listing_apis` (supplier official API `cj_api` or SearXNG results `searxng` placed in front of the host browser, fallback said and counted) — shared/polymath_shared/acquisition/__init__.py:4-7 [DERIVED].

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| segments | def | (text: str \| None) -> list[str] | shared/polymath_shared/acquisition/challenge.py:93-102 | — |
| looks_like_challenge | def | (text: str \| None) -> str \| None | shared/polymath_shared/acquisition/challenge.py:118-143 | `opencli.blocked`, `service.shape`, search-engine listing reader, `adapter.transitions.validate_receipt` — shared/polymath_shared/acquisition/challenge.py:5-9 [DERIVED] |
| ApiFailed | class(Exception) | (reason: str, detail: str) | shared/polymath_shared/acquisition/listing_apis.py:24-30 | raised by cj_api/searxng readers, caught at shared/polymath_shared/acquisition/listing_apis.py:72 [INFERRED: both are FACTS.importers and are the only API readers] |
| counts | def | () -> dict[str, dict[str, Any]] | shared/polymath_shared/acquisition/listing_apis.py:47-50 | — |
| ListingAPIs | class | (browser: Backend, apis: Mapping[str, Any]); .status() -> dict[str, Any]; .read(target: Target, limit: int) -> dict[str, Any] | shared/polymath_shared/acquisition/listing_apis.py:53-90 | — |
| configured | def | (env: Mapping[str, str]) -> dict[str, Any] | shared/polymath_shared/acquisition/listing_apis.py:93-103 | `wrap` — shared/polymath_shared/acquisition/listing_apis.py:108 |
| wrap | def | (browser: Backend, env: Mapping[str, str]) -> Backend | shared/polymath_shared/acquisition/listing_apis.py:106-109 | — (package importers include orchestrator/orchestrator/api/acquisition.py — FACTS.importers) |

Package importers (FACTS.importers): orchestrator/orchestrator/api/acquisition.py, cj_api.py, opencli.py, searxng.py, service.py, supplier.py, adapter/transitions.py.

## contracts

**segments(text)** — shared/polymath_shared/acquisition/challenge.py:93-102
- in: any `str | None` (None/empty tolerated, challenge.py:96).
- normalise: NFKC; apostrophes `’ ‘ ʼ ＇` → `'` (challenge.py:29,96).
- split at line breaks, sentence end + space, CJK marks `。！？，；：、`, ` | `-style separators (challenge.py:31); trim chars of `_TRIM` (challenge.py:32,99).
- post: output segments are non-empty and stripped (challenge.py:99-101).

**looks_like_challenge(text)** — shared/polymath_shared/acquisition/challenge.py:118-143
- out: one of `"slider check"`, `"unusual-traffic notice"`, `"human check"`, `"robot check"`, `"browser check"`, `"block page"`, `"security check"`, `"captcha"`, `"access denied beside a bot notice"`, `"安全验证 (security verification)"`, else `None` (challenge.py:118-121).
- rule: one strong wall line (whole-segment `fullmatch`, challenge.py:110,137-138) suffices; `"access denied"` counts only beside a bot notice (challenge.py:84-86,139-140); weak lines need `>= 2` (challenge.py:141-142).
- post: content over budget → `None` even with wall lines present (challenge.py:135-136).
- CJK: strong only when the segment holds a `_CJK_WALL` phrase and `len(seg) <= 40` (challenge.py:27,107-108).

**ApiFailed** — shared/polymath_shared/acquisition/listing_apis.py:24-30
- `reason` ∈ {unreachable, network, auth, quota, rate_limit, bad_request, refused, bad_reply, server, error}; `detail` plain words, never a key or token (listing_apis.py:25-26).

**ListingAPIs.read(target, limit)** — shared/polymath_shared/acquisition/listing_apis.py:66-78
- pre: `self.apis.get(target.reader)` decides routing (listing_apis.py:67); no api → `browser.read(target, limit)` untouched (listing_apis.py:68-69).
- `ApiFailed` → `_fall_back(..., exc.reason, exc.detail)` (listing_apis.py:72-73).
- any other `Exception` → `log.exception` then `_fall_back(..., "error", type(exc).__name__)` (listing_apis.py:74-76).
- post: success increments `api_reads` and returns `raw` as-is, no `backend_notes` added (listing_apis.py:77-78).

**ListingAPIs._fall_back** — shared/polymath_shared/acquisition/listing_apis.py:80-90
- counts one fallback with reason (listing_apis.py:81); `log.warning` with reader/api/reason/fallbacks/api_reads (listing_apis.py:82-83).
- note literal: `f"the {label} could not answer ({reason}: {detail}); the host browser read {target.site} instead"` (listing_apis.py:84).
- post: note prepended to `raw["backend_notes"]`; browser failure yields `{"state": "unavailable", "note": ..., "retrieved_at": now_iso()}` (listing_apis.py:87-89).

**ListingAPIs.status** — shared/polymath_shared/acquisition/listing_apis.py:59-64
- out: browser status plus `"listing_apis"` per reader (sorted): `{"api": label, "api_reads": …, "fallbacks": …, "fallback_reasons": …}` (listing_apis.py:62-63).

**configured(env) / wrap(browser, env)** — shared/polymath_shared/acquisition/listing_apis.py:93-109
- `configured` reads the environment only (listing_apis.py:94); lazy import of `cj_api`, `searxng` (listing_apis.py:95).
- `"cj_listings"` added when `cj_api.client_from_env(env)` is not None (listing_apis.py:97-99); `"alibaba_listings"` when `searxng.base_url(env)` is truthy (listing_apis.py:100-102).
- `wrap`: empty apis → the same browser object; else `ListingAPIs(browser, apis)` (listing_apis.py:108-109).

## effect surface
- Postgres tables: none read/written (FACTS `tables_read`/`tables_written` empty); Qdrant: none shown.
- Network: `api.read(target, limit)` → CJ official API / SearXNG inside `cj_api`/`searxng` (listing_apis.py:71; docstring listing_apis.py:5-6); `browser.read` → host browser bridge (listing_apis.py:69,86; __init__.py:3-4).
- Process state: `_COUNTS` dict guarded by `_COUNT_LOCK` (listing_apis.py:33-34); reset by a process bounce (listing_apis.py:38).
- Env flags: `CJ_API_KEY` (unset → no `cj_listings`) — listing_apis.py:5; `SEARXNG_URL` (value `off` disables) — listing_apis.py:6; parsed inside cj_api/searxng, not here [INFERRED: `configured` only delegates].
- Logs: logger `"polymath.acquisition"` (listing_apis.py:21); `log.exception` (75), `log.warning` (82-83). Keys never reach a log, result or error (listing_apis.py:10-11).
- Files/subprocesses: none.

## invariants
INVARIANT: content budget == 3 segments AND 200 chars — shared/polymath_shared/acquisition/challenge.py:25 [DERIVED]
  fails-if: pages with a wall's words plus more chrome get flagged as walls (or real walls dropped, if tightened).
INVARIANT: strong lines needed == 1, weak lines needed == 2 — shared/polymath_shared/acquisition/challenge.py:137-142 [DERIVED]
  fails-if: one shared line ("Captcha", "I'm not a robot") alone would mark content as a wall (B-17 lesson, challenge.py:11,17).
INVARIANT: CJK wall segment length <= 40 — shared/polymath_shared/acquisition/challenge.py:27,107-108 [DERIVED]
  fails-if: a long CJK sentence that merely mentions verification is counted as a wall prompt.
INVARIANT: strong[0] wins over "access denied beside a bot notice", which wins over weak[0] — shared/polymath_shared/acquisition/challenge.py:137-142 [DERIVED]
  fails-if: a page that is both strong and denied reports the less specific label.
INVARIANT: every `_COUNTS` mutation happens under `_COUNT_LOCK` — shared/polymath_shared/acquisition/listing_apis.py:34,39-44,48-50 [DERIVED]
  fails-if: lost counter updates under concurrent reads.
INVARIANT: `api_reads` increments only when `api.read` returned — shared/polymath_shared/acquisition/listing_apis.py:71-77 [DERIVED]
  fails-if: fallbacks get counted as successful API reads.
INVARIANT: `wrap` with no configured API returns the identical browser object — shared/polymath_shared/acquisition/listing_apis.py:106-109 [DERIVED]
  fails-if: no-API hosts lose the "today's backend, untouched" behaviour promised at listing_apis.py:10.

## determinism & idempotency
determinism: challenge.py DETERMINISTIC ("Pure: no I/O." — challenge.py:18; imports only `re`, `unicodedata` — challenge.py:20-21). listing_apis.py NONDETERMINISTIC (network: listing_apis.py:71,69,86; clock: `now_iso` listing_apis.py:88; env: listing_apis.py:93-103; concurrency: listing_apis.py:33-34).
idempotency: challenge SAFE (no state). listing_apis UNSAFE (every read/fallback mutates `_COUNTS` — listing_apis.py:40-43,81; no other external writes).

## failure behaviour
- listing_apis.py:74 broad `except Exception` (an API reader's own bug): not silent — `log.exception`, then fallback with reason `"error"` and detail `type(exc).__name__`; caller sees the browser result plus a `backend_notes` line (listing_apis.py:74-76) — FACTS.fallbacks.
- listing_apis.py:87 broad `except Exception` (browser failed too): handled by assign — caller sees `state: "unavailable"`, a note with the exception type and first 200 chars, plus the fallback note prepended to `backend_notes` (listing_apis.py:87-89) — FACTS.fallbacks.
- `ApiFailed` from a reader is caught at listing_apis.py:72; its stable one-word `reason` flows into the note and the counters (listing_apis.py:73,81).
- challenge.py raises nothing shown; its failure mode is returning `None` for content (challenge.py:136,143).

## dumb-code flags
- Magic numbers: `3`, `200` (challenge.py:25); `40` (challenge.py:27); `str(exc)[:200]` truncation (listing_apis.py:88) — the two `200`s are numeric coincidence, unrelated meanings.
- Duplicated literal: `{"api_reads": 0, "fallbacks": 0, "fallback_reasons": {}}` at listing_apis.py:40 and 62; same shape rebuilt a third time in `counts()` (listing_apis.py:49).
- Label vocabulary duplicated across `_STRONG` and `_WEAK` ("security check", "human check", "robot check", "browser check", "block page" appear in both) — challenge.py:41-73.
- Lazy import inside `configured` (`from polymath_shared.acquisition import cj_api, searxng`, listing_apis.py:95) breaks an import cycle, since cj_api/searxng import the package [INFERRED: FACTS.importers lists both].
- Dead branches: none visible.

## refactor notes
- The label strings returned by `looks_like_challenge` are an API consumed by `opencli.blocked`, `service.shape`, the search-engine listing reader and `adapter.transitions.validate_receipt` (refusal `CHALLENGE_PAGE_AS_EVIDENCE`) — challenge.py:5-9; renaming a label changes receipt validation.
- Reader keys `"cj_listings"` / `"alibaba_listings"` must keep matching `Target.reader` values — listing_apis.py:67,99,102.
- `backend_notes` entries reach `limitations` "in every state" — listing_apis.py:8-9,89; downstream parses the note format `the {label} could not answer ({reason}: {detail}); the host browser read {site} instead` (listing_apis.py:84).
- `ApiFailed.reason` words become `fallback_reasons` keys and note text (listing_apis.py:81,84); changing the vocabulary breaks count continuity.
- Keys come from the environment only and never reach a log, result or error (listing_apis.py:10-11); any new note/detail field must preserve this.
- `wrap`'s identity return when unconfigured changes `status()` output for every no-API host (`listing_apis` key added at listing_apis.py:62).
- Module moves ripple to all FACTS.importers: orchestrator/orchestrator/api/acquisition.py, service.py, supplier.py, opencli.py, cj_api.py, searxng.py, adapter/transitions.py.

## VERIFY
```verify
grep -Fq 'CONTENT_SEGMENTS_MAX, CONTENT_CHARS_MAX = 3, 200' shared/polymath_shared/acquisition/challenge.py
grep -Fq 'CJK_SEGMENT_MAX = 40' shared/polymath_shared/acquisition/challenge.py
grep -Fq 'if len(weak) >= 2:' shared/polymath_shared/acquisition/challenge.py
grep -Fq 'return self._fall_back(target, limit, api.label, "error", type(exc).__name__)' shared/polymath_shared/acquisition/listing_apis.py
grep -Fq 'apis["alibaba_listings"] = searxng.SearXNGListings(url)' shared/polymath_shared/acquisition/listing_apis.py
grep -Fq '"state": "unavailable"' shared/polymath_shared/acquisition/listing_apis.py
! grep -Fq 'import requests' shared/polymath_shared/acquisition/challenge.py
test "$(grep -c -F 'except Exception' shared/polymath_shared/acquisition/listing_apis.py)" -ge 2
```
