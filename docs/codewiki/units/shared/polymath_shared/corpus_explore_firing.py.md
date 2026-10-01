# unit: shared/polymath_shared/corpus_explore_firing.py
anchor: shared/polymath_shared/corpus_explore_firing.py:1-224

## purpose
Miss-attribution for Corpus Explore requests: every non-firing request gets exactly ONE cause code — the FIRST gate that closed, in pipeline order — because CORPUS-EXPLORER-V1 shipped fail-open and CE7 measured 14/18 firing with unattributable misses [DERIVED: shared/polymath_shared/corpus_explore_firing.py:1-13]. Pure observation module: changes no gate, threshold, or ranking; the live path `orchestrator/api/ui.py::_add_corpus_explore_expansion` only fills in the flat `FiringState` [DERIVED: shared/polymath_shared/corpus_explore_firing.py:9-12]. "fired" = explorer added >=1 CORPUS_EXPLORE subquery to a plan whose retrieval then ran [DERIVED: shared/polymath_shared/corpus_explore_firing.py:11-12].

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `fallback_open_enabled` | def | `() -> bool` | :56-57 | orchestrator/orchestrator/api/ui.py (sole module importer) |
| `fallback_blocks_explorer` | def | `(reason: str \| None, *, fallback_open: bool \| None = None) -> bool` | :60-69 | orchestrator/orchestrator/api/ui.py |
| `FiringState` | dataclass | 26 fields with defaults | :72-100 | orchestrator/orchestrator/api/ui.py |
| `classify` | def | `(s: FiringState) -> tuple[bool, str \| None, str \| None]` | :103-154 | orchestrator/orchestrator/api/ui.py |
| `firing_receipt` | def | `(s: FiringState) -> dict` | :157-167 | orchestrator/orchestrator/api/ui.py |
| `record` | def | `(receipt: dict, *, q0: str = "") -> None` | :170-187 | orchestrator/orchestrator/api/ui.py |
| `summarize` | def | `(rows) -> dict` | :190-203 | orchestrator/orchestrator/api/ui.py |
| `turn_receipt` | def | `(plan_receipt, *, capability_on: bool, requested: bool, compiler_applied: bool, retrieval_skipped: bool, compiler_flag: str = "on") -> dict` | :206-223 | orchestrator/orchestrator/api/ui.py |

## contracts

**`classify`** (:103-154) — total, deterministic [DERIVED: :104-105]
- in: flat `FiringState` (`None` field = stage never reached [DERIVED: :74]); out: `(fired, cause, detail)`; a firing request returns `(True, None, None)` (:154).
- post: FIRST closed gate in pipeline order, so a miss has exactly one cause [DERIVED: :104-105].
- gate order (first match wins):

| # | condition (line) | cause | detail format |
|---|---|---|---|
| 1 | `not s.capability_on` (:106) | `CAPABILITY_OFF` | `None` |
| 2 | `not s.requested` (:108) | `REQUEST_OFF` | `None` |
| 3 | `not s.plan_present` (:110) | `OTHER` | `"no_plan"` |
| 4 | `s.plan_fallback and s.fallback_blocks` (:112) | `PLAN_FALLBACK` | `fallback_reason or None` |
| 5 | `not s.has_primary` (:114) | `OTHER` | `"no_primary[:reason]"` |
| 6 | `s.upstream_error` (:118) | `OTHER` | `"finish_error:{type}"` |
| 7 | `s.no_corpus` (:120) | `OTHER` | `"no_corpus"` |
| 8 | `s.atoms_error` (:122) | `ATOMS_ERROR_OR_TIMEOUT` | `"{stage or 'atoms'}:{type}"` |
| 9 | `s.n_hits is None` (:124) | `OTHER` | `"explorer_error:{e}"` or `"not_attempted"` |
| 10 | `n_hits==0 and s.fetch_errors` (:128) | `ATOMS_ERROR_OR_TIMEOUT` | `"fetch_errors:{n}"` |
| 11 | `n_hits==0 and s.atom_universe == 0` (:130) | `NO_ATOM_COVERAGE` | `"atom_universe:0"` |
| 12 | `n_hits==0` else (:132) | `ATOMS_EMPTY` | `None` or `"atom_universe:{n}"` |
| 13 | `not s.n_candidates` (:133) | `CANDIDATES_FILTERED` | `"hits:{n_hits}"` |
| 14 | `s.explorer_error` (:135) | `OTHER` | `"explorer_error:{type}"` |
| 15 | eligible False, reason `"intent_not_latent"` (:139) | `INTENT_INELIGIBLE` | `"intent:{intent}"` |
| 16 | eligible False, reason `"no_nominated_concepts"` (:141) | `CANDIDATES_FILTERED` | `"no_nominated_concepts"` |
| 17 | eligible False, other reason (:143) | `OTHER` | the reason string |
| 18 | `s.generate_error` (:144) | `BRIDGE_COMPILE_EMPTY` | `"generate_error:{type}"` |
| 19 | `s.json_status == "invalid_json"` (:146) | `BRIDGE_JSON_INVALID` | `None` |
| 20 | `not s.generated` (:148) | `BRIDGE_COMPILE_EMPTY` | `json_status or None` |
| 21 | `not s.added` (:150) | `SUBQUERY_DROPPED` | `"generated:{g} admitted:{a or 0}"` |
| 22 | `s.retrieval_skipped` (:152) | `OTHER` | `"retrieval_skipped"` |
| — | all open (:154) | fires | `(True, None, None)` |

