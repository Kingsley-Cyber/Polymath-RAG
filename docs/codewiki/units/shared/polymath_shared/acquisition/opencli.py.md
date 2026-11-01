# unit: shared/polymath_shared/acquisition/opencli.py
anchor: shared/polymath_shared/acquisition/opencli.py:1-433

## purpose
The OpenCLI backend of research acquisition (AUTORESEARCH-SOURCES-AND-HARNESS-V1 slice R8). It reads pages through OpenCLI (a separately installed host tool with a browser bridge extension and daemon): web search, comment lists (TikTok, Instagram, YouTube, Reddit), and marketplace listings (CJ, Amazon). Read-only by contract; sign-in walls and human checks are detected and reported as `state`, never worked around. Sole importer: `shared/polymath_shared/acquisition/service.py` (FACTS.importers) — opencli.py:1-16 [DERIVED], opencli.py:149-150 of FACTS.

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `OpenCLIBackend` | class | `(binary: str \| None = None)` | opencli.py:133-432 | service.py (module importer) [DERIVED] |
| `OpenCLIBackend.read` | method | `(target: Target, limit: int) -> dict[str, Any]` | opencli.py:198-208 | — |
| `OpenCLIBackend.status` | method | `() -> dict[str, Any]` | opencli.py:188-196 | — |
| `Disabled` | class | `(note: str)`, `status()`, `read(target, limit)` | opencli.py:122-130 | — |
| `CommandFailed` | class | `(returncode: int, stderr: str)`, subclass of `subprocess.SubprocessError` | opencli.py:104-119 | — |
| `blocked` | function | `(state: dict, *, read_nothing: bool = False) -> str \| None` | opencli.py:66-82 | — |

## contracts

**`blocked(state, read_nothing=False)`** — opencli.py:66-82 [DERIVED]
- in: a page-state dict with keys `url`, `title`, `text`, `login_prompt`, `wall`, `content`.
- out: `"human_check"`, `"sign_in"`, or `None`.
- post: path matching `_HUMAN_CHECK_ROUTE` (= `WALL_ROUTE` from challenge.py) -> `"human_check"` (:75-76); `_SIGN_IN_ROUTE` OR `login_prompt` OR (`wall` and not `content`) -> `"sign_in"` (:77-78); with `read_nothing=True`, any of `WALL_WORDS` in title+text OR `looks_like_challenge(...)` -> `"human_check"` (:79-81).

**`OpenCLIBackend.read(target, limit)`** — opencli.py:198-208 [DERIVED]
- in: a `Target` (from service.py), an int limit.
- out: dict with `state` (`"ok"` / `"unavailable"` / `"sign_in"` / `"human_check"`), `retrieved_at` (`now_iso()`), and on success `records`.
- pre: dispatch resolves `getattr(self, "_" + target.reader)`; missing reader -> `{"state": "unavailable", "note": f"no reader for {target.reader}"}` (:199-201).
- post: runs under `_SLOTS`; `TimeoutExpired` and `SubprocessError`/`OSError` are converted to `state="unavailable"` (:205-208).

**`OpenCLIBackend.status()`** — opencli.py:188-196 [DERIVED]
- out: `{"backend": "opencli", "available": bool, "note": str}`; `available` requires both `Daemon: running` and `Extension: connected` in `doctor` output (:195).

**`CommandFailed(returncode, stderr)`** — opencli.py:104-119 [DERIVED]
- in: exit code plus OpenCLI's YAML error envelope on stderr (`error.message`, `error.help`).
- out: `.message` (envelope message, else stderr[:200], else `f"exit status {returncode}"`), `.state` = `"human_check"` if regex `robot check|captcha|human verification` (IGNORECASE) matches, else `"unavailable"` (:108, :117-119).

**`Disabled.read`** ignores `target`/`limit`, returns `{"state": "unavailable", "note": ..., "retrieved_at": ...}` — opencli.py:129-130 [DERIVED].

