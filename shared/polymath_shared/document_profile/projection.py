"""DOCUMENT-PROFILE-V1 step 4 — the profile vector projection (owner spec 2026-09-07).

One point per document in its OWN collection (`polymath_document_profiles_<embedding contract>`), never mixed
with the chunk points: named dense vectors `title`, `identity`, `theme` and named MULTIVECTORS `questions`,
`searches`, `theories`, `concepts`, `seealso` (one vector per atomic unit, MaxSim at query time). TERM is not a
dense vector. The compiler produces semantic units; this module produces vectors — from an injected `embed`
(production wires the embedder sidecar, tests wire a deterministic stub) and an injected Qdrant client.

`projection_key = hash(source_doc_hash, schema, prompt_version, embedding contract)` — change chunking and
nothing here moves; change the embedding model and only this re-runs. The projection receipt closes the chain:
content hash → input hash → raw response hash → compiled hash → PROJECTION HASH.
"""
from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import Callable, Sequence
from typing import Any

from .selection import SELECTION_VERSION, select as _select
from polymath_shared.surface_registry import DENSE_SURFACES, MULTI_SURFACES  # single source (P4a)

PROJECTION_VERSION = "doc-profile-projection-v1"
COLLECTION_PREFIX = "polymath_document_profiles"
#: normal answer retrieval prefetches these; `seealso` (and by default theories / concepts) belong to exploration
ANSWER_SURFACES = ("identity", "theme", "questions", "searches", "title")
EXPLORATION_SURFACES = ("seealso", "theories", "concepts")
#: FACET-RETRIEVAL-V1 F4: a point's `scope` payload — the document's own profile, or ONE SECTION of a giant
#: document (plan §3.4). A point without the field is a document point (every point projected before F4).
SCOPE_DOCUMENT = "document"
SCOPE_SECTION = "section"
#: F4: `profile_nominate` runs the document points' query exactly as before F4 and a SECOND query over the section
#: points alone (this many times `k` points, collapsed onto their documents), then merges the two by fused score. A
#: giant's sections can neither crowd other documents out of the document query nor vote more than once.
NOMINATE_OVERFETCH = 4


def collection_name(embedding_contract_id: str) -> str:
    return f"{COLLECTION_PREFIX}_{embedding_contract_id}"


def point_id(doc_id: str) -> str:
    """Stable UUID per document (Qdrant ids are ints or UUIDs)."""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"polymath:doc_profile:{doc_id}"))


def section_point_id(doc_id: str, section_key: str) -> str:
    """Stable UUID per (document, section): a rebuilt section REPLACES its point (F4)."""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"polymath:doc_profile:{doc_id}#section:{section_key}"))


def profile_nominate(client, collection: str, query_vec, corpus_id: str, k: int = 8,
                     *, surfaces: tuple[str, ...] = ANSWER_SURFACES, scope=None) -> list[str]:
    """RRF nomination over the profile collection → ordered doc_ids (the S8/S9 door).

    The SAME surfaces the self-retrieval gate qualified: dense `identity`/`theme`/`title`
    + `questions`/`searches` multivectors, fused by RRF, filtered to the corpus. Read-only
    — this is the reusable profile-search contract the shadow canary and the live dual-read
    lane both nominate through.

    F4 (giant documents): the document points are queried exactly as before, and the SECTION points
    (`scope: section`, plan §3.4) in a second query of their own, `NOMINATE_OVERFETCH × k` deep, each
    document counted once at its best section; the two lists merge by fused RRF score (ties keep the
    document query's order). A collection without section points nominates byte-identically to pre-F4."""
    from qdrant_client.http import models as qm
    from polymath_shared.code.scope import scope_or_all
    corpus = qm.FieldCondition(key="corpus_id", match=qm.MatchValue(value=corpus_id))
    is_section = qm.FieldCondition(key="scope", match=qm.MatchValue(value=SCOPE_SECTION))
    v = list(query_vec)

    def _fused(flt, fetch: int) -> list[tuple[str, float]]:
        flt = scope_or_all(scope).apply(flt)      # K1: the knowledge-role scope rides every prefetch
        pre = [qm.Prefetch(query=([v] if s in MULTI_SURFACES else v), using=s, limit=fetch, filter=flt)
               for s in surfaces]
        res = client.query_points(collection, prefetch=pre, query=qm.FusionQuery(fusion=qm.Fusion.RRF),
                                  limit=fetch, with_payload=["doc_id"])
        return [((p.payload or {}).get("doc_id"), float(getattr(p, "score", 0.0) or 0.0)) for p in res.points]

    # 1. the document points — the query exactly as before F4 (a point without `scope` is a document point)
    docs_q = _fused(qm.Filter(must=[corpus], must_not=[is_section]), k)
    # 2. F4: the section points of giant documents, in a pool of their own, collapsed onto their documents
    sec_q = _fused(qm.Filter(must=[corpus, is_section]), max(1, int(k)) * NOMINATE_OVERFETCH)
    best: dict[str, float] = {}
    order: list[str] = []
    for d, score in docs_q + sec_q:
        if not d:
            continue
        if d not in best:
            best[d] = score
            order.append(d)
        elif score > best[d]:
            best[d] = score
    ranked = sorted(order, key=lambda d: (-best[d], order.index(d)))
    return ranked[:k]


