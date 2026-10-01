# unit: shared/polymath_shared/conformance/assess.py
anchor: shared/polymath_shared/conformance/assess.py:1-289

## purpose
Turns discovery output into classified components (provider lanes, workers, API routes, durable state tables); every verdict is derived from an observation and the observation travels with the verdict — a component with no evidence becomes `NOT_TESTED`, never green, never silently omitted — shared/polymath_shared/conformance/assess.py:1-6 [DERIVED]. Pure classification over caller-supplied evidence dicts; enums and severity come from `polymath_shared.conformance.classify` — shared/polymath_shared/conformance/assess.py:11 [DERIVED].

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| FUNCTION_STAGE | const | dict lane-function -> `stage_tickets.stage` value | shared/polymath_shared/conformance/assess.py:17-18 | — |
| assess_lanes | def | (lanes: list[dict], controller: dict[str, dict], attempts: dict[str, dict] \| None = None) -> list[dict] | shared/polymath_shared/conformance/assess.py:30-80 | — |
| qualify_lane | def | (lane: dict, attempts_per_lane: dict[str, dict], controller: dict[str, dict], stage_act: dict[str, dict], chat_receipts: dict) -> dict | shared/polymath_shared/conformance/assess.py:100-173 | — |
| assess_workers | def | (on_disk: list[dict], supervisor: dict, live: dict, stage_activity: dict[str, dict]) -> list[dict] | shared/polymath_shared/conformance/assess.py:178-213 | — |
| assess_routes | def | (routes: list[dict], probe_results: dict[str, dict] \| None = None) -> list[dict] | shared/polymath_shared/conformance/assess.py:218-238 | — |
| assess_state | def | (tables: list[dict], readers: dict[str,dict]) -> list[dict] | shared/polymath_shared/conformance/assess.py:243-275 | — |
| summarize | def | (components: list[dict]) -> dict | shared/polymath_shared/conformance/assess.py:278-288 | — |

Private helpers: `_c` (:21-25), `_chat_pipeline_status` (:83-89), `_chat_e2e_status` (:92-97). No importers listed in FACTS.

Component shape (all assess_* outputs, built by `_c`): keys `kind`, `name`, `state` (enum value), `severity` (`severity(state)`), `levels` (list of enum values), `evidence` (dict), `notes` (str, default `""`) — shared/polymath_shared/conformance/assess.py:21-25 [DERIVED].

## contracts

**assess_lanes** — shared/polymath_shared/conformance/assess.py:30-80
- in: lane keys `name` (:40), `enabled` (:48, :55), `reachability` (:48, :59), `function` (:49, :64), `model`, `account_env`, `stage_pin`, `fallback_tier`, `capacity` (:49-51); `controller[name]["day_count"]` (:43); `attempts[name]["attempts"]` (:44) and `["ok"]` (:45).
- out: one component per lane, `kind="lane"` (:56, :75, :78).
- post state, first match wins: not `enabled` -> `State.RETIRE_CANDIDATE`, note `"disabled in config; superseded unless a rollback needs it"` (:55-57); `reachability != "active"` -> `State.BROKEN_REACHABLE` (:59-61); `function == "dedicated_unpinned"` -> `State.BROKEN_REACHABLE` (:64-66); dispatch evidence `day > 0 or seen > 0` with `ok > 0 or day > 0` -> `State.WORKING_PROVEN` (:68-72); dispatch evidence with `ok == 0, day == 0` -> `State.BROKEN_REACHABLE` (:70-74); else `State.CONFIGURED_IDLE`, note `"reachable, pinned, but no dispatch observed"` (:78-79).
- post levels: base `[Level.IMPLEMENTED]` (:46); `+WIRED+LIVE` only past enabled+active (:63); `+OBSERVED` (:69); `+CONTRACT_QUALIFIED` (:71).
- note format: `f"{day} durable dispatches today"` plus `f", {seen} ledger attempts"` iff `seen` (:215).

