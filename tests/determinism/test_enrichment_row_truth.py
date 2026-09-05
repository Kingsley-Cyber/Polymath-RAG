"""ENRICHMENT-ROW-TRUTH-V2 (2026-09-05): an enrichment row is proof only
while its parent chunk exists.

Measured: a document deleted and re-ingested while a corpus sweep still
held its old parents got 184 rows persisted against dead chunk ids three
minutes after the delete; the UI reported it "enriched 103 / failed 81"
before the first real call, and identity reuse (EXISTING on input_hash)
would have skipped the new parents whose content matched.

Requires the dev Postgres; every row is created inside a transaction that
is rolled back at the end.
"""
from __future__ import annotations

import os
import pathlib
import sys
import uuid

import psycopg
import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
for sub in ("workers", "shared"):
    if str(ROOT / sub) not in sys.path:
        sys.path.insert(0, str(ROOT / sub))

from workers import summary_worker_impl as impl  # noqa: E402
from polymath_shared.latent.runtime import persist_compiled_parent  # noqa: E402
from polymath_shared.latent.compiler import CompiledParent  # noqa: E402
from polymath_shared.latent.contract import ChildGist, EnrichmentOutput  # noqa: E402

DSN = os.environ.get("POLYMATH_TEST_DSN", "postgresql://polymath:polymath-dev@127.0.0.1:5432/polymath")


@pytest.fixture
def conn():
    try:
        c = psycopg.connect(DSN, autocommit=False, connect_timeout=3)
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"dev postgres not reachable: {exc}")
    yield c
    try:
        c.rollback(); c.close()
    except Exception:  # noqa: BLE001
        pass


def _seed(conn):
    corpus = "rowtruth-" + uuid.uuid4().hex[:8]
    doc = "doc_rowtruth_" + uuid.uuid4().hex
    conn.execute("INSERT INTO corpora (corpus_id, name, config_hash) VALUES (%s, %s, 'h') ON CONFLICT DO NOTHING", (corpus, corpus))
    conn.execute("INSERT INTO documents (doc_id, corpus_id, source_name, media_type, byte_length, content_hash) VALUES (%s, %s, 'rt.md', 'text/markdown', 10, 'ch')", (doc, corpus))
    live = "chk_live_" + uuid.uuid4().hex[:16]
    conn.execute("INSERT INTO chunks (chunk_id, doc_id, chunk_index, tier, text, char_start, char_end) VALUES (%s, %s, 0, 'parent', 'live parent text', 0, 16)", (live, doc))
    dead = "chk_dead_" + uuid.uuid4().hex[:16]          # never inserted into chunks
    return corpus, doc, live, dead


def _row(conn, *, parent, doc, corpus, ih, status, error_class=None):
    conn.execute(
        """INSERT INTO parent_enrichments (enrichment_id, parent_id, corpus_id, doc_id, source_child_ids, source_hash,
                                           input_hash, provider, model, prompt_version, status, error_class)
           VALUES (%s, %s, %s, %s, %s, 'sh', %s, 'llm:test', 'm', 'v', %s, %s)""",
        ("penr_" + uuid.uuid4().hex[:24], parent, corpus, doc, ["c1"], ih, status, error_class))


def test_ready_row_on_live_parent_is_done_but_orphan_is_not(conn):
    corpus, doc, live, dead = _seed(conn)
    ih_live, ih_dead = "ih_" + uuid.uuid4().hex[:12], "ih_" + uuid.uuid4().hex[:12]
    _row(conn, parent=live, doc=doc, corpus=corpus, ih=ih_live, status="READY")
    _row(conn, parent=dead, doc=doc, corpus=corpus, ih=ih_dead, status="READY")
    assert impl._enrichment_row_done(conn, ih_live) is True
    assert impl._enrichment_row_done(conn, ih_dead) is False, "a READY row on a deleted chunk is not proof"


def test_summary_job_state_alone_is_never_proof(conn):
    corpus, doc, live, dead = _seed(conn)
    ih = "ih_" + uuid.uuid4().hex[:12]
    conn.execute("INSERT INTO summary_jobs (ticket_id, stage, corpus_id, input_hash, contract_version, state, completed_at) VALUES (%s, 'PARENT_ENRICHMENT', %s, %s, 'v', 'COMPLETE', now())",
                 ("tkt_rt_" + uuid.uuid4().hex[:12], corpus, ih))
    assert impl._enrichment_row_done(conn, ih) is False


def test_terminal_invalid_counts_only_on_a_live_parent(conn):
    corpus, doc, live, dead = _seed(conn)
    ih_live, ih_dead = "ih_" + uuid.uuid4().hex[:12], "ih_" + uuid.uuid4().hex[:12]
    _row(conn, parent=live, doc=doc, corpus=corpus, ih=ih_live, status="INVALID", error_class="ENRICH_HARD_CASE")
    _row(conn, parent=dead, doc=doc, corpus=corpus, ih=ih_dead, status="INVALID", error_class="ENRICH_HARD_CASE")
    assert impl._enrichment_row_done(conn, ih_live) is True       # three lanes rejected: terminal, stop retrying
    assert impl._enrichment_row_done(conn, ih_dead) is False


def test_persist_replaces_an_orphan_row_instead_of_answering_existing(conn):
    corpus, doc, live, dead = _seed(conn)
    ih = "ih_" + uuid.uuid4().hex[:12]
    _row(conn, parent=dead, doc=doc, corpus=corpus, ih=ih, status="READY")     # orphan under this identity
    cp = CompiledParent(parent_id=live, status="READY", source_hash="sh", source_child_ids=["c1"],
                        output=EnrichmentOutput(summary="s", children=[ChildGist(0, "g")], abstraction="a"),
                        child_ref_map={0: "c1"}, gist_coverage=1.0)
    res = persist_compiled_parent(conn, corpus_id=corpus, doc_id=doc, compiled=cp, input_hash=ih, provider="llm:test", model="m")
    assert res["status"] == "READY", res
    rows = conn.execute("SELECT parent_id, status FROM parent_enrichments WHERE input_hash=%s", (ih,)).fetchall()
    assert rows == [(live, "READY")], rows                          # orphan gone, new parent owns the identity
    # and a second persist on the live parent is the ordinary EXISTING no-op
    assert persist_compiled_parent(conn, corpus_id=corpus, doc_id=doc, compiled=cp, input_hash=ih, provider="llm:test", model="m")["status"] == "EXISTING"


def test_parent_alive_and_worker_skips_persisting_into_a_deleted_document(conn):
    corpus, doc, live, dead = _seed(conn)
    assert impl._parent_alive(conn, live) is True and impl._parent_alive(conn, dead) is False
    import inspect
    src = inspect.getsource(impl._do_enrichment)
    assert src.count("_parent_alive(_c, cp.parent_id)") == 2, "both persistence sites must refuse a dead parent"
    assert "ENRICH_PERSIST_SKIPPED_DOC_GONE" in src
    assert "_job_done(conn, \"PARENT_ENRICHMENT\"" not in src, "job state must not decide enrichment done-ness"
