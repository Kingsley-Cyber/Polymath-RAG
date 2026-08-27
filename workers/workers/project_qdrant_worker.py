"""Qdrant projector: chunks -> vector points. A durable projection stage.

Consumes `extracted.v1` outbox events. Projects EVERY chunk of the run's
documents (children and parents) into the collection
`polymath_<corpus_hash>_<embedding_contract>`.

Idempotency contract (PLAN Phase F):

  - point ids are the source chunk ids — Qdrant never invents identity;
  - payload carries corpus_id, doc_id, parent_id, content_hash,
    embedding_contract — everything needed to rebuild;
  - the Postgres projection receipt commits AFTER the Qdrant write, in
    the stage transaction: receipts are the commit point, Qdrant writes
    are re-drivable (a crash between the two leaves an orphan point
    that VERIFY_PROJECTIONS detects, acceptance test 7).

The vector database never decides whether a chunk exists.
"""
from __future__ import annotations

import json
import logging
import os
import time

import psycopg
from psycopg import Connection
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

from polymath_shared.db import tx
from polymath_shared.logging import configure_logging
from polymath_shared.projection_contracts import (
    KIND_CHUNK,
    PROJECTION_QDRANT,
    embed,
    projection_id,
    qdrant_collection_name,
    qdrant_point_uuid,
    receipt_hash,
)
from polymath_shared.receipts import (
    StageFailed,
    claim_events,
    record_projection_attempt,
    stage_contract_hash,
    stage_transaction,
)
from polymath_shared.settings import get_settings

STAGE = "project_qdrant"
EVENT_TYPE = "project_qdrant.v1"

CONTRACT_VERSION = "1.1.0"

log = logging.getLogger("project-qdrant")


def _active_contract():
    """Resolve the active embedding contract through the shared resolver
    (friendly id or derived contract id)."""
    from polymath_shared.embedding_contracts import active_contract

    return active_contract()


def _corpus_contract(conn, corpus_id: str):
    """EMBEDDING-CONTRACT-REGISTRY-V1 (G1 owner decision): the contract
    pinned for this corpus in Postgres is the retrieval authority. A
    projection must never run under a different contract than the
    vectors already stored for that corpus. Falls back to the settings
    default only when the corpus row predates the registry."""
    from polymath_shared.embedding_contracts import (
        CONTRACTS,
        SHORT_NAMES,
        active_contract,
    )

    row = conn.execute(
        "SELECT embedding_contract_id FROM corpora WHERE corpus_id=%s",
        (corpus_id,),
    ).fetchone()
    pinned = row[0] if row else None
    if not pinned:
        return active_contract()
    resolved = SHORT_NAMES.get(pinned) or CONTRACTS.get(pinned)
    if resolved is None:
        raise ValueError(
            f"corpus {corpus_id!r} pins unknown embedding contract "
            f"{pinned!r}")
    return resolved


EMBED_BATCH = 16  # measured optimum: 6.9 texts/s vs 3.5 at 32 (saturation matrix 2026-08-27; contract cap is 32)

# PROJECTION-TELEMETRY-V1: per-ticket attribution. project_qdrant wall
# time was measured ~95% embedding, but the stage name hid that — every
# second must be attributable to embed / qdrant / receipts / lookup.
_TELEMETRY: dict = {}


def _tel_reset() -> None:
    _TELEMETRY.clear()
    _TELEMETRY.update({
        "receipt_lookup_ms": 0.0, "embed_ms": 0.0, "embed_calls": 0,
        "embed_texts": 0, "qdrant_upsert_ms": 0.0, "qdrant_batches": 0,
        "receipt_persist_ms": 0.0, "checkpoints": 0,
        "representations_total": 0, "representations_already_current": 0,
        "started": time.perf_counter(),
    })


def _tel(key: str, dt_ms: float = 0.0, n: int = 0) -> None:
    if not _TELEMETRY:
        return
    if dt_ms:
        _TELEMETRY[key] = _TELEMETRY.get(key, 0.0) + dt_ms
    if n:
        _TELEMETRY[key] = _TELEMETRY.get(key, 0) + n


