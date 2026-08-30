"""LOCAL-LLM-EXTRACTION-V1 — the LLM proposal lane inside the extract stage.

GLiNER-replacement seam (owner directive 2026-08-29: with LLM extraction,
GLiNER is not needed). This module is the ONLY new thing between the model
and the existing pipeline; identity, Harbor admission, E1–E7, the predicate
compiler, and F1–F8 are untouched. The model proposes; Python validates
(gate.py) and the frozen deterministic layer still decides everything.

Lane routing follows the 300 KB boundary policy (fail closed, enforced
again at dispatch inside the client): source <= threshold stays local,
above it MAY use cloud.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

from polymath_shared.contracts import EvidenceSpan
from polymath_shared.llm_extraction.client import (
    LLMCallResult,
    LLMExtractionClient,
)
from polymath_shared.llm_extraction.gate import (
    ChunkView,
    NormalizedExtraction,
    validate_and_normalize,
)
from polymath_shared.llm_extraction.policy import (
    select_lane as _policy_select_lane,
)
from polymath_shared.settings import get_settings

LLM_ENTITY_VERSION = "polymath-extraction-v1-entity"
LLM_EVIDENCE_VERSION = "polymath-extraction-v1-evidence"
LLM_RELATION_CLASS = "llm_relation"
LLM_MIN_CHUNK_WORDS = 15          # <15-word stubs are structural noise

NEIGHBORHOODS_PER_CALL = 4

_MD_HEADING_RE = __import__("re").compile(r"^#{1,6}\s+(.+)$", __import__("re").MULTILINE)


def _word_count(text: str) -> int:
    return len(text.split())


@dataclass
class Neighborhood:
    nid: str
    chunks: list[tuple[str, str]]          # (chunk_id, text) in source order

    @property
    def char_len(self) -> int:
        return sum(len(t) for _, t in self.chunks)


def _chunk_heading_kind(text: str) -> str:
    """ChunkKind via the v3.3 section classifier (Docling lineage): the
    markdown headings inside the child text are its heading path."""
    from workers.chunk_kind import classify_heading
    headings = [m.group(1).strip() for m in _MD_HEADING_RE.finditer(text)]
    return classify_heading(headings)


def build_neighborhoods(child_chunks: list[dict],
                        max_chars: int | None = None) -> list[Neighborhood]:
    """Group children by parent (source order) into BALANCED neighborhoods.

    Three v3.3/Docling-lineage structure rules:
    * **ChunkKind noise skip:** children classified TOC / bibliography /
      index / appendix / front/back matter never enter an LLM neighborhood
      (the dominant token cost for zero extraction value; they stay in the
      corpus for retrieval).
    * **Uniform-size packing (straggler control):** each parent's children
      are distributed into k = ceil(chars/cap) buckets of near-equal size.
    * **Structural noise skip:** <15-word stubs are skipped too.

    The stored parent row (a generated summary) is never sent — the model
    reads the parent's CHILD CHUNKS.
    """
    from workers.chunk_kind import is_noisy
    if max_chars is None:
        max_chars = get_settings().worker.llm_max_neighborhood_chars
    order: list[str] = []
    by_parent: dict[str, list[dict]] = {}
    skipped_noise = 0
    for row in sorted(child_chunks, key=lambda r: (r["char_start"], r["chunk_id"])):
        if _word_count(row["text"]) < LLM_MIN_CHUNK_WORDS:
            continue
        if is_noisy(_chunk_heading_kind(row["text"])):
            skipped_noise += 1
            continue
        pid = row["parent_id"] or f"__orphan__{row['chunk_id']}"
        if pid not in by_parent:
            by_parent[pid] = []
            order.append(pid)
        by_parent[pid].append(row)
    out: list[Neighborhood] = []
    for pid in order:
        rows = by_parent[pid]
        total = sum(len(r["text"]) for r in rows)
        k = max(1, -(-total // max_chars))          # ceil division
        target = -(-total // k)
        buckets: list[list[tuple[str, str]]] = [[]]
        size = 0
        for row in rows:
            if buckets[-1] and size + len(row["text"]) > target and len(buckets) < k:
                buckets.append([])
                size = 0
            buckets[-1].append((row["chunk_id"], row["text"]))
            size += len(row["text"])
        for b in buckets:
            out.append(Neighborhood(nid=f"{pid}:{len(out)}", chunks=b))
    return out


def select_lane(source_bytes: int):
    """Selection boundary (documents.byte_length is the durable input)."""
    return _policy_select_lane(source_bytes, get_settings().worker.cloud_min_bytes)


def make_client(lane: str) -> LLMExtractionClient:
    s = get_settings().sidecars
    if lane == "local":
        return LLMExtractionClient(
            "local", url=s.llm_local_extract_url, model=s.llm_local_extract_model)
    if lane == "cloud":
        return LLMExtractionClient(
            "cloud", url=s.llm_cloud_url, model=s.llm_cloud_model)
    raise ValueError(f"unknown lane: {lane!r}")


def run_proposals(neighborhoods: list[Neighborhood], *, lane: str,
                  source_bytes: int) -> tuple[list[LLMCallResult], NormalizedExtraction]:
    """Extract every neighborhood through the gate.

    Returns per-call receipts plus the merged, validated, worker-shaped
    extraction. Parse failures surface as QUARANTINED call results — never
    as silently missing evidence.

    LOCAL: one neighborhood per prompt through /infer_batch (true batch
    decode). CLOUD: pool sized at the limiter's CEILING, gated at the
    limiter's EFFECTIVE limit — AIMD moves the effective concurrency within
    [min, max] as the provider proves clean (climb) or throttles (halve),
    so the controller is live, not decorative.
    """
    s = get_settings().worker
    client = make_client(lane)
    limiter = client._lane_limiter()
    views_by_nid = {n.nid: [ChunkView(cid, text) for cid, text in n.chunks]
                    for n in neighborhoods}

    if lane == "local":
        results = client.extract_batched(
            [(n.nid, n.chunks) for n in neighborhoods],
            source_bytes=source_bytes, threshold_bytes=s.cloud_min_bytes)
        results = results if isinstance(results, list) else [results]
    else:
        batches = [neighborhoods[i:i + NEIGHBORHOODS_PER_CALL]
                   for i in range(0, len(neighborhoods), NEIGHBORHOODS_PER_CALL)]
        pool_size = min(len(batches), limiter.spec.conc_cap or limiter.spec.max) or 1

        def one(batch: list[Neighborhood]) -> LLMCallResult:
            return client.extract(
                [(n.nid, n.chunks) for n in batch],
                source_bytes=source_bytes,
                threshold_bytes=s.cloud_min_bytes)

        with ThreadPoolExecutor(max_workers=pool_size) as pool:
            results = list(pool.map(one, batches))

    merged = NormalizedExtraction()
    for r in results:
        if r.packet is None:
            continue
        partial = validate_and_normalize(r.packet, views_by_nid)
        for key in ("entities_by_chunk", "evidence_by_chunk"):
            target = getattr(merged, key)
            for cid, items in getattr(partial, key).items():
                target.setdefault(cid, []).extend(items)
        merged.digests.extend(partial.digests)
        merged.rejections.extend(partial.rejections)
        merged.coercions.extend(partial.coercions)
        for k, v in partial.stats.items():
            merged.stats[k] = merged.stats.get(k, 0) + v
    merged.stats["calls"] = len(results)
    merged.stats["calls_quarantined"] = sum(1 for r in results if r.packet is None)
    return results, merged


def to_precomputed_entities(merged: NormalizedExtraction,
                            label_compositions: list[tuple[str, ...]],
                            all_chunk_ids: list[str] | None = None) -> dict:
    """Shape validated entities into the PHASE B2 precomputed form:
    {chunk_id: {tuple(labels): {"spans": [...]}}} for EVERY label
    composition the worker's _entity_spans may request (composition keys
    must exist or _entity_spans fails loudly). Every chunk gets an entry —
    a chunk with no proposals is an empty span list, never a missing key
    (a missing key would silently fall through to the GLiNER path)."""
    spans_by_chunk = {
        cid: [{"start": e["start"], "end": e["end"], "text": e["text"],
               "label": e["label"], "score": e["score"]}
              for e in items]
        for cid, items in merged.entities_by_chunk.items()}
    if all_chunk_ids is not None:
        spans_by_chunk.update({cid: spans_by_chunk.get(cid, [])
                               for cid in all_chunk_ids})
    # GLiNER batch contract: the per-composition value is the PLAIN span
    # list (entity_pass_batch rows are list[span-dict]); _entity_spans
    # wraps it in {"spans": ...} itself.
    return {
        cid: {tuple(labels): spans for labels in label_compositions}
        for cid, spans in spans_by_chunk.items()
    }


def to_evidence_spans(merged: NormalizedExtraction) -> dict[str, list[EvidenceSpan]]:
    out: dict[str, list[EvidenceSpan]] = {}
    for cid, items in merged.evidence_by_chunk.items():
        out[cid] = sorted(
            (EvidenceSpan(
                chunk_id=cid, start=e["start"], end=e["end"], text=e["text"],
                evidence_class=LLM_RELATION_CLASS, trigger_lemma=None,
                score=e["score"], extractor_version=LLM_EVIDENCE_VERSION)
             for e in items),
            key=lambda s: (s.start, s.end))
    return out


def ledger_items(merged: NormalizedExtraction) -> tuple[list[tuple], list[tuple]]:
    """Raw-ledger items carrying the model's observations EXACTLY as
    proposed (raw open-vocabulary types preserved; Python-located offsets)."""
    entity_items: list[tuple[str, dict]] = []
    evidence_items: list[tuple[str, dict]] = []
    raw_type_by_chunk: dict[str, dict[tuple[int, int], str]] = {}
    for cid, items in merged.entities_by_chunk.items():
        for e in items:
            raw_type_by_chunk.setdefault(cid, {})[(e["start"], e["end"])] = \
                e.get("raw_type", e["label"])
            entity_items.append((cid, {"start": e["start"], "end": e["end"],
                                       "text": e["text"],
                                       "label": e.get("raw_type", e["label"]),
                                       "score": e["score"]}))
    for cid, items in merged.evidence_by_chunk.items():
        for e in items:
            evidence_items.append((cid, {"start": e["start"], "end": e["end"],
                                         "text": e["text"],
                                         "label": f"{LLM_RELATION_CLASS}:{e['predicate']}",
                                         "score": e["score"]}))
    return entity_items, evidence_items


def call_receipts(results: list[LLMCallResult]) -> list[dict]:
    return [{
        "lane": r.lane, "model": r.model, "wall_ms": r.wall_ms,
        "tokens_in": r.tokens_in, "tokens_out": r.tokens_out,
        "attempts": r.attempts, "ok": r.packet is not None,
        "error_class": r.error_class or r.sanitize.error_class,
        "salvaged": r.sanitize.salvaged,
        "raw_head": (r.raw_head or "")[:200],
    } for r in results]
