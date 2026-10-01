# unit: shared/polymath_shared/conformance/evidence.py
anchor: shared/polymath_shared/conformance/evidence.py:1-172

## purpose
Evidence collector for the conformance assessment: gathers durable limiter state, stage activity, query receipts, a static reader/writer census, read-only route probes, and git/runtime/config fingerprints — "the observations the assessment turns into verdicts" — shared/polymath_shared/conformance/evidence.py:1 [DERIVED]. All functions are read-only observers; no table is written anywhere in the unit (FACTS `tables_written` empty; shared/polymath_shared/conformance/evidence.py:13-172) [DERIVED].

## public surface
| symbol | kind | signature (params -> return) | anchor | used by |
| controller_state | def | conn -> dict[str, dict] | shared/polymath_shared/conformance/evidence.py:13-25 | — |
| stage_activity | def | conn, window="24 hours" -> dict[str, dict] | shared/polymath_shared/conformance/evidence.py:28-36 | — |
| query_receipt_summary | def | conn, window="7 days" -> dict | shared/polymath_shared/conformance/evidence.py:39-77 | — |
| reader_writer_census | def | tables: list[str] -> dict[str, dict] | shared/polymath_shared/conformance/evidence.py:80-121 | — |
| probe_routes | def | paths: list[str], base=None, timeout=10 -> dict[str, dict] | shared/polymath_shared/conformance/evidence.py:124-141 | — |
| git_state | def | () -> dict | shared/polymath_shared/conformance/evidence.py:144-149 | — |
| runtime_bundle | def | conn -> dict | shared/polymath_shared/conformance/evidence.py:152-162 | — |
| config_hashes | def | () -> dict | shared/polymath_shared/conformance/evidence.py:165-172 | — |

No importer data in FACTS; only outgoing import known: `polymath_shared.execution_bundle.compute_execution_bundle` (shared/polymath_shared/conformance/evidence.py:158, FACTS.imports) [DERIVED].

## contracts
**controller_state** — shared/polymath_shared/conformance/evidence.py:13-25
- in: `conn` with `.execute` against table `llm_controller_state(key, state, updated_at)` — :17.
- out: map lane name -> `{day, day_count, effective, ceiling, decreases, increases, last_dispatch_at, updated_at}` — :20-24.
- post: row keys of form `llm_cloud[<lane>]` are stripped to `<lane>`; other keys pass through — :18; non-dict `state` coerced to `{}` — :19; `updated_at` stringified or `None` — :24.

**stage_activity** — shared/polymath_shared/conformance/evidence.py:28-36
- in: `conn`, `window` default `"24 hours"` — :28.
- out: `{stage: {recent, total, last}}`; `last` is `str(...)` or `None` — :35-36.
- pre: table `stage_tickets(stage, updated_at)` — :30-34.

**query_receipt_summary** — shared/polymath_shared/conformance/evidence.py:39-77
- in: `conn`, `window` default `"7 days"` — :39.
- out (success): `{"available": True, "window": window, "overall": {...}, "by_kind_mode": {}}` — :77; per-bucket counters `ok, error, grounded, abstained, cited, last_at` — :61, :64-65; by-mode key `f"{kind}:{mode or 'unspecified'}"` — :63.
- mapping: grounded = `verdict IN ('supported','generated')` — :51; abstained = `verdict = 'insufficient_evidence'` — :52; cited = `citations > 0` — :53.
- out (failure): `{"available": False, "error": str(exc)[:200]}` — :59.

**reader_writer_census** — shared/polymath_shared/conformance/evidence.py:80-121
- in: list of table names.
- out: `{table: {"readers": sorted(files), "writers": sorted(files)}}` — :120; on subprocess failure `{table: {}}` — :105.
- classification: writer if line contains `insert into`, `update `, `delete from`, `create table`, or `alter table` (lowercased); otherwise reader — :112-116.
- scope: only files ending `.py`, `.sql`, `.ts`, `.tsx`, `.md` — :110; `docs/` and `tests/` deliberately included — :88-96.