def projection_key(*, source_doc_hash: str, schema_version: str, prompt_version: str, embedding_contract_id: str) -> str:
    return hashlib.sha256(json.dumps({"doc": source_doc_hash, "schema": schema_version, "prompt": prompt_version,
                                      "embedding": embedding_contract_id, "projection": PROJECTION_VERSION},
                                     sort_keys=True).encode()).hexdigest()


def vectors_config(dim: int):
    """Named dense + multivector config (qdrant ≥ 1.10; measured 1.13.4)."""
    from qdrant_client.http import models as qm
    cfg: dict[str, Any] = {s: qm.VectorParams(size=dim, distance=qm.Distance.COSINE) for s in DENSE_SURFACES}
    for s in MULTI_SURFACES:
        cfg[s] = qm.VectorParams(size=dim, distance=qm.Distance.COSINE,
                                 multivector_config=qm.MultiVectorConfig(comparator=qm.MultiVectorComparator.MAX_SIM))
    return cfg


def ensure_collection(client, name: str, dim: int) -> bool:
    """Create the profile collection when absent. Returns True when created."""
    if client.collection_exists(name):
        return False
    client.create_collection(collection_name=name, vectors_config=vectors_config(dim))
    return True


def texts_to_embed(title: str, representations: dict[str, Any]) -> list[tuple[str, int | None, str]]:
    """(surface, index-or-None, text) in a fixed order — the batch the embedder receives."""
    out: list[tuple[str, int | None, str]] = []
    if (title or "").strip():
        out.append(("title", None, title.strip()))
    for s in ("identity", "theme"):
        v = str(representations.get(s) or "").strip()
        if v:
            out.append((s, None, v))
    for s in MULTI_SURFACES:
        for i, item in enumerate(representations.get(s) or []):
            it = str(item or "").strip()
            if it:
                out.append((s, i, it))
    return out


def build_point_vectors(batch: list[tuple[str, int | None, str]], vectors: list[list[float]]) -> dict[str, Any]:
    """Named vectors for the point: str surfaces → one vector, list surfaces → a list of vectors (multivector)."""
    if len(batch) != len(vectors):
        raise ValueError(f"embedded {len(vectors)} vectors for {len(batch)} texts")
    named: dict[str, Any] = {}
    for (surface, idx, _text), vec in zip(batch, vectors):
        if idx is None:
            named[surface] = list(vec)
        else:
            named.setdefault(surface, []).append(list(vec))
    return named


def section_payload(section: dict) -> dict[str, Any]:
    """The payload fields a SECTION point carries beside the document fields (F4): the scope marker, the
    section's stable key / title / heading path, and the durable ids of the parents it stands for — so a lane
    that lands on the point can name the document AND the section."""
    return {"scope": SCOPE_SECTION,
            "section_key": str(section["key"]),
            "section_title": str(section.get("title") or ""),
            "heading_path": [str(x) for x in (section.get("heading_path") or ())],
            "parent_ids": [str(x) for x in (section.get("parent_ids") or ())],
            "parent_count": int(section.get("parent_count") or len(section.get("parent_ids") or ())),
            "section_ordinal": int(section.get("ordinal") or 0)}