def _embed_texts(contract, texts: list[str]) -> list[list[float]]:
    """Embed under the active contract: local fn or the embedder sidecar.

    Batched: a book-sized run (~700+ chunks) in one sidecar call exceeded
    the HTTP client timeout ("timed out", project_qdrant stage failure —
    same defect class as the syntax 512-cap). Batching is transport only:
    same texts, same contract, same vectors, same order.
    """
    if contract.embed_fn is not None:
        return [contract.embed(text, "child_chunk") for text in texts]
    from polymath_shared.clients import EmbedderClient

    client = EmbedderClient()
    try:
        client.verify_pin()
        out: list[list[float]] = []
        for i in range(0, len(texts), EMBED_BATCH):
            _t0 = time.perf_counter()
            out.extend(client.embed(texts[i:i + EMBED_BATCH],
                                    "child_chunk")["vectors"])
            _tel("embed_ms", (time.perf_counter() - _t0) * 1000)
            _tel("embed_calls", n=1)
            _tel("embed_texts", n=len(texts[i:i + EMBED_BATCH]))
        return out
    finally:
        client.close()


def _collection_exists(client: QdrantClient, name: str) -> bool:
    try:
        client.get_collection(name)
        return True
    except Exception:
        return False


def _ensure_collection(client: QdrantClient, name: str, dim: int) -> None:
    if _collection_exists(client, name):
        return
    client.create_collection(
        collection_name=name,
        vectors_config=VectorParams(size=dim, distance=Distance.COSINE),
    )


def _chunks_for_run(conn: Connection, run_id: str) -> list[dict]:
    rows = conn.execute(
        """
        SELECT c.chunk_id, c.doc_id, c.parent_id, c.chunk_index, c.tier,
               c.text, c.summary, d.corpus_id
          FROM chunks c
          JOIN documents d ON d.doc_id = c.doc_id
          JOIN runs r ON r.corpus_id = d.corpus_id
         WHERE r.run_id = %s
         ORDER BY c.chunk_index
        """,
        (run_id,),
    ).fetchall()
    return [
        {
            "chunk_id": row[0],
            "doc_id": row[1],
            "parent_id": row[2],
            "chunk_index": row[3],
            "tier": row[4],
            "text": row[5],
            "summary": row[6],
            "corpus_id": row[7],
        }
        for row in rows
    ]


UPSERT_BATCH = 128

#: Qdrant read budget. Indexing a batch while the host is also running
#: GPU extraction routinely outlives a 60s client timeout, and the bare
#: "timed out" that produced was the last real cause of failed
#: projections once the lease defect stopped masking it. Batching bounds
#: how much work one call carries; this bounds how long we wait for it.
QDRANT_TIMEOUT_S = 300


def _upsert_batched(client: QdrantClient, collection: str, points: list) -> None:
    """A single wait=True upsert of a book-sized point set outlives the
    client read timeout while Qdrant indexes ("timed out", third instance of
    the unbatched-at-scale defect class). Transport only: same points, same
    payloads, same ids, order preserved."""
    for i in range(0, len(points), UPSERT_BATCH):
        _t0 = time.perf_counter()
        client.upsert(collection_name=collection,
                      points=points[i:i + UPSERT_BATCH], wait=True)
        _tel("qdrant_upsert_ms", (time.perf_counter() - _t0) * 1000)
        _tel("qdrant_batches", n=1)


