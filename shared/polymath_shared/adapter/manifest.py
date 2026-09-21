"""Admitted adapter manifests (config/adapters/*.json): load, validate, graph integrity. Pure."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .contracts import _REPO, STEP_TYPES, validate

#: ADR-0020 — a DOMAIN_OPERATION names a directory under adapters/ and a dotted operation id of that domain's binding
_DOMAIN_RE = re.compile(r"^[a-z][a-z0-9_]{1,40}$")
_DOMAIN_OP_RE = re.compile(r"^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*){0,5}$")


def _is_input_path(v: Any) -> bool:
    """A DOMAIN_OPERATION input selects ONE value by dotted path, or a LIST of values by a non-empty list of dotted paths."""
    if isinstance(v, str):
        return bool(v)
    return isinstance(v, list) and bool(v) and all(isinstance(x, str) and x for x in v)

ADAPTER_DIR = _REPO / "config" / "adapters"


class ManifestError(ValueError):
    pass


@dataclass(frozen=True)
class Manifest:
    adapter_id: str
    adapter_version: str
    workflow_version: str
    retrieval_policy_version: str
    input_schema_version: str
    output_schema_version: str
    entry_step_id: str
    terminal_step_id: str
    budgets: dict[str, int]
    steps: dict[str, dict[str, Any]]          # step_id -> step definition (insertion order = manifest order)
    raw: dict[str, Any]

    @property
    def identity(self) -> dict[str, str]:
        return {k: getattr(self, k) for k in ("adapter_id", "adapter_version", "workflow_version",
                                              "retrieval_policy_version", "input_schema_version", "output_schema_version")}

    def step(self, step_id: str) -> dict[str, Any]:
        try:
            return self.steps[step_id]
        except KeyError:
            raise ManifestError(f"{self.adapter_id}: unknown step {step_id!r}") from None


def graph_integrity_errors(raw: dict[str, Any]) -> list[str]:
    """Invariants the JSON Schema cannot express (mirrors tests/contracts/test_adapter_contract_v1.py)."""
    errs: list[str] = []
    steps = raw.get("steps") or []
    ids = [s.get("step_id") for s in steps]
    if len(ids) != len(set(ids)):
        errs.append("duplicate step_id")
    by_id = {s.get("step_id"): s for s in steps}
    entry, terminal = raw.get("entry_step_id"), raw.get("terminal_step_id")
    if entry not in by_id:
        errs.append(f"entry_step_id {entry!r} is not a step")
    if terminal not in by_id:
        errs.append(f"terminal_step_id {terminal!r} is not a step")
    elif by_id[terminal].get("type") != "COMPILE_RESULT":
        errs.append("terminal step must be COMPILE_RESULT")
    for s in steps:
        sid, typ, nxt = s.get("step_id"), s.get("type"), s.get("next")
        if typ not in STEP_TYPES:
            errs.append(f"{sid}: unknown type {typ!r}")
        if typ == "COMPILE_RESULT":
            if nxt is not None:
                errs.append(f"{sid}: COMPILE_RESULT has no successor")
        elif nxt not in by_id:
            errs.append(f"{sid}: next {nxt!r} is not a step")
        for b in s.get("branches") or []:
            if b.get("next") not in by_id:
                errs.append(f"{sid}: branch target {b.get('next')!r} is not a step")
        if typ == "AGENT_REASON" and not (s.get("objective") and s.get("output_schema")):
            errs.append(f"{sid}: AGENT_REASON needs objective + output_schema")
        if typ == "EXTERNAL_OPERATION":
            ext = s.get("external") or {}
            if ext.get("system") != "trailsignal":
                errs.append(f"{sid}: EXTERNAL_OPERATION must name system=trailsignal")
            if ext.get("availability") == "planned" and not ext.get("planned_node"):
                errs.append(f"{sid}: a planned Trail capability names its graph node")
        if typ == "DOMAIN_OPERATION":
            # ADR-0020: the manifest NAMES domain code (a directory under adapters/ + an operation id); the runtime never does
            cfg = s.get("config") or {}
            if not _DOMAIN_RE.match(str(cfg.get("domain") or "")):
                errs.append(f"{sid}: DOMAIN_OPERATION needs config.domain (a directory name under adapters/)")
            if not _DOMAIN_OP_RE.match(str(cfg.get("operation") or "")):
                errs.append(f"{sid}: DOMAIN_OPERATION needs config.operation (a dotted operation id)")
            ins = cfg.get("inputs", {})
            if not isinstance(ins, dict) or not all(isinstance(k, str) and _is_input_path(v) for k, v in ins.items()):
                errs.append(f"{sid}: DOMAIN_OPERATION config.inputs maps a name to a dotted path (or a list of dotted paths)")
        elif any(k in (s.get("config") or {}) for k in ("domain", "operation")):
            errs.append(f"{sid}: config.domain / config.operation are only valid on DOMAIN_OPERATION")
        show = (s.get("config") or {}).get("show")
        if show is not None:
            # ADR-0020 addendum: only a step the agent / harness answers may be SHOWN prior outputs (name -> dotted path)
            if typ not in ("AGENT_REASON", "HARNESS_ACTION"):
                errs.append(f"{sid}: config.show is only valid on AGENT_REASON / HARNESS_ACTION")
            elif not isinstance(show, dict) or not show or not all(isinstance(k, str) and isinstance(v, str) and v.startswith(("outputs.", "input.")) for k, v in show.items()):
                errs.append(f"{sid}: config.show maps a name to a dotted path under outputs. or input.")
        if typ == "BRANCH" and not (s.get("branches") or nxt):
            errs.append(f"{sid}: BRANCH needs branches or a default next")
        # ADR-0019: HARNESS_ACTION is a typed hand-off to the host harness; theta ops belong to AGENT_REASON only; and
        # an evidence-gap loop must return through reasoning, never straight into another research action
        if typ == "HARNESS_ACTION":
            if not ((s.get("harness") or {}).get("action_kind") and s.get("objective")):
                errs.append(f"{sid}: HARNESS_ACTION needs harness.action_kind + objective")
        elif s.get("harness") is not None:
            errs.append(f"{sid}: only a HARNESS_ACTION step may carry `harness`")
        if s.get("theta_op") is not None and typ != "AGENT_REASON":
            errs.append(f"{sid}: theta_op is only valid on AGENT_REASON")
        if typ == "BRANCH":
            for b in s.get("branches") or []:
                tgt = by_id.get(b.get("next")) or {}
                if tgt.get("type") == "HARNESS_ACTION":
                    errs.append(f"{sid}: a BRANCH may not target HARNESS_ACTION {b.get('next')!r} directly (loop through reasoning)")
    if entry in by_id and terminal in by_id:
        seen, todo = set(), [entry]
        while todo:
            cur = todo.pop()
            if cur in seen or cur not in by_id:
                continue
            seen.add(cur)
            s = by_id[cur]
            todo += [x for x in ([s.get("next")] + [b.get("next") for b in s.get("branches") or []]) if x]
        if terminal not in seen:
            errs.append("terminal step is unreachable from the entry step")
    return errs


def load_manifest(path: Path) -> Manifest:
    raw = json.loads(Path(path).read_text())
    errors = validate("adapter_manifest", raw) + graph_integrity_errors(raw)
    if errors:
        raise ManifestError(f"{path.name}: " + "; ".join(errors[:5]))
    return Manifest(adapter_id=raw["adapter_id"], adapter_version=raw["adapter_version"], workflow_version=raw["workflow_version"],
                    retrieval_policy_version=raw["retrieval_policy_version"], input_schema_version=raw["input_schema_version"],
                    output_schema_version=raw["output_schema_version"], entry_step_id=raw["entry_step_id"],
                    terminal_step_id=raw["terminal_step_id"], budgets=dict(raw["budgets"]),
                    steps={s["step_id"]: s for s in raw["steps"]}, raw=raw)


def list_manifests(directory: Path = ADAPTER_DIR) -> list[Manifest]:
    """Every admitted manifest, sorted by adapter_id. A malformed file fails LOUDLY (never silently skipped)."""
    out = [load_manifest(p) for p in sorted(Path(directory).glob("*.json"))]
    ids = [m.adapter_id for m in out]
    if len(ids) != len(set(ids)):
        raise ManifestError(f"duplicate adapter_id in {directory}: {ids}")
    return sorted(out, key=lambda m: m.adapter_id)
