# unit: shared/polymath_shared/observability.py
anchor: shared/polymath_shared/observability.py:1-309

## purpose
Extraction-pipeline observer, contract `"extraction-observability-v1"` (OBSERVER_CONTRACT_VERSION, shared/polymath_shared/observability.py:22). Records what the extraction system did; decides nothing; never sees evaluator gold; timing fields never enter semantic hashes (shared/polymath_shared/observability.py:1-12). Three modes via `POLYMATH_EXTRACTION_TRACE`: `off` (no collection, semantic path untouched), `summary` (funnel counters + reason distributions + first-loss only), `full` (complete event chains) (shared/polymath_shared/observability.py:8-11). Consumed by `workers/workers/extract_worker.py`.

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `binding_discipline` | def | (source) -> str | shared/polymath_shared/observability.py:139-145 | workers/workers/extract_worker.py |
| `event_id` | def | (payload: dict) -> str | shared/polymath_shared/observability.py:148-149 | — |
| `TraceEvent` | dataclass | fields + `envelope(contracts: dict) -> dict` | shared/polymath_shared/observability.py:153-185 | — |
| `TraceCollector` | class | `__init__(mode: str, run_id: str, contracts: dict \| None = None)`; `enabled -> bool`, `full -> bool`, `record(**kwargs) -> None`, `count(key: str, n: int = 1) -> None`, `stage_start(name)`, `stage_end(name)`, `flush(conn) -> int`, `funnel() -> dict` | shared/polymath_shared/observability.py:191-283 | workers/workers/extract_worker.py |
| `trace_mode` | def | () -> str | shared/polymath_shared/observability.py:286-288 | — |
| `extraction_contracts` | def | () -> dict | shared/polymath_shared/observability.py:291-308 | — |

Module-level vocabularies: `DISCOVERY`/`SYNTAX`/`RESCUE`/`ADMISSION`/`TRIGGER`/`ARGUMENT_BINDING`/`CANDIDATE`/`COMPILER`/`FACT` (shared/polymath_shared/observability.py:26-69), kimi_v1-lane `UD_BINDING`/`ROLE`/`TYPE_PRECHECK` (shared/polymath_shared/observability.py:77-88), `FIRST_LOSS_STAGES` (shared/polymath_shared/observability.py:104-110), binding tiers `UD_PRIMARY`/`SAFE_FALLBACK`/`BOUNDED_RECALL` + `BINDING_DISCIPLINE` (shared/polymath_shared/observability.py:117-136), `SUMMARY_EVENT_TYPES` (shared/polymath_shared/observability.py:188).

## contracts

**binding_discipline(source)**
- in: a `BindingSource` enum member or bare string (shared/polymath_shared/observability.py:139-143).
- out: one of `"UD_PRIMARY"`, `"SAFE_FALLBACK"`, `"BOUNDED_RECALL"` (shared/polymath_shared/observability.py:117-119).
- post: unknown source degrades to `"BOUNDED_RECALL"` — the observer never claims stronger provenance than it can prove (shared/polymath_shared/observability.py:142-145).
- post: 12 keys in `BINDING_DISCIPLINE`; 9 → `UD_PRIMARY`, 2 → `SAFE_FALLBACK` (`SAFE_LOCAL_PATTERN`, `DISCOURSE_ANAPHORA`), 1 → `BOUNDED_RECALL` (`BOUNDED_LINEAR_RECALL`) (shared/polymath_shared/observability.py:120-136).

**event_id(payload)**
- in: any dict.
- out: `"tev_" + sha256(json.dumps(payload, sort_keys=True, default=str)).hexdigest()[:40]` — deterministic, 40 hex chars (shared/polymath_shared/observability.py:149).

**TraceEvent.envelope(contracts)**
- pre: `contracts` dict of identity fields is merged into the base (shared/polymath_shared/observability.py:180).
- post: `trace_event_id = event_id(base)` computed over the base WITHOUT `duration_ms`; `duration_ms` is appended only after hashing, only when not `None` (shared/polymath_shared/observability.py:182-184).
- post: base always carries `observer_contract_version`, `event_type`, `decision`, `reason_code`, `run_id`, `doc_id`, `chunk_id`, `sentence_id`, `trace_parent_id`, `surface`, `char_start`, `char_end`, `detail` (shared/polymath_shared/observability.py:169-180).