**qualify_lane** — shared/polymath_shared/conformance/assess.py:100-173
- in: `lane["function"]` (:135), `lane["name"]` (:136); `attempts_per_lane[name]["attempts"]/["succeeded"]` (:137); `controller[name]["day_count"]` (:138); `stage_act[stage]["recent"]` (:157); `chat_receipts` keys `ok`/`error`/`grounded`/`cited` (:87-97).
- out: `{"contract_qualified", "pipeline_qualified", "e2e_qualified", "qualification_evidence": {"attempt_ledger", "attempts", "succeeded", "durable_day_count", "contract_evidence_tier", ...pipeline evidence}}` (:162-173).
- post contract: `attempts > 0` -> `Status.FAIL` iff `succeeded == 0`, `Status.DEGRADED` iff `succeeded < attempts`, else `Status.PASS` (:140-146); `attempts == 0 and day > 0` -> `Status.PASS` (:147-148); else `Status.NOT_TESTED` (:149-150).
- post tier: `"attempt_ledger"` if `attempts > 0`, else `"day_count"` if `day > 0`, else `"none"` (:169-170).
- post pipeline/e2e: `fn == "CHAT"` -> from `chat_receipts` via the two helpers, evidence key `"query_receipts_overall"` (:152-154); else `stage = FUNCTION_STAGE.get(fn)`, pipeline `Status.PASS` iff `recent` truthy else `Status.NOT_TESTED`, `e2e = Status.NOT_APPLICABLE` (:156-159).
- pre: `fn` not in FUNCTION_STAGE -> `stage = None`, `recent = 0` -> pipeline `NOT_TESTED`, no error raised (:156-157) [DERIVED].
- CHAT pipeline PASS bar: `agg["ok"] > 0`; an `insufficient_evidence` abstention still counts as working pipeline (:84-89). CHAT E2E bar: `ok == 0` -> FAIL/NOT_TESTED; PASS iff `grounded` or `cited`, else `Status.DEGRADED` (:92-97).

**assess_workers** — shared/polymath_shared/conformance/assess.py:178-213
- in: `on_disk[].module` (:185), `.path` (:193); `supervisor["slots"][].name` (:181); `live["by_type"][].worker_type` (:182); `stage_activity` keyed by live type (:189-191).
- matching: slot iff `stem in str(s.get("name", ""))` or slot name startswith `stem.replace("_worker", "")` (:187); live iff `t.replace("_", "") in stem.replace("_", "")` or `stem.replace("_worker", "").replace("_", "") in t.replace("_", "")` (:188).
- post: no slot and no live -> `State.NOT_TESTED`, note `"no supervisor slot and no live registration found — verify before assuming dead"` (:195-197); live + `act["recent"]` -> `State.WORKING_PROVEN`, levels `+LIVE+OBSERVED+PIPELINE_QUALIFIED`, note `f"{act.get('recent')} tickets in the activity window"` (:200-205); live without recent -> `State.CONFIGURED_IDLE`, `"registered and healthy, no recent tickets"` (:206-208); slot-only -> `State.CONFIGURED_IDLE`, note mentions `"(autopilot parking is normal)"` (:209-211).

**assess_routes** — shared/polymath_shared/conformance/assess.py:218-238
- in: `route["path"]` (:221), optional `methods`/`source` (:224); `probe_results[path]` keys `ok`/`status`/`error` (:230-237).
- post: levels start at `[Level.IMPLEMENTED, Level.WIRED]`; `source == "live"` -> `+Level.LIVE` (:224-226); no probe entry -> `State.NOT_TESTED`, `"not probed in this scope"` (:227-229); probe `ok` -> `State.WORKING_PROVEN`, note `f"HTTP {pr.get('status')}"` (:230-234); else `State.BROKEN_REACHABLE`, note `f"HTTP {pr.get('status')}: {str(pr.get('error'))[:120]}"` (:235-237).

