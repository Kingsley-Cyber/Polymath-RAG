# unit: control/control/reconciliation.py
anchor: control/control/reconciliation.py:1-499

## purpose
Self-healing half of contract-pinned claiming (CONTRACT-RECONCILIATION-1C, addendum 5e): when a fleet upgrade changes the execution contract, open runs pinned to the old contract are superseded by successor runs pinning CURRENT contracts; DONE stages whose declared dependencies are unchanged carry forward, the rest regenerate. Zero deletion, claim gate untouched. Consumer is the control-plane tick (FACTS.importers: control/control/main.py). — control/control/reconciliation.py:1-27 [DERIVED]

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| reconcile_contract_drift | def | (conn: Connection) -> dict | control/control/reconciliation.py:102-171 | control/control/main.py (module importer, FACTS) |
| mint_shadow_successor | def | (conn, old_run_id: str, *, generation: str) -> str or None | control/control/reconciliation.py:268-333 | control/control/main.py (module importer, FACTS) |
| backfill_carried_events | def | (conn: Connection) -> int | control/control/reconciliation.py:463-499 | control/control/main.py (module importer, FACTS) |
| successor_run_id | def | (old_run_id: str, execution_contract: dict) -> str | control/control/reconciliation.py:94-99 | internal (:146, :293) |
| STAGE_CONTRACT_DEPENDENCIES | const | dict[str, tuple[str, ...]] | control/control/reconciliation.py:55-78 | internal (:90, :204-205, :306-307) |

Private helpers: `_changed_keys` control/control/reconciliation.py:81-84, `_stale_stages` :87-91, `_mint_successor` :174-265, `_run_generation` :336-346, `_carry_completed_stages` :349-460.

## contracts

### reconcile_contract_drift(conn) -> dict — control/control/reconciliation.py:102-171
- in: `conn` (psycopg); current contract from `default_execution_contract()` :110
- pre: called once per control tick, BEFORE ticket creation, inside the tick transaction :103-104
- selection: `status = ANY(("intake","reconciling","degraded"))` :118,:45; `execution_contract::text IS NOT NULL` :119; `execution_contract <> %s::jsonb` :120; `superseded_by_run_id IS NULL` :121; corpus NOT in `archived_corpora` :122-124; ≥1 ticket in ("pending","ready","leased","failed") :125-127; ordered `created_at` :128
- out: `{"reconciled": {old_run_id: successor_run_id}, "skipped": {run_id: reason}}`, both empty when fleet is consistent :106-108, :134-136
- post: every stranded run minted or skipped, reason ∈ {"unreadable_pin_or_metadata" :143, "successor_pointer_occupied" :162, "successor_exists" :170}; per-run savepoint `with conn.transaction()` :157

### mint_shadow_successor(conn, old_run_id, *, generation) -> str or None — control/control/reconciliation.py:268-333
- pre: run exists else `ValueError(f"unknown run {old_run_id}")` :284-285; `status == "query_ready"` else ValueError :287-289
- out: successor run_id, or None if successor id exists :294-295 or any run has `supersedes_run_id = old_run_id` :296-298
- post: predecessor untouched (no status/ticket change) :316; successor inserted `'reconciling'` with `metadata.blue_green` = {"supersedes", "generation", "predecessor_generation", "regenerated_stages", "carried_stages"} :301-315; old `reconciliation` metadata key popped :309; intake.v1 events copied :318-327; `ensure_run_tickets` :328-329
- docstring: `control.generation_swap.swap` retires the predecessor in the promotion transaction :274-275

### backfill_carried_events(conn) -> int — control/control/reconciliation.py:463-499
- in: runs with `superseded_by_run_id IS NOT NULL`, stages from `metadata->'reconciliation'->'carried_stages'` :470-474
- out: count of event rows inserted (`fixed`) :469, :498-499
- post: replays produced-event copy; deterministic keys make replays no-ops :464-466. Only the `reconciliation` metadata path is read — blue/green successors (metadata `blue_green`, key popped at :309) are never selected :471-472

