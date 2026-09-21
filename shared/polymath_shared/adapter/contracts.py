"""Contract access for contracts/adapter/v1 — schema loading, validation, canonical hashing. Pure."""
from __future__ import annotations

import hashlib
import json
from functools import lru_cache
from pathlib import Path
from typing import Any

import jsonschema

#: repository root = .../shared/polymath_shared/adapter/contracts.py -> parents[3]
_REPO = Path(__file__).resolve().parents[3]
CONTRACT_DIR = _REPO / "contracts" / "adapter" / "v1"

STEP_TYPES = ("POLYMATH_RETRIEVE", "POLYMATH_COMPILE_PLAN", "POLYMATH_GRAPH_EXPAND", "EXTERNAL_OPERATION", "DOMAIN_OPERATION",
              "AGENT_REASON", "HARNESS_ACTION", "VALIDATE", "BRANCH", "COMPILE_RESULT")
#: steps answered through adapter_submit: AGENT_REASON by the connected agent (reasoning), HARNESS_ACTION by the host
#: harness (a HarnessResearchReceiptV1). Every other step is executed by the runtime.
AGENT_ANSWERED_STEP_TYPES = frozenset({"AGENT_REASON", "HARNESS_ACTION"})
AUTOMATIC_STEP_TYPES = frozenset(STEP_TYPES) - AGENT_ANSWERED_STEP_TYPES
RUN_STATUSES = ("created", "running", "awaiting_agent", "awaiting_harness", "completed", "terminal_gap", "cancelled", "failed")
# ── ADR-0019 closed cognitive vocabulary (generic: the engine knows hypotheses and transitions, never a domain)
HARNESS_ACTION_KINDS = ("AGENT_RESEARCH", "PRODUCT_REALITY_CHECK", "SUPPLIER_RESEARCH")
THETA_OPS = ("generate_hypotheses", "derive_mechanisms", "cross_map_frictions", "derive_physical_jobs", "derive_analogies",
             "split_hypotheses", "generate_product_mechanisms")
PHI_OPS = ("reject", "merge", "deduplicate", "weaken", "strengthen", "challenge", "require_evidence", "promote")
HYPOTHESIS_STATUSES = ("proposed", "filtered", "retained", "revised", "split", "merged", "weakened", "strengthened",
                       "contradicted", "killed", "promoted")
TRANSITION_KINDS = ("GENERATE", "REVISE", "SPLIT", "MERGE", "WEAKEN", "STRENGTHEN", "CONTRADICT", "KILL", "PROMOTE")
TRANSITION_ACTORS = ("theta", "phi", "runtime")
#: evidence roles are DOMAIN DATA: declared by a manifest (`evidence_roles`) and by the Trail registry snapshot, never here
EVIDENCE_ROLE_PATTERN = r"^[a-z][a-z0-9_]{1,40}$"
#: evidence-ref kinds an agent may CITE (knowledge + Trail-admitted field evidence); `trail_prior` is a coordinate, never evidence
CITABLE_EVIDENCE_KINDS = frozenset({"chunk", "document", "graph_fact", "graph_hop", "parent_map", "field_evidence"})
PRIOR_EVIDENCE_KINDS = frozenset({"trail_prior"})
#: ORIGIN LINKAGE (restoration reference §8.3): ids of the lead(s) / latent structure(s) a hypothesis came from. They are LINEAGE ids
#: of the run's own step outputs — NOT evidence citations — so the `*_ids` citation convention does not read them; the ledger checks
#: them against what the run actually produced instead.
ORIGIN_ID_FIELDS = ("lead_ids", "latent_structure_ids")
TERMINAL_RUN_STATUSES = frozenset({"completed", "terminal_gap", "cancelled", "failed"})
STEP_STATUSES = ("issued", "accepted", "rejected", "executed", "failed", "skipped")


class ContractViolation(ValueError):
    """An instance does not satisfy its contracts/adapter/v1 schema."""

    def __init__(self, name: str, errors: list[str]) -> None:
        super().__init__(f"{name}: " + "; ".join(errors[:5]))
        self.name = name
        self.errors = errors


@lru_cache(maxsize=None)
def schema(name: str) -> dict[str, Any]:
    path = CONTRACT_DIR / f"{name}.schema.json"
    if not path.exists():
        raise KeyError(f"unknown adapter contract {name!r}")
    return json.loads(path.read_text())


@lru_cache(maxsize=None)
def _validator(name: str) -> jsonschema.Draft202012Validator:
    return jsonschema.Draft202012Validator(schema(name), format_checker=jsonschema.FormatChecker())


def validate(name: str, instance: Any) -> list[str]:
    """All violations of contract ``name`` for ``instance`` (empty list = valid). Deterministic order."""
    errs = sorted(_validator(name).iter_errors(instance), key=lambda e: (list(map(str, e.path)), e.message))
    return [("/".join(map(str, e.path)) or "$") + ": " + e.message for e in errs]


def assert_valid(name: str, instance: Any) -> None:
    errors = validate(name, instance)
    if errors:
        raise ContractViolation(name, errors)


def stable_hash(obj: Any) -> str:
    """sha256 over canonical JSON (sorted keys, no whitespace) — the receipt/submission hash."""
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")).hexdigest()
