# unit: shared/polymath_shared/acquisition/opencli.py
anchor: shared/polymath_shared/acquisition/opencli.py:1-447

## purpose
OpenCLI backend of research acquisition (AUTORESEARCH-SOURCES-AND-HARNESS-V1 slice R8): reads web-search results, page comments (TikTok/Instagram/YouTube/Reddit) and marketplace listing cards (Alibaba/CJ/Amazon) through the host's separately installed OpenCLI tool and the owner's browser — shared/polymath_shared/acquisition/opencli.py:1-5 [DERIVED].
Only read-only site commands and read-only in-page scripts are used; sign-in walls and human-verification pages are reported as `state`, never worked around, and the comment/like/follow/post/purchase commands OpenCLI also has are never called — shared/polymath_shared/acquisition/opencli.py:6-14 [DERIVED].
Sole importer: `shared/polymath_shared/acquisition/service.py` (FACTS.importers).

## public surface
| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `OpenCLIBackend` | class | `(binary: str \| None = None)`; `status() -> dict[str, Any]`; `read(target: Target, limit: int) -> dict[str, Any]` | shared/polymath_shared/acquisition/opencli.py:131-446 | service.py |
| `CommandFailed` | class (subprocess.SubprocessError) | `(returncode: int, stderr: str)`; attrs `.message: str`, `.state: str` | shared/polymath_shared/acquisition/opencli.py:102-117 | service.py |
| `Disabled` | class | `(note: str)`; `status() -> dict`; `read(target, limit) -> dict` | shared/polymath_shared/acquisition/opencli.py:120-128 | service.py |
| `blocked` | def | `(state: dict[str, Any], *, read_nothing: bool = False) -> str \| None` (`"human_check"` / `"sign_in"` / None); pure | shared/polymath_shared/acquisition/opencli.py:64-80 | service.py |
| `READ_TIMEOUT_S` | constant | `75` | shared/polymath_shared/acquisition/opencli.py:34 | — |
| `WALL_WORDS` | constant | `("human verification", "not a robot", "captcha")` | shared/polymath_shared/acquisition/opencli.py:61 | — |
| `LOGIN_PROMPT` | constant | regex `^\s*(?:log in to tiktok\|log in to continue\|sign in to continue)\s*[.!]?\s*$` | shared/polymath_shared/acquisition/opencli.py:91 | — |