def _write_points_checkpointed(client: QdrantClient, collection: str,
                               chunks: list[dict], contract,
                               checkpoint_every: int = 64) -> None:
    """CHUNK-LANE-CHECKPOINT-V1: embed/upsert/checkpoint in bounded
    slices so worker death forfeits at most one slice, not the book.

    Same shape as _write_routing_points (the routing lane received this
    fix first, after the documented 1,705-wasted-embeds incident); the
    chunk lane had remained all-or-nothing: receipts only at ticket
    settlement, so every restart re-embedded everything. 64 reps at the
    measured ~1.1 texts/s bounds replay to ~1 minute while the
    checkpoint transaction itself costs milliseconds."""
    for start in range(0, len(chunks), checkpoint_every):
        slice_chunks = chunks[start:start + checkpoint_every]
        _write_points(client, collection, slice_chunks, contract)
        _checkpoint_chunks(slice_chunks, contract)


def _checkpoint_chunks(chunks: list[dict], contract) -> None:
    """Durably record a completed chunk slice, independent of the stage
    tx (points in Qdrant already survive a rollback; the receipt records
    that fact so _already_current can skip them on retry)."""
    _t0 = time.perf_counter()
    try:
        with tx() as conn:
            for c in chunks:
                record_projection_attempt(
                    conn,
                    projection=PROJECTION_QDRANT,
                    entity_kind=KIND_CHUNK,
                    entity_id=c["chunk_id"],
                    receipt_hash=receipt_hash(
                        PROJECTION_QDRANT, KIND_CHUNK, c["chunk_id"],
                        CONTRACT_VERSION),
                    contract=contract.contract_id,
                )
    except Exception:
        log.warning("chunk checkpoint failed; progress will be re-done",
                    extra={"error_code": "checkpoint_failed"})
    finally:
        _tel("receipt_persist_ms", (time.perf_counter() - _t0) * 1000)
        _tel("checkpoints", n=1)


def _write_points(client: QdrantClient, collection: str, chunks: list[dict], contract) -> None:
    vectors = _embed_texts(contract, [chunk["text"] for chunk in chunks])
    points = [
        PointStruct(
            id=qdrant_point_uuid(chunk["chunk_id"]),
            vector=vectors[i],
            payload={
                "chunk_id": chunk["chunk_id"],
                "doc_id": chunk["doc_id"],
                "parent_id": chunk["parent_id"] or "",
                "corpus_id": chunk["corpus_id"],
                "tier": chunk["tier"],
                # PAYLOAD-VOCABULARY-UNIFICATION (measured Stage-K pilot):
                # production retrieval filters representation_kind
                # ('routing_child' per pass1.py); tier-only payloads made
                # every child invisible to the FAST/dense lane.
                "representation_kind":
                    "routing_child" if chunk.get("tier") == "child"
                    else "parent_summary",
                "chunk_index": chunk["chunk_index"],
                "content_hash": projection_id(
                    PROJECTION_QDRANT, KIND_CHUNK, chunk["chunk_id"], CONTRACT_VERSION
                ),
                "embedding_contract": contract.contract_id,
                "text": chunk["text"],
                "summary": chunk["summary"],
            },
        )
        for i, chunk in enumerate(chunks)
    ]
    _upsert_batched(client, collection, points)


# ---------------------------------------------------------------------------
# R1A substrate: routing representations (SUMMARIES ROUTE / CHILDREN PROVE)
# ---------------------------------------------------------------------------
ROUTING_KIND_DOCUMENT_SUMMARY = "routing_document_summary"
ROUTING_KIND_SECTION_SUMMARY = "routing_section_summary"
ROUTING_KIND_CHILD = "routing_child"
# KNOWLEDGE-ARTIFACT-PERSISTENCE-V1: typed knowledge-object lanes.
ROUTING_KIND_PROCEDURE = "routing_procedure"
ROUTING_KIND_CONCEPT = "routing_concept"

ROUTING_CONTRACT_VERSION = "1.0.0"


