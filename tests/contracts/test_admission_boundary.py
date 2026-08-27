"""ARCHITECTURE INVARIANTS — states the system must not be able to reach.

These are not unit tests. Every assertion here corresponds to a state
Polymath was actually in, happily, while every other test passed:

  * ENTITY-KNOWLEDGE-ADMISSION-V1 built, tested, qualified, frozen, with
    ZERO production callers.
  * FACT-ADMISSION-V1 called only from `eval/`, every decision carrying
    shadow=TRUE, while production projected the unadmitted graph.
  * Documentation declaring rule pack v1.3.0 byte-frozen while the
    runtime loaded v1.2.0, leaving frame arbitration inert.

None of those is a bug in a function. Each is a bug in what the
architecture permits. So the question these tests ask is not "did we
build fact admission?" but "can this repository physically project a
graph without it?"

The answer must be no, and it must stay no without anyone remembering
to check.
"""

from __future__ import annotations

import pathlib
import re
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))

from polymath_shared import bundle_integrity as BI  # noqa: E402


# ---------------------------------------------------------------------------
# 1. Namespace direction: production imports runtime, never eval
# ---------------------------------------------------------------------------

def _production_files() -> list[pathlib.Path]:
    out = []
    for d in BI.PRODUCTION_DIRS:
        base = ROOT / d
        if base.exists():
            out += [p for p in base.rglob("*.py")
                    if "__pycache__" not in str(p)]
    return out


def test_production_never_imports_evaluation():
    """`eval/` is where measurement lives, not where meaning lives.

    Fact admission was reachable ONLY from eval/, which is how a
    qualified boundary came to have no production caller: the logic had
    a home, and it was the wrong one.
    """
    offenders = []
    for p in _production_files():
        try:
            src = p.read_text()
        except Exception:
            continue
        if re.search(r"^\s*(from|import)\s+eval[\s.]", src, re.M):
            offenders.append(str(p.relative_to(ROOT)))
    assert not offenders, (
        f"production code imports from eval/: {offenders}. Production "
        f"imports runtime; evaluation imports runtime; never the reverse.")


# ---------------------------------------------------------------------------
# 2. The admission boundaries must have production callers
# ---------------------------------------------------------------------------

def test_entity_admission_has_a_production_caller():
    callers = BI.call_graph_census()["entity_admission"]
    assert callers, (
        "ENTITY-KNOWLEDGE-ADMISSION-V1 has zero production callers. It "
        "exists in source and does not run. Implementation is not "
        "activation: this is NOT_IMPLEMENTED.")


def test_fact_admission_has_a_production_caller():
    callers = BI.call_graph_census()["fact_admission"]
    assert callers, (
        "FACT-ADMISSION-V1 has zero production callers. Production ships "
        "the unadmitted graph while the shadow harness reports 14.5% "
        "wrong -- a number that describes nothing the system does. "
        "This was xfail while A3 was open; it flipped to a hard assertion "
        "the moment F1-F8 was wired, and must never be relaxed again.")


# ---------------------------------------------------------------------------
# 3. Configuration coherence
# ---------------------------------------------------------------------------

def test_declared_rule_pack_is_the_loaded_rule_pack():
    declared, loaded = BI._declared_rule_pack(), BI._loaded_rule_pack()
    assert declared and loaded, "could not resolve both versions"
    assert declared == loaded, (
        f"documentation declares core-predicates-v{declared} byte-frozen "
        f"while the runtime loads v{loaded}. This drift left grammatical "
        f"frame arbitration inert in production while the docs said it "
        f"was enforced.")


def test_semantic_bundle_lock_exists_and_matches_the_tree():
    lock = BI.read_lock()
    assert lock is not None, (
        f"no {BI.LOCK.relative_to(ROOT)}. Nothing pins the semantic "
        f"surface, so drift cannot be detected.")
    current = BI.compute_bundle()
    assert lock["bundle_sha256"] == current["bundle_sha256"], (
        "the semantic surface has drifted from the lock. Re-freeze "
        "deliberately (--freeze) or revert. 'Mostly compatible' is not a "
        "state this system may run in.")


def test_every_bundle_member_exists():
    missing = BI.compute_bundle()["missing"]
    assert not missing, f"declared semantic authorities absent: {missing}"


# ---------------------------------------------------------------------------
# 4. Projection may only read admitted knowledge
# ---------------------------------------------------------------------------

def test_graph_projection_reads_the_knowledge_tier_not_raw_candidates():
    """The physical question: can a graph be built without admission?

    A projector that selects straight from `relation_candidates` can
    assert an unadmitted claim, whether or not it does so today. It must
    read the tier view whose membership is DERIVED from admission
    outcomes.
    """
    proj = ROOT / "workers" / "workers" / "project_neo4j_worker.py"
    if not proj.exists():
        pytest.skip("neo4j projector not present")
    src = proj.read_text()
    reads_tier = ("knowledge_tier_facts" in src or "T2" in src)
    reads_raw = re.search(r"FROM\s+relation_candidates", src, re.I)
    assert reads_tier or not reads_raw, (
        "the graph projector reads relation_candidates directly and has "
        "no knowledge-tier source. Nothing physically prevents projecting "
        "a fact that admission never passed.")


def test_shadow_decisions_are_marked_and_separable():
    """A shadow decision must be distinguishable in the schema itself."""
    mig = ROOT / "stores" / "postgres" / "migrations"
    texts = " ".join(p.read_text() for p in mig.glob("*.sql"))
    assert "fact_admission_decisions" in texts
    assert "entity_admission_decisions" in texts, (
        "entity admission decisions have no ledger; activation cannot be "
        "verified from state")
    for table in ("fact_admission_decisions", "entity_admission_decisions"):
        seg = texts.split(table, 1)[1][:1400]
        assert "shadow" in seg, (
            f"{table} has no `shadow` column; a decision that does not "
            f"govern would be indistinguishable from one that does")


# ---------------------------------------------------------------------------
# 5. No model may write knowledge
# ---------------------------------------------------------------------------

def test_no_provider_writes_directly_to_the_graph():
    """GLiNER, GLiREL, REBEL, an LLM -- all are untrusted evidence.

    A provider that can reach the projector bypasses admission by
    construction, which is the generalised form of the original GLiNER
    problem: model output treated as truth.
    """
    offenders = []
    for p in (ROOT / "sidecars").rglob("*.py"):
        # Sidecars carry their own virtualenvs; a pygments lexer named
        # graph.py is not a provider reaching Neo4j. Scan OUR code only.
        parts = set(p.parts)
        if parts & {"__pycache__", ".venv", "site-packages", "node_modules"}:
            continue
        src = p.read_text()
        if re.search(r"\b(neo4j|GraphDatabase|MERGE\s*\()", src):
            offenders.append(str(p.relative_to(ROOT)))
    assert not offenders, (
        f"a provider sidecar reaches the graph directly: {offenders}. "
        f"Model output is untrusted evidence and must pass admission.")
