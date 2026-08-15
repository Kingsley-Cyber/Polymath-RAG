"""Q1-R v1.1.0 revision locks (no stores).

Freeze the deterministic pieces of the realistic-prose revision:
- passive/purpose-passive syntactic fallback (semantic-role direction);
- rule-pack version selection (1.0.1 frozen / 1.1.0 candidate);
- v1.1.0 pack content (leads tightened: "run" removed);
- scope lexicon: "can" is a hedge; "could" is not hypothetical.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "shared"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "workers"))

from polymath_shared.rulepack.compiler import load_rule_pack  # noqa: E402
from polymath_shared.rulepack.negation import analyze_scope  # noqa: E402
from workers.syntax import parse_sentence  # noqa: E402


def test_passive_purpose_parse_orients_semantic_roles() -> None:
    p = parse_sentence("Qdrant is used for vector retrieval.")
    assert p is not None and p["voice"] == "passive"
    assert p["subject"]["token_text"] == "Qdrant"
    assert p["agent"]["token_text"] == "vector retrieval"


def test_passive_by_parse() -> None:
    p = parse_sentence("The vaccine was developed by the institute.")
    assert p is not None and p["voice"] == "passive"
    assert p["agent"]["token_text"] == "the institute"


def test_passive_with_adverb_and_compound_clause() -> None:
    p = parse_sentence(
        "Qdrant is still used for vector retrieval and Neo4j is still used for graph traversal."
    )
    assert p is not None and p["voice"] == "passive"
    assert p["agent"]["token_text"] == "vector retrieval"


def test_active_sentence_gets_no_deterministic_parse() -> None:
    assert parse_sentence("The system processes events quickly.") is None


def test_rule_pack_versions_select_different_artifacts() -> None:
    old = load_rule_pack(use_resources=False, pack_version="1.0.1")
    new = load_rule_pack(use_resources=False, pack_version="1.1.0")
    assert old["pack"]["version"] == "1.0.1"
    assert new["pack"]["version"] == "1.1.0"
    leads_old = old["predicates"]["leads"]["evidence"]["verbs"]
    leads_new = new["predicates"]["leads"]["evidence"]["verbs"]
    assert "run" in leads_old
    assert "run" not in leads_new


def test_scope_can_is_hedge_and_could_is_not_hypothetical() -> None:
    flags = analyze_scope("The system can be rebuilt from receipts.", 0, 10)
    assert flags.speculative is True
    assert flags.hypothetical is False
    flags = analyze_scope("The model could influence the result.", 0, 10)
    assert flags.speculative is True
    assert flags.hypothetical is False
    flags = analyze_scope("The system would be rebuilt if it failed.")
    assert flags.hypothetical is True
    assert flags.conditional is True


def test_negated_scope_still_rejects() -> None:
    flags = analyze_scope("The company did not acquire the rival.", 0, 30)
    assert flags.negated is True
