# unit: adapters/ecommerce/python/field_evidence.py
anchor: adapters/ecommerce/python/field_evidence.py:1-181

## purpose
Turns prior field-evidence corpus rows (tagged `field_evidence`, each opening with a `FIELD_OBS ...` machine line) back into observation candidates for the CURRENT run's open gaps — same gap id when the signal repeats, keyword overlap otherwise — keeping original author/thread identity and recomputing freshness from the export date (adapters/ecommerce/python/field_evidence.py:2-16) [DERIVED]. With `--leads`, emits `field_records` for leads whose community matched (origin `PRIOR_RUN`, docs/25 §2) instead of gap observations (adapters/ecommerce/python/field_evidence.py:124-127, 162) [DERIVED]. Every emitted item cites `corpus_row_id`, which the utilization receipt counts as "gaps with corpus support" (adapters/ecommerce/python/field_evidence.py:15-16) [DERIVED]. CLI: `python3 python/field_evidence.py --state run.json --out payload.json [--min-overlap 3]` (adapters/ecommerce/python/field_evidence.py:18) [DERIVED].

## public surface
| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `_toks` | def (helper) | `(s: str) -> set` | adapters/ecommerce/python/field_evidence.py:37-38 | — (intra-module) |
| `parse_row` | def | `(row: dict) -> dict \| None` | adapters/ecommerce/python/field_evidence.py:41-67 | — (`candidates`, `lead_candidates`) |
| `recompute_freshness` | def | `(cls_at_export, exported_at, today=None) -> str` | adapters/ecommerce/python/field_evidence.py:70-82 | — (`candidates`, `lead_candidates`) |
| `candidates` | def | `(state: dict, min_overlap=3, today=None) -> list[dict]` | adapters/ecommerce/python/field_evidence.py:85-121 | — (`main`) |
| `lead_candidates` | def | `(state: dict, today=None) -> list[dict]` | adapters/ecommerce/python/field_evidence.py:124-156 | — (`main`) |
| `main` | def | `() -> int` | adapters/ecommerce/python/field_evidence.py:159-177 | — (`__main__` guard 180-181) |

FACTS list no external importers; callers shown are the ones visible in SOURCE [DERIVED].

## contracts
**parse_row** — adapters/ecommerce/python/field_evidence.py:41-67
- in: `row` with `"text"` or `"summary"` (42); optional `row["document"]["frontmatter"]` (61).
- pre: text matches `_HDR` = `FIELD_OBS\s+(.*)` (29, 43-45); at least one body line matches `_QUOTE` = `^"(.*)"$` (31, 52-54); else returns `None` (45, 60).
- out: keys `author_key, roles, purchase_language, freshness_at_export, gap_id, obs_id, quote, problem, workaround, platform, thread_key, community, source_url, exported_at` (62-67); `roles` split on `|` (62); `purchase_language` = `(kv.get("purchase") or "no").lower() in ("yes", "true", "1")` (63); `platform` defaults `"reddit"` (66); `source_url` = frontmatter value or `row.get("source")` (67).
- post: `problem`/`workaround` parsed only from lines starting `problem:` / `workaround:` (55-58); only the first quoted line is kept (53-54).

**recompute_freshness** — adapters/ecommerce/python/field_evidence.py:70-82
- in: class at export (`"LIVE"`/`"FAST"`/other), ISO date string (first 10 chars used, 75), optional `today` defaulting to `dt.date.today()` (73).
- out: `"LIVE"` iff cls=`"LIVE"` and age <= 90; `"FAST"` if age <= 730; `"SLOW"` otherwise (78-82).
- post: unparseable/missing `exported_at` → `"SLOW"` (74-77); conservative — thread is at least as old as its export (71-72).

