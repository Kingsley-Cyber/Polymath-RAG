"""CONTROL-PLANE-V2 execution identity (ADR-0014).

Workers advertise WHO they are (build SHA + contract versions); runs
pin WHAT they require (the execution contract). Leasing checks the
two against each other — an incompatible or stale worker is refused
and marked, never mysteriously served.
"""
from __future__ import annotations

import os
import socket
import subprocess
import time
import uuid
from typing import Any

from psycopg import Connection

STALE_AFTER_S = 90.0  # ~3 control ticks + margin


def _build_sha() -> str:
    sha = os.environ.get("POLYMATH_BUILD_SHA", "").strip()
    if sha:
        return sha
    from pathlib import Path

    repo_root = Path(__file__).resolve().parents[2]
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, timeout=5, cwd=str(repo_root),
        )
        return out.stdout.strip() if out.returncode == 0 else "unknown"
    except Exception:
        return "unknown"


SEMANTIC_CONTRACT_V1_1 = "admission-v1.1"
SEMANTIC_CONTRACT_V2 = "admission-harbor-v2"


def semantic_authorities() -> dict[str, Any]:
    """PRODUCTION-WIRING-GATE S2 — every authority capable of changing
    mention interpretation, entity identity, graph eligibility, canonical
    membership or fact identity.

    Same source + same pinned bundle MUST reproduce the same identities and
    facts. Anything omitted here is a hole in deterministic replay.

    Pinned in S2; NOT yet live. Historical runs keep `semantic_contract`
    NULL and are never rewritten to claim V2.
    """
    from polymath_shared.concept_evidence import CONCEPT_CONTRACT
    from polymath_shared.contraction_resolution import CONTRACTION_CONTRACT
    from polymath_shared.discourse_reference import (
        DISCOURSE_CONTRACT, POLICY_SHA256, POLICY_VERSION,
    )
    from polymath_shared.entity_harbor import HARBOR_CONTRACT
    from polymath_shared.generic_classification import GENERIC_CONTRACT
    from polymath_shared.identity_allocation import (
        IDENTITY_ALLOCATION_CONTRACT, TYPE_ALIGNMENT_CONTRACT,
    )
    from polymath_shared.identity_evidence import IDENTITY_CONTRACT
    from polymath_shared.layout_evidence import LAYOUT_CONTRACT
    from polymath_shared.referential_span import REFERENTIAL_SPAN_CONTRACT
    from polymath_shared.settings import get_settings

    s = get_settings()
    return {
        "semantic_contract": SEMANTIC_CONTRACT_V2,
        "identity_precision_contract": IDENTITY_CONTRACT,
        "entity_harbor_contract": HARBOR_CONTRACT,
        "referential_envelope_contract": REFERENTIAL_SPAN_CONTRACT,
        "discourse_reference_contract": DISCOURSE_CONTRACT,
        "discourse_reference_policy": POLICY_VERSION,
        "discourse_reference_policy_sha256": POLICY_SHA256,
        "concept_evidence_contract": CONCEPT_CONTRACT,
        "contraction_resolution_contract": CONTRACTION_CONTRACT,
        "generic_classification_contract": GENERIC_CONTRACT,
        "identity_allocation_contract": IDENTITY_ALLOCATION_CONTRACT,
        "type_identity_alignment_contract": TYPE_ALIGNMENT_CONTRACT,
        "layout_evidence_contract": LAYOUT_CONTRACT,
        # Declared contract IDs are not enough on their own: a semantic
        # authority can be EDITED without its version string moving, and a
        # worker holding that older code would still advertise the same
        # bundle. Hashing the authorities' source closes that gap, which is
        # exactly the stale-worker case (identity_allocation.py changed and
        # bumped no version).
        "authority_code_sha256": _authority_code_sha256(),
        # eligibility and the fact gate live in the Harbor module and are
        # versioned with it; named separately so a future split is visible.
        "graph_eligibility_contract": HARBOR_CONTRACT,
        "canonical_fact_gate_contract": HARBOR_CONTRACT,
        # syntax is a HARD dependency of V2 (R1). Pinning which spaCy
        # contract governs regeneration is what makes reprocessing
        # deterministic: old rows parsed with model X and new rows with
        # model Y under one execution_contract would defeat replay.
    }


