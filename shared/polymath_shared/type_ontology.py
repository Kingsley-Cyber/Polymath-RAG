"""Type ontology loader (type-ontology-v1).

The knowledge-object hierarchy behind predicate-signature families.
Signature tokens in a rule pack may name either a concrete CoreType or
an ontology node; `expand_type` resolves any token to the set of
concrete canonical types it covers. Unknown tokens fail loudly —
a signature that references nothing real is a pack-authoring bug, not
a runtime guess.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml

from polymath_shared.contracts import CoreType

_ONTOLOGY_PATH = Path(__file__).resolve().parent / "type_ontology.yaml"


@lru_cache(maxsize=4)
def _load(path: str, mtime: float) -> dict:
    return yaml.safe_load(Path(path).read_text())


def ontology() -> dict:
    st = _ONTOLOGY_PATH.stat()
    return _load(str(_ONTOLOGY_PATH), st.st_mtime)


def node_names() -> set[str]:
    return set(ontology()["nodes"].keys())


def concrete_leaves(node: str) -> set[str]:
    """All CoreType values `node` covers: itself when it is canonical,
    plus everything reachable below it."""
    enum_values = {t.value for t in CoreType}
    nodes = ontology()["nodes"]
    if node not in nodes:
        raise ValueError(
            f"type ontology has no node {node!r}; signature families must "
            "reference declared nodes or canonical types")
    out: set[str] = set()
    stack = [node]
    while stack:
        cur = stack.pop()
        if cur in enum_values:
            out.add(cur)
        stack.extend(nodes[cur].get("children") or [])
    return out


def expand_type(token: str) -> frozenset[str]:
    """Signature token -> concrete canonical type set.

    A declared ontology node expands to itself (when canonical) plus its
    descendants — hybrid nodes like Method are both a type and a family.
    A bare canonical type with no node expands to itself. Anything else
    is an authoring error."""
    return frozenset(concrete_leaves(token))


def validate_closure() -> None:
    """Structural closure: every canonical type is covered by exactly one
    declared node path, and no type is declared twice."""
    enum_values = {t.value for t in CoreType}
    nodes = ontology()["nodes"]
    declared = [k for k in nodes if k in enum_values]
    dupes = sorted({v for v in declared if declared.count(v) > 1})
    covered: set[str] = set()
    for v in enum_values:
        covered |= expand_type(v)
    missing = sorted(enum_values - covered)
    orphans = sorted(set(nodes) - enum_values
                     - {n for n, spec in nodes.items() if spec.get("abstract")})
    if dupes or missing or orphans:
        raise ValueError(
            f"type ontology closure violated; duplicates={dupes}, "
            f"missing={missing}, orphan_nodes={orphans}")


def expand_signature(sig: dict) -> dict:
    """Expand one rule-pack signature's subject_core/object_core lists."""
    out = dict(sig)
    for side in ("subject_core", "object_core"):
        values = sig.get(side) or []
        expanded: list[str] = []
        for token in values:
            expanded.extend(sorted(expand_type(token)))
        out[side] = list(dict.fromkeys(expanded))
    return out
