"""SEMANTIC-RESIDUE-RECONCILIATION-V1.

`entities` and `facts` are not corpus-scoped, so a corpus wipe leaves them
behind. A failed run's rows then survive every subsequent wipe and stay
visible to canonicalization candidates, antecedent selection, entity counts
and graph reconstruction — contaminating measurements taken afterwards.

The authority is the provenance chain, never a timestamp or run label.
"""
import pytest

from workers.verify_worker import (
    RESIDUE_CONTRACT, reconcile_semantic_residue,
)


class _FakeConn:
    """Records the SQL a pass issues, so ordering can be asserted without a
    live database."""

    def __init__(self, rows):
        self.rows, self.executed, self.committed = rows, [], False

    def execute(self, sql, params=None):
        self.executed.append((" ".join(sql.split()), params))
        key = next((k for k in self.rows if k in sql), None)
        return _Result(self.rows.get(key, []) if key else [])

    def commit(self):
        self.committed = True


class _Result:
    def __init__(self, rows): self._rows = rows
    def fetchall(self): return [(r,) for r in self._rows]


def test_dry_run_is_the_default_and_deletes_nothing():
    conn = _FakeConn({"FROM facts f": ["f1"], "FROM entities e": ["e1"]})
    report = reconcile_semantic_residue(conn)
    assert report["applied"] is False
    assert not any("DELETE" in sql for sql, _ in conn.executed)
    assert conn.committed is False


def test_dry_run_reports_the_cascade_not_just_the_first_step():
    """Removing an orphan fact orphans the entities it alone held up. A dry
    run that ignored that would understate what the apply would remove."""
    conn = _FakeConn({"FROM facts f": ["f1", "f2"], "FROM entities e": ["e1"]})
    reconcile_semantic_residue(conn)
    entity_query = [(sql, p) for sql, p in conn.executed if "FROM entities e" in sql]
    assert entity_query, "entities were never evaluated"
    assert entity_query[-1][1] == (["f1", "f2"],), (
        "the entity scan must exclude facts already scheduled for removal")


def test_apply_deletes_along_the_provenance_chain_in_order():
    conn = _FakeConn({"FROM evidence e": ["v1"], "FROM facts f": ["f1"],
                      "FROM entities e": ["e1"]})
    report = reconcile_semantic_residue(conn, apply=True)
    deletes = [sql for sql, _ in conn.executed if sql.startswith("DELETE")]
    order = [next(t for t in ("evidence", "facts", "entities") if f"FROM {t}" in d)
             for d in deletes]
    # evidence before facts before entities; a fact's evidence goes with it
    assert order.index("entities") == len(order) - 1
    assert order.index("facts") < order.index("entities")
    assert conn.committed is True
    assert report["contract"] == RESIDUE_CONTRACT


def test_apply_reports_what_remains():
    conn = _FakeConn({})
    report = reconcile_semantic_residue(conn, apply=True)
    assert report["residual_after"] == {
        "dangling_evidence": 0, "unsupported_facts": 0,
        "unreferenced_entities": 0}


def test_rows_with_an_intact_chain_are_never_residue():
    """An entity referenced by a live mention stays, however old it is. The
    rule is provenance, not age."""
    conn = _FakeConn({})   # no orphan queries return rows
    report = reconcile_semantic_residue(conn, apply=True)
    assert report["unreferenced_entities"] == 0
    assert not [sql for sql, _ in conn.executed
                if sql.startswith("DELETE FROM entities")]
