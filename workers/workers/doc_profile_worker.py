"""DOCUMENT-PROFILE-V1 step 3 — the `doc_profile` stage worker (owner architecture 2026-09-07).

One durable stage per run: lean context → enrichment LLM (isolated `doc_profile` pool) → deterministic compiler
(rag-profile-v3) → profile artifact → profile vector projection (own collection). Everything commits in ONE
stage transaction; the two artifacts carry the receipt chain
    content hash → input hash → raw response hash → compiled hash → projection hash.

Invariants (owner): chunk vectors, chunk ids, parent/child projection identity and graph receipts are never
touched — this stage only ADDS an artifact and a point in its own collection.

Rollout phase A: the stage sits among the background stages (non-blocking) so existing corpora keep serving;
phase B (after the backfill) moves it ahead of `verify_projections`, which makes QUERY_READY require it.
"""
from __future__ import annotations

import hashlib
import json
import logging
import time

from polymath_shared.document_profile import compiler as C
from polymath_shared.document_profile import context as CX
from polymath_shared.document_profile import projection as PJ
from polymath_shared.document_profile.prompt import (
    PROMPT_VERSION,
    SYSTEM,
    build_user_prompt,
)
from polymath_shared.logging import configure_logging
from polymath_shared.receipts import stage_contract_hash, stage_transaction
from polymath_shared.worker_runtime import TransientStageHold, run_worker
from psycopg import Connection

STAGE = "doc_profile"
EVENT_TYPE = "doc_profile.v1"
CONTEXT_BUDGET_TOKENS = 500
MAX_OUTPUT_TOKENS = 2400         # ~80 labelled lines at the v3.1 aims (10 / 10 / 15 / 15 / 10 / 10 / 10)
MAX_LANE_ATTEMPTS = 4            # up to 2 primary lanes (rotated by run), then the fallbacks in pin order
FALLBACK_MARK = "fallback"       # a pinned lane whose name contains this is a fallback tier, tried after every primary

log = logging.getLogger("doc_profile")

#: dependency hooks (tests inject; production wires the pool, the embedder sidecar and Qdrant)
HOOKS: dict = {"complete": None, "embed": None, "qdrant": None}


def contract() -> str:
    return stage_contract_hash(STAGE, {
        "schema": C.SCHEMA_VERSION, "prompt": PROMPT_VERSION, "compiler": C.COMPILER_VERSION,
        "builder": CX.BUILDER_VERSION, "projection": PJ.PROJECTION_VERSION, "budget_tokens": CONTEXT_BUDGET_TOKENS,
    })


