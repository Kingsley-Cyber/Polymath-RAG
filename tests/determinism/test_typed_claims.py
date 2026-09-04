"""TYPED-CLAIMS-V1: the claim kind travels contract -> prompt -> lean form -> evidence rows."""
import json
from pathlib import Path

import pytest

from polymath_shared.llm_extraction import client as llm_client
from polymath_shared.llm_extraction.contract import RelationProposal

ROOT = Path(__file__).resolve().parents[2]
KINDS = ("friction", "behavior", "workaround", "purchase_language")


def test_relation_proposal_accepts_the_four_kinds_and_defaults_to_none():
    for k in KINDS:
        assert RelationProposal(subject="s", predicate="USES", object="o", quote="q", claim_kind=k).claim_kind == k
    assert RelationProposal(subject="s", predicate="USES", object="o", quote="q").claim_kind is None
    with pytest.raises(Exception):
        RelationProposal(subject="s", predicate="USES", object="o", quote="q", claim_kind="vibe")


def test_json_schema_and_prompts_carry_claim_kind():
    from polymath_shared.llm_extraction import contract as c
    src = Path(c.__file__).read_text()
    assert '"claim_kind"' in src and "purchase_language" in src
    assert "claim_kind" in llm_client.SYSTEM_PROMPT and "9. claim_kind" in llm_client.SYSTEM_PROMPT
    assert "claim_kind" in llm_client.LEAN_SYSTEM_PROMPT


def test_lean_expand_maps_the_optional_fifth_element():
    obj = {"items": [{"id": "n1", "e": [["women", "Person"], ["car tweezers", "Product"]],
                      "r": [[0, "USES", 1, "I now have car tweezers.", "workaround"],
                            [0, "USES", 1, "I now have car tweezers.", "nonsense"],
                            [0, "USES", 1, "plain"]]}]}
    rels = llm_client._lean_expand(obj)["items"][0]["relations"]
    assert rels[0]["claim_kind"] == "workaround"
    assert "claim_kind" not in rels[1] and "claim_kind" not in rels[2]


def test_evidence_rows_read_claim_kind_from_qualifiers():
    from orchestrator.api.evidence_rows import _fact_claim_kinds

    class _Cur:
        def __init__(self, rows): self._rows = rows
        def fetchall(self): return self._rows

    class _Conn:
        def execute(self, sql, params):
            assert "qualifiers->>'claim_kind'" in sql
            return _Cur([("f1", "friction"), ("f2", None)])

    assert _fact_claim_kinds(_Conn(), ["f1", "f2"]) == {"f1": "friction"}
    assert _fact_claim_kinds(_Conn(), []) == {}
