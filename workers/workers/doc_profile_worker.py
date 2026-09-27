"""DOCUMENT-PROFILE-V1 step 3 — the `doc_profile` stage worker (owner architecture 2026-09-07).

One durable stage per run: lean context → enrichment LLM (isolated `doc_profile` pool) → deterministic compiler
(rag-profile-v3) → profile artifact → profile vector projection (own collection). Everything commits in ONE
stage transaction; the two artifacts carry the receipt chain
    content hash → input hash → raw response hash → compiled hash → projection hash.

Invariants (owner): chunk vectors, chunk ids, parent/child projection identity and graph receipts are never
touched — this stage only ADDS an artifact and a point in its own collection.

Rollout phase A: the stage sits among the background stages (non-blocking) so existing corpora keep serving;
phase B (after the backfill) moves it ahead of `verify_projections`, which makes QUERY_READY require it.

FACET-RETRIEVAL-V1 F4 (plan §3.4, giant documents): a document with more than
`giant_profile.GIANT_PARENT_THRESHOLD` parents gets one SECTION profile per top-level heading
(`build_section_profiles`: the same prompt, compiler, projection and atom lane as the document profile, one
point per section beside the document point, `scope: section`), built BEFORE the document profile in short
transactions (never a transaction across an LLM call, the pMAP rule §28), at most
`POLYMATH_DOC_PROFILE_SECTIONS_PER_PASS` per ticket pass — the rest hands the ticket back READY
(TransientStageHold) and the next pass resumes, skipping sections whose input has not changed. The document
profile of a giant is then built from `giant_profile.build_giant_fingerprint` (a stratified sample across ALL
sections, never the first pages). `POLYMATH_DOC_PROFILE_GIANT=0` is the rollback switch: byte-identical to
the pre-F4 stage for every document.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import logging
import time

from polymath_shared.document_profile import compiler as C
from polymath_shared.document_profile import context as CX
from polymath_shared.document_profile import fingerprint as FP
from polymath_shared.document_profile import giant_profile as GP
from polymath_shared.document_profile import profile_prompt_vnext as PP
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
PRIMARY_ATTEMPTS = 2             # primaries tried per pass before the fallback tier (six keys would otherwise starve it)
FALLBACK_MARK = "fallback"       # a pinned lane whose name contains this is a fallback tier, tried after every primary
# Errors that mean "the pool cannot answer right now" (rate/size limits, 5xx, transport) — the ticket is handed back
# READY (TRANSIENT-HOLD-V1). Anything else (HTTP 400/401/403/404, a 200 with empty text) is a failed attempt, so a
# document that can never be profiled ends as a receipted failure instead of holding forever.
# LLM-BACKEND-BATCH1 (gap L-09): LIMITER_REFUSED is this process's own rate limiter saying "wait" (budget spent,
# breaker open, family gate) — capacity, never a fault of the document, so it holds the ticket like a 429 does.
_TRANSIENT_ERR = re.compile(r"^(?:HTTP_(?:408|413|425|429|5\d\d)|TRANSPORT_.*|.*Timeout.*|Connect.*|RemoteProtocolError"
                            r"|ReadError|WriteError|rate_limited|pool_dark|circuit_open|no_active_lane|no_attempt"
                            r"|LIMITER_REFUSED)$")

log = logging.getLogger("doc_profile")

#: dependency hooks (tests inject; production wires the pool, the embedder sidecar and Qdrant; F4: `tx` is the
#: short-transaction factory the section loop commits through — `polymath_shared.db.tx` in production)
HOOKS: dict = {"complete": None, "embed": None, "qdrant": None, "tx": None}
#: F4: section profiles built per ticket pass before the ticket is handed back (env override; ≥ 1)
DEFAULT_SECTIONS_PER_PASS = 8


def _giant_enabled() -> bool:
    """F4 rollback switch (`POLYMATH_DOC_PROFILE_GIANT`, default ON): off ⇒ no section profiles, the
    document profile of a giant is built exactly as before F4 (a config change, never a re-ingest)."""
    return os.environ.get("POLYMATH_DOC_PROFILE_GIANT", "1").strip().lower() not in ("0", "false", "no", "off")


def sections_per_pass() -> int:
    raw = os.environ.get("POLYMATH_DOC_PROFILE_SECTIONS_PER_PASS", "").strip()
    return max(1, int(raw)) if raw.isdigit() else DEFAULT_SECTIONS_PER_PASS


def _force_sections() -> bool:
    """`POLYMATH_DOC_PROFILE_FORCE_SECTIONS=1` (the rebuild script's `--force`): rebuild every section, even one whose
    input is unchanged under the live prompt."""
    return os.environ.get("POLYMATH_DOC_PROFILE_FORCE_SECTIONS", "").strip().lower() in ("1", "true", "yes", "on")


def _vnext_enabled() -> bool:
    """DOCUMENT-SEMANTIC-INDEX-V1 S8 rollback switch (plan §28 `profile_generation`):
    when set, the stage builds the vNext DocumentFingerprint (full-structure, no
    first-400 bias) + `profile_prompt_vnext` and DROPS the `document_summaries.major_concepts`
    read (GAP-04). Default OFF — the live path is byte-identical, so flipping it back is
    a config change, never a re-ingest. The base surfaces still project unchanged; the
    research-index tags land in the artifact (not yet projected)."""
    return os.environ.get("POLYMATH_DOC_PROFILE_VNEXT", "").strip().lower() in ("1", "true", "yes", "on")


def contract() -> str:
    giant = {"giant": GP.GIANT_PROFILE_VERSION} if _giant_enabled() else {}
    if _vnext_enabled():
        return stage_contract_hash(STAGE, {
            "schema": C.SCHEMA_VERSION, "prompt": PP.PROFILE_VNEXT_PROMPT_VERSION, "compiler": C.COMPILER_VERSION,
            "builder": FP.FINGERPRINT_BUILDER_VERSION, "projection": PJ.PROJECTION_VERSION,
            "budget_tokens": FP.DEFAULT_BUDGET_TOKENS, "vnext": True, **giant,
        })
    return stage_contract_hash(STAGE, {
        "schema": C.SCHEMA_VERSION, "prompt": PROMPT_VERSION, "compiler": C.COMPILER_VERSION,
        "builder": CX.BUILDER_VERSION, "projection": PJ.PROJECTION_VERSION, "budget_tokens": CONTEXT_BUDGET_TOKENS,
        **giant,
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


def _load_inputs(conn: Connection, doc_id: str, *, want_terms: bool = True) -> tuple[dict, list[dict], list[str]]:
    d = conn.execute(
        "SELECT doc_id, corpus_id, source_name, media_type, frontmatter, content_hash FROM documents WHERE doc_id=%s",
        (doc_id,)).fetchone()
    if not d:
        raise RuntimeError(f"DOC_PROFILE_NO_DOCUMENT: {doc_id[:20]}")
    document = {"doc_id": d[0], "corpus_id": d[1], "source_name": d[2], "media_type": d[3],
                "frontmatter": d[4] or {}, "content_hash": d[5]}
    parents = [
        {"chunk_index": r[0], "char_start": r[1], "char_end": r[2], "heading_path": r[3], "text": r[4], "region_role": r[5],
         "chunk_id": r[6]}
        for r in conn.execute(
            "SELECT chunk_index, char_start, char_end, heading_path, text, region_role, chunk_id FROM chunks "
            "WHERE doc_id=%s AND tier='parent' ORDER BY chunk_index", (doc_id,)).fetchall()]
    terms: list[str] = []
    # GAP-04: the vNext fingerprint derives its own vocabulary, so the vNext path passes
    # want_terms=False and this legacy `document_summaries.major_concepts` read is skipped.
    if want_terms:
        try:
            t = conn.execute("SELECT major_concepts FROM document_summaries WHERE document_id=%s ORDER BY created_at DESC LIMIT 1",
                             (doc_id,)).fetchone()
            if t and t[0]:
                vals = t[0] if isinstance(t[0], list) else json.loads(t[0])
                terms = [str(x.get("name") if isinstance(x, dict) else x) for x in vals][:12]
        except Exception:  # noqa: BLE001 — terms are an optional surface
            terms = []
    return document, parents, terms


def lane_order(pin: list[str], run_key: str, owners: list[list[str]] | None = None) -> list[str]:
    """The pool's attempt order for one run: the PRIMARY lanes (pin entries without "fallback" in the name)
    rotated by a hash of the run so consecutive documents start on different keys, then the fallback lanes in
    pin order (owner 2026-09-07: six dedicated keys as tier 0, Gemini as fallback 1, OpenRouter as fallback 2).

    LLM-BACKEND L3 (register 11.467, gap L-07): when the stage declares ownership (`stage_owners`) and the supervisor
    gave this slot its index, the slot calls ITS OWN key's lane and then the shared fallbacks — never another slot's
    key, so each Groq (key, model) pair has one calling process and that process may spend the whole pair's budget."""
    offset = lane_offset()
    if owners and offset is not None:
        from polymath_shared.llm_extraction.pool import owned_lane_order
        return owned_lane_order(pin, owners, offset, run_key, fallback_mark=FALLBACK_MARK)
    primaries = [n for n in pin if FALLBACK_MARK not in n]
    fallbacks = [n for n in pin if FALLBACK_MARK in n]
    if primaries:
        if offset is not None:
            # DOC-PROFILE-SCALE-OUT-V1: this slot's own key first (doc_profileN → primary N), the rest in order
            start = (offset - 1) % len(primaries)
        else:
            start = int(hashlib.sha256((run_key or "").encode("utf-8")).hexdigest(), 16) % len(primaries)
        primaries = primaries[start:] + primaries[:start]
    return primaries + fallbacks


def lane_offset() -> int | None:
    """1-based primary-lane offset the supervisor gives each profile slot (POLYMATH_DOC_PROFILE_LANE_OFFSET);
    None when unset → rotate by run hash. Measured 2026-09-07: six slots on run-hash rotation collided on keys
    and drew 22 HTTP 429s in five minutes (groq/compound); one key per slot keeps each account at one call in flight."""
    raw = os.environ.get("POLYMATH_DOC_PROFILE_LANE_OFFSET", "").strip()
    if not raw.isdigit() or int(raw) < 1:
        return None
    return int(raw)


def attempt_lanes(pin: list[str], run_key: str, owners: list[list[str]] | None = None) -> list[str]:
    """The lanes ONE pass actually tries: the first PRIMARY_ATTEMPTS rotated primaries, then the fallbacks, capped at
    MAX_LANE_ATTEMPTS — so with six primaries a document still reaches Gemini on its third attempt. An owning slot
    (L3) tries its own lane(s) and the shared tier, capped the same way."""
    order = lane_order(pin, run_key, owners)
    if owners and lane_offset() is not None:
        return order[:MAX_LANE_ATTEMPTS]
    primaries = [n for n in order if FALLBACK_MARK not in n][:PRIMARY_ATTEMPTS]
    fallbacks = [n for n in order if FALLBACK_MARK in n]
    return (primaries + fallbacks)[:MAX_LANE_ATTEMPTS]


def transient_pool_error(pool_rec: dict, err: str | None) -> bool:
    """True when every attempt failed for a transient reason (or nothing could be attempted)."""
    errors = [a.get("error") for a in (pool_rec.get("attempts") or [])] or [err or "no_attempt"]
    return all(bool(_TRANSIENT_ERR.match(str(e or "empty_response"))) for e in errors)


def _pool_complete(system_prompt: str, user_prompt: str, max_tokens: int, run_key: str = "") -> tuple[str, str | None, dict]:
    """The isolated profile pool: walk `lane_order(stage_pin("doc_profile"), run)` — primaries rotated by run,
    fallbacks last. Returns (raw_text, error, receipt). A transport failure on one lane moves to the next."""
    from polymath_shared.llm_extraction.client import LLMExtractionClient
    from polymath_shared.llm_extraction.pool import cloud_endpoints, lane_max_tokens, stage_owners, stage_pin

    pin = stage_pin(STAGE) or []
    by_name = {e.name: e for e in cloud_endpoints() if e.name in pin}
    endpoints = [by_name[n] for n in attempt_lanes(pin, run_key, stage_owners(STAGE)) if n in by_name]
    if not endpoints:
        return "", "no_active_lane", {"attempts": [], "pin": list(pin)}
    attempts: list[dict] = []
    for ep in endpoints:
        t0 = time.perf_counter()
        try:
            client = LLMExtractionClient("cloud", url=ep.url, model=ep.model, limiter_key=ep.limiter_key,
                                         api_key=ep.api_key, cloud_opts=ep.cloud_opts, timeout_s=90.0, max_attempts=1)
            client.endpoint_name = ep.name
            client.attempt_stage, client.attempt_function = STAGE, "PROFILE"   # gap L-17: attributable rows
            raw, err = client.complete_one(user_prompt, system_prompt=system_prompt,
                                           max_tokens=lane_max_tokens(ep, max_tokens))
        except Exception as exc:  # noqa: BLE001 — a lane failure is a receipted attempt, never a crash
            raw, err = "", f"{type(exc).__name__}"
        if not err and not (raw or "").strip():
            err = "empty_response"
        attempts.append({"lane": ep.name, "model": ep.model, "ms": round((time.perf_counter() - t0) * 1000, 1), "error": err})
        if not err:
            return raw, None, {"attempts": attempts, "lane": ep.name, "model": f"{ep.name}:{ep.model}"}
    return "", attempts[-1]["error"] if attempts else "no_attempt", {"attempts": attempts}


def embed_batch_size() -> int:
    """The embedder sidecar rejects (422) a request with more texts than POLYMATH_MAX_BATCH_TEXTS (fleet: 4 since the
    2026-09-07 OOM relief); a profile is ~63 texts, so the worker sends them in slices of that size."""
    try:
        return max(1, int(os.environ.get("POLYMATH_MAX_BATCH_TEXTS", "4")))
    except ValueError:
        return 4


def _embed_texts(texts: list[str], embed_one_batch=None) -> list[list[float]]:
    if embed_one_batch is None:
        from polymath_shared.clients import EmbedderClient
        client = EmbedderClient()
        embed_one_batch = lambda chunk: client.embed(chunk, "doc_profile")  # noqa: E731
    size = embed_batch_size()
    out: list[list[float]] = []
    for i in range(0, len(texts), size):
        resp = embed_one_batch(texts[i:i + size])
        vecs = resp.get("vectors") or resp.get("embeddings")
        if vecs is None:
            raise RuntimeError(f"embedder response without vectors: {sorted(resp.keys())}")
        out.extend(list(v) for v in vecs)
    if len(out) != len(texts):
        raise RuntimeError(f"embedder returned {len(out)} vectors for {len(texts)} texts")
    return out


def _embed_atom_texts(texts: list[str]) -> list[list[float]]:
    """ATOM-REPAIR-V1: atoms are routing hypotheses matched against QUERY vectors, and the live atom collection holds
    query-mode vectors (projected 2026-09-08; measured cos 0.9999 against query-mode re-embeddings). One embedding mode
    per collection — a doc-mode atom would score on a different scale than its neighbours."""
    from polymath_shared.clients import EmbedderClient
    client = EmbedderClient()
    try:
        return _embed_texts(texts, embed_one_batch=lambda chunk: client.embed(chunk, "query"))
    finally:
        client.close()


def _prompt_for(fp, *, vnext: bool) -> tuple[str, str, str, str]:
    """(system, user, prompt_version, builder_version) for a fingerprint-shaped input under the live prompt."""
    if vnext:
        system_prompt, user_prompt = PP.build_vnext_profile_prompt(fp)
        return system_prompt, user_prompt, PP.PROFILE_VNEXT_PROMPT_VERSION, fp.builder_version
    structure, excerpts = GP.base_prompt_blocks(fp)
    return SYSTEM, build_user_prompt(fp.title, structure, excerpts), PROMPT_VERSION, fp.builder_version


def _complete(system_prompt: str, user_prompt: str, run_key: str) -> tuple[str, str | None, dict]:
    complete = HOOKS.get("complete")
    if complete is None:
        return _pool_complete(system_prompt, user_prompt, MAX_OUTPUT_TOKENS, run_key=run_key)
    return complete(system_prompt, user_prompt, MAX_OUTPUT_TOKENS)


def _open_qdrant():
    client = HOOKS.get("qdrant")
    if client is not None:
        return client, False
    from polymath_shared.settings import get_settings
    from qdrant_client import QdrantClient
    return QdrantClient(url=get_settings().stores.qdrant_url, timeout=60), True


def build_section_profiles(tx_factory, *, run_id: str, doc_id: str, corpus_id: str, document: dict,
                           groups: list, vnext: bool, per_pass: int | None = None, force: bool = False,
                           budget_tokens: int = GP.SECTION_BUDGET_TOKENS, client=None) -> dict:
    """F4: build / refresh the SECTION profiles of a giant document — one LLM call, one compile, one profile
    point (`scope: section`, the section's `parent_ids`) and one atom set per section, each committed in its
    own short transaction. Resumable and idempotent: a section whose point already carries this input's hash
    under the live prompt is skipped (unless `force`); at most `per_pass` sections are built per call and the
    rest are reported as `pending`; a transient pool error stops the pass and is reported, never raised.
    Orphan section points (a re-cut document) are purged once every section is done. Returns the receipt the
    stage artifact carries under `doc_profile_sections`."""
    from polymath_shared.document_profile import profile_atom_projection as PAP
    from polymath_shared.embedding_contracts import active_contract
    per_pass = per_pass if per_pass is not None else sections_per_pass()
    contract_obj = active_contract()
    cid, dim = contract_obj.contract_id, contract_obj.dimension
    embed = HOOKS.get("embed") or _embed_texts
    atom_embed = HOOKS.get("embed") or _embed_atom_texts
    owned = client is None
    if owned:
        client, owned = _open_qdrant()
    prompt_ver = PP.PROFILE_VNEXT_PROMPT_VERSION if vnext else PROMPT_VERSION
    rec: dict = {"version": GP.GIANT_PROFILE_VERSION, "threshold": GP.GIANT_PARENT_THRESHOLD, "scope": "section",
                 "sections_total": len(groups), "budget_tokens": budget_tokens, "prompt_version": prompt_ver,
                 "built": [], "skipped": [], "failed": [], "pending": [], "transient_error": None, "orphans_purged": 0}
    try:
        existing = PJ.list_section_points(client, cid, doc_id)
        keys = [g.key for g in groups]
        for i, g in enumerate(groups, start=1):
            fp = GP.build_section_fingerprint(document, g, ordinal=i, total=len(groups), budget_tokens=budget_tokens)
            input_hash = fp.input_hash(g.content_hash())
            title = fp.title
            ex = existing.get(g.key)
            head = {"ordinal": i, "key": g.key, "title": g.title, "heading_path": list(g.heading_path),
                    "parent_count": g.parent_count, "first_parent_id": g.parent_ids[0] if g.parent_ids else None,
                    "last_parent_id": g.parent_ids[-1] if g.parent_ids else None, "input_hash": input_hash}
            if ex and not force and ex.get("input_hash") == input_hash and ex.get("prompt_version") == prompt_ver:
                # the point carries its compiled surfaces, so a pass that skips a section still receipts them
                rec["skipped"].append({**head, "compiled_hash": ex.get("compiled_hash"), "point_id": ex.get("point_id"),
                                       "compiled": ex.get("compiled"), "reason": "unchanged"})
                continue
            if len(rec["built"]) >= per_pass or rec["transient_error"]:
                rec["pending"].append(g.key)
                continue
            system_prompt, user_prompt, _pv, builder_ver = _prompt_for(fp, vnext=vnext)
            raw, err, pool_rec = _complete(system_prompt, user_prompt, run_key=f"{run_id}:{g.key}")
            if err or not (raw or "").strip():
                if transient_pool_error(pool_rec, err):
                    rec["transient_error"] = f"{err} ({len(pool_rec.get('attempts') or [])} lanes tried)"
                    rec["pending"].append(g.key)
                else:
                    rec["failed"].append({**head, "error": err or "empty_response", "attempts": pool_rec.get("attempts")})
                continue
            source_text = "\n".join(p.get("text") or "" for p in g.parents)
            result = C.compile_llm_output(raw, source_text=source_text, grounding_mode="warn")
            r = result.record
            valid, missing = C.profile_valid(r)
            artifact = C.semantic_artifact(r)
            emitted = C.emit(r, doc_id)
            compiled_hash = _sha(artifact)
            entry = {**head, "builder_version": builder_ver, "used_tokens": fp.used_tokens, "model": pool_rec.get("model"),
                     "lane": pool_rec.get("lane"), "attempts": pool_rec.get("attempts"), "raw_response_hash": _sha(raw),
                     "compiled_hash": compiled_hash, "quality": round(result.quality, 3), "ok": result.ok, "valid": valid,
                     "missing": missing, "truncated": result.truncated, "compiled": artifact, "raw": raw[:2000]}
            if not result.ok or not valid:
                rec["failed"].append({**entry, "error": f"DOC_PROFILE_INVALID: ok={result.ok} missing={missing}"})
                continue
            section = {"key": g.key, "title": g.title, "heading_path": g.heading_path, "parent_ids": g.parent_ids,
                       "parent_count": g.parent_count, "ordinal": i}
            existing_surfaces = PJ.fetch_existing_surfaces(client, cid, doc_id, section_key=g.key)
            receipt = PJ.project_profile(
                client, embed=embed, embedding_contract_id=cid, dim=dim, doc_id=doc_id, corpus_id=corpus_id,
                title=title, representations=emitted["representations"],
                payload_extra={"topics": r.topics, "terms": r.terms, "quality": round(result.quality, 3),
                               "source_name": document.get("source_name"), "compiled": artifact},
                existing_surfaces=existing_surfaces, force=force,
                source_doc_hash=g.content_hash(), schema_version=C.SCHEMA_VERSION, prompt_version=prompt_ver,
                compiled_hash=compiled_hash, section=section, input_hash=input_hash)
            entry["projection"] = {k: v for k, v in receipt.items() if k in
                                   ("point_id", "projection_key", "projection_hash", "vectors", "kept_last_known_good",
                                    "selection", "collection")}
            if not receipt.get("kept_last_known_good"):
                try:
                    with tx_factory() as conn:
                        entry["atoms"] = PAP.ingest_section_atoms(
                            conn, client, embed=atom_embed, embedding_contract_id=cid, dim=dim, doc_id=doc_id,
                            corpus_id=corpus_id, compiled=artifact, profile_contract=C.SCHEMA_VERSION,
                            section_key=g.key, parent_ids=g.parent_ids, compiled_hash=compiled_hash)
                except Exception as atom_err:  # noqa: BLE001 — atoms are additive; the projected section point stands
                    entry["atoms"] = {"ok": False, "error": str(atom_err)[:200]}
                    log.warning("doc_profile section atoms failed run=%s doc=%s section=%s err=%s",
                                run_id[:16], doc_id[:16], g.key, atom_err)
            rec["built"].append(entry)
            log.info("doc_profile section done run=%s doc=%s section=%s/%s quality=%.2f lane=%s", run_id[:16],
                     doc_id[:16], i, len(groups), result.quality, pool_rec.get("lane"))
        if not rec["pending"]:
            rec["orphans_purged"] = PJ.purge_section_points(client, cid, doc_id, keep_keys=keys)
    finally:
        if owned:
            client.close()
    return rec


def process_event(conn: Connection, event: dict) -> None:
    run_id = event["run_id"]
    vnext = _vnext_enabled()
    # F4: resolve + load OUTSIDE the stage transaction (the pMAP rule §28: never a transaction across an LLM call),
    # so a giant's section loop commits per section through `tx_factory` while `conn` stays idle.
    doc_id, corpus_id = _resolve_document(conn, run_id)
    document, parents, terms = _load_inputs(conn, doc_id, want_terms=not vnext)
    conn.commit()
    groups = GP.section_groups(parents) if _giant_enabled() else []
    sections_rec: dict | None = None
    if groups:
        from polymath_shared.db import tx as _db_tx
        tx_factory = HOOKS.get("tx") or _db_tx
        sections_rec = build_section_profiles(tx_factory, run_id=run_id, doc_id=doc_id, corpus_id=corpus_id,
                                              document=document, groups=groups, vnext=vnext, force=_force_sections())
        if sections_rec["pending"]:
            done = len(sections_rec["built"]) + len(sections_rec["skipped"])
            log.info("doc_profile sections pending run=%s doc=%s done=%s/%s built=%s transient=%s", run_id[:16],
                     doc_id[:16], done, len(groups), len(sections_rec["built"]), sections_rec["transient_error"])
            raise TransientStageHold(f"DOC_PROFILE_SECTIONS_PENDING: {done}/{len(groups)} done, "
                                     f"{len(sections_rec['pending'])} pending"
                                     + (f", pool: {sections_rec['transient_error']}" if sections_rec["transient_error"] else ""))
    with stage_transaction(conn, run_id=run_id, stage=STAGE, contract_hash=contract()) as writer:
        if groups:
            # F4: a giant's document profile — the stratified sample across ALL sections (never the first pages)
            fp = GP.build_giant_fingerprint(document, parents, groups)
            input_hash = fp.input_hash(document.get("content_hash") or "")
            system_prompt, user_prompt, prompt_ver, builder_ver = _prompt_for(fp, vnext=vnext)
            title = fp.title
            ctx_meta = {"builder_version": fp.builder_version, "title": fp.title, "identity": fp.identity,
                        "used_tokens": fp.used_tokens, "sources": fp.sources, "budget_tokens": fp.budget_tokens}
        elif vnext:
            fp = FP.build_fingerprint(document, parents)   # budget = canary-selected default (500)
            input_hash = fp.input_hash(document.get("content_hash") or "")
            system_prompt, user_prompt = PP.build_vnext_profile_prompt(fp)
            title = fp.title
            prompt_ver, builder_ver = PP.PROFILE_VNEXT_PROMPT_VERSION, FP.FINGERPRINT_BUILDER_VERSION
            ctx_meta = {"builder_version": FP.FINGERPRINT_BUILDER_VERSION, "title": fp.title, "identity": fp.identity,
                        "used_tokens": fp.used_tokens, "sources": fp.sources, "budget_tokens": fp.budget_tokens}
        else:
            ctx = CX.build_context(document, parents, terms=terms, budget_tokens=CONTEXT_BUDGET_TOKENS)
            input_hash = ctx.input_hash(document.get("content_hash") or "")
            system_prompt = SYSTEM
            user_prompt = build_user_prompt(ctx.title, ctx.structure_block, ctx.excerpts_block)
            title = ctx.title
            prompt_ver, builder_ver = PROMPT_VERSION, CX.BUILDER_VERSION
            ctx_meta = {k: v for k, v in ctx.to_dict().items()
                        if k in ("title", "identity", "structure", "used_tokens", "sources", "allocation", "budget_tokens")}

        raw, err, pool_rec = _complete(system_prompt, user_prompt, run_key=run_id)
        if err or not (raw or "").strip():
            tried = len(pool_rec.get("attempts") or [])
            log.warning("doc_profile pool failed run=%s doc=%s err=%s attempts=%s",
                        run_id[:16], doc_id[:16], err, json.dumps(pool_rec.get("attempts"))[:300])
            if transient_pool_error(pool_rec, err):
                # rate/size-limited or dark: hand the ticket back without consuming an attempt (TRANSIENT-HOLD-V1)
                raise TransientStageHold(f"DOC_PROFILE_POOL_UNAVAILABLE: {err} ({tried} lanes tried)")
            raise RuntimeError(f"DOC_PROFILE_POOL_FAILED: {err} ({tried} lanes tried)")

        source_text = "\n".join(p.get("text") or "" for p in parents)
        result = C.compile_llm_output(raw, source_text=source_text, grounding_mode="warn")
        rec = result.record
        valid, missing = C.profile_valid(rec)
        artifact = C.semantic_artifact(rec)
        emitted = C.emit(rec, doc_id)
        compiled_hash = _sha(artifact)
        profile_record = {
            "doc_id": doc_id, "corpus_id": corpus_id,
            "schema_version": C.SCHEMA_VERSION, "prompt_version": prompt_ver, "compiler_version": C.COMPILER_VERSION,
            "builder_version": builder_ver, "vnext": vnext, "model": pool_rec.get("model"), "lane": pool_rec.get("lane"),
            "attempts": pool_rec.get("attempts"),
            "content_hash": document.get("content_hash"), "input_hash": input_hash, "raw_response_hash": _sha(raw),
            "compiled_hash": compiled_hash,
            "quality": round(result.quality, 3), "format_quality": round(result.format_quality, 3),
            "coverage_quality": round(result.coverage_quality, 3), "ok": result.ok, "valid": valid, "missing": missing,
            "truncated": result.truncated,
            "issues": [{"severity": i.severity, "code": i.code, "message": i.message[:160]} for i in result.issues][:24],
            "context": ctx_meta,
            "raw": raw[:8000], "compiled": artifact, "representations": emitted["representations"],
            **({"giant": True, "sections": len(groups)} if groups else {}),
        }
        writer.artifact({"doc_profile": profile_record})
        if sections_rec is not None:
            writer.artifact({"doc_profile_sections": sections_rec})
        if not result.ok or not valid:
            raise RuntimeError(f"DOC_PROFILE_INVALID: ok={result.ok} missing={missing} quality={result.quality:.2f}")

        # projection — its own collection, one point per document, one vector per atomic unit
        from polymath_shared.embedding_contracts import active_contract
        contract_obj = active_contract()
        embed = HOOKS.get("embed") or _embed_texts
        client, owned = _open_qdrant()
        atom_receipt = None
        try:
            # CANONICAL-PROFILE-SELECTION-V1 (checklist P4): fetch the active point's surface
            # counts so the projector can refuse a thinner overwrite of a richer last-known-good.
            existing_surfaces = PJ.fetch_existing_surfaces(client, contract_obj.contract_id, doc_id)
            receipt = PJ.project_profile(
                client, embed=embed, embedding_contract_id=contract_obj.contract_id, dim=contract_obj.dimension,
                doc_id=doc_id, corpus_id=corpus_id, title=title, representations=emitted["representations"],
                payload_extra={"topics": rec.topics, "terms": rec.terms, "quality": round(result.quality, 3),
                               "source_name": document.get("source_name")},
                existing_surfaces=existing_surfaces,
                source_doc_hash=document.get("content_hash") or "", schema_version=C.SCHEMA_VERSION,
                prompt_version=prompt_ver, compiled_hash=compiled_hash, input_hash=input_hash)
            if not receipt.get("kept_last_known_good"):
                # PROFILE-ATOM ingest wiring (checklist P4a): the addressable atom lane is now
                # pipeline-maintained (not canary). Atoms track the projected profile; skip on a
                # kept last-known-good (the richer atoms stand). Additive + best-effort — a
                # transient atom failure must never fail the already-projected profile.
                try:
                    from polymath_shared.document_profile import profile_atom_projection as PAP
                    from polymath_shared.document_profile import profile_atom as PA
                    # ATOM-REPAIR-V1: family-scoped supersession (a vNext profile keeps the base atoms and vice
                    # versa, owner D4 "alongside") + the collection's query-mode embedding
                    atom_receipt = PAP.ingest_document_atoms(
                        conn, client, embed=HOOKS.get("embed") or _embed_atom_texts,
                        embedding_contract_id=contract_obj.contract_id,
                        dim=contract_obj.dimension, doc_id=doc_id, corpus_id=corpus_id,
                        compiled=artifact, profile_contract=C.SCHEMA_VERSION,
                        source=PA.source_tag("vnext" if vnext else "base", compiled_hash))
                except Exception as _atom_err:
                    atom_receipt = {"ok": False, "error": str(_atom_err)[:200]}
                    log.warning("doc_profile atom ingest failed run=%s doc=%s err=%s",
                                run_id[:16], doc_id[:16], _atom_err)
        finally:
            if owned:
                client.close()
        if receipt.get("kept_last_known_good"):
            # The incoming profile was thinner than the active last-known-good projection; the
            # richer point stands. This is a success, not a failure — do not run the vector gate.
            writer.artifact({"doc_profile_qdrant": {**receipt, "compiled_hash": compiled_hash}})
            sel = receipt.get("selection") or {}
            log.info("doc_profile kept last-known-good run=%s doc=%s reason=%s existing=%s incoming=%s",
                     run_id[:16], doc_id[:16], sel.get("reason"), sel.get("existing"), sel.get("incoming"))
            return
        vec_ok, vmissing = PJ.has_required_vectors(receipt)
        writer.artifact({"doc_profile_qdrant": {**receipt, "valid": vec_ok, "missing": vmissing, "compiled_hash": compiled_hash}})
        if atom_receipt is not None:
            writer.artifact({"doc_profile_atoms": {**atom_receipt, "compiled_hash": compiled_hash}})
        if not vec_ok:
            raise RuntimeError(f"DOC_PROFILE_VECTORS_INCOMPLETE: {vmissing}")
        log.info("doc_profile done run=%s doc=%s quality=%.2f vectors=%s atoms=%s lane=%s sections=%s", run_id[:16],
                 doc_id[:16], result.quality, receipt.get("vectors"), (atom_receipt or {}).get("active"),
                 pool_rec.get("lane"), len(groups))


def main() -> None:
    configure_logging("doc_profile")
    run_worker("doc_profile", [EVENT_TYPE], process_event)


if __name__ == "__main__":
    main()
