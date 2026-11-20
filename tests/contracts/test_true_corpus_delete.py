"""TRUE-CORPUS-DELETE-V1 (2026-11-20): deleting a library removes every row tied to it and can give the disk space back.

Owner: "I SHOULD BE ABLE TO TRULY DELETE A CORPUS AND IT DOES WHAT ITS SUPPOSE TO DO ON MY MACHINE AND GIVES ME STORAGE."

Measured live 2026-11-20 before this change: the delete named `projection_attempts.run_id`, a column that does not exist
(the step always failed behind `optional=True`); it purged evidence receipts with a sub-select that ran after the evidence
rows were deleted (it found nothing); 18 library-linked tables were never touched; the shared Qdrant collections kept the
library's points; nothing ever compacted Postgres, so the disk space never came back.

The database tests run only in the sealed harness (POLYMATH_TEST_DSN, a throwaway Postgres with every migration). The
Qdrant and Neo4j clients are replaced by fakes: a test never reaches a live store.
"""
from __future__ import annotations

import os
import re
import uuid
from types import SimpleNamespace
from urllib.parse import urlsplit

import pytest

psycopg = pytest.importorskip("psycopg")


def sealed_dsn() -> str | None:
    """The sealed harness's throwaway database, or None. Never the fleet's (port 5432, thousands of documents)."""
    dsn = os.environ.get("POLYMATH_TEST_DSN")
    if not dsn or (urlsplit(dsn).port or 5432) == 5432:
        return None
    try:
        with psycopg.connect(dsn, connect_timeout=3) as conn:
            if int(conn.execute("SELECT count(*) FROM documents").fetchone()[0]) >= 1000:
                return None
    except Exception:  # noqa: BLE001 — no database: the test is skipped
        return None
    return dsn


needs_db = pytest.mark.skipif(sealed_dsn() is None, reason="needs the sealed Postgres")

_DUMMY = {  # a value for a NOT NULL column without a default, by its information_schema data_type
    "text": "'{u}'", "character varying": "'{u}'", "character": "'x'", "integer": "0", "bigint": "0", "smallint": "0",
    "numeric": "0", "real": "0", "double precision": "0", "boolean": "false", "jsonb": "'{{}}'::jsonb",
    "json": "'{{}}'::json", "timestamp with time zone": "now()", "timestamp without time zone": "now()", "date": "now()",
    "uuid": "gen_random_uuid()", "ARRAY": "'{{}}'", "bytea": "'\\x00'::bytea",
}


def _seed(conn, table: str, keys: dict, uid: str) -> bool:
    """Insert one row tied to the test library; NOT NULL columns get type dummies. False when a constraint refuses it."""
    cols = conn.execute(
        """SELECT column_name, data_type, is_nullable, column_default FROM information_schema.columns
            WHERE table_schema='public' AND table_name=%s ORDER BY ordinal_position""", (table,)).fetchall()
    allowed = {}   # a column CHECKed against a value list ("status IN (...)") gets that list's first value
    for (definition,) in conn.execute("SELECT pg_get_constraintdef(oid) FROM pg_constraint "
                                      "WHERE conrelid = %s::regclass AND contype = 'c'", (f"public.{table}",)).fetchall():
        for col, first in re.findall(r"\(+(\w+)\)?(?:::text)? = ANY \(+ARRAY\['([^']*)'", definition):
            allowed.setdefault(col, first)
    names, exprs, args = [], [], []
    for name, dtype, nullable, default in cols:
        if name in allowed and name not in keys and nullable == "NO" and default is None:
            names.append(name)
            exprs.append("%s")
            args.append(allowed[name])
        elif name in keys:
            names.append(name)
            exprs.append("%s")
            args.append(keys[name])
        elif name == "corpus_ids":
            names.append(name)
            exprs.append("ARRAY[%s]::text[]")
            args.append(keys["corpus_id"])
        elif nullable == "NO" and default is None:
            if dtype not in _DUMMY:
                return False
            names.append(name)
            exprs.append(_DUMMY[dtype].format(u=f"{uid}-{name}"))
    conn.execute("SAVEPOINT seed_sp")
    try:
        conn.execute(f'INSERT INTO "{table}" ({", ".join(chr(34) + n + chr(34) for n in names)}) '
                     f'VALUES ({", ".join(exprs)})', args)
        conn.execute("RELEASE SAVEPOINT seed_sp")
        return True
    except Exception:  # noqa: BLE001 — a CHECK or foreign key refused the dummy row
        conn.execute("ROLLBACK TO SAVEPOINT seed_sp")
        conn.execute("RELEASE SAVEPOINT seed_sp")
        return False