**probe_routes** — shared/polymath_shared/conformance/evidence.py:124-141
- in: `paths`, `base=None` -> env `POLYMATH_BASE_URL` default `'http://127.0.0.1:7200'` — :127; `timeout=10` — :125.
- out: `{path: {"ok": bool, "status": int, "error": str?}}` — :134, :137-138, :140.
- pre/behaviour: paths containing `"{"` (parameterized) are skipped — :130-131; GET-only via `urlopen(f"{base}{p}")` — :133.
- post: HTTP 400/422 reported `ok: True` with `"missing required parameters"` — :137-138.

**git_state** — shared/polymath_shared/conformance/evidence.py:144-149
- out: `{"sha", "branch", "dirty": bool, "unpushed"}` from `git rev-parse/branch/status/rev-list` — :147-149; `unpushed` falls back to `"unknown"` — :149.

**runtime_bundle** — shared/polymath_shared/conformance/evidence.py:152-162
- out: `{"live": [hash16...], "repo_computed": hash16 or "", "uniform": len(live) <= 1}` — :156-162.
- pre: `worker_registrations(execution_bundle_hash, heartbeat_at)` — :154-155; live = heartbeats within `interval '60 seconds'` — :155.

**config_hashes** — shared/polymath_shared/conformance/evidence.py:165-172
- out: `{relpath: sha256[:16]}` over `config/cloud_providers.json` and `config/extraction_models/limiter.yaml`, only when the file exists — :168-171.

## effect surface
- Postgres read: `llm_controller_state` (:17), `stage_tickets` (:34), `query_receipts` (:55), `worker_registrations` (:154-155). Written: none (FACTS `tables_written: []`).
- Network: `urllib.request.urlopen(f"{base}{p}")` GET probes (:133); base from env `POLYMATH_BASE_URL` = `'http://127.0.0.1:7200'` (:127).
- Subprocess: `git grep -n -i -- <table>` with `timeout=45`, `cwd=ROOT` (:101-102); `git rev-parse/branch/status/rev-list` (:146-149).
- Files read: `config/cloud_providers.json`, `config/extraction_models/limiter.yaml` (:168); repo root resolved as `Path(__file__).resolve().parents[3]` (:10).
- Import at call time: `polymath_shared.execution_bundle.compute_execution_bundle` (:158).

## invariants
INVARIANT: `query_receipt_summary` default window `"7 days"` > `stage_activity` default window `"24 hours"` — shared/polymath_shared/conformance/evidence.py:28, :39 [DERIVED]
  fails-if: tight equal windows mark low-volume GRAPH/WILDCARD modes NOT_TESTED despite working (:44-46).
INVARIANT: writer keyword set has exactly 5 members (`insert into`, `update `, `delete from`, `create table`, `alter table`) — shared/polymath_shared/conformance/evidence.py:113 [DERIVED]
  fails-if: any other write phrasing (e.g. `TRUNCATE`) silently counts the file as a reader only.
INVARIANT: census extension filter == (".py", ".sql", ".ts", ".tsx", ".md") — shared/polymath_shared/conformance/evidence.py:110 [DERIVED]
  fails-if: mentions in other file types are dropped → zero-reader false negative → wrong RETIRE_CANDIDATE (documented measured incident, :90-96).
INVARIANT: readers ∪ writers contains no path with `"migrations/"` — shared/polymath_shared/conformance/evidence.py:118-119 [DERIVED]
  fails-if: creation DDL counted as a live writer, so a migration-only table can never retire.
INVARIANT: `runtime_bundle.live` entries and `repo_computed` are both 16-char hash prefixes (`LEFT(execution_bundle_hash,16)`, `[:16]`) — shared/polymath_shared/conformance/evidence.py:154, :159 [DERIVED]
  fails-if: comparing a full hash against a 16-char prefix always mismatches → false non-uniform verdict.
INVARIANT: `uniform` ⇔ `len(live) <= 1` — shared/polymath_shared/conformance/evidence.py:162 [DERIVED]
  fails-if: 0 live workers reported as "uniform", conflating "nobody running" with "everyone agrees" [INFERRED: `<= 1` includes the empty case].
INVARIANT: route `ok` ⇔ HTTP 2xx, or HTTPError code in `(400, 422)` — shared/polymath_shared/conformance/evidence.py:134, :137 [DERIVED]
  fails-if: a route that legitimately 400s is reported healthy.