def _routing_rows(conn: Connection, run_id: str) -> list[dict]:
    """Authoritative routing representations for the run's corpus:
    canonical DOCUMENT_RETRIEVAL_SUMMARY + SECTION_RETRIEVAL_SUMMARY
    rows (contract retrieval-summary-v2) + child evidence chunks."""
    from polymath_shared.retrieval_summaries import (
        DOC_SUMMARY_KIND,
        SECTION_SUMMARY_KIND,
    )

    rows = conn.execute(
        """
        SELECT rs.summary_id, rs.kind, rs.summary_text, rs.corpus_id, rs.doc_id,
               rs.parent_id, d.source_name
          FROM retrieval_summaries rs
          JOIN documents d ON d.doc_id = rs.doc_id
          JOIN runs r ON r.corpus_id = rs.corpus_id
         WHERE r.run_id = %s
         ORDER BY rs.doc_id, rs.parent_id NULLS FIRST
        """,
        (run_id,),
    ).fetchall()
    out = []
    for row in rows:
        kind = ROUTING_KIND_DOCUMENT_SUMMARY if row[1] == DOC_SUMMARY_KIND else ROUTING_KIND_SECTION_SUMMARY
        out.append({
            "summary_id": row[0],
            "representation_kind": kind,
            "text": row[2],
            "corpus_id": row[3],
            "doc_id": row[4],
            "parent_id": row[5],
            "source_name": row[6],
        })
    children = conn.execute(
        """
        SELECT c.chunk_id, c.doc_id, c.parent_id, c.text, d.corpus_id
          FROM chunks c
          JOIN documents d ON d.doc_id = c.doc_id
          JOIN runs r ON r.corpus_id = d.corpus_id
         WHERE r.run_id = %s AND c.tier = 'child'
         ORDER BY c.chunk_index
        """,
        (run_id,),
    ).fetchall()
    for row in children:
        out.append({
            "summary_id": None,
            "representation_kind": ROUTING_KIND_CHILD,
            "text": row[3],
            "corpus_id": row[4],
            "doc_id": row[1],
            "parent_id": row[2],
            "source_name": "",
            "chunk_id": row[0],
        })
    # KNOWLEDGE-ARTIFACT-PERSISTENCE-V1: typed knowledge-object lanes.
    # Procedures and concepts project as first-class retrieval objects
    # with their own representation kinds — never flattened into child
    # chunks, never mixed into fact evidence.
    procs = conn.execute(
        """
        SELECT p.procedure_id, p.document_id, p.corpus_id, p.title,
               p.goal, p.steps_json, p.tools_json, d.source_name
          FROM procedure_artifacts p
          JOIN documents d ON d.doc_id = p.document_id
          JOIN runs r ON r.corpus_id = p.corpus_id
         WHERE r.run_id = %s
        """,
        (run_id,),
    ).fetchall()
    for pid, did, corpus, title, goal, steps, tools, sname in procs:
        steps_l = steps if isinstance(steps, list) else json.loads(steps or "[]")
        tools_l = tools if isinstance(tools, list) else json.loads(tools or "[]")
        numbered = "\n".join(f"{i+1}. {s}" for i, s in enumerate(steps_l))
        text = f"{title}. {goal}.\n{numbered}"
        if tools_l:
            text += f"\nTools: {', '.join(tools_l)}."
        out.append({
            "summary_id": pid,
            "representation_kind": ROUTING_KIND_PROCEDURE,
            "text": text,
            "corpus_id": corpus,
            "doc_id": did,
            "parent_id": None,
            "source_name": sname or "",
        })
    concepts = conn.execute(
        """
        SELECT c.concept_id, c.document_id, c.corpus_id, c.name,
               c.description, c.domain, d.source_name
          FROM concept_artifacts c
          JOIN documents d ON d.doc_id = c.document_id
          JOIN runs r ON r.corpus_id = c.corpus_id
         WHERE r.run_id = %s
        """,
        (run_id,),
    ).fetchall()
    for cid_, did, corpus, name, desc, domain, sname in concepts:
        out.append({
            "summary_id": cid_,
            "representation_kind": ROUTING_KIND_CONCEPT,
            "text": f"{name}: {desc}",
            "corpus_id": corpus,
            "doc_id": did,
            "parent_id": None,
            "source_name": sname or "",
        })
    return out