**assess_state** — shared/polymath_shared/conformance/assess.py:243-275
- in: `table["table"]` (:252), `["rows"]`, `["last_activity"]` (:256); `readers[table] = {"readers": [...], "writers": [...], "runtime": bool}` (:246, :253-254).
- post: `rd or wr` -> `+WIRED`, and `rows` -> `+LIVE` (:259-262); `rd and rows` -> `State.WORKING_PROVEN` else `State.LEGACY_REQUIRED` (:263); `rd and not wr` -> `State.LEGACY_REQUIRED`, note `f"read by {len(rd)} site(s) but nothing writes it"` (:265-266); census entry missing -> `State.NOT_TESTED`, `"reader/writer census not run for this table"` (:269-271); census ran with zero readers and zero writers -> `State.RETIRE_CANDIDATE`, `"needs runtime proof before removal"` (:272-274).
- post: never `DEAD_PROVEN`; retirement requires zero readers AND zero writers (:247-248).

**summarize** — shared/polymath_shared/conformance/assess.py:278-288
- in: `_c`-shaped dicts; reads `c["state"]` (:280-281) and `c["severity"]` (:284-286).
- out: `{"total", "by_state" (sorted by state name), "green", "amber", "red"}` (:282-287).

## effect surface
- Postgres tables read/written by this unit: none (FACTS `tables_read: []`, `tables_written: []`). Durable stores appear only as caller-supplied argument data: `llm_controller_state` (:34, :113, :138), `llm_provider_attempts` (:112, :137), `stage_tickets` (:104, :157), `query_receipts` (:104, :154) [DERIVED].
- Qdrant collections: none. No file I/O, network calls, subprocesses, or env flags; only import is `.classify` (:11) [DERIVED].
- Referenced-but-not-touched module: `doc_parent_map_stage_worker.py` named in the qualify_lane docstring as historical caller of `attempt_context` (:116-117).

## invariants
INVARIANT: FUNCTION_STAGE entries == {`"GRAPH_EXTRACTION": "extract"`, `"DOCUMENT_PROFILE": "doc_profile"`, `"PMAP": "doc_parent_map"`} and CHAT is absent — shared/polymath_shared/conformance/assess.py:14-18 [DERIVED]
  fails-if: a CHAT lane would take the `stage_tickets` branch and derive pipeline status from a stage it does not run under.
INVARIANT: contract evidence tier precedence is `attempt_ledger` > `day_count` > `none` — shared/polymath_shared/conformance/assess.py:169-170 [DERIVED]
  fails-if: count-only evidence would be allowed to produce DEGRADED/FAIL, which the day_count tier cannot honestly support (:124-126).
INVARIANT: `assess_lanes` promotes past `CONFIGURED_IDLE` only when `day > 0 or seen > 0` — shared/polymath_shared/conformance/assess.py:68-79 [DERIVED]
  fails-if: a configured-but-never-called lane would report green.
INVARIANT: qualify_lane contract bar must not be stricter than `assess_lanes` (`day > 0` -> at least PASS in both) — shared/polymath_shared/conformance/assess.py:71-72, :126-127, :147-148 [DERIVED]
  fails-if: the two assessors disagree on the same lane's qualification for the same evidence.
INVARIANT: component dict has exactly the 7 keys `kind`, `name`, `state`, `severity`, `levels`, `evidence`, `notes` — shared/polymath_shared/conformance/assess.py:21-25 [DERIVED]
  fails-if: `summarize` counting on `c["state"]`/`c["severity"]` (:280-286) KeyErrors or undercounts.

## determinism & idempotency
determinism: DETERMINISTIC — pure functions over argument dicts; no clock/random/uuid/network/db/env access, sole import is `.classify` — shared/polymath_shared/conformance/assess.py:11 [DERIVED]
idempotency: SAFE — no writes or side effects; every call builds fresh dicts (:22-25, :162-173) [DERIVED]