## determinism & idempotency
determinism: NONDETERMINISTIC (subprocess: git grep shared/polymath_shared/conformance/evidence.py:101, git shared/polymath_shared/conformance/evidence.py:146; network: urlopen shared/polymath_shared/conformance/evidence.py:133; db clock `now()` shared/polymath_shared/conformance/evidence.py:31, :56, :155; env `POLYMATH_BASE_URL` shared/polymath_shared/conformance/evidence.py:127)
idempotency: SAFE (zero table writes per FACTS, GET-only probes shared/polymath_shared/conformance/evidence.py:133, read-only git subcommands shared/polymath_shared/conformance/evidence.py:101, :146)

## failure behaviour
- `query_receipt_summary`: `Exception` swallowed → caller sees `{"available": False, "error": str(exc)[:200]}` — shared/polymath_shared/conformance/evidence.py:58-59.
- `reader_writer_census`: `Exception` around `git grep` → `out[t] = {}`, loop continues — shared/polymath_shared/conformance/evidence.py:104-106. The failure shape `{}` differs from the success shape `{"readers": [...], "writers": [...]}` (:120); a consumer doing `.get("readers", [])` reads "no readers", which per the docstring (:85-86) enables a wrong deletion [INFERRED].
- `probe_routes`: `HTTPError` → `ok = e.code in (400, 422)`, error string `"missing required parameters"` or `e.reason` — :135-138; any other `Exception` → `{"ok": False, "status": None, "error": "<TypeName>: <msg>"}` — :139-140.
- `runtime_bundle`: `Exception` from `compute_execution_bundle` → `repo = ""`; live list still returned — :160-161.
- `git_state`: empty `rev-list --count` output → `unpushed = "unknown"` — :149.
- Nothing raises; every path returns a dict.

## dumb-code flags
- `except urllib.error.HTTPError` at :135, but only `import urllib.request` exists (:7) — the name resolves only via the transitive package attribute; the `# noqa: F821` at :135 concedes the missing import.
- `window` is f-string-interpolated into the SQL `interval '{window}'` in two places — :31 and :56 — a duplicated trusted-string SQL pattern.
- Writer keyword `"update "` carries a trailing space (:113) — a line ending in `UPDATE` with no following character is classified as a reader.
- Comment justifies only 422 as ok (:136) but the code also accepts 400 (:137).
- FACTS `tables_read` lists `llm_controller_state`, `query_receipts`, `worker_registrations` and omits `stage_tickets`, though it is SELECTed at :34 — static-analysis gap for downstream consumers of the FACTS feed.
- Magic numbers: git timeout `45` (:102), probe timeout `10` (:125), heartbeat `interval '60 seconds'` (:155), error truncation `[:200]` (:59), hash truncation `16` (:154, :159, :171), `parents[3]` (:10).
- Duplicated accumulation loop `for bucket in (d, overall)` — :66-76.

## refactor notes
- `ROOT = Path(__file__).resolve().parents[3]` (:10) is the anchor for every git call (:101-102, :146) and config path (:169); relocating this file silently breaks all of them.
- Return shapes are the assessment contract: controller_state value keys (:20-24), the `{"available": ...}` envelope (:59, :77), census `{"readers", "writers"}` (:120), `git_state` keys (:147-149), `runtime_bundle` keys (:162) — any rename breaks verdict consumers.
- The census failure shape `{}` (:105) vs success `{"readers": [...], "writers": [...]}` (:120) is load-bearing for retirement decisions; unify only with downstream sign-off.
- Default windows `"24 hours"` / `"7 days"` are semantic policy, not tuning knobs (:43-46) — changing them alters NOT_TESTED verdicts.
- `probe_routes` 400/422-ok semantics (:137-138) conflates "requires params" with "healthy"; tightening it changes route health verdicts.

## VERIFY
```verify
grep -Fq 'llm_cloud[' shared/polymath_shared/conformance/evidence.py
grep -Fq 'http://127.0.0.1:7200' shared/polymath_shared/conformance/evidence.py
grep -Eq 'interval .\{window\}' shared/polymath_shared/conformance/evidence.py
grep -Fq 'insufficient_evidence' shared/polymath_shared/conformance/evidence.py
grep -Fq 'migrations/' shared/polymath_shared/conformance/evidence.py
! grep -Fq 'import urllib.error' shared/polymath_shared/conformance/evidence.py
test "$(grep -c -F 'subprocess.run' shared/polymath_shared/conformance/evidence.py)" -ge 2
```
