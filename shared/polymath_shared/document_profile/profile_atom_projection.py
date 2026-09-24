"""PROFILE-ATOM projection — one dense point per Profile Atom in its OWN contract-named
collection (§34 "one atom = one dense vector"; §14 additive, never mutate other collections).

Postgres `document_profile_atoms` is the authority; this collection is a rebuildable cache of
its ACTIVE rows. `reconcile()` is the §14 gate: projected point count == active atom count.
The atom lane searches this collection (`search_atoms`) filtered by atom kind — a routing/
expansion lookup that never returns factual evidence, only nominated (doc, atom) routes.
"""
from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import Callable, Sequence

from polymath_shared.document_profile.profile_atom import ProfileAtom, atom_id  # noqa: F401

PROJECTION_VERSION = "profile-atom-projection-v1"
COLLECTION_PREFIX = "polymath_document_profile_atoms"
VECTOR_NAME = "atom"
#: the embedder sidecar rejects large single requests (measured: 32 ok, 64 fails); batch it.
EMBED_BATCH = 32


def _embed_batched(embed: Callable[[list[str]], list[list[float]]], texts: list[str]) -> list[list[float]]:
    out: list[list[float]] = []
    for i in range(0, len(texts), EMBED_BATCH):
        out.extend(embed(texts[i:i + EMBED_BATCH]))
    return out


def collection_name(embedding_contract_id: str) -> str:
    return f"{COLLECTION_PREFIX}_{embedding_contract_id}"


def point_id(atom_id: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"polymath:profile_atom:{atom_id}"))


def vectors_config(dim: int):
    from qdrant_client.http import models as qm
    return {VECTOR_NAME: qm.VectorParams(size=dim, distance=qm.Distance.COSINE)}


def build_payload(atom: ProfileAtom) -> dict:
    return {"doc_id": atom.doc_id, "corpus_id": atom.corpus_id, "atom_kind": atom.kind,
            "text": atom.text, "ordinal": atom.ordinal, "atom_id": atom.atom_id}


def ensure_collection(client, name: str, dim: int) -> bool:
    if client.collection_exists(name):
        return False
    client.create_collection(collection_name=name, vectors_config=vectors_config(dim))
    return True


def project_atoms(client, *, embed: Callable[[list[str]], list[list[float]]],
                  embedding_contract_id: str, dim: int, atoms: Sequence[ProfileAtom]) -> dict:
    """Embed each atom's text once and upsert one point per atom. Returns the projection
    receipt (counts, collection, point ids, hash — no vectors)."""
    from qdrant_client.http import models as qm
    name = collection_name(embedding_contract_id)
    created = ensure_collection(client, name, dim)
    atoms = list(atoms)
    if not atoms:
        return {"projection": PROJECTION_VERSION, "collection": name, "created_collection": created,
                "points": 0, "point_ids": [], "projection_hash": hashlib.sha256(b"").hexdigest()}
    vectors = _embed_batched(embed, [a.text for a in atoms])
    points, pids = [], []
    for a, v in zip(atoms, vectors):
        pid = point_id(a.atom_id)
        pids.append(pid)
        points.append(qm.PointStruct(id=pid, vector={VECTOR_NAME: list(v)}, payload=build_payload(a)))
    client.upsert(collection_name=name, points=points, wait=True)
    phash = hashlib.sha256(json.dumps({"collection": name, "points": sorted(pids)}, sort_keys=True).encode()).hexdigest()
    return {"projection": PROJECTION_VERSION, "collection": name, "created_collection": created,
            "points": len(points), "point_ids": pids, "projection_hash": phash}


def projected_count(client, embedding_contract_id: str, corpus_id: str | None = None) -> int:
    from qdrant_client.http import models as qm
    name = collection_name(embedding_contract_id)
    if not client.collection_exists(name):
        return 0
    flt = None
    if corpus_id is not None:
        flt = qm.Filter(must=[qm.FieldCondition(key="corpus_id", match=qm.MatchValue(value=corpus_id))])
    return client.count(name, count_filter=flt, exact=True).count


def reconcile(conn, client, *, corpus_id: str, embedding_contract_id: str) -> dict:
    """§14 gate: active atom count (Postgres) == projected point count (Qdrant), per corpus."""
    from polymath_shared.document_profile.profile_atom import active_atom_count
    active = active_atom_count(conn, corpus_id=corpus_id)
    projected = projected_count(client, embedding_contract_id, corpus_id=corpus_id)
    return {"corpus_id": corpus_id, "active_atoms": active, "projected_points": projected,
            "reconciled": active == projected}


def purge(client, embedding_contract_id: str, corpus_id: str) -> int:
    """Delete a corpus's projected atom points (rebuildable). Returns points removed."""
    from qdrant_client.http import models as qm
    name = collection_name(embedding_contract_id)
    if not client.collection_exists(name):
        return 0
    before = projected_count(client, embedding_contract_id, corpus_id=corpus_id)
    client.delete(collection_name=name, points_selector=qm.FilterSelector(
        filter=qm.Filter(must=[qm.FieldCondition(key="corpus_id", match=qm.MatchValue(value=corpus_id))])), wait=True)
    return before


