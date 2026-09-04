"""Deterministic data layer: schema-lite validation + work-state IO.

No third-party deps beyond PyYAML (already in the Hermes venv). Validation
reads the `required` arrays and `enum` constraints straight from the JSON
schema files, so schemas/ stays the single source of truth.
"""
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCHEMAS = os.path.join(ROOT, "schemas")


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def stable_id(*parts: str) -> str:
    return hashlib.sha256("|".join(str(p) for p in parts).encode()).hexdigest()[:12]


def load_schema(name: str) -> dict:
    with open(os.path.join(SCHEMAS, f"{name}.json"), encoding="utf-8") as f:
        return json.load(f)


def _type_ok(value, t: str) -> bool:
    if t == "object":
        return isinstance(value, dict)
    if t == "array":
        return isinstance(value, list)
    if t == "string":
        return isinstance(value, str)
    if t == "boolean":
        return isinstance(value, bool)
    if t == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if t == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if t == "null":
        return value is None
    return True  # unknown type words never fail closed on the type axis


def _walk(value, spec: dict, path: str, errors: list[str]) -> None:
    """Recursive validation over the JSON-schema subset the skill's schemas
    use: type (incl. lists and the `{"enum": [...]}` shorthand two schemas
    carry), enum, required, properties, items, additionalProperties,
    minItems/maxItems, minimum/maximum. Required means present AND not
    null/empty-string — the controller's long-standing rule."""
    if not isinstance(spec, dict):
        return
    t = spec.get("type")
    if isinstance(t, dict):                       # "type": {"enum": [...]} shorthand
        if t.get("enum") is not None and value not in t["enum"]:
            errors.append(f"{path}: {value!r} not in {t['enum']}")
        t = None
    if t is not None:
        types = t if isinstance(t, list) else [t]
        if not any(_type_ok(value, x) for x in types):
            errors.append(f"{path}: expected {'|'.join(map(str, types))}, got {type(value).__name__}")
            return
    enum = spec.get("enum")
    if enum is not None and value not in enum:
        errors.append(f"{path}: {value!r} not in {enum}")
    if isinstance(value, dict):
        for key in spec.get("required", []):
            if key not in value or value[key] in (None, ""):
                errors.append(f"{path}.{key}: required")
        props = spec.get("properties") or {}
        for key, sub in props.items():
            if key in value and isinstance(sub, dict):
                _walk(value[key], sub, f"{path}.{key}", errors)
        if spec.get("additionalProperties") is False:
            extra = sorted(set(value) - set(props))
            if extra:
                errors.append(f"{path}: unexpected keys {extra}")
    elif isinstance(value, list):
        items = spec.get("items")
        if isinstance(items, dict):
            for i, v in enumerate(value):
                _walk(v, items, f"{path}[{i}]", errors)
        if spec.get("minItems") is not None and len(value) < spec["minItems"]:
            errors.append(f"{path}: fewer than {spec['minItems']} items")
        if spec.get("maxItems") is not None and len(value) > spec["maxItems"]:
            errors.append(f"{path}: more than {spec['maxItems']} items")
    elif isinstance(value, (int, float)) and not isinstance(value, bool):
        if spec.get("minimum") is not None and value < spec["minimum"]:
            errors.append(f"{path}: {value} below minimum {spec['minimum']}")
        if spec.get("maximum") is not None and value > spec["maximum"]:
            errors.append(f"{path}: {value} above maximum {spec['maximum']}")


def validate(obj: dict, schema_name: str) -> list[str]:
    """Return a list of violations (empty = valid). Full recursive check of
    the schema subset in schemas/ (types, enums, required, nested objects,
    array items) — no external dependency (the Hermes venv has none)."""
    schema = load_schema(schema_name)
    if not isinstance(obj, dict):
        return [f"{schema_name}: not an object"]
    errors: list[str] = []
    _walk(obj, schema, schema_name, errors)
    return errors


def new_state(run_id: str, signal: str = "") -> dict:
    return {
        "run_id": run_id,
        "created_at": now(),
        "node": None,          # set by controller to graph entry
        "status": "running",
        "rounds": {"research": 0},
        "history": [],
        "verdict": None,
        "data": {
            "signal": signal,
            "corpus_queries": [],
            "communities": [],
            "research_allocation": [],
            "sourcing_plan": [],
            "sourcing_coverage": [],
            "product_concepts": [],
            "corpus_evidence": [],
            "primitives": {},
            "cross_domain_analogies": [],
            "lenses": [],
            "hypotheses": [],
            "challenges": [],
            "evaluations": [],
            "gaps": [],
            "queries": [],
            "observations": [],
            "mechanisms": [],
            "product_candidates": [],
            "supplier_candidates": [],
            "leads": [],
            "registry_candidates": [],
            "maintenance_triggers": [],
            "approvals": [],
            "promotion_summary": {},
            "registry_patch": {},
            "corpus_backend": {},
            "corpus_answers": [],
            "utilization": {},
            # LIVED-WORLD-V2 (docs/25): population discovery before ideation
            "population_leads": [],
            "community_leads": [],
            "field_records": [],
            "participant_cards": [],
            "lived_clusters": [],
            "lived_situations": [],
            "corpus_questions": [],
            "example_terms": [],
            "provenance": [],
            # docs/26: source-agnostic interpretation objects (mirrored from primitives at submit)
            "latent_structures": [],
            "corpus_observations": [],
            "row_relevance": {},
        },
    }


# Legacy vocabulary (pre corpus-neutral rename) — migrated once on load so old
# run states keep working; new submissions must use the current names.
_LEGACY_DATA_KEYS = {"polymath_evidence": "corpus_evidence"}
_LEGACY_NODES = {"polymath": "corpus"}
_LEGACY_SOURCE_FAMILIES = {"polymath_evergreen": "corpus_evergreen"}


def _migrate_legacy(state: dict) -> dict:
    data = state.get("data")
    if isinstance(data, dict):
        for old, new in _LEGACY_DATA_KEYS.items():
            if old in data:
                data.setdefault(new, data.pop(old))
        for obs in data.get("observations") or []:
            ident = obs.get("source_identity") if isinstance(obs, dict) else None
            if isinstance(ident, dict) and ident.get("source_family") in _LEGACY_SOURCE_FAMILIES:
                ident["source_family"] = _LEGACY_SOURCE_FAMILIES[ident["source_family"]]
    if state.get("node") in _LEGACY_NODES:
        state["node"] = _LEGACY_NODES[state["node"]]
    return state


def load_state(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return _migrate_legacy(json.load(f))


def save_state(state: dict, path: str) -> None:
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=1, ensure_ascii=False)
    os.replace(tmp, path)
