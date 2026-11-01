"""PRODUCT LIBRARY ROUTING (product-library-routing-v1): a product turn whose resolved scope holds several libraries is ROUTED to the
best one before retrieval, instead of the runtime's 422 `mode_requires_single_corpus` (the owner: "it should be able to use any
corpus"; agents never guess the library).

This is the document skeleton's ROUTER job (DOCUMENT-SKELETON-V1 §3: profiles find documents and libraries; their text is never
hydrated): ONE embedding of the request, ONE Qdrant query over the document profile collection
(`polymath_document_profiles_<active embedding contract>`; the same answer surfaces `profile_nominate` fuses by RRF, document
points only, filtered to the caller's resolved libraries by the `corpus_id` payload), then each library scores the reciprocal ranks
(1 / (RRF_K + rank)) of its best PER_CORPUS documents, each document counted once. The top library is chosen and the runner-up
recorded. No profile for any candidate (or the profile query failed) → the library with the most query-ready documents; nothing
countable either → the first candidate by id. Every outcome is receipted (`candidates, chosen, runner_up, scores, method, notes`).
A single library skips routing (`method: single`). Pure apart from the injected embedder, Qdrant client and readiness counter."""
from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from typing import Any

CONTRACT = "product-library-routing-v1"
TOP_DOCS = 30            # documents read from the one profile query
PER_CORPUS = 3           # a library scores its best three documents
RRF_K = 60
METHODS = ("single", "profile_rrf", "most_query_ready_documents", "first_candidate")


def aggregate(points: Iterable[Any], candidates: list[str]) -> tuple[dict[str, float], int]:
    """({library: score}, documents read): reciprocal-rank fusion of the fused profile ranking per library — each document once,
    at its best rank; a library scores its best PER_CORPUS documents. Libraries without a document are absent."""
    per: dict[str, list[float]] = {c: [] for c in candidates}
    seen: set[str] = set()
    rank = 0
    for p in points:
        payload = (getattr(p, "payload", None) if not isinstance(p, Mapping) else p.get("payload")) or {}
        corpus, doc = payload.get("corpus_id"), payload.get("doc_id")
        if corpus not in per or not doc or doc in seen:
            continue
        seen.add(doc)
        rank += 1
        if len(per[corpus]) < PER_CORPUS:
            per[corpus].append(1.0 / (RRF_K + rank))
    return {c: round(sum(v), 6) for c, v in per.items() if v}, rank


def query_profiles(client, collection: str, query_vec, candidates: list[str], *, role_scope=None, limit: int = TOP_DOCS) -> list:
    """ONE query over the profile collection: the answer surfaces fused by RRF server-side, document points only, filtered to the
    candidate libraries (and to the knowledge-role scope when one is set)."""
    from qdrant_client.http import models as qm

    from polymath_shared.code.scope import scope_or_all
    from polymath_shared.document_profile.projection import ANSWER_SURFACES, SCOPE_SECTION
    from polymath_shared.surface_registry import MULTI_SURFACES
    flt = qm.Filter(must=[qm.FieldCondition(key="corpus_id", match=qm.MatchAny(any=list(candidates)))],
                    must_not=[qm.FieldCondition(key="scope", match=qm.MatchValue(value=SCOPE_SECTION))])
    flt = scope_or_all(role_scope).apply(flt)
    v = list(query_vec)
    prefetch = [qm.Prefetch(query=([v] if s in MULTI_SURFACES else v), using=s, limit=limit, filter=flt) for s in ANSWER_SURFACES]
    res = client.query_points(collection, prefetch=prefetch, query=qm.FusionQuery(fusion=qm.Fusion.RRF), limit=limit,
                              with_payload=["doc_id", "corpus_id"])
    return list(getattr(res, "points", None) or [])


def make_client():
    """The production Qdrant client and the active contract's profile collection."""
    from qdrant_client import QdrantClient

    from polymath_shared.document_profile.projection import collection_name
    from polymath_shared.embedding_contracts import active_contract
    from polymath_shared.settings import get_settings
    return QdrantClient(url=get_settings().stores.qdrant_url, timeout=10), collection_name(active_contract().contract_id)


