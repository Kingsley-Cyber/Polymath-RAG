# unit: shared/polymath_shared/conformance/_small-modules
anchor: shared/polymath_shared/conformance/__init__.py:1-20

## purpose
Defines the production-conformance audit vocabulary (component `State`, proof `Level`, attempt `Status`) and the durable per-run audit bundle writer (`report.py`). Framework rule: nothing about provider topology is hardcoded — providers, models, accounts, lanes, workers, routes and durable state are discovered per run from config, DB, processes and code graph (shared/polymath_shared/conformance/__init__.py:3-7). Consumed by `assess.py` and `llm_extraction/client.py` (FACTS.importers).

## public surface
Package-level importers (FACTS.importers): `shared/polymath_shared/conformance/assess.py`, `shared/polymath_shared/llm_extraction/client.py` — importing `polymath_shared.conformance`, `AUDIT_VERSION`, `classify`, `classify.State` (FACTS.imports).

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `AUDIT_VERSION` | constant | `"conformance-audit-v1"` | __init__.py:17 | report.py:9; assess.py; llm_extraction/client.py |
| `State` | str-Enum (10 members) | — | classify.py:12-22 | report.py:10; llm_extraction/client.py |
| `GREEN` / `AMBER` / `RED` | frozenset[State] | — | classify.py:26 / 29-30 / 33 | severity, is_green (classify.py:37, 42) |
| `is_green` | def | (state: State \| str) -> bool | classify.py:36-37 | — |
| `severity` | def | (state: State \| str) -> str | classify.py:40-42 | — |
| `Level` | str-Enum (7 members) | — | classify.py:45-53 | — |
| `LEVEL_ORDER` | list[Level] | — | classify.py:56-57 | highest (classify.py:62) |
| `highest` | def | (levels: set[Level] \| set[str]) -> Level \| None | classify.py:60-65 | — |
| `Status` | str-Enum (5 members) | — | classify.py:68-73 | — |
| `PERMANENT_FUNCTIONS` | tuple (4 names) | — | classify.py:79 | — |
| `new_audit_id` | def | () -> str | report.py:16-17 | Bundle.__init__ (report.py:22) |
| `Bundle` | class | (audit_id: str \| None = None, root: Path \| None = None); .write(name, payload) -> Path; .write_text(name, text) -> Path | report.py:20-37 | — |
| `manifest` | def | (*, git: dict, bundle_state: dict, config: dict, scope: dict, discovered: dict, live_calls: int) -> dict | report.py:40-51 | — |
| `render_report` | def | (man: dict, components: list[dict], summary: dict, sections: dict[str, Any]) -> str | report.py:54-113 | — |

## contracts

`is_green` — classify.py:36-37
- in: `State` member or its string value; coerced via `State(state)` (classify.py:37)
- out: bool; True iff state ∈ `GREEN` == `{WORKING_PROVEN}` (classify.py:26)
- pre: value must name a `State` member, else `State(state)` raises [INFERRED: Enum lookup semantics]
- post: `is_green(s)` ⟺ `severity(s) == "green"` (classify.py:37 vs 42)

`severity` — classify.py:40-42
- out: one of `"green"`, `"amber"`, `"red"` (classify.py:42)
- post: default branch is `"red"` — anything not in GREEN/AMBER returns red (fail-closed, classify.py:42)
- post: `severity("DEAD_PROVEN") == "red"` — DEAD_PROVEN is in no bucket [INFERRED: member list classify.py:13-22 vs buckets 26/29-30/33, else-chain at 42]

`highest` — classify.py:60-65
- in: set of `Level` members or strings, coerced via `Level(l)` (classify.py:61)
- out: highest level by `LEVEL_ORDER`, `None` for empty set (classify.py:62-65)
- post: E2E_QUALIFIED > PIPELINE_QUALIFIED > CONTRACT_QUALIFIED > OBSERVED > LIVE > WIRED > IMPLEMENTED (classify.py:56-57 scanned reversed)

