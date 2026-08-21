"""S4c — the cutover is all-or-nothing, and these gates hold it that way.

Wiring invariant 1: no parallel old/new truth paths. The failure mode this
guards is not a crash — it is a SILENT one, where one call site still asks
v1.1 and quietly disagrees with the mention row for the same span. Static
gates catch that at edit time; the runtime tests catch it at execution time.
"""
import ast
from pathlib import Path

import pytest

PRODUCTION = [
    Path("workers/workers/extract_worker.py"),
    Path("workers/workers/candidates.py"),
    Path("workers/workers/kimi_candidates.py"),
    Path("workers/workers/canonicalize_worker.py"),
]

# The v1.1 authority and its id allocator. Both are HISTORICAL after S4c.
FORBIDDEN_NAMES = {"decide", "decide_v1_1_historical", "allocate_entity_id"}


def _imported_admission_names(path: Path) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.ImportFrom) and node.module == "polymath_shared.entity_admission":
            names |= {a.asname or a.name for a in node.names}
    return names


@pytest.mark.parametrize("path", PRODUCTION, ids=lambda p: p.name)
def test_no_production_module_imports_the_historical_authority(path):
    """After the cutover the live path calls interpret_admission ONLY."""
    leaked = _imported_admission_names(path) & FORBIDDEN_NAMES
    assert not leaked, (
        f"{path.name} imports the historical v1.1 authority {sorted(leaked)}; "
        "production must call interpret_admission(contract_version=...)")


def test_the_single_authority_is_called_exactly_once_in_the_worker():
    """One interpretation site. Two would be two truth paths."""
    src = Path("workers/workers/extract_worker.py").read_text()
    assert src.count("interpret_admission(") == 1, (
        "extract_worker must contain exactly one interpret_admission call site")


@pytest.mark.parametrize("path", PRODUCTION, ids=lambda p: p.name)
def test_no_runtime_flag_selects_semantics(path):
    """Rollback is a contract/deployment change, never a boolean flipped
    against existing records."""
    src = path.read_text()
    for banned in ("POLYMATH_USE_NEW_ADMISSION", "USE_V2_ADMISSION",
                   "ADMISSION_V2_ENABLED"):
        assert banned not in src, f"{path.name} selects semantics via {banned}"


def test_no_fallback_from_v2_to_v1_1():
    """`try v2; on failure use v1.1` is explicitly forbidden."""
    from polymath_shared import admission_interpreter as ai

    src = Path(ai.__file__).read_text()
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if not isinstance(node, ast.Try):
            continue
        for handler in node.handlers:
            calls = {getattr(n.func, "id", getattr(n.func, "attr", ""))
                     for n in ast.walk(handler) if isinstance(n, ast.Call)}
            assert "_interpret_v1_1_historical" not in calls, (
                "v1.1 is reachable as an exception fallback from V2")


def test_unpinned_contract_fails_rather_than_guessing():
    from polymath_shared.admission_interpreter import (
        UnknownAdmissionContract, interpret_admission,
    )

    with pytest.raises(UnknownAdmissionContract):
        interpret_admission(contract_version="admission-v9.9",
                            proposal_surface="Ada Lovelace", core_type="PERSON")


def test_persisted_class_is_exactly_the_projection_of_graph_eligible():
    """SQL cannot call graph_eligible(), so projection eligibility reads a
    column. That is safe ONLY while the column is written as this predicate's
    projection: ineligible decisions must store MENTION_ONLY whatever their
    scope, or the SQL consumers silently admit what Harbor refused."""
    from polymath_shared.admission_interpreter import AdmissionResult
    from polymath_shared.identity_allocation import allocate_identity
    from polymath_shared.neo4j_eligibility import fact_eligible_from_classes

    def _result(scope: str, eligible: bool) -> AdmissionResult:
        return AdmissionResult(
            proposal_surface="x", referential_surface="x", core_type="CONCEPT",
            anchor_kind="CONCEPT", decision_status="RESOLVED", scope=scope,
            reference_basis=None, graph_eligible=eligible,
            admission_reason="test", semantic_contract="admission-harbor-v2")

    # MENTION_ONLY + eligible is not a state graph_eligible() can produce
    # (it refuses that scope outright), so it is asserted unreachable rather
    # than enumerated as if it were a real combination.
    from polymath_shared.entity_harbor import (
        AnchorKind, HarborDecision, Referentiality, graph_eligible,
    )
    assert not graph_eligible(HarborDecision(
        "x", AnchorKind.IDENTITY, Referentiality.SPECIFIC, "MENTION_ONLY"))

    for scope in ("GLOBAL", "CORPUS_SCOPED", "DOCUMENT_SCOPED"):
        for eligible in (True, False):
            ident = allocate_identity(
                _result(scope, eligible), corpus_id="c", doc_id="d",
                chunk_id="ch", span_start=0, span_end=1)
            projected = ident.admission_class
            assert (projected != "MENTION_ONLY") == eligible, (
                f"scope={scope} graph_eligible={eligible} stored as "
                f"{projected!r}: the SQL predicate would disagree with Harbor")
            # and the SQL-side predicate must reach the same verdict
            assert fact_eligible_from_classes(projected, projected) == eligible


