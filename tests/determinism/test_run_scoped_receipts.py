"""RUN-SCOPED-RECEIPTS-V1: a document's own downstream stages are gated on
ITS chunks' projection receipts; only corpus-level stages (corpus_summary,
vocabulary) wait for the whole corpus. Found by STALL-TRACER on 2026-09-03:
document B (query_ready) held `parent_summary` PENDING for > 5 min because
document C of the same corpus was still extracting — the receipt predicate
was a corpus-wide anti-join for every stage. Real Postgres, rolled back."""
import pathlib
import sys
import uuid

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))
sys.path.insert(0, str(ROOT / "control"))

import psycopg
import pytest

import control.tickets as T
from control.stall_tracer import diagnose_pending

DSN = "postgresql://polymath:polymath-dev@127.0.0.1:5432/polymath"


@pytest.fixture()
def conn():
    with psycopg.connect(DSN, autocommit=False) as c:
        yield c
        c.rollback()


def _doc(conn, corpus, name, n_chunks, with_receipts):
    did = "doc_probe_" + uuid.uuid4().hex[:16]
    conn.execute("""INSERT INTO documents (doc_id, corpus_id, source_name, media_type, byte_length, content_hash)
                    VALUES (%s,%s,%s,'text/markdown',10,%s)""", (did, corpus, name, "h" + uuid.uuid4().hex[:10]))
    for i in range(n_chunks):
        cid = "chunk_probe_" + uuid.uuid4().hex[:16]
        conn.execute("""INSERT INTO chunks (chunk_id, doc_id, chunk_index, text, tier, char_start, char_end)
                        VALUES (%s,%s,%s,'t','child',0,1)""", (cid, did, i))
        if with_receipts:
            conn.execute("""INSERT INTO projection_receipts (projection, entity_kind, entity_id, receipt_hash, active)
                            VALUES ('qdrant','chunk',%s,'r',true)""", (cid,))
    return did


def _run(conn, corpus, source_name):
    rid = "run_probe_" + uuid.uuid4().hex[:16]
    conn.execute("""INSERT INTO runs (run_id, corpus_id, status, metadata)
                    VALUES (%s,%s,'reconciling', jsonb_build_object('source_name', %s::text))""",
                 (rid, corpus, source_name))
    return rid


def test_projected_document_is_present_while_a_sibling_is_still_missing(conn, monkeypatch):
    monkeypatch.setattr(T, "_verdict_get", lambda key: None)      # no cross-tick cache in the probe
    monkeypatch.setattr(T, "_verdict_put", lambda key, state: None)
    corpus = "probe-rsr-" + uuid.uuid4().hex[:8]
    conn.execute("INSERT INTO corpora (corpus_id, name, config_hash, purpose) VALUES (%s,%s,'p','probe')", (corpus, corpus))
    _doc(conn, corpus, "B.md", 3, with_receipts=True)
    _doc(conn, corpus, "C.md", 3, with_receipts=False)
    run_b = _run(conn, corpus, "B.md")
    run_c = _run(conn, corpus, "C.md")
    assert T._run_doc_ids(conn, run_b) and T._run_doc_ids(conn, run_c)
    # B's own chunks are all receipted -> present for B's per-document stages
    assert T._receipts_present(conn, run_b, corpus, "qdrant", scope="run") is True
    # the corpus as a whole is not (C is unprojected) -> corpus-level stages still wait
    assert T._receipts_present(conn, run_b, corpus, "qdrant", scope="corpus") is False
    assert T._receipts_present(conn, run_c, corpus, "qdrant", scope="run") is False
    # legacy run without a source_name falls back to corpus scope (unchanged behaviour)
    legacy = "run_probe_" + uuid.uuid4().hex[:16]
    conn.execute("INSERT INTO runs (run_id, corpus_id, status, metadata) VALUES (%s,%s,'reconciling','{}'::jsonb)",
                 (legacy, corpus))
    assert T._run_doc_ids(conn, legacy) == []
    assert T._receipts_present(conn, legacy, corpus, "qdrant", scope="run") is False


def test_corpus_stages_are_exactly_the_two_barrier_stages():
    assert T.CORPUS_STAGES == ("corpus_summary", "vocabulary")
    assert T.receipt_scope_for("parent_summary") == "run"
    assert T.receipt_scope_for("document_summary") == "run"
    assert T.receipt_scope_for("corpus_summary") == "corpus"
    assert T.receipt_scope_for("vocabulary") == "corpus"


def test_advance_and_tracer_use_the_run_scope_for_per_document_stages():
    src = (ROOT / "control" / "control" / "tickets.py").read_text()
    body = src[src.index("def _try_advance_one("):src.index("def _corpus_of(")]
    assert "receipt_scope_for(stage)" in body, "advance must pick the scope from the stage being advanced"
    tracer = (ROOT / "control" / "control" / "stall_tracer.py").read_text()
    assert "receipt_scope_for(stage)" in tracer, "tracer must diagnose with the scheduler's own scope"


def test_tracer_traces_a_per_document_stage_blocked_on_its_own_receipts_even_with_live_siblings(conn, monkeypatch):
    """The V1.2 sibling exemption is for CORPUS stages only: a per-document
    stage missing its own document's receipts is a scheduler/projection
    defect and must be traced whatever the siblings are doing."""
    monkeypatch.setattr(T, "_stage_attempt_ok", lambda *a, **k: True)
    monkeypatch.setattr(T, "_artifacts_present", lambda *a, **k: True)
    monkeypatch.setattr(T, "_receipts_present", lambda *a, **k: False)
    from control.stall_tracer import _live_sibling_runs
    corpus = "probe-rsr-" + uuid.uuid4().hex[:8]
    conn.execute("INSERT INTO corpora (corpus_id, name, config_hash, purpose) VALUES (%s,%s,'p','probe')", (corpus, corpus))
    run_b = _run(conn, corpus, "B.md")
    run_c = _run(conn, corpus, "C.md")
    conn.execute("""INSERT INTO stage_tickets (ticket_id, run_id, corpus_id, stage, event_type, status, updated_at)
                    VALUES (%s,%s,%s,'extract','chunked.v1','ready', now())""",
                 ("tkt_probe_" + uuid.uuid4().hex[:16], run_c, corpus))
    row = {"run_id": run_b, "corpus_id": corpus, "stage": "parent_summary"}
    assert _live_sibling_runs(conn, row, 180) == [run_c]
    diag, detail = diagnose_pending(conn, row, {}, threshold_s=180)
    assert diag == "PENDING_ADVANCE_BLOCKED" and detail["missing"] == "receipts" and detail["scope"] == "run"
    # the same situation on a CORPUS stage is waiting on live sibling work -> not traced
    assert diagnose_pending(conn, {**row, "stage": "corpus_summary"}, {}, threshold_s=180) is None
