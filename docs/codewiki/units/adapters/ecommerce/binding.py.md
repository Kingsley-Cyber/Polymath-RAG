# unit: adapters/ecommerce/binding.py
anchor: adapters/ecommerce/binding.py:1-1215

## purpose
- The ONE door between the Polymath adapter runtime and the engine (DOMAIN_OPERATION, ADR-0020): the worker runs this file out of process — one JSON request on stdin, one JSON object on stdout — so engine crashes become typed step failures, not dead workers. adapters/ecommerce/binding.py:1-6 [DERIVED]
- `OPERATIONS` wraps existing engine functions; nothing here re-implements domain logic, reads/writes run state, or touches a ledger — the runtime owns state, this file only computes. adapters/ecommerce/binding.py:14 [DERIVED]
- Anything the engine prints goes to stderr, never into the response. adapters/ecommerce/binding.py:15 [DERIVED]

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
| main | def | () — file protocol: stdin JSON request → stdout JSON response | adapters/ecommerce/binding.py:1208-1215 | adapter worker, runs file out of process (adapters/ecommerce/binding.py:3-4) |
| handle | def | () | adapters/ecommerce/binding.py:1190-1205 | — |
| Refusal | class | `__init__(code: str, message: str)`; attrs `.code`, `.message` | adapters/ecommerce/binding.py:41-46 | internal; surfaces as `{"ok": false, "code", "message"}` (adapters/ecommerce/binding.py:11) |

No FACTS importers recorded; every other symbol is `_`-prefixed and dispatched internally.

## contracts

**Worker protocol (main/handle)** — adapters/ecommerce/binding.py:8-12 [DERIVED]
- in: `{"schema_version": "domain_operation_request.v1", "domain", "operation", "run_id", "step_id", "input", "inputs", "config"}` (adapters/ecommerce/binding.py:8-9)
- out: `{"ok": true, "output": {…}}` or `{"ok": false, "code": "UPPER_SNAKE", "message"}` (adapters/ecommerce/binding.py:10-11)
- pre: import sets `os.environ["OPPORTUNITY_RESEARCH_REGISTRY"] = "compile"` (adapters/ecommerce/binding.py:30) and pops `OPPORTUNITY_RESEARCH_REGISTRY_SRC` (adapters/ecommerce/binding.py:36); prepends `<ROOT>/python` to `sys.path` (adapters/ecommerce/binding.py:27-28)
- post: exit != 0 / non-JSON stdout = crash → runtime records `STEP_EXECUTOR_ERROR` (adapters/ecommerce/binding.py:12)

**Operations (selected, all `req: dict[str, Any] -> dict[str, Any]`)**

| operation | pre (else Refusal) | out / post | anchor |
| `hypotheses.validate_bridge` | `inputs.hypotheses` non-empty list (`HYPOTHESES_MISSING`) | `{admissible, bridge_errors, portfolio_errors, anchor_errors, hypotheses_checked, portfolio_unreachable, portfolio_needs}`; with `live_hypotheses`: named ids must equal live ledger ids; portfolio bounds default 3–6; anchor checks only when `lived_clusters` is a list | adapters/ecommerce/binding.py:56-93 |
| knowledge rows (`_op_corpus_evidence`) | `inputs.row_sets` holds ≥1 non-empty list (`KNOWLEDGE_ROWS_MISSING`); rows need `kind == "chunk"` (default `"chunk"`), `id`, non-blank `text`, `corpus_id` else skipped | `{corpus_evidence, row_count, skipped, corpora}`; row id = evidence id with `"polymath:chunk:"` prefix stripped, first occurrence of an id wins; all skipped → `KNOWLEDGE_ROWS_UNUSABLE` | adapters/ecommerce/binding.py:141-168 |
| `_op_lenses` | `signal` non-blank (`SIGNAL_MISSING`); corpus rows via `_corpus_rows` (`CORPUS_EVIDENCE_MISSING`) | `{lenses, note}` from `executors.lens_gate` | adapters/ecommerce/binding.py:176-182, 127-131 |
| `_op_validate_primitives` | `inputs.primitives` is a dict (`PRIMITIVES_MISSING`) | `{valid, errors}`; on valid also `row_relevance`, `latent_structures`, `corpus_observations` | adapters/ecommerce/binding.py:193-203 |
| `_op_population_nominate` | `signal` + `primitives` dict (`POPULATION_INPUT_MISSING`) | batch = top `batch_size` (default 4) eligible leads in VOI order; no ranked leads → `POPULATION_NOT_FOUND`; output carries `registry: {source: REGISTRY_SOURCE, build_id, seeds, friction_families}` | adapters/ecommerce/binding.py:214-234 |
| `_op_evidence_cards` | — (no refusal) | field records built from ADMITTED observations only; `duplicate_of` records stay citable but are excluded from clustering; zero records → graceful note, not a failure | adapters/ecommerce/binding.py:277-281, 360-366 |
| `_op_validate_situations` | `lived_situations` non-empty list (`LIVED_SITUATIONS_MISSING`) | schema errors per index + law errors; malformed items never crash (gap B-01) | adapters/ecommerce/binding.py:383-390 |
| `_op_corpus_questions` | — | no `lived_clusters` → `{"corpus_questions": [], "need": "", "note": "no lived cluster — no field-grounded corpus question"}`; else `need` = joined questions truncated to 2000 | adapters/ecommerce/binding.py:402-406 |
| `_op_research_plan` | `research_directive` dict with `search_intents` (`RESEARCH_DIRECTIVE_MISSING`) | same directive, governance fields untouched, Trail intents first and in order; added intents ≤ cap = `max(len(trail_intents), min(100, budget.max_queries or 24))`; overflow counted, never silently dropped | adapters/ecommerce/binding.py:478-494 |

