# unit: shared/polymath_shared/gap_check.py
anchor: shared/polymath_shared/gap_check.py:1-494

## purpose
Post-answer safety net for grounded chat turns ("FACET-RETRIEVAL-V1 F6 (register 11.545, plan §3.6)") — after the answer is generated, every sentence claiming a corpus gap (deterministic list `GAP_PATTERNS`) plus every facet the retrieval receipt marked uncovered becomes ONE targeted retrieval through the turn's own `retrieve` — shared/polymath_shared/gap_check.py:1-11 [DERIVED].
Found (≥ 1 passage above floor) → a cited "**More on this.**" addition appended and the gap sentence marked refuted; not found → the claim is rewritten deterministically to "the passages found don't cover X"; never runs on lookups (`eligible`) — shared/polymath_shared/gap_check.py:7-11 [DERIVED].
Pure module: no I/O, no model call — caller passes `retrieve`, `hydrate`, `complete` — shared/polymath_shared/gap_check.py:13 [DERIVED].
Module imported by `orchestrator/orchestrator/api/ui.py` (FACTS.importers).

## public surface
| symbol | kind | signature (params -> return) | anchor | used by |
| enabled | def | (env: Mapping[str, str] \| None = None) -> bool | shared/polymath_shared/gap_check.py:109-111 | — |
| limits | def | () -> dict[str, Any] | shared/polymath_shared/gap_check.py:128-132 | — |
| eligible | def | (plan: Any) -> bool | shared/polymath_shared/gap_check.py:135-146 | — |
| sigmoid | def | (x: float \| None) -> float \| None | shared/polymath_shared/gap_check.py:149-152 | — |
| gap_sentences | def | (text: str) -> list[dict[str, Any]] | shared/polymath_shared/gap_check.py:157-169 | — |
| content_words | def | (text: str) -> list[str] | shared/polymath_shared/gap_check.py:172-182 | — |
| gap_query | def | (sentence: str, *, fallback: str = "", max_words: int = 12) -> str | shared/polymath_shared/gap_check.py:185-195 | — |
| honest_rewrite | def | (sentence: str, *, subject: str = "the passages found", singular: str = "the material found", strong_only: bool = False) -> tuple[str, str \| None] | shared/polymath_shared/gap_check.py:227-265 | — |
| mark_found | def | (sentence: str, tags: Iterable[str]) -> str | shared/polymath_shared/gap_check.py:275-279 | — |
| strip_unknown_tags | def | (text: str, allowed: Iterable[str]) -> tuple[str, int] | shared/polymath_shared/gap_check.py:282-295 | — |
| addition_messages | def | (resolved_request: str, claims: list, passages: list) -> list[dict[str, str]] | shared/polymath_shared/gap_check.py:308-316 | — |
| stub_addition | def | (claims: list[dict[str, Any]]) -> str | shared/polymath_shared/gap_check.py:319-325 | — |
| run_gap_check | def | (text: str, *, resolved_request, legend, retrieve, hydrate=None, complete=None, floor=0.5, facets_uncovered=(), max_claims=None, limit=None, budget_s=None, max_tokens=None, cite_max=CITE_MAX, clock=time.perf_counter) -> dict[str, Any] | shared/polymath_shared/gap_check.py:330-494 | — |

Only importer on record: `orchestrator/orchestrator/api/ui.py` (FACTS.importers); specific symbols used are not recorded.

## contracts

**run_gap_check** — shared/polymath_shared/gap_check.py:330-494
- in: `text` (the answer), `legend` entries must carry `"tag"` (filtered `if e.get("tag")`) — shared/polymath_shared/gap_check.py:352 [DERIVED]; `retrieve(query)` returns final rows `{chunk_id, doc_id, rerank_score}` — shared/polymath_shared/gap_check.py:343 [DERIVED]; `hydrate(row)` returns passage text/presentation or None (skip) — shared/polymath_shared/gap_check.py:343-344 [DERIVED]; `complete(messages, max_tokens)` → str — shared/polymath_shared/gap_check.py:344-345 [DERIVED].
- pre: `None` tunables are filled from `limits()` (env overrides) — shared/polymath_shared/gap_check.py:346-350 [DERIVED].
- out: `{text, legend_added, receipt}` — shared/polymath_shared/gap_check.py:494 [DERIVED]; `receipt` = `meta.gap_check` with keys `{contract, claims, searches, ms, call, section_added, limits, budget_exhausted}` — shared/polymath_shared/gap_check.py:342, shared/polymath_shared/gap_check.py:489-493 [DERIVED]; receipt claims drop the `sentence` and `passages` keys — shared/polymath_shared/gap_check.py:490 [DERIVED].
- post: sentence replaced only via `new_text.replace(c["sentence"], edited, 1)` and only when the sentence is a verbatim substring, else `c["edited"] = None` — shared/polymath_shared/gap_check.py:453-456 [DERIVED]; found-claim sentences get rewrite + `mark_found` pointer — shared/polymath_shared/gap_check.py:445-449 [DERIVED]; unfound get default `honest_rewrite` — shared/polymath_shared/gap_check.py:450-452 [DERIVED]; when anything found, text gains `"\n\n" + "**More on this.**" + " " + body` — shared/polymath_shared/gap_check.py:487 [DERIVED].