## effect surface
- subprocess: `subprocess.run([self.binary, *args], ...)` — no shell (`# noqa: S603`), commands `browser <session> open|eval|close`, `duckduckgo search`, `amazon search`, `doctor` — opencli.py:145, :158, :174, :183, :192, :225, :411 [DERIVED]
- in-page network via the tab's own `fetch`: TikTok `/api/comment/list/?aid=1988&aweme_id=...`, YouTube `/youtubei/v1/next?prettyPrint=false`, Reddit `<path>.json?limit=...&depth=1&raw_json=1` — opencli.py:235, :313, :346 [DERIVED]
- env read: `POLYMATH_ACQUISITION_OPENCLI` (default `null` -> which -> `/opt/homebrew/bin/opencli`) :135; `POLYMATH_ACQUISITION_CONCURRENCY` (default `"2"`) :37; child `PATH` extended with the binary's directory :143-144 [DERIVED]
- uuid: session id `"pm-acq-" + uuid.uuid4().hex[:10]` — opencli.py:180 [DERIVED]
- Postgres tables: none; Qdrant: none; files: none (FACTS.tables_read/tables_written empty) [DERIVED]

## invariants
INVARIANT: default read timeout = `READ_TIMEOUT_S = 75` seconds — opencli.py:36 [DERIVED]
  fails-if: `_run` default changes and a slow host browser gets cut off early/late.
INVARIANT: max concurrent reads = `max(1, int(POLYMATH_ACQUISITION_CONCURRENCY or 2))` via `threading.BoundedSemaphore` — opencli.py:37 [DERIVED]
  fails-if: owner's browser flooded; semaphore over-/under-release changes parallelism.
INVARIANT: binary resolution order = arg -> `POLYMATH_ACQUISITION_OPENCLI` -> `shutil.which("opencli")` -> `"/opt/homebrew/bin/opencli"` — opencli.py:135 [DERIVED]
  fails-if: reordering silently picks a different OpenCLI install.
INVARIANT: every `_in_tab` closes its session in `finally` — opencli.py:219-220 [DERIVED]
  fails-if: background tabs leak in the owner's browser.
INVARIANT: every comment reader returns `page_published_at`; an undated item is dated by it, never by read time — opencli.py:10-11, :260, :298, :328, :364 [DERIVED]
  fails-if: items get backdated/forward-dated to the acquisition moment.
INVARIANT: DuckDuckGo limit = `min(limit, 10)` — opencli.py:225 [DERIVED]
  fails-if: caller passes a larger limit and expects more than 10 rows.
INVARIANT: Amazon ASIN must fullmatch `[A-Z0-9]{10}`; canonical URL `https://www.amazon.com/dp/{asin}` — opencli.py:419, :422 [DERIVED]
  fails-if: non-listing rows or duplicate (sponsored) slots enter records.
INVARIANT: alibaba.com is never read here; its search is handed to Agent Reach by `service.acquire` — opencli.py:14-16 [DERIVED]
  fails-if: violates the owner's PRODUCT-SEARCH-E2E rule "alibaba is strictly agent reach".
INVARIANT: write commands (comment, like, follow, post, purchase) are never called — opencli.py:13-14 [DERIVED]
  fails-if: backend performs actions instead of reads.

## determinism & idempotency
determinism: NONDETERMINISTIC (subprocess/network: OpenCLI daemon + live pages, opencli.py:145; uuid session ids, opencli.py:180; env flags, opencli.py:37, :135) [DERIVED]
idempotency: SAFE (read-only commands and fresh per-read sessions, always closed; no DB/file writes) — opencli.py:6-13, :219-220 [INFERRED: only read paths exist in SOURCE]

