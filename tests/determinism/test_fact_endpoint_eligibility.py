"""FACT-ENDPOINT-ELIGIBILITY-V2.

An unresolved closed-class pronoun is evidence, never durable knowledge
identity. It remains fully valid as raw source, as a mention, and as
syntax/discourse evidence — it simply may not BE the thing a fact is
about.

MEASURED before this gate: 557 of 3,184 accepted facts (17.5%) carried a
pronoun endpoint (`you --instance_of--> microsoft`,
`you --founded--> organization`, `they --uses--> ssh`). Three `they`
entities had additionally reached CORPUS_SCOPED admission, which carried
those edges into Neo4j.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
for p in (ROOT / "shared", ROOT):
    sys.path.insert(0, str(p))

from polymath_shared.entity_admission import (  # noqa: E402
    CLOSED_CLASS_PRONOUNS,
    is_unresolved_pronoun,
)

DSN = os.environ.get(
    "POLYMATH_PG_DSN",
    "postgresql://polymath:polymath-dev@127.0.0.1:5432/polymath")


def _pg():
    import psycopg
    try:
        return psycopg.connect(DSN, connect_timeout=3)
    except Exception:
        return None


pg_required = pytest.mark.skipif(_pg() is None, reason="postgres unavailable")


# ============================================== PRECISION HARD NEGATIVES
# A naive lowercase membership test destroys real named entities. Every
# one of these must survive.
NAMED_ENTITIES = [
    "You.com",   # punctuation — not a bare token
    "WeWork",    # internal capital
    "US", "IT", "WHO", "WE",   # ALL-CAPS acronym identity
    "They Might Be Giants",    # multi-token
    "iPhone", "Microsoft", "nmap", "SIEM", "ATT&CK",
]
PRONOUNS = ["you", "You", "they", "They", "it", "we", "this", "them", "her"]


@pytest.mark.parametrize("surface", NAMED_ENTITIES)
def test_named_entities_are_never_treated_as_pronouns(surface):
    assert not is_unresolved_pronoun(surface), (
        f"{surface!r} classified as a pronoun — the gate would destroy a "
        "real named entity")


@pytest.mark.parametrize("surface", PRONOUNS)
def test_bare_pronouns_are_detected(surface):
    assert is_unresolved_pronoun(surface)


def test_pronoun_class_is_closed():
    """The list must stay a language-level closed class. If it starts
    growing to cover domain vocabulary, it has become a heuristic."""
    assert len(CLOSED_CLASS_PRONOUNS) <= 40
    assert all(w.isalpha() and w == w.lower() for w in CLOSED_CLASS_PRONOUNS)


# ================================================= ADMISSION IS FIRST
def test_pronoun_can_never_receive_a_durable_admission_class():
    """The three leaked `they` entities reached CORPUS_SCOPED through a
    later branch. The pronoun decision must therefore come FIRST, so no
    acronym/proper/discriminative rule can promote it."""
    from polymath_shared.entity_admission import _classify

    for surface in ("you", "They", "it", "we", "them"):
        cls, reasons = _classify(surface, sentence_initial=False)
        assert cls == "MENTION_ONLY", (
            f"{surface!r} admitted as {cls} — it can become a fact "
            "endpoint and a graph node")
        assert "unresolved_closed_class_pronoun" in reasons

    # and a named entity must still be admitted normally
    cls, _ = _classify("Microsoft", sentence_initial=False)
    assert cls != "MENTION_ONLY"


# ==================================================== LEDGER STATE
@pg_required
def test_no_active_fact_has_a_pronoun_endpoint():
    """GATE: unresolved pronoun accepted fact endpoints = 0.

    DERIVED FROM THE AUTHORITATIVE SET, not a hand-written list. The
    first version of this test hardcoded 12 surfaces while
    CLOSED_CLASS_PRONOUNS held 29, so it reported GREEN while `i` and
    `it` were live fact endpoints on a freshly ingested transcript —
    both of them in the 17 it never checked. A gate that enumerates a
    subset of the thing it guards is a false green.
    """
    conn = _pg()
    with conn:
        rows = conn.execute(
            """SELECT DISTINCT e.normalized_surface
                 FROM facts f
                 JOIN entities e ON e.entity_id IN (f.subject_id, f.object_id)
                WHERE f.decision <> 'REJECT'""").fetchall()
    offenders = sorted({r[0] for r in rows if is_unresolved_pronoun(r[0] or "")})
    assert not offenders, (
        f"{len(offenders)} pronoun surfaces are live fact endpoints: "
        f"{offenders[:12]}")


@pg_required
def test_no_active_fact_has_a_mention_only_endpoint():
    """An endpoint with no durable identity cannot be what a fact is
    about. MEASURED before FACT-ENDPOINT-ENFORCEMENT-V1: the admission
    chain recorded 147 rejections and enforced none of them, because it
    runs in shadow by default."""
    conn = _pg()
    with conn:
        n = conn.execute(
            """SELECT count(*) FROM facts f
                WHERE f.decision <> 'REJECT'
                  AND (f.subject_id LIKE 'mention\\_%'
                    OR f.object_id LIKE 'mention\\_%')""").fetchone()[0]
    assert n == 0, f"{n} active facts carry a MENTION_ONLY endpoint"


def test_the_gate_covers_the_whole_closed_class():
    """Pin the derivation itself: this test must not drift back into a
    hand-maintained subset."""
    src = Path(__file__).read_text()
    body = src[src.index("def test_no_active_fact_has_a_pronoun_endpoint"):]
    body = body[:body.index("\n@pg_required", 1)]
    assert "is_unresolved_pronoun" in body, (
        "the pronoun gate no longer derives from the authoritative "
        "closed-class set")
    assert "normalized_surface IN (" not in body, (
        "the gate is enumerating surfaces again; it will go green on the "
        "pronouns it forgot to list")


def test_endpoint_gate_enforces_even_in_shadow():
    """The chain is shadow-by-default, which is right for gates still
    being qualified and wrong for endpoint eligibility."""
    from workers.fact_admission_stage import ALWAYS_ENFORCED_GATES

    assert "F3_ENDPOINTS" in ALWAYS_ENFORCED_GATES, (
        "endpoint eligibility is advisory again; ineligible endpoints "
        "will be written as durable facts while the chain records that "
        "it refused them")
    stage_src = (ROOT / "workers" / "workers"
                 / "fact_admission_stage.py").read_text()
    assert "if hard_refusal:\n            return False" in stage_src, (
        "a hard refusal no longer withholds the assertion")


@pg_required
def test_retirement_preserved_raw_observations_and_dispositions():
    """Retirement is not deletion: the pronoun remains valid evidence,
    and every withdrawal keeps its disposition."""
    conn = _pg()
    with conn:
        mentions = conn.execute(
            "SELECT count(*) FROM mentions "
            "WHERE lower(surface) IN ('you','we','they')").fetchone()[0]
        candidates = conn.execute(
            "SELECT count(*) FROM relation_candidates").fetchone()[0]
        dispositions = conn.execute(
            "SELECT count(*) FROM fact_admission_decisions "
            "WHERE gate = 'FACT_ENDPOINT_ELIGIBILITY_V2'").fetchone()[0]
    assert mentions > 0, "raw pronoun mentions were deleted — they are valid evidence"
    assert candidates > 0, "relation candidates were deleted"
    assert dispositions > 0, "retirement recorded no dispositions"


# ============================================ GRAPH ENDPOINT GUARD
def test_fact_projection_cannot_manufacture_an_ineligible_endpoint():
    """The measured bypass: the fact projection's
    `MERGE (s:Entity {entity_id: …})` CREATES an endpoint node, so a fact
    that slipped the eligibility filter manufactured an Entity the
    canonical policy had refused.

    The guard filters facts against the SAME eligible entity set the
    projector derived — one authority, not two competing policies."""
    src = (ROOT / "workers" / "workers" / "project_neo4j_worker.py").read_text()
    start = src.index("def _graph_rows")
    body = src[start:src.index("\ndef ", start + 1)]
    assert "eligible = {" in body and "projectable" in body, (
        "the graph endpoint guard is gone — fact projection can again "
        "MERGE an Entity node that entity admission refused")
    assert "refused_facts" in body, "guard no longer reports what it refused"
