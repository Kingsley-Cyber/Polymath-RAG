# unit: shared/polymath_shared/acquisition/challenge.py
anchor: shared/polymath_shared/acquisition/challenge.py:1-206

## purpose
Classifies whether a text is a verification wall (CAPTCHA, slider, "verify you are human", unusual-traffic notice, bot block) rather than content, and names the wall kind — shared/polymath_shared/acquisition/challenge.py:1-29. Used by the research-acquisition read paths (`opencli.blocked`, `service.shape`, the search-engine listing reader) and the receipt check (`adapter.transitions.validate_receipt`, refusal code CHALLENGE_PAGE_AS_EVIDENCE) so a wall never becomes evidence — shared/polymath_shared/acquisition/challenge.py:5-9. A detector only, never a solver; pure, no I/O — shared/polymath_shared/acquisition/challenge.py:2-3, shared/polymath_shared/acquisition/challenge.py:29.

## public surface
| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `wall_route` | def | (url: str \| None) -> bool | shared/polymath_shared/acquisition/challenge.py:111-117 | opencli.py, service.py, transitions.py (module importers) |
| `segments` | def | (text: str \| None) -> list[str] | shared/polymath_shared/acquisition/challenge.py:146-155 | opencli.py, service.py, transitions.py (module importers) |
| `looks_like_challenge` | def | (text: str \| None) -> str \| None | shared/polymath_shared/acquisition/challenge.py:171-206 | opencli.py, service.py, transitions.py (module importers) |

Importers: shared/polymath_shared/acquisition/opencli.py, shared/polymath_shared/acquisition/service.py, shared/polymath_shared/adapter/transitions.py (FACTS.importers; call sites named at shared/polymath_shared/acquisition/challenge.py:5-9).

## contracts
`wall_route(url)` — shared/polymath_shared/acquisition/challenge.py:111-117
- in: `url` str or None; coerced via `str(url or "").strip()` — shared/polymath_shared/acquisition/challenge.py:114.
- out: True iff the urlsplit `path` (lowercased) is non-empty and matches `WALL_ROUTE` from its start — shared/polymath_shared/acquisition/challenge.py:114-117.
- pre: none; `urlsplit` ValueError is swallowed → False — shared/polymath_shared/acquisition/challenge.py:114-116.
- post: `WALL_ROUTE = /captcha(?:[/.]|$) | /egg/cj/validation\.html$` — shared/polymath_shared/acquisition/challenge.py:99.

`segments(text)` — shared/polymath_shared/acquisition/challenge.py:146-155
- in: any str or None.
- out: non-empty segments after NFKC, curly-apostrophe translate, `_SPLIT` split, whitespace collapse, `_TRIM` strip — shared/polymath_shared/acquisition/challenge.py:149-155.
- pre/post: pure string transform; `_SPLIT` cuts at line breaks, sentence end + space, CJK marks, " | " separators — shared/polymath_shared/acquisition/challenge.py:43.

`looks_like_challenge(text)` — shared/polymath_shared/acquisition/challenge.py:171-206
- in: any str or None.
- out: one of "slider check", "unusual-traffic notice", "human check", "robot check", "browser check", "block page", "security check", "captcha", "access denied beside a bot notice", "安全验证 (security verification)", "verification page route", or None for content/empty — shared/polymath_shared/acquisition/challenge.py:172-175.
- pre: none.
- post, in order:
  1. reader-framing URL line (`URL:`, `URL Source:`, `Final URL:`) whose path is a wall route → "verification page route" — shared/polymath_shared/acquisition/challenge.py:129-130, shared/polymath_shared/acquisition/challenge.py:177-178.
  2. page `Title:` matching `_WALL_TITLE` ("Human verification", "Captcha Interception") counts as a strong "human check" line — shared/polymath_shared/acquisition/challenge.py:101, shared/polymath_shared/acquisition/challenge.py:184-187.
  3. content budget: more than 3 non-wall segments or more than 200 content characters → None — shared/polymath_shared/acquisition/challenge.py:37, shared/polymath_shared/acquisition/challenge.py:198-199.
  4. any strong line → its label (first wins) — shared/polymath_shared/acquisition/challenge.py:200-201.
  5. "Access denied" (or 访问被拒绝/訪問被拒絕) only counts beside a `_BOT_NOTICE` match somewhere in `segs` — shared/polymath_shared/acquisition/challenge.py:137-139, shared/polymath_shared/acquisition/challenge.py:202-203.
  6. at least 2 weak lines needed for a weak-only wall — shared/polymath_shared/acquisition/challenge.py:204-205.