_KEYS = ("corpus_id", "doc_id", "chunk_id", "run_id", "parent_id")


def _linked_tables(conn) -> list[tuple[str, str]]:
    """The test's OWN list of library-linked tables (it does not ask the code under test): every public base table with a
    library key, except the owner's query log and the governed-research tables (their run_id is an adapter run)."""
    rows = conn.execute(
        """SELECT c.table_name, array_agg(c.column_name::text) FROM information_schema.columns c
             JOIN information_schema.tables t ON t.table_schema=c.table_schema AND t.table_name=c.table_name
                                             AND t.table_type='BASE TABLE'
            WHERE c.table_schema='public' AND c.column_name = ANY(%s) AND c.data_type IN ('text','character varying')
            GROUP BY 1 ORDER BY 1""", (list(_KEYS),)).fetchall()
    return [(t, next(k for k in _KEYS if k in cols)) for t, cols in rows
            if t != "query_receipts" and not t.startswith("adapter_")]


def _count(conn, table: str, col: str, value) -> int:
    op = "= %s" if col == "corpus_id" else "= ANY(%s)"
    return int(conn.execute(f'SELECT count(*) FROM "{table}" WHERE "{col}" {op}',
                            (value if col == "corpus_id" else [value],)).fetchone()[0])


class _NoStore:
    """Stands in for Qdrant and Neo4j: the delete's derived-store step reports an error and touches nothing live."""

    def __call__(self, *a, **k):
        raise RuntimeError("no live store in a contract test")


@needs_db
def test_a_deleted_library_leaves_no_row_in_any_library_linked_table(monkeypatch):
    from orchestrator.api import ui
    from polymath_shared import stores

    monkeypatch.setattr(stores, "qdrant_client", _NoStore())
    monkeypatch.setattr(stores, "neo4j_driver", _NoStore())
    uid = uuid.uuid4().hex[:10]
    corpus, run, doc, chunk = f"tcd-{uid}", f"run_tcd{uid}", f"doc_tcd{uid}", f"chk_tcd{uid}"
    evidence = f"ev_tcd{uid}"
    keys = {"corpus_id": corpus, "run_id": run, "doc_id": doc, "chunk_id": chunk, "parent_id": chunk}
    seeded: list[tuple[str, str, str]] = []
    with psycopg.connect(sealed_dsn()) as conn:
        for anchor in ("corpora", "runs", "documents", "chunks"):
            assert _seed(conn, anchor, keys, uid), f"could not seed the anchor table {anchor}"
        conn.execute("INSERT INTO projection_attempts (projection, entity_kind, entity_id, receipt_hash, contract) "
                     "VALUES ('qdrant','chunk',%s,'h','c'), ('neo4j','evidence',%s,'h','c')", (chunk, evidence))
        for table, col in _linked_tables(conn):
            if table in ("corpora", "runs", "documents", "chunks"):
                continue
            if _seed(conn, table, keys, uid):
                seeded.append((table, col, keys[col]))
        conn.commit()
    assert len(seeded) >= 10, f"too few library-linked tables accepted a test row to prove anything: {seeded}"

    with psycopg.connect(sealed_dsn()) as conn:   # the evidence receipt purge reads evidence ids before evidence goes
        if _seed(conn, "evidence", {**keys, "evidence_id": evidence}, uid) and _seed(
                conn, "projection_receipts", {"projection": "neo4j", "entity_kind": "evidence", "entity_id": evidence}, uid):
            conn.commit()
            evidence_seeded = True
        else:
            conn.rollback()
            evidence_seeded = False

    removed: dict = {}
    out = ui._delete_corpus_tx(corpus, removed)
    assert out["deleted"] == corpus
    assert "tables_not_deleted" not in removed, removed.get("tables_not_deleted")

    with psycopg.connect(sealed_dsn()) as conn:
        left = {t: n for t, c, v in seeded if (n := _count(conn, t, c, v))}
        assert left == {}, f"rows of the deleted library survived: {left}"
        for anchor, col, value in (("corpora", "corpus_id", corpus), ("runs", "run_id", run),
                                   ("documents", "doc_id", doc), ("chunks", "chunk_id", chunk)):
            assert _count(conn, anchor, col, value) == 0, anchor
        attempts = conn.execute("SELECT count(*) FROM projection_attempts WHERE entity_id = ANY(%s)",
                                ([chunk, evidence],)).fetchone()[0]
        assert attempts == (0 if evidence_seeded else 1), "projection_attempts of the deleted library survived"
        if evidence_seeded:
            receipts = conn.execute("SELECT count(*) FROM projection_receipts WHERE entity_id = %s", (evidence,)).fetchone()[0]
            assert receipts == 0, "the evidence receipt of the deleted library survived"
        else:  # evidence refused the dummy row: clean the attempt this test wrote
            conn.execute("DELETE FROM projection_attempts WHERE entity_id = %s", (evidence,))
            conn.commit()


