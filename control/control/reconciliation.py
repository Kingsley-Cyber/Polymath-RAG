"""CONTRACT-RECONCILIATION-1C: pipeline-version lifecycle (addendum 5e).

Contract-pinned claiming is fail-closed by design: a worker refuses any
run whose pinned execution_contract differs from its own advertised
contracts. Correct for determinism, fatal for liveness across
upgrades -- every corpus ingested before an upgrade used to freeze
mid-pipeline the moment the fleet changed. This module adds the missing
self-healing half WITHOUT weakening the claim gate:

    old run (historical evidence, never deleted)
        |  supersedes_run_id / superseded_by_run_id
        v
    successor run (pins CURRENT contracts, fresh ticket chain)

Invariants:

* ZERO DELETION. Superseded runs keep tickets, events, attempts,
  artifacts and receipts as history.
* ONE ACTIVE INTENT per superseded run, ever. Enforced by the partial
  unique index runs_one_successor_idx (migration 0029) plus terminal
  status transitions; repeated ticks are no-ops.
* SELECTIVE REGENERATION. STAGE_CONTRACT_DEPENDENCIES declares which
  contract keys each pipeline stage's output depends on. A DONE stage
  whose dependencies are ALL unchanged carries into the successor;
  anything depending on a changed key regenerates under the new
  contract. Document identity is content-derived, so re-running intake
  reuses doc_id/chunk_id rows verbatim (identity model, addendum 3).
"""
from __future__ import annotations

import json
import logging

from psycopg import Connection

from polymath_shared.execution import default_execution_contract
from polymath_shared.identity import content_hash

log = logging.getLogger("control-reconcile")

#: Runs eligible for reconciliation: still-open lifecycles with a pinned
#: contract that no longer matches the fleet. NULL pins predate the
#: fence and pass every claim gate, so they are NOT stranded by drift.
_RECONCILABLE_RUN_STATUSES = ("intake", "reconciling", "degraded")

#: Ticket states that mean "this run still owes work". A run whose
#: tickets are all done/failed-terminal is historical, not stranded.
_OPEN_TICKET_STATES = ("pending", "ready", "leased", "failed")

#: Stage -> contract keys whose change invalidates the stage's outputs.
#: Declared here so reconciliation knows WHAT IS STALE (addendum 5e):
#: stages whose keys all match between old pin and current fleet carry
#: their DONE state forward; the rest regenerate.
STAGE_CONTRACT_DEPENDENCIES: dict[str, tuple[str, ...]] = {
    # intake materializes raw documents/chunks; byte-identity depends on
    # normalization+chunking, not on extraction semantics downstream.
    "intake": ("chunker",),
    "extract": (
        "semantic_bundle",   # entity/evidence semantics
        "rule_pack",         # predicate candidates + compilation
        "syntax_provider",   # syntax evidence feeding candidates
        "rescue_stages",     # span rescue hypotheses
        "gliner_url",        # which model instance produced spans
        "chunker",
    ),
    "profile_document": ("semantic_bundle",),
    "project_qdrant": ("semantic_bundle",),   # embeddings of chunks
    "project_neo4j": ("semantic_bundle", "rule_pack"),  # settled facts
    "canonicalize": ("semantic_bundle", "rule_pack"),
    "project_canonical": ("semantic_bundle", "rule_pack"),
    "verify_projections": (),
    "parent_summary": ("semantic_bundle",),
    "document_summary": ("semantic_bundle",),
    "corpus_summary": ("semantic_bundle",),
    "vocabulary": ("semantic_bundle",),
}


def _changed_keys(old: dict, new: dict) -> set[str]:
    """Contract keys whose values differ between old pin and now."""
    return {k for k in set(old) | set(new)
            if old.get(k) != new.get(k)}


def _stale_stages(old: dict, new: dict) -> set[str]:
    """Stages that MUST regenerate: at least one dependency changed."""
    changed = _changed_keys(old, new)
    return {stage for stage, deps in STAGE_CONTRACT_DEPENDENCIES.items()
            if changed & set(deps)}


