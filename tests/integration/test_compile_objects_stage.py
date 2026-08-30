"""COMPILE-OBJECTS-STAGE-V1 (§11, register 11.4) — DB-backed.

NOTE: stage_transaction COMMITS (receipts are the commit point), so the
rollback fixture cannot contain this test — ids are per-run unique and
the fixture deletes its rows afterwards, committed.

The deterministic concept/procedure compilers as their own stage: given a
run whose document has child chunks and admitted mentions, process_event
must write concept artifacts, stage attempt + receipt, and an artifact
carrying opportunity accounting — with no provider anywhere in sight.
"""
from __future__ import annotations

import pathlib
import sys

import psycopg
import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))
sys.path.insert(0, str(ROOT / "workers"))

from polymath_shared.settings import get_settings  # noqa: E402
from workers.compile_objects_worker import process_event  # noqa: E402

TEXT = ("A firewall is a network security device that filters traffic. "
        "An intrusion detection system is a monitor that flags anomalous "
        "events. Vulnerability scanning is the process of enumerating "
        "weaknesses in hosts.")


@pytest.fixture
def conn():
    c = psycopg.connect(get_settings().postgres.dsn, connect_timeout=5)
    try:
        yield c
    finally:
        c.rollback()
        c.close()


def test_stage_compiles_objects_with_receipts(conn) -> None:
    import uuid
    tag = uuid.uuid4().hex[:10]
    corpus, run, doc = (f"compile-test-{tag}", f"run_compile_test_{tag}",
                        f"doc_compile_test_{tag}")
    conn.execute("INSERT INTO corpora (corpus_id, name, config_hash) VALUES (%s,%s,'t') "
                 "ON CONFLICT DO NOTHING", (corpus, corpus))
    conn.execute("INSERT INTO runs (run_id, corpus_id, status, metadata) "
                 "VALUES (%s,%s,'reconciling','{}')", (run, corpus))
    conn.execute("INSERT INTO documents (doc_id, corpus_id, source_name, source_hash, byte_length, "
                 "media_type, content_hash, profile) "
                 "VALUES (%s,%s,'compile-test.md','h_compile_test',%s,'text/markdown','h_compile_test','{}')",
                 (doc, corpus, len(TEXT)))
    conn.execute("INSERT INTO document_processing_runs (run_id, document_id, pipeline_version, artifact_hash, status) "
                 "VALUES (%s,%s,'t','t','ok')", (run, doc))
    chunk = f"chunk_compile_{tag}"
    conn.execute("INSERT INTO chunks (chunk_id, doc_id, tier, chunk_index, text, summary, char_start, char_end) "
                 "VALUES (%s,%s,'child',0,%s,'',0,%s)",
                 (chunk, doc, TEXT, len(TEXT)))
    for i, s in enumerate(("firewall", "intrusion detection system")):
        start = TEXT.index(s)
        conn.execute(
            """INSERT INTO mentions (mention_id, corpus_id, doc_id, chunk_id, char_start,
                   char_end, surface, normalized_surface, core_type, gliner_score,
                   extractor_version, admission_class, entity_id)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,'Concept',1.0,'t','CORPUS_SCOPED',NULL)""",
            (f"mention_compile_{tag}_{i}", corpus, doc, chunk, start,
             start + len(s), s, s))

    process_event(conn, {"run_id": run, "event_type": "compile_objects.v1",
                         "payload": {"run_id": run}})

    att = conn.execute(
        "SELECT outcome FROM stage_attempts WHERE run_id=%s AND stage='compile_objects'",
        (run,)).fetchall()
    assert att == [("ok",)]
    rec = conn.execute(
        "SELECT status FROM receipts WHERE run_id=%s AND stage='compile_objects'",
        (run,)).fetchall()
    assert rec == [("committed",)]
    art = conn.execute(
        "SELECT payload FROM artifacts WHERE run_id=%s AND stage='compile_objects'",
        (run,)).fetchone()[0]
    assert art["contract"] == "compile-objects-v1" and art["documents"] == 1
    doc_counts = art["per_document"][doc]
    assert "concept_opportunities" in doc_counts and "procedures" in doc_counts
    # three definitional sentences: the concept compiler must fire
    assert art["concepts"] > 0
    n = conn.execute("SELECT count(*) FROM concept_artifacts WHERE corpus_id=%s",
                     (corpus,)).fetchone()[0]
    assert n == art["concepts"]
    # stage_transaction committed; remove this test's durable rows
    for sql in (
        "DELETE FROM concept_artifacts WHERE corpus_id=%s",
        "DELETE FROM procedure_artifacts WHERE corpus_id=%s",
        "DELETE FROM knowledge_lane_attempts WHERE corpus_id=%s",
        "DELETE FROM mentions WHERE corpus_id=%s",
    ):
        conn.execute(sql, (corpus,))
    for sql in (
        "DELETE FROM artifacts WHERE run_id=%s",
        "DELETE FROM receipts WHERE run_id=%s",
        "DELETE FROM stage_attempts WHERE run_id=%s",
        "DELETE FROM document_processing_runs WHERE run_id=%s",
    ):
        conn.execute(sql, (run,))
    conn.execute("DELETE FROM chunks WHERE doc_id=%s", (doc,))
    conn.execute("DELETE FROM documents WHERE doc_id=%s", (doc,))
    conn.execute("DELETE FROM runs WHERE run_id=%s", (run,))
    conn.execute("DELETE FROM corpora WHERE corpus_id=%s", (corpus,))
    conn.commit()
