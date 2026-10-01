# unit: adapters/ecommerce/python/adapter_receipt.py
anchor: adapters/ecommerce/python/adapter_receipt.py:1-488

## purpose
Converts a HarnessActionV1 (issued by the Polymath cognitive adapter `trail.product_discovery` in GOVERNED mode) plus this skill's harvested observations / field_records / supplier_candidates into a HarnessResearchReceiptV1 for `adapter_submit kind=receipt`. adapters/ecommerce/python/adapter_receipt.py:2-8 [DERIVED]
Fetches/searches/ranks nothing, carries no score, never invents provenance, never re-labels roles — TrailSignal decides admission. adapters/ecommerce/python/adapter_receipt.py:8-17 [DERIVED]
CLI with `build` and `validate` subcommands. adapters/ecommerce/python/adapter_receipt.py:19-22 [DERIVED]

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| polarity_for | def | (admitted: dict, hypothesis_id: str \| None) -> str \| None | adapters/ecommerce/python/adapter_receipt.py:87-95 | — |
| load_schema | def | () -> dict | adapters/ecommerce/python/adapter_receipt.py:99-101 | — |
| schema_sha256 | def | () -> str | adapters/ecommerce/python/adapter_receipt.py:104-106 | — |
| schema_errors | def | (value, spec: dict, path: str = "$") -> list[str] | adapters/ecommerce/python/adapter_receipt.py:116-160 | — |
| source_class_for | def | (url: str, source_identity: dict \| None = None) -> str \| None | adapters/ecommerce/python/adapter_receipt.py:177-189 | — |
| trail_role_for | def | (item: dict) -> str \| None | adapters/ecommerce/python/adapter_receipt.py:192-204 | — |
| build_receipt | def | (action, *, observations=None, field_records=None, supplier_candidates=None, harness_id, started_at, completed_at, tool_trace=None, limitations=None) -> tuple[dict, dict] | adapters/ecommerce/python/adapter_receipt.py:280-387 | — |
| validate_receipt | def | (receipt: dict, action: dict \| None = None) -> list[str] | adapters/ecommerce/python/adapter_receipt.py:403-430 | — |
| now_iso | def | () -> str | adapters/ecommerce/python/adapter_receipt.py:433-434 | — |
| main | def | (argv: list \| None = None) -> int | adapters/ecommerce/python/adapter_receipt.py:448-484 | CLI `__main__` adapters/ecommerce/python/adapter_receipt.py:487-488 |

## contracts

**build_receipt** adapters/ecommerce/python/adapter_receipt.py:280-387
- in: action dict; keyword-only observations / field_records / supplier_candidates / tool_trace / limitations; strings harness_id, started_at, completed_at (280-282)
- pre: each item needs an `https?://` source, RFC 3339 `retrieved_at`, and a present `published_at_if_known` (null allowed) — else omitted with that reason (211-222, 304-317)
- out: `(receipt, report)`; report carries omitted {id, lane, reason}, omitted_by_reason, notes, roles, source_classes, queries_recorded, errors (382-386)
- post: "same inputs -> same bytes"; every omission and clamp also written into receipt `limitations` (283-285)
- budget: max_sources ≤ 100, max_obs ≤ 200 even when the action budget is larger (287-288)

**validate_receipt** adapters/ecommerce/python/adapter_receipt.py:403-430
- in: receipt dict, optional action dict
- out: list of violations; empty = `adapter_submit kind=receipt` provenance check accepts it (404)
- checks: byte-copied JSON Schema (408); observation `source_id` ∈ sources (411-414); no key matching `score|rank|weight` anywhere (81, 415); with action: `action_id`/`run_id` match (417-420), hypothesis ids ⊆ action's (421-426), tool_trace intents ⊆ action's search_intents (427-429)

**trail_role_for** adapters/ecommerce/python/adapter_receipt.py:192-204
- `contradicts is True` -> `"contradiction"` (195-196); explicit `evidence_role_claimed` returned verbatim if in TRAIL_ROLES else None, no fallthrough (197-199); else first `evidence_roles` entry with a non-None ROLE_MAP value (200-203)

**source_class_for** adapters/ecommerce/python/adapter_receipt.py:177-189
- PATTERN_CLASS substring first (181-183), then DOMAIN_CLASS host/subdomain (184-187), then PLATFORM_CLASS[platform] / FAMILY_CLASS[source_family] (188-189); None = will not guess

**polarity_for** adapters/ecommerce/python/adapter_receipt.py:87-95
- hypothesis-specific relation via RELATION_POLARITY when `hypothesis_relations` names that hypothesis_id, else the record's global `polarity`; NEUTRAL -> None (83-84, 91-95)

**schema_errors** adapters/ecommerce/python/adapter_receipt.py:116-160
- JSON-Schema subset read from the byte-copied schema at runtime; `required` = key PRESENT (null is a value); models.validate deliberately NOT used (117-120)