@needs_db
def test_the_query_log_and_research_runs_are_kept():
    from orchestrator.api import ui
    with psycopg.connect(sealed_dsn()) as conn:
        tables = {t for t, _ in ui.library_linked_tables(conn)}
    assert "query_receipts" not in tables
    assert not any(t.startswith("adapter_") for t in tables)
    assert {"chunks", "documents", "runs", "corpora"} <= tables


class _FakeQdrant:
    def __init__(self, points: dict[str, list[str]]):
        self.points = points   # collection -> corpus_id of each point
        self.deleted: list[tuple[str, str]] = []

    def get_collections(self):
        return SimpleNamespace(collections=[SimpleNamespace(name=n) for n in self.points])

    @staticmethod
    def _corpus(flt) -> str:
        return flt.must[0].match.value

    def count(self, name, count_filter, exact):
        return SimpleNamespace(count=sum(1 for c in self.points[name] if c == self._corpus(count_filter)))

    def delete(self, name, points_selector):
        corpus = self._corpus(points_selector.filter)
        self.points[name] = [c for c in self.points[name] if c != corpus]
        self.deleted.append((name, corpus))


def test_the_shared_collections_lose_only_the_deleted_librarys_points():
    from orchestrator.api import ui
    fake = _FakeQdrant({
        "polymath_document_parent_maps_bge": ["cinema", "mythos", "mythos"],
        "polymath_document_profiles_bge": ["mythos"],
        "polymath_document_profile_atoms_bge": ["cinema"],
        "polymath_gnn_parent_bge_cinema": ["cinema"],
        "polymath_0123456789ab_bge": ["mythos"],          # a library's own collection: the prefix sweep's job, not this one
    })
    assert ui._delete_shared_collection_points(fake, "mythos") == 3
    assert fake.points["polymath_document_parent_maps_bge"] == ["cinema"]
    assert fake.points["polymath_document_profiles_bge"] == []
    assert fake.points["polymath_document_profile_atoms_bge"] == ["cinema"]
    assert fake.points["polymath_0123456789ab_bge"] == ["mythos"]
    assert {n for n, _ in fake.deleted} == {"polymath_document_parent_maps_bge", "polymath_document_profiles_bge"}


@needs_db
def test_reclaim_compacts_an_emptied_table_and_skips_one_the_disk_cannot_copy(tmp_path):
    from polymath_shared.storage_reclaim import reclaim
    table = f"tcd_reclaim_{uuid.uuid4().hex[:8]}"
    with psycopg.connect(sealed_dsn(), autocommit=True) as conn:
        conn.execute(f"CREATE TABLE {table} (id int, pad text)")
        try:
            conn.execute(f"INSERT INTO {table} SELECT g, repeat('x', 500) FROM generate_series(1, 20000) g")
            removed = conn.execute(f"DELETE FROM {table} WHERE id > 1000").rowcount
            def size() -> int:
                return conn.execute("SELECT pg_total_relation_size(%s::regclass)", (table,)).fetchone()[0]
            before = size()

            no_room = reclaim(conn, {table: removed}, data_dir=tmp_path, free_bytes=lambda p: 10 * 1024 ** 2)
            assert no_room["tables"][0]["status"] == "skipped"
            assert size() == before, "a skipped table must not be touched"

            done = reclaim(conn, {table: removed, "no_such_table": 5, "not_a_count": "x"}, data_dir=tmp_path,
                           reserve_bytes=0)
            row = done["tables"][0]
            assert [r["table"] for r in done["tables"]] == [table]
            assert row["status"] == "compacted" and row["rows_kept"] == 1000
            assert row["bytes_after"] < before / 5, (before, row["bytes_after"])
            assert done["freed_bytes"] == before - row["bytes_after"]
        finally:
            conn.execute(f"DROP TABLE IF EXISTS {table}")