## failure behaviour
- No try/except anywhere; missing required dict keys (e.g. lane `name`, route `path`) raise KeyError to the caller — whole file, e.g. shared/polymath_shared/conformance/assess.py:40, :221 [DERIVED].
- Missing/None evidence values default to 0 via `int(x.get(...) or 0)` for `day_count`, `attempts`, `ok`, `succeeded` — shared/polymath_shared/conformance/assess.py:43-45, :137-138 [DERIVED].
- Absence of evidence is surfaced, never inferred: zero-evidence lanes/workers/routes/tables land in `NOT_TESTED` rather than FAIL — shared/polymath_shared/conformance/assess.py:4-5, :149-150, :195-197, :227-229, :269-271 [DERIVED].
- Honest abstention is not a failure: `_chat_pipeline_status` returns PASS on `ok > 0` regardless of grounded evidence — shared/polymath_shared/conformance/assess.py:84-89 [DERIVED].

## dumb-code flags
- Ledger success key mismatch: `assess_lanes` reads `at["ok"]` (:45) while `qualify_lane` reads `at["succeeded"]` (:137) from the same per-lane attempt ledger — one of the two disagrees with the ledger schema.
- Dead branch: `State.WORKING_UNQUALIFIED` at :72 is unreachable — the enclosing branch requires `ok > 0 or day > 0` (:70), which makes `ok or day` always truthy, so the ternary always yields `WORKING_PROVEN`.
- Magic number `[:120]` error truncation in route notes — shared/polymath_shared/conformance/assess.py:237.
- Fuzzy worker matching strips underscores and does bidirectional substring matching on `"_worker"`-suffixed stems — shared/polymath_shared/conformance/assess.py:186-188; cross-matching between similarly named worker types is possible.
- `assess_routes` asserts `Level.WIRED` for every route unconditionally (:224) — no check produces a non-WIRED route.
- Stage strings `"extract"`/`"doc_profile"`/`"doc_parent_map"` are literals duplicated against `stage_tickets.stage` DB values — shared/polymath_shared/conformance/assess.py:17-18.

## refactor notes
- `_c`'s 7-key component shape is consumed by `summarize` (:280-287); changing keys breaks state/severity counting.
- `Status.NOT_TESTED` semantics are a cross-module contract with `classify.py` ("NOT_TESTED must never be manufactured into a PASS") — shared/polymath_shared/conformance/assess.py:106-108; any change here must match classify.
- `qualify_lane`'s output keys (`contract_qualified`, `pipeline_qualified`, `e2e_qualified`, `qualification_evidence`) are a public result shape; callers unknown from FACTS — shared/polymath_shared/conformance/assess.py:162-173.
- Keep CHAT out of `FUNCTION_STAGE` and keep the two-tier (`attempt_ledger`/`day_count`) contract bar aligned with `assess_lanes` — shared/polymath_shared/conformance/assess.py:14-16, :126-127.
- Worker matching heuristics (:186-188) encode naming conventions (`_worker` suffix); renaming worker modules silently detaches them from supervisor/live evidence.

## VERIFY
```verify
grep -Fq 'FUNCTION_STAGE = {"GRAPH_EXTRACTION": "extract"' shared/polymath_shared/conformance/assess.py
grep -Eq 'def (assess_lanes|qualify_lane|assess_workers|assess_routes|assess_state|summarize)\(' shared/polymath_shared/conformance/assess.py
grep -Fq 'State.WORKING_PROVEN if ok or day else State.WORKING_UNQUALIFIED' shared/polymath_shared/conformance/assess.py
grep -Fq 'disabled in config; superseded unless a rollback needs it' shared/polymath_shared/conformance/assess.py
grep -Fq 'e2e = Status.NOT_APPLICABLE' shared/polymath_shared/conformance/assess.py
test "$(grep -c -F 'Status.NOT_TESTED' shared/polymath_shared/conformance/assess.py)" -ge 2
! grep -Fq 'import requests' shared/polymath_shared/conformance/assess.py
```