### successor_run_id(old_run_id, execution_contract) -> str — control/control/reconciliation.py:94-99
- out: `"run_" + content_hash({"reconciles": old_run_id, "execution_contract": execution_contract})` :97-99; same inputs → same successor id, so replay can never mint a second lineage

## effect surface

| effect | detail | anchor |
|---|---|---|
| PG read | runs (:184, :281-283, :471), stage_tickets (:125, :367-370), stage_attempts (:373-377), artifacts (:378-382), outbox_events (:249, :324, :444-447, :483-486), archived_corpora (:122-124), chunks+documents (:340-344) | [DERIVED] |
| PG write | runs (:210-218, :222-224, :311-315), stage_tickets (:193-196, :225-227, :387-400), stage_attempts (:403-410), artifacts (:427-434), outbox_events (:244-254, :318-327, :448-458, :487-497) | [DERIVED] |
| DB clock | `now()` into runs.updated_at :223, stage_tickets.updated_at :226, stage_attempts started_at/completed_at :407 | [DERIVED] |
| module deps | control.tickets (`DAG_ORDER`, `_STAGE_SPEC`, `ensure_run_tickets`, `ticket_id`) :255,:328,:361,:467; polymath_shared.execution :37; polymath_shared.identity :38; polymath_shared.extract_projection :423 | [DERIVED] |
| other I/O | no files, network, subprocess, or env flags in this unit | [DERIVED] |

## invariants
INVARIANT: successors per superseded run == 1, enforced by partial unique index `runs_one_successor_idx` (migration 0029) — control/control/reconciliation.py:19-21 [DERIVED]
  fails-if: duplicate lineage; UniqueViolation rolls back the whole tick unless caught at :161-166
INVARIANT: stage regenerates ⟺ `_changed_keys(old,new) ∩ STAGE_CONTRACT_DEPENDENCIES[stage] ≠ ∅` — control/control/reconciliation.py:89-91 [DERIVED]
  fails-if: a stage depending on a changed key is carried; successor serves stale-format output
INVARIANT: carried stage ⇒ done ticket AND latest `outcome='ok'` attempt AND artifact all present — control/control/reconciliation.py:367-384 [DERIVED]
  fails-if: carried without evidence; downstream claims hit `KeyError('doc_id')` :436-440
INVARIANT: carried ticket status == `'done'`, generation == `1` — control/control/reconciliation.py:392, :397 [DERIVED]
INVARIANT: `"verify_projections": ()` ⇒ verify_projections never enters the stale set — control/control/reconciliation.py:73, :90-91 [DERIVED]
INVARIANT: retired run keeps all tickets/events/attempts/artifacts; only status flips to `'superseded'` — control/control/reconciliation.py:220-227 [DERIVED]
  fails-if: history loss or two active intents per corpus
INVARIANT: blue/green predecessor status and tickets unchanged after mint — control/control/reconciliation.py:316 [DERIVED]
INVARIANT: carried intake idempotency_key == `content_hash({"carried_to": new_run_id, "kind": "intake"}) || e.idempotency_key::text` — control/control/reconciliation.py:248, :252-254, :322, :326-327 [DERIVED]
INVARIANT: carried event idempotency_key == `content_hash({"carried_to": new_run_id, "src_event": src_event_id})` — control/control/reconciliation.py:456-458, :495-497 [DERIVED]

## determinism & idempotency
determinism: NONDETERMINISTIC (db clock `now()` :223, :226, :407; current contract reflects fleet state via `default_execution_contract()` :110, :292; stranded set depends on DB contents :113-132; concurrent-tick races resolved only by the unique index :179-181). All identity/idempotency keys are pure `content_hash`, so replays converge.
idempotency: SAFE — every write is `ON CONFLICT DO NOTHING`: runs :214, stage_tickets :398, stage_attempts :408, artifacts :431, outbox_events :251, :325, :454, :493; repeated ticks documented as no-ops :20-21; backfill replays no-ops :466.