**candidates** — adapters/ecommerce/python/field_evidence.py:85-121
- in: `state["data"]` with `hypotheses`, `gaps`, `observations`, `corpus_evidence` (86-92).
- pre: gap eligible iff `status == "open"` and its `hypothesis_id` is in a hypothesis whose status is not `("REJECTED", "HOLD")` (87-88); row eligible iff `"field_evidence" in row.get("tags")` (93).
- out: one observation per (row, gap) pair; `matched_by` = `"same_gap"` when the row's original `gap_id` is still open (100-101), else `f"overlap:{ov}"` when token overlap >= `min_overlap` (105-107); `evidence_roles` default `["BEHAVIOR_SUPPORT"]` (115); `query_used` = `"field-evidence corpus"`, `query_id` = `None` (119).
- post: id = `"fobs_" +` sha1 of `f"{row_id}|{gap_id}"` truncated to 12 hex, skipped if already an observation id (109-110).

**lead_candidates** — adapters/ecommerce/python/field_evidence.py:124-156
- in: leads via `lived_world.all_leads(state)` (128-130) and `corpus_evidence` rows (137).
- pre: parsed row must have `community` (141) whose `_lw._norm_community` matches a lead `community_key` (132-134, 143-145).
- out: field_record per (row, lead); id = `"frec_" +` sha1 of `f"{row_id}|{lead_id}"` truncated to 12 hex, deduped against existing `field_records` (135, 146-147); `origin` = `"PRIOR_RUN"` (155).

**main** — adapters/ecommerce/python/field_evidence.py:159-177
- in: flags `--state` (required), `--out` (required), `--min-overlap` (`type=int, default=3`), `--leads` (`store_true`) (161-162).
- out: `--leads` → `{"field_records": recs}` (168) + stdout `{"field_records", "leads_covered"}` (169); default → `{"observations": cands}` (172) + stdout `{"candidates", "gaps_covered", "threads_per_gap"}` with gap ids truncated `k[:8]` (173-176); returns 0 (170, 177).

## effect surface
- Postgres tables read/written: none — imports are only `argparse, datetime, hashlib, json, re, sys` (adapters/ecommerce/python/field_evidence.py:22-27); FACTS report `tables_read: []`, `tables_written: []` [DERIVED].
- Files: reads state JSON at `--state` (164-165); writes payload JSON at `--out` (168, 172); writes summaries to stdout (169, 176).
- Local module dependency: `import lived_world as _lw` inside `lead_candidates` — uses `all_leads` and `_norm_community` (128, 130, 134, 137).
- Qdrant collections / network / subprocess / env flags: none visible (22-27, whole file) [DERIVED].

## invariants
INVARIANT: LIVE retention window = 90 days from export (`age <= 90` → LIVE, else FAST) — adapters/ecommerce/python/field_evidence.py:79 [DERIVED]
  fails-if: stale LIVE evidence overstays; utilization receipt counts old support as LIVE.
INVARIANT: FAST cutoff = 730 days, for both LIVE-origin and FAST-origin rows — adapters/ecommerce/python/field_evidence.py:79, 81 [DERIVED]
  fails-if: FAST and SLOW classes collapse or split at the wrong age.
INVARIANT: invalid or missing `exported_at` ⇒ freshness class `"SLOW"` — adapters/ecommerce/python/field_evidence.py:74-77 [DERIVED]
  fails-if: bad dates would otherwise crash the run or inflate freshness.
INVARIANT: default `min_overlap` = 3 in both the `candidates` signature and the CLI — adapters/ecommerce/python/field_evidence.py:85, 161 [DERIVED]
  fails-if: the two defaults diverge; CLI runs and library calls score overlap differently.
INVARIANT: observation id = `"fobs_" +` 12 hex of sha1(`row_id|gap_id`); record id = `"frec_" +` 12 hex of sha1(`row_id|lead_id`) — adapters/ecommerce/python/field_evidence.py:109, 146 [DERIVED]
  fails-if: id format change re-emits duplicates into `observations`/`field_records`.
INVARIANT: only rows tagged `"field_evidence"` are considered — adapters/ecommerce/python/field_evidence.py:93, 138 [DERIVED]
  fails-if: untagged corpus rows leak in as field observations.
