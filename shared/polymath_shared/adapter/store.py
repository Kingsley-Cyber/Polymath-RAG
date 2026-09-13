"""Postgres persistence for adapter runs (migration 0061). Every function takes an open psycopg connection from
`polymath_shared.db.tx`; the caller owns the transaction so a step's output, receipt and run-state update commit
together (the same shape as receipts.stage_transaction)."""
from __future__ import annotations

import json
from dataclasses import replace
from typing import Any

from .manifest import Manifest
from .transitions import RunState

_STATE_COLS = ("run_id", "adapter_id", "status", "current_step_id", "sequence", "steps_accepted", "branch_loops",
               "agent_reason_count", "external_operation_count", "input", "request_options", "outputs", "failure", "gap")


def _j(v: Any) -> str:
    return json.dumps(v, sort_keys=True, ensure_ascii=False)


def _load(v: Any) -> Any:
    return json.loads(v) if isinstance(v, str) else v


def insert_run(conn, state: RunState, manifest: Manifest, *, idempotency_key: str | None, agent_identity: str | None) -> None:
    conn.execute(
        """INSERT INTO adapter_runs (run_id, adapter_id, adapter_version, workflow_version, retrieval_policy_version,
               input_schema_version, output_schema_version, status, current_step_id, sequence, steps_accepted, branch_loops,
               agent_reason_count, external_operation_count, input, request_options, outputs, failure, gap, agent_identity, idempotency_key)
           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s::jsonb,%s::jsonb,%s::jsonb,%s,%s)""",
        (state.run_id, manifest.adapter_id, manifest.adapter_version, manifest.workflow_version, manifest.retrieval_policy_version,
         manifest.input_schema_version, manifest.output_schema_version, state.status, state.current_step_id, state.sequence,
         state.steps_accepted, state.branch_loops, state.agent_reason_count, state.external_operation_count, _j(state.input),
         _j(state.options), _j(state.outputs), _j(state.failure) if state.failure else None, _j(state.gap) if state.gap else None,
         agent_identity, idempotency_key))


def find_run_by_idempotency(conn, key: str) -> str | None:
    row = conn.execute("SELECT run_id FROM adapter_runs WHERE idempotency_key=%s", (key,)).fetchone()
    return row[0] if row else None


def load_run(conn, run_id: str, *, for_update: bool = False) -> tuple[RunState, dict[str, Any]] | None:
    row = conn.execute(
        f"""SELECT {", ".join(_STATE_COLS)}, adapter_version, workflow_version, retrieval_policy_version, input_schema_version,
                   output_schema_version, agent_identity, created_at, updated_at, terminal_at, lease_owner, lease_expires_at
              FROM adapter_runs WHERE run_id=%s {"FOR UPDATE" if for_update else ""}""", (run_id,)).fetchone()
    if not row:
        return None
    d = dict(zip(_STATE_COLS, row[:len(_STATE_COLS)]))
    meta_keys = ("adapter_version", "workflow_version", "retrieval_policy_version", "input_schema_version", "output_schema_version",
                 "agent_identity", "created_at", "updated_at", "terminal_at", "lease_owner", "lease_expires_at")
    meta = dict(zip(meta_keys, row[len(_STATE_COLS):]))
    meta["adapter_id"] = d["adapter_id"]
    state = RunState(run_id=d["run_id"], adapter_id=d["adapter_id"], status=d["status"], current_step_id=d["current_step_id"],
                     sequence=d["sequence"], steps_accepted=d["steps_accepted"], branch_loops=d["branch_loops"],
                     agent_reason_count=d["agent_reason_count"], external_operation_count=d["external_operation_count"],
                     input=_load(d["input"]) or {}, options=_load(d["request_options"]) or {}, outputs=_load(d["outputs"]) or {},
                     failure=_load(d["failure"]), gap=_load(d["gap"]))
    return state, meta


def save_state(conn, state: RunState) -> None:
    conn.execute(
        """UPDATE adapter_runs SET status=%s, current_step_id=%s, sequence=%s, steps_accepted=%s, branch_loops=%s,
               agent_reason_count=%s, external_operation_count=%s, outputs=%s::jsonb, failure=%s::jsonb, gap=%s::jsonb,
               updated_at=now(), terminal_at=CASE WHEN %s THEN COALESCE(terminal_at, now()) ELSE terminal_at END
           WHERE run_id=%s""",
        (state.status, state.current_step_id, state.sequence, state.steps_accepted, state.branch_loops, state.agent_reason_count,
         state.external_operation_count, _j(state.outputs), _j(state.failure) if state.failure else None,
         _j(state.gap) if state.gap else None, state.terminal, state.run_id))


