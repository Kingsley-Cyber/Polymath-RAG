# unit: shared/polymath_shared/event_adapter.py
anchor: shared/polymath_shared/event_adapter.py:1-165

## purpose
Single compatibility boundary between legacy stage-event payloads and workers: `legacy payload -> normalize_event() -> canonical payload` — shared/polymath_shared/event_adapter.py:1-14 [DERIVED]. Recovers missing required payload keys from durable state (intake artifacts, `runs` row) so workers stop crash-looping on `KeyError` — shared/polymath_shared/event_adapter.py:10-13 [DERIVED]. Unrecoverable poison raises `LegacyEventUnrecoverable` so the caller fails the ticket once with a typed reason — shared/polymath_shared/event_adapter.py:11-13 [DERIVED]. Imported by `shared/polymath_shared/worker_runtime.py` (FACTS.importers).

## public surface
| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `normalize_event` | def | `(conn: Callable[[str, tuple], Any], event_type: str, payload: dict, run_id: str) -> dict` | shared/polymath_shared/event_adapter.py:99-164 | shared/polymath_shared/worker_runtime.py (module import; exact symbols unknown) |
| `LegacyEventUnrecoverable` | class (Exception) | `__init__(reason: str)`; exposes `.reason` | shared/polymath_shared/event_adapter.py:37-43 | shared/polymath_shared/worker_runtime.py (module import; exact symbols unknown) |
| `_REQUIRED` | module constant | dict: event_type -> required-key tuple | shared/polymath_shared/event_adapter.py:24-34 | — (internal) |
| `_row_value` | def (private) | `(row: Any, key: str) -> Any` | shared/polymath_shared/event_adapter.py:46-57 | — (internal) |
| `_recover_from_intake_artifact` | def (private) | `(conn: Callable[[str, tuple], Any], run_id: str) -> Optional[dict]` | shared/polymath_shared/event_adapter.py:60-96 | — (internal) |

## contracts

**normalize_event(conn, event_type, payload, run_id) -> dict** — shared/polymath_shared/event_adapter.py:99-164
- in: `payload` may be `None` or dict; normalized via `dict(payload or {})` — shared/polymath_shared/event_adapter.py:107 [DERIVED]
- in: `event_type` looked up in `_REQUIRED`; unknown types get `()` — shared/polymath_shared/event_adapter.py:108 [DERIVED]
- pre: `conn.execute(sql, params)` returns a cursor-like object with `.fetchall()` / `.fetchone()` — shared/polymath_shared/event_adapter.py:65-72, shared/polymath_shared/event_adapter.py:130-133, shared/polymath_shared/event_adapter.py:147-150 [DERIVED]
- out: copy of payload with every key in `_REQUIRED[event_type]` truthy, else raises — shared/polymath_shared/event_adapter.py:109-111, shared/polymath_shared/event_adapter.py:160-163 [DERIVED]
- post: input `payload` never mutated (copied first); recovered keys merged with `setdefault`, never overwrite — shared/polymath_shared/event_adapter.py:107, shared/polymath_shared/event_adapter.py:117, shared/polymath_shared/event_adapter.py:141, shared/polymath_shared/event_adapter.py:156 [DERIVED]

**LegacyEventUnrecoverable** — shared/polymath_shared/event_adapter.py:37-43
- out: `.reason` == the `reason` string passed; message starts with `LEGACY_EVENT_UNRECOVERABLE ` — shared/polymath_shared/event_adapter.py:41-43, shared/polymath_shared/event_adapter.py:162 [DERIVED]

**_row_value(row, key)** — shared/polymath_shared/event_adapter.py:46-57
- in: dict row (dict_row cursor) or tuple row
- out: `row.get(key)` for dicts; `row[0] if row else None` for tuples — shared/polymath_shared/event_adapter.py:55-57 [DERIVED]

**_recover_from_intake_artifact(conn, run_id)** — shared/polymath_shared/event_adapter.py:60-96
- out: `{"doc_id": card["doc_id"]}` plus optional `"profile"`, or `None` — shared/polymath_shared/event_adapter.py:90-96 [DERIVED]
- reads latest intake artifact: `SELECT payload FROM artifacts WHERE run_id=%s AND stage='intake' ORDER BY created_at DESC LIMIT 1` — shared/polymath_shared/event_adapter.py:65-72 [DERIVED]