# Modules that can change mention interpretation, entity identity, graph
# eligibility, canonical membership or fact identity. Editing any of them
# changes the semantics of a run, whether or not a version string moves.
_SEMANTIC_AUTHORITY_MODULES = (
    "admission_interpreter",
    "concept_evidence",
    "contraction_resolution",
    "discourse_reference",
    "entity_harbor",
    "generic_classification",
    "identity_allocation",
    "identity_evidence",
    "layout_evidence",
    "referential_span",
)


def _authority_code_sha256() -> str:
    """Content hash of the semantic authorities' source, in a fixed order."""
    import hashlib
    import pathlib

    here = pathlib.Path(__file__).parent
    h = hashlib.sha256()
    for name in _SEMANTIC_AUTHORITY_MODULES:
        h.update(name.encode())
        h.update(b"\x00")
        h.update(hashlib.sha256((here / f"{name}.py").read_bytes()).digest())
    return h.hexdigest()


def semantic_authority_sha256() -> str:
    """SEMANTIC-BUNDLE-WORKER-FENCE-V1 — the claim-gate identity.

    This is `semantic_authorities()` MINUS `syntax_model`, which is probed
    from a live sidecar and therefore goes None during a hiccup. Including a
    probed value in a claim gate would let a momentary sidecar blip change
    every worker's advertised bundle and stall the queue with tickets nothing
    can claim. The syntax dependency is already gated, and better, by
    `claim_eligible()` against FRESH capability — this hash answers the
    different question of whether the worker is running the same semantics.
    """
    import hashlib
    import json as _json

    surface = {k: v for k, v in semantic_authorities().items()
               if k != "syntax_model"}
    body = _json.dumps(surface, sort_keys=True, default=str)
    return hashlib.sha256(body.encode()).hexdigest()


def semantic_bundle_sha256() -> str:
    """One hash over the whole semantic authority surface."""
    import hashlib
    import json as _json

    body = _json.dumps(semantic_authorities(), sort_keys=True, default=str)
    return hashlib.sha256(body.encode()).hexdigest()


def worker_contracts() -> dict[str, Any]:
    """The contract surface a worker runs with, resolved from settings —
    the same identity inputs the extraction contract hash uses."""
    from polymath_shared.query_policy import active_policy_version
    from polymath_shared.settings import get_settings

    s = get_settings()
    from polymath_shared.execution_bundle import semantic_file_hashes
    files = semantic_file_hashes()
    return {
        "query_policy": active_policy_version(),
        "chunker": s.worker.chunker,
        # SEMANTIC-BUNDLE-WORKER-FENCE-V1: what semantics this process can
        # actually execute. A worker alive but running older code advertises
        # a different value and is refused the ticket.
        "semantic_bundle": semantic_authority_sha256(),
        # EXECUTION-BUNDLE-FENCE-V1: lexical/semantic authority FILE hashes.
        # The ontology realization edit moved no existing fence because the
        # yaml escapes the python-module code hash; these close that hole,
        # so contract reconciliation mints successors when they change.
        "ontology_file_sha": files["scientific-predicate-ontology-v2.yaml"],
        # GENERATION-SWAP-V1 (2026-09-03): the LLM gate is the sole durability
        # authority (ADR-0017); a gate/attestation change must be contract
        # drift the reconciler can see, or `reingest_corpus.py` reports
        # "nothing to re-ingest" after the very change that needs one.
        "extraction_gate": _extraction_gate_contract(),
    }


def _extraction_gate_contract() -> str:
    from polymath_shared.llm_extraction.gate import GATE_VERSION, attestation_policy
    # TYPED-CLAIMS-V1 (2026-09-03): the extraction prompt/schema now labels lived claims;
    # a prompt-contract change is an extraction-contract change, so blue/green REGENERATES extract
    # instead of carrying the untyped predecessor stage.
    return str(f"{GATE_VERSION}/{attestation_policy()}") + "|typed_claims=v1"


def worker_identity(worker_type: str) -> dict[str, Any]:
    from polymath_shared.execution_bundle import (
        bundle_id,
        compute_execution_bundle,
    )

    bundle = compute_execution_bundle()
    return {
        "worker_id": f"{worker_type}-{os.getpid()}-{uuid.uuid4().hex[:8]}",
        "worker_type": worker_type,
        "pid": os.getpid(),
        "host": socket.gethostname(),
        "build_sha": _build_sha(),
        "contracts": worker_contracts(),
        "started_at": time.time(),
        # EXECUTION-BUNDLE-FENCE-V1
        "execution_bundle": bundle,
        "execution_bundle_id": bundle_id(bundle),
    }


