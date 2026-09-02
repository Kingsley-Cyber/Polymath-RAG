"""LOCAL-LLM-EXTRACTION-V1 — the LLM proposal lane inside the extract stage.

GLiNER-replacement seam (owner directive 2026-08-29: with LLM extraction,
GLiNER is not needed). This module is the ONLY new thing between the model
and the existing pipeline; identity, Harbor admission, E1–E7, the predicate
compiler, and F1–F8 are untouched. The model proposes; Python validates
(gate.py) and the frozen deterministic layer still decides everything.

Lane routing follows the byte-threshold THROUGHPUT policy (owner v2,
2026-08-30): above the threshold always cloud; at/below prefers local,
and rides the cloud pool as an explicit ASSIST when the claiming worker
has cloud affinity (its own lane was dry). The dispatch guard inside
the client verifies assist intent on every sub-threshold cloud call.
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
from polymath_shared.llm_extraction.pool import (
    pool_fingerprint as _pool_fingerprint,
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
    from polymath_shared.region_role import is_noise as _region_is_noise

    from workers.chunk_kind import is_noisy
    if max_chars is None:
        max_chars = get_settings().worker.llm_max_neighborhood_chars
    order: list[str] = []
    by_parent: dict[str, list[dict]] = {}
    skipped_noise = 0
    for row in sorted(child_chunks, key=lambda r: (r["char_start"], r["chunk_id"])):
        if _word_count(row["text"]) < LLM_MIN_CHUNK_WORDS:
            continue
        # REGION-ROLE-V1: the durable, chunker-independent role wins;
        # the heading rule stays as the fallback for rows without one.
        if _region_is_noise(row.get("region_role")):
            skipped_noise += 1
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
        # EXTRACTION-POOL-V1: the roster is contract input — adding,
        # removing, or re-modeling a provider changes what a cloud doc
        # may be extracted by.
        "cloud_pool": _pool_fingerprint(),
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
        # EXTRACTION-COVERAGE-V1 + REGION-ROLE-V1: accounting and region
        # thresholds change what is sent and what counts as returned.
        "coverage": "extraction-coverage-v1",
        "region_role_sha256": content_hash(_region_fingerprint()),
        "entity_version": LLM_ENTITY_VERSION,
        "evidence_version": LLM_EVIDENCE_VERSION,
    }


def _region_fingerprint() -> dict:
    from polymath_shared.region_role import contract_fingerprint
    return contract_fingerprint()


def select_lane(source_bytes: int, affinity: str | None = None):
    """Selection boundary (documents.byte_length is the durable input;
    CLOUD-ASSIST-V1: the claiming worker's lane affinity rides along so
    an idle cloud lane assists the local backlog)."""
    return _policy_select_lane(source_bytes,
                               get_settings().worker.cloud_min_bytes,
                               affinity=affinity)


def make_client(lane: str, doc_id: str = "",
                ring_offset: int = 0) -> LLMExtractionClient:
    s = get_settings().sidecars
    if lane == "local":
        return LLMExtractionClient(
            "local", url=s.llm_local_extract_url, model=s.llm_local_extract_model)
    if lane == "cloud":
        # EXTRACTION-POOL-V1: deterministic doc -> endpoint over the
        # enabled roster (one endpoint == exactly the old behavior).
        from polymath_shared.llm_extraction.pool import select_cloud_endpoint
        ep = select_cloud_endpoint(doc_id, ring_offset)
        client = LLMExtractionClient(
            "cloud", url=ep.url, model=ep.model, limiter_key=ep.limiter_key,
            api_key=ep.api_key,
            cloud_opts=ep.cloud_opts if ep.name != "primary" else None)
        client.endpoint_name = ep.name
        return client
    raise ValueError(f"unknown lane: {lane!r}")


def spread_decision(queue_depth: int | None, doc_id: str,
                    n_neighborhoods: int) -> bool:
    """EXTRACT-DEPTH-SPREAD-V1 decision, pure: spread ONLY when lanes
    would otherwise idle — no other extract doc waiting (depth <= 1
    counts this doc's own just-consumed ticket at most), the doc is
    pool-routed (doc_id set), and there is more than one batch to
    spread. Unknown depth (None) NEVER spreads: per-doc affinity is
    the safe default and the frozen single-endpoint test shape."""
    return (queue_depth is not None and queue_depth <= 1
            and bool(doc_id) and n_neighborhoods > NEIGHBORHOODS_PER_CALL)


def run_proposals(neighborhoods: list[Neighborhood], *, lane: str,
                  source_bytes: int,
                  doc_id: str = "",
                  assist: bool = False,
                  queue_depth: int | None = None,
                  active_rank: int | None = None,
                  active_docs: int | None = None,
                  call_cache: tuple | None = None,
                  ) -> tuple[list[LLMCallResult], NormalizedExtraction]:
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
    views_by_nid = {n.nid: [ChunkView(cid, text) for cid, text in n.chunks]
                    for n in neighborhoods}

    if lane == "local":
        # doc_id engages pool routing; the bare call keeps the frozen
        # single-endpoint shape (and the test doubles that pin it).
        client = make_client(lane, doc_id) if doc_id else make_client(lane)
        limiter = client._lane_limiter()
        controller_before = _controller_snapshot(lane, limiter)
        results = client.extract_batched(
            [(n.nid, n.chunks) for n in neighborhoods],
            source_bytes=source_bytes, threshold_bytes=s.cloud_min_bytes)
        results = results if isinstance(results, list) else [results]
    else:
        # EXTRACTION-THROUGHPUT-V2 (owner-blessed 2026-09-01). The
        # 4-book live post-mortem: 74 cloud calls -> 39x413 + 23x429 +
        # 12x200, one lane serving two colliding docs while six idled,
        # effective concurrency ~1, and every stage failure re-bought
        # the whole document. Four mechanics replace the old per-doc
        # single-lane dispatch:
        #   RANK SLICING   each active doc owns a disjoint slice of the
        #                  ring (rank * n_lanes .. +n_lanes), n_lanes =
        #                  ring // active_docs -- a lone doc takes the
        #                  whole fleet, a full queue degrades to per-doc
        #                  affinity, and ranks cannot collide.
        #   SIZE PACKING   batches pack to the slice's smallest
        #                  request_char_budget -- 413s cannot happen by
        #                  construction; a single oversize neighborhood
        #                  routes alone to the biggest-budget lane.
        #   RECEIPTS       every parsed call's raw response persists
        #                  content-addressed; a stage retry REPLAYS
        #                  cached raws through the same sanitize path
        #                  and only pays for calls it never made.
        #   413 LADDER     split -> halves on the same lane -> single
        #                  still over -> cross-HOST escape (never the
        #                  same provider family; never a rate signal).
        import logging as _logging
        from polymath_shared.identity import content_hash as _chash
        from polymath_shared.llm_extraction.pool import (
            cloud_ring,
            home_ring_index,
            select_cloud_endpoint_abs,
        )

        ring_eps = cloud_ring()
        ring_n = max(1, len(ring_eps))
        known_active = active_docs if active_docs is not None else (
            (queue_depth + 1) if queue_depth is not None else None)
        n_lanes = (max(1, ring_n // max(1, known_active))
                   if known_active is not None else 1)
        base = (active_rank * n_lanes
                if active_rank is not None else home_ring_index(doc_id))

        _abs_clients: dict = {}

        def _client_abs(idx):
            idx %= ring_n
            c = _abs_clients.get(idx)
            if c is None:
                ep = select_cloud_endpoint_abs(idx)
                c = LLMExtractionClient(
                    "cloud", url=ep.url, model=ep.model,
                    limiter_key=ep.limiter_key, api_key=ep.api_key,
                    cloud_opts=ep.cloud_opts if ep.name != "primary" else None)
                c.endpoint_name = ep.name
                c.base_url = ep.url
                c.request_char_budget = ep.request_char_budget
                _abs_clients[idx] = c
            return c

        slice_idx = [base + s for s in range(n_lanes)]
        slice_budget = min(
            getattr(select_cloud_endpoint_abs(i), "request_char_budget",
                    60000) for i in slice_idx)
        big_i = max(range(ring_n), key=lambda i: getattr(
            select_cloud_endpoint_abs(i), "request_char_budget", 0))

        # SIZE PACKING: greedy by chars within the slice budget, capped
        # at NEIGHBORHOODS_PER_CALL; oversize singles go to the escape.
        batches: list[list[Neighborhood]] = []
        oversize: list[Neighborhood] = []
        buf: list[Neighborhood] = []
        buf_chars = 0
        for n in neighborhoods:
            if n.char_len > slice_budget:
                oversize.append(n)
                continue
            if buf and (buf_chars + n.char_len > slice_budget
                        or len(buf) >= NEIGHBORHOODS_PER_CALL):
                batches.append(buf)
                buf, buf_chars = [], 0
            buf.append(n)
            buf_chars += n.char_len
        if buf:
            batches.append(buf)

        cache_get = call_cache[0] if call_cache else None
        cache_put = call_cache[1] if call_cache else None
        _ident = _chash({"contract": contract_identity()})
        _stats = {"cache_hits": 0, "splits": 0, "escapes": 0}

        def _key(batch):
            return "ecr_" + _chash({
                "ident": _ident,
                "batch": [(n.nid, n.chunks) for n in batch]})[:40]

        def _call(client, batch):
            payload = [(n.nid, n.chunks) for n in batch]
            key = _key(batch)
            if cache_get is not None:
                try:
                    raw = cache_get(key)
                except Exception:
                    raw = None
                if raw:
                    _stats["cache_hits"] += 1
                    return client.extract_from_raw(payload, raw)
            r = client.extract(payload, source_bytes=source_bytes,
                               threshold_bytes=s.cloud_min_bytes,
                               assist=assist)
            if cache_put is not None and r.packet is not None:
                accepted = sum(
                    len(getattr(r.packet, f, None) or [])
                    for f in ("entities", "relations", "digests"))
                try:
                    cache_put(key, doc_id, r.lane, r.model, r.raw_text,
                              accepted)
                except TypeError:            # older 5-arg cache double
                    cache_put(key, doc_id, r.lane, r.model, r.raw_text)
                except Exception:
                    pass
            return r

        # LANE-AUTH-QUARANTINE-V1 (2026-09-01): a lane answering 401/403
        # is DEAD for this run (revoked/rotated key, wrong env
        # snapshot) — measured live: one openrouter 401 struck a whole
        # document's extract stage to failed. Auth failure is a lane
        # property, never a document property: quarantine the lane and
        # escape cross-host, like 413's terminal path.
        _dead: set = set()

        def _dispatch(batch, lane_i, depth=0):
            client = _client_abs(lane_i)
            try:
                r = _call(client, batch)
            except ExtractionTransportError as exc:
                if "HTTP 401" in str(exc) or "HTTP 403" in str(exc):
                    if client.endpoint_name not in _dead:
                        _dead.add(client.endpoint_name)
                        _logging.getLogger("llm-provider").warning(
                            "lane %s quarantined for this run: %s",
                            client.endpoint_name, str(exc)[:100],
                            extra={"error_code":
                                   "EXTRACTION_LANE_AUTH_DEAD"})
                    from urllib.parse import urlparse
                    home = urlparse(getattr(client, "base_url", "")
                                    or "").netloc
                    for off in range(1, ring_n):
                        alt = _client_abs(lane_i + off)
                        if alt.endpoint_name in _dead:
                            continue
                        if urlparse(getattr(alt, "base_url", "")
                                    or "").netloc != home:
                            _stats["escapes"] += 1
                            return _dispatch(batch, lane_i + off, depth)
                    raise
                if "413" in str(exc):
                    _stats["splits"] += 1
                    if len(batch) > 1:
                        half = len(batch) // 2
                        return (_dispatch(batch[:half], lane_i, depth)
                                + _dispatch(batch[half:], lane_i, depth))
                    from urllib.parse import urlparse
                    home = urlparse(getattr(client, "base_url", "")
                                    or "").netloc
                    for off in range(1, ring_n):
                        alt = _client_abs(lane_i + off)
                        if urlparse(getattr(alt, "base_url", "")
                                    or "").netloc != home:
                            _stats["escapes"] += 1
                            return [_call(alt, batch)]
                    raise
                if depth >= 1:
                    raise
                # TRANSPORT-FAILOVER-CROSS-HOST (2026-09-01, live: a lone
                # document's n_lanes == ring, so lane_i + n_lanes wrapped
                # to the SAME lane and one transient gemini 503 failed
                # the whole attempt). Fail over to the first live lane
                # on a DIFFERENT host — a 5xx is a host condition.
                from urllib.parse import urlparse
                home = urlparse(getattr(client, "base_url", "")
                                or "").netloc
                fb = None
                for off in range(1, ring_n):
                    cand = _client_abs(lane_i + off)
                    if cand.endpoint_name in _dead:
                        continue
                    if urlparse(getattr(cand, "base_url", "")
                                or "").netloc != home:
                        fb, fb_off = cand, off
                        break
                if fb is None:
                    raise
                _logging.getLogger("llm-provider").warning(
                    "lane failover: %s -> %s after transport failure (%s)",
                    client.endpoint_name, fb.endpoint_name, str(exc)[:120],
                    extra={"error_code": "EXTRACTION_LANE_FAILOVER"})
                return _dispatch(batch, lane_i + fb_off, depth + 1)
            if (getattr(r, "finish_reason", None) == "length"
                    and len(batch) > 1):
                # OUTPUT-AWARE SPLIT (fleet review 2026-09-01): a dense
                # batch can overflow the OUTPUT budget even when the
                # request payload fits — truncation is a payload-class
                # condition (split), never provider health.
                _stats["splits"] += 1
                half = len(batch) // 2
                return (_dispatch(batch[:half], lane_i, depth)
                        + _dispatch(batch[half:], lane_i, depth))
            if (r.packet is None
                    and r.error_class != "LIMITER_REFUSED"
                    and depth < 1):
                # FLEET-V3 SEMANTIC ESCAPE (PARSED ≠ ACCEPTED): a call
                # that quarantined — valid transport, unusable output —
                # gets EXACTLY ONE try on a different HOST (different
                # model family), the enrichment hard-case pattern
                # ported to extraction. Keep whichever parses.
                from urllib.parse import urlparse
                home = urlparse(getattr(client, "base_url", "")
                                or "").netloc
                for off in range(1, ring_n):
                    alt = _client_abs(lane_i + off)
                    if urlparse(getattr(alt, "base_url", "")
                                or "").netloc != home:
                        _stats["escapes"] += 1
                        _logging.getLogger("llm-provider").warning(
                            "semantic escape: %s -> %s (quarantined)",
                            client.endpoint_name, alt.endpoint_name,
                            extra={"error_code":
                                   "EXTRACTION_SEMANTIC_ESCAPE"})
                        try:
                            r2 = _call(alt, batch)
                        except ExtractionTransportError:
                            break
                        return [r2 if r2.packet is not None else r]
                return [r]
            if r.error_class == "LIMITER_REFUSED" and depth < 1:
                fb = _client_abs(lane_i + n_lanes)
                if fb.endpoint_name != client.endpoint_name:
                    _logging.getLogger("llm-provider").warning(
                        "lane failover: %s -> %s after limiter refusal",
                        client.endpoint_name, fb.endpoint_name,
                        extra={"error_code": "EXTRACTION_LANE_FAILOVER"})
                    return _dispatch(batch, lane_i + n_lanes, depth + 1)
            return [r]

        # the doc's BASE lane serves the shared tail (reissues +
        # controller snapshot); per-batch dispatch stays per-lane
        client = _client_abs(base)
        limiter = (client._lane_limiter()
                   if hasattr(client, "_lane_limiter") else None)
        controller_before = (_controller_snapshot(lane, limiter)
                             if limiter is not None else {})
        work = ([(b, slice_idx[i % n_lanes]) for i, b in enumerate(batches)]
                + [([n], big_i) for n in oversize])
        pool_size = max(1, min(len(work), 4 * n_lanes, 24))
        _logging.getLogger("llm-provider").info(
            "throughput-v2 dispatch: %d batches (+%d oversize) over %d "
            "lane(s) [base %d/%d], budget %d chars, pool %d",
            len(batches), len(oversize), n_lanes, base % ring_n, ring_n,
            slice_budget, pool_size,
            extra={"error_code": "EXTRACTION_V2_DISPATCH"})
        with ThreadPoolExecutor(max_workers=pool_size) as pool:
            results = [r for rs in pool.map(
                lambda w: _dispatch(w[0], w[1]), work) for r in rs]
        if _stats["cache_hits"] or _stats["splits"] or _stats["escapes"]:
            _logging.getLogger("llm-provider").info(
                "throughput-v2: %(cache_hits)d cached, %(splits)d "
                "splits, %(escapes)d escapes", _stats,
                extra={"error_code": "EXTRACTION_V2_STATS"})

    # A limiter refusal (breaker open / Retry-After hold) is an
    # INFRASTRUCTURE condition, not a model disposition: it must fail the
    # stage (StageFailed → ticket retry), never complete the document with
    # those neighborhoods silently missing.
    _raise_if_refused(results, lane)

    # ---- EXTRACTION-COVERAGE-V1: one durable disposition per neighborhood
    # MEASURED 2026-08-30 (cysa-study-v1): with 4 neighborhoods per cloud
    # call and the pre-fix output cap, only the FIRST neighborhood of each
    # call came back (67 of 181; pattern X...X...X...) and the stage
    # completed anyway. Nothing counted sent vs returned. Now every
    # neighborhood is accounted for; incomplete / missing / quarantined
    # ones are re-issued ONCE, singly; what still fails is recorded as
    # `dropped` and the census refuses promotion — never silent.
    by_nid = {n.nid: n for n in neighborhoods}
    items, disp = _dispose(results, list(by_nid))
    todo = [by_nid[nid] for nid in by_nid if disp.get(nid) in _REISSUE_DISPOSITIONS]
    reissue_results: list[LLMCallResult] = []
    if todo:
        reissue_results = _reissue(
            client, todo, lane=lane, source_bytes=source_bytes,
            threshold_bytes=s.cloud_min_bytes, assist=assist,
            pool_size=(min(len(todo),
                           (limiter.spec.conc_cap or limiter.spec.max)
                           if limiter is not None else 4) or 1)
            if lane == "cloud" else 1)
        _raise_if_refused(reissue_results, lane)
        items2, disp2 = _dispose(reissue_results, [n.nid for n in todo])
        for n in todo:
            nid = n.nid
            second = disp2.get(nid)
            if second in ("returned", "returned_empty"):
                items[nid] = items2[nid]
                disp[nid] = "reissued_returned"
            elif second == "incomplete" and nid in items2:
                items[nid] = items2[nid]
                disp[nid] = "incomplete_kept"
            elif disp[nid] == "incomplete" and nid in items:
                disp[nid] = "incomplete_kept"      # first-pass partial survives
            else:
                items.pop(nid, None)
                disp[nid] = "dropped"
    results = list(results) + reissue_results

    ordered_items = [items[n.nid] for n in neighborhoods
                     if n.nid in items and disp.get(n.nid) != "dropped"]
    if ordered_items:
        template = next(r.packet for r in results if r.packet is not None)
        merged = validate_and_normalize(
            template.model_copy(update={"items": ordered_items}), views_by_nid)
    else:
        merged = NormalizedExtraction()
        merged.stats = {"entities": 0, "relations": 0, "entities_rejected": 0,
                        "relations_rejected": 0, "predicate_fallbacks": 0,
                        "neighborhoods": 0}

    parent_of = {n.nid: n.nid.rsplit(":", 1)[0] for n in neighborhoods}
    chunk_parent = {cid: parent_of[n.nid] for n in neighborhoods for cid, _ in n.chunks}
    touched = {chunk_parent[cid] for cid, its in merged.entities_by_chunk.items()
               if its and cid in chunk_parent}
    touched |= {chunk_parent[cid] for cid, its in merged.evidence_by_chunk.items()
                if its and cid in chunk_parent}
    counts = {}
    for d in disp.values():
        counts[d] = counts.get(d, 0) + 1
    merged.dispositions = [
        {"nid": n.nid, "parent_id": parent_of[n.nid], "disposition": disp[n.nid]}
        for n in neighborhoods]
    merged.stats.update({
        "neighborhoods_sent": len(neighborhoods),
        "neighborhoods_returned": counts.get("returned", 0) + counts.get("reissued_returned", 0),
        "neighborhoods_returned_empty": counts.get("returned_empty", 0),
        "neighborhoods_reissued": len(todo),
        "neighborhoods_recovered": counts.get("reissued_returned", 0),
        "neighborhoods_incomplete_kept": counts.get("incomplete_kept", 0),
        "neighborhoods_dropped": counts.get("dropped", 0),
        "neighborhoods_unaccounted": counts.get("unaccounted", 0),
        "parents_total": len(set(parent_of.values())),
        "parents_with_extraction": len(touched),
        "calls_reissue": len(reissue_results),
        "calls_salvaged": sum(1 for r in results if r.sanitize.salvaged),
    })
    merged.stats["calls"] = len(results)
    merged.stats["calls_quarantined"] = sum(1 for r in results if r.packet is None)
    merged.stats["calls_truncated"] = sum(1 for r in results if r.finish_reason == "length")
    # The controller's trajectory over THIS document, durable in the stage
    # artifact: where the lane started, where it ended, and whether the
    # value is persisted (so the climb is provable and survives restarts).
    merged.stats["controller"] = {
        "before": controller_before,
        "after": (_controller_snapshot(lane, limiter)
                  if limiter is not None else {}),
        "persisted": REGISTRY.store_attached,
    }
    return results, merged


_REISSUE_DISPOSITIONS = frozenset({"missing", "incomplete", "quarantined", "unaccounted"})


def _raise_if_refused(results: list[LLMCallResult], lane: str) -> None:
    refused = [r for r in results if r.error_class == "LIMITER_REFUSED"]
    if refused:
        raise ExtractionTransportError(
            f"{lane} lane refused {len(refused)}/{len(results)} call(s) "
            "(breaker open or rate hold); stage must retry, not complete")


def _dispose(results: list[LLMCallResult], sent_ids: list[str]) -> tuple[dict, dict[str, str]]:
    """Per-neighborhood disposition for one pass.

    returned / returned_empty — the item came back (empty = model found
    nothing; legitimate); incomplete — the call was truncated
    (`finish_reason == "length"`) or its JSON had to be salvaged, so the
    LAST item present in prompt order is the cut point and cannot be
    trusted whole; missing — the call answered but never mentioned the
    id; quarantined — the call produced no packet; unaccounted — no call
    carried the id at all (an invariant breach, counted, re-issued)."""
    items: dict = {}
    disp: dict[str, str] = {}
    for r in results:
        sent = list(r.neighborhood_ids) or (
            [i.neighborhood_id for i in r.packet.items] if r.packet is not None else [])
        if r.packet is None:
            for nid in sent:
                disp[nid] = "quarantined"
            continue
        present: dict = {}
        for it in r.packet.items:
            present.setdefault(it.neighborhood_id, it)
        cut = (r.finish_reason == "length") or bool(r.sanitize.salvaged)
        ordered = [nid for nid in sent if nid in present]
        cut_nid = ordered[-1] if (cut and ordered) else None
        for nid in sent:
            if nid not in present:
                disp[nid] = "missing"
                continue
            items[nid] = present[nid]
            if nid == cut_nid:
                disp[nid] = "incomplete"
            elif not present[nid].entities and not present[nid].relations:
                disp[nid] = "returned_empty"
            else:
                disp[nid] = "returned"
    for nid in sent_ids:
        disp.setdefault(nid, "unaccounted")
    return items, disp


def _reissue(client: LLMExtractionClient, todo: list[Neighborhood], *, lane: str,
             source_bytes: int, threshold_bytes: int, pool_size: int,
             assist: bool = False) -> list[LLMCallResult]:
    """Second pass: ONE neighborhood per call (the truncation failure mode
    cannot recur inside a single-neighborhood budget), bounded to one
    pass — a neighborhood that fails twice is recorded, not retried."""
    if lane == "local":
        out = client.extract_batched(
            [(n.nid, n.chunks) for n in todo],
            source_bytes=source_bytes, threshold_bytes=threshold_bytes)
        out = out if isinstance(out, list) else [out]
    else:
        def one(n: Neighborhood) -> LLMCallResult:
            return client.extract([(n.nid, n.chunks)], source_bytes=source_bytes,
                                  threshold_bytes=threshold_bytes, assist=assist)
        with ThreadPoolExecutor(max_workers=max(1, pool_size)) as pool:
            out = list(pool.map(one, todo))
    for r in out:
        r.reissue = True
        if not r.neighborhood_ids and len(out) == len(todo):
            pass    # ids come from the client; legacy fakes fall back to packet ids
    return out


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
        "neighborhood_ids": list(r.neighborhood_ids),
        "reissue": bool(r.reissue),
        "raw_head": (r.raw_head or "")[:200],
    } for r in results]
