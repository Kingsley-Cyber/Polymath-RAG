"""intake worker: parse -> chunk -> profile. One durable stage.

Consumes `intake.v1` outbox events. Everything this stage produces —
document row, chunk rows, routing card artifact, receipt, status
transition, and the `chunked.v1` outbox event — commits in ONE Postgres
transaction (AGENTS.md rule 5). Replaying an event is a no-op: every row
is content-hashed and lands on the same primary keys.

No LLM anywhere in this stage: chunking is sentence-aligned greedy
packing, summaries are deterministic extractive (workers.summarizer),
profiles are keyword/filename priors (workers.profile_router).
"""
from __future__ import annotations

import base64
import hashlib
import json
import logging
import time

import psycopg
from psycopg import Connection

from polymath_shared.db import tx
from polymath_shared.identity import document_id, normalize_document_bytes
from polymath_shared.logging import configure_logging
from polymath_shared.receipts import (
    StageFailed,
    claim_events,
    stage_contract_hash,
    stage_transaction,
)
from workers.chunker import materialize_chunks, plan_document
from workers.profile_router import route_document

STAGE = "intake"
EVENT_TYPE = "intake.v1"
NEXT_EVENT_TYPE = "chunked.v1"

CHUNK_FROZEN_PARAMS = {
    "child_target_chars": 1200,
    "parent_fanout": 4,
}
NORMALIZATION = {"strip_bom": True, "normalize_crlf": True, "nfc": True}
ROUTER_VERSION = "1.0.0"

log = logging.getLogger("intake")


def contract() -> str:
    return stage_contract_hash(STAGE, {
        "chunk_frozen": CHUNK_FROZEN_PARAMS,
        "normalization": NORMALIZATION,
        "router_version": ROUTER_VERSION,
    })


def process_event(conn: Connection, event: dict) -> None:
    payload = event["payload"]
    run_id = event["run_id"]
    corpus_id = payload["corpus_id"]
    source_name = payload["source_name"]
    media_type = payload["media_type"]

    raw = base64.b64decode(payload["content_b64"])
    normalized = normalize_document_bytes(
        raw, strip_bom=NORMALIZATION["strip_bom"], normalize_crlf=NORMALIZATION["normalize_crlf"]
    )
    doc_id = document_id(normalized)
    content_hash = hashlib.sha256(normalized).hexdigest()

    try:
        text = normalized.decode("utf-8")
    except UnicodeDecodeError:
        text = ""

    profile = route_document(source_name, text[:4000])
    plan = plan_document(text, doc_id, **CHUNK_FROZEN_PARAMS)
    chunks = materialize_chunks(plan)

    with stage_transaction(
        conn, run_id=run_id, stage=STAGE, contract_hash=contract()
    ) as writer:
        conn.execute(
            """
            INSERT INTO corpora (corpus_id, name, config_hash, profile)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (corpus_id) DO NOTHING
            """,
            (corpus_id, corpus_id, contract(), json.dumps(profile.model_dump())),
        )
        conn.execute(
            """
            INSERT INTO documents (doc_id, corpus_id, source_name, media_type,
                                   byte_length, content_hash, profile)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (doc_id) DO NOTHING
            """,
            (doc_id, corpus_id, source_name, media_type,
             len(normalized), content_hash, json.dumps(profile.model_dump())),
        )

        # Parents first, then children: children carry parent_id foreign
        # keys, so the parent rows must exist before the FK is checked.
        for row in chunks:
            if row["tier"] != "parent":
                continue
            conn.execute(
                """
                INSERT INTO chunks (chunk_id, doc_id, parent_id, chunk_index, tier,
                                    text, summary, char_start, char_end)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (chunk_id) DO NOTHING
                """,
                (row["chunk_id"], row["doc_id"], row["parent_id"], row["chunk_index"],
                 row["tier"], row["text"], row["summary"], row["char_start"], row["char_end"]),
            )
        for row in chunks:
            if row["tier"] != "child":
                continue
            conn.execute(
                """
                INSERT INTO chunks (chunk_id, doc_id, parent_id, chunk_index, tier,
                                    text, summary, char_start, char_end)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (chunk_id) DO NOTHING
                """,
                (row["chunk_id"], row["doc_id"], row["parent_id"], row["chunk_index"],
                 row["tier"], row["text"], row["summary"], row["char_start"], row["char_end"]),
            )

        routing_card = {
            "doc_id": doc_id,
            "source_name": source_name,
            "profile": profile.model_dump(),
            "document_summary": plan.document_summary,
            "child_chunks": len(plan.children),
            "parent_chunks": len(plan.parents),
        }
        writer.artifact({"routing_card": routing_card})
        writer.outbox(NEXT_EVENT_TYPE, {
            "run_id": run_id,
            "corpus_id": corpus_id,
            "doc_id": doc_id,
            "doc_content": payload["content_b64"],
            "profile": profile.model_dump(),
        })
        writer.run_status("reconciling")


def run_forever(poll_interval_s: float = 2.0, batch_size: int = 8) -> None:
    configure_logging("worker-intake")
    while True:
        try:
            with tx() as conn:
                events = claim_events(conn, [EVENT_TYPE], batch_size)
                if events:
                    for event in events:
                        try:
                            process_event(conn, event)
                            log.info("intake event processed", extra={
                                "run_id": event["run_id"], "stage": STAGE,
                                "attempt_id": event["idempotency_key"][:16],
                            })
                        except StageFailed as exc:
                            log.error(str(exc), extra={
                                "run_id": event["run_id"], "stage": STAGE,
                                "error_code": "stage_failed",
                            })
        except psycopg.errors.OperationalError as exc:
            log.warning("postgres unavailable; backing off", extra={"error_code": "pg_unavailable"})
        except Exception as exc:
            log.exception("intake processing failed", extra={"error_code": type(exc).__name__})
        time.sleep(poll_interval_s)


if __name__ == "__main__":
    run_forever()