## failure behaviour
- `UniqueViolation` from `_mint_successor` → savepoint rollback, `skipped["successor_pointer_occupied"]` + log.warning, tick continues — control/control/reconciliation.py:156-166. Live cause (2026-08-31 wedge): PARKED successor husk (status superseded, superseded_by NULL) held `runs_one_successor_idx`, killing census+ticketing every tick; detach is the owner's move via `scripts/reingest_corpus.py` :147-155 [DERIVED]
- `json.JSONDecodeError` on pin/metadata → `skipped["unreadable_pin_or_metadata"]` :142-144
- race already lost → `_mint_successor` returns False → `skipped["successor_exists"]`; the missing retirement half is still applied :185-197, :170
- `mint_shadow_successor` raises ValueError for unknown run :285 and non-`query_ready` status :288-289; no try/except or savepoint in its body, so a concurrent mint's UniqueViolation would propagate to the caller :268-333 [INFERRED — body contains no handler]

## dumb-code flags
- Intake.v1 copy SQL duplicated verbatim: `_mint_successor` control/control/reconciliation.py:244-254 vs `mint_shadow_successor` :318-327
- Produced-event copy loop duplicated: `_carry_completed_stages` :448-458 vs `backfill_carried_events` :487-497
- Literal `generation` value `1` in carried ticket insert :392 vs caller-supplied chunk-contract `generation` param :269, :303 — two meanings of "generation" in one file [INFERRED]
- Magic substring `new_run_id[:16]` for log `attempt_id` :262, :332
- One hash body, two roles: `content_hash({"run": new_run_id, "stage": stage})` is both `stage_attempts.contract_hash` :402 and the artifacts `artifact_id` body :432
- `_ = carried` dead assignment :264
- `pin_text or "{}"` fallback :140 is unreachable for the pin (query requires `execution_contract::text IS NOT NULL` :119); only `metadata_text or "{}"` :141 can fire
- Positional `[0]` event-type access into `_STAGE_SPEC` :400, :443, :482

## refactor notes
- `STAGE_CONTRACT_DEPENDENCIES` keys must stay identical to control.tickets `DAG_ORDER`/`_STAGE_SPEC` stage names (iterated :364, indexed :443, :482, spec lookup :400) — a rename in one place breaks carry and backfill
- `successor_run_id` formula :97-99 is persistent identity; changing it orphans already-minted successors and can mint second lineages [INFERRED — ids are content-derived and stored as run_id]
- `runs_one_successor_idx` (migration 0029) backs the UniqueViolation skip path :19-21, :161-166; removing it turns skips into duplicate successors
- `reconcile_contract_drift` must run BEFORE ticket creation inside the tick transaction :103-104; importer control/control/main.py must preserve that ordering
- `produced_type = _STAGE_SPEC[DAG_ORDER[idx + 1]][0]` :441-443 — reordering `DAG_ORDER` changes which events get carried
- Carried extract artifacts must yield projection columns via `extract_projection_columns_for` or operational reads regress to NULL/stale :417-425
- `backfill_carried_events` reads only the `reconciliation` metadata path :471-472; covering blue/green successors needs a new query

## VERIFY
```verify
grep -Fq 'STAGE_CONTRACT_DEPENDENCIES: dict[str, tuple[str, ...]]' control/control/reconciliation.py
grep -Fq 'result["skipped"][old_run_id] = "successor_pointer_occupied"' control/control/reconciliation.py
grep -Fq 'except UniqueViolation:' control/control/reconciliation.py
grep -Fq '"run_" + content_hash(' control/control/reconciliation.py
grep -Fq 'ON CONFLICT (idempotency_key) DO NOTHING' control/control/reconciliation.py
! grep -Fq 'DELETE FROM' control/control/reconciliation.py
```
