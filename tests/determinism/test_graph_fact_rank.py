"""D1 (gap D-01 + D-02, roadmap row 6): GRAPH hop-1 facts ranked instead of the first 20 by `fact_id`, card seeds kept
best-first, and MCP rows that say when their text was cut.

The fact order is lexicographic and weight-free: evidence among the selected chunks → a specific predicate before the
ontology's last resort (`RELATED_TO`) → the seeds take turns (in seed order) → `fact_id`. Flag OFF (`POLYMATH_GRAPH_FACT_RANK`) keeps the
legacy `ORDER BY fact_id LIMIT 20` query and order unchanged. No database, no Neo4j: fakes capture what reaches them.
"""
from __future__ import annotations

import pathlib
import random
import types
from contextlib import contextmanager

import pytest

from orchestrator.api import retrieve as retrieve_mod
from polymath_shared import stores


def _fact(fid: str, pred: str, sub: str, obj: str) -> dict:
    return {"fact_id": fid, "predicate": pred, "subject_id": sub, "subject": sub, "object_id": obj, "object": obj}


SEEDS = ["card-best", "card-next", "surface-x"]
ROWS = [
    _fact("f_a", "RELATED_TO", "card-best", "o1"),    # top seed, last-resort predicate
    _fact("f_b", "CAUSES", "surface-x", "o2"),        # specific, lowest seed
    _fact("f_c", "PART_OF", "o3", "card-next"),       # specific, seed 1 (as the object)
    _fact("f_d", "RELATED_TO", "surface-x", "o4"),    # last resort, lowest seed — but its evidence is on the page
    _fact("f_e", "USES", "card-best", "o5"),          # specific, top seed
]


def test_the_rank_is_selected_then_specific_then_seed_then_id():
    got = [r["fact_id"] for r in retrieve_mod.rank_graph_facts(ROWS, SEEDS, {"f_d"})]
    assert got == ["f_d", "f_e", "f_c", "f_b", "f_a"]
    # without a selected set: specific facts by seed rank, then the last resort
    assert [r["fact_id"] for r in retrieve_mod.rank_graph_facts(ROWS, SEEDS, set())] == ["f_e", "f_c", "f_b", "f_a", "f_d"]


def test_the_seeds_take_turns_so_one_seed_cannot_fill_the_list():
    rows = [_fact(f"s0_{i}", "USES", "card-best", f"o{i}") for i in range(3)] + \
           [_fact(f"s1_{i}", "USES", "o", "card-next") for i in range(2)]
    got = [r["fact_id"] for r in retrieve_mod.rank_graph_facts(rows, SEEDS, set())]
    assert got == ["s0_0", "s1_0", "s0_1", "s1_1", "s0_2"]


def test_the_rank_is_deterministic_whatever_the_input_order():
    want = [r["fact_id"] for r in retrieve_mod.rank_graph_facts(ROWS, SEEDS, {"f_d"})]
    for seed in range(5):
        rows = ROWS[:]
        random.Random(seed).shuffle(rows)  # noqa: S311 — a test shuffle, not a security use
        assert [r["fact_id"] for r in retrieve_mod.rank_graph_facts(rows, SEEDS, {"f_d"})] == want
    ties = [_fact("f_z", "USES", "card-best", "o"), _fact("f_y", "USES", "card-best", "p")]
    assert [r["fact_id"] for r in retrieve_mod.rank_graph_facts(ties, SEEDS, set())] == ["f_y", "f_z"]   # ties by id


class _SeedConn:
    def __init__(self, rows):
        self.rows = rows

    def execute(self, sql, params=()):
        rows = self.rows

        class _R:
            def fetchall(self_inner):
                return list(rows)
        return _R()


def test_card_seeds_keep_the_probe_order_only_with_the_flag(monkeypatch):
    rows = [("card-b", "beta", False), ("card-a", "alpha", False), ("e1", "gamma", True)]
    args = (_SeedConn(rows), ["gamma"], ["cinema"], ["k1"])
    monkeypatch.delenv(retrieve_mod.FACT_RANK_FLAG, raising=False)
    assert retrieve_mod._corpus_seed_ids(*args, seed_entity_ids=["card-b", "card-a"]) == ["card-a", "card-b", "e1"]
    assert retrieve_mod._corpus_seed_ids(*args, seed_entity_ids=["card-b", "card-a"], max_seeds=1) == ["card-a"]
    monkeypatch.setenv(retrieve_mod.FACT_RANK_FLAG, "1")
    assert retrieve_mod._corpus_seed_ids(*args, seed_entity_ids=["card-b", "card-a"]) == ["card-b", "card-a", "e1"]
    assert retrieve_mod._corpus_seed_ids(*args, seed_entity_ids=["card-b", "card-a"], max_seeds=1) == ["card-b"]
    # a card the corpus does not authorize never seeds, whatever its rank
    assert retrieve_mod._corpus_seed_ids(*args, seed_entity_ids=["ghost", "card-a"]) == ["card-a", "e1"]


