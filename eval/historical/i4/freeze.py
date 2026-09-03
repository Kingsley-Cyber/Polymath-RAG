"""I4 Phase 8 — freeze everything before the first extraction invocation."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))

from polymath_shared.rulepack import load_rule_pack  # noqa: E402

FIXTURE = ROOT / "eval" / "i4"


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main() -> int:
    pack = load_rule_pack(pack_version="1.2.0")
    files = {
        "manifest.yaml": FIXTURE / "manifest.yaml",
        "capability_matrix.json": FIXTURE / "capability_matrix.json",
        "CAPABILITY_MATRIX.md": FIXTURE / "CAPABILITY_MATRIX.md",
        "corpus/01_northvale_health.md": FIXTURE / "corpus" / "01_northvale_health.md",
        "corpus/02_nimbus_cloud.md": FIXTURE / "corpus" / "02_nimbus_cloud.md",
        "corpus/03_crestline_automation.md": FIXTURE / "corpus" / "03_crestline_automation.md",
        "corpus/04_brightpath_learning.md": FIXTURE / "corpus" / "04_brightpath_learning.md",
        "corpus/05_corval_logistics.md": FIXTURE / "corpus" / "05_corval_logistics.md",
        "gold/entity_gold.json": FIXTURE / "gold" / "entity_gold.json",
        "gold/fact_gold.json": FIXTURE / "gold" / "fact_gold.json",
        "gold/text_concept_gold.json": FIXTURE / "gold" / "text_concept_gold.json",
    }
    state = {
        "head": "ce2545f",
        "frozen_at_gold_authoring_complete": True,
        "rule_pack_version": "1.2.0",
        "compiled_lexical_sha256": pack["compiled_lexical_sha256"],
        "resource_contract_id": pack["resource_contract_id"],
        "gliner": {"model": "urchade/gliner_medium-v2.1",
                   "revision": "40ec419335d09393f298636f471328b722c6da9e",
                   "entity_threshold": 0.5, "evidence_threshold": 0.4},
        "embedder": {"model": "Qwen/Qwen3-Embedding-0.6B",
                     "revision": "97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3"},
        "contracts": {
            "entity_admission": "entity-admission-v1.1",
            "identity": "entity-identity-v2",
            "binding_gates": "endpoint-binding-v1",
            "provenance": "exact-evidence-v1",
            "retrieval_summary": "retrieval-summary-v2",
        },
        "hashes": {name: sha(p) for name, p in files.items()},
    }
    out = FIXTURE / "FROZEN_STATE.json"
    out.write_text(json.dumps(state, indent=1, sort_keys=True))
    print(json.dumps({"frozen_files": len(files),
                      "frozen_state_sha": sha(out)}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