def successor_run_id(old_run_id: str, execution_contract: dict) -> str:
    """Deterministic successor identity: same inputs -> same successor,
    so replaying reconciliation can never mint a second lineage."""
    return "run_" + content_hash(
        {"reconciles": old_run_id,
         "execution_contract": execution_contract})


def reconcile_contract_drift(conn: Connection) -> dict:
    """STEP 1c entry point. Called once per control tick, BEFORE ticket
    creation, inside the tick transaction.

    Returns {"reconciled": {old_run_id: successor_run_id, ...},
             "skipped": {run_id: reason, ...}} of what THIS tick did;
    both empty when the fleet is consistent (the common case).
    """
    current = default_execution_contract()
    current_json = json.dumps(current, sort_keys=True)

    stranded = conn.execute(
        """
        SELECT r.run_id, r.corpus_id, r.execution_contract::text AS pin,
               r.metadata::text AS metadata
          FROM runs r
         WHERE r.status = ANY(%s)
           AND r.execution_contract::text IS NOT NULL
           AND r.execution_contract <> %s::jsonb
           AND r.superseded_by_run_id IS NULL
           AND NOT EXISTS (
               SELECT 1 FROM archived_corpora ac
                WHERE ac.corpus_id = r.corpus_id)
           AND EXISTS (SELECT 1 FROM stage_tickets t
                        WHERE t.run_id = r.run_id
                          AND t.status = ANY(%s))
         ORDER BY r.created_at
        """,
        (list(_RECONCILABLE_RUN_STATUSES), current_json,
         list(_OPEN_TICKET_STATES)),
    ).fetchall()

    result: dict[str, dict] = {"reconciled": {}, "skipped": {}}
    if not stranded:
        return result

    for old_run_id, corpus_id, pin_text, metadata_text in stranded:
        try:
            old_pin = json.loads(pin_text or "{}")
            metadata = json.loads(metadata_text or "{}")
        except json.JSONDecodeError:
            result["skipped"][old_run_id] = "unreadable_pin_or_metadata"
            continue

        new_run_id = successor_run_id(old_run_id, current)
        minted = _mint_successor(conn, old_run_id, new_run_id,
                                 corpus_id, old_pin, current, metadata)
        if minted:
            result["reconciled"][old_run_id] = new_run_id
        else:
            result["skipped"][old_run_id] = "successor_exists"
    return result


