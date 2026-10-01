"""SERVED-PROFILE-LABEL (the owner, 2026-10-01: "fix the cinema badge so this confusion doesnt happen"): which document
profile card SEARCH actually serves for each file, read from the profile index itself.

A file can carry a newer card that search never uses: CANONICAL-PROFILE-SELECTION-V1 keeps the richer last-known-good point
when a new card is thinner (`kept_last_known_good`). So "the latest card is vNext" — `profile_vnext`, `vnext_ready`, the
vNext verdict, which count WRITTEN cards — is not "search uses vNext". Measured live 2026-10-01: cinema has a vNext card on
77 / 77 files and is served by 0 of them (the index holds the basic cards, ~30 questions + searches each, against 2-6 on the
refused vNext cards). Those written-card fields stay exactly as they are (scripts read them); this only feeds the labels.

Read-only and fail-open: `served_profiles` returns None when the index cannot be read, and every caller then keeps the old
label. Section cards of giant files (F4, `scope: section`) are not a file's card and are left out."""
from __future__ import annotations

import contextlib
from collections.abc import Iterable, Mapping
from typing import Any

from polymath_shared.document_profile import projection as PJ

VNEXT_PREFIX = "doc-profile-vnext"
WRITER_VNEXT, WRITER_BASIC = "vnext", "basic"


def writer_of(prompt_version: Any) -> str | None:
    """Which writer produced a card, from its prompt version (`doc-profile-vnext-*` = vNext, any other = basic)."""
    if not prompt_version:
        return None
    return WRITER_VNEXT if str(prompt_version).startswith(VNEXT_PREFIX) else WRITER_BASIC


def served_profiles(corpus_id: str, *, client: Any = None, embedding_contract_id: str | None = None,
                    timeout: float = 5.0) -> dict[str, dict[str, Any]] | None:
    """doc_id -> {"writer", "prompt_version", "compiled_hash"} of the DOCUMENT card the profile index serves for every file
    of `corpus_id`; a file without a served card is absent. None when the index cannot be read (never raises)."""
    owned = client is None
    try:
        if embedding_contract_id is None:
            from polymath_shared.embedding_contracts import active_contract
            embedding_contract_id = active_contract().contract_id
        if owned:
            from qdrant_client import QdrantClient

            from polymath_shared.settings import get_settings
            client = QdrantClient(url=get_settings().stores.qdrant_url, timeout=timeout)
        from qdrant_client.http import models as qm
        flt = qm.Filter(must=[qm.FieldCondition(key="corpus_id", match=qm.MatchValue(value=corpus_id))])
        out: dict[str, dict[str, Any]] = {}
        offset = None
        while True:
            points, offset = client.scroll(collection_name=PJ.collection_name(embedding_contract_id), scroll_filter=flt,
                                           limit=512, offset=offset, with_payload=True, with_vectors=False)
            for p in points:
                pl = getattr(p, "payload", None) or {}
                if pl.get("scope", PJ.SCOPE_DOCUMENT) != PJ.SCOPE_DOCUMENT or not pl.get("doc_id"):
                    continue
                out[str(pl["doc_id"])] = {"writer": writer_of(pl.get("prompt_version")),
                                          "prompt_version": pl.get("prompt_version"), "compiled_hash": pl.get("compiled_hash")}
            if offset is None:
                return out
    except Exception:  # noqa: BLE001 — labels only: an unreadable index must never fail a status read
        return None
    finally:
        if owned and client is not None:
            with contextlib.suppress(Exception):                # closing a read-only client must never fail a status read
                client.close()


def apply_served(summaries: Mapping[str, dict], served: Mapping[str, Mapping[str, Any]] | None) -> None:
    """Add `profile_served` ("vnext" | "basic" | None = no served card) to each per-file summary, in place. When the index
    could not be read (`served` is None) nothing is added, so the labels keep their old basis."""
    if served is None:
        return
    for did, s in summaries.items():
        s["profile_served"] = (served.get(did) or {}).get("writer")


def served_vnext_count(doc_ids: Iterable[str], served: Mapping[str, Mapping[str, Any]] | None) -> int | None:
    """How many of `doc_ids` search serves with a vNext card; None when the index could not be read."""
    if served is None:
        return None
    return sum(1 for d in doc_ids if (served.get(d) or {}).get("writer") == WRITER_VNEXT)