- framing lines (Title/URL/Published/Author/Highlights/Markdown Content/Warning) and markdown images/links/bold are stripped before segmentation — shared/polymath_shared/acquisition/challenge.py:103-104, shared/polymath_shared/acquisition/challenge.py:132-134.

## effect surface
- None. No tables read/written (FACTS.tables_read/tables_written empty); docstring states "Pure: no I/O." — shared/polymath_shared/acquisition/challenge.py:29. Imports only `re`, `unicodedata`, `urllib.parse.urlsplit` — shared/polymath_shared/acquisition/challenge.py:32-34.

## invariants
INVARIANT: CONTENT_SEGMENTS_MAX = 3 and CONTENT_CHARS_MAX = 200 — shared/polymath_shared/acquisition/challenge.py:37 [DERIVED]
  fails-if: a page with real content plus one wall line is misreported as a wall (or a sparse wall as content).
INVARIANT: CJK_SEGMENT_MAX = 40 — shared/polymath_shared/acquisition/challenge.py:39 [DERIVED]
  fails-if: long CJK sentences containing wall words flip to content, or long CJK content flips to wall.
INVARIANT: len(weak) >= 2 for a weak-only wall — shared/polymath_shared/acquisition/challenge.py:204 [DERIVED]
  fails-if: a content line like "Captcha" alone would flag content as a wall (the B-17 lesson, shared/polymath_shared/acquisition/challenge.py:11-18).
INVARIANT: _STRONG has 18 patterns, _WEAK 6, _FURNITURE 22 — shared/polymath_shared/acquisition/challenge.py:54-76, shared/polymath_shared/acquisition/challenge.py:78-85, shared/polymath_shared/acquisition/challenge.py:87-96 [DERIVED]
  fails-if: silent label-coverage drift between revisions.
INVARIANT: _STRONG/_WEAK/_FURNITURE match with `fullmatch`; `_BOT_NOTICE` with `search` — shared/polymath_shared/acquisition/challenge.py:169-173, shared/polymath_shared/acquisition/challenge.py:196, shared/polymath_shared/acquisition/challenge.py:202 [DERIVED]
  fails-if: a segment merely containing a wall phrase (not being one) would be flagged.
INVARIANT: all _STRONG/_WEAK/_FURNITURE patterns compiled with re.IGNORECASE — shared/polymath_shared/acquisition/challenge.py:49-50 [DERIVED]
  fails-if: case-varied wall lines ("CAPTCHA") stop matching.

## determinism & idempotency
determinism: DETERMINISTIC (pure regex/unicode text transforms; no clock, random, uuid, network, db, env reads — shared/polymath_shared/acquisition/challenge.py:29, shared/polymath_shared/acquisition/challenge.py:32-34)
idempotency: SAFE (stateless functions, no module-level mutable state)

## failure behaviour
- `wall_route` swallows `urlsplit` ValueError and returns False — shared/polymath_shared/acquisition/challenge.py:114-116.
- `looks_like_challenge` never raises for bad input; None/empty text yields None — shared/polymath_shared/acquisition/challenge.py:172-175, shared/polymath_shared/acquisition/challenge.py:176.
- No error codes raised in this module; the refusal code CHALLENGE_PAGE_AS_EVIDENCE lives in the caller `adapter.transitions.validate_receipt` — shared/polymath_shared/acquisition/challenge.py:8-9.