def _mint_successor(conn: Connection, old_run_id: str, new_run_id: str,
                    corpus_id: str, old_pin: dict, current: dict,
                    metadata: dict) -> bool:
    """Retire old run, mint + wire the successor, carry reusable state.

    False => successor already exists (concurrent tick or prior run);
    the unique index guarantees this is the only race outcome.
    """
    stale = _stale_stages(old_pin, current)
    existing = conn.execute(
        "SELECT 1 FROM runs WHERE run_id=%s", (new_run_id,)).fetchone()
    if existing:
        # Prior reconciliation won the race; just retire the old row if
        # that half did not commit (crash between the two updates).
        conn.execute(
            """UPDATE runs SET status='superseded',
                   superseded_by_run_id=%s, updated_at=now()
                 WHERE run_id=%s AND status <> 'superseded'""",
            (new_run_id, old_run_id))
        conn.execute(
            """UPDATE stage_tickets SET status='superseded', updated_at=now()
                WHERE run_id=%s AND status <> 'done'
                  AND status <> 'superseded'""", (old_run_id,))
        return False

    successor_metadata = dict(metadata)
    successor_metadata["reconciliation"] = {
        "supersedes": old_run_id,
        "reason": "contract_drift",
        "regenerated_stages": sorted(stale),
        "carried_stages": sorted(
            s for s in STAGE_CONTRACT_DEPENDENCIES if s not in stale),
    }

    # 1. mint the successor first: lineage columns are FKs, so the
    #    target must exist before the old row points at it
    conn.execute(
        """INSERT INTO runs (run_id, corpus_id, status, metadata,
                            execution_contract, supersedes_run_id)
           VALUES (%s, %s, 'reconciling', %s, %s, %s)
           ON CONFLICT (run_id) DO NOTHING""",
        (new_run_id, corpus_id,
         json.dumps(successor_metadata),
         json.dumps(current, sort_keys=True),
         old_run_id))

    # 2. retire the old intent -- evidence preserved, nothing deleted
    conn.execute(
        """UPDATE runs SET status='superseded',
               superseded_by_run_id=%s, updated_at=now()
             WHERE run_id=%s""", (new_run_id, old_run_id))
    conn.execute(
        """UPDATE stage_tickets SET status='superseded', updated_at=now()
            WHERE run_id=%s AND status <> 'done'""", (old_run_id,))

    # 3. carry DONE state for stages whose dependencies are unchanged --
    #    run-scoped copies (never cross-run pointers), provenance kept.
    #    Unconditional: when NOTHING relevant changed, every done stage
    #    carries; when something changed, only unaffected stages do.
    carried = _carry_completed_stages(conn, old_run_id, new_run_id,
                                      corpus_id, stale)

    # 4. fresh ticket chain under the CURRENT contract; intake READY +
    #    event emitted by the existing idempotent path. The successor's
    #    intake claim needs the REAL intake payload (corpus_id,
    #    content_b64...) -- copy the parent's original intake.v1 rows
    #    verbatim FIRST, so _emit_ticket_event finds them instead of
    #    falling back to a bare {run_id} payload (observed live as
    #    KeyError('corpus_id') burning retry budget). Content-derived
    #    doc/chunk identities make re-intake reuse the raw document.
    conn.execute(
        """INSERT INTO outbox_events
               (run_id, event_type, payload, idempotency_key)
            SELECT %s, e.event_type, e.payload,
                   %s || e.idempotency_key::text
              FROM outbox_events e
             WHERE e.run_id=%s AND e.event_type='intake.v1'
            ON CONFLICT (idempotency_key) DO NOTHING""",
        (new_run_id, content_hash({"carried_to": new_run_id,
                                   "kind": "intake"}),
         old_run_id))
    from control.tickets import ensure_run_tickets
    ensure_run_tickets(conn, new_run_id, corpus_id, dict(current))

    log.info("reconciled run to current contract", extra={
        "run_id": old_run_id,
        "stage": "reconcile",
        "error_code": None,
        "attempt_id": new_run_id[:16],
    })
    _ = carried  # recorded in successor metadata; verifier asserts it
    return True


