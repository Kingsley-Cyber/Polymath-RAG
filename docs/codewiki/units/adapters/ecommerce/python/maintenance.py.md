# unit: adapters/ecommerce/python/maintenance.py
anchor: adapters/ecommerce/python/maintenance.py:1-333

## purpose
Executor layer of the Registry Maintenance lifecycle (docs/23): runtime deposits `registry_candidates`, this graph evaluates them (collect → normalize → type → dedupe → novelty → evidence → promotion gate), then emits patched CSV copies plus a unified diff for human L5 approval; overlay-compile and regression checks follow. Live registry files are never edited — a human applies the patch and commits ("git promotes"). — maintenance.py:1-15 [DERIVED]

## public surface
All step functions share `(state: dict, policies: dict) -> str` and mutate `state` in place.

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| collect_candidates | def | (state, policies) -> str | maintenance.py:76-91 | — |
| normalize_candidates | def | (state, policies) -> str | maintenance.py:94-101 | — |
| resolve_candidate_types | def | (state, policies) -> str | maintenance.py:104-149 | — |
| dedupe_candidates | def | (state, policies) -> str | maintenance.py:171-200 | — |
| novelty_check | def | (state, policies) -> str | maintenance.py:203-211 | — |
| candidate_evidence | def | (state, policies) -> str | maintenance.py:214-227 | — |
| promotion_satisfaction | def | (state, policies) -> str | maintenance.py:230-244 | — |
| csv_patch | def | (state, policies) -> str | maintenance.py:253-291 | — |
| registry_compile | def | (state, policies) -> str | maintenance.py:313-319 | — |
| regression_tests | def | (state, policies) -> str | maintenance.py:322-332 | — |

Private helpers: `_norm` 46-47, `_slug` 50-51, `_toks` 54-55, `_read_csv` 58-62, `_cands` 65-66, `_thresholds` 69-72, `_existing_names` 153-168, `_approved` 248-250, `_overlay_compile` 294-310. No importers recorded in FACTS.

## contracts

**collect_candidates** — maintenance.py:76-91
- in: `state["data"]["registry_candidates"]` (dicts only, filtered at 65-66); `memory.candidate_recurrence()` as `{(kind, name): runs}` (79)
- pre: `memory` importable; any Exception → `rec = {}` (80-81)
- post: deduped by `(kind, name)`; `c["runs"] = max(int(c.runs), int(rec[key]))` (88); list written back to `state["data"]["registry_candidates"]` (90)

**normalize_candidates** — maintenance.py:94-101
- post: each candidate gets `norm_name`, `slug`, `target_table`, `promotion_risk` from `TARGET`; unknown kind → `(None, "n/a")` (96-100, 38-41)

**resolve_candidate_types** — maintenance.py:104-149
- pre: `friction_library.csv` and `search_query_templates.csv` readable under TRAIL (107-108)
- post: `draft_row` per table (`seed` / `search_query_templates` / `source_registry`); `type_hold_reason` set when friction family not in `friction_library` (116-117) or kind has no table (147-148); seed rows stamped `created_at`/`last_verified_at` = `dt.date.today().isoformat()` (109, 134)
- rule: friction families are held, never invented (105-106)

**dedupe_candidates** — maintenance.py:171-200
- pre: `registry.load_snapshot()` available (172-173)
- post: `dedupe_status` ∈ {`EXISTING` exact normalized match (181), `ALIAS` Jaccard ≥ 0.6 over `_toks` (190-191), `MERGE` in-batch duplicate (194), `NEW` (195)}; sets `alias_of`, `alias_similarity`

**novelty_check** — maintenance.py:203-211
- post: `novelty` ∈ {`NEW_SEED` (NEW + seed table), `NEW_ROW`, `EXTENDS_EXISTING` (ALIAS), `KNOWN`} (205-210)

**candidate_evidence** — maintenance.py:214-227
- in: thresholds from `policies["maintenance_triggers"]`, defaults all 2 (69-72); `researched` = ≥1 history entry with `to == "research"` (216)
- post: `evidence_status` ∈ {`sufficient`, `needs_field_evidence`, `insufficient`}; `QUERY_PATTERN_CANDIDATE`/`SOURCE_CANDIDATE` exempt from the `evidence_refs >= 1` requirement (220)

