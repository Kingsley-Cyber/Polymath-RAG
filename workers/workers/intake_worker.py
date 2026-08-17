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
from polymath_shared.settings import get_settings
from polymath_shared.receipts import (
    StageFailed,
    claim_events,
    stage_contract_hash,
    stage_transaction,
)
from workers.chunker import materialize_chunks, plan_document
from workers.summarizer import summarize
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

    with stage_transaction(
        conn, run_id=run_id, stage=STAGE, contract_hash=contract()
    ) as writer:
        # I0: native document materialization (ADR 0010). Deterministic,
        # per-format, fail-loud: a materialization failure commits a
        # FAILURE receipt (never a silent empty document). TXT/Markdown
        # go through the SAME byte normalization as before — the
        # Q1-qualified path is unchanged.
        from polymath_shared.materializer import MaterializationError, materialize

        try:
            materialization = materialize(raw, media_type, source_name)
        except MaterializationError as exc:
            raise RuntimeError(
                f"materialization failed for {source_name}: {type(exc).__name__}: {exc}"
            ) from exc
        text = materialization.text

        profile = route_document(source_name, text[:4000])
        chunker_provider = get_settings().worker.chunker
        if chunker_provider not in ("legacy_v1", "semantic_v2"):
            raise ValueError(f"unknown chunking provider: {chunker_provider}")
        if chunker_provider == "semantic_v2":
            # SEMANTIC-CHUNKING-V2 (chunk-contract-v2): structure-
            # constrained semantic chunking; headings NEVER enter chunk
            # body text. Chonkie is a library dependency — Polymath
            # owns orchestration, offsets, and state.
            from workers.semantic_chunker import SemanticEmbeddingCache, semantic_chunk_rows

            chunks = semantic_chunk_rows(
                text, doc_id, cache=SemanticEmbeddingCache())
        else:
            plan = plan_document(text, doc_id, **CHUNK_FROZEN_PARAMS)
            chunks = materialize_chunks(plan)

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
                                   byte_length, content_hash, profile,
                                   source_hash, materialization, source_map)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (doc_id) DO NOTHING
            """,
            (doc_id, corpus_id, source_name, media_type,
             len(normalized), content_hash, json.dumps(profile.model_dump()),
             materialization.original_sha256,
             json.dumps({
                 "parser": materialization.parser,
                 "parser_version": materialization.parser_version,
                 "format": materialization.format,
                 "normalized_text_sha256": materialization.normalized_text_sha256,
                 "original_byte_length": materialization.original_byte_length,
                 "warnings": materialization.warnings,
             }),
             json.dumps(materialization.source_map)),
        )

        # Parents first, then children: children carry parent_id foreign
        # keys, so the parent rows must exist before the FK is checked.
        for row in chunks:
            if row["tier"] != "parent":
                continue
            conn.execute(
                """
                INSERT INTO chunks (chunk_id, doc_id, parent_id, chunk_index, tier,
                                    text, summary, char_start, char_end,
                                    chunk_contract_version, provider, heading_path, token_count)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (chunk_id) DO NOTHING
                """,
                (row["chunk_id"], row["doc_id"], row["parent_id"], row["chunk_index"],
                 row["tier"], row["text"], row["summary"], row["char_start"], row["char_end"],
                 row.get("chunk_contract_version"), row.get("provider"),
                 json.dumps(row["heading_path"]) if row.get("heading_path") else None,
                 row.get("token_count")),
            )
        for row in chunks:
            if row["tier"] != "child":
                continue
            conn.execute(
                """
                INSERT INTO chunks (chunk_id, doc_id, parent_id, chunk_index, tier,
                                    text, summary, char_start, char_end,
                                    chunk_contract_version, provider, heading_path, token_count)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (chunk_id) DO NOTHING
                """,
                (row["chunk_id"], row["doc_id"], row["parent_id"], row["chunk_index"],
                 row["tier"], row["text"], row["summary"], row["char_start"], row["char_end"],
                 row.get("chunk_contract_version"), row.get("provider"),
                 json.dumps(row["heading_path"]) if row.get("heading_path") else None,
                 row.get("token_count")),
            )

        children = [r for r in chunks if r["tier"] == "child"]
        parents = [r for r in chunks if r["tier"] == "parent"]
        routing_card = {
            "doc_id": doc_id,
            "source_name": source_name,
            "profile": profile.model_dump(),
            "document_summary": summarize(text, max_sentences=6, max_chars=1600),
            "child_chunks": len(children),
            "parent_chunks": len(parents),
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
    from polymath_shared.worker_runtime import run_worker

    run_worker('intake', [EVENT_TYPE], process_event,
               poll_interval_s=poll_interval_s, batch_size=batch_size)

if __name__ == "__main__":
    run_forever()