## effect surface
| effect | detail | anchor |
|---|---|---|
| Postgres read | `artifacts`: columns `payload`, filter `run_id`, `stage='intake'`, order `created_at DESC`, `LIMIT 1` | shared/polymath_shared/event_adapter.py:65-72 |
| Postgres read | `runs`: `SELECT metadata FROM runs WHERE run_id=%s` | shared/polymath_shared/event_adapter.py:130-133 |
| Postgres read | `runs`: `SELECT corpus_id FROM runs WHERE run_id=%s` | shared/polymath_shared/event_adapter.py:147-150 |
| Postgres write | none — module contains only SELECTs; FACTS.tables_written == [] | shared/polymath_shared/event_adapter.py:65-72 |
| Qdrant / files / network / subprocess | none visible | — |
| Env flags read | none visible | — |
| Logging | logger name `"event-adapter"`; `log.info` on each recovery, `log.warning` on unparseable artifact | shared/polymath_shared/event_adapter.py:21, shared/polymath_shared/event_adapter.py:85-86 |

## invariants
INVARIANT: `_REQUIRED["chunked.v1"]` == `("doc_id",)` — shared/polymath_shared/event_adapter.py:25 [DERIVED]
  fails-if: extract workers crash `KeyError: 'doc_id'` again (measured 408 events, shared/polymath_shared/event_adapter.py:4-5).
INVARIANT: `_REQUIRED["intake.v1"]` == `("corpus_id", "source_name")` — both keys required — shared/polymath_shared/event_adapter.py:33 [DERIVED]
  fails-if: corpus-only recovery crashes `KeyError('source_name')` (shared/polymath_shared/event_adapter.py:30-31).
INVARIANT: every recovery write is `setdefault`; count of overwrite writes == 0 — shared/polymath_shared/event_adapter.py:117, shared/polymath_shared/event_adapter.py:141, shared/polymath_shared/event_adapter.py:156 [DERIVED]
  fails-if: a stale durable value would clobber a fresher value already in the event payload.
INVARIANT: missing test is `not canonical.get(k)` — falsy values (`""`, `None`, `0`) count as missing — shared/polymath_shared/event_adapter.py:109 [DERIVED]
  fails-if: an empty-string key present in the payload would pass a presence-only (`k in canonical`) check and crash the worker.
INVARIANT: `_row_value(tuple_row, key)` == `row[0]` for every `key` — shared/polymath_shared/event_adapter.py:57 [DERIVED]
  fails-if: any caller's SELECT grows a second column; tuple path silently returns the wrong column.
INVARIANT: unknown `event_type` -> `required == ()` -> payload returned unchanged — shared/polymath_shared/event_adapter.py:108, shared/polymath_shared/event_adapter.py:110-111 [DERIVED]
  fails-if: adding an event type to `_REQUIRED` without a recovery branch makes every legacy payload of it raise (shared/polymath_shared/event_adapter.py:160-163).

## determinism & idempotency
determinism: NONDETERMINISTIC (db — result depends on latest `artifacts` row by `created_at DESC` shared/polymath_shared/event_adapter.py:69 and on `runs.metadata` / `runs.corpus_id` shared/polymath_shared/event_adapter.py:130-150; no clock/random/uuid/network/env use).
idempotency: SAFE — no writes; output is a pure function of `(payload, db state)`; input dict copied, never mutated — shared/polymath_shared/event_adapter.py:107 [DERIVED].

## failure behaviour
- `except Exception: return None` around the artifacts SELECT — SWALLOWED — shared/polymath_shared/event_adapter.py:73-74 [DERIVED]. Caller of `normalize_event` then sees `LegacyEventUnrecoverable` at shared/polymath_shared/event_adapter.py:160-163 instead of the DB error; root cause masked.
- `except Exception: row = None` around `SELECT metadata FROM runs` — handled: assign — shared/polymath_shared/event_adapter.py:134-135 [DERIVED]; metadata recovery silently skipped.
- `except Exception: row = None` around `SELECT corpus_id FROM runs` — handled: assign — shared/polymath_shared/event_adapter.py:151-152 [DERIVED]; corpus_id fallback silently skipped.
- Typed refusal: `LegacyEventUnrecoverable` with message `LEGACY_EVENT_UNRECOVERABLE {event_type}: missing {missing} after adapter recovery` — shared/polymath_shared/event_adapter.py:161-163 [DERIVED].
- Unparseable artifact payload: `log.warning("intake artifact payload unparseable; cannot recover")` then `continue` — shared/polymath_shared/event_adapter.py:84-87 [DERIVED].