## failure behaviour
- `read()` catches `subprocess.TimeoutExpired` -> `{"state": "unavailable", "note": "the host browser did not answer in time"}`; `SubprocessError`/`OSError` -> unavailable with `str(exc)[:160]` — opencli.py:205-208 [DERIVED]
- `_run(check=True)` raises `CommandFailed(returncode, stderr)` on non-zero exit — opencli.py:146-147 [DERIVED]
- `CommandFailed` swallows YAML/attribute errors on stderr -> empty envelope `{}` — opencli.py:111-114 [DERIVED]
- `_close` swallows `SubprocessError`/`OSError` entirely — opencli.py:183-186 [DERIVED]
- `_json`/`_eval` return `None`/raw string on `json.JSONDecodeError` — opencli.py:153-155, :162-171 [DERIVED]
- `status()` reports `available: False` when binary missing or `doctor` fails (`"doctor failed: {str(exc)[:120]}"`) — opencli.py:189-194 [DERIVED]
- Amazon `CommandFailed` -> `state = exc.state` (so "amazon search hit a robot check" surfaces as `human_check`, never worked around) — opencli.py:412-413 [DERIVED]
- Wall pages return the wall reason as `state` with no records — e.g. opencli.py:243-244, :270-271, :352-353 [DERIVED]

## dumb-code flags
- Per-reader settle magic numbers: `4.0` TikTok :242, `5.0` Instagram :269, `5.0` YouTube :323, `3.0` Reddit :351, `6.0` CJ :394 — no shared constant [DERIVED]
- Hardcoded TikTok app id `aid=1988` — opencli.py:235 [DERIVED]
- `_NOISE` line filter literals `("Update available", "npm install")` applied to all stdout — opencli.py:38, :148 [DERIVED]
- `LOGIN_PROMPT` regex spliced into JS via `%s` string formatting — opencli.py:176, :93 [DERIVED]
- Truncation magic numbers: page text `600` :175, Instagram block `900` :268, card `600`/`300` :368/:377, stderr fallback `[:200]` :117, error note `[:160]`/`[:120]` :208/:194 [DERIVED]
- `_nothing` name vs meaning: returns a wall state or `"unavailable"`, not "nothing" — opencli.py:85-87 [DERIVED]
- `CommandFailed.__init__` assigns `self.message` twice (envelope then fallback) — opencli.py:115, :117 [DERIVED]
- OpenCLI's own YouTube command (300-char cut, no has_more) duplicated as the reason this reader reimplements it — opencli.py:8-9, :303-304 [DERIVED]

## refactor notes
- Sole importer is `shared/polymath_shared/acquisition/service.py`; `Target` and `now_iso` are imported *from* service into this module — changing either module's shapes breaks the other — opencli.py:34, FACTS.importers [DERIVED]
- Reader dispatch is by string name `"_" + target.reader` — renaming `_web_search`/`_tiktok_comments`/`_instagram_comments`/`_youtube_comments`/`_reddit_comments`/`_cj_listings`/`_amazon_listings` silently breaks `read()` into "no reader" — opencli.py:199-201 [DERIVED]
- `_HUMAN_CHECK_ROUTE = WALL_ROUTE` is deliberately one definition shared by browser, parser and receipt check (challenge.py) — opencli.py:60 [DERIVED]
- TikTok takes the video id positionally as `t.ident[1]` — opencli.py:234 [DERIVED]
- `_SLOTS` is module-global and shared across all `OpenCLIBackend` instances — opencli.py:37 [DERIVED]

## VERIFY
```verify
grep -Fq 'READ_TIMEOUT_S = 75' shared/polymath_shared/acquisition/opencli.py
grep -Fq '"human verification", "not a robot", "captcha"' shared/polymath_shared/acquisition/opencli.py
grep -Fq '/opt/homebrew/bin/opencli' shared/polymath_shared/acquisition/opencli.py
grep -Eq 'robot check|captcha|human verification' shared/polymath_shared/acquisition/opencli.py
grep -Fq 'pm-acq-' shared/polymath_shared/acquisition/opencli.py
test "$(grep -c -F '_in_tab' shared/polymath_shared/acquisition/opencli.py)" -ge 5
```