class _ExpandConn:
    """Answers the three SQL reads `_neo4j_expand` makes: seeds, authorized facts, selected facts."""

    def __init__(self):
        self.selected_params = None

    def execute(self, sql, params=()):
        conn = self
        if "FROM entities e" in sql:
            out = [("card-best", "best", False), ("card-next", "next", False), ("surface-x", "x", True)]
        elif "chunk_id = ANY" in sql:
            conn.selected_params = params
            out = [("f_d",)]
        elif "NOT EXISTS" in sql:
            out = []
        else:
            out = [(f"f_{c}",) for c in "abcde"] + [(f"g{i:02d}",) for i in range(30)]

        class _R:
            def fetchall(self_inner):
                return list(out)
        return _R()


def _install_graph(monkeypatch, rows):
    conn = _ExpandConn()

    @contextmanager
    def _tx():
        yield conn

    calls = []

    class _Session:
        def run(self, cypher, **kw):
            calls.append((cypher, kw))
            return types.SimpleNamespace(data=lambda: [dict(r) for r in rows])

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(retrieve_mod, "tx", _tx)
    monkeypatch.setattr(stores, "neo4j_driver", lambda: types.SimpleNamespace(session=_Session, close=lambda: None))
    return conn, calls


def test_flag_off_keeps_the_legacy_query_and_its_order(monkeypatch):
    monkeypatch.delenv(retrieve_mod.FACT_RANK_FLAG, raising=False)
    conn, calls = _install_graph(monkeypatch, ROWS)
    out = retrieve_mod._neo4j_expand(["best", "x"], corpus_ids=["cinema"], preferred_chunk_ids=["k1"],
                                     seed_entity_ids=["card-next", "card-best"])
    cypher, kw = calls[0]
    assert "ORDER BY fact_id" in cypher and "LIMIT 20" in cypher and "$pool" not in cypher and "pool" not in kw
    assert [r["fact_id"] for r in out] == [r["fact_id"] for r in ROWS]          # the store's order, untouched
    assert conn.selected_params is None                                          # no extra read when off
    assert kw["ids"] == ["card-best", "card-next", "surface-x"]                  # legacy: cards sorted by id


def test_flag_on_ranks_the_authorized_pool_and_keeps_twenty(monkeypatch):
    monkeypatch.setenv(retrieve_mod.FACT_RANK_FLAG, "1")
    pool = ROWS + [_fact(f"g{i:02d}", "USES", "surface-x", f"z{i}") for i in range(30)]
    conn, calls = _install_graph(monkeypatch, pool)
    out = retrieve_mod._neo4j_expand(["best", "x"], corpus_ids=["cinema"], preferred_chunk_ids=["k1", "k2"],
                                     seed_entity_ids=["card-next", "card-best"])
    cypher, kw = calls[0]
    assert "LIMIT $pool" in cypher and "LIMIT 20" not in cypher and kw["pool"] == retrieve_mod._FACT_RANK_POOL
    assert "r.fact_id IN $authorized" in cypher and kw["authorized"]            # authorization still inside the query
    assert kw["ids"] == ["card-next", "card-best", "surface-x"]                  # cards keep the probe's order
    assert conn.selected_params == (["k1", "k2"],)
    got = [r["fact_id"] for r in out]
    assert len(got) == 20
    # the fact whose evidence is on the page leads; then specific facts by seed rank (card-next = 0, card-best = 1)
    assert got[:4] == ["f_d", "f_c", "f_e", "f_b"]
    assert "f_a" not in got                                                      # the top seed's RELATED_TO fell below 20


def test_the_mcp_rows_say_when_their_text_was_cut(monkeypatch):
    monkeypatch.setenv("POLYMATH_MCP_API_KEY", "test-key")
    from orchestrator import mcp_server as mcp
    long_text, short = "x" * 1500, "short text"
    rows = mcp._trim_rows([{"id": "r1", "text": long_text, "text_clean": long_text},
                           {"id": "r2", "text": short, "text_clean": short}])
    assert len(rows[0]["text"]) == 1200 and len(rows[0]["text_clean"]) == 1200
    assert rows[0]["truncated"] is True and rows[0]["full_length"] == 1500
    assert rows[1] == {"id": "r2", "text": short, "text_clean": short}          # a row that fits is unchanged
    hit = mcp._trim_hit({"text": long_text, "chunk_id": "c1"})
    assert len(hit["text"]) == 1400 and hit["truncated"] is True and hit["full_length"] == 1500
    assert mcp._trim_hit({"text": short, "chunk_id": "c2"}) == {"text": short, "chunk_id": "c2"}
    assert mcp._trim_hit({"text": long_text}, 600)["full_length"] == 1500


def test_the_retrieve_route_says_which_order_served_it():
    src = pathlib.Path(retrieve_mod.__file__).read_text()
    body = src[src.index("async def _retrieve_impl"):src.index("def _document_clause")]
    assert 'out["graph_fact_order"] = "ranked"' in body and "if fact_rank_enabled():" in body


@pytest.mark.parametrize("value, on", [("1", True), ("0", False), ("", False), ("true", False)])
def test_the_flag_reads_exactly_one(monkeypatch, value, on):
    monkeypatch.setenv(retrieve_mod.FACT_RANK_FLAG, value)
    assert retrieve_mod.fact_rank_enabled() is on