**`fallback_blocks_explorer`** (:60-69) — pure (:63); pre: none
- switch off (env default `"0"`): returns `True` for every reason — the pre-fix gate (:66-67).
- switch on: blocks only when the reason does NOT start with one of the 5 `NO_JUDGMENT_FALLBACK_PREFIXES` (:68-69); unknown/missing reason blocks (fail closed, `""` matches no prefix) [DERIVED: :63, :68-69].

**`firing_receipt`** (:157-167)
- out keys: `contract="corpus-explore-firing-v1"`, `requested`, `fired`, `cause`, `detail`, `stages` (:166-167).
- `stages` = non-`None` subset of exactly 10 fields: `intent, n_hits, atom_universe, n_candidates, eligible, json_status, generated, admitted, added, fetch_errors` (:160-162).
- if `plan_fallback`: `stages["plan_fallback"] = fallback_reason or True` (:163-165).

**`record`** (:170-187)
- pre: writes only when `receipt["requested"]` is truthy (:174-175); un-requested turns are never recorded (:172).
- row: `{"ts": round(time.time(), 3), "q0_sha": sha1(q0)[:12], "fired", "cause", "detail", "stages"}` (:181-183) appended as JSONL (:184-185).
- post: never raises (:172, :186-187).

**`summarize`** (:190-203) — pure (:191)
- in: rows iterable; drops non-dicts and rows with `requested == False` (missing key defaults `True`) (:192).
- out: `{"n", "fired", "firing_rate": round(fired/n, 3) or None, "causes"}` with causes sorted by `(-count, name)` (:202-203).

**`turn_receipt`** (:206-223) — pure (:208-211)
- `plan_receipt` not a dict: builds receipt from `FiringState(capability_on=..., requested=..., plan_present=False)`; if cause is `OTHER`, detail becomes `"no_plan:compiler_flag={flag}"` (:212-216).
- plan-level fire + `not compiler_applied` -> `{"fired": False, "cause": OTHER, "detail": "compiler_not_applied:{flag}"}` (:219-220).
- plan-level fire + `retrieval_skipped` -> `{"fired": False, "cause": OTHER, "detail": "retrieval_skipped"}` (:221-222).
- a plan-level MISS passes through unchanged (:217-218).

## effect surface
- env read: `POLYMATH_CORPUS_EXPLORER_FALLBACK_OPEN` = `"0"` (:57); `POLYMATH_CE_FIRING_RECEIPT` = `"/private/tmp/polymath_fleet/corpus_explore_firing.jsonl"` (:179-180).
- file: append one JSON line per requested receipt to that path (:184-185); directory `polymath_fleet` is this tmp path, not a queried store [DERIVED: :180].
- clock: `time.time()` in `record` only (:181).
- Postgres tables read/written: none (FACTS `tables_read`/`tables_written` empty). Qdrant/network/subprocess: none in this unit; embed/qdrant failures arrive only as type-name strings on `FiringState.atoms_error` (:86).

## invariants
INVARIANT: `len(CAUSES) == 12` — :34-37 [DERIVED]
  fails-if: a cause returned by `classify` but missing from `CAUSES` shows up as an unlisted key in `summarize` dashboards.
INVARIANT: `classify` returns `fired=True` only when `s.added >= 1` AND `s.retrieval_skipped == False` — :150-154 [DERIVED]
  fails-if: firing counted when added subqueries never ran inflates `firing_rate`.
INVARIANT: env unset ⟹ `fallback_blocks_explorer(reason) == True` for every reason — :57, :66-67 [DERIVED]
  fails-if: default flip silently enables Phase B (explorer on fallback plans) fleet-wide.
INVARIANT: `len(q0_sha) == 12` hex chars — :181 [DERIVED]
  fails-if: JSONL log joins keyed on q0 hash break on length change.
INVARIANT: `firing_rate == round(fired / n, 3)` when `n > 0`, else `None` — :202 [DERIVED]
  fails-if: empty rows divide by zero instead of returning `None`.
INVARIANT: JSONL line growth == count of receipts with `requested` truthy — :174-175, :184-185 [DERIVED]
  fails-if: recording un-requested turns adds noise rows, contradicting :172.