**_supplier_items** adapters/ecommerce/python/adapter_receipt.py:246-276
- each supplier_candidate becomes up to two observations (price, MOQ) parsed by `executors._parse_price` / `_parse_moq`, or one SUPPLIER_AVAILABILITY listing row when neither parses (256-275)

## effect surface
- Postgres tables: none read/written (FACTS tables_read/tables_written empty)
- Files read: `schemas/harness_receipt.schema.json` (36, 100, 105); CLI JSON inputs via `_load` — --action, --observations, --field-records, --supplier-candidates, --tool-trace, --receipt (438-445, 451-465)
- Files written: --out receipt JSON, `indent=1, ensure_ascii=False` (479-480)
- Runtime module import: `executors` from same dir via `sys.path.insert` (250-251); calls `_ex._parse_price` / `_ex._parse_moq` (256-257)
- Network / subprocesses: none
- Env flags: none read
- Clock: `_dt.datetime.now(_dt.timezone.utc)` (434), reached only as default for --completed-at (459, 477)

## invariants
INVARIANT: max_sources = min(budget.max_sources or 100, 100) and max_obs = min(budget.max_observations or 200, 200) — adapters/ecommerce/python/adapter_receipt.py:287-288,43 [DERIVED]
  fails-if: receipt exceeds contract caps and validate_receipt schema check rejects it (408)
INVARIANT: observation.hypothesis_ids ⊆ action.hypothesis_ids — adapters/ecommerce/python/adapter_receipt.py:342,421-426 [DERIVED]
  fails-if: build drops foreign ids with a note (338-340); validate flags them as errors
INVARIANT: every emitted observation.source_id ∈ receipt.sources (unused source rows filtered out) — adapters/ecommerce/python/adapter_receipt.py:350,380,411-414 [DERIVED]
  fails-if: orphan observation fails validate_receipt
INVARIANT: no key matching regex `score|rank|weight` anywhere in the receipt — adapters/ecommerce/python/adapter_receipt.py:81,415 [DERIVED]
  fails-if: "forbidden key" error; a score cannot ride along (11-12)
INVARIANT: kept hypothesis_relations ⊆ linked hypotheses × {"SUPPORTS", "CONTRADICTS", "NEUTRAL"}; linked hypothesis ids capped [:64] — adapters/ecommerce/python/adapter_receipt.py:342-346 [DERIVED]
  fails-if: relations naming unlinked hypotheses or unknown relations are dropped with a note (345-346)
INVARIANT: every non-None ROLE_MAP value ∈ TRAIL_ROLES — adapters/ecommerce/python/adapter_receipt.py:48-57 [INFERRED: comparing the two literals; trail_role_for returns mapped values unchecked]
  fails-if: a role TrailSignal rejects would pass the omit gate at 312-313
INVARIANT: source row identity = `_sid("src_", url, source_date or "")`; budget counts pages (urls), not rows — adapters/ecommerce/python/adapter_receipt.py:326-333 [DERIVED]
  fails-if: same page with differing dates wrongly merges or splits source rows
INVARIANT: an item inherits `page_published_at` only when its own `published_at_if_known` is null — adapters/ecommerce/python/adapter_receipt.py:322-323 [DERIVED]
  fails-if: TrailSignal would see a source fresher than it is (319-321)
INVARIANT: every omitted item yields a limitations line with count and reason — adapters/ecommerce/python/adapter_receipt.py:366-370 [DERIVED]
  fails-if: dossier and TrailSignal see a different account than the harness (284-285)
INVARIANT: tool_trace rows only for intents in the action, aggregated per (intent, tool_class), ≤ 200 rows — adapters/ecommerce/python/adapter_receipt.py:351-362,427-429 [DERIVED]
  fails-if: validation error "tool trace intent … is not one the action issued"

## determinism & idempotency
determinism: NONDETERMINISTIC (clock `_dt.datetime.now` at adapters/ecommerce/python/adapter_receipt.py:434; core build documented "same inputs -> same bytes" at adapters/ecommerce/python/adapter_receipt.py:283; clock reached only when --completed-at omitted, adapters/ecommerce/python/adapter_receipt.py:459,477)
idempotency: SAFE (validate is read-only; build only overwrites the --out file adapters/ecommerce/python/adapter_receipt.py:479-480; rerun with explicit --completed-at reproduces identical bytes adapters/ecommerce/python/adapter_receipt.py:283)

