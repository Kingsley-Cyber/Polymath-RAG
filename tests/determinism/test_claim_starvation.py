"""One unclaimable event must never starve the queue behind it.

Observed in production: an old `vocab-probe-v2` run pinned
`semantic-query-policy-v2` and the `semantic_v2` chunker, semantics this
fleet does not run. No worker could ever claim it. The claim query
ordered by event_id and took the first `limit` rows, so that single
permanently incompatible event sat at the head of the intake queue and
starved 48 compatible events behind it -- an entire freshly ingested
corpus among them.

Nothing looked wrong. Workers heartbeated, leases were sound, no ticket
errored, no receipt failed. The fleet simply never claimed anything, and
the only symptom was one WARNING repeating every two seconds.

The fence is structural rather than behavioural because reproducing it
needs a live queue: what matters is that the query EXCLUDES what this
process already refused, and that refusals expire so a deliberate
semantic cutover re-admits the work.
"""

from __future__ import annotations

import ast
import pathlib
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))

RUNTIME = ROOT / "shared" / "polymath_shared" / "worker_runtime.py"


def _fn(name: str):
    tree = ast.parse(RUNTIME.read_text())
    for node in ast.walk(tree):
        if (isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                and node.name == name):
            return node
    raise AssertionError(f"{name}() missing from {RUNTIME.name}")


def test_claim_query_excludes_already_refused_events():
    """Without this the scan re-reads the same unclaimable head forever."""
    fn = _fn("claim_ticket_events")
    sql = " ".join(n.value for n in ast.walk(fn)
                   if isinstance(n, ast.Constant) and isinstance(n.value, str))
    assert "event_id = ANY" in sql and "NOT (" in sql, (
        "the claim query does not exclude previously refused events, so a "
        "permanently incompatible event at the head starves everything "
        "behind it")


def test_refusal_is_recorded_not_merely_logged():
    fn = _fn("claim_ticket_events")
    handlers = [n for n in ast.walk(fn)
                if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                and n.func.attr == "add"]
    assert handlers, ("an incompatible event is skipped without being "
                      "recorded; the next fetch will return it again")


def test_refusals_expire_so_a_cutover_readmits_work():
    """A refusal is a statement about THIS configuration, not forever."""
    from polymath_shared import worker_runtime as wr

    assert getattr(wr, "_REFUSED_TTL_S", 0) > 0, "refusals never expire"
    wr._REFUSED["probe"] = {1, 2, 3}
    wr._REFUSED_AT["probe"] = time.time() - (wr._REFUSED_TTL_S + 1)
    assert wr._refused_set("probe") == set(), (
        "refusals outlived their TTL; a semantic cutover would never "
        "re-admit work the previous configuration could not run")


def test_refusal_sets_are_per_worker_type():
    """Different stages run different contracts and refuse different work."""
    from polymath_shared import worker_runtime as wr

    wr._REFUSED.clear()
    wr._REFUSED_AT.clear()
    a = wr._refused_set("intake")
    a.add(11)
    b = wr._refused_set("extract")
    assert 11 not in b, "refusal sets are shared across worker types"


def test_repeated_refusal_does_not_relog_every_poll():
    """The original defect's only symptom was a line repeating every 2s."""
    fn = _fn("claim_ticket_events")
    for node in ast.walk(fn):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and node.func.attr == "warning"):
            enclosing = [g for g in ast.walk(fn)
                         if isinstance(g, ast.If) and node in list(ast.walk(g))]
            assert enclosing, ("the refusal warning is unconditional; it will "
                              "repeat every poll and read as noise rather "
                              "than as a starved queue")
            return
    raise AssertionError("no refusal warning found")


def test_fresh_runs_claim_before_historical_backlog():
    """FOREGROUND-UNDER-BACKLOG (measured live 2026-08-25): strict
    event_id FIFO parked a newly submitted document behind 238 ready
    backlog tickets — new work waited tens of minutes for downstream
    stages while the fleet was otherwise healthy. The claim query now
    sorts FRESH runs (created within 15 min) ahead of historical work,
    FIFO within each lane, ticketed-before-orphan preserved."""
    sql = " ".join(
        n.value for n in ast.walk(_fn("claim_ticket_events"))
        if isinstance(n, ast.Constant) and isinstance(n.value, str))
    assert "r.created_at > now() - interval '15 minutes'" in sql
    # fresh lane first, then legacy ticketed-first priority, then FIFO
    assert sql.index("r.created_at > now() - interval '15 minutes'") \
        < sql.index("t.ticket_id IS NOT NULL")
    assert "e.event_id" in sql
