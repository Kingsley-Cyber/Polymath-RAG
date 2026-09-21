#!/usr/bin/env python3
"""Hermes Preference Control Plane (docs/16).

The skill declares its safe degrees of freedom in graph/settings_schema.yaml;
this module is the sole gate between "what the user asked for" and "what the
run does". Hermes discovers controls with `describe`, explains them with
`explain`, compiles plain English into a patch (prompts/preference_compiler.md)
and submits it here — it NEVER edits graph/policy/code files.

Laws:
- users control desired stopping conditions and emphasis; φ retains absolute
  safety ceilings, stagnation detection, and every evidence/authority rule;
- SYSTEM_LOCKED settings are visible and explainable, never settable;
- settings resolve ONCE at init (preset + overrides) into a hashed snapshot;
- mid-run changes are versioned SettingsRevisions with an effective-from
  boundary — never retroactive, never silent.

  settings.py describe --mode niche_loadout
  settings.py explain  --id community_strength
  settings.py presets
  settings.py resolve  --file prefs.json [--preset DEEP_INSIDER]
  settings.py apply    --state run.json --file patch.json [--requested-by USER]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import graph as graphmod

SCHEMA_PATH = os.path.join(graphmod.ROOT, "graph", "settings_schema.yaml")
_AUTHORITIES = {"USER_SAFE", "ADVANCED_SAFE", "SYSTEM_LOCKED"}
_MUTABILITIES = {"INIT_ONLY", "DURING_RUN", "BEFORE_PORTFOLIO"}
# loadout nodes at/after which BEFORE_PORTFOLIO settings are frozen
_PORTFOLIO_LOCKED_NODES = {"portfolio", "community_skeptic", "apply_skeptic",
                           "loadout_gate", "stop"}


def _doc() -> dict:
    return graphmod.load_yaml_file(SCHEMA_PATH)


def load_schema() -> dict:
    return _doc().get("settings_schema") or {}


def load_presets() -> dict:
    return _doc().get("presets") or {}


# ---------------------------------------------------------------- validate --
def _check_value(key: str, spec: dict, val) -> str | None:
    t = spec.get("type")
    if t == "enum":
        if val not in (spec.get("allowed") or []):
            return f"{key}: {val!r} not in allowed {spec.get('allowed')}"
    elif t == "integer":
        if not isinstance(val, int) or isinstance(val, bool):
            return f"{key}: integer required"
        lo, hi = spec.get("min"), spec.get("max")
        if (lo is not None and val < lo) or (hi is not None and val > hi):
            return f"{key}: {val} outside [{lo}..{hi}] — the schema range is the ceiling"
    return None


def validate_schema() -> list[str]:
    """Doctor hook: the declared surface itself must be well-formed."""
    errors = []
    schema = load_schema()
    for key, spec in schema.items():
        spec = spec or {}
        auth = spec.get("authority") or spec.get("level")
        if auth not in _AUTHORITIES:
            errors.append(f"settings_schema.{key}: level {auth!r} invalid")
        if "default" not in spec:
            errors.append(f"settings_schema.{key}: no default")
        if auth == "SYSTEM_LOCKED":
            if not spec.get("reason"):
                errors.append(f"settings_schema.{key}: SYSTEM_LOCKED without reason")
            continue
        if not spec.get("label") or not spec.get("description"):
            errors.append(f"settings_schema.{key}: label+description required (Hermes explains from here)")
        t = spec.get("type")
        if t == "enum":
            if not spec.get("allowed"):
                errors.append(f"settings_schema.{key}: enum without allowed[]")
        elif t == "integer":
            if spec.get("min") is None or spec.get("max") is None:
                errors.append(f"settings_schema.{key}: integer without min/max")
        else:
            errors.append(f"settings_schema.{key}: type {t!r} invalid")
        if spec.get("mutability") not in _MUTABILITIES:
            errors.append(f"settings_schema.{key}: mutability undeclared/invalid")
        bad = _check_value(key, spec, spec.get("default"))
        if bad:
            errors.append(f"settings_schema.{key}: default invalid ({bad})")
        if "cannot_affect" not in spec:
            errors.append(f"settings_schema.{key}: cannot_affect undeclared")
    for pname, patch in load_presets().items():
        for key, val in (patch or {}).items():
            spec = schema.get(key)
            if spec is None:
                errors.append(f"presets.{pname}: unknown setting {key!r}")
            elif (spec.get("level") or spec.get("authority")) == "SYSTEM_LOCKED":
                errors.append(f"presets.{pname}: {key} is SYSTEM_LOCKED")
            else:
                bad = _check_value(key, spec, val)
                if bad:
                    errors.append(f"presets.{pname}: {bad}")
    return errors


# ------------------------------------------------------------- introspect --
def _applies(spec: dict, mode: str | None) -> bool:
    modes = spec.get("modes")
    return mode is None or not modes or mode in modes


def describe(mode: str | None = None) -> dict:
    """What can the user adjust for this mode? Read from the implementation,
    never from prompt memory."""
    out = {"adjustable": [], "locked": []}
    for key, spec in load_schema().items():
        spec = spec or {}
        if not _applies(spec, mode):
            continue
        level = spec.get("level") or spec.get("authority")
        row = {"id": key, "label": spec.get("label"), "level": level,
               "default": spec.get("default")}
        if level == "SYSTEM_LOCKED":
            row["reason"] = spec.get("reason")
            out["locked"].append(row)
        else:
            row.update({"type": spec.get("type"),
                        "allowed": spec.get("allowed"),
                        "range": ([spec.get("min"), spec.get("max")]
                                  if spec.get("type") == "integer" else None),
                        "mutability": spec.get("mutability"),
                        "cost_effect": spec.get("cost_effect"),
                        "description": spec.get("description")})
            out["adjustable"].append(row)
    out["presets"] = sorted(load_presets())
    return out


def explain(setting_id: str) -> dict:
    spec = load_schema().get(setting_id)
    if spec is None:
        return {"ok": False, "error": f"unknown setting {setting_id!r}"}
    return {"ok": True, "id": setting_id, **spec}


# ---------------------------------------------------------------- resolve ---
def resolve(overrides: dict | None = None, preset: str | None = None) -> dict:
    """preset + overrides -> {resolved, hash, preset}. Raises ValueError with
    every violation listed. SYSTEM_LOCKED refuses; ranges are ceilings."""
    schema = load_schema()
    patch: dict = {}
    if preset:
        presets = load_presets()
        if preset not in presets:
            raise ValueError(f"unknown preset {preset!r} (known: {sorted(presets)})")
        patch.update(presets[preset] or {})
    patch.update(overrides or {})
    errors = []
    for key, val in patch.items():
        spec = schema.get(key)
        if spec is None:
            errors.append(f"{key}: unknown setting — nothing outside the schema is settable")
            continue
        if (spec.get("level") or spec.get("authority")) == "SYSTEM_LOCKED":
            errors.append(f"{key}: SYSTEM_LOCKED ({spec.get('reason', 'constitutional')}) — "
                          "override refused; evidence laws cannot be weakened per run")
            continue
        bad = _check_value(key, spec, val)
        if bad:
            errors.append(bad)
    if errors:
        raise ValueError("; ".join(errors))
    resolved = {k: s.get("default") for k, s in schema.items()
                if (s.get("level") or s.get("authority")) != "SYSTEM_LOCKED"}
    resolved.update(patch)
    return {"resolved": resolved, "hash": _hash(resolved),
            "preset": preset or None, "revisions": []}


def _hash(resolved: dict) -> str:
    return hashlib.sha256(json.dumps(resolved, sort_keys=True, default=str)
                          .encode()).hexdigest()[:16]


# -------------------------------------------------- mid-run revisions -------
def apply_revision(state: dict, patch: dict, requested_by: str = "USER") -> dict:
    """Versioned, non-retroactive SettingsRevision. Only settings declared
    mutable at the run's current position may change; the revision records
    who, what, and from-when — earlier steps keep their meaning."""
    schema = load_schema()
    settings = state.get("settings") or resolve()
    current = settings.get("resolved") or {}
    errors = []
    for key, val in (patch or {}).items():
        spec = schema.get(key)
        if spec is None or (spec.get("level") or spec.get("authority")) == "SYSTEM_LOCKED":
            errors.append(f"{key}: not settable")
            continue
        mut = spec.get("mutability")
        if mut == "INIT_ONLY":
            errors.append(f"{key}: immutable mid-run — resolved at init, pinned by hash")
        elif mut == "BEFORE_PORTFOLIO" and state.get("node") in _PORTFOLIO_LOCKED_NODES:
            errors.append(f"{key}: frozen — the run already reached {state['node']!r}; "
                          "this setting is only mutable before portfolio selection")
        else:
            bad = _check_value(key, spec, val)
            if bad:
                errors.append(bad)
    if errors:
        raise ValueError("; ".join(errors))
    merged = dict(current)
    changes = {k: {"from": current.get(k), "to": v} for k, v in patch.items()
               if current.get(k) != v}
    merged.update(patch)
    import models
    revision = {"revision": len(settings.get("revisions") or []) + 1,
                "previous_hash": settings.get("hash"),
                "patch": changes, "requested_by": requested_by,
                "effective_from_node": state.get("node"),
                "retroactive": False, "at": models.now()}
    settings = dict(settings)
    settings["resolved"] = merged
    settings["hash"] = _hash(merged)
    settings.setdefault("revisions", []).append(revision)
    state["settings"] = settings
    return revision


# legacy alias kept for callers/tests predating docs/16
def apply_overrides_mid_run(state: dict, overrides: dict) -> dict:
    apply_revision(state, overrides)
    return state["settings"]


def effective(state: dict, key: str, fallback):
    """Runtime lookup: resolved setting if the run pinned one, else fallback
    (the policy default). SYSTEM_LOCKED values never come from here."""
    return ((state.get("settings") or {}).get("resolved") or {}).get(key, fallback)


def for_mode(state: dict, mode: str | None) -> dict:
    """The preference slice a worker should see: shared + this mode's keys."""
    resolved = (state.get("settings") or {}).get("resolved") or {}
    schema = load_schema()
    return {k: v for k, v in resolved.items()
            if _applies(schema.get(k) or {}, mode)}


