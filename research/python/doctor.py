#!/usr/bin/env python3
"""Configuration qualification — fail closed (docs/15 §1).

Every graph, policy file, schema, prompt reference, executor binding, edge
condition, ContextContract and EvidenceRole reference is checked BEFORE a run
trusts it. The failure mode this prevents is not a crash — it is a beautiful
architecture producing subtly wrong research because a reference silently
pointed nowhere.

  doctor.py            lint everything, exit 1 on any error
  controller.py doctor same, through the runner
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import yaml

import graph as graphmod

ROOT = graphmod.ROOT
NODE_TYPES = {"reason", "retrieve", "agent", "transform", "gate", "terminal"}
CONTRACT_KEYS = {"require", "prefer", "exclude", "evidence_roles", "branch_scope", "budget"}
GRAPHS = ["control_graph.yaml", "loadout_graph.yaml", "market_discovery_graph.yaml",
          "product_anchored_graph.yaml", "maintenance_graph.yaml"]
# every graph is bound: the maintenance executor layer landed 2026-09-03 (docs/23)
DEFERRED_GRAPHS: set = set()


def _known_data_keys() -> set:
    import controller
    import memory
    import models
    keys = set(controller.SCHEMA_BY_KEY) | set(controller.SINGULAR_KEYS)
    keys |= set(memory._NODE_TYPES)
    keys |= set(models.new_state("probe")["data"])
    keys |= {"handoff_packet", "satisfaction", "run_identity", "registry_snapshot",
             "evidence_authority_rules", "frontier_rankings", "research_plan",
             "loadout", "loadout_receipt", "signal_divergences", "promoted_scopes",
             "product_seed", "market_seed"}
    return keys


def lint_yaml(path: str) -> list[str]:
    try:
        graphmod.load_yaml_file(path)
        return []
    except yaml.YAMLError as e:
        return [f"{os.path.basename(path)}: {e}"]
    except OSError as e:
        return [f"{os.path.basename(path)}: unreadable ({e})"]


def check_graph_file(name: str) -> list[str]:
    errors = []
    path = os.path.join(ROOT, "graph", name)
    errors += lint_yaml(path)
    if errors:
        return errors
    g = graphmod.load_graph(name)
    errors += [f"{name}: {e}" for e in graphmod.validate_graph(g)]
    import executors
    import transitions
    known_keys = _known_data_keys()
    valid_roles = set((graphmod.load_policies().get("evidence_roles") or {}).get("valid") or [])
    for n, spec in (g.get("nodes") or {}).items():
        spec = spec or {}
        ntype = spec.get("type")
        if ntype not in NODE_TYPES:
            errors.append(f"{name}:{n}: unknown node type {ntype!r}")
        ex = spec.get("executor") or ""
        _oe = spec.get("on_enter")
        if _oe and _oe not in executors.EXECUTORS:
            errors.append(f"{name}: on_enter executor {_oe!r} not registered")
        if ntype in ("transform", "gate"):
            if not ex:
                errors.append(f"{name}:{n}: {ntype} node without executor")
            elif ex.startswith("python.") and ex not in executors.EXECUTORS \
                    and name not in DEFERRED_GRAPHS:
                errors.append(f"{name}:{n}: executor {ex!r} not registered")
        if spec.get("prompt") and name not in DEFERRED_GRAPHS:
            pf = os.path.join(ROOT, "prompts", f"{spec['prompt']}.md")
            if not os.path.isfile(pf):
                errors.append(f"{name}:{n}: prompt file prompts/{spec['prompt']}.md missing")
        for k in (spec.get("outputs") or []) + (spec.get("optional_outputs") or []):
            if k not in known_keys:
                errors.append(f"{name}:{n}: output key {k!r} unknown to the data model")
        ctx = spec.get("context") or {}
        for k in ctx:
            if k not in CONTRACT_KEYS:
                errors.append(f"{name}:{n}: unknown ContextContract key {k!r}")
        for r in ctx.get("evidence_roles") or []:
            if r not in valid_roles:
                errors.append(f"{name}:{n}: contract references unknown EvidenceRole {r!r}")
        for k in (ctx.get("require") or []) + (ctx.get("prefer") or []) + (ctx.get("exclude") or []):
            if k not in known_keys:
                errors.append(f"{name}:{n}: contract key {k!r} unknown to the data model")
    for i, e in enumerate(g.get("edges") or []):
        cond = e.get("when")
        if cond and cond not in transitions.CONDITIONS and name not in DEFERRED_GRAPHS:
            errors.append(f"{name}:edge[{i}]: unknown condition {cond!r}")
    return errors


def check_policies() -> list[str]:
    errors = []
    pol = graphmod.load_policies()
    valid = set((pol.get("evidence_roles") or {}).get("valid") or [])
    classes = set(pol.get("freshness_classes") or [])
    if not valid:
        return ["policies: evidence_roles.valid missing"]
    for fam, spec in (pol.get("source_suitability") or {}).items():
        for r in (spec or {}).get("may_support") or []:
            if r not in valid:
                errors.append(f"policies: source_suitability.{fam} references unknown role {r!r}")
    for role, allowed in (pol.get("freshness_requirements") or {}).items():
        if role not in valid:
            errors.append(f"policies: freshness_requirements references unknown role {role!r}")
        for c in allowed or []:
            if c not in classes:
                errors.append(f"policies: freshness_requirements.{role} unknown class {c!r}")
    for req, spec in (pol.get("physical_product_requirements") or {}).items():
        for r in (spec or {}).get("roles") or []:
            if r not in valid:
                errors.append(f"policies: physical_product_requirements.{req} unknown role {r!r}")
    # compiled gap-role lists must stay inside the constitution
    import executors
    import market_discovery
    import product_anchored
    for src, roles in (("executors._GAP_DEFAULT_ROLES", executors._GAP_DEFAULT_ROLES),
                       ("market_discovery gap roles", market_discovery._WHITESPACE_GAP_ROLES),
                       ("product_anchored gap roles", product_anchored._BRIDGE_GAP_ROLES)):
        for r in roles:
            if r not in valid:
                errors.append(f"policies: {src} uses unknown role {r!r}")
    return errors


def check_schemas() -> list[str]:
    errors = []
    sdir = os.path.join(ROOT, "schemas")
    for fn in sorted(os.listdir(sdir)):
        if not fn.endswith(".json"):
            continue
        try:
            with open(os.path.join(sdir, fn), encoding="utf-8") as f:
                s = json.load(f)
            if fn != "work_state.json" and not s.get("required"):
                errors.append(f"schemas/{fn}: no required[] — schema-lite validation would be vacuous")
        except (json.JSONDecodeError, OSError) as e:
            errors.append(f"schemas/{fn}: {e}")
    return errors


def check_settings_schema() -> list[str]:
    import settings
    return settings.validate_schema()


def check_misc_yaml() -> list[str]:
    errors = []
    for rel in ("loop.yaml", os.path.join("registry", "niche_scopes.yaml"),
                os.path.join("graph", "loadout_policies.yaml"),
                os.path.join("graph", "settings_schema.yaml")):
        p = os.path.join(ROOT, rel)
        if os.path.isfile(p):
            errors += lint_yaml(p)
    return errors


def run() -> dict:
    errors = []
    errors += check_misc_yaml()
    errors += check_policies()
    errors += check_schemas()
    try:
        errors += check_settings_schema()
    except Exception as e:
        errors.append(f"settings schema: {e}")
    for gname in GRAPHS:
        errors += check_graph_file(gname)
    try:
        import registry
        snap = registry.load_snapshot()
        if not (snap and snap.get("build_id")):
            errors.append("registry: snapshot unavailable — CSV compile failed (run registry.py build for errors)")
    except Exception as e:
        errors.append(f"registry: {e}")
    return {"ok": not errors, "errors": errors,
            "checked": {"graphs": GRAPHS, "policies": True, "schemas": True,
                        "settings_schema": True, "registry_snapshot": True}}


if __name__ == "__main__":
    result = run()
    print(json.dumps(result, indent=1, ensure_ascii=False))
    raise SystemExit(0 if result["ok"] else 1)