`new_audit_id` — report.py:16-17
- out: UTC wall-clock string, format `"%Y%m%dT%H%M%SZ"` (report.py:17)
- nondeterministic: `datetime.now(timezone.utc)` (report.py:17; FACTS.nondeterminism)

`Bundle` — report.py:20-37
- defaults: `audit_id=None` → `new_audit_id()`; `root=None` → `BUNDLE_ROOT` (report.py:22-23)
- post-init: `self.dir` exists (`mkdir(parents=True, exist_ok=True)`, report.py:24); `self.files == []` (report.py:25)
- `write`: dumps `json.dumps(payload, indent=2, default=str, sort_keys=False) + "\n"` (report.py:29); appends name to `self.files` (report.py:30)
- `write_text`: writes text verbatim (report.py:35)

`manifest` — report.py:40-51
- keyword-only params (report.py:40)
- out keys exactly: `audit_version`, `generated_at`, `repo`, `runtime_bundle`, `config_hashes`, `scope`, `discovered`, `live_calls_performed` (report.py:42-51)
- post: `audit_version == "conformance-audit-v1"` (report.py:43 + __init__.py:17); `generated_at` is a UTC ISO string (report.py:44)

`render_report` — report.py:54-113
- required `man` keys: `repo.branch/sha/dirty`, `runtime_bundle.live/uniform`, `discovered`, `scope`, `live_calls_performed` (report.py:61-66, 69, 76)
- required `summary` keys: `total`, `green`, `amber`, `red`, `by_state` (report.py:79-81)
- component row keys: `state`, `kind`, `name`, `notes` (report.py:86, 90-91)
- `sections`: str bodies inlined; non-str bodies JSON-dumped and truncated to 6000 chars (report.py:98-103)
- missing `_agnostic` / `_discovery` / `_retirement` render as `NOT_TESTED` (report.py:107, 109, 111)
- per-state listing capped at 60 rows, overflow points to `function_results.json` (report.py:90-93)

## effect surface
- filesystem: creates `<root or BUNDLE_ROOT>/<audit_id>/` — `BUNDLE_ROOT = ROOT / "artifacts" / "audit"`, `ROOT = Path(__file__).resolve().parents[3]` (report.py:12-13, 23-24)
- filesystem: writes JSON and text files into that dir (report.py:29, 35)
- clock: `datetime.now(timezone.utc)` at report.py:17 and report.py:44 (FACTS.nondeterminism)
- Postgres: none — `tables_read`/`tables_written` empty (FACTS)
- network / subprocess / env flags: none visible in SOURCE

## invariants
INVARIANT: |GREEN| == 1 (only `WORKING_PROVEN`) — classify.py:26 [DERIVED]
  fails-if: extra green state launders "no evidence" into success, which the docstring forbids (classify.py:3-5)
INVARIANT: |GREEN|+|AMBER|+|RED| == 9 but |State| == 10 — `DEAD_PROVEN` is in no bucket — classify.py:13-22 vs 26/29-30/33 [INFERRED: set difference over member lists]
  fails-if: summary colouring mislabels a proven-safe-to-remove component as `"red"` via the else-chain (classify.py:42)
INVARIANT: len(LEVEL_ORDER) == len(Level) == 7, order matches declaration order — classify.py:47-53 vs 56-57 [DERIVED]
  fails-if: `highest()` skips or mis-ranks a level (it scans `reversed(LEVEL_ORDER)`, classify.py:62)
INVARIANT: manifest["audit_version"] == `AUDIT_VERSION` == `"conformance-audit-v1"` — report.py:43, __init__.py:17 [DERIVED]
  fails-if: bundle provenance breaks against version-stamped consumers
INVARIANT: len(PERMANENT_FUNCTIONS) == 4 and `"parent_enrichment"` ∉ it — classify.py:79, 76-78 [DERIVED]
  fails-if: models qualify against a contract set that includes the transitional function
INVARIANT: rendered rows per state ≤ 60 — report.py:90, 92-93 [DERIVED]
  fails-if: silent truncation without the overflow note