## dumb-code flags
- URL labels appear twice: in the `_FRAMING` alternation (`url\s+source|final\s+url|url`) and again in `_URL_LABELS = frozenset({"url", "url source", "final url"})` — shared/polymath_shared/acquisition/challenge.py:103, shared/polymath_shared/acquisition/challenge.py:105. Two places to keep in sync.
- Title normalization at shared/polymath_shared/acquisition/challenge.py:185 skips the `_APOSTROPHES` translate that `segments` applies at shared/polymath_shared/acquisition/challenge.py:149 — a curly apostrophe in a `Title:` line is normalized differently [INFERRED: visible difference in the two code paths; only matters if a wall title ever tests _WALL_TITLE with curly quotes, which it currently does not].
- Magic numbers 3, 200 (shared/polymath_shared/acquisition/challenge.py:37) and 40 (shared/polymath_shared/acquisition/challenge.py:39) as bare literals.
- `_rx` is a one-line wrapper around `re.compile(pattern, re.IGNORECASE)` — shared/polymath_shared/acquisition/challenge.py:49-50.
- `_WALL_TITLE` knows exactly two titles — shared/polymath_shared/acquisition/challenge.py:101.
- Return value is `strong[0]` / `weak[0]`, so the tuple ordering of `_STRONG` decides which label a multi-signal wall reports — shared/polymath_shared/acquisition/challenge.py:201, shared/polymath_shared/acquisition/challenge.py:205 [INFERRED: first-match-wins is visible; reordering _STRONG changes the returned label].

## refactor notes
- Three importers depend on this module (opencli.py, service.py, transitions.py, per FACTS.importers); renaming `looks_like_challenge`, `wall_route` or `segments` breaks them. Docstring names the exact call sites `opencli.blocked`, `service.shape`, `adapter.transitions.validate_receipt` — shared/polymath_shared/acquisition/challenge.py:5-9.
- `WALL_ROUTE` parity: the comment says it is "anchored at its start, as `opencli.blocked` matches it" — shared/polymath_shared/acquisition/challenge.py:97-99. Changing the regex or the anchoring (`.match` at shared/polymath_shared/acquisition/challenge.py:117) desynchronizes the two matchers.
- Adding/removing return labels ripples into callers that map labels to outcomes (HUMAN_ACTION_REQUIRED or exclusion in the read paths; CHALLENGE_PAGE_AS_EVIDENCE in the receipt check) — shared/polymath_shared/acquisition/challenge.py:6-9.
- `_URL_LABELS` must stay a subset of the `_FRAMING` label alternation or framing URL lines stop being recognized — shared/polymath_shared/acquisition/challenge.py:103-105.
- The content budget (3/200) encodes the "content that merely MENTIONS a check is content" rule; loosening it re-introduces the B-17 false positive — shared/polymath_shared/acquisition/challenge.py:11-18, shared/polymath_shared/acquisition/challenge.py:37.

## VERIFY
```verify
grep -Fq 'CONTENT_SEGMENTS_MAX, CONTENT_CHARS_MAX = 3, 200' shared/polymath_shared/acquisition/challenge.py
grep -Fq 'CJK_SEGMENT_MAX = 40' shared/polymath_shared/acquisition/challenge.py
grep -Fq 'WALL_ROUTE = re.compile(r"/captcha(?:[/.]|$)|/egg/cj/validation\.html$")' shared/polymath_shared/acquisition/challenge.py
grep -Eq 'def (looks_like_challenge|wall_route|segments)\(' shared/polymath_shared/acquisition/challenge.py
grep -Fq 'return "verification page route"' shared/polymath_shared/acquisition/challenge.py
test "$(grep -c -F 'slider check' shared/polymath_shared/acquisition/challenge.py)" -ge 2
! grep -Fq 'import requests' shared/polymath_shared/acquisition/challenge.py
```