## failure behaviour
- No try/except exists in the unit — missing schema or input files surface as tracebacks to the CLI caller. adapters/ecommerce/python/adapter_receipt.py:99-101,438-445 [INFERRED: no handler token anywhere in SOURCE]
- Harvest-provenance failures are omissions with reason strings (e.g. no `retrieved_at`, missing `published_at_if_known`), never errors; they land in `limitations`. adapters/ecommerce/python/adapter_receipt.py:211-222,316-317,366-370 [DERIVED]
- Zero admitted observations is recorded as a limitation: "no observation in this receipt: nothing harvested met the provenance contract (a finding, not a failure to hide)". adapters/ecommerce/python/adapter_receipt.py:376-377 [DERIVED]
- Query budget overrun is recorded as a "BUDGET EXCEEDED" note, not rewritten. adapters/ecommerce/python/adapter_receipt.py:364-365 [DERIVED]
- Exit codes: `build` 0 ok / 1 when report["errors"] non-empty / 2 when --strict and anything omitted or noted; `validate` 0 clean / 1 violations. adapters/ecommerce/python/adapter_receipt.py:472,482-484 [DERIVED]

## dumb-code flags
- Two sources of truth for caps: hardcoded `SCHEMA_MAX = {"sources": 100, "observations": 200, "tool_trace": 200, "limitations": 50}` vs the byte-copied schema enforced at runtime. adapters/ecommerce/python/adapter_receipt.py:43,116-120 [INFERRED: drift if the contract tightens]
- Duplicate detection keys the full oid (`seen_ids.add(oid)`) while `observation_id` is emitted as `oid[:200]` — ids sharing a 200-char prefix pass the check but collide on output. adapters/ecommerce/python/adapter_receipt.py:302,341,347 [INFERRED]
- TRAIL_ROLES `"seasonality"` and `"risk"` have no ROLE_MAP key producing them — reachable only via explicit `evidence_role_claimed`. adapters/ecommerce/python/adapter_receipt.py:48-57,197-199 [DERIVED]
- Magic numbers: [:64] hypothesis cap (342), foreign[:4] (340), sorted(intents)[:6] (357), url[:2000] (333). adapters/ecommerce/python/adapter_receipt.py:342,340,357,333 [DERIVED]
- `sys.path.insert` + runtime `import executors` inside `_supplier_items` on every call. adapters/ecommerce/python/adapter_receipt.py:250-251 [DERIVED]
- ROLE_MAP carries explicit None markers `MECHANISM_SUPPORT`, `INSIDER_LANGUAGE` as vocabulary documentation. adapters/ecommerce/python/adapter_receipt.py:54 [DERIVED]

## refactor notes
- Contract pin blast radius: SCHEMA_PATH byte-copy + SCHEMA_SHA256; a contract change = re-copy + re-pin in the same slice; tests/run_all.py fails on drift. adapters/ecommerce/python/adapter_receipt.py:36-40 [DERIVED]
- CLI flag set (--action, --observations, --field-records, --supplier-candidates, --tool-trace, --harness-id, --started-at, --completed-at, --limitation, --out, --strict) is the documented invocation surface. adapters/ecommerce/python/adapter_receipt.py:19-22,451-462 [DERIVED]
- `executors._parse_price` / `_parse_moq` are private parsers consumed here; renaming them breaks `_supplier_items`. adapters/ecommerce/python/adapter_receipt.py:256-257 [DERIVED]
- ROLE_MAP mirrors graph/policies.yaml `evidence_roles.valid`; DOMAIN_CLASS / PATTERN_CLASS mirror TrailSignal `data/source_capabilities.csv` — both sides must move together. adapters/ecommerce/python/adapter_receipt.py:45-46,58-59,68-69 [DERIVED]
- polarity_for is the gap B-11 admitted-record reading convention; consumers must use it, not the global polarity flag alone. adapters/ecommerce/python/adapter_receipt.py:90 [DERIVED]
- `_metric` always emits `sample_n` (nullable) — TrailSignal requires the key (TRAIL_REFUSED without it). adapters/ecommerce/python/adapter_receipt.py:229-231 [DERIVED]

## VERIFY
```verify
grep -Fq 'SCHEMA_SHA256 = "c5a8e1ca1c3a28e18b1a0ae5a5b66c1d765793df507c6e9a76d8304c4e3cd7e8"' adapters/ecommerce/python/adapter_receipt.py
grep -Fq 'SCHEMA_MAX = {"sources": 100, "observations": 200, "tool_trace": 200, "limitations": 50}' adapters/ecommerce/python/adapter_receipt.py
grep -Fq 'RELATION_POLARITY = {"SUPPORTS": "supporting", "CONTRADICTS": "contradicting"}' adapters/ecommerce/python/adapter_receipt.py
grep -Fq 'NOT_FIELD_FAMILIES = {"corpus_evergreen"}' adapters/ecommerce/python/adapter_receipt.py
grep -Fq 'return 2 if args.strict and (report["omitted"] or report["notes"]) else 0' adapters/ecommerce/python/adapter_receipt.py
! grep -Fq 'except' adapters/ecommerce/python/adapter_receipt.py
test "$(grep -c -F 'SCHEMA_MAX' adapters/ecommerce/python/adapter_receipt.py)" -ge 6
```