**Helpers**
- `_context_field(context, key)`: tolerant `key: value` read; title tags `"listing"`/`"product"` keep `|` and `;`; a tag whose every occurrence follows the title reads at its LAST occurrence, one written before it at its first (gap B-52). adapters/ecommerce/binding.py:249-264 [DERIVED]
- `_intent_lineage(context)`: `gap_id` set only when the intent-id tail startswith `("gap", "falsify")`. adapters/ecommerce/binding.py:270-274 [DERIVED]
- `_round_robin(per_subject, seen, room, *, channel_floor=False) -> (added, dropped_over_budget, unhostable)`; with `channel_floor`, every channel gets one proposal (diagonal across subjects) before rank-major fill. adapters/ecommerce/binding.py:409-415 [DERIVED]
- `_channel_of(intent)`: `parts[-2]` only when the intent id splits into ≥3 `:`-parts, else `""`. adapters/ecommerce/binding.py:456-457 [DERIVED]
- `_ledger_hypotheses`: zips `hypotheses` with `hypothesis_ids` only when lengths match; ledger id becomes both `hypothesis_id` and `id`. adapters/ecommerce/binding.py:116-123 [DERIVED]

**Post-excerpt operations (FACTS metadata only; bodies at anchors)**
- `_op_validate_concepts` (3–6 DISTINCT product concepts, `ideation.validate_concepts`), `_op_supply_plan` (one sourcing job PER CONCEPT per channel), `_host_lookups` (supplier reads Polymath HOST makes), `_op_supply_draft_receipt`, `_concept_ref` (tag → concept id or None, gap B-34), `_supply_channel` (gap B-35), `_op_supply_leads`, `_op_product_reality_plan`, `_op_product_reality_join`, `_semantic_research_plan`, `_agent_reach`, `_mechanisms` (status DERIVED from ledger, never claimed by the agent), `_op_refuse` (honest end, typed gap), `_op_no_signal` (NO_GENERATIVE_SIGNAL is a SUCCESS outcome), `_phrase_hits`, `_op_seed_check` (F12), `_op_unresolved_gaps` (gap A-05), `_unreadable`. adapters/ecommerce/binding.py:527-1187 [DERIVED]

## effect surface
- Postgres tables: none read, none written (FACTS `tables_read`/`tables_written` empty). adapters/ecommerce/binding.py [DERIVED]
- Files: engine policies via `graphmod.load_policies()` (adapters/ecommerce/binding.py:62); registry snapshot via `registry.load_snapshot()` (adapters/ecommerce/binding.py:231).
- Network: none — "No HTTP here: the runtime already retrieved" (adapters/ecommerce/binding.py:137); only `urllib.parse.urlparse` for host extraction (adapters/ecommerce/binding.py:282).
- Subprocess: none emitted; this file is itself run as a subprocess by the adapter worker (adapters/ecommerce/binding.py:3-4).
- Env: writes `OPPORTUNITY_RESEARCH_REGISTRY = "compile"` (adapters/ecommerce/binding.py:30; FACTS env: required); deletes `OPPORTUNITY_RESEARCH_REGISTRY_SRC` (adapters/ecommerce/binding.py:36); mutates `sys.path` (adapters/ecommerce/binding.py:28).
- Streams: stdout reserved for the single JSON response; engine output → stderr (adapters/ecommerce/binding.py:15).