def _already_current(conn, wanted: list[tuple[str, str, str]]) -> set[tuple[str, str]]:
    """(entity_kind, entity_id) pairs whose ACTIVE receipt already matches
    the hash this projection would write.

    Routing representations are corpus-wide by design, so every run's
    projection re-derives the whole corpus. That is correct for retrieval
    and quadratic for ingestion: on the 25-book corpus each ticket
    re-embedded all 19,016 chunks, which is ~50 minutes of work per
    ticket and the real reason projections never converged.

    The receipt hash already encodes the contract version, so comparing
    against it skips only rows that are genuinely current: a contract
    change, a wiped receipt or new content all produce a different hash
    and are re-projected.
    """
    if not wanted:
        return set()
    rows = conn.execute(
        """
        SELECT pr.entity_kind, pr.entity_id
          FROM projection_receipts pr
          JOIN (VALUES %s) AS w(kind, eid, rhash)
            ON pr.entity_kind = w.kind AND pr.entity_id = w.eid
           AND pr.receipt_hash = w.rhash
         WHERE pr.projection = %%s AND pr.active
        """ % ",".join(["(%s,%s,%s)"] * len(wanted)),
        [v for triple in wanted for v in triple] + [PROJECTION_QDRANT],
    ).fetchall()
    return {(k, e) for k, e in rows}


def _write_routing_points(client: QdrantClient, collection: str, rows: list[dict],
                          contract, checkpoint_every: int = 512) -> None:
    """Embed, upsert and CHECKPOINT in slices.

    A full corpus routing pass is ~2.3 hours of embedding (chunk texts run
    to thousands of tokens; a 32-text batch measured 6-45 s). Receipts used
    to be written only after the whole pass, inside the stage transaction,
    so any failure discarded every completed batch and the retry started
    from zero — three attempts burned 1,705 embed calls without ever
    finishing one pass.

    Points in Qdrant are a non-transactional side effect that already
    survives a rollback, so the receipt recording that fact is committed
    on its own connection as each slice lands. A retry then sees those
    entities as current (`_already_current`) and resumes where it stopped.
    """
    for start in range(0, len(rows), checkpoint_every):
        slice_rows = rows[start:start + checkpoint_every]
        _write_routing_slice(client, collection, slice_rows, contract)
        _checkpoint_routing(slice_rows, contract)


def _checkpoint_routing(rows: list[dict], contract) -> None:
    """Durably record a completed slice, independent of the stage tx."""
    try:
        with tx() as conn:
            for r in rows:
                record_projection_attempt(
                    conn,
                    projection=PROJECTION_QDRANT,
                    entity_kind=r["representation_kind"],
                    entity_id=r["summary_id"] or r["chunk_id"],
                    receipt_hash=receipt_hash(
                        PROJECTION_QDRANT, r["representation_kind"],
                        r["summary_id"] or r["chunk_id"], ROUTING_CONTRACT_VERSION),
                    contract=contract.contract_id,
                )
    except Exception:
        # A checkpoint is an optimisation: losing one costs re-work on
        # retry, never correctness. The stage still records receipts on
        # success.
        log.warning("routing checkpoint failed; progress will be re-done",
                    extra={"error_code": "checkpoint_failed"})


def _write_routing_slice(client: QdrantClient, collection: str, rows: list[dict], contract) -> None:
    # the embedder contract bounds batches at 32 texts per request
    batch_limit = getattr(contract, "batch_limit", 32) or 32
    vectors: list[list[float]] = []
    for i in range(0, len(rows), batch_limit):
        vectors.extend(_embed_texts(contract, [r["text"] for r in rows[i:i + batch_limit]]))
    points = []
    for i, r in enumerate(rows):
        point_id = qdrant_point_uuid(r["summary_id"] or r["chunk_id"])
        points.append(PointStruct(
            id=point_id,
            vector=vectors[i],
            payload={
                "summary_id": r["summary_id"],
                "chunk_id": r.get("chunk_id"),
                "representation_kind": r["representation_kind"],
                "corpus_id": r["corpus_id"],
                "doc_id": r["doc_id"],
                "parent_id": r["parent_id"] or "",
                "source_name": r["source_name"],
                "embedding_contract": contract.contract_id,
                "text": r["text"],
            },
        ))
    _upsert_batched(client, collection, points)