## determinism & idempotency
determinism: NONDETERMINISTIC (clock: `datetime.now(timezone.utc)` at report.py:17 and report.py:44 — FACTS.nondeterminism). classify.py is pure: no clock/random/db/env reads in SOURCE [DERIVED].
idempotency: SAFE — mkdir uses `exist_ok=True` (report.py:24); `write`/`write_text` overwrite a same-named file (report.py:29, 35). Caveat: repeated write of the same name appends duplicate entries to `Bundle.files` [INFERRED: report.py:30/36 append unconditionally].

## failure behaviour
No try/except in any of the three files; FACTS contains no fallbacks list [DERIVED]. Raw exceptions propagate to callers:
- `ValueError` from `State(state)` / `Level(l)` on unknown value — classify.py:37, 41, 61 [INFERRED: Enum lookup]
- `KeyError` from direct dict indexing in `render_report` on missing `man`/`summary`/component keys — report.py:61-63, 79-81, 86 [INFERRED]
- `OSError` from `mkdir` / `write_text` — report.py:24, 29, 35 [INFERRED]

## dumb-code flags
- `DEAD_PROVEN` unbucketed → `severity` returns `"red"` for a retirement-success state — classify.py:20 vs 26/29-30/33 + 42 [INFERRED]
- literal `NOT_TESTED` duplicated across two enums and as a render default: `State.NOT_TESTED` (classify.py:21), `Status.NOT_TESTED` (classify.py:72), `sections.get(..., 'NOT_TESTED')` ×3 (report.py:107, 109, 111)
- magic numbers: row cap `60` (report.py:90, 93), JSON truncation `6000` (report.py:102), `parents[3]` (report.py:12), format paddings `:12` and `:22` (report.py:74, 82)
- `Bundle.write` hardcodes `indent=2`, `default=str`, `sort_keys=False` (report.py:29) — bundle JSON key order equals payload insertion order
- `render_report` references `function_results.json`, a file this module never writes (report.py:93) — name is an external convention

## refactor notes
- Changing `AUDIT_VERSION` ripples into `manifest["audit_version"]` (report.py:43) and both importers `assess.py` + `llm_extraction/client.py` (FACTS.importers/imports)
- `State` values are persisted and compared as strings (`c["state"] == st.value`, report.py:86); renaming members breaks old bundles and `llm_extraction/client.py`, which imports `classify.State` (FACTS.imports)
- `GREEN` must stay `{WORKING_PROVEN}`: `is_green`/`severity` and the "NOT_TESTED never green" rule depend on it (classify.py:26, 3-5; __init__.py:12)
- `ROOT = parents[3]` (report.py:12) — moving report.py in the tree silently relocates `BUNDLE_ROOT`
- `sections` keys `_agnostic`/`_discovery`/`_retirement` are an implicit contract with the section builder (report.py:107-111)
- `parent_enrichment` is deliberately absent from `PERMANENT_FUNCTIONS` pending discovery evidence (classify.py:76-78) — do not add without it

## VERIFY
```verify
grep -Fq 'AUDIT_VERSION = "conformance-audit-v1"' shared/polymath_shared/conformance/__init__.py
grep -Fq 'GREEN = frozenset({State.WORKING_PROVEN})' shared/polymath_shared/conformance/classify.py
grep -Fq 'RED = frozenset({State.BROKEN_REACHABLE, State.NOT_TESTED, State.UNKNOWN})' shared/polymath_shared/conformance/classify.py
grep -Fq 'PERMANENT_FUNCTIONS = ("GRAPH_EXTRACTION", "DOCUMENT_PROFILE", "PMAP", "CHAT")' shared/polymath_shared/conformance/classify.py
grep -Fq 'BUNDLE_ROOT = ROOT / "artifacts" / "audit"' shared/polymath_shared/conformance/report.py
grep -Fq 'datetime.now(timezone.utc)' shared/polymath_shared/conformance/report.py
test "$(grep -c -F 'NOT_TESTED' shared/polymath_shared/conformance/classify.py)" -ge 4
! grep -Fq 'try:' shared/polymath_shared/conformance/report.py
```
