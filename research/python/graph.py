"""Control-graph loader + structural validation + legal-transition logic.

Config loading FAILS CLOSED (docs/15 §1): a duplicate YAML key silently
shadowing an earlier declaration is exactly the kind of bug that produces
subtly wrong research — so the loader rejects it instead of last-wins.
"""
from __future__ import annotations

import os

import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class _StrictLoader(yaml.SafeLoader):
    pass


def _no_duplicate_keys(loader, node, deep=False):
    seen = set()
    for k_node, _ in node.value:
        key = loader.construct_object(k_node, deep=deep)
        if key in seen:
            raise yaml.YAMLError(
                f"duplicate YAML key {key!r} at line {k_node.start_mark.line + 1} — "
                "fail closed, never last-wins")
        seen.add(key)
    return yaml.SafeLoader.construct_mapping(loader, node, deep=deep)


_StrictLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _no_duplicate_keys)


def loads(text: str) -> dict:
    """Strict-parse YAML text (duplicate keys are a hard error)."""
    return yaml.load(text, Loader=_StrictLoader)


def load_yaml_file(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return loads(f.read())


def load_graph(name: str = "control_graph.yaml") -> dict:
    if not name.endswith(".yaml"):
        name += ".yaml"
    return load_yaml_file(os.path.join(ROOT, "graph", os.path.basename(name)))


def load_policies() -> dict:
    pol = load_yaml_file(os.path.join(ROOT, "graph", "policies.yaml"))
    try:  # mode policies overlay (loadout math weights etc.)
        pol.update(load_yaml_file(os.path.join(ROOT, "graph", "loadout_policies.yaml")) or {})
    except OSError:
        pass
    return pol


def validate_graph(g: dict) -> list[str]:
    errors = []
    nodes = g.get("nodes") or {}
    entry = (g.get("graph") or {}).get("entry")
    if entry not in nodes:
        errors.append(f"entry node {entry!r} not defined")
    terminals = [n for n, spec in nodes.items() if (spec or {}).get("type") == "terminal"]
    if not terminals:
        errors.append("no terminal node")
    for i, e in enumerate(g.get("edges") or []):
        for end in ("from", "to"):
            if e.get(end) not in nodes:
                errors.append(f"edge[{i}].{end}={e.get(end)!r} undefined")
    # every non-terminal node must have at least one outgoing edge
    outs = {e["from"] for e in g.get("edges") or [] if e.get("from") in nodes}
    for n, spec in nodes.items():
        if (spec or {}).get("type") != "terminal" and n not in outs:
            errors.append(f"node {n!r} has no outgoing edge")
    # docs/10: every model-executed node must declare a ContextContract —
    # "here is what the next reasoning call is legally allowed and required
    # to know", not hope that the agent remembers what matters
    for n, spec in nodes.items():
        if (spec or {}).get("type") in ("reason", "retrieve", "agent"):
            ctx = (spec or {}).get("context") or {}
            if not (ctx.get("require") or ctx.get("prefer")):
                errors.append(f"node {n!r} ({spec['type']}) missing ContextContract")
            overlap = set(ctx.get("require") or []) & set(ctx.get("exclude") or [])
            if overlap:
                errors.append(f"node {n!r} contract requires AND excludes {sorted(overlap)}")
    return errors


def outgoing(g: dict, node: str) -> list[dict]:
    return [e for e in g.get("edges") or [] if e.get("from") == node]


def node_spec(g: dict, node: str) -> dict:
    return (g.get("nodes") or {}).get(node) or {}
