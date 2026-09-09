"""DOC-PARENT-MAP STAGE worker (RAG-PIPELINE-FINISH — the auto-minted pMAP stage).

Makes `PMAP` a true drained functional pool for FRESH uploads: one durable stage per
run that maps every retrieval-eligible parent so the document can reach
`VNEXT_COMPLETE` (readiness floor `unresolved_eligible_parents == 0`). Until this
worker existed, `doc_parent_map` ran only from `scripts/parent_map_backfill.py`
(owner-gated), so no fresh upload could complete the vNext substrate.

Shape (mirrors `doc_profile_worker`, drives the durable core in `doc_parent_map_worker`):

    resolve run → load document + parents → build DocumentGroundingContextV1 (Phase 5/6)
      → run_document_mapping(infer=<in-run cross-lane failover over map_groq*>,
                             reliability_cap=pmap_pool_batch_cap(), grounding=…)   [own short txns, §28]
      → project active maps to Qdrant → write the `doc_parent_map` stage artifact.

The INFER closure is the PMAP pool's in-run cross-lane failover (the Phase 4/7 drain
gap): a batch walks the six `map_groq*` accounts (rotated per run) and the FIRST healthy
lane finishes it; only if EVERY lane is unavailable does the batch defer (partial) and the
stage hand its ticket back TRANSIENT (no attempt burned) for a later pass — never a
document-level failure while a qualified lane could do the job. Architecture frozen:
ParentSkeleton → plaintext MAP DSL → deterministic map_compiler → durable maps → projection.

Non-blocking (rollout phase A): a lingering pMAP ticket never holds legacy QUERY_READY.
Minting is owner-flag-gated (see control.tickets `doc_parent_map` gate) so enabling it can
never silently re-map existing corpora under the forensic hold.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os

from polymath_shared.document_profile import map_compiler
from polymath_shared.document_profile.grounding import (
    GROUNDING_CONTEXT_VERSION,
    build_grounding_context,
)
from polymath_shared.document_profile.map_prompt import MAP_PROMPT_VERSION, build_map_prompt
from polymath_shared.document_profile.parent_map_projection import PROJECTION_VERSION
from polymath_shared.document_profile.parent_skeleton import build_parent_skeletons
from polymath_shared.logging import configure_logging
from polymath_shared.receipts import stage_contract_hash, stage_transaction
from polymath_shared.worker_runtime import TransientStageHold, run_worker
from psycopg import Connection
from workers.doc_parent_map_worker import (
    MapInferError,
    MappingOutcome,
    run_document_mapping,
)

STAGE = "doc_parent_map"
EVENT_TYPE = "doc_parent_map.v1"
MAX_MAP_TOKENS = 2400

log = logging.getLogger("doc_parent_map")

#: dependency hooks (tests inject; production wires the Groq pool, Qdrant + db.tx)
HOOKS: dict = {"infer": None, "tx": None, "project": None}


def contract() -> str:
    return stage_contract_hash(STAGE, {
        "compiler": map_compiler.MAP_COMPILER_VERSION, "prompt": MAP_PROMPT_VERSION,
        "grounding": GROUNDING_CONTEXT_VERSION, "projection": PROJECTION_VERSION,
    })


def _sha(obj) -> str:
    s = obj if isinstance(obj, str) else json.dumps(obj, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def _resolve_document(conn: Connection, run_id: str) -> tuple[str, str]:
    """(doc_id, corpus_id) from the run's chunked.v1 payload, else the intake payload."""
    row = conn.execute(
        "SELECT payload FROM outbox_events WHERE run_id=%s AND event_type='chunked.v1' ORDER BY event_id LIMIT 1",
        (run_id,)).fetchone()
    if row and row[0]:
        p = row[0] if isinstance(row[0], dict) else json.loads(row[0])
        if p.get("doc_id") and p.get("corpus_id"):
            return str(p["doc_id"]), str(p["corpus_id"])
    meta = conn.execute("SELECT metadata FROM runs WHERE run_id=%s", (run_id,)).fetchone()
    m = (meta[0] if meta else None) or {}
    m = m if isinstance(m, dict) else json.loads(m or "{}")
    ip = m.get("intake_payload") or {}
    doc = conn.execute("SELECT doc_id FROM documents WHERE corpus_id=%s AND source_name=%s",
                       (ip.get("corpus_id"), ip.get("source_name"))).fetchone()
    if not doc:
        raise RuntimeError(f"DOC_PARENT_MAP_NO_DOCUMENT: run {run_id[:20]} has no landed document")
    return str(doc[0]), str(ip.get("corpus_id"))


