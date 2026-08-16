"""I4 Phase 0 — derive the executable compiler capability matrix.

Reads ONLY executable configuration/code: the active rule pack YAML
(core-predicates-v1.2.0), the argument-frame implementation in
workers/candidates.py, and the compiler's gate semantics in
rulepack/compiler.py. Emits capability_matrix.json + CAPABILITY_MATRIX.md.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))
sys.path.insert(0, str(ROOT / "workers"))

import yaml  # noqa: E402

from polymath_shared.rulepack import load_rule_pack  # noqa: E402
from workers.candidates import _REFERENTIAL_FRAMES, MAX_LIST_MEMBERS  # noqa: E402

PACK = load_rule_pack(pack_version="1.2.0")
YAML = ROOT / "shared" / "polymath_shared" / "rulepack" / "core-predicates-v1.2.0.yaml"
raw = yaml.safe_load(YAML.read_text())

FRAME_DEFAULT = "SUBJ_BEFORE_TRIGGER_OBJ_AFTER (nearest type-compatible entity per slot; predicate-region bounded)"
FRAME_ASSOCIATION = ("ARG1_AFTER_TRIGGER_ARG2_AFTER_PREP when a preposition follows the trigger "
                     "(referential-argument gate: MENTION_ONLY args abstain); otherwise the default frame")


def main() -> None:
    matrix: dict = {
        "derived_from": {
            "rule_pack_yaml": str(YAML.relative_to(ROOT)),
            "rule_pack_version": PACK["pack"]["version"],
            "compiled_lexical_sha256": PACK["compiled_lexical_sha256"],
            "resource_contract_id": PACK["resource_contract_id"],
        },
        "global_semantics": {
            "trigger_matching": (
                "typed trigger contract: the compiler tests ONLY the lexical arm "
                "(verbs/nouns/multiword) of the predicate that localized the trigger; "
                "verb surfaces match BOUNDED inflection forms (base/+s/+es/+d/+ed/+ing "
                "with e-drop, y->ies/ied, consonant doubling) — arbitrary prefix "
                "strings never match; noun surfaces match exact word boundaries; "
                "multiword triggers match by substring"),
            "argument_frames": FRAME_DEFAULT,
            "association_frame": FRAME_ASSOCIATION,
            "coordination": (
                "predicate-region boundaries: a coordinator (and/but/or/while, "
                "optionally comma-prefixed, or ';') opens a NEW region only when the "
                "word after it is a trigger surface; entity lists (max "
                f"{MAX_LIST_MEMBERS} members) expand only on ONE side; double lists "
                "fail closed"),
            "surface_weak": "YES — without a syntactic parse every pairing is a "
                            "surface frame; at most one unambiguous binding per "
                            "trigger, else no fact",
            "local_reference": (
                "bounded definite descriptions ('the X', 1-3 content words) resolve "
                "the SUBJECT slot only: head-match against one unique history entity, "
                "or closed-class org descriptions against the unique Organization "
                "entity; 0 or >1 candidates -> abstain; alias-only identity"),
            "passive": "UNSUPPORTED without a parse record — no syntactic parse "
                       "means surface order only; 'by'-passives typically fail "
                       "subject signatures and abstain",
            "negation_modality": "per-predicate constraints (reject/qualify); "
                                 "negated/conditional/question -> REJECT; "
                                 "speculative/hypothetical/attributed -> QUALIFY",
            "graph_eligibility": (
                "fact eligible iff BOTH endpoints have admission_class != "
                "MENTION_ONLY (shared neo4j_eligibility predicate used by "
                "projector, census, verifier)"),
            "referentiaL_gate_evidence_classes": sorted(_REFERENTIAL_FRAMES),
        },
        "predicates": {},
    }
    for pid in PACK["predicate_order"]:
        rule = PACK["predicates"][pid]
        ev = rule["evidence"]
        matrix["predicates"][pid] = {
            "rule_pack_version": PACK["pack"]["version"],
            "tier": rule.get("tier"),
            "definition": rule.get("definition", ""),
            "signatures": rule["signatures"],
            "subject_core": sorted({t for sig in rule["signatures"]
                                    for t in sig.get("subject_core", [])}),
            "object_core": sorted({t for sig in rule["signatures"]
                                   for t in sig.get("object_core", [])}),
            "verbs": sorted(ev.get("verbs", [])),
            "nouns": sorted(ev.get("nouns", [])),
            "multiword": sorted(ev.get("multiword", [])),
            "evidence_classes": ev.get("classes", []),
            "negative_triggers": ev.get("negative_triggers", []),
            "ambiguous_triggers": ev.get("ambiguous_triggers", []),
            "direction": rule["direction"]["canonical"],
            "inverse": rule["direction"].get("inverse"),
            "constraints": rule.get("constraints", {}),
            "supported_frames": [
                FRAME_ASSOCIATION if pid == "associated_with" else FRAME_DEFAULT,
            ],
            "graph_traversal_weight": rule.get("graph", {}).get("traversal_weight"),
        }
    out_json = ROOT / "eval" / "i4" / "capability_matrix.json"
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(matrix, indent=1, sort_keys=True))
    sha = hashlib.sha256(out_json.read_bytes()).hexdigest()

    md_lines = [
        "# I4 Compiler Capability Matrix (derived from executable config)",
        "",
        f"- rule pack: core-predicates-v1.2.0 (active default)",
        f"- compiled_lexical_sha256: `{PACK['compiled_lexical_sha256'][:24]}…`",
        f"- resource_contract_id: `{PACK['resource_contract_id'][:24]}…`",
        "",
        "## Global semantics",
        "",
    ]
    for k, v in matrix["global_semantics"].items():
        md_lines.append(f"- **{k}**: {v}")
    md_lines += ["", "## Predicates", ""]
    for pid, p in matrix["predicates"].items():
        md_lines.append(f"### {pid}")
        md_lines.append(f"- definition: {p['definition']}")
        md_lines.append(f"- subject core types: {p['subject_core']}")
        md_lines.append(f"- object core types: {p['object_core']}")
        md_lines.append(f"- verbs: {p['verbs'][:12]}{' …' if len(p['verbs']) > 12 else ''}")
        md_lines.append(f"- nouns: {p['nouns'][:8]}{' …' if len(p['nouns']) > 8 else ''}")
        md_lines.append(f"- multiword: {p['multiword']}")
        md_lines.append(f"- direction: {p['direction']} (inverse {p['inverse']})")
        md_lines.append(f"- constraints: {p['constraints']}")
        md_lines.append(f"- frames: {p['supported_frames']}")
        md_lines.append(f"- graph weight: {p['graph_traversal_weight']}")
        md_lines.append("")
    (ROOT / "eval" / "i4" / "CAPABILITY_MATRIX.md").write_text("\n".join(md_lines))
    print(f"predicates: {len(matrix['predicates'])}")
    print(f"capability_matrix.json sha256: {sha}")


if __name__ == "__main__":
    main()
