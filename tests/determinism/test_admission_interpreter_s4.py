"""S4 — single live admission authority.

`interpret_admission(contract_version=...)` is the only live authority.
There is NO fallback: `if V2 fails: try v1.1` would make graph semantics
depend on which interpreter happened to succeed.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))

from polymath_shared.admission_interpreter import (
    AdmissionResult, UnknownAdmissionContract, interpret_admission,
)
from polymath_shared.execution import SEMANTIC_CONTRACT_V1_1, SEMANTIC_CONTRACT_V2
from polymath_shared.identity_evidence import RetryableDependencyUnavailable


def _syntax(pairs, text):
    toks, pos = [], 0
    for i, (t, p) in enumerate(pairs):
        cs = text.index(t, pos); pos = cs + len(t)
        toks.append({"i": i, "text": t, "pos": p, "lemma": t.lower(),
                     "char_start": cs, "char_end": cs + len(t)})
    return {"tokens": toks, "noun_chunks": []}


def test_unknown_contract_fails_rather_than_guessing():
    with pytest.raises(UnknownAdmissionContract):
        interpret_admission(contract_version="admission-v3-imaginary",
                            proposal_surface="x", core_type="Technology")


def test_unpinned_contract_fails():
    with pytest.raises(UnknownAdmissionContract):
        interpret_admission(contract_version="", proposal_surface="x",
                            core_type="Technology")


def test_v2_requires_syntax_and_never_falls_back():
    """The execution assertion fires inside the interpreter itself."""
    with pytest.raises(RetryableDependencyUnavailable):
        interpret_admission(contract_version=SEMANTIC_CONTRACT_V2,
                            proposal_surface="Researchers", core_type="Organization",
                            syntax=None)


def test_v2_identity_uses_pos_not_capitalization():
    text = "Postgres is the workflow authority."
    r = interpret_admission(
        contract_version=SEMANTIC_CONTRACT_V2, proposal_surface="Postgres",
        core_type="Technology", span=(0, 8), sentence_text=text,
        syntax=_syntax([("Postgres", "PROPN"), ("is", "AUX")], text),
        document_text=text)
    assert r.anchor_kind == "IDENTITY" and r.graph_eligible

    text2 = "Researchers generally distinguish the systems."
    r2 = interpret_admission(
        contract_version=SEMANTIC_CONTRACT_V2, proposal_surface="Researchers",
        core_type="Organization", span=(0, 11), sentence_text=text2,
        syntax=_syntax([("Researchers", "NOUN"), ("generally", "ADV")], text2),
        document_text=text2)
    assert r2.anchor_kind != "IDENTITY"
    assert not r2.graph_eligible


def test_historical_contract_is_reachable_only_when_explicitly_pinned():
    r = interpret_admission(contract_version=SEMANTIC_CONTRACT_V1_1,
                            proposal_surface="Researchers", core_type="Organization")
    assert r.semantic_contract == SEMANTIC_CONTRACT_V1_1
    assert r.anchor_kind == "UNSPECIFIED_V1_1"
    # v1.1 genuinely disagrees with V2 here — that is the migration, not a bug
    assert r.graph_eligible is True


def test_v1_1_and_v2_are_allowed_to_disagree():
    """Backward equivalence is an explicit NON-goal: V2 intentionally changes
    the semantics, so forcing `V2 == v1.1` would defeat the migration."""
    text = "Researchers generally distinguish the systems."
    v2 = interpret_admission(
        contract_version=SEMANTIC_CONTRACT_V2, proposal_surface="Researchers",
        core_type="Organization", span=(0, 11), sentence_text=text,
        syntax=_syntax([("Researchers", "NOUN"), ("generally", "ADV")], text),
        document_text=text)
    v1 = interpret_admission(contract_version=SEMANTIC_CONTRACT_V1_1,
                             proposal_surface="Researchers", core_type="Organization")
    assert v2.graph_eligible != v1.graph_eligible


def test_result_carries_full_auditable_provenance():
    text = "Postgres is the workflow authority."
    r = interpret_admission(
        contract_version=SEMANTIC_CONTRACT_V2, proposal_surface="Postgres",
        core_type="Technology", span=(0, 8), sentence_text=text,
        syntax=_syntax([("Postgres", "PROPN"), ("is", "AUX")], text),
        document_text=text)
    assert isinstance(r, AdmissionResult)
    assert r.proposal_surface == "Postgres"       # raw provider evidence
    assert r.referential_surface                   # envelope recorded
    assert r.admission_reason and r.semantic_contract == SEMANTIC_CONTRACT_V2


def test_the_cutover_is_performed_and_no_worker_calls_the_historical_authority():
    """S4c landed: this is the promised flip of the pre-cutover test.

    Before the cutover this asserted the exact REMAINING v1.1 surface, so the
    gate could never pass silently while sites were still outstanding. It now
    asserts the surface is empty. `GENERIC_HEAD` is a shared lexicon constant,
    not an admission authority, so importing it is not a call site.
    """
    import re

    AUTHORITIES = {"decide", "decide_v1_1_historical", "allocate_entity_id"}
    remaining = {}
    for mod in (ROOT / "workers/workers").glob("*.py"):
        for hit in re.findall(r"entity_admission import ([^\n]+)", mod.read_text()):
            names = {n.split(" as ")[0].strip() for n in hit.split(",")}
            if names & AUTHORITIES:
                remaining.setdefault(mod.name, set()).update(names & AUTHORITIES)
    assert remaining == {}, (
        f"production workers still call the historical v1.1 authority: "
        f"{ {k: sorted(v) for k, v in remaining.items()} }. The cutover is "
        "all-or-nothing; a partial one is the parallel truth path wiring "
        "invariant 1 forbids.")


def test_interpreter_never_reads_normalized_surface():
    src = (ROOT / "shared/polymath_shared/admission_interpreter.py").read_text()
    body = "\n".join(l for l in src.split("\n") if not l.strip().startswith("#"))
    assert "normalized_surface" not in body.split('"""')[-1]