def _sha(obj) -> str:
    s = obj if isinstance(obj, str) else json.dumps(obj, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def _resolve_document(conn: Connection, run_id: str) -> tuple[str, str]:
    """(doc_id, corpus_id) for the run — from its chunked.v1 payload, else from the intake payload."""
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
        raise RuntimeError(f"DOC_PROFILE_NO_DOCUMENT: run {run_id[:20]} has no landed document")
    return str(doc[0]), str(ip.get("corpus_id"))


def _load_inputs(conn: Connection, doc_id: str) -> tuple[dict, list[dict], list[str]]:
    d = conn.execute(
        "SELECT doc_id, corpus_id, source_name, media_type, frontmatter, content_hash FROM documents WHERE doc_id=%s",
        (doc_id,)).fetchone()
    if not d:
        raise RuntimeError(f"DOC_PROFILE_NO_DOCUMENT: {doc_id[:20]}")
    document = {"doc_id": d[0], "corpus_id": d[1], "source_name": d[2], "media_type": d[3],
                "frontmatter": d[4] or {}, "content_hash": d[5]}
    parents = [
        {"chunk_index": r[0], "char_start": r[1], "char_end": r[2], "heading_path": r[3], "text": r[4], "region_role": r[5]}
        for r in conn.execute(
            "SELECT chunk_index, char_start, char_end, heading_path, text, region_role FROM chunks "
            "WHERE doc_id=%s AND tier='parent' ORDER BY chunk_index", (doc_id,)).fetchall()]
    terms: list[str] = []
    try:
        t = conn.execute("SELECT major_concepts FROM document_summaries WHERE document_id=%s ORDER BY created_at DESC LIMIT 1",
                         (doc_id,)).fetchone()
        if t and t[0]:
            vals = t[0] if isinstance(t[0], list) else json.loads(t[0])
            terms = [str(x.get("name") if isinstance(x, dict) else x) for x in vals][:12]
    except Exception:  # noqa: BLE001 — terms are an optional surface
        terms = []
    return document, parents, terms


def lane_order(pin: list[str], run_key: str) -> list[str]:
    """The pool's attempt order for one run: the PRIMARY lanes (pin entries without "fallback" in the name)
    rotated by a hash of the run so consecutive documents start on different keys, then the fallback lanes in
    pin order (owner 2026-09-07: six dedicated keys as tier 0, Gemini as fallback 1, OpenRouter as fallback 2)."""
    primaries = [n for n in pin if FALLBACK_MARK not in n]
    fallbacks = [n for n in pin if FALLBACK_MARK in n]
    if primaries:
        start = int(hashlib.sha256((run_key or "").encode("utf-8")).hexdigest(), 16) % len(primaries)
        primaries = primaries[start:] + primaries[:start]
    return primaries + fallbacks


def _pool_complete(system_prompt: str, user_prompt: str, max_tokens: int, run_key: str = "") -> tuple[str, str | None, dict]:
    """The isolated profile pool: walk `lane_order(stage_pin("doc_profile"), run)` — primaries rotated by run,
    fallbacks last. Returns (raw_text, error, receipt). A transport failure on one lane moves to the next."""
    from polymath_shared.llm_extraction.client import LLMExtractionClient
    from polymath_shared.llm_extraction.pool import cloud_endpoints, stage_pin

    pin = stage_pin(STAGE) or []
    by_name = {e.name: e for e in cloud_endpoints() if e.name in pin}
    order = lane_order(pin, run_key)
    endpoints = [by_name[n] for n in order if n in by_name]
    if not endpoints:
        return "", "no_active_lane", {"attempts": [], "pin": list(pin)}
    attempts: list[dict] = []
    for ep in endpoints[:MAX_LANE_ATTEMPTS]:
        t0 = time.perf_counter()
        try:
            client = LLMExtractionClient("cloud", url=ep.url, model=ep.model, limiter_key=ep.limiter_key,
                                         api_key=ep.api_key, cloud_opts=ep.cloud_opts, timeout_s=90.0, max_attempts=1)
            client.endpoint_name = ep.name
            raw, err = client.complete_one(user_prompt, system_prompt=system_prompt, max_tokens=max_tokens)
        except Exception as exc:  # noqa: BLE001 — a lane failure is a receipted attempt, never a crash
            raw, err = "", f"{type(exc).__name__}"
        attempts.append({"lane": ep.name, "model": ep.model, "ms": round((time.perf_counter() - t0) * 1000, 1), "error": err})
        if not err and (raw or "").strip():
            return raw, None, {"attempts": attempts, "lane": ep.name, "model": f"{ep.name}:{ep.model}"}
    return "", attempts[-1]["error"] if attempts else "no_attempt", {"attempts": attempts}


def _embed_texts(texts: list[str]) -> list[list[float]]:
    from polymath_shared.clients import EmbedderClient
    resp = EmbedderClient().embed(texts, "doc_profile")
    vecs = resp.get("vectors") or resp.get("embeddings")
    if vecs is None:
        raise RuntimeError(f"embedder response without vectors: {sorted(resp.keys())}")
    return [list(v) for v in vecs]


def process_event(conn: Connection, event: dict) -> None:
    run_id = event["run_id"]
    with stage_transaction(conn, run_id=run_id, stage=STAGE, contract_hash=contract()) as writer:
        doc_id, corpus_id = _resolve_document(conn, run_id)
        document, parents, terms = _load_inputs(conn, doc_id)
        ctx = CX.build_context(document, parents, terms=terms, budget_tokens=CONTEXT_BUDGET_TOKENS)
        input_hash = ctx.input_hash(document.get("content_hash") or "")
        user_prompt = build_user_prompt(ctx.title, ctx.structure_block, ctx.excerpts_block)

        complete = HOOKS.get("complete")
        if complete is None:
            raw, err, pool_rec = _pool_complete(SYSTEM, user_prompt, MAX_OUTPUT_TOKENS, run_key=run_id)
        else:
            raw, err, pool_rec = complete(SYSTEM, user_prompt, MAX_OUTPUT_TOKENS)
        if err or not (raw or "").strip():
            # the pool is dark or rate-limited: hand the ticket back without consuming an attempt (TRANSIENT-HOLD-V1)
            log.warning("doc_profile pool unavailable run=%s doc=%s err=%s attempts=%s",
                        run_id[:16], doc_id[:16], err, json.dumps(pool_rec.get("attempts"))[:300])
            raise TransientStageHold(f"DOC_PROFILE_POOL_UNAVAILABLE: {err} ({len(pool_rec.get('attempts') or [])} lanes tried)")

        source_text = "\n".join(p.get("text") or "" for p in parents)
        result = C.compile_llm_output(raw, source_text=source_text, grounding_mode="warn")
        rec = result.record
        valid, missing = C.profile_valid(rec)
        artifact = C.semantic_artifact(rec)
        emitted = C.emit(rec, doc_id)
        compiled_hash = _sha(artifact)
        profile_record = {
            "schema_version": C.SCHEMA_VERSION, "prompt_version": PROMPT_VERSION, "compiler_version": C.COMPILER_VERSION,
            "builder_version": CX.BUILDER_VERSION, "model": pool_rec.get("model"), "lane": pool_rec.get("lane"),
            "attempts": pool_rec.get("attempts"),
            "content_hash": document.get("content_hash"), "input_hash": input_hash, "raw_response_hash": _sha(raw),
            "compiled_hash": compiled_hash,
            "quality": round(result.quality, 3), "format_quality": round(result.format_quality, 3),
            "coverage_quality": round(result.coverage_quality, 3), "ok": result.ok, "valid": valid, "missing": missing,
            "truncated": result.truncated,
            "issues": [{"severity": i.severity, "code": i.code, "message": i.message[:160]} for i in result.issues][:24],
            "context": {k: v for k, v in ctx.to_dict().items() if k in ("title", "identity", "structure", "used_tokens", "sources", "allocation", "budget_tokens")},
            "raw": raw[:8000], "compiled": artifact, "representations": emitted["representations"],
        }
        writer.artifact({"doc_profile": profile_record})
        if not result.ok or not valid:
            raise RuntimeError(f"DOC_PROFILE_INVALID: ok={result.ok} missing={missing} quality={result.quality:.2f}")

        # projection — its own collection, one point per document, one vector per atomic unit
        from polymath_shared.embedding_contracts import active_contract
        contract_obj = active_contract()
        embed = HOOKS.get("embed") or _embed_texts
        client = HOOKS.get("qdrant")
        owned = client is None
        if owned:
            from polymath_shared.settings import get_settings
            from qdrant_client import QdrantClient
            client = QdrantClient(url=get_settings().stores.qdrant_url, timeout=60)
        try:
            receipt = PJ.project_profile(
                client, embed=embed, embedding_contract_id=contract_obj.contract_id, dim=contract_obj.dimension,
                doc_id=doc_id, corpus_id=corpus_id, title=ctx.title, representations=emitted["representations"],
                payload_extra={"topics": rec.topics, "terms": rec.terms, "quality": round(result.quality, 3),
                               "source_name": document.get("source_name")},
                source_doc_hash=document.get("content_hash") or "", schema_version=C.SCHEMA_VERSION,
                prompt_version=PROMPT_VERSION, compiled_hash=compiled_hash)
        finally:
            if owned:
                client.close()
        vec_ok, vmissing = PJ.has_required_vectors(receipt)
        writer.artifact({"doc_profile_qdrant": {**receipt, "valid": vec_ok, "missing": vmissing, "compiled_hash": compiled_hash}})
        if not vec_ok:
            raise RuntimeError(f"DOC_PROFILE_VECTORS_INCOMPLETE: {vmissing}")
        log.info("doc_profile done run=%s doc=%s quality=%.2f vectors=%s lane=%s", run_id[:16], doc_id[:16],
                 result.quality, receipt.get("vectors"), pool_rec.get("lane"))


def main() -> None:
    configure_logging("doc_profile")
    run_worker("doc_profile", [EVENT_TYPE], process_event)


if __name__ == "__main__":
    main()