def purge_doc(client, embedding_contract_id: str, doc_id: str) -> int:
    """Delete ONE document's projected atom points (the per-doc analogue of `purge`, for the
    ingest DAG: a fresh profile supersedes a doc's atoms, so drop its old points before
    projecting the new set → the collection stays == the doc's ACTIVE rows). Returns removed."""
    from qdrant_client.http import models as qm
    name = collection_name(embedding_contract_id)
    if not client.collection_exists(name):
        return 0
    flt = qm.Filter(must=[qm.FieldCondition(key="doc_id", match=qm.MatchValue(value=doc_id))])
    before = client.count(name, count_filter=flt, exact=True).count
    client.delete(collection_name=name, points_selector=qm.FilterSelector(filter=flt), wait=True)
    return before


def ingest_document_atoms(conn, client, *, embed, embedding_contract_id: str, dim: int,
                          doc_id: str, corpus_id: str | None, compiled: dict, profile_contract: str,
                          source: str | None = None) -> dict:
    """PROFILE-ATOM ingest (P4a DAG wiring) — lift a compiled profile's atom surfaces into the
    live architecture instead of a canary: extract → persist as durable rows (Postgres authority,
    supersede the doc's prior atoms) → purge the doc's stale atom points → project the new set.
    Per-doc rebuild keeps the atom collection == the doc's ACTIVE rows. Additive: touches only
    `document_profile_atoms` + the atom collection, never the global profile point or chunks.

    ATOM-REPAIR-V1: with a `source` (`family:compiled_hash`) supersession is family-scoped, so the
    doc keeps the other family's atoms active; the doc's points are rebuilt from ALL its active
    rows (both families), which keeps the collection == the active rows."""
    from polymath_shared.document_profile.profile_atom import active_atoms, extract_atoms, persist_atoms
    atoms = extract_atoms(compiled, doc_id=doc_id, corpus_id=corpus_id, profile_contract=profile_contract)
    persisted = persist_atoms(conn, doc_id=doc_id, profile_contract=profile_contract, atoms=atoms, source=source)
    purged = purge_doc(client, embedding_contract_id, doc_id)
    to_project = atoms if source is None else active_atoms(conn, doc_id=doc_id)
    proj = project_atoms(client, embed=embed, embedding_contract_id=embedding_contract_id, dim=dim, atoms=to_project)
    by_kind: dict[str, int] = {}
    for a in atoms:
        by_kind[a.kind] = by_kind.get(a.kind, 0) + 1
    return {"ok": True, "active": len(atoms), "persisted": persisted, "purged_points": purged,
            "projected_points": proj["points"], "collection": proj["collection"],
            "by_kind": by_kind, "profile_contract": profile_contract, "source": source}


def corpus_scope(corpus_ids) -> list[str]:
    """The corpus scope of an atom lookup: a de-duplicated list of non-empty corpus ids (a bare string is ONE id)."""
    if isinstance(corpus_ids, str):
        corpus_ids = [corpus_ids]
    return list(dict.fromkeys(str(c) for c in (corpus_ids or ()) if c))


def search_atoms(client, collection: str, query_vec, kinds: Sequence[str], k: int = 12, *,
                 corpus_ids: Sequence[str]) -> list[dict]:
    """Search the atom collection by the query vector, filtered to the given atom kinds AND to the given corpora →
    [{doc_id, corpus_id, atom_kind, text, atom_id, score}] desc. Read-only routing lookup.

    CORPUS ISOLATION (finish-line Item 2 / D): every corpus shares ONE atom collection, so the corpus scope is part of
    the retrieval CONTRACT — `corpus_ids` is REQUIRED and rides INSIDE the Qdrant filter, so the nearest-neighbour
    result itself is corpus-correct (never a post-filter over a cross-corpus top-k). No scope → no atoms (fail closed):
    an unscoped lookup is how a corpus-A query activates a corpus-B concept."""
    from qdrant_client.http import models as qm
    scope = corpus_scope(corpus_ids)
    if not scope:
        return []
    must = [qm.FieldCondition(key="corpus_id", match=qm.MatchAny(any=scope))]
    ks = tuple(kinds or ())
    if ks:
        must.append(qm.FieldCondition(key="atom_kind", match=qm.MatchAny(any=list(ks))))
    res = client.query_points(collection, query=list(query_vec), using=VECTOR_NAME, query_filter=qm.Filter(must=must),
                              limit=k, with_payload=["doc_id", "corpus_id", "atom_kind", "text", "atom_id"])
    return [{"doc_id": p.payload.get("doc_id"), "corpus_id": p.payload.get("corpus_id"), "atom_kind": p.payload.get("atom_kind"),
             "text": p.payload.get("text"), "atom_id": p.payload.get("atom_id"), "score": p.score}
            for p in res.points]


def count_atoms(client, collection: str, kinds: Sequence[str], *, corpus_ids: Sequence[str], exact: bool = False) -> int:
    """How many atoms of these kinds exist INSIDE the corpus scope (the "is there anything to search" diagnostic).
    Same scope rule as `search_atoms`: no scope → 0."""
    from qdrant_client.http import models as qm
    scope = corpus_scope(corpus_ids)
    if not scope:
        return 0
    must = [qm.FieldCondition(key="corpus_id", match=qm.MatchAny(any=scope))]
    ks = tuple(kinds or ())
    if ks:
        must.append(qm.FieldCondition(key="atom_kind", match=qm.MatchAny(any=list(ks))))
    return int(client.count(collection, exact=exact, count_filter=qm.Filter(must=must)).count)