def _carry_completed_stages(conn: Connection, old_run_id: str,
                            new_run_id: str, corpus_id: str,
                            stale: set[str]) -> list[str]:
    """Copy DONE-stage evidence from the superseded run into the
    successor so unchanged-dependency work never executes twice.

    Copies, per non-stale DONE stage: the done ticket, the latest ok
    stage_attempt (keyed by the NEW contract hash, payload records the
    producing run), and the stage artifact. Receipts/projections are
    entity-keyed (doc_id/chunk_id) and remain valid untouched because
    document identity is preserved byte-for-byte.
    """
    from control.tickets import DAG_ORDER, _STAGE_SPEC, ticket_id

    carried: list[str] = []
    for stage in DAG_ORDER:
        if stage in stale:
            continue
        done_ticket = conn.execute(
            """SELECT 1 FROM stage_tickets
                WHERE run_id=%s AND stage=%s AND status='done'""",
            (old_run_id, stage)).fetchone()
        if not done_ticket:
            continue
        attempt = conn.execute(
            """SELECT contract_hash FROM stage_attempts
                WHERE run_id=%s AND stage=%s AND outcome='ok'
                ORDER BY started_at DESC LIMIT 1""",
            (old_run_id, stage)).fetchone()
        artifact = conn.execute(
            """SELECT payload FROM artifacts
                WHERE run_id=%s AND stage=%s
                ORDER BY artifact_id DESC LIMIT 1""",
            (old_run_id, stage)).fetchone()
        if attempt is None or artifact is None:
            continue

        tid = ticket_id(new_run_id, stage)
        conn.execute(
            """INSERT INTO stage_tickets
                   (ticket_id, run_id, corpus_id, stage, event_type,
                    generation, required_artifacts, required_receipts,
                    status)
               VALUES (%s,%s,%s,%s,%s,1,
                       (SELECT required_artifacts FROM stage_tickets
                         WHERE run_id=%s AND stage=%s LIMIT 1),
                       (SELECT required_receipts FROM stage_tickets
                         WHERE run_id=%s AND stage=%s LIMIT 1),
                       'done')
               ON CONFLICT (ticket_id) DO NOTHING""",
            (tid, new_run_id, corpus_id, stage,
             _STAGE_SPEC[stage][0], old_run_id, stage, old_run_id, stage))

        contract_hash = content_hash({"run": new_run_id, "stage": stage})
        conn.execute(
            """INSERT INTO stage_attempts
                   (run_id, stage, contract_hash, started_at,
                    completed_at, outcome, error, payload)
               VALUES (%s,%s,%s,now(),now(),'ok',NULL,%s)
               ON CONFLICT (run_id, stage, contract_hash) DO NOTHING""",
            (new_run_id, stage, contract_hash,
             json.dumps({"carried_from_run": old_run_id})))

        art_payload = artifact[0]
        if not isinstance(art_payload, dict):
            art_payload = json.loads(art_payload)
        art_payload = dict(art_payload)
        art_payload["carried_from_run"] = old_run_id
        conn.execute(
            """INSERT INTO artifacts
                   (artifact_id, run_id, stage, contract_hash, payload)
               VALUES (%s,%s,%s,%s,%s)
               ON CONFLICT (artifact_id) DO NOTHING""",
            ("art_" + content_hash({"run": new_run_id, "stage": stage}),
             new_run_id, stage, contract_hash, json.dumps(art_payload)))

        # The DOWNSTREAM stage's claim payload derives from the event
        # this stage PRODUCED (_emit_ticket_event copies that row
        # verbatim). Carrying a done stage without its produced events
        # leaves downstream claims a bare {run_id} payload -- observed
        # live as KeyError('doc_id') on every gated extract claim.
        idx = DAG_ORDER.index(stage)
        if idx + 1 < len(DAG_ORDER):
            produced_type = _STAGE_SPEC[DAG_ORDER[idx + 1]][0]
            src_rows = conn.execute(
                """SELECT event_id FROM outbox_events
                    WHERE run_id=%s AND event_type=%s""",
                (old_run_id, produced_type)).fetchall()
            for (src_event_id,) in src_rows:
                conn.execute(
                    """INSERT INTO outbox_events
                           (run_id, event_type, payload, idempotency_key)
                        SELECT %s, e.event_type, e.payload, %s
                          FROM outbox_events e WHERE e.event_id=%s
                        ON CONFLICT (idempotency_key) DO NOTHING""",
                    (new_run_id,
                     content_hash({"carried_to": new_run_id,
                                   "src_event": src_event_id}),
                     src_event_id))
        carried.append(stage)
    return carried


def backfill_carried_events(conn: Connection) -> int:
    """One-time-idempotent repair for successors minted BEFORE the
    produced-events copy existed: re-run the carry copy for each run's
    recorded carried_stages. Deterministic keys make replays no-ops."""
    from control.tickets import DAG_ORDER, _STAGE_SPEC

    fixed = 0
    rows = conn.execute(
        """SELECT run_id, supersedes_run_id,
                  metadata->'reconciliation'->'carried_stages'
             FROM runs
            WHERE supersedes_run_id IS NOT NULL""").fetchall()
    for new_run_id, old_run_id, carried in rows:
        if not old_run_id or not carried:
            continue
        for stage in carried:
            idx = DAG_ORDER.index(stage)
            if idx + 1 >= len(DAG_ORDER):
                continue
            produced_type = _STAGE_SPEC[DAG_ORDER[idx + 1]][0]
            src_rows = conn.execute(
                """SELECT event_id FROM outbox_events
                    WHERE run_id=%s AND event_type=%s""",
                (old_run_id, produced_type)).fetchall()
            for (src_event_id,) in src_rows:
                conn.execute(
                    """INSERT INTO outbox_events
                           (run_id, event_type, payload, idempotency_key)
                        SELECT %s, e.event_type, e.payload, %s
                          FROM outbox_events e WHERE e.event_id=%s
                        ON CONFLICT (idempotency_key) DO NOTHING""",
                    (new_run_id,
                     content_hash({"carried_to": new_run_id,
                                   "src_event": src_event_id}),
                     src_event_id))
                fixed += 1
    return fixed
