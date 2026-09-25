"""SEEALSO-BLEND-V1 — SEE ALSO as a semantic search for similar ideas (owner 2026-09-24; register 11.475).

The owner: "see also is doc level … i dont think see also should be used to find books i think semantic search for
similar ideas, maybe a system that takes see also in a document level supplemnent it with a search simialr to semantci and
relevant of the query and search for whats in their". It replaces the book-finding hop of 11.472.

For the documents the QUESTION is about (the profile nomination the scout already uses), their SEE ALSO lines are ranked by
the question; each chosen line is BLENDED with the question (`alpha · q + (1 − alpha) · item`, normalized) and that probe
searches passages anywhere in the corpus. The see-also line widens the idea; the question keeps it relevant; nothing picks
books. The line routes, the passages prove, the cross-encoder judges. No model call (the vectors come from the turn's
single batch embed).

Pure orchestration over an injected search, so the lane's I/O stays with the caller (`chat_retrieval.fanout_search`).
"""
from __future__ import annotations

import math
import os
from collections.abc import Callable, Mapping, Sequence

FLAG = "POLYMATH_CHAT_SEEALSO_BLEND"


def enabled(env: Mapping[str, str] | None = None) -> bool:
    return (env if env is not None else os.environ).get(FLAG, "0") == "1"


def blend(question_vector: Sequence[float], item_vector: Sequence[float], alpha: float = 0.5) -> list[float]:
    """Unit-length `alpha · q̂ + (1 − alpha) · î` (each side normalized first, so neither dominates by its length)."""
    def _unit(v):
        n = math.sqrt(sum(float(x) * float(x) for x in v)) or 1.0
        return [float(x) / n for x in v]
    q, i = _unit(question_vector), _unit(item_vector)
    a = min(max(float(alpha), 0.0), 1.0)
    return _unit([a * x + (1.0 - a) * y for x, y in zip(q, i)])


def blend_rows(items: Sequence[Mapping], item_vectors: Sequence[Sequence[float]], *,
               question_vector: Sequence[float],
               search_children: Callable[[Sequence[float], int], list[dict]],
               alpha: float = 0.5, children_per_item: int = 4) -> tuple[list[dict], list[dict]]:
    """One blended probe per SEE ALSO item → passages anywhere in the corpus.

    `items[i]` = {"text", "doc_id"} (the document the line belongs to); `search_children(vec, k)` → original child rows
    ({payload, score}) in the corpus. Returns (rows, trace): rows tagged `fanout_atom` (the line: the path's need for the
    judge) and `seealso_blend` ({item, from_doc}); chunks are not repeated across items; a failed search drops only its
    item."""
    rows: list[dict] = []
    trace: list[dict] = []
    seen: set[str] = set()
    for item, vec in zip(items, item_vectors):
        text = str(item.get("text") or "").strip()
        if not text or vec is None:
            continue
        try:
            found = search_children(blend(question_vector, vec, alpha), children_per_item * 2) or []
        except Exception:  # noqa: BLE001 — one failed probe drops only this item
            continue
        kept = 0
        for r in found:
            cid = str((r.get("payload") or {}).get("chunk_id") or "")
            if not cid or cid in seen:
                continue
            seen.add(cid)
            r = dict(r)
            r["fanout_atom"] = text
            r["seealso_blend"] = {"item": text, "from_doc": str(item.get("doc_id") or "")}
            rows.append(r)
            kept += 1
            if kept >= children_per_item:
                break
        if kept:
            trace.append({"item": text[:120], "from_doc": str(item.get("doc_id") or ""), "children": kept})
    return rows, trace
