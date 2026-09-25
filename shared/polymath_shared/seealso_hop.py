"""SEEALSO-HOP-V1 — the one-hop SEE ALSO door (owner decision D8, DOCUMENT-RAG-COMPLETION-V1 §5 "neighbour door";
register 11.472).

A document's profile says where else to look ("SEEALSO: Bayesian reasoning applications"). Lane G already probes children
with those texts anywhere in the corpus (the global door). The hop follows the pointer to DOCUMENTS: the SEE ALSO item's
vector finds the other documents whose profile is about it (never the pointing document itself). The QUESTION then picks
the sections (parent maps) and the original children inside those documents: the pointer chooses where to look, the
question chooses what to read. One hop only (D8); no model call (the vectors come from the turn's single batch embed); the
item routes, the children prove, the cross-encoder judges.

Pure orchestration over injected lookups, so the lane's I/O stays with the caller (`chat_retrieval.fanout_search`).
"""
from __future__ import annotations

import os
from collections.abc import Callable, Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor

FLAG = "POLYMATH_CHAT_SEEALSO_HOP"
#: the neighbour documents are nominated on what they are ABOUT (identity / theme / title) and what they teach
#: (concepts / theories) — never on their own see-also pointers, so the hop cannot bounce through a chain of pointers
HOP_SURFACES = ("identity", "theme", "title", "concepts", "theories")


def enabled(env: Mapping[str, str] | None = None) -> bool:
    return (env if env is not None else os.environ).get(FLAG, "0") == "1"


def _follow(item: Mapping, vec, question_vector, *, nominate, search_maps, search_children,
            docs_per_item: int, children_per_item: int) -> tuple[str, str, list[str], list[dict]]:
    """One item's hop → (text, from_doc, target docs, child rows in their search order). Fail-open to nothing."""
    text = str(item.get("text") or "").strip()
    src = str(item.get("doc_id") or "")
    if not text or vec is None:
        return text, src, [], []
    try:
        targets = [d for d in (nominate(vec, docs_per_item + 1) or []) if d and d != src][:docs_per_item]
    except Exception:  # noqa: BLE001 — a failed nomination drops this item's hop only
        return text, src, [], []
    if not targets:
        return text, src, [], []
    try:
        maps = search_maps(question_vector, targets, max(8, children_per_item * 3)) or []
    except Exception:  # noqa: BLE001
        maps = []
    parents: list[tuple[str, str]] = []
    for m in maps:
        did, pid = str(m.get("doc_id") or ""), str(m.get("parent_id") or "")
        if did in targets and pid and (did, pid) not in parents:
            parents.append((did, pid))
    if not parents:
        return text, src, targets, []
    try:
        found = search_children(question_vector, parents[: max(2, children_per_item)], children_per_item * 2) or []
    except Exception:  # noqa: BLE001
        found = []
    return text, src, targets, found


def hop_rows(items: Sequence[Mapping], vectors: Sequence[Sequence[float]], *, question_vector: Sequence[float],
             nominate: Callable[[Sequence[float], int], list[str]],
             search_maps: Callable[[Sequence[float], list[str], int], list[dict]],
             search_children: Callable[[Sequence[float], list[tuple[str, str]], int], list[dict]],
             docs_per_item: int = 2, children_per_item: int = 4, parallel: int = 3) -> tuple[list[dict], list[dict]]:
    """Follow each SEE ALSO item one hop. `items[i]` = {"text", "doc_id"} (the pointing document), `vectors[i]` its vector.

    - `nominate(item_vec, k)` → doc ids whose profile matches the item (ordered);
    - `search_maps(question_vec, doc_ids, k)` → [{doc_id, parent_id, ...}] parent-map hits inside those documents;
    - `search_children(question_vec, [(doc_id, parent_id), …], k)` → original child rows ({payload, score}) in ONE search.

    Items run concurrently (`parallel`); results merge in item order, so the output is deterministic. Returns (rows, hops):
    child rows tagged `fanout_atom` (the item text: the path's need for the judge) and `seealso_hop` ({item, from_doc,
    to_doc, parent_id}), plus one trace entry per item that landed."""
    pairs = [(it, v) for it, v in zip(items, vectors)]
    if not pairs:
        return [], []
    kw = dict(nominate=nominate, search_maps=search_maps, search_children=search_children,
              docs_per_item=docs_per_item, children_per_item=children_per_item)
    workers = max(1, min(int(parallel or 1), len(pairs)))
    if workers == 1:
        results = [_follow(it, v, question_vector, **kw) for it, v in pairs]
    else:
        with ThreadPoolExecutor(max_workers=workers) as ex:
            results = list(ex.map(lambda p: _follow(p[0], p[1], question_vector, **kw), pairs))
    rows: list[dict] = []
    hops: list[dict] = []
    seen: set[str] = set()
    for text, src, _targets, found in results:
        kept = 0
        landed: list[str] = []
        for r in found:
            pl = r.get("payload") or {}
            cid, did = str(pl.get("chunk_id") or ""), str(pl.get("doc_id") or "")
            if not cid or cid in seen:
                continue
            seen.add(cid)
            r = dict(r)
            r["fanout_atom"] = text
            r["seealso_hop"] = {"item": text, "from_doc": src, "to_doc": did, "parent_id": str(pl.get("parent_id") or "")}
            rows.append(r)
            kept += 1
            if did and did not in landed:
                landed.append(did)
            if kept >= children_per_item:
                break
        if kept:
            hops.append({"item": text[:120], "from_doc": src, "to_docs": landed, "children": kept})
    return rows, hops
