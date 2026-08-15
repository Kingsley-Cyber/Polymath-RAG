"""R1B reconciliation: neural routing projections cannot silently
disappear (receipt-is-the-commit-point for routing kinds).

Self-contained: creates its own corpus via the shared intake writer
and the existing workers; no dependency on other suites' corpora.
Requires live stores (POLYMATH_INTEGRATION=1).
"""
from __future__ import annotations

import base64
import json
import os
import sys
from pathlib import Path

import pytest

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.environ.get("POLYMATH_INTEGRATION") != "1",
        reason="set POLYMATH_INTEGRATION=1 with live stores (make db-up)",
    ),
]

sys_path = str(Path(__file__).resolve().parents[2])
if sys_path not in sys.path:
    sys.path.insert(0, sys_path)

from polymath_shared.db import tx  # noqa: E402
from polymath_shared.intake_submission import canonical_intake_payload, submit_intake  # noqa: E402
from polymath_shared.identity import content_hash  # noqa: E402

CORPUS = "r1b-recon-corpus"

TEXT_A = ("# R1B Recon Document Alpha\n\nRetrieval plans combine summary routing with child "
          "evidence. Sufficiently long unique material about r1b reconciliation appears here.\n")
TEXT_B = ("# R1B Recon Document Beta\n\nFiltered deepening constrains child search to a parent "
          "section. Distinct beta material about r1b filters appears here.\n")


def _wipe():
    with tx() as conn:
        rids = [r[0] for r in conn.execute("SELECT run_id FROM runs WHERE corpus_id=%s", (CORPUS,)).fetchall()]
        for rid in rids:
            for t in ("stage_attempts", "artifacts", "receipts", "outbox_events"):
                conn.execute(f"DELETE FROM {t} WHERE run_id=%s", (rid,))
        docs = [r[0] for r in conn.execute("SELECT doc_id FROM documents WHERE corpus_id=%s", (CORPUS,)).fetchall()]
        if docs:
            conn.execute("DELETE FROM projection_receipts WHERE entity_id = ANY(%s)", (docs,))
        chunks = [r[0] for r in conn.execute(
            """SELECT ch.chunk_id FROM chunks ch JOIN documents d ON d.doc_id=ch.doc_id
               WHERE d.corpus_id=%s""", (CORPUS,)).fetchall()]
        if chunks:
            conn.execute("DELETE FROM projection_receipts WHERE entity_id = ANY(%s)", (chunks,))
        conn.execute("DELETE FROM retrieval_summaries WHERE corpus_id=%s", (CORPUS,))
        conn.execute("DELETE FROM runs WHERE corpus_id=%s", (CORPUS,))
        conn.execute("DELETE FROM documents WHERE corpus_id=%s", (CORPUS,))
        conn.execute("DELETE FROM corpora WHERE corpus_id=%s", (CORPUS,))
    # disposable projections: hash + neural collections
    from qdrant_client import QdrantClient
    from polymath_shared.embedding_contracts import HASH_EMBED_CONTRACT, NEURAL_EMBED_CONTRACT
    from polymath_shared.projection_contracts import qdrant_collection_name
    from polymath_shared.settings import get_settings

    client = QdrantClient(url=get_settings().stores.qdrant_url)
    try:
        for contract in (HASH_EMBED_CONTRACT, NEURAL_EMBED_CONTRACT):
            name = qdrant_collection_name(CORPUS, contract.contract_id)
            if client.collection_exists(name):
                client.delete_collection(name)
    finally:
        client.close()


def _submit_and_drive(text: str, name: str) -> str:
    from workers.intake_worker import process_event as intake_event
    from workers.profile_worker import process_event as profile_event
    from workers.project_qdrant_worker import process_event as qdrant_event

    payload = canonical_intake_payload(
        CORPUS, name, "text/markdown",
        base64.b64encode(text.encode()).decode(),
    )
    with tx() as conn:
        res = submit_intake(conn, payload)
    rid = res["run_id"]
    with tx() as conn:
        intake_event(conn, {"run_id": rid, "payload": payload, "idempotency_key": content_hash({"i": rid})[:16]})
    with tx() as conn:
        conn.execute(
            """INSERT INTO stage_attempts (run_id, stage, contract_hash, started_at, completed_at, outcome)
               VALUES (%s,'extract',%s,now(),now(),'ok') ON CONFLICT DO NOTHING""",
            (rid, content_hash({"s": "extract", "r1b": "recon"})),
        )
    with tx() as conn:
        profile_event(conn, {"run_id": rid, "payload": {"run_id": rid}, "idempotency_key": "r1b-p"})
    with tx() as conn:
        qdrant_event(conn, {"run_id": rid, "payload": {"run_id": rid}, "idempotency_key": "r1b-q"})
    with tx() as conn:
        conn.execute("UPDATE runs SET status='query_ready' WHERE run_id=%s", (rid,))
    return rid


def test_routing_receipts_converge_and_reconstruct():
    from control.census import _missing_projection_receipts

    _wipe()
    r1 = _submit_and_drive(TEXT_A, "alpha.md")
    r2 = _submit_and_drive(TEXT_B, "beta.md")

    # converged state: no missing receipts of any kind (chunks + routing)
    with tx() as conn:
        for rid in (r1, r2):
            assert _missing_projection_receipts(conn, rid, "project_qdrant") == []

    # damage: supersede one routing receipt (store loss equivalent)
    with tx() as conn:
        row = conn.execute(
            """SELECT pr.entity_id FROM projection_receipts pr
                JOIN retrieval_summaries rs ON rs.summary_id = pr.entity_id
               WHERE pr.projection='qdrant' AND pr.entity_kind='routing_document_summary'
                 AND pr.active AND rs.corpus_id=%s LIMIT 1""",
            (CORPUS,)).fetchone()
        assert row, "no routing receipts to damage"
        victim = row[0]
        conn.execute(
            """UPDATE projection_receipts SET active=FALSE
                WHERE projection='qdrant' AND entity_kind='routing_document_summary'
                  AND entity_id=%s""", (victim,))

    # census sees the gap
    with tx() as conn:
        gaps = _missing_projection_receipts(conn, r1, "project_qdrant")
        assert victim in gaps, "census did not detect the routing receipt loss"

    # re-drive the projector -> receipt restored -> census clean
    from workers.project_qdrant_worker import process_event as _q
    with tx() as conn:
        _q(conn, {"run_id": r1, "payload": {"run_id": r1}, "idempotency_key": "r1b-recon"})
    with tx() as conn:
        assert _missing_projection_receipts(conn, r1, "project_qdrant") == []

    # verify converges with an empty routing report
    from workers.verify_worker import reconcile_routing_qdrant
    with tx() as conn:
        report = reconcile_routing_qdrant(conn, CORPUS)
        assert report["missing_in_store"] == [], report
        assert report["missing_receipts"] == [], report
    _wipe()
