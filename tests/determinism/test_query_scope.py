"""QUERY-SCOPE-V1 regressions (owner decision 2026-08-25).

Scope is explicit and fails closed. The implicit missing-scope →
search-all-corpora behavior is REMOVED. Probes/evaluations/fixtures can
never leak into ALL_AUTHORIZED. Scope propagates through every /ask
retrieval surface; no stage may widen it.
"""
from __future__ import annotations

import sys
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))
sys.path.insert(0, str(ROOT / "orchestrator"))
sys.path.insert(0, str(ROOT / "eval" / "v5" / "retrieval"))

import pytest

from polymath_shared.query_scope import (
    QueryScope,
    QueryScopeRequired,
    UnknownQueryScope,
    resolve_query_scope,
)


class FakeConn:
    """Serves corpora/workspaces rows; records SQL for propagation."""

    known = {"release-books-v1", "wedding-niche-v1", "probe-x"}

    def __init__(self, corpora_rows, workspace_rows=None):
        self._corpora = corpora_rows
        self._workspaces = workspace_rows or {}
        self.sqls: list[tuple[str, tuple]] = []

    def execute(self, sql, params=None):
        flat = " ".join(sql.split())
        if "FROM query_workspaces" in flat:
            ids = self._workspaces.get(params[0])
            return _Row((ids,) if ids else None)
        if "FROM corpora" in flat and "purpose" in flat:
            return _Rows([(c,) for c in self.production_enabled])
        return _Capture(self, flat, params)


class _Row:
    def __init__(self, row):
        self._row = row

    def fetchone(self):
        return self._row


class _Rows:
    def __init__(self, rows):
        self._rows = rows

    def fetchall(self):
        return self._rows


class _Capture:
    def __init__(self, conn, sql, params):
        self._conn = conn
        self._sql = sql
        self._params = params or ()

    def fetchone(self):
        self._conn.sqls.append((self._sql, self._params))
        if "FROM corpora WHERE corpus_id=%s" in self._sql:
            cid = self._params[0]
            if cid in self._conn.known:
                return (1,)
            return None
        return None

    known = {"release-books-v1", "wedding-niche-v1", "probe-x"}


def _conn(production=("release-books-v1",)):
    c = FakeConn([])
    c.production_enabled = list(production)
    return c


# ---- A: no scope fails closed ---------------------------------------
def test_missing_scope_raises_typed_error():
    with pytest.raises(QueryScopeRequired) as e:
        resolve_query_scope(_conn())
    assert e.value.reason == "QUERY_SCOPE_REQUIRED"


def test_empty_corpus_ids_list_is_no_scope():
    with pytest.raises(QueryScopeRequired):
        resolve_query_scope(_conn(), corpus_ids=[])


def test_ambiguous_scope_rejected():
    with pytest.raises(ValueError):
        resolve_query_scope(_conn(), corpus_id="release-books-v1",
                            all_authorized=True)


# ---- B/C/D/E: scope resolution rules ---------------------------------
def test_corpus_scope_resolves_single():
    s = resolve_query_scope(_conn(), corpus_id="release-books-v1")
    assert s == QueryScope("CORPUS", ("release-books-v1",))


def test_unknown_corpus_fails_closed():
    with pytest.raises(UnknownQueryScope):
        resolve_query_scope(_conn(), corpus_id="nope")


def test_multi_corpus_scope_permits_both():
    c = _conn()
    c.known.add("wedding-niche-v1")
    s = resolve_query_scope(c, corpus_ids=["release-books-v1",
                                           "wedding-niche-v1"])
    assert s.mode == "CORPORA"
    assert set(s.corpus_ids) == {"release-books-v1", "wedding-niche-v1"}


def test_all_authorized_returns_only_production_query_enabled():
    c = _conn(production=["release-books-v1", "wedding-niche-v1"])
    s = resolve_query_scope(c, all_authorized=True)
    assert s.mode == "ALL_AUTHORIZED"
    assert set(s.corpus_ids) == {"release-books-v1", "wedding-niche-v1"}
    # probe corpora absent even if they contain perfect matches
    assert "probe-x" not in s.corpus_ids


def test_workspace_resolves_persisted_group():
    c = FakeConn([], {"team": ["release-books-v1", "wedding-niche-v1"]})
    c.production_enabled = []
    c.known = set()
    s = resolve_query_scope(c, workspace="team")
    assert s.mode == "WORKSPACE"
    assert len(s.corpus_ids) == 2


def test_unknown_workspace_fails_closed():
    with pytest.raises(UnknownQueryScope):
        resolve_query_scope(FakeConn([]), workspace="ghost")


# ---- F–K: propagation through ask surfaces ---------------------------
from orchestrator.api.ask import (_procedures, _concepts, _facts,
                                  _concept_graph)


class RecordingConn(FakeConn):
    """Captures artifact-table queries; serves empty result sets."""

    def execute(self, sql, params=None):
        self.sqls.append((sql, params))
        return _Rows([])


SCOPE = QueryScope("CORPORA", ("release-books-v1",))


def test_procedures_obey_scope():
    c = RecordingConn([])
    _procedures(c, SCOPE, "install splunk on aws")
    sql, params = [s for s in c.sqls if "procedure_artifacts" in s[0]][0]
    assert "corpus_id = ANY(%s)" in sql
    assert params[0] == ["release-books-v1"]