INVARIANT: role fallback = `["BEHAVIOR_SUPPORT"]`; platform fallback = `"reddit"` — adapters/ecommerce/python/field_evidence.py:115, 151, 66 [DERIVED]
  fails-if: downstream role/platform filters stop matching these records.

## determinism & idempotency
determinism: NONDETERMINISTIC (clock: `dt.date.today()` at adapters/ecommerce/python/field_evidence.py:73 whenever `today=None` — the default for `candidates`, `lead_candidates`, and both CLI paths at 167, 171; freshness class in output depends on run date).
idempotency: SAFE — ids are pure sha1 over `row_id|gap_id` / `row_id|lead_id` and are checked against existing `observations` (109-110) and `field_records` (146-147) before emission; re-running adds nothing. Freshness class may drift between days while ids stay stable.

## failure behaviour
- `parse_row` returns `None` on missing `FIELD_OBS` header (44-45) or missing quoted line (59-60); both `candidates` and `lead_candidates` silently `continue` (96-97, 141-142) — malformed rows are dropped with no error or count.
- `recompute_freshness` swallows `ValueError` from `dt.date.fromisoformat` and returns `"SLOW"` (74-77).
- No other handlers; `main` returns 0 on both branches (170, 177); argparse/JSON/OS errors propagate uncaught (159-177).

## dumb-code flags
- Magic numbers: `90` and `730` day thresholds (79, 81); sha1 truncated to 12 hex (109, 146); `[a-z]{4,}` min token length (38); `[:10]` date slice (75); `k[:8]` gap-id truncation in the stdout summary (176) — two gaps sharing an 8-char id prefix collide in the printed report [INFERRED].
- Duplicated literals: `"field_evidence"` tag test (93, 138); `["BEHAVIOR_SUPPORT"]` default (115, 151); `"field-evidence corpus"` (119, 155); `"source_family": "community"` (117, 153); the candidate dict (112-120) and record dict (148-155) are near-duplicates.
- `_QUOTE` = `^"(.*)"$` with `re.S`, and only the first quoted line is kept (`if q and not quote`, 53-54); later quoted lines are silently ignored (53-54).
- `query_id: None` is written into every observation (119) and never set anywhere else in this file.

## refactor notes
- `lead_candidates` depends on `lived_world.all_leads` and the underscore-private `_lw._norm_community` (128-137); renaming either in `lived_world` breaks this file.
- The id scheme (`"fobs_"`/`"frec_"` + sha1 over `row|gap` / `row|lead`) is the dedup contract; changing it re-emits duplicates into downstream `observations`/`field_records` stores (109-110, 146-147).
- Payload keys `observations` (172) and `field_records` (168) are the `--out` contract; consumers read those names.
- `matched_by` values `"same_gap"` and `f"overlap:{ov}"` (101, 107) flow into state and the utilization receipt semantics (15-16).
- Freshness thresholds 90/730 (79, 81) duplicate knowledge stated in the docstring (71-72); changing one without the other silently changes receipt classes.
- CLI flags `--state --out --min-overlap --leads` (161-162) are the runbook interface documented at line 18.

## VERIFY
```verify
grep -Fq 'FIELD_OBS' adapters/ecommerce/python/field_evidence.py
grep -Fq 'age <= 90' adapters/ecommerce/python/field_evidence.py
test "$(grep -c -F 'age <= 730' adapters/ecommerce/python/field_evidence.py)" -ge 2
grep -Fq '"fobs_" + hashlib.sha1' adapters/ecommerce/python/field_evidence.py
grep -Eq 'min.overlap.{0,30}default=3' adapters/ecommerce/python/field_evidence.py
! grep -Fq 'requests' adapters/ecommerce/python/field_evidence.py
test "$(grep -c -F 'BEHAVIOR_SUPPORT' adapters/ecommerce/python/field_evidence.py)" -ge 2
```