def _load_inputs(conn: Connection, doc_id: str) -> tuple[dict, list[dict]]:
    d = conn.execute(
        "SELECT doc_id, corpus_id, source_name, media_type, frontmatter, content_hash FROM documents WHERE doc_id=%s",
        (doc_id,)).fetchone()
    if not d:
        raise RuntimeError(f"DOC_PARENT_MAP_NO_DOCUMENT: {doc_id[:20]}")
    document = {"doc_id": d[0], "corpus_id": d[1], "source_name": d[2], "media_type": d[3],
                "frontmatter": d[4] or {}, "content_hash": d[5]}
    parents = [
        {"chunk_id": r[0], "chunk_index": r[1], "char_start": r[2], "heading_path": r[3],
         "text": r[4], "region_role": r[5]}
        for r in conn.execute(
            "SELECT chunk_id, chunk_index, char_start, heading_path, text, region_role FROM chunks "
            "WHERE doc_id=%s AND tier='parent' ORDER BY chunk_index", (doc_id,)).fetchall()]
    return document, parents


def _pmap_lanes(run_key: str):
    """The ACTIVE doc_parent_map pin endpoints, rotated by run so consecutive documents
    start on different accounts (spread). Empty when the whole pool is dark."""
    from polymath_shared.llm_extraction.pool import cloud_endpoints, stage_pin
    pin = stage_pin(STAGE) or []
    active = [e for e in cloud_endpoints() if e.name in pin]
    active.sort(key=lambda e: e.name)
    if not active:
        return []
    start = int(hashlib.sha256((run_key or "").encode("utf-8")).hexdigest(), 16) % len(active)
    return active[start:] + active[:start]


def _make_pmap_infer(run_key: str):
    """Build the injected inference boundary: in-run cross-lane failover over the pMAP
    pool. The FIRST healthy account finishes a batch; if every account is unavailable the
    batch raises MapInferError (carrying whether any HTTP was dispatched) so the durable
    core defers it — a lane outage never manufactures a document failure."""
    from polymath_shared.llm_extraction.client import LLMExtractionClient

    def infer(skeletons, *, is_combined: bool = False, grounding=None) -> str:
        system, user = build_map_prompt(skeletons, grounding=grounding, is_combined=is_combined)
        endpoints = _pmap_lanes(run_key)
        if not endpoints:
            raise MapInferError("NO_ACTIVE_LANE", reason="pool_dark", dispatched=False)
        any_dispatched = False
        last_err = "no_attempt"
        for ep in endpoints:
            client = LLMExtractionClient("cloud", url=ep.url, model=ep.model, limiter_key=ep.limiter_key,
                                         api_key=ep.api_key, cloud_opts=ep.cloud_opts, timeout_s=90.0, max_attempts=1)
            client.endpoint_name = ep.name
            try:
                raw, err = client.complete_one(user, system_prompt=system, max_tokens=MAX_MAP_TOKENS)
            except Exception as exc:  # noqa: BLE001 — a lane failure moves to the next account
                raw, err = "", f"{type(exc).__name__}"
            any_dispatched = any_dispatched or bool(getattr(client, "_last_http_dispatched", False))
            if not err and (raw or "").strip():
                return raw                                   # a healthy lane finished the batch
            last_err = err or "empty_response"
        # every account was unavailable — defer the batch (the durable core records partial)
        raise MapInferError(last_err, reason="all_lanes_failed", dispatched=any_dispatched)

    return infer


def _project_active_maps(document, parents, corpus_id, map_contract) -> dict | None:
    """Project the document's ACTIVE maps into the parent-map Qdrant collection. Reuses the
    backfill projection path. Returns the projection receipt, or None when there is nothing
    to project."""
    hook = HOOKS.get("project")
    if hook is not None:
        return hook(document, parents, corpus_id, map_contract)
    doc_id = document["doc_id"]
    from polymath_shared.db import tx
    from polymath_shared.document_profile import parent_map_projection as PMP
    from polymath_shared.document_profile.map_compiler import CompiledMap
    from polymath_shared.embedding_contracts import active_contract
    with tx() as conn:
        mrows = conn.execute(
            "SELECT alias, parent_id, routing_signature, semantic_hooks, exact_identifiers, map_hash, quality_flags "
            "FROM document_parent_maps WHERE doc_id=%s AND map_contract=%s AND active ORDER BY alias",
            (doc_id, map_contract)).fetchall()
    if not mrows:
        return None
    maps = [CompiledMap(alias=r[0], parent_id=r[1], routing_signature=r[2], semantic_hooks=tuple(r[3] or []),
                        exact_identifiers=tuple(r[4] or []), map_hash=r[5], quality_flags=tuple(r[6] or []))
            for r in mrows]
    manifest = build_parent_skeletons(parents)
    ct = active_contract()
    # the projection's embed contract is (list[str]) -> list[list[float]]; reuse the proven
    # batch-slicing embed helper the backfill/profile paths use (returns vectors, not the raw
    # embedder response). Its embed-lane tag is immaterial — same model, same vector space.
    from workers.doc_profile_worker import _embed_texts
    from polymath_shared.settings import get_settings
    from qdrant_client import QdrantClient
    client = QdrantClient(url=get_settings().stores.qdrant_url, timeout=60)
    try:
        return PMP.project_parent_maps(
            client, embed=lambda t: _embed_texts(t), embedding_contract_id=ct.contract_id,
            dim=ct.dimension, doc_id=doc_id, corpus_id=corpus_id, maps=maps, manifest=manifest,
            map_contract=map_contract)
    finally:
        client.close()