**eligible** — shared/polymath_shared/gap_check.py:135-146
- in: a plan object with `retrieval_required`, `task_type`, `facets` (via `getattr`) — shared/polymath_shared/gap_check.py:138-145 [DERIVED].
- out: True for `task_type in ("GROUNDED_SYNTHESIS", "CREATE_FROM_KNOWLEDGE")`; for `"GROUNDED_QA"` only when ≥ 2 facets are Mappings with an `id` — shared/polymath_shared/gap_check.py:141-146 [DERIVED].
- pre: `plan is None` or `retrieval_required` falsy → False — shared/polymath_shared/gap_check.py:138-139 [DERIVED].

**gap_sentences** — shared/polymath_shared/gap_check.py:157-169
- in: answer text; sentences split by `split_sentences` (headings/fences/tables skipped) — shared/polymath_shared/gap_check.py:161 [DERIVED].
- out: list of `{index, text, pattern}`; first matching pattern wins — shared/polymath_shared/gap_check.py:166-168 [DERIVED].
- pre: weak (non-strong) patterns are skipped on sentences containing an `[S#]` tag — shared/polymath_shared/gap_check.py:162-165 [DERIVED].

**gap_query** — shared/polymath_shared/gap_check.py:185-195
- out: ≤ `max_words` (12) content words; a sentence with < 2 content words borrows from `fallback` until 8 words; empty string = no search — shared/polymath_shared/gap_check.py:189-195 [DERIVED].

**honest_rewrite** — shared/polymath_shared/gap_check.py:227-265
- out: `(rewritten, rule)`; rule `None` = unchanged — shared/polymath_shared/gap_check.py:229 [DERIVED]; rules named `first_found`, `subject_do`, `subject_plural`, `subject_singular`, `nothing_in`, `not_in`, `beyond`, `participle_by`, `qualified` — shared/polymath_shared/gap_check.py:239-264 [DERIVED].
- pre: sentence already worded "the passages found" is left alone (or subject renamed) — shared/polymath_shared/gap_check.py:237-240 [DERIVED].
- post: `strong_only=True` skips the weak-pattern `qualified` fallback — shared/polymath_shared/gap_check.py:256-257 [DERIVED].

**mark_found** — shared/polymath_shared/gap_check.py:275-279
- out: `core + " (more below: [S7] [S8])."` — terminal punctuation split off and reattached — shared/polymath_shared/gap_check.py:277-279 [DERIVED].

**strip_unknown_tags** — shared/polymath_shared/gap_check.py:282-295
- out: `(text, dropped)`; every `[S#]` not in `allowed` removed, double spaces and space-before-punctuation cleaned — shared/polymath_shared/gap_check.py:287-295 [DERIVED].

**enabled / limits** — shared/polymath_shared/gap_check.py:109-111, shared/polymath_shared/gap_check.py:128-132
- `enabled`: default on; `"0", "false", "no", "off"` (stripped, lowered) disable — shared/polymath_shared/gap_check.py:110-111 [DERIVED].
- `limits`: `{max_claims, limit, budget_s, max_tokens}` from env with defaults 3 / 8 / 12.0 / 700 — shared/polymath_shared/gap_check.py:129-132 [DERIVED].

## effect surface
- env flags read (name = default): `POLYMATH_CHAT_GAP_CHECK` = `'1'` — shared/polymath_shared/gap_check.py:28, shared/polymath_shared/gap_check.py:110 (FACTS.env); `POLYMATH_CHAT_GAP_CHECK_MAX_CLAIMS` = 3 — shared/polymath_shared/gap_check.py:129; `POLYMATH_CHAT_GAP_CHECK_LIMIT` = 8 — shared/polymath_shared/gap_check.py:130; `POLYMATH_CHAT_GAP_CHECK_BUDGET_S` = 12.0 — shared/polymath_shared/gap_check.py:131; `POLYMATH_CHAT_GAP_CHECK_MAX_TOKENS` = 700 — shared/polymath_shared/gap_check.py:132.
- `os.environ` read directly in `enabled`/`_env_int`/`_env_float` — shared/polymath_shared/gap_check.py:110, shared/polymath_shared/gap_check.py:116, shared/polymath_shared/gap_check.py:122 [DERIVED].
- Postgres tables read/written: none (FACTS `tables_read`/`tables_written` empty). No files, network, subprocess, or model call in-module ("Pure: no I/O, no model call") — shared/polymath_shared/gap_check.py:13 [DERIVED]; all external effects flow through the injected `retrieve`/`hydrate`/`complete` — shared/polymath_shared/gap_check.py:332-334 [DERIVED].

