"""COGNITIVE-ADAPTER-V1 (ADR-0018): the pure, I/O-free core of the Polymath cognitive-adapter runtime.

Deterministic adapter definitions (manifests), JSON-Schema validation against `contracts/adapter/v1`, the CLOSED
step vocabulary, the branch-predicate evaluator and the run/step state-transition rules. No database, no HTTP,
no provider call lives here — the orchestrator (MCP tools) and the adapter step worker compose these functions
with the existing Postgres receipts/outbox/lease primitives.
"""
from .contracts import (STEP_TYPES, RUN_STATUSES, STEP_STATUSES, TERMINAL_RUN_STATUSES, schema, validate,
                        assert_valid, ContractViolation, stable_hash)
from .manifest import Manifest, ManifestError, load_manifest, list_manifests, graph_integrity_errors, ADAPTER_DIR
from .transitions import (RunState, SubmissionRejected, BudgetExhausted, evaluate_predicate, next_step_id, issue_step,
                          validate_submission, accept_submission, record_automatic_output, cancel_run, terminal_gap,
                          start_run, complete_run, run_status_view)

__all__ = [n for n in dir() if not n.startswith("_")]