def register_worker(conn: Connection, identity: dict[str, Any]) -> None:
    import json

    bundle = identity.get("execution_bundle") or {}
    conn.execute(
        """
        INSERT INTO execution_bundles
            (bundle_hash, git_sha, tree_dirty, semantic_authority,
             rule_pack_file, ontology_file, config)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (bundle_hash) DO UPDATE SET last_seen_at = now()
        """,
        (bundle.get("execution_bundle_hash", ""),
         bundle.get("git_sha", ""),
         bundle.get("tree_dirty") == "True",
         bundle.get("semantic_authority", ""),
         bundle.get("rule_pack_file", ""),
         bundle.get("ontology_file", ""),
         json.dumps(bundle.get("config", {}))),
    )
    conn.execute(
        """
        INSERT INTO worker_registrations
            (worker_id, worker_type, pid, host, build_sha, contracts,
             status, execution_bundle_hash, execution_bundle)
        VALUES (%s, %s, %s, %s, %s, %s, 'healthy', %s, %s)
        ON CONFLICT (worker_id) DO UPDATE SET
            pid = EXCLUDED.pid, host = EXCLUDED.host,
            build_sha = EXCLUDED.build_sha, contracts = EXCLUDED.contracts,
            status = 'healthy', started_at = now(), heartbeat_at = now(),
            execution_bundle_hash = EXCLUDED.execution_bundle_hash,
            execution_bundle = EXCLUDED.execution_bundle
        """,
        (identity["worker_id"], identity["worker_type"], identity["pid"],
         identity["host"], identity["build_sha"],
         json.dumps(identity["contracts"]),
         bundle.get("execution_bundle_hash", ""), json.dumps(bundle)),
    )


#: Sentinel distinguishing "leave current_ticket alone" (the default)
#: from an explicit None ("clear it"). The old COALESCE(%s, ...) form
#: could never clear: a worker that finished a stage kept advertising
#: its last ticket forever, which made every idle worker look mid-stage
#: (measured while diagnosing STALL-2026-08-27).
_TICKET_UNSET = object()


def heartbeat(conn: Connection, worker_id: str, *,
              current_ticket: object = _TICKET_UNSET,
              processed_count: int | None = None,
              last_error: str | None = None) -> None:
    """Touch the registration; revive from stale on activity.

    `processed_count` is a DELTA, not an absolute: pass 1 per completed
    ticket. (It was previously assigned verbatim, so every worker
    reported a lifetime count of exactly 1 regardless of throughput.)
    """
    set_ticket = current_ticket is not _TICKET_UNSET
    ticket_value = current_ticket if set_ticket else None
    conn.execute(
        """
        UPDATE worker_registrations SET
            heartbeat_at = now(),
            status = CASE WHEN status = 'stale' THEN 'healthy' ELSE status END,
            current_ticket = CASE WHEN %s THEN %s ELSE current_ticket END,
            processed_count = processed_count + COALESCE(%s, 0),
            last_error = %s
        WHERE worker_id = %s
        """,
        (set_ticket, ticket_value, processed_count, last_error, worker_id),
    )


def compatible(worker_contracts: dict[str, Any],
              execution_contract: dict[str, Any]) -> bool:
    """Lease rule: the worker must run the build the run pinned (when
    the run pinned one) and the same semantic-policy surface. URL-level
    identity (which sidecar instance) must match exactly; semantic
    versions must match; unspecified run requirements pass."""
    required_build = execution_contract.get("worker_build")
    if required_build and worker_contracts.get("build_sha") != required_build:
        return False
    # SEMANTIC-BUNDLE-WORKER-FENCE-V1. A stale process is ALIVE, so liveness
    # checks pass and supervision sees nothing wrong; it simply computes
    # different semantics. Refusing the claim is what makes a semantic
    # cutover atomic across the fleet instead of silently mixed.
    # Runs pinned before this fence existed carry no `semantic_bundle` and
    # are unaffected.
    want_bundle = execution_contract.get("semantic_bundle")
    if want_bundle is not None and worker_contracts.get("semantic_bundle") != want_bundle:
        return False
    for key in ("query_policy", "chunker"):
        want = execution_contract.get(key)
        if want is not None and worker_contracts.get(key) != want:
            return False
    # (S3 syntax claim-eligibility retired with the spaCy sidecar — ADR-0017.)
    return True


def default_execution_contract() -> dict[str, Any]:
    """What a run pins when the submitter doesn't say: the fleet's
    CURRENT configuration — captured at ticket creation by the control
    plane, not by the worker."""
    return dict(worker_contracts())