def project_profile(client, *, embed: Callable[[list[str]], list[list[float]]], embedding_contract_id: str, dim: int,
                    doc_id: str, corpus_id: str, title: str, representations: dict[str, Any], payload_extra: dict | None = None,
                    existing_surfaces: dict[str, int] | None = None, force: bool = False,
                    source_doc_hash: str, schema_version: str, prompt_version: str, compiled_hash: str,
                    section: dict | None = None, input_hash: str | None = None) -> dict[str, Any]:
    """Embed every atomic unit once and upsert the document's single multi-representation point. Returns the
    projection receipt (no vectors inside — counts, hashes, collection, point id).

    F4: with `section` ({key, title, heading_path, parent_ids, parent_count, ordinal}) the point is that SECTION's
    profile point (`section_point_id`, payload `scope: section` + the section fields, still the document's
    `doc_id` / `corpus_id`), projected beside the document point in the same collection so every lane that
    nominates through this collection reads it. `input_hash` (the prompt input's hash) rides the payload when
    given, so a rebuild can skip a section whose input has not changed."""
    from qdrant_client.http import models as qm
    name = collection_name(embedding_contract_id)
    created = ensure_collection(client, name, dim)
    batch = texts_to_embed(title, representations)
    if not batch:
        raise ValueError("nothing to project: the profile has no embeddable surface")
    vectors = embed([t for _, _, t in batch])
    named = build_point_vectors(batch, vectors)
    new_counts = {s: (len(v) if isinstance(v, list) and v and isinstance(v[0], list) else 1) for s, v in named.items()}
    pkey = projection_key(source_doc_hash=source_doc_hash, schema_version=schema_version,
                          prompt_version=prompt_version, embedding_contract_id=embedding_contract_id)
    pid = section_point_id(doc_id, str(section["key"])) if section else point_id(doc_id)
    scope_fields = section_payload(section) if section else {"scope": SCOPE_DOCUMENT}
    # CANONICAL-PROFILE-SELECTION-V1: never let a thinner profile silently overwrite a richer
    # last-known-good projection (checklist P4). `existing_surfaces` is the active point's counts
    # (the worker fetches them); default None preserves first-projection / caller behaviour.
    decision = _select(existing_surfaces, new_counts, force=force)
    if not decision.replace:
        return {"projection": PROJECTION_VERSION, "collection": name, "created_collection": created,
                "point_id": pid, "projection_key": pkey, "projection_hash": None,
                "embedding_contract": embedding_contract_id, "dim": dim, "vectors": {}, "texts_embedded": len(batch),
                "kept_last_known_good": True, "scope": scope_fields["scope"],
                "section_key": scope_fields.get("section_key"),
                "selection": {"reason": decision.reason, "existing": decision.existing,
                              "incoming": decision.incoming, "version": SELECTION_VERSION}}
    payload = {"doc_id": doc_id, "corpus_id": corpus_id, "title": title, "schema_version": schema_version,
               "prompt_version": prompt_version, "embedding_contract": embedding_contract_id,
               "projection_key": pkey, "compiled_hash": compiled_hash, "source_doc_hash": source_doc_hash,
               "surfaces": new_counts,
               **scope_fields,
               **({"input_hash": input_hash} if input_hash else {}),
               **(payload_extra or {})}
    client.upsert(collection_name=name, points=[qm.PointStruct(id=pid, vector=named, payload=payload)], wait=True)
    counts = new_counts
    projection_hash = hashlib.sha256(json.dumps({"key": pkey, "point": pid, "counts": counts,
                                                 "texts": [t for _, _, t in batch]}, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    return {"projection": PROJECTION_VERSION, "collection": name, "created_collection": created, "point_id": pid,
            "projection_key": pkey, "projection_hash": projection_hash, "embedding_contract": embedding_contract_id,
            "dim": dim, "vectors": counts, "texts_embedded": len(batch), "kept_last_known_good": False,
            "scope": scope_fields["scope"], "section_key": scope_fields.get("section_key"),
            "selection": {"reason": decision.reason, "existing": decision.existing,
                          "incoming": decision.incoming, "version": SELECTION_VERSION}}


def has_required_vectors(receipt: dict[str, Any]) -> tuple[bool, list[str]]:
    """The projector's half of the readiness contract: identity + theme + at least one Q/SEARCH vector."""
    v = receipt.get("vectors") or {}
    missing = []
    if not v.get("identity"):
        missing.append("identity_vector")
    if not v.get("theme"):
        missing.append("theme_vector")
    if not (v.get("questions") or v.get("searches")):
        missing.append("query_hook_vector")
    return (not missing), missing


#: the payload fields a rebuild reads back from an existing point (F4: the skip-unchanged check)
EXISTING_POINT_FIELDS = ("surfaces", "input_hash", "prompt_version", "compiled_hash", "scope", "section_key",
                         "section_title", "parent_count", "compiled")


def fetch_existing_point(client, embedding_contract_id: str, doc_id: str, *, section_key: str | None = None,
                         fields: tuple[str, ...] = EXISTING_POINT_FIELDS) -> dict[str, Any] | None:
    """The active point's payload (the document point, or the section's point with `section_key`), or None
    when absent. Defensive like `fetch_existing_surfaces`: any store/transport error → None."""
    try:
        name = collection_name(embedding_contract_id)
        if not client.collection_exists(name):
            return None
        pid = section_point_id(doc_id, section_key) if section_key else point_id(doc_id)
        pts = client.retrieve(collection_name=name, ids=[pid], with_payload=list(fields), with_vectors=False)
        if not pts:
            return None
        payload = getattr(pts[0], "payload", None) or {}
        return dict(payload) if isinstance(payload, dict) else None
    except Exception:
        return None


def fetch_existing_surfaces(client, embedding_contract_id: str, doc_id: str,
                            *, section_key: str | None = None) -> dict[str, int] | None:
    """The active profile point's per-surface counts (for the CANONICAL-PROFILE-SELECTION guard),
    or None when there is no active point. Defensive: any store/transport error → None (treated as
    "no existing" → the new profile projects), so the guard can never wedge ingestion.
    F4: `section_key` reads the section's point instead of the document's."""
    payload = fetch_existing_point(client, embedding_contract_id, doc_id, section_key=section_key, fields=("surfaces",))
    if not payload:
        return None
    surfaces = payload.get("surfaces")
    return {str(k): int(v) for k, v in surfaces.items()} if isinstance(surfaces, dict) else None


def _section_filter(doc_id: str, *, exclude_keys: Sequence[str] | None = None):
    from qdrant_client.http import models as qm
    must = [qm.FieldCondition(key="doc_id", match=qm.MatchValue(value=doc_id)),
            qm.FieldCondition(key="scope", match=qm.MatchValue(value=SCOPE_SECTION))]
    must_not = None
    keep = [str(k) for k in (exclude_keys or ()) if k]
    if keep:
        must_not = [qm.FieldCondition(key="section_key", match=qm.MatchAny(any=keep))]
    return qm.Filter(must=must, must_not=must_not)


def list_section_points(client, embedding_contract_id: str, doc_id: str,
                        *, fields: tuple[str, ...] = EXISTING_POINT_FIELDS) -> dict[str, dict[str, Any]]:
    """The document's SECTION points, `section_key` → payload (F4). Read-only; {} when the collection is absent."""
    name = collection_name(embedding_contract_id)
    if not client.collection_exists(name):
        return {}
    out: dict[str, dict[str, Any]] = {}
    offset = None
    while True:
        pts, offset = client.scroll(collection_name=name, scroll_filter=_section_filter(doc_id), limit=256,
                                    with_payload=list(fields), with_vectors=False, offset=offset)
        for p in pts or ():
            payload = getattr(p, "payload", None) or {}
            key = payload.get("section_key")
            if key:
                out[str(key)] = {**payload, "point_id": str(getattr(p, "id", ""))}
        if not pts or offset is None:
            break
    return out


def purge_section_points(client, embedding_contract_id: str, doc_id: str, *, keep_keys: Sequence[str] | None = None) -> int:
    """Delete the document's section points — all of them, or only those whose `section_key` is NOT in
    `keep_keys` (the orphans of a re-cut document). Returns the number removed."""
    from qdrant_client.http import models as qm
    name = collection_name(embedding_contract_id)
    if not client.collection_exists(name):
        return 0
    flt = _section_filter(doc_id, exclude_keys=keep_keys)
    before = int(client.count(name, count_filter=flt, exact=True).count)
    if before:
        client.delete(collection_name=name, points_selector=qm.FilterSelector(filter=flt), wait=True)
    return before
