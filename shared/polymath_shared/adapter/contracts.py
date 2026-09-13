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

STEP_TYPES = ("POLYMATH_RETRIEVE", "POLYMATH_COMPILE_PLAN", "POLYMATH_GRAPH_EXPAND", "EXTERNAL_OPERATION",
              "AGENT_REASON", "VALIDATE", "BRANCH", "COMPILE_RESULT")
#: steps the runtime executes itself; AGENT_REASON is the only step a connected agent answers
AUTOMATIC_STEP_TYPES = frozenset(STEP_TYPES) - {"AGENT_REASON"}
RUN_STATUSES = ("created", "running", "awaiting_agent", "completed", "terminal_gap", "cancelled", "failed")
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