def test_ineligible_decisions_never_receive_a_durable_id():
    """Successful anaphora must not manufacture identity: only a decision
    graph_eligible() accepts may hold an ent_/entc_/entd_ id."""
    from polymath_shared.admission_interpreter import AdmissionResult
    from polymath_shared.identity_allocation import allocate_identity

    ineligible = AdmissionResult(
        proposal_surface="the second group", referential_surface="the second group",
        core_type="CONCEPT", anchor_kind="LOCAL_REFERENCE",
        decision_status="ABSTAINED", scope="DOCUMENT_SCOPED",
        reference_basis="AMBIGUOUS", graph_eligible=False,
        admission_reason="test", semantic_contract="admission-harbor-v2")
    ident = allocate_identity(ineligible, corpus_id="c", doc_id="d",
                              chunk_id="ch", span_start=0, span_end=16)
    assert ident.entity_id.startswith("mention_")
    assert ident.durable is False


def test_migration_adds_no_graph_eligible_column():
    import re

    sql = Path("stores/postgres/migrations/0015_semantic_contract_v2.sql").read_text()
    assert not re.search(r"ADD\s+COLUMN[^;]*graph_eligible", sql, re.I), (
        "a stored graph_eligible column would become a second authority")


def test_identity_does_not_fragment_on_a_determiner():
    """`the CareConnect portal` and `CareConnect portal` are ONE referent.

    Keying identity on the referential envelope split them into two entities,
    because the envelope deliberately keeps the determiner so the discourse
    consumer can see it. Identity keys on the proposal surface instead.
    """
    from polymath_shared.admission_interpreter import AdmissionResult
    from polymath_shared.identity_allocation import allocate_identity

    def _id(proposal, envelope):
        r = AdmissionResult(
            proposal_surface=proposal, referential_surface=envelope,
            core_type="TECHNOLOGY", anchor_kind="IDENTITY",
            decision_status="RESOLVED", scope="GLOBAL", reference_basis=None,
            graph_eligible=True, admission_reason="test",
            semantic_contract="admission-harbor-v2")
        return allocate_identity(r, corpus_id="c", doc_id="d", chunk_id="ch",
                                 span_start=0, span_end=len(proposal)).entity_id

    bare = _id("CareConnect portal", "CareConnect portal")
    definite = _id("CareConnect portal", "the CareConnect portal")
    assert bare == definite, (
        "a determiner in the envelope split one referent into two entities")


def test_non_durable_resolved_endpoints_write_their_own_parked_entity_row():
    """Row-57 edge found at book scale: skipping the entities insert for
    ANTECEDENT_RESOLVED endpoints is correct ONLY when a durable anchor was
    inherited (the anchor's mention wrote the row). A resolved reference that
    inherited nothing carries its own span-scoped mention_ id, which nothing
    else writes — a parked fact referencing it violated facts' FK."""
    import inspect

    from workers.extract_worker import _persist_decision

    src = inspect.getsource(_persist_decision)
    guard = src.split('ANTECEDENT_RESOLVED"')[1][:120]
    assert "identity.durable" in guard, (
        "the skip must require an inherited DURABLE identity, or non-durable "
        "resolved endpoints leave dangling fact FKs")