**TraceCollector**
- pre: `enabled` ⟺ `mode in ("summary", "full")`; `full` ⟺ `mode == "full"` (shared/polymath_shared/observability.py:205-210).
- pre: `record` is a no-op when disabled; in summary mode it only keeps `event_type in SUMMARY_EVENT_TYPES` (shared/polymath_shared/observability.py:213-216).
- post: `stage_end` stores `round((perf_counter - t0) * 1000, 2)` ms; names not started via `stage_start` are ignored (shared/polymath_shared/observability.py:227-229).
- out: `flush(conn)` batch-inserts all events into `extraction_trace_events` with `ON CONFLICT (trace_event_id) DO NOTHING` and returns rows actually inserted — `cur.rowcount` when `>= 0`, else `len(rows)`; the in-memory `events` list is cleared (shared/polymath_shared/observability.py:231-260).
- out: `funnel()` returns `{"counts", "reason_distribution", "first_loss", "timings_ms", "events"}` (shared/polymath_shared/observability.py:262-269).

**trace_mode()**
- out: `os.environ.get("POLYMATH_EXTRACTION_TRACE", "off")` (shared/polymath_shared/observability.py:288).

**extraction_contracts()**
- out: `{"extraction_contract_hash": "pinned-per-stage-attempt", "chunk_contract_hash": s.worker.chunker, "query_policy_version": QUERY_POLICY_VERSION, "relation_pipeline": env(POLYMATH_RELATION_PIPELINE, "legacy_v1"), "worker_build_sha": _build_sha()}` (shared/polymath_shared/observability.py:298-308).
- pre: lazy imports of `polymath_shared.query_policy.QUERY_POLICY_VERSION`, `polymath_shared.settings.get_settings`, `polymath_shared.execution._build_sha` (shared/polymath_shared/observability.py:293-295).

## effect surface
- Postgres written: `extraction_trace_events` (trace_event_id, run_id, doc_id, chunk_id, sentence_id, event_type, decision, reason_code, surface, char_start, char_end, envelope) — one `executemany` per flush (shared/polymath_shared/observability.py:245-251).
- Postgres read: none (FACTS.tables_read empty).
- Env flags read: `POLYMATH_EXTRACTION_TRACE` = `"off"` (shared/polymath_shared/observability.py:288); `POLYMATH_RELATION_PIPELINE` = `"legacy_v1"` (shared/polymath_shared/observability.py:306).
- No files, network, Qdrant, or subprocess use visible.

## invariants
INVARIANT: `STEP_CODES == (UD_BINDING | ROLE | TYPE_PRECHECK) - {"TYPE_PRECHECK_NO_VIABLE_PAIR"}` — shared/polymath_shared/observability.py:100-102 [DERIVED]
  fails-if: `TYPE_PRECHECK_NO_VIABLE_PAIR` (the only terminal code of those sets) is treated as a step code and first-loss attribution loses pair-exhaustion losses.
INVARIANT: `len(FIRST_LOSS_STAGES) == 17` (chunking … graph_projection) — shared/polymath_shared/observability.py:104-110 [DERIVED]
  fails-if: stage names drift from the pipeline; `_first_loss_distribution` buckets them as `"unknown"` (shared/polymath_shared/observability.py:281).
INVARIANT: `event_id` prefix `"tev_"` and hex length 40 — shared/polymath_shared/observability.py:149 [DERIVED]
  fails-if: id shape change breaks dedupe key expectations of `extraction_trace_events`.
INVARIANT: `duration_ms` excluded from the hashed base — added post-hash only — shared/polymath_shared/observability.py:182-184, 166 [DERIVED]
  fails-if: timing jitter changes `trace_event_id`; `ON CONFLICT` then silently merges distinct events.
INVARIANT: `SUMMARY_EVENT_TYPES == {"candidate", "compiler", "fact", "first_loss", "admission", "rescue"}` (6 members) — shared/polymath_shared/observability.py:188 [DERIVED]
  fails-if: summary mode records the wrong event set (shared/polymath_shared/observability.py:215-216).
INVARIANT: `binding_discipline(x) == "BOUNDED_RECALL"` for any x not in `BINDING_DISCIPLINE` — shared/polymath_shared/observability.py:144-145 [DERIVED]
  fails-if: an enum rename makes every binding of that source read as weakest-tier provenance.
INVARIANT: `flush` returns inserted rowcount, not `len(rows)` — shared/polymath_shared/observability.py:255-258 [DERIVED]
  fails-if: stage artifacts claim events the table deduplicated away (per the code comment).

