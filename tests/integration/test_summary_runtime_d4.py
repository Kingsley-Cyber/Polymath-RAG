"""SUMMARY RUNTIME D4: corpus mapping — weighting, policy, idempotency."""
from __future__ import annotations

import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import psycopg

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))

DSN = "postgresql://polymath:polymath-dev@127.0.0.1:5432/polymath"
CORPUS = "summary-d4-test"


def _seed_doc(conn, sid, ents, cpts, methods):
    conn.execute(
        """INSERT INTO document_summaries (summary_id, document_id,
           corpus_id, artifact_hash, contract_version,
           created_by_worker, source_ids, major_entities,
           major_concepts, methods, summary)
           VALUES (%s,%s,%s,%s,'admission-harbor-v2','w','{}',
                   %s::text[], %s::text[], %s::text[], 's')""",
        (sid, "doc_" + sid, CORPUS, "h_" + sid, ents, cpts, methods))


def _reset_corpus_tables():
    import psycopg

    with psycopg.connect(DSN) as c:
        for t in ("summary_artifacts", "document_summaries",
                  "corpus_summaries", "summary_jobs"):
            c.execute("DELETE FROM " + t + " WHERE corpus_id=%s",
                      (CORPUS,))


def test_weighting_prefers_document_spread_and_fact_degree():
    from polymath_shared.corpus_mapping import build_corpus_map
    rows = [
        {"summary_id": "d1", "major_entities": ["BERT"],
         "major_concepts": ["attention"], "methods": ["trained_on"]},
        {"summary_id": "d2", "major_entities": ["BERT", "GPT"],
         "major_concepts": ["attention"], "methods": []},
        {"summary_id": "d3", "major_entities": ["GPT"],
         "major_concepts": [], "methods": []},
    ]
    cmap = build_corpus_map(corpus_id="c", document_summaries=rows,
                            fact_degrees={"BERT": 74})
    ent_w = {e["item"]: e["weight"] for e in cmap["entities"]}
    assert ent_w["BERT"] > ent_w["GPT"]  # spread + fact_degree boost
    att = [c for c in cmap["concepts"] if c["item"] == "attention"][0]
    assert att["document_spread"] == 2
    assert att["source_document_summary_ids"] == ["d1", "d2"]
    assert cmap["predicates"][0]["item"] == "trained_on"
    assert cmap["document_clusters"]


def test_refresh_policy_gates():
    from polymath_shared.corpus_mapping import corpus_refresh_policy
    now = datetime.now(timezone.utc)
    ok, why = corpus_refresh_policy(completed_documents=100,
                                    last_run_at=None, now=now)
    assert ok and why == "document_count_threshold"
    ok, why = corpus_refresh_policy(completed_documents=5,
                                    last_run_at=None, now=now, force=True)
    assert ok and why == "manual_rebuild"
    ok, why = corpus_refresh_policy(completed_documents=5,
                                    last_run_at=now - timedelta(minutes=40),
                                    now=now)
    assert ok and why == "scheduled_refresh"
    ok, why = corpus_refresh_policy(completed_documents=5,
                                    last_run_at=now, now=now)
    assert not ok and why == "policy_deferred"


def test_corpus_ticket_lifecycle_and_idempotency():
    from polymath_shared.corpus_mapping import run_corpus_mapping_ticket
    with psycopg.connect(DSN) as conn:
        _seed_doc(conn, "s1_" + uuid.uuid4().hex[:6], ["BERT"],
                  ["attention"], ["trained_on"])
        conn.commit()
    ticket = "tkt_" + uuid.uuid4().hex
    ih = "in_" + uuid.uuid4().hex
    with psycopg.connect(DSN) as conn:
        conn.execute("""INSERT INTO summary_jobs (ticket_id, stage,
            corpus_id, input_hash, contract_version)
            VALUES (%s,'CORPUS_MAPPING',%s,%s,'admission-harbor-v2')""",
            (ticket, CORPUS, ih))
        r = run_corpus_mapping_ticket(
            conn, ticket_id=ticket, corpus_id=CORPUS, input_hash=ih,
            contract_version="admission-harbor-v2", worker_id="d4w",
            fact_degrees={"BERT": 5})
        assert r["status"] == "COMPLETE", r

        conn.execute("""INSERT INTO summary_jobs (ticket_id, stage,
            corpus_id, input_hash, contract_version)
            VALUES (%s,'CORPUS_MAPPING',%s,%s,'admission-harbor-v2')""",
            (ticket + "_b", CORPUS, ih))
        r2 = run_corpus_mapping_ticket(
            conn, ticket_id=ticket + "_b", corpus_id=CORPUS,
            input_hash=ih, contract_version="admission-harbor-v2",
            worker_id="d4w")
        assert r2["status"] == "EXISTING"

    # cleanup
    with psycopg.connect(DSN) as conn:
        for t in ("summary_artifacts", "corpus_summaries",
                  "document_summaries", "summary_jobs"):
            conn.execute(f"DELETE FROM {t} WHERE corpus_id=%s", (CORPUS,))
        conn.commit()


@pytest.fixture(autouse=True)
def _isolated_corpus():
    _reset_corpus_tables()
    yield