## invariants
INVARIANT: passages offered per found claim ≤ `cite_max` = `CITE_MAX` = 3 — shared/polymath_shared/gap_check.py:33, shared/polymath_shared/gap_check.py:406 [DERIVED]
  fails-if: more than 3 chips per claim → oversized addition and legend bloat.
INVARIANT: sentence-claim receipt `text` length ≤ 240 chars (`g["text"][:240]`) — shared/polymath_shared/gap_check.py:360 [DERIVED]
  fails-if: longer claims are silently truncated in the receipt/prompts.
INVARIANT: facet claim query ≤ 200 chars, facet name ≤ 80 — shared/polymath_shared/gap_check.py:369-370 [DERIVED]
  fails-if: over-long facet queries truncate to a different search.
INVARIANT: hydrated passage text stored ≤ `PASSAGE_CHARS` = 1500 — shared/polymath_shared/gap_check.py:34, shared/polymath_shared/gap_check.py:427, shared/polymath_shared/gap_check.py:313 [DERIVED]
  fails-if: legend entries and addition prompt disagree with full passage text.
INVARIANT: new legend tag = `"S" + (max existing legend S-number + 1)`, monotonically incremented — shared/polymath_shared/gap_check.py:354, shared/polymath_shared/gap_check.py:424-425 [DERIVED]
  fails-if: tag collision → new `[S#]` chips resolve to the wrong passage.
INVARIANT: a row counts as found only when `sigmoid(rerank_score) >= floor` AND row has `chunk_id`; rows with no `rerank_score` only increment `unjudged` — shared/polymath_shared/gap_check.py:395-400 [DERIVED]
  fails-if: unscored rows cited → unjudged evidence enters the answer.
INVARIANT: rows per search ≤ `max(1, limit)` — shared/polymath_shared/gap_check.py:387 [DERIVED]
  fails-if: `limit=0` silently becomes 1 instead of no search.
INVARIANT: claim past `budget_s` wall-clock is `skipped="budget"`, never searched — shared/polymath_shared/gap_check.py:381-383 [DERIVED]
  fails-if: unbounded latency added to the turn.
INVARIANT: addition accepted only if body non-empty AND contains ≥ 1 offered tag; else `error="empty_or_uncited"` → stub — shared/polymath_shared/gap_check.py:476-486 [DERIVED]
  fails-if: uncited or hallucinated-tag prose rides the answer.

## determinism & idempotency
determinism: NONDETERMINISTIC (default `clock=time.perf_counter` gates claims — shared/polymath_shared/gap_check.py:337, shared/polymath_shared/gap_check.py:381; `os.environ` reads — shared/polymath_shared/gap_check.py:110, shared/polymath_shared/gap_check.py:116, shared/polymath_shared/gap_check.py:122; injected `retrieve`/`hydrate`/`complete` may hit db/network — shared/polymath_shared/gap_check.py:332-334). All text edits are pure regex — shared/polymath_shared/gap_check.py:53-69, shared/polymath_shared/gap_check.py:200-210 [DERIVED].
idempotency: UNSAFE — the module's own rewrite output ("the passages (first )?found … don't cover …") still matches the STRONG `passages_found` pattern — shared/polymath_shared/gap_check.py:54, shared/polymath_shared/gap_check.py:446 — so re-running `run_gap_check` on already-checked text re-flags rewritten sentences and can append a second "**More on this.**" section [INFERRED: pattern at :54 matches the rewrite wording produced at :446-451].

## failure behaviour
- `except Exception` around `retrieve` (FACTS.fallbacks :388): swallowed; claim gets `error = "TypeName: msg[:160]"`, search receipted `{returned: 0, above_floor: 0, error}`, loop continues — shared/polymath_shared/gap_check.py:388-392 [DERIVED].
- `except Exception` around `hydrate` (FACTS.fallbacks :419): swallowed; `c["error"] = "hydrate:TypeName"`, `h = None`, that passage is not cited — shared/polymath_shared/gap_check.py:419-421 [DERIVED].
- `except Exception` around `complete` (FACTS.fallbacks :481): swallowed; `call["error"]` set, `body = ""` → deterministic `stub_addition`, `call["fallback"] = "stub"` — shared/polymath_shared/gap_check.py:481-486 [DERIVED].
- `complete` returning empty or uncited text: `call["error"] = "empty_or_uncited"`, body reset, stub used — shared/polymath_shared/gap_check.py:478-486 [DERIVED].
- No raise path is visible in `run_gap_check`; every failure rides the receipt instead of breaking the turn ("a failed search is a receipted search, never a broken turn") — shared/polymath_shared/gap_check.py:385, shared/polymath_shared/gap_check.py (line out of range) region not used; anchor: shared/polymath_shared/gap_check.py (line out of range) [DERIVED].
- `_env_int`/`_env_float` swallow `ValueError` and return the default — shared/polymath_shared/gap_check.py:114-125 [DERIVED].

