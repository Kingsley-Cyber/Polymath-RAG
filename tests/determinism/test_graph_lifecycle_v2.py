"""P9 GRAPH-LIFECYCLE-V2 — derived graph state must be pruned, and
authorization must not run after the limit.

MEASURED on the live graph before this phase:

    node/edge      total     stale (no Postgres row at all)
    Document      10,142    10,124        (18 real documents)
    Fact          12,428     9,280
    Evidence      12,514     9,451
    Chunk          8,887         0 — already reconciled
    Entity         4,108         0 — clean
    REL              545         0 — every edge has a PG fact

CORRECTION worth recording: the 85 REL edges whose fact is not ACCEPTED
are QUALIFY, not garbage. QUALIFY is a hedged or attributed claim that
is legitimately projected and legitimately withheld from plain-fact
answers. They must NOT be deleted. What was wrong was not their
existence but their timing — see defect 1.

Two distinct defects behind that.

1. THE ACUTE ONE — authorization after the limit.
   `_neo4j_expand` ran `ORDER BY fact_id LIMIT 20` in Cypher and only
   then filtered the rows against the authorized fact set in Python.
   Stale edges therefore consumed answer slots and were discarded
   afterwards. MEASURED: 15.6% of REL edges are unauthorized and a
   20-row fact_id window could be 8/20 garbage — 40% of the graph
   evidence budget spent on rows nobody is allowed to see. That is
   answer-bearing evidence displaced, which is a release blocker.
   Fixed by filtering inside the query, before LIMIT.

2. THE LIFECYCLE ONE — the reconciler pruned orphan Chunk nodes and
   endpoint-ineligible REL edges and nothing else, so Document, Fact and
   Evidence nodes accumulated forever. Deletion pruning Chunks is
   exactly what made this invisible: chunk counts reconciled cleanly
   while the rest of the graph kept growing. 28,855 orphan nodes were
   pruned when this phase ran; the reconciler now covers every derived
   node kind so it cannot recur.

The phase goal warned against exactly the trap we were in: "do not rely
on query authorization to hide permanent garbage." Authorization was
hiding it — and, because it ran too late, not even hiding it correctly.
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
for p in (ROOT / "shared", ROOT):
    sys.path.insert(0, str(p))

DSN = os.environ.get(
    "POLYMATH_PG_DSN",
    "postgresql://polymath:polymath-dev@127.0.0.1:5432/polymath")

RETRIEVE = ROOT / "orchestrator" / "orchestrator" / "api" / "retrieve.py"
VERIFY = ROOT / "workers" / "workers" / "verify_worker.py"


def _pg():
    try:
        import psycopg
        return psycopg.connect(DSN, connect_timeout=3)
    except Exception:
        return None


def _neo4j():
    try:
        from polymath_shared.stores import neo4j_driver
        d = neo4j_driver()
        with d.session() as s:
            s.run("RETURN 1").consume()
        return d
    except Exception:
        return None


pg_required = pytest.mark.skipif(_pg() is None, reason="postgres unavailable")
graph_required = pytest.mark.skipif(_neo4j() is None, reason="neo4j unavailable")


# ================================ AUTHORIZATION MUST PRECEDE THE LIMIT
def test_authorization_is_applied_before_the_limit():
    """THE ACUTE DEFECT. If LIMIT runs first, unauthorized rows spend
    slots that authorized evidence needed."""
    src = RETRIEVE.read_text()
    body = src[src.index("def _neo4j_expand"):]
    body = body[:body.index("\ndef ", 1)] if "\ndef " in body[1:] else body

    cypher_start = body.index("CALL ()")
    limit_at = body.index("LIMIT 20", cypher_start)
    auth_in_cypher = body.index("auth_filter", cypher_start)
    assert auth_in_cypher < limit_at, (
        "the authorization filter no longer appears inside the query "
        "before LIMIT — stale edges can consume answer slots again")
    assert "r.fact_id IN $authorized" in body, (
        "the Cypher authorization predicate is gone")
    assert "authorized=(" in body, (
        "the authorized set is no longer passed as a query parameter")


def test_unscoped_callers_still_work():
    """corpus_ids=None is the eval-only unscoped form. It must not
    inject an empty allowlist and silently return nothing."""
    body = RETRIEVE.read_text()
    assert 'auth_filter = "" if authorized is None' in body, (
        "an unscoped call would now filter against a null/empty set")


# ========================================= THE RECONCILER MUST PRUNE
@pytest.mark.parametrize("label,needle", [
    ("orphan Document nodes", "MATCH (n:Document {doc_id: $id}) DETACH DELETE n"),
    ("orphan Fact nodes", "MATCH (n:Fact {fact_id: $id}) DETACH DELETE n"),
    ("orphan Evidence nodes",
     "MATCH (n:Evidence {evidence_id: $id}) DETACH DELETE n"),
    ("orphan REL edges", "edge_ids - live_facts"),
    ("orphan Chunk nodes", "MATCH (c:Chunk {chunk_id: $id}) DETACH DELETE c"),
])
def test_reconciler_prunes_every_derived_node_kind(label, needle):
    """Pruning Chunks alone is what let the rest accumulate unseen."""
    assert needle in VERIFY.read_text(), f"reconciler no longer prunes {label}"


def test_reconciler_only_deletes_what_postgres_proves_is_gone():
    """In-flight rows must survive. The predicate is 'no PG row at all',
    never 'not accepted yet'."""
    src = VERIFY.read_text()
    assert "SELECT fact_id FROM facts" in src, (
        "the reconciler compares against a narrower set than all facts; "
        "an in-flight fact could be deleted mid-pipeline")
    assert not re.search(r"live_facts\s*=\s*\{[^}]*decision\s*=\s*'ACCEPT'", src), (
        "the reconciler now treats non-accepted facts as orphans — "
        "pending work would be deleted while in flight")


# ============================================== LIVE GRAPH DELTA
@pg_required
@graph_required
def test_no_derived_node_outlives_its_postgres_row():
    """ACCEPTANCE: PG expected vs Neo4j actual delta = 0 for every
    derived node kind. Postgres is authority; a node whose id has no PG
    row is permanent garbage."""
    import psycopg
    conn = psycopg.connect(DSN, connect_timeout=5)
    with conn:
        live = {
            "Document": ({r[0] for r in conn.execute(
                "SELECT doc_id FROM documents").fetchall()}, "doc_id"),
            "Fact": ({r[0] for r in conn.execute(
                "SELECT fact_id FROM facts").fetchall()}, "fact_id"),
            "Evidence": ({r[0] for r in conn.execute(
                "SELECT evidence_id FROM evidence").fetchall()}, "evidence_id"),
            "Chunk": ({r[0] for r in conn.execute(
                "SELECT chunk_id FROM chunks").fetchall()}, "chunk_id"),
        }
    driver = _neo4j()
    orphans = {}
    with driver.session() as s:
        for label, (ids, key) in live.items():
            got = {r["i"] for r in s.run(
                f"MATCH (n:{label}) RETURN n.{key} AS i") if r["i"]}
            stale = got - ids
            if stale:
                orphans[label] = len(stale)
    driver.close()
    assert not orphans, (
        f"derived graph nodes outliving their Postgres rows: {orphans}")


@pg_required
@graph_required
def test_qualified_edges_are_kept_not_deleted():
    """A QUALIFY fact is hedged or attributed knowledge, not garbage.
    It is legitimately projected and legitimately withheld from
    plain-fact answers by authorization — deleting it would be data
    loss, so the reconciler must leave it alone."""
    import psycopg
    conn = psycopg.connect(DSN, connect_timeout=5)
    with conn:
        qualified = {r[0] for r in conn.execute(
            "SELECT fact_id FROM facts WHERE decision='QUALIFY'").fetchall()}
    if not qualified:
        pytest.skip("no QUALIFY facts in this corpus")
    driver = _neo4j()
    with driver.session() as s:
        edges = {r["f"] for r in s.run(
            "MATCH ()-[r:REL]->() RETURN r.fact_id AS f") if r["f"]}
    driver.close()
    assert edges & qualified, (
        "no QUALIFY fact survives in the graph — the reconciler may be "
        "deleting hedged knowledge as if it were orphaned")