def process_event(conn: Connection, event: dict) -> None:
    payload = event["payload"]
    run_id = event["run_id"]
    corpus_id = payload.get("corpus_id")
    _tel_reset()
    chunks = _chunks_for_run(conn, run_id)
    # EMBEDDING-CONTRACT-REGISTRY-V1: resolve the pin FIRST so routing
    # summaries and children land under the corpus's authoritative
    # contract, never the settings default by accident.
    _pin_corpus_id = corpus_id or (chunks[0]["corpus_id"] if chunks else None)
    contract = (_corpus_contract(conn, _pin_corpus_id)
                if _pin_corpus_id else _active_contract())

    stage_contract = stage_contract_hash(STAGE, {
        "projection": PROJECTION_QDRANT,
        "embedding_contract": contract.contract_id,
        "contract_version": CONTRACT_VERSION,
        "routing_contract": "neural-embed-v1",
        "routing_contract_version": ROUTING_CONTRACT_VERSION,
    })

    with stage_transaction(conn, run_id=run_id, stage=STAGE, contract_hash=stage_contract) as writer:
        writer.artifact({
            "chunk_count": len(chunks),
            "embedding_contract": contract.contract_id,
        })
        _tel_emit_run = run_id  # settled below with final numbers

        # CHUNK-LANE-INCREMENTAL-V1: drop chunks whose ACTIVE receipt
        # already matches this exact projection. _chunks_for_run selects
        # by CORPUS, so without this filter every ticket re-embeds every
        # corpus chunk (measured: 12 tickets x 8,351 chunks scheduled
        # ~100k embeddings where ~8.4k were needed). The routing lane
        # has carried the identical guard since the 19,016-chunk
        # incident; this closes the same defect in the chunk lane.
        if chunks:
            _wanted_chunks = [
                (KIND_CHUNK, c["chunk_id"],
                 receipt_hash(PROJECTION_QDRANT, KIND_CHUNK, c["chunk_id"],
                              CONTRACT_VERSION))
                for c in chunks]
            _t0 = time.perf_counter()
            _current_chunks = _already_current(conn, _wanted_chunks)
            _tel("receipt_lookup_ms", (time.perf_counter() - _t0) * 1000)
            _tel("representations_total", n=len(_wanted_chunks))
            _tel("representations_already_current", n=len(_current_chunks))
            _chunk_total = len(chunks)
            chunks = [c for c in chunks
                      if (KIND_CHUNK, c["chunk_id"]) not in _current_chunks]
            if len(chunks) != _chunk_total:
                log.info("chunk projection incremental",
                         extra={"run_id": run_id, "stage": STAGE,
                                "error_code": None})
        if chunks:
            client = QdrantClient(url=get_settings().stores.qdrant_url,
                                  timeout=QDRANT_TIMEOUT_S)
            try:
                corpus_id = corpus_id or chunks[0]["corpus_id"]
                collection = qdrant_collection_name(corpus_id, contract.contract_id)
                _ensure_collection(client, collection, contract.dimension)
                _write_points_checkpointed(client, collection, chunks, contract)
            finally:
                client.close()
            for chunk in chunks:
                record_projection_attempt(
                    conn,
                    projection=PROJECTION_QDRANT,
                    entity_kind=KIND_CHUNK,
                    entity_id=chunk["chunk_id"],
                    receipt_hash=receipt_hash(PROJECTION_QDRANT, KIND_CHUNK, chunk["chunk_id"], CONTRACT_VERSION),
                    contract=contract.contract_id,
                )

        # R1A routing representations under the QUALIFIED neural
        # contract, in a separate collection (hash vectors never appear
        # semantically equivalent to neural vectors). Idempotent upserts
        # (point ids are summary/chunk content ids).
        from polymath_shared.embedding_contracts import NEURAL_EMBED_CONTRACT

        routing_contract = NEURAL_EMBED_CONTRACT
        routing_rows = _routing_rows(conn, run_id)
        # Incremental: drop rows already projected under this exact
        # contract. Without this every ticket re-embeds the whole corpus.
        if routing_rows:
            _wanted = [
                (r["representation_kind"], r["summary_id"] or r["chunk_id"],
                 receipt_hash(PROJECTION_QDRANT, r["representation_kind"],
                              r["summary_id"] or r["chunk_id"],
                              ROUTING_CONTRACT_VERSION))
                for r in routing_rows]
            _current = _already_current(conn, _wanted)
            _before = len(routing_rows)
            routing_rows = [
                r for r in routing_rows
                if (r["representation_kind"],
                    r["summary_id"] or r["chunk_id"]) not in _current]
            if _before != len(routing_rows):
                log.info("routing projection incremental",
                         extra={"run_id": run_id, "stage": STAGE,
                                "error_code": None})
        if routing_rows:
            client = QdrantClient(url=get_settings().stores.qdrant_url,
                                  timeout=QDRANT_TIMEOUT_S)
            try:
                routing_collection = qdrant_collection_name(
                    corpus_id or routing_rows[0]["corpus_id"], routing_contract.contract_id
                )
                _ensure_collection(client, routing_collection, routing_contract.dimension)
                _write_routing_points(client, routing_collection, routing_rows, routing_contract)
            finally:
                client.close()
            for r in routing_rows:
                record_projection_attempt(
                    conn,
                    projection=PROJECTION_QDRANT,
                    entity_kind=r["representation_kind"],
                    entity_id=r["summary_id"] or r["chunk_id"],
                    receipt_hash=receipt_hash(
                        PROJECTION_QDRANT, r["representation_kind"],
                        r["summary_id"] or r["chunk_id"], ROUTING_CONTRACT_VERSION,
                    ),
                    contract=routing_contract.contract_id,
                )

        crash_after = int(os.environ.get("POLYMATH_TEST_CRASH_AFTER_POINTS", "0"))
        if crash_after and len(chunks) >= crash_after:
            # Fault injection for acceptance test 3 (kill the projector
            # mid-flight). Never set in production.
            raise RuntimeError("fault injection: simulated crash after points write")

        # No outbox event: the control census schedules the verify stage
        # from this receipt.
        total_ms = (time.perf_counter() - _TELEMETRY.get("started", time.perf_counter())) * 1000
        summary = {k: (round(v, 1) if isinstance(v, float) else v)
                   for k, v in _TELEMETRY.items() if k != "started"}
        summary["total_ms"] = round(total_ms, 1)
        writer.artifact({"projection_telemetry": summary})
        log.info("projection telemetry", extra={
            "run_id": run_id, "stage": STAGE, "error_code": None,
            "duration_ms": summary["total_ms"]})
        log.info("projection telemetry detail: %s", summary,
                 extra={"run_id": run_id, "stage": STAGE, "error_code": None})
        writer.run_status("reconciling")


def run_forever(poll_interval_s: float = 2.0, batch_size: int = 1) -> None:
    """LONG-STAGE-LEASE-CORRECTNESS-V1: claim depth 1.

    A worker executes tickets serially, so claiming ahead bought nothing
    but made "held" differ from "being processed" -- and a stage running
    past claim_ttl_s let the reaper expire the queued ones. Parallelism
    comes from running several workers of a type.
    """
    from polymath_shared.worker_runtime import run_worker

    run_worker('project_qdrant', [EVENT_TYPE], process_event,
               poll_interval_s=poll_interval_s, batch_size=batch_size)

if __name__ == "__main__":
    run_forever()