## dumb-code flags
- Magic truncations inline: `240` (claim text) — shared/polymath_shared/gap_check.py:360; `80` and `200` (facet name/query) — shared/polymath_shared/gap_check.py:369-370; `160` in two error strings — shared/polymath_shared/gap_check.py:389, shared/polymath_shared/gap_check.py:482.
- The four env-override names at shared/polymath_shared/gap_check.py:129-132 are raw strings with no named constants, while `FLAG` has one — shared/polymath_shared/gap_check.py:28.
- Env access split two ways: `enabled(env=...)` is injectable but `limits()`/`_env_int`/`_env_float` read `os.environ` directly — shared/polymath_shared/gap_check.py:109-110 vs shared/polymath_shared/gap_check.py:128-132.
- Negation/subject word lists duplicated between `GAP_PATTERNS` and the rewrite regexes `_R_SUBJECT_DO/_R_NOTHING_IN/_R_NOT_IN/_R_BEYOND` — shared/polymath_shared/gap_check.py:54-68 vs shared/polymath_shared/gap_check.py:200-210; drift risk between detect and rewrite.
- `floor` (0.5) is a parameter with no env override, unlike the other four tunables — shared/polymath_shared/gap_check.py:334 vs shared/polymath_shared/gap_check.py:129-132.
- Tag numbers re-parsed through the `S_TAG` regex: `int(m) for e in entries for m in S_TAG.findall(f"[{e['tag']}]")` — shared/polymath_shared/gap_check.py:354.
- `c["edited"]` silently reset to `None` when the gap sentence is not a verbatim substring ("never expected") — shared/polymath_shared/gap_check.py:455-456.

## refactor notes
- `CONTRACT = "chat-gap-check-v1"` rides the receipt as `meta.gap_check`; consumers matching the contract or receipt keys `{contract, claims, searches, ms, call, section_added, limits, budget_exhausted}` break on rename — shared/polymath_shared/gap_check.py:27, shared/polymath_shared/gap_check.py:342, shared/polymath_shared/gap_check.py:489-493.
- `legend_added` entry schema `{tag, locator, chunk_id, doc_id, text, breadcrumb, carried, carry_score, gap_check, source_name, title, heading_path, human_locator}` is appended by the caller to the turn's legend and chunk inventory — schema changes have caller blast radius — shared/polymath_shared/gap_check.py:426-430, shared/polymath_shared/gap_check.py:340-341.
- Sole recorded importer `orchestrator/orchestrator/api/ui.py` (FACTS.importers) — renaming `enabled`/`eligible`/`run_gap_check`/`limits` touches it.
- Detection (`GAP_PATTERNS`) and rewrite (`_R_*` + `honest_rewrite`) must stay aligned: a detected pattern with no rewrite rule falls through to the `"(among the passages found)"` qualifier or stays unchanged — shared/polymath_shared/gap_check.py:53-69, shared/polymath_shared/gap_check.py:200-210, shared/polymath_shared/gap_check.py:261-264.
- Sentence splitting (headings, fences, tables skipped) comes from `polymath_shared.deep_research.evidence.split_sentences` — gap detection inherits that splitter's behavior — shared/polymath_shared/gap_check.py:25.
- Flag-off contract: `POLYMATH_CHAT_GAP_CHECK=0` promises "today's answer byte for byte" — any new edit must stay behind the flag — shared/polymath_shared/gap_check.py:13-14.

## VERIFY
```verify
grep -Fq 'chat-gap-check-v1' shared/polymath_shared/gap_check.py
grep -Fq '**More on this.**' shared/polymath_shared/gap_check.py
grep -Eq 'DEFAULT_MAX_CLAIMS = 3' shared/polymath_shared/gap_check.py
grep -Eq 'DEFAULT_BUDGET_S = 12\.0' shared/polymath_shared/gap_check.py
grep -Fq 'if s >= floor and r.get("chunk_id"):' shared/polymath_shared/gap_check.py
grep -Fq 'call["fallback"] = "stub"' shared/polymath_shared/gap_check.py
test "$(grep -c -F 'POLYMATH_CHAT_GAP_CHECK' shared/polymath_shared/gap_check.py)" -ge 5
! grep -Fq 'import requests' shared/polymath_shared/gap_check.py
```