def insert_step(conn, step: dict[str, Any]) -> None:
    conn.execute(
        """INSERT INTO adapter_steps (run_id, sequence, step_id, step_type, status, step) VALUES (%s,%s,%s,%s,'issued',%s::jsonb)""",
        (step["run_id"], step["sequence"], step["step_id"], step["step_type"], _j(step)))


def current_step(conn, run_id: str) -> dict[str, Any] | None:
    row = conn.execute(
        """SELECT sequence, step_id, step_type, status, step, submission, output, receipt, external_operation, started_at, ended_at
             FROM adapter_steps WHERE run_id=%s ORDER BY sequence DESC LIMIT 1""", (run_id,)).fetchone()
    if not row:
        return None
    keys = ("sequence", "step_id", "step_type", "status", "step", "submission", "output", "receipt", "external_operation", "started_at", "ended_at")
    d = dict(zip(keys, row))
    for k in ("step", "submission", "output", "receipt", "external_operation"):
        d[k] = _load(d[k])
    return d


def list_steps(conn, run_id: str) -> list[dict[str, Any]]:
    rows = conn.execute(
        """SELECT sequence, step_id, step_type, status, step, submission, output, receipt, external_operation
             FROM adapter_steps WHERE run_id=%s ORDER BY sequence""", (run_id,)).fetchall()
    keys = ("sequence", "step_id", "step_type", "status", "step", "submission", "output", "receipt", "external_operation")
    out = []
    for r in rows:
        d = dict(zip(keys, r))
        for k in ("step", "submission", "output", "receipt", "external_operation"):
            d[k] = _load(d[k])
        out.append(d)
    return out


def finish_step(conn, run_id: str, sequence: int, *, status: str, receipt: dict[str, Any], output: Any = None,
                submission: dict[str, Any] | None = None, external: dict[str, Any] | None = None) -> None:
    conn.execute(
        """UPDATE adapter_steps SET status=%s, receipt=%s::jsonb, output=COALESCE(%s::jsonb, output),
               submission=COALESCE(%s::jsonb, submission), external_operation=COALESCE(%s::jsonb, external_operation),
               ended_at=CASE WHEN %s IN ('accepted','executed','failed','skipped') THEN now() ELSE ended_at END
           WHERE run_id=%s AND sequence=%s""",
        (status, _j(receipt), _j(output) if output is not None else None, _j(submission) if submission else None,
         _j(external) if external else None, status, run_id, sequence))


def insert_result(conn, run_id: str, result: dict[str, Any], result_hash: str) -> None:
    conn.execute("""INSERT INTO adapter_results (run_id, result, result_hash) VALUES (%s,%s::jsonb,%s)
                    ON CONFLICT (run_id) DO NOTHING""", (run_id, _j(result), result_hash))


def load_result(conn, run_id: str) -> dict[str, Any] | None:
    row = conn.execute("SELECT result FROM adapter_results WHERE run_id=%s", (run_id,)).fetchone()
    return _load(row[0]) if row else None


# ─────────────────────────────────────────────────────────── worker leases
def claim_run(conn, owner: str, lease_s: int) -> str | None:
    """Lease ONE running adapter run whose lease is free or expired (FOR UPDATE SKIP LOCKED: many workers, no double-claim)."""
    row = conn.execute(
        """SELECT run_id FROM adapter_runs
            WHERE status='running' AND (lease_expires_at IS NULL OR lease_expires_at < now())
            ORDER BY updated_at LIMIT 1 FOR UPDATE SKIP LOCKED""").fetchone()
    if not row:
        return None
    conn.execute("UPDATE adapter_runs SET lease_owner=%s, lease_expires_at=now() + make_interval(secs => %s) WHERE run_id=%s",
                 (owner, lease_s, row[0]))
    return row[0]


def renew_lease(conn, run_id: str, owner: str, lease_s: int) -> bool:
    cur = conn.execute("UPDATE adapter_runs SET lease_expires_at=now() + make_interval(secs => %s) WHERE run_id=%s AND lease_owner=%s",
                       (lease_s, run_id, owner))
    return cur.rowcount == 1


def release_lease(conn, run_id: str, owner: str) -> None:
    conn.execute("UPDATE adapter_runs SET lease_owner=NULL, lease_expires_at=NULL WHERE run_id=%s AND lease_owner=%s", (run_id, owner))


def delete_run(conn, run_id: str) -> None:
    """Test cleanup only (cascades to steps/results)."""
    conn.execute("DELETE FROM adapter_runs WHERE run_id=%s", (run_id,))