def test_concepts_obey_scope():
    c = RecordingConn([])
    _concepts(c, SCOPE, "propaganda")
    sql, params = [s for s in c.sqls if "concept_artifacts" in s[0]][0]
    assert "corpus_id = ANY(%s)" in sql
    assert params[0] == ["release-books-v1"]


def test_facts_obey_scope():
    c = RecordingConn([])
    _facts(c, SCOPE, "orion benchmark")
    sql, params = [s for s in c.sqls if "FROM facts" in s[0]][0]
    assert "d.corpus_id = ANY(%s)" in sql
    assert params[0] == ["release-books-v1"]


def test_concept_graph_obey_scope():
    c = RecordingConn([])
    _concept_graph(c, SCOPE, ["propaganda"])
    sql, params = [s for s in c.sqls if "concept_families" in s[0]][0]
    assert "corpus_id = ANY(%s)" in sql
    assert params[0] == ["release-books-v1"]


def test_no_implicit_widening_exists_in_source():
    """The removed fallback must stay removed: no helper may accept a
    None-corpus all-corpora path."""
    import inspect
    import orchestrator.api.ask as A
    for name in ("_procedures", "_concepts", "_facts"):
        src = inspect.getsource(getattr(A, name))
        assert "Optional[str]" not in src, \
            f"{name} regressed to optional-corpus semantics"


# ---- dense/graph lane scoping (existing production behavior pinned) --
def test_dense_lane_payload_filters_corpus():
    """VECTOR/HYBRID dense search filters representation_kind AND
    corpus_id at Qdrant level (three_mode_benchmark.Bench.dense)."""
    import inspect
    from three_mode_benchmark import Bench
    src = inspect.getsource(Bench.dense)
    assert '"key": "corpus_id"' in src
    assert '"match": {"value": self.corpus}' in src


def test_graph_seeds_derive_from_scoped_children():
    """GRAPH seeds come only from scoped hybrid children; facts join
    evidence by those seed docs — traversal cannot leave the scope."""
    import inspect
    from three_mode_benchmark import Bench
    seeds_src = inspect.getsource(Bench.mode_graph)
    assert "fused_evidence" in seeds_src          # seeds from scoped fusion
    facts_src = inspect.getsource(Bench.graph_facts)
    assert "ev.doc_id = ANY(%s)" in facts_src     # fact backfill doc-bounded


# ---- creation round-robin (measured live during Stage-K pilot) -------
def test_creation_round_robin_serves_workless_corpora():
    """A work-less corpus must still advance its last_creation_tick when
    served, otherwise stale entries pin the window edge and new corpora
    starve forever (measured: pilot-modern-v1 unserved for 70 min at
    position 36 of a 32-wide rotation)."""
    import ast
    src = pathlib.Path(ROOT / "control" / "control" / "tickets.py").read_text()
    tree = ast.parse(src)
    fn = next(n for n in ast.walk(tree)
              if isinstance(n, ast.FunctionDef)
              and n.name == "fair_ensure_tickets_backpressure_gated")
    # the UPDATE to last_creation_tick must appear BEFORE the `continue`
    positions = {}
    for node in ast.walk(fn):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            if "last_creation_tick=now()" in node.value:
                positions["update"] = node.lineno
        if isinstance(node, ast.Continue):
            positions.setdefault("continue", node.lineno)
    assert "update" in positions and "continue" in positions
    assert positions["update"] < positions["continue"], (
        "work-less corpora skip the tick update and starve the rotation")


def test_archived_chain_suppression():
    """schedule_gaps must not re-arm events for runs whose ticket chain
    was deliberately superseded/archived — measured live: 44k armed
    scale-debris events occupied the claim FIFO after ticket archival."""
    import inspect
    from control import scheduler as S
    src = inspect.getsource(S.schedule_gaps)
    assert "_archived_run_ids" in src
    helper = inspect.getsource(S._archived_run_ids)
    assert "superseded" in helper and "ANY(%s)" in helper
    assert "archived_corpora" in helper, (
        "registry marker must survive runtime ticket cleanup")


def test_archived_corpora_out_of_lifecycle():
    """ARCHIVED-CORPUS-REGISTRY: archived corpora get no creation window
    and no contract-drift reconciliation (measured: drift reconciliation
    regenerated 9,373 ready scale events minutes after cleanup)."""
    import inspect
    from control import reconciliation as R
    rec_src = inspect.getsource(R.reconcile_contract_drift)
    assert "archived_corpora" in rec_src
    from control import tickets as T
    elig = inspect.getsource(T.eligible_creation_corpora)
    assert "archived_corpora" in elig


def test_done_ticket_is_completion_proof_for_attemptless_stages():
    """SUMMARY-ATTEMPT-EQUIVALENCE: the summaries layer completes tickets
    without stage_attempt rows; a DONE predecessor ticket must satisfy
    _stage_attempt_ok or the summary waterfall can never advance
    (measured live: parent_summary done -> document_summary pending
    forever)."""
    import inspect
    from control import tickets as T

    class Conn:
        def __init__(self):
            self.queries = []
        def execute(self, sql, params=None):
            self.queries.append(" ".join(sql.split()))
            return self
        def fetchone(self):
            q = self.queries[-1]
            if "FROM stage_attempts" in q:
                return None              # no attempt row exists
            if "status='done'" in q:
                return (1,)              # durable DONE ticket exists
            return None

    assert T._stage_attempt_ok(Conn(), "run_x", "parent_summary") is True