## determinism & idempotency
determinism: NONDETERMINISTIC (clock: `time.perf_counter` at shared/polymath_shared/observability.py:225 and 229; env reads at shared/polymath_shared/observability.py:288 and 306). Hashed content is deterministic: `event_id` uses `sort_keys=True` JSON + sha256 (shared/polymath_shared/observability.py:149), and clock output stays in `duration_ms`/`timings`, outside the hash (shared/polymath_shared/observability.py:182-184).
idempotency: SAFE — `flush` re-inserts are no-ops via `ON CONFLICT (trace_event_id) DO NOTHING` and the event list resets (shared/polymath_shared/observability.py:250, 259).

## failure behaviour
- `flush` swallows duplicate `trace_event_id` inserts; caller sees only the inserted count (shared/polymath_shared/observability.py:250-258).
- `record` silently drops events when mode is `off` or, in summary mode, outside `SUMMARY_EVENT_TYPES` (shared/polymath_shared/observability.py:213-216).
- `stage_end` silently ignores names never passed to `stage_start` (shared/polymath_shared/observability.py:228).
- `binding_discipline` silently degrades unknown sources to `BOUNDED_RECALL` instead of raising (shared/polymath_shared/observability.py:144-145).
- `_first_loss_distribution` buckets missing `first_loss_stage` as `"unknown"` rather than failing (shared/polymath_shared/observability.py:281).

## dumb-code flags
- `"extraction_contract_hash": "pinned-per-stage-attempt"` — a placeholder string where the field name promises a hash (shared/polymath_shared/observability.py:299).
- `import os` inside `trace_mode` (shared/polymath_shared/observability.py:287) duplicates the module-level `import os` (shared/polymath_shared/observability.py:17).
- `TraceEvent.event_type` comment enumerates `discovery|syntax|rescue|admission|trigger|binding|candidate|compiler|fact` (shared/polymath_shared/observability.py:154) but omits `first_loss`, which the collector both filters on (shared/polymath_shared/observability.py:215) and counts (shared/polymath_shared/observability.py:280) — comment vocabulary out of sync with actual event types.
- The `legacy_v1` default for `POLYMATH_RELATION_PIPELINE` (shared/polymath_shared/observability.py:306) also acts as an A/B-arm discriminator baked into every envelope id; see refactor notes.
- Unknown `BindingSource` strings are indistinguishable from typos — both become `BOUNDED_RECALL` with no signal (shared/polymath_shared/observability.py:144-145).

## refactor notes
- `OBSERVER_CONTRACT_VERSION` is stamped into every envelope (shared/polymath_shared/observability.py:170); changing the literal `"extraction-observability-v1"` changes every `trace_event_id` and splits history in `extraction_trace_events`.
- `relation_pipeline` in the contracts exists specifically so legacy_v1 and kimi_v1 arms of the same corpus/pack do not collide on `trace_event_id` (shared/polymath_shared/observability.py:302-306); removing or renaming it makes the second arm's events vanish under `ON CONFLICT`.
- The reason-code sets (shared/polymath_shared/observability.py:26-102) are the machine-readable vocabulary consumed by the importer `workers/workers/extract_worker.py`; renaming any code changes emitted envelopes.
- `flush` row tuple order (shared/polymath_shared/observability.py:236-240) must stay aligned with the INSERT column list (shared/polymath_shared/observability.py:246-248).
- `duration_ms` must remain post-hash (shared/polymath_shared/observability.py:182-184); moving it into the hashed base reintroduces timing nondeterminism into ids.

## VERIFY
```verify
grep -Fq 'OBSERVER_CONTRACT_VERSION = "extraction-observability-v1"' shared/polymath_shared/observability.py
grep -Fq 'return os.environ.get("POLYMATH_EXTRACTION_TRACE", "off")' shared/polymath_shared/observability.py
grep -Fq '"relation_pipeline": os.environ.get("POLYMATH_RELATION_PIPELINE", "legacy_v1")' shared/polymath_shared/observability.py
grep -Fq 'ON CONFLICT (trace_event_id) DO NOTHING' shared/polymath_shared/observability.py
grep -Fq 'SUMMARY_EVENT_TYPES = {"candidate", "compiler", "fact", "first_loss", "admission", "rescue"}' shared/polymath_shared/observability.py
! grep -Fq 'random' shared/polymath_shared/observability.py
test "$(grep -c -F 'time.perf_counter' shared/polymath_shared/observability.py)" -ge 2
```