## invariants
INVARIANT: live-hypothesis count ∈ [3, 6] (defaults of `portfolio.min_hypotheses`/`max_hypotheses`) — adapters/ecommerce/binding.py:77 [DERIVED]
  fails-if: `portfolio_unreachable = true`; "more" loops to generation, "fewer" only φ can fix (adapters/ecommerce/binding.py:79-84)
INVARIANT: named bridge ids == live ledger ids (no duplicate, no phantom, no unbridged) — adapters/ecommerce/binding.py:69-75 [DERIVED]
  fails-if: per-hypothesis bridge_errors; manifest misroutes the loop
INVARIANT: eligible statuses ⊆ frozenset `{"proposed", "retained", "revised", "split", "strengthened", "promoted"}`; `weakened/contradicted/filtered/killed/merged` never eligible — adapters/ecommerce/binding.py:107-109 [DERIVED]
  fails-if: mechanisms/concepts build on dead hypotheses
INVARIANT: governed evidence id = runtime evidence id (`"polymath:chunk:"` prefix stripped); first occurrence of an id wins — adapters/ecommerce/binding.py:157-165 [DERIVED]
  fails-if: `context.evidence_refs` and Polymath's citation check disagree with row ids
INVARIANT: research intents added ≤ cap = max(len(trail_intents), min(100, budget.max_queries or 24)) — adapters/ecommerce/binding.py:494 [DERIVED]
  fails-if: silent intent drops; budget overrun uncounted
INVARIANT: `_neutral_intent` sizes — intent_id ≤ 200 chars, intent ≤ 500, template ≤ 500 — adapters/ecommerce/binding.py:465-466 [DERIVED]
  fails-if: over-long intents break downstream consumers of the compiled ids
INVARIANT: field-record truncation — `problem` ≤ 300, `quote_ref` ≤ 300, `workaround` ≤ 200 chars — adapters/ecommerce/binding.py:334-336 [DERIVED]
INVARIANT: supplier-draft API statuses ∈ `["OK", "PARTIAL", "EMPTY"]` (`_API_OK`) — adapters/ecommerce/binding.py:789 [DERIVED]
  fails-if: any other status treated as success/failure incorrectly
INVARIANT: batch = top `batch_size` (default 4) eligible leads, "a pure function of the inputs" (queue/wall-clock NOT used) — adapters/ecommerce/binding.py:207-210, 228 [DERIVED]

## determinism & idempotency
determinism: DETERMINISTIC (pure over request + policy files `graphmod.load_policies()` adapters/ecommerce/binding.py:62 + registry snapshot adapters/ecommerce/binding.py:231; no clock/random/uuid/network in the visible source lines 1-496; import-time env writes are constant values adapters/ecommerce/binding.py:30,36)
idempotency: SAFE (each operation gets a throwaway `state["data"]`, written keys returned as output — adapters/ecommerce/binding.py:101-104; no run state or ledger writes adapters/ecommerce/binding.py:14)