# -------------------------------------------------------------------- cli ---
def main():
    p = argparse.ArgumentParser(prog="settings")
    sub = p.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("describe"); d.add_argument("--mode", default=None)
    e = sub.add_parser("explain"); e.add_argument("--id", required=True)
    sub.add_parser("presets")
    r = sub.add_parser("resolve")
    r.add_argument("--file", default=None); r.add_argument("--preset", default=None)
    a = sub.add_parser("apply")
    a.add_argument("--state", required=True); a.add_argument("--file", required=True)
    a.add_argument("--requested-by", default="USER", dest="requested_by")
    args = p.parse_args()
    if args.cmd == "describe":
        print(json.dumps(describe(args.mode), indent=1, ensure_ascii=False)); return 0
    if args.cmd == "explain":
        print(json.dumps(explain(args.id), indent=1, ensure_ascii=False)); return 0
    if args.cmd == "presets":
        print(json.dumps(load_presets(), indent=1, ensure_ascii=False)); return 0
    if args.cmd == "resolve":
        overrides = {}
        if args.file:
            with open(args.file, encoding="utf-8") as f:
                overrides = json.load(f)
        try:
            print(json.dumps(resolve(overrides, args.preset), indent=1)); return 0
        except ValueError as err:
            print(json.dumps({"ok": False, "error": "SETTINGS_REJECTED", "detail": str(err)}))
            return 1
    if args.cmd == "apply":
        import memory
        import models
        state = models.load_state(args.state)
        if state.get("status") == "stopped":
            print(json.dumps({"ok": False, "error": "terminal run — settings frozen forever"}))
            return 1
        with open(args.file, encoding="utf-8") as f:
            patch = json.load(f)
        try:
            revision = apply_revision(state, patch, args.requested_by)
        except ValueError as err:
            print(json.dumps({"ok": False, "error": "SETTINGS_REJECTED", "detail": str(err)}))
            return 1
        models.save_state(state, args.state)
        memory.record_event(state["run_id"], "SETTINGS_REVISED", revision)
        print(json.dumps({"ok": True, "revision": revision,
                          "hash": state["settings"]["hash"],
                          "law": "non-retroactive — effective from the next action"},
                         indent=1, ensure_ascii=False))
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
