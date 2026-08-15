#!/usr/bin/env python3
"""compile_predicate_rules.py — rules YAML × compiled lexical tables →
compiled_lexical.json (the compiler's runtime lookup artifact).

Compile gates (build FAILS on any violation):

  1. a rule cites a VN class / PB roleset / FN frame that does not exist
     in the FLATTENED REAL-RESOURCE index (no handwritten index);
  2. a SemLink mapping references a missing source or destination;
  3. a lexical member expands to two canonical predicates for the same
     (evidence_class, roleset, oriented_signature);
  4. an inverse has inconsistent orientation;
  5. a predicate references an undeclared core type.

Plus the gate-5 behavior: verbs that belong to a cited VerbNet class
but are absent from the manual trigger YAML are expanded INTO the
compiled trigger set (class membership generalizes the hand lists).

Usage:
    python3 scripts/compile_predicate_rules.py
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
RULES_YAML = ROOT / "shared" / "polymath_shared" / "rulepack" / "core-predicates.yaml"

sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "shared"))


def _find_compiled_dir() -> Path:
    compiled_root = ROOT / "resources" / "compiled"
    dirs = [d for d in compiled_root.iterdir() if d.is_dir()]
    if not dirs:
        raise RuntimeError("no compiled resource tables; run flatten_resources.py first")
    if len(dirs) > 1:
        raise RuntimeError(
            f"multiple compiled contracts present: {[d.name for d in dirs]} — "
            "a new contract must supersede the old one in one change"
        )
    return dirs[0]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pack", default=None,
                        help="rules YAML path (default: frozen core-predicates.yaml -> compiled_lexical.json)")
    parser.add_argument("--out-name", default="compiled_lexical.json",
                        help="output filename inside the compiled contract dir")
    args = parser.parse_args()

    compiled_dir = _find_compiled_dir()
    manifest = json.loads((compiled_dir / "manifest.json").read_text())
    tables = {
        name: json.loads((compiled_dir / name).read_text())
        for name in manifest["tables"]
    }
    rules_yaml = Path(args.pack) if args.pack else RULES_YAML
    rules = yaml.safe_load(rules_yaml.read_text())

    failures, out = validate_and_compile(rules, tables, manifest)
    if failures:
        print("COMPILE FAILED:")
        for failure in failures:
            print(f"  {failure}")
        return 1

    (compiled_dir / args.out_name).write_text(
        json.dumps(out, sort_keys=True, separators=(",", ":"), indent=None)
    )
    print(f"{args.out_name} written to {compiled_dir.name}")
    print(f"  predicates: {len(out['predicates'])}")
    print(f"  resource_contract_id: {manifest['resource_contract_id'][:24]}...")
    print(f"  compiled_lexical_sha256: {out['compiled_lexical_sha256'][:24]}...")
    return 0


def validate_and_compile(
    rules: dict,
    tables: dict,
    manifest: dict,
) -> tuple[list[str], dict]:
    """The build gate. Returns (failures, compiled_artifact). Tests call
    this directly with mutated rule dicts (GATE 3)."""
    resource_index = tables["resource_index.json"]
    core_types = set(rules["core_types"])
    failures: list[str] = []

    def fail(msg: str) -> None:
        failures.append(msg)

    # -- gate 5: core types --------------------------------------------------
    for rule in rules["predicates"]:
        for sig in rule.get("signatures", []):
            for side in ("subject_core", "object_core"):
                unknown = set(sig.get(side, [])) - core_types
                if unknown:
                    fail(f"{rule['id']}: undeclared core types {sorted(unknown)}")

    # -- gate 1: citations exist in the REAL resource index -----------------
    vn_classes = set(resource_index["verbnet_classes"])
    pb_rolesets = set(resource_index["propbank_rolesets"])
    fn_frames = set(resource_index["framenet_frames"])
    fn_lus = set(resource_index["framenet_lus"])

    for rule in rules["predicates"]:
        ev = rule.get("evidence", {})
        for cls in ev.get("verbnet_classes", []):
            if cls not in vn_classes:
                fail(f"{rule['id']}: VerbNet class not in real index: {cls}")
        for rs in ev.get("propbank_rolesets", []):
            if rs not in pb_rolesets:
                fail(f"{rule['id']}: PropBank roleset not in real index: {rs}")
        for frame in ev.get("framenet_frames", []):
            if frame not in fn_frames:
                fail(f"{rule['id']}: FrameNet frame not in real index: {frame}")

    # -- gate 2: SemLink mapping endpoints exist -----------------------------
    pb_to_vn = tables["pb_to_vn.json"]
    pb_to_fn = tables["pb_to_fn.json"]
    vn_to_fn = tables["vn_to_fn.json"]
    for roleset, classes in pb_to_vn.items():
        if roleset not in pb_rolesets:
            fail(f"semlink pb-vn: roleset not in PropBank index: {roleset}")
        for vn_class in classes:
            if vn_class not in vn_classes:
                fail(f"semlink pb-vn: class not in VerbNet index: {vn_class}")
    for vn_class, frames in vn_to_fn.items():
        if vn_class not in vn_classes:
            fail(f"semlink vn-fn: class not in VerbNet index: {vn_class}")
        for frame in frames:
            if frame not in fn_frames:
                fail(f"semlink vn-fn: frame not in FrameNet index: {frame}")
    for roleset in pb_to_fn:
        if roleset not in pb_rolesets:
            fail(f"semlink pb-fn: roleset not in PropBank index: {roleset}")

    # -- gate 4: inverse consistency -----------------------------------------
    by_id = {rule["id"]: rule for rule in rules["predicates"]}
    for rule in rules["predicates"]:
        inverse = rule.get("direction", {}).get("inverse")
        if not inverse or inverse not in by_id:
            continue
        back = by_id[inverse].get("direction", {}).get("inverse")
        if back != rule["id"]:
            fail(f"inverse mismatch: {rule['id']} -> {inverse} -> {back}")

    # -- gate 5: class-membership expansion ----------------------------------
    vn_class_index = tables["vn_class_index.json"]
    compiled_rules: dict[str, dict] = {}
    for rule in rules["predicates"]:
        ev = rule["evidence"]
        verbs = set(ev.get("verbs", []))
        class_members: dict[str, list[str]] = {}
        for cls in ev.get("verbnet_classes", []):
            members = sorted(
                m for m in vn_class_index.get(cls, [])
                if m not in verbs
            )
            class_members[cls] = members
            verbs.update(members)
        compiled_rules[rule["id"]] = {
            "evidence_classes": ev.get("classes", []),
            "verbs": sorted(verbs),
            "nouns": sorted(ev.get("nouns", [])),
            "multiword": sorted(ev.get("multiword", [])),
            "negative_triggers": sorted(ev.get("negative_triggers", [])),
            "ambiguous_triggers": sorted(ev.get("ambiguous_triggers", [])),
            "verbnet_classes": sorted(ev.get("verbnet_classes", [])),
            "propbank_rolesets": sorted(ev.get("propbank_rolesets", [])),
            "framenet_frames": sorted(ev.get("framenet_frames", [])),
            "class_members": class_members,
            "signatures": rule.get("signatures", []),
        }

    # -- gate 3: determinism — no two rules may map the same
    # (evidence_class, roleset, signature) to different predicates --------
    for i, rule_a in enumerate(rules["predicates"]):
        for rule_b in rules["predicates"][i + 1:]:
            ev_a, ev_b = rule_a["evidence"], rule_b["evidence"]
            classes = set(ev_a.get("classes", [])) & set(ev_b.get("classes", []))
            if not classes:
                continue
            rolesets = set(ev_a.get("propbank_rolesets", [])) & set(ev_b.get("propbank_rolesets", []))
            vn = set(ev_a.get("verbnet_classes", [])) & set(ev_b.get("verbnet_classes", []))
            if not rolesets and not vn:
                continue
            if not _signatures_overlap(rule_a["signatures"], rule_b["signatures"]):
                continue
            if rolesets or (not ev_a.get("propbank_rolesets") and not ev_b.get("propbank_rolesets")):
                fail(
                    f"determinism violation: {rule_a['id']} / {rule_b['id']} overlap on "
                    f"classes={sorted(classes)} rolesets={sorted(rolesets)}"
                )

    if failures:
        return failures, {}

    out = {
        "resource_contract_id": manifest["resource_contract_id"],
        "flattener_version": manifest["flattener_version"],
        "rule_pack_id": rules["rule_pack"]["id"],
        "rule_pack_version": rules["rule_pack"]["version"],
        "predicates": compiled_rules,
        "core_types": sorted(core_types),
        "evidence_classes": rules.get("evidence_classes", {}),
        "resource_versions": rules["rule_pack"].get("resource_versions", {}),
        "rule_coverage": _rule_coverage(rules, tables),
    }
    out["compiled_lexical_sha256"] = hashlib.sha256(
        json.dumps(out, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return [], out


def _rule_coverage(rules: dict, tables: dict) -> dict[str, dict]:
    """Per-rule coverage report (spec §25): where the hand-curated rule
    pack is confirmed / expanded / unsupported / conflicting with the
    real resources. Manual rules are NEVER auto-deleted on missing
    coverage — external resources are incomplete by design."""
    vn_index = tables["vn_class_index.json"]
    frame_index = tables["frame_index.json"]
    pb_to_vn = tables["pb_to_vn.json"]
    pb_to_fn = tables["pb_to_fn.json"]
    flattened_rolesets = set(tables["resource_index.json"]["propbank_rolesets"])

    report: dict[str, dict] = {}
    for rule in rules["predicates"]:
        ev = rule["evidence"]
        entry = {
            "manual_verbs": sorted(ev.get("verbs", [])),
            "manual_nouns": sorted(ev.get("nouns", [])),
            "manual_multiword": sorted(ev.get("multiword", [])),
            "cited_vn_classes": sorted(ev.get("verbnet_classes", [])),
            "cited_pb_rolesets": sorted(ev.get("propbank_rolesets", [])),
            "cited_fn_frames": sorted(ev.get("framenet_frames", [])),
        }
        cited_vn = set(ev.get("verbnet_classes", []))
        cited_pb = set(ev.get("propbank_rolesets", []))
        cited_fn = set(ev.get("framenet_frames", []))

        vn_ok = all(c in vn_index for c in cited_vn)
        pb_ok = all(rs in flattened_rolesets for rs in cited_pb)
        fn_ok = all(f in frame_index for f in cited_fn)

        # SemLink: does any cited roleset resolve (attested or composed)?
        semlink_rolesets = {
            rs for rs in cited_pb
            if rs in pb_to_vn or rs in pb_to_fn
        }

        has_manual = bool(entry["manual_verbs"] or entry["manual_nouns"] or entry["manual_multiword"])
        has_resources = bool(cited_vn or cited_pb or cited_fn)

        if has_resources and (not vn_ok or not pb_ok or not fn_ok):
            status = "CONFLICT"
        elif has_manual and semlink_rolesets:
            status = "COMPLETE"
        elif has_manual and has_resources:
            status = "PARTIAL"
        elif has_resources:
            status = "PARTIAL"
        else:
            status = "MANUAL_ONLY"

        entry.update({
            "resource_confirmed": sorted((cited_vn if vn_ok else set()) | (cited_pb if pb_ok else set()) | (cited_fn if fn_ok else set())),
            "semlink_resolved_rolesets": sorted(semlink_rolesets),
            "status": status,
        })
        report[rule["id"]] = entry
    return report


def _signatures_overlap(sigs_a: list[dict], sigs_b: list[dict]) -> bool:
    for sa in sigs_a:
        for sb in sigs_b:
            if set(sa.get("subject_core", [])) & set(sb.get("subject_core", [])) and (
                set(sa.get("object_core", [])) & set(sb.get("object_core", []))
            ):
                return True
    return False


if __name__ == "__main__":
    sys.exit(main())