## failure behaviour
- `Refusal(code, message)` = well-formed request the engine declines; the run stops with that gap code. adapters/ecommerce/binding.py:41-46, 10-11 [DERIVED]
- Crash path: exit != 0 or anything else on stdout → runtime records `STEP_EXECUTOR_ERROR`. adapters/ecommerce/binding.py:12 [DERIVED]
- Invalid law verdicts are OUTPUTS (`admissible`/`valid` + error lists), not refusals — the run can branch back to reasoning. adapters/ecommerce/binding.py:50-52, 186-188, 375-376 [DERIVED]
- Graceful empty states: no admitted evidence and no lived cluster return `note`s, not failures. adapters/ecommerce/binding.py:362-364, 402-403 [DERIVED]
- Refusal codes raised in the visible half: `HYPOTHESES_MISSING` (:58), `CORPUS_EVIDENCE_MISSING` (:130), `KNOWLEDGE_ROWS_MISSING` (:143), `KNOWLEDGE_ROWS_UNUSABLE` (:167), `SIGNAL_MISSING` (:179), `PRIMITIVES_MISSING` (:195), `POPULATION_INPUT_MISSING` (:218), `POPULATION_NOT_FOUND` (:227), `LIVED_SITUATIONS_MISSING` (:384), `RESEARCH_DIRECTIVE_MISSING` (:489). adapters/ecommerce/binding.py [DERIVED]
- `_unreadable(operation, exc)`: a law that could not read the submission returns an unlawful verdict with a reason the agent can act on. adapters/ecommerce/binding.py:1181-1187 [DERIVED]
- `_op_refuse`: a law unsatisfiable within the loop budget ends the run honestly — typed gap carrying the law's own errors. adapters/ecommerce/binding.py:1060-1068 [DERIVED]
- `NO_GENERATIVE_SIGNAL` is a SUCCESS outcome (engine's `signal_gate`, docs/07). adapters/ecommerce/binding.py:1071-1087 [DERIVED]

## dumb-code flags
- `import re` re-imported locally inside `_context_field` despite module-level `import re`. adapters/ecommerce/binding.py:23, 254 [DERIVED]
- Hardcoded fallback defaults that duplicate policy values: `min_hypotheses` 3 / `max_hypotheses` 6 (adapters/ecommerce/binding.py:77), `batch_size` 4 (adapters/ecommerce/binding.py:228), `max_queries` 24 and cap 100 (adapters/ecommerce/binding.py:494). [DERIVED]
- Magic truncation lengths: 300/300/200 on field records (adapters/ecommerce/binding.py:334-336), 2000 on `need` (adapters/ecommerce/binding.py:406), 200/500/500 in `_neutral_intent` (adapters/ecommerce/binding.py:465-466). [DERIVED]
- Near-duplicate context regexes `_CONTEXT_FIELD` vs `_TITLE_FIELD` (title variant re-derives the same prefix pattern). adapters/ecommerce/binding.py:237, 244-245 [DERIVED]
- `REGISTRY_SOURCE` is a prose-laden constant that also ships verbatim into operation output. adapters/ecommerce/binding.py:35, 233-234 [DERIVED]
- `_ledger_hypotheses` silently attaches no ids when `len(hypothesis_ids) != len(hypotheses)`. adapters/ecommerce/binding.py:117-120 [DERIVED]

## refactor notes
- Wire contract: request version `"domain_operation_request.v1"` and response keys `ok`/`output`/`code`/`message` — every manifest step and the runtime depend on them. adapters/ecommerce/binding.py:8-11, 38 [DERIVED]
- Evidence id space: the `"polymath:chunk:"` strip couples this boundary to what `context.evidence_refs` shows the agent and to Polymath's citation check. adapters/ecommerce/binding.py:160-162 [DERIVED]
- `sys.path` prepend of `<ROOT>/python` is required by every flat engine import (`bridge`, `graph`, `lived_world`, `executors`, `corpus_polymath`, `adapter_receipt`, `registry`, `models`) — moving/renaming the file breaks all of them. adapters/ecommerce/binding.py:27-28, 53-54, 139, 231 [DERIVED]
- Import-time env writes are process-global in the worker; any co-resident module inherits `OPPORTUNITY_RESEARCH_REGISTRY="compile"`. adapters/ecommerce/binding.py:30, 36 [DERIVED]
- `_field_records_from_admissions` overrides generation-time proposals with the runtime `semantics` projection keyed on `("population", "activity", "task", "suspected_friction")` — renaming those projection keys mis-clusters records as `unassigned`. adapters/ecommerce/binding.py:296-299, 333 [DERIVED]
- `handle`/`main` (adapters/ecommerce/binding.py:1190, 1208) dispatch operations; renaming any `_op_*` handler or operation string breaks manifests. [INFERRED — docstring names an `OPERATIONS` registry at adapters/ecommerce/binding.py:14; dispatch bodies lie beyond the excerpt]

## VERIFY
```verify
grep -Fq 'REQUEST_VERSION = "domain_operation_request.v1"' adapters/ecommerce/binding.py
grep -Fq 'os.environ["OPPORTUNITY_RESEARCH_REGISTRY"] = "compile"' adapters/ecommerce/binding.py
grep -Fq 'class Refusal(Exception):' adapters/ecommerce/binding.py
grep -Fq 'ELIGIBLE_HYPOTHESIS_STATUSES = frozenset' adapters/ecommerce/binding.py
grep -Fq 'get("batch_size", 4)' adapters/ecommerce/binding.py
grep -Fq 'get("max_queries") or 24' adapters/ecommerce/binding.py
grep -Fq 'polymath:chunk:' adapters/ecommerce/binding.py
test "$(grep -c -F 'raise Refusal(' adapters/ecommerce/binding.py)" -ge 10
```