def _is_transient_incomplete(outcome: MappingOutcome) -> bool:
    """An incomplete document is TRANSIENT (requeue, no attempt burned) when the shortfall
    carries a capacity/transport signal — refusals, 429s, HTTP faults or empties. With no
    such signal the compiler simply could not map some parent (deterministic) → a real
    failed attempt, so a document that can never map ends receipted, not looping forever."""
    return bool(outcome.limiter_refusals or outcome.http_429 or outcome.http_failures
                or outcome.empty_completions)


def process_event(conn: Connection, event: dict) -> None:
    run_id = event["run_id"]
    doc_id, corpus_id = _resolve_document(conn, run_id)
    document, parents = _load_inputs(conn, doc_id)

    if not parents:
        with stage_transaction(conn, run_id=run_id, stage=STAGE, contract_hash=contract()) as writer:
            writer.artifact({"doc_parent_map": {"doc_id": doc_id, "corpus_id": corpus_id,
                                                "eligible_parents": 0, "parents_mapped": 0, "complete": True,
                                                "note": "no_parent_chunks"}})
        return

    from polymath_shared.llm_extraction.lane_registry import pmap_pool_batch_cap
    grounding = build_grounding_context(document, parents)
    cap = pmap_pool_batch_cap()
    infer = HOOKS.get("infer") or _make_pmap_infer(run_id)
    from polymath_shared.db import tx as _db_tx
    tx_factory = HOOKS.get("tx") or _db_tx

    outcome = run_document_mapping(
        tx_factory, run_id=run_id, doc_id=doc_id, corpus_id=corpus_id, parents=parents,
        infer=infer, grounding=grounding, reliability_cap=cap, provider="groq")

    proj = None
    if outcome.parents_mapped:
        try:
            proj = _project_active_maps(document, parents, corpus_id, outcome.map_contract)
        except Exception as exc:  # noqa: BLE001 — a projection outage is transient; maps are durable, retry later
            log.warning("doc_parent_map projection deferred run=%s doc=%s err=%s", run_id[:16], doc_id[:16], exc)
            raise TransientStageHold(f"DOC_PARENT_MAP_PROJECTION_UNAVAILABLE: {type(exc).__name__}")

    with stage_transaction(conn, run_id=run_id, stage=STAGE, contract_hash=contract()) as writer:
        writer.artifact({"doc_parent_map": {
            "doc_id": doc_id, "corpus_id": corpus_id, "map_contract": outcome.map_contract,
            "grounding_version": GROUNDING_CONTEXT_VERSION, "grounding_hash": grounding.context_hash,
            "reliability_cap": cap, "eligible_parents": outcome.eligible_parents,
            "excluded_parents": outcome.excluded_parents, "parents_mapped": outcome.parents_mapped,
            "parents_newly_mapped": outcome.parents_newly_mapped,
            "batches_total": outcome.batches_total, "batches_done": outcome.batches_done,
            "batches_partial": outcome.batches_partial, "unresolved": len(outcome.unresolved_parent_ids),
            "complete": outcome.complete, "limiter_refusals": outcome.limiter_refusals,
            "http_dispatches": outcome.http_dispatches, "http_429": outcome.http_429,
            "http_failures": outcome.http_failures, "empty_completions": outcome.empty_completions,
            "compiler_complete": outcome.compiler_complete, "compiler_partial": outcome.compiler_partial,
            "compiler_invalid": outcome.compiler_invalid, "projection": proj,
        }})

    log.info("doc_parent_map run=%s doc=%s mapped=%s/%s complete=%s refusals=%s dispatch=%s",
             run_id[:16], doc_id[:16], outcome.parents_mapped, outcome.eligible_parents,
             outcome.complete, outcome.limiter_refusals, outcome.http_dispatches)

    if not outcome.complete:
        detail = (f"unresolved={len(outcome.unresolved_parent_ids)} partial={outcome.batches_partial} "
                  f"refusals={outcome.limiter_refusals} http_fail={outcome.http_failures}")
        if _is_transient_incomplete(outcome):
            raise TransientStageHold(f"DOC_PARENT_MAP_POOL_UNAVAILABLE: {detail}")
        raise RuntimeError(f"DOC_PARENT_MAP_INCOMPLETE: {detail}")


def main() -> None:
    configure_logging("doc_parent_map")
    run_worker("doc_parent_map", [EVENT_TYPE], process_event)


if __name__ == "__main__":
    main()