def ready_counts(candidates: list[str]) -> dict[str, dict[str, int]]:
    """{library: {documents, query_ready_runs}} from Postgres (two indexed aggregates per library)."""
    from polymath_shared.db import tx
    with tx() as conn:
        rows = conn.execute(
            """SELECT c.corpus_id,
                      (SELECT COUNT(*) FROM documents d WHERE d.corpus_id = c.corpus_id),
                      (SELECT COUNT(*) FROM runs r WHERE r.corpus_id = c.corpus_id AND r.status = 'query_ready')
                 FROM corpora c WHERE c.corpus_id = ANY(%s)""", (list(candidates),)).fetchall()
    return {str(r[0]): {"documents": int(r[1] or 0), "query_ready_runs": int(r[2] or 0)} for r in rows}


def _ready_score(row: Mapping[str, int] | None) -> int:
    """Query-ready documents of a library: its documents when it has a query-ready run, else none."""
    row = row or {}
    return int(row.get("documents") or 0) if int(row.get("query_ready_runs") or 0) > 0 else 0


def route_library(message: str, candidates: Iterable[str], *, embed: Callable[[list[str]], list] | None = None,
                  client=None, collection: str | None = None, client_factory: Callable[[], tuple[Any, str]] | None = None,
                  counts: Callable[[list[str]], Mapping[str, Mapping[str, int]]] | None = None, role_scope=None) -> dict[str, Any]:
    """The routing receipt: {contract, candidates, chosen, runner_up, scores, method, notes[, documents_read | counts]}."""
    cands = list(dict.fromkeys(str(c) for c in candidates if c))
    out: dict[str, Any] = {"contract": CONTRACT, "candidates": cands, "chosen": cands[0] if cands else None, "runner_up": None,
                           "scores": {}, "method": "single", "notes": []}
    if len(cands) <= 1:
        return out
    notes: list[str] = []
    scores: dict[str, float] = {}
    read = 0
    if embed is None:
        notes.append("no embedder was given: the profile query did not run")
    else:
        own_client = client is None
        try:
            if own_client:
                client, collection = (client_factory or make_client)()
            points = query_profiles(client, str(collection), list(embed([message])[0]), cands, role_scope=role_scope)
            scores, read = aggregate(points, cands)
            if not scores:
                notes.append("no document profile of any candidate library matched the request")
        except Exception as exc:  # noqa: BLE001 — routing degrades to the readiness fallback, receipted
            notes.append(f"the profile query failed ({type(exc).__name__}: {str(exc)[:120]})")
        finally:
            if own_client and client is not None and hasattr(client, "close"):
                try:
                    client.close()
                except Exception:  # noqa: BLE001
                    pass
    if scores:
        ranked = sorted(cands, key=lambda c: (-scores.get(c, 0.0), cands.index(c)))
        return {**out, "chosen": ranked[0], "runner_up": ranked[1], "scores": {c: scores.get(c, 0.0) for c in ranked},
                "method": "profile_rrf", "documents_read": read, "notes": notes}
    table: Mapping[str, Mapping[str, int]] = {}
    try:
        table = (counts or ready_counts)(cands)
    except Exception as exc:  # noqa: BLE001
        notes.append(f"the readiness count failed ({type(exc).__name__}: {str(exc)[:120]})")
    ready = {c: _ready_score(table.get(c)) for c in cands}
    if any(ready.values()):
        ranked = sorted(cands, key=lambda c: (-ready[c], cands.index(c)))
        return {**out, "chosen": ranked[0], "runner_up": ranked[1], "scores": {c: ready[c] for c in ranked},
                "method": "most_query_ready_documents", "counts": {c: dict(table.get(c) or {}) for c in cands}, "notes": notes}
    ranked = sorted(cands)
    return {**out, "chosen": ranked[0], "runner_up": ranked[1], "method": "first_candidate",
            "notes": notes + ["nothing ranked the candidate libraries: the first by id was taken"]}