## dumb-code flags
- `key` parameter unused on the tuple path of `_row_value` (`return row[0] if row else None`) — correct only because every call site is single-column — shared/polymath_shared/event_adapter.py:57, shared/polymath_shared/event_adapter.py:67, shared/polymath_shared/event_adapter.py:131, shared/polymath_shared/event_adapter.py:148 [DERIVED].
- FACTS renders `_REQUIRED` values as lists (`["doc_id"]`); source has tuples (`("doc_id",)`) — equal for membership, unequal under `==` — shared/polymath_shared/event_adapter.py:25, shared/polymath_shared/event_adapter.py:33 [DERIVED].
- Event-type literals duplicated: `"chunked.v1"` at shared/polymath_shared/event_adapter.py:25 and :113; `"intake.v1"` at :33 and :124 [DERIVED].
- `LIMIT 1` makes the `for row in rows or []` loop iterate at most once — loop machinery beyond the first row is dead — shared/polymath_shared/event_adapter.py:69, shared/polymath_shared/event_adapter.py:75 [DERIVED].
- Signature declares `payload: dict` but `None` is tolerated via `dict(payload or {})` — shared/polymath_shared/event_adapter.py:100, shared/polymath_shared/event_adapter.py:107 [DERIVED].
- `intake_payload` merge copies ALL its keys into canonical (comment says it also carries `media_type`, `content`), not just the required two — shared/polymath_shared/event_adapter.py:126-128, shared/polymath_shared/event_adapter.py:139-141 [DERIVED].

## refactor notes
- Blast radius: `shared/polymath_shared/worker_runtime.py` imports this module (FACTS.importers) — renaming `normalize_event`, `LegacyEventUnrecoverable`, or `.reason` breaks it; `.reason` is documented as carried "for last_error" — shared/polymath_shared/event_adapter.py:38-39 [DERIVED].
- Message prefix `LEGACY_EVENT_UNRECOVERABLE ` is a literal contract at shared/polymath_shared/event_adapter.py:162 — callers/tests matching on it break if the string changes [INFERRED: typed reason string is the module's stated failure interface, shared/polymath_shared/event_adapter.py:11-13].
- `setdefault` merge semantics at shared/polymath_shared/event_adapter.py:117, :141, :156 must not become assignment — recovery must never overwrite present keys.
- Recovery couples to schema `artifacts(run_id, stage, created_at, payload)` and `runs(run_id, metadata, corpus_id)` — because SELECT failures are swallowed at shared/polymath_shared/event_adapter.py:73, :134, :151, schema drift converts silently into permanent `LegacyEventUnrecoverable` raises.
- Any new `_REQUIRED` entry needs its own recovery branch or legacy payloads of that type go straight to the raise — shared/polymath_shared/event_adapter.py:108, shared/polymath_shared/event_adapter.py:160-163.

## VERIFY
```verify
grep -Fq '"chunked.v1": ("doc_id",)' shared/polymath_shared/event_adapter.py
grep -Fq '"intake.v1": ("corpus_id", "source_name")' shared/polymath_shared/event_adapter.py
grep -Fq 'LEGACY_EVENT_UNRECOVERABLE' shared/polymath_shared/event_adapter.py
grep -Fq 'ORDER BY created_at DESC LIMIT 1' shared/polymath_shared/event_adapter.py
! grep -Fq 'INSERT' shared/polymath_shared/event_adapter.py
test "$(grep -c -F 'setdefault' shared/polymath_shared/event_adapter.py)" -ge 3
grep -Eq 'def normalize_event\(conn' shared/polymath_shared/event_adapter.py
```