**promotion_satisfaction** — maintenance.py:230-244
- post: `promotion_status` ∈ {`EXISTING`, `HELD` (type hold or evidence ≠ sufficient), `ELIGIBLE`}; writes `state["data"]["promotion_summary"]` (242); `state["verdict"] = "NEEDS_APPROVAL"` if any ELIGIBLE else `"NO_CHANGES"` (243)

**csv_patch** — maintenance.py:253-291
- pre: `state["data"]["approvals"]` entries with `decision == "approve"` matching ELIGIBLE ids (248-250)
- post: patched copies under `registry/patches/<run_id>/trailsignal/` + unified diff `registry/patches/<run_id>.diff`; `state["data"]["registry_patch"]` manifest with `apply` src→dst pairs (284-290); live files untouched (254-256)

**registry_compile** — maintenance.py:313-319
- post: overlay compile in temp copy of TRAIL with patch applied (294-308); result stored at `registry_patch["compile"]` (318); reports seeds/templates before→after (317)

**regression_tests** — maintenance.py:322-332
- post: runs `controller.py doctor`; passes iff compile valid AND doctor ok AND seeds ≥ seeds_before (329); `state["verdict"] = "MAINTENANCE_COMPLETE"` or `"BLOCKED"` (331); result at `registry_patch["regression"]` (330)

## effect surface
- Files read: `registry/trailsignal/friction_library.csv` (107), `registry/trailsignal/search_query_templates.csv` (108), `registry/trailsignal/source_registry.csv` (166), live table CSVs via `_read_csv` in csv_patch (268-269)
- Files written: `registry/patches/<run_id>/trailsignal/<fname>.csv` (258, 276-277), `registry/patches/<run_id>.diff` (284-286), temp dir `registry_overlay_*` created/removed (298, 308)
- Subprocess: `subprocess.run([sys.executable, ROOT/python/controller.py, "doctor"], cwd=ROOT)` (324)
- Cross-module calls: `memory.candidate_recurrence()` (79), `registry.load_snapshot()` / `compile_registry()` (173, 305); global `registry.SRC` swapped and restored in `finally` (304-307)
- Clock: `dt.date.today()` (109)
- Postgres tables: none (FACTS `tables_read`/`tables_written` empty); no network imports; no env flags read (17-29)

## invariants
INVARIANT: alias similarity threshold == 0.6 — maintenance.py:190 [DERIVED]
  fails-if: lower merges unrelated candidates into ALIAS; higher lets true duplicates through as NEW
INVARIANT: recurrence_min_runs == query_yield_min_runs == source_yield_min_runs == 2 (defaults) — maintenance.py:71-72 [DERIVED]
  fails-if: evidence gate passes candidates seen in fewer runs than policy intends
INVARIANT: promotion_risk — ACTIVITY_CANDIDATE "LOW_MEDIUM", MECHANISM_CANDIDATE "MEDIUM", QUERY_PATTERN_CANDIDATE "MEDIUM", FRICTION_CANDIDATE "HIGH", SOURCE_CANDIDATE "HIGH", motifs "n/a" — maintenance.py:38-41 [DERIVED]
  fails-if: approver underestimates risk of a promoted row
INVARIANT: motif kinds (REASONING_MOTIF_CANDIDATE, NEGATIVE_REASONING_MOTIF, WHITESPACE_MOTIF_CANDIDATE, DEMAND_REROUTE_MOTIF_CANDIDATE) map to table None and are always held — maintenance.py:40-41, 147-148 [DERIVED]
  fails-if: patch tries to write a registry table that does not exist
INVARIANT: discovered ids — `"seed-d-"+sha256[:8]`, `"act-"+slug`, `"q-d-"+sha256(norm_name)[:8]`, `"src-d-"+sha256(norm_name)[:8]` — maintenance.py:119-120, 138, 142 [DERIVED]
  fails-if: id collisions or drift from existing registry id grammar
INVARIANT: discovered sources land `enabled_by_default == "false"`; discovered templates land `enabled == "true"` — maintenance.py:140, 145 [DERIVED]
  fails-if: unverified discovered source becomes active in every run
INVARIANT: discovered seed rows ship `fact_status == "hypothesis"` and `research_status == "seed"` — maintenance.py:133 [DERIVED]
  fails-if: hypothesis rows presented as verified facts
INVARIANT: live registry files are never written by this module — maintenance.py:5-6, 254-256, 276-277 [DERIVED]
  fails-if: breaks the human-applies-patch law; unreviewed rows go live
