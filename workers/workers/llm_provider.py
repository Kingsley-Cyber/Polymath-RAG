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
    ExtractionTransportError,
    LLMCallResult,
    LLMExtractionClient,
)
from polymath_shared.llm_extraction.gate import (
    ChunkView,
    NormalizedExtraction,
    validate_and_normalize,
)
from polymath_shared.llm_extraction.limiter import REGISTRY
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
            n = len(row["text"])
            # `target` balances the k planned buckets; `max_chars` is the
            # HARD cap — a bucket may exceed it only when a single child
            # does (children are never split). Without the hard-cap test
            # the last planned bucket absorbed every remaining child.
            if buckets[-1] and (
                    (size + n > target and len(buckets) < k)
                    or size + n > max_chars):
                buckets.append([])
                size = 0
            buckets[-1].append((row["chunk_id"], row["text"]))
            size += n
        for b in buckets:
            out.append(Neighborhood(nid=f"{pid}:{len(out)}", chunks=b))
    return out


def contract_identity() -> dict:
    """Every LLM-lane input that can change semantic output, for the
    extract stage's contract hash (the GLiNER path hashes its model pin
    the same way). A change to any of these must yield a NEW receipt so
    the document is re-extracted and old facts stay attributable."""
    from dataclasses import asdict

    from polymath_shared.identity import content_hash
    from polymath_shared.llm_extraction.client import (
        GENERATION_CONFIG,
        SYSTEM_PROMPT,
        _lane_limit,
        output_budget_for,
    )
    from polymath_shared.llm_extraction.contract import CONTRACT_ID
    from polymath_shared.llm_extraction.gate import (
        LLM_TYPE_FALLBACKS,
        MAX_MENTIONS_PER_SURFACE,
    )
    from polymath_shared.llm_extraction.ontology import (
        PREDICATE_ALIASES,
        RELATION_ONTOLOGY,
    )

    from workers.chunk_kind import _RULES, NOISY_KINDS

    s = get_settings()
    return {
        "contract": CONTRACT_ID,
        "cloud_min_bytes": s.worker.cloud_min_bytes,
        "models": {"local": s.sidecars.llm_local_extract_model,
                   "cloud": s.sidecars.llm_cloud_model},
        "neighborhood": {"max_chars": s.worker.llm_max_neighborhood_chars,
                         "per_call": NEIGHBORHOODS_PER_CALL,
                         "min_chunk_words": LLM_MIN_CHUNK_WORDS},
        "prompt_sha256": content_hash({"system": SYSTEM_PROMPT}),
        "ontology_sha256": content_hash({"enum": RELATION_ONTOLOGY,
                                         "aliases": PREDICATE_ALIASES}),
        "type_fallbacks_sha256": content_hash({"fallbacks": LLM_TYPE_FALLBACKS,
                                               "max_mentions": MAX_MENTIONS_PER_SURFACE}),
        "generation": {**GENERATION_CONFIG,
                       "output_budget_anchors": [output_budget_for(800),
                                                 output_budget_for(15_000)]},
        "chunk_kind_sha256": content_hash({
            "noisy": list(NOISY_KINDS),
            "rules": [[r.pattern, kind] for r, kind in _RULES]}),
        "limiter_seeds": {lane: asdict(_lane_limit(lane)) for lane in ("local", "cloud")},
        "materialization": ("llm-direct-facts-v1" if s.worker.extraction_provider == "llm_live"
                            else "compiler"),
        "entity_version": LLM_ENTITY_VERSION,
        "evidence_version": LLM_EVIDENCE_VERSION,
    }


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
    _ensure_controller_store()
    client = make_client(lane)
    limiter = client._lane_limiter()
    views_by_nid = {n.nid: [ChunkView(cid, text) for cid, text in n.chunks]
                    for n in neighborhoods}
    controller_before = _controller_snapshot(lane, limiter)

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

    # A limiter refusal (breaker open / Retry-After hold) is an
    # INFRASTRUCTURE condition, not a model disposition: it must fail the
    # stage (StageFailed → ticket retry), never complete the document with
    # those neighborhoods silently missing.
    refused = [r for r in results if r.error_class == "LIMITER_REFUSED"]
    if refused:
        raise ExtractionTransportError(
            f"{lane} lane refused {len(refused)}/{len(results)} call(s) "
            "(breaker open or rate hold); stage must retry, not complete")

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
    merged.stats["calls_truncated"] = sum(1 for r in results if r.finish_reason == "length")
    # The controller's trajectory over THIS document, durable in the stage
    # artifact: where the lane started, where it ended, and whether the
    # value is persisted (so the climb is provable and survives restarts).
    merged.stats["controller"] = {
        "before": controller_before,
        "after": _controller_snapshot(lane, limiter),
        "persisted": REGISTRY.store_attached,
    }
    return results, merged


_STORE_ATTACHED = False


def _ensure_controller_store() -> None:
    """Attach the Postgres-backed controller store once per process, so
    the AIMD state (cloud concurrency, local batch budget) restores from
    the last run instead of the yaml seed. Fail-soft: the store logs once
    and the controllers run in-memory if the table/DB is unavailable."""
    global _STORE_ATTACHED
    if _STORE_ATTACHED:
        return
    from polymath_shared.llm_extraction.state_store import PostgresControllerStore
    REGISTRY.attach_store(PostgresControllerStore(get_settings().postgres.dsn))
    _STORE_ATTACHED = True


def _controller_snapshot(lane: str, limiter) -> dict:
    snap = {"lane": lane, "limiter_effective": limiter.effective,
            "limiter_ceiling": limiter._ceil, "limiter_floor": limiter._floor,
            "breaker_open": limiter.breaker_open}
    if lane == "local":
        from polymath_shared.llm_extraction.client import local_batch_budget
        budget = local_batch_budget()
        snap["batch_tokens_cap"] = budget.effective
        snap["batch_tokens_ceiling"] = budget.ceiling
    return snap


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
    """Per-call receipts. `limiter_effective` / `batch_tokens_cap` are the
    values captured AT THE CALL by the client (never a registry lookup
    after the fact), so the AIMD climb is readable straight from artifacts."""
    return [{
        "lane": r.lane, "model": r.model, "wall_ms": r.wall_ms,
        "tokens_in": r.tokens_in, "tokens_out": r.tokens_out,
        "attempts": r.attempts, "ok": r.packet is not None,
        "limiter_effective": r.limiter_effective,
        "batch_tokens_cap": r.batch_tokens_cap,
        "finish_reason": r.finish_reason,
        "error_class": r.error_class or r.sanitize.error_class,
        "salvaged": r.sanitize.salvaged,
        "raw_head": (r.raw_head or "")[:200],
    } for r in results]