## contracts
`OpenCLIBackend.read(target, limit)` — shared/polymath_shared/acquisition/opencli.py:196-206
- in: `target.reader` names a method `_ + target.reader` on the backend (`getattr`), `limit: int` — shared/polymath_shared/acquisition/opencli.py:197 [DERIVED]
- pre: reader methods exist per site: `_web_search`, `_tiktok_comments`, `_instagram_comments`, `_youtube_comments`, `_reddit_comments`, `_alibaba_listings`, `_cj_listings`, `_amazon_listings` — shared/polymath_shared/acquisition/opencli.py:221, 231, 263, 300, 343, 390, 406, 422 [DERIVED]
- out: dict always containing `state` and `retrieved_at` (from `now_iso()`); `state` ∈ {"ok", "unavailable", "human_check", "sign_in"} — shared/polymath_shared/acquisition/opencli.py:199-206, 229, 242, 257-258 [DERIVED]
- post: runs under `_SLOTS` (BoundedSemaphore, default 2); unknown reader -> `{"state": "unavailable", "note": f"no reader for {target.reader}"}` — shared/polymath_shared/acquisition/opencli.py:200, 198-199 [DERIVED]
- post: every successful comment read carries `page_published_at` (the page's own date); an item with no own date is dated by it, never by read time — shared/polymath_shared/acquisition/opencli.py:10-11, 258, 296, 341, 362 [DERIVED]

`OpenCLIBackend.status()` — shared/polymath_shared/acquisition/opencli.py:186-194
- out: `{"backend": "opencli", "available": bool, "note": str}`; `available` requires both `Daemon: running` and `Extension: connected` in `opencli doctor` output (timeout 25) — shared/polymath_shared/acquisition/opencli.py:190-194 [DERIVED]
- binary resolution order: `binary` arg -> env `POLYMATH_ACQUISITION_OPENCLI` -> `shutil.which("opencli")` -> `"/opt/homebrew/bin/opencli"` — shared/polymath_shared/acquisition/opencli.py:133 [DERIVED]

`blocked(state, *, read_nothing=False)` — shared/polymath_shared/acquisition/opencli.py:64-80
- in: dict keys read: `url`, `login_prompt`, `wall`, `content`, `title`, `text` — shared/polymath_shared/acquisition/opencli.py:70-78 [DERIVED]
- out precedence: `_HUMAN_CHECK_ROUTE` (`/captcha...` or `/egg/cj/validation.html$`) -> `"human_check"`; `_SIGN_IN_ROUTE` (`/(?:accounts/)?login...`) or `login_prompt` or (`wall` and not `content`) -> `"sign_in"`; only when `read_nothing`: a `WALL_WORDS` hit in title+text or `looks_like_challenge(...)` -> `"human_check"`; else None — shared/polymath_shared/acquisition/opencli.py:57-58, 73-79 [DERIVED]

`CommandFailed.__init__(returncode, stderr)` — shared/polymath_shared/acquisition/opencli.py:108-117
- in: OpenCLI's YAML error envelope on stderr (`error.message`, `error.help`); fallback message = first 200 chars of stderr or `f"exit status {returncode}"` — shared/polymath_shared/acquisition/opencli.py:110-115 [DERIVED]
- post: `.state = "human_check"` if message matches `HUMAN_CHECK = re.compile(r"robot check|captcha|human verification", re.IGNORECASE)`, else `"unavailable"` — shared/polymath_shared/acquisition/opencli.py:106, 117 [DERIVED]

`Disabled.read` — returns `{"state": "unavailable", "note": note, "retrieved_at": now_iso()}`; `limit` ignored — shared/polymath_shared/acquisition/opencli.py:127-128 [DERIVED]

Reader result shape (cross-reader contract): `records` items carry `kind` ("comment"/"caption"/"post"/"listing"), `ref`, `text`, `published_at`, `precision` ("exact"/"relative"/"none"); listings add `url` and nested `listing` — shared/polymath_shared/acquisition/opencli.py:252-256, 337-338, 355-358, 378-388, 444 [DERIVED]

## effect surface
- subprocess: `subprocess.run([self.binary, *args], capture_output=True, text=True, timeout, env)` — no shell — shared/polymath_shared/acquisition/opencli.py:143 [DERIVED]. Commands issued: `duckduckgo search <query> --limit N -f json` (shared/polymath_shared/acquisition/opencli.py:223), `amazon search <query> --limit N -f json` (shared/polymath_shared/acquisition/opencli.py:425), `doctor` (shared/polymath_shared/acquisition/opencli.py:190), `browser <session> open <url> --window background` (shared/polymath_shared/acquisition/opencli.py:156), `browser <session> eval <js>` (shared/polymath_shared/acquisition/opencli.py:160), `browser <session> close` (shared/polymath_shared/acquisition/opencli.py:182).
- network (via the owner's browser tab): TikTok `/api/comment/list/?aid=1988&aweme_id=...` (shared/polymath_shared/acquisition/opencli.py:233), YouTube `/youtubei/v1/next?prettyPrint=false` (shared/polymath_shared/acquisition/opencli.py:311), Reddit `<path>.json?limit=N&depth=1&raw_json=1` (shared/polymath_shared/acquisition/opencli.py:344), `https://www.alibaba.com/trade/search?SearchText=...` (shared/polymath_shared/acquisition/opencli.py:391), `https://cjdropshipping.com/search/<q>.html` (shared/polymath_shared/acquisition/opencli.py:407), plus target URLs opened per read (shared/polymath_shared/acquisition/opencli.py:240, 267, 321, 349).
- env flags: `POLYMATH_ACQUISITION_OPENCLI` = null (binary override, shared/polymath_shared/acquisition/opencli.py:133); `POLYMATH_ACQUISITION_CONCURRENCY` = '2' (read slots, shared/polymath_shared/acquisition/opencli.py:35); `PATH` = '' (read, then prepended with the binary's real directory and its own directory for the child env, shared/polymath_shared/acquisition/opencli.py:141-142).
- filesystem: `os.path.exists(self.binary)` check only (shared/polymath_shared/acquisition/opencli.py:187). No Postgres tables, no Qdrant collections (FACTS.tables_read / tables_written empty).
- sleeps: `time.sleep(settle)` after each tab open (shared/polymath_shared/acquisition/opencli.py:157).

## invariants
INVARIANT: concurrent `read` calls <= 2 (env `POLYMATH_ACQUISITION_CONCURRENCY` default `"2"`, floored at 1) — shared/polymath_shared/acquisition/opencli.py:35, 200 [DERIVED]
  fails-if: the owner's browser gets more simultaneous tabs/commands than promised (shared/polymath_shared/acquisition/opencli.py:12)
INVARIANT: read subprocess timeout = 75 s (`READ_TIMEOUT_S`); `doctor` = 25 s; `browser close` = 20 s — shared/polymath_shared/acquisition/opencli.py:34, 136, 190, 182 [DERIVED]
  fails-if: a hung bridge stacks reads past 75 s each; close hangs block `_in_tab` cleanup
INVARIANT: every `read` return contains `state` and `retrieved_at`; `state` domain = {"ok", "unavailable", "human_check", "sign_in"} — shared/polymath_shared/acquisition/opencli.py:196-206, 83-85, 117 [DERIVED]
  fails-if: callers in service.py can no longer branch on wall vs failure
INVARIANT: blocked() precedence: human_check route > sign_in (route / login_prompt / wall-without-content) > wall words (only when read_nothing) — shared/polymath_shared/acquisition/opencli.py:73-79 [DERIVED]
  fails-if: a captcha page is misreported as `sign_in`, or a thread *about* captchas is reported as `human_check`
INVARIANT: `_in_tab` closes its browser session on every path (try/finally) — shared/polymath_shared/acquisition/opencli.py:208-218 [DERIVED]
  fails-if: background tabs leak in the owner's browser
INVARIANT: duckduckgo limit <= 10 (`min(limit, 10)`) — shared/polymath_shared/acquisition/opencli.py:223 [DERIVED]
  fails-if: search command rejects/errors on oversized limit
INVARIANT: Amazon record kept only if ASIN matches `[A-Z0-9]{10}` and is deduped by ASIN — shared/polymath_shared/acquisition/opencli.py:433-435 [DERIVED]
  fails-if: a sponsored slot repeats an organic listing and inflates the record set
INVARIANT: page text captured <= 600 chars, listing card text <= 600, stored card <= 300, Instagram block <= 900 — shared/polymath_shared/acquisition/opencli.py:173, 366, 385, 266 [DERIVED]
  fails-if: oversized payloads change wall-detection and card-parsing behavior
INVARIANT: session id = `"pm-acq-" + uuid.uuid4().hex[:10]` — shared/polymath_shared/acquisition/opencli.py:178 [DERIVED]
  fails-if: session collision reuses/closes another read's tab

## determinism & idempotency
determinism: NONDETERMINISTIC (subprocess `subprocess.run` shared/polymath_shared/acquisition/opencli.py:143; `uuid.uuid4` shared/polymath_shared/acquisition/opencli.py:178; wall clock via `now_iso()` in every result e.g. shared/polymath_shared/acquisition/opencli.py:202, 423; network through the host browser shared/polymath_shared/acquisition/opencli.py:156, 160; sleeps shared/polymath_shared/acquisition/opencli.py:157; env flags shared/polymath_shared/acquisition/opencli.py:35, 133)
idempotency: SAFE (only read commands with fixed arguments, never through a shell; every tab closed in `finally`; no tables written — shared/polymath_shared/acquisition/opencli.py:6-7, 14, 208-218)

## failure behaviour
- `read` converts `subprocess.TimeoutExpired` -> `{"state": "unavailable", "note": "the host browser did not answer in time"}`; `subprocess.SubprocessError`/`OSError` -> `{"state": "unavailable", "note": f"the browser bridge failed: {str(exc)[:160]}"}` — shared/polymath_shared/acquisition/opencli.py:203-206 [DERIVED]
- `CommandFailed` raised by `_run(check=True)` (shared/polymath_shared/acquisition/opencli.py:144-145); caught locally by `_web_search` (always -> "unavailable", "never a human action") and `_amazon_listings` (preserves `exc.state`) — shared/polymath_shared/acquisition/opencli.py:224-225, 426-427 [DERIVED]
- `_close` swallows `subprocess.SubprocessError, OSError` (`pass`) — close failures invisible — shared/polymath_shared/acquisition/opencli.py:180-184 [DERIVED]
- `_json` returns None on `json.JSONDecodeError` (shared/polymath_shared/acquisition/opencli.py:151-153); `_eval` returns the raw string on decode failure (shared/polymath_shared/acquisition/opencli.py:162-170); readers then isinstance-check — shared/polymath_shared/acquisition/opencli.py:226-227, 244, 324 [DERIVED]
- `status` swallows subprocess/OS errors -> `{"available": False, "note": f"doctor failed: {str(exc)[:120]}"}` — shared/polymath_shared/acquisition/opencli.py:189-192 [DERIVED]
- walls are in-band states, not exceptions: readers return `state` from `blocked(page)` before parsing — shared/polymath_shared/acquisition/opencli.py:241-242, 268-269, 293, 322-323, 350-351, 393-394, 409-410 [DERIVED]
- unparsed-but-200 answers are "no answer": TikTok (shared/polymath_shared/acquisition/opencli.py:243-248), YouTube 200 with unparsed body / missing comment section / threads without text (shared/polymath_shared/acquisition/opencli.py:330-336) — never an empty "complete" read [DERIVED]

## dumb-code flags
- Per-site settle magic numbers: TikTok 4.0, Instagram 5.0, YouTube 5.0, Reddit 3.0, Alibaba 5.0, CJ 6.0 — shared/polymath_shared/acquisition/opencli.py:240, 267, 321, 349, 392, 408 [DERIVED]
- `min(limit, 10)` caps duckduckgo but the amazon `--limit str(limit)` is uncapped — shared/polymath_shared/acquisition/opencli.py:223 vs 425 [DERIVED]
- Triple default in `_SLOTS`: `os.environ.get("POLYMATH_ACQUISITION_CONCURRENCY", "2") or 2` inside `max(1, ...)` — the `or 2` only fires on empty-string env — shared/polymath_shared/acquisition/opencli.py:35 [DERIVED]
- Wall vocabulary duplicated: `"captcha"` and `"human verification"` appear both in `WALL_WORDS` and in `CommandFailed.HUMAN_CHECK` — shared/polymath_shared/acquisition/opencli.py:61 vs 106 [DERIVED]
- `_NOISE` filters any stdout *line containing* `"Update available"` or `"npm install"` — substring match can drop a legit result line — shared/polymath_shared/acquisition/opencli.py:36, 146 [DERIVED]
- `_page` builds its JS by `%`-interpolating `LOGIN_PROMPT` straight into a regex literal `/%s/im` — no escaping — shared/polymath_shared/acquisition/opencli.py:173-174 [DERIVED]
- `Disabled.read(target, limit)` ignores `limit` — shared/polymath_shared/acquisition/opencli.py:127 [DERIVED]

## refactor notes
- Reader dispatch is by attribute name: `getattr(self, "_" + target.reader)` — every `Target.reader` string used by service.py must keep matching a `_x` method, else reads degrade to `"no reader for ..."` — shared/polymath_shared/acquisition/opencli.py:197-199 [DERIVED]
- The result dict shape (`state`, `records`, `total`, `complete`, `page_published_at`, `retrieved_at`, `notes`) is the contract consumed by the importer service.py across all readers — shared/polymath_shared/acquisition/opencli.py:228-229, 257-258, 295-298, 340-341, 361-362, 445-446 [DERIVED]
- `blocked` is pure and "tested on recorded page states"; WALL_WORDS, the two route regexes and LOGIN_PROMPT jointly define every reader's wall detection — change them and every site's `state` output shifts — shared/polymath_shared/acquisition/opencli.py:57-61, 64-68, 91 [DERIVED]
- A new reader using `_json` must catch `CommandFailed` itself to preserve `"human_check"`; `read`'s generic handler flattens it to `"unavailable"` — shared/polymath_shared/acquisition/opencli.py:205-206, 426-427 [INFERRED: only `_web_search`/`_amazon_listings` call `_json` today, both catch locally]
- Binary fallback `"/opt/homebrew/bin/opencli"` is host-specific (Homebrew); the child-env PATH prepend assumes OpenCLI is a Node program needing `node` beside it — shared/polymath_shared/acquisition/opencli.py:133, 139-142 [DERIVED]
- `_SLOTS` is process-global: multi-process fleets each get their own cap of 2 — shared/polymath_shared/acquisition/opencli.py:35 [INFERRED: module-level semaphore, no cross-process lock visible]

## VERIFY
```verify
grep -Fq 'READ_TIMEOUT_S = 75' shared/polymath_shared/acquisition/opencli.py
grep -Fq '"/opt/homebrew/bin/opencli"' shared/polymath_shared/acquisition/opencli.py
grep -Fq 'POLYMATH_ACQUISITION_CONCURRENCY' shared/polymath_shared/acquisition/opencli.py
grep -Fq '[A-Z0-9]{10}' shared/polymath_shared/acquisition/opencli.py
grep -Fq '"pm-acq-" + uuid.uuid4().hex[:10]' shared/polymath_shared/acquisition/opencli.py
grep -Fq 'min(limit, 10)' shared/polymath_shared/acquisition/opencli.py
! grep -Fq 'shell=True' shared/polymath_shared/acquisition/opencli.py
```