INVARIANT: `_toks` discards tokens with `len(t) <= 3` — maintenance.py:55 [DERIVED]
  fails-if: short tokens skew the 0.6 Jaccard alias test

## determinism & idempotency
determinism: NONDETERMINISTIC (clock `dt.date.today()` at 109; subprocess `controller.py doctor` at 324 — FACTS.nondeterminism)
idempotency: SAFE — reruns overwrite the same `registry/patches/<run_id>/` outputs (258, 284) and never touch live files; patch bytes are not day-stable because of the date stamp (109, 134, 145)

## failure behaviour
- `collect_candidates`: any Exception from `memory.candidate_recurrence()` swallowed, `rec = {}` (80-81) — recurrence-gated candidates then rely on in-payload `runs` only and may fall below threshold [DERIVED]
- `regression_tests`: any Exception parsing doctor output swallowed, `doctor_ok = False` (327-328) — verdict becomes "BLOCKED" [DERIVED]
- `_read_csv` returns `[]` for a missing file (59-60) — a missing `friction_library.csv` yields an empty `families` set, which holds every FRICTION_CANDIDATE at 116-117 [INFERRED: membership test against empty set always fails]
- No raised error codes; control flow is via `state["verdict"]`: "NEEDS_APPROVAL"/"NO_CHANGES" (243), "MAINTENANCE_COMPLETE"/"BLOCKED" (331)

## dumb-code flags
- Magic numbers: `0.6` alias threshold (190); default `2` repeated for all three triggers (71-72); slug cap `[:48]` (51); `len(t) > 3` (55); hash slice `[:8]` (119, 138, 142); error truncation `[:10]` (309) then `[:3]` in the message (319)
- `_read_csv(live)` invoked twice in one expression (268) — file parsed twice
- Non-seed `columns` fallback uses only `cs[0].draft_row` keys when the live file is absent (268) — heterogeneous candidates silently lose columns [INFERRED]
- `c not in approved` compares dicts by equality against a list (289) — O(n²), and an unapproved candidate equal to an approved one's dict would be misclassified [INFERRED]
- Literal `"complaint"` duplicated as goal fallback at 108 and 137
- `"\n".join(diffs)` (286) joins chunks that already end in newlines — stray blank lines in `<run_id>.diff` [INFERRED]
- `registry.SRC` global swap (304-307) — not reentrant under concurrency [INFERRED]
- `source_registry.csv` read raw at 166 although `registry.load_snapshot()` was already called at 173-174 — two sources for the same registry state [INFERRED]

## refactor notes
- `TARGET` table names ("seed", "search_query_templates", "source_registry") must stay in sync with `registry.py` compile expectations and `SEED_PACK` filename (34, 38-41, 172, 296-307) — blast radius: dedupe, patch emission, overlay compile
- `SEED_COLUMNS` order defines the patched seed CSV header (35-37, 268, 271) — changing it reorders `discovered_activity_niche_seed.csv`
- `state` keys consumed downstream: `registry_candidates` (90), `promotion_summary` (242), `registry_patch` incl. `apply`/`compile`/`regression` (287-290, 318, 330), `approvals` (249), `verdict` (243, 331) — L5 approver and controller depend on these shapes
- Cross-module contracts: `memory.candidate_recurrence()` shape (79); `registry.SRC`/`compile_registry()`/`load_snapshot()` (173, 296-307); `controller.py doctor` JSON with `ok` field (324, 326)
- Retuning `0.6` (190) or the trigger defaults (71-72) changes promotion outcomes — policy-level change, not a code fix

## VERIFY
```verify
grep -Fq 'SEED_PACK = "discovered_activity_niche_seed.csv"' adapters/ecommerce/python/maintenance.py
grep -Fq 'if best_j >= 0.6:' adapters/ecommerce/python/maintenance.py
grep -Fq '"FRICTION_CANDIDATE": ("seed", "HIGH")' adapters/ecommerce/python/maintenance.py
grep -Fq 'th.get("recurrence_min_runs", 2)' adapters/ecommerce/python/maintenance.py
grep -Fq 'state["verdict"] = "MAINTENANCE_COMPLETE" if ok else "BLOCKED"' adapters/ecommerce/python/maintenance.py
test "$(grep -c -F 'def ' adapters/ecommerce/python/maintenance.py)" -ge 19
! grep -Fq 'import requests' adapters/ecommerce/python/maintenance.py
```