INVARIANT: a plan-level miss keeps its cause unchanged at turn level — :217-218 [DERIVED]
  fails-if: turn-level aggregation reassigns causes and double-counts a miss.
INVARIANT: turn-level fire requires plan-level fire AND `compiler_applied` AND `not retrieval_skipped` — :218-222 [DERIVED]

## determinism & idempotency
determinism: DETERMINISTIC for `fallback_blocks_explorer`, `classify`, `firing_receipt`, `summarize`, `turn_receipt` (pure, :9-13, :63, :104-105, :191, :208-211); NONDETERMINISTIC for `record` (clock `time.time` :181, env :179, filesystem append :184).
idempotency: UNSAFE for `record` — append-only JSONL, replaying a receipt duplicates rows (:184-185); all other functions SAFE (no side effects).

## failure behaviour
- `record` swallows every exception: `except Exception:  # noqa: BLE001` -> `pass` (:186-187). An unwritable/missing path (e.g. `polymath_fleet` dir absent) silently drops all receipts; the caller sees a normal `None` return — the receipts themselves become the one silent fallback, against the module's stated goal (:7, :172).
- All other failures are modeled as data, not exceptions: type-name strings on `FiringState` (`atoms_error` :86, `generate_error` :94, `explorer_error` :99) plus cause codes; no error is raised in this unit [DERIVED: :21-32, :86-99].

## dumb-code flags
- `JSON_OK = "ok"` (:39) and `JSON_EMPTY_OUTPUT = "empty_output"` (:40) are defined but never compared in this unit — `classify` checks only `JSON_INVALID` (:146); `empty_output` leaks only as a raw detail string (:149) [DERIVED].
- `NO_JUDGMENT_FALLBACK_PREFIXES` mixes colon-suffixed prefixes (`"transport:"`, `"budget_exceeded:"`, `"compiler_unavailable:"`, `"join_failed:"`) with bare `"invalid_json"` (:51-52); matching is bare `startswith` (:69) — a future reason `"invalid_jsonx"` would pass as NO-JUDGMENT [INFERRED: prefix match has no delimiter].
- `"retrieval_skipped"` is spelled three ways: field name (:100), detail literal in `classify` (:153), detail literal in `turn_receipt` (:221) — rename must touch all three [DERIVED].
- Fail-closed default encoded twice: `FiringState.fallback_blocks = True` default (:80) AND `fallback_blocks_explorer` unconditional `True` when the switch is off (:66-67) [DERIVED].
- `stages["plan_fallback"] = s.fallback_reason or True` (:165) — one key holds `str | bool`.
- Default receipt path lives under `/private/tmp` (:179-180) — volatile tmp storage for the metric that counts the miss rate [INFERRED: tmp dirs are wiped on reboot].

## refactor notes
- Sole importer is `orchestrator/orchestrator/api/ui.py` (FACTS importers; the live fill path is named at :10) — renaming `FiringState` fields or `classify`'s return shape breaks it first.
- Receipt keys `contract/requested/fired/cause/detail/stages` (:166-167) and JSONL row keys `ts/q0_sha/fired/cause/detail/stages` (:181-183) are cross-component schemas: surfaced beside `corpus_activation` and inside the EvidencePacket (:158) and parsed by `summarize` (:192-199).
- Cause-code strings are the public metric vocabulary (`CAUSES` :34-37; `summarize` counts by them :199-203) — renaming breaks any dashboard over the JSONL.
- The gate ORDER in `classify` (:106-153) is the attribution contract; reordering changes which cause a multi-gate miss reports (:104-105).
- `FALLBACK_OPEN_ENV` default `"0"` is the Phase B kill switch (:53, :57) — changing the default alters behavior for every deployment with no downstream code change.
- `summarize` defaults missing `"requested"` to `True` (:192), matching `record`'s filter (:174); any other row producer must preserve that key or misses get dropped from the rate.

## VERIFY
```verify
grep -Fq 'CONTRACT = "corpus-explore-firing-v1"' shared/polymath_shared/corpus_explore_firing.py
grep -Fq 'return os.environ.get(FALLBACK_OPEN_ENV, "0") == "1"' shared/polymath_shared/corpus_explore_firing.py
grep -Fq 'return not any(r.startswith(p) for p in NO_JUDGMENT_FALLBACK_PREFIXES)' shared/polymath_shared/corpus_explore_firing.py
grep -Fq '"/private/tmp/polymath_fleet/corpus_explore_firing.jsonl"' shared/polymath_shared/corpus_explore_firing.py
grep -Fq 'except Exception:  # noqa: BLE001' shared/polymath_shared/corpus_explore_firing.py
grep -Fq 'hexdigest()[:12]' shared/polymath_shared/corpus_explore_firing.py
test "$(grep -c -F 'return False, OTHER,' shared/polymath_shared/corpus_explore_firing.py)" -ge 8
```
