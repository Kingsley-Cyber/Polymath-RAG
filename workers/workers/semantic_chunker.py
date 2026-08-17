"""SEMANTIC-CHUNKING-V2: structure-constrained semantic chunking.

chunk-contract-v2. Hard structure first (ADR: SEMANTIC-CHUNKING-V2):
markdown-derived regions — headings (metadata, NEVER chunk-body text),
paragraph blocks, fenced code, tables, lists — form hard boundaries.
Chonkie SemanticChunker (pinned 1.7.0) decides where WITHIN a prose
region to split, using Polymath's own pinned Qwen embedder through a
batching adapter with a content-addressed cache. Chunks are contiguous
source spans (skip_window=0) and every offset is validated against the
authoritative text. Chonkie's internal sentence splitting never
becomes Polymath sentence identity: extraction keeps
summarizer.split_sentences.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field

import numpy as np

from polymath_shared.identity import chunk_id as make_chunk_id
from workers.summarizer import split_sentences, summarize, summarize_children

CHUNK_CONTRACT_V2 = "chunk-contract-v2"
CHONKIE_VERSION = "1.7.0"
HARD_BOUNDARY_POLICY = "hard-boundary-v1"
SENTENCE_CONTRACT = "sentence-contract-v1"
TOKENIZER_CONTRACT = "chonkie-word-v1"

SEMANTIC_V2_DEFAULTS = {
    "threshold": 0.65,          # first controlled-matrix value (see harness)
    "similarity_window": 1,
    "max_chunk_tokens": 256,
    "min_sentences_per_chunk": 1,
    "filter_window": 5,
    "filter_polyorder": 3,
    "filter_tolerance": 0.2,
    "skip_window": 0,           # mandatory: contiguous spans only
    "parent_fanout": 4,
    "child_target_chars_fallback": 1200,
}

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
_CODE_FENCE_RE = re.compile(r"^```")
_TABLE_RE = re.compile(r"^\s*\|.*\|\s*$")
_LIST_RE = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+")


@dataclass(frozen=True)
class Region:
    kind: str            # heading | prose | code | table | list
    text: str            # exact source substring
    start: int           # document-relative char offset
    heading_path: tuple[str, ...]


def split_structural_regions(text: str) -> list[Region]:
    """Deterministic markdown-aware structural scan. Headings, fenced
    code, tables, and list blocks are hard boundaries; a heading NEVER
    becomes part of a prose region's text (the general fix for the
    header bug: headings live in heading_path metadata, not in chunk
    body text)."""
    regions: list[Region] = []
    heading: tuple[str, ...] = ()
    lines = text.splitlines(keepends=True)
    i = 0
    offset = 0

    def _flush(buf: list[tuple[str, int]], kind: str, hpath: tuple[str, ...]):
        if not buf:
            return
        region_text = "".join(line for line, _ in buf)
        regions.append(Region(kind=kind, text=region_text,
                              start=buf[0][1], heading_path=hpath))

    prose_buf: list[tuple[str, int]] = []
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        in_fence = any(k == "code" for k in (regions[-1].kind if regions else "",)) and not regions[-1].text.endswith("```")
        m = _HEADING_RE.match(stripped)
        if m and not in_fence:
            _flush(prose_buf, "prose", heading)
            prose_buf = []
            heading = heading + (m.group(2).strip(),)
            regions.append(Region(kind="heading", text=line, start=offset, heading_path=heading))
        elif _CODE_FENCE_RE.match(stripped):
            _flush(prose_buf, "prose", heading)
            prose_buf = []
            start = offset
            block = [line]
            i += 1
            offset += len(line)
            while i < len(lines) and not _CODE_FENCE_RE.match(lines[i].strip()):
                block.append(lines[i])
                offset += len(lines[i])
                i += 1
            if i < len(lines):
                block.append(lines[i])
                offset += len(lines[i])
                i += 1
            regions.append(Region(kind="code", text="".join(block), start=start, heading_path=heading))
            continue
        elif _TABLE_RE.match(line):
            _flush(prose_buf, "prose", heading)
            prose_buf = []
            start = offset
            block = []
            while i < len(lines) and _TABLE_RE.match(lines[i]):
                block.append(lines[i])
                offset += len(lines[i])
                i += 1
            regions.append(Region(kind="table", text="".join(block), start=start, heading_path=heading))
            continue
        elif _LIST_RE.match(line) and stripped:
            # contiguous list blocks are hard boundaries (bullet prose
            # is not argument prose; Chonkie similarity is meaningless
            # across list items)
            _flush(prose_buf, "prose", heading)
            prose_buf = []
            start = offset
            block = []
            while i < len(lines) and (lines[i].strip() == "" or _LIST_RE.match(lines[i])):
                if lines[i].strip() == "" and i + 1 < len(lines) and not _LIST_RE.match(lines[i + 1]):
                    break
                block.append(lines[i])
                offset += len(lines[i])
                i += 1
            regions.append(Region(kind="list", text="".join(block).rstrip(), start=start, heading_path=heading))
            continue
        else:
            prose_buf.append((line, offset))
        offset += len(line)
        i += 1
    _flush(prose_buf, "prose", heading)
    return regions


try:
    from chonkie import BaseEmbeddings as _ChonkieBaseEmbeddings
except ImportError:  # pragma: no cover - chonkie is pinned in the root venv
    _ChonkieBaseEmbeddings = object


class PolymathEmbeddingsAdapter(_ChonkieBaseEmbeddings):
    """Chonkie-compatible embeddings over Polymath's pinned Qwen sidecar
    (batch ≤ 32 per the /infer contract) with a content-addressed
    cache. No new model is loaded anywhere."""

    def __init__(self, cache: "SemanticEmbeddingCache"):
        if _ChonkieBaseEmbeddings is object:
            raise RuntimeError("chonkie is not installed")
        super().__init__()
        self._cache = cache
        self._dimension: int | None = None

    @property
    def dimension(self) -> int:
        if self._dimension is None:
            v = self.embed("dimension probe")
            self._dimension = len(v)
        return self._dimension

    def embed(self, text: str) -> np.ndarray:
        return np.asarray(self.embed_batch([text])[0], dtype=np.float32)

    def embed_batch(self, texts: list[str]) -> list[np.ndarray]:
        out: list[np.ndarray | None] = [None] * len(texts)
        missing: list[int] = []
        for idx, t in enumerate(texts):
            hit = self._cache.get(t)
            if hit is not None:
                out[idx] = np.asarray(hit, dtype=np.float32)
            else:
                missing.append(idx)
        for b in range(0, len(missing), 32):
            batch_idx = missing[b:b + 32]
            vectors = self._cache.embed_texts([texts[i] for i in batch_idx])
            for i, vec in zip(batch_idx, vectors):
                self._cache.put(texts[i], vec)
                out[i] = np.asarray(vec, dtype=np.float32)
        return out

    def similarity(self, u: np.ndarray, v: np.ndarray) -> np.float64:
        return np.float64(np.dot(u, v) / (np.linalg.norm(u) * np.linalg.norm(v) + 1e-12))

    def get_tokenizer(self):
        from chonkie import WordTokenizer

        return WordTokenizer()


class SemanticEmbeddingCache:
    """Content-addressed sentence/window embedding cache: Postgres
    authority, disposable/reconstructible. Key = sha256(embedding
    contract + text)."""

    def __init__(self, dsn: str | None = None):
        self._dsn = dsn
        self.hits = 0
        self.misses = 0
        self.requests = 0

    def _key(self, text: str) -> str:
        from polymath_shared.embedding_contracts import active_contract

        contract = active_contract().contract_id
        return hashlib.sha256(f"{contract}|{text}".encode()).hexdigest()

    def get(self, text: str) -> list[float] | None:
        self.requests += 1
        row = self._q("SELECT vector FROM semantic_embedding_cache WHERE cache_key=%s",
                      (self._key(text),))
        if row:
            self.hits += 1
            return row[0]
        self.misses += 1
        return None

    def put(self, text: str, vector: list[float]) -> None:
        self._x("INSERT INTO semantic_embedding_cache (cache_key, vector) "
                "VALUES (%s, %s) ON CONFLICT (cache_key) DO NOTHING",
                (self._key(text), json.dumps(vector)))

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        from polymath_shared.clients import EmbedderClient

        client = EmbedderClient()
        try:
            client.verify_pin()
            out = []
            for i in range(0, len(texts), 32):
                r = client.embed(texts[i:i + 32], representation_kind="child_chunk")
                out.extend(r["vectors"])
            return out
        finally:
            client.close()

    def _q(self, sql, params):
        import psycopg

        with psycopg.connect(self._dsn or _default_dsn()) as c:
            row = c.execute(sql, params).fetchone()
            if not row:
                return None
            vec = row[0]
            return (json.loads(vec) if isinstance(vec, str) else vec,)

    def _x(self, sql, params):
        import psycopg

        with psycopg.connect(self._dsn or _default_dsn()) as c:
            c.execute(sql, params)
            c.commit()


def _default_dsn() -> str:
    from polymath_shared.settings import get_settings

    return get_settings().postgres.dsn


def chunk_contract_identity(params: dict | None = None) -> dict:
    """Every input that can change chunk output — the contract identity
    (§21). Any change creates a new interpretation."""
    p = dict(SEMANTIC_V2_DEFAULTS)
    if params:
        p.update(params)
    return {
        "contract": CHUNK_CONTRACT_V2,
        "provider": "semantic_v2",
        "provider_version": "2.0.0",
        "chonkie_version": CHONKIE_VERSION,
        "embedding": _embedding_identity(),
        "semantic_threshold": p["threshold"],
        "similarity_window": p["similarity_window"],
        "max_chunk_tokens": p["max_chunk_tokens"],
        "min_sentences": p["min_sentences_per_chunk"],
        "filter_window": p["filter_window"],
        "filter_polyorder": p["filter_polyorder"],
        "filter_tolerance": p["filter_tolerance"],
        "skip_window": p["skip_window"],
        "hard_boundary_policy": HARD_BOUNDARY_POLICY,
        "sentence_contract": SENTENCE_CONTRACT,
        "tokenizer_contract": TOKENIZER_CONTRACT,
    }


def _embedding_identity() -> dict:
    from polymath_shared.clients import EmbedderClient

    client = EmbedderClient()
    try:
        m = client.manifest()
        model = m.get("identity", {}).get("model", {})
        return {
            "contract_id": m.get("contract_id"),
            "model": model.get("id"),
            "revision": model.get("revision"),
        }
    finally:
        client.close()


def semantic_chunk_rows(text: str, doc_id: str, *,
                        cache: SemanticEmbeddingCache,
                        params: dict | None = None) -> list[dict]:
    """Semantic-v2 chunk rows for one document: structural regions →
    Chonkie inside prose regions only → contiguous, offset-validated
    children (+ deterministic parent summaries, same hierarchy shape as
    legacy). Heading text NEVER appears in chunk body text.

    Offset contract (§8): each chunk is an EXACT substring of the
    source document — source[start:end] == text — with exactly one
    documented normalization: leading/trailing whitespace of Chonkie's
    sentence-group span is trimmed, and offsets are adjusted to match."""
    from chonkie import SemanticChunker

    p = dict(SEMANTIC_V2_DEFAULTS)
    if params:
        p.update(params)
    regions = split_structural_regions(text)
    adapter = PolymathEmbeddingsAdapter(cache)

    children: list[dict] = []
    for region in regions:
        if region.kind == "heading":
            continue  # metadata only — never chunk-body text
        if region.kind in ("code", "table", "list"):
            children.append(_region_row(region, doc_id))
            continue
        prose = region.text.strip()
        if not prose:
            continue
        prose_offset = len(region.text) - len(region.text.lstrip())  # strip() == lstrip() here (already rstripped? no — compute both)
        lead_ws = len(region.text) - len(region.text.lstrip())
        trail_ws = len(region.text) - len(region.text.rstrip())
        core = region.text[lead_ws:len(region.text) - trail_ws]
        assert core == prose, "prose anchoring mismatch"
        chunker = SemanticChunker(
            embedding_model=adapter,
            threshold=p["threshold"],
            chunk_size=p["max_chunk_tokens"],
            similarity_window=p["similarity_window"],
            min_sentences_per_chunk=p["min_sentences_per_chunk"],
            skip_window=0,
            filter_window=p["filter_window"],
            filter_polyorder=p["filter_polyorder"],
            filter_tolerance=p["filter_tolerance"],
        )
        for c in chunker.chunk(prose):
            raw = prose[c.start_index:c.end_index]
            chunk_text = raw.strip()
            if not chunk_text:
                continue
            rel_start = c.start_index + (len(raw) - len(raw.lstrip()))
            rel_end = rel_start + len(chunk_text)
            # exactness proof: chunk_text IS prose[rel_start:rel_end]
            assert prose[rel_start:rel_end] == chunk_text
            abs_start = region.start + lead_ws + rel_start
            abs_end = region.start + lead_ws + rel_end
            assert text[abs_start:abs_end] == chunk_text, "document offset roundtrip failed"
            children.append({
                "doc_id": doc_id,
                "tier": "child",
                "text": chunk_text,
                "summary": summarize(chunk_text, max_sentences=2, max_chars=420),
                "char_start": abs_start,
                "char_end": abs_end,
                "heading_path": list(region.heading_path),
                "token_count": _token_count(chunk_text),
                "chunk_contract_version": CHUNK_CONTRACT_V2,
                "provider": "semantic_v2",
            })

    _validate_contiguous(children, text)
    rows = _with_parents(children, doc_id, p["parent_fanout"], text)
    return rows


def _with_parents(children: list[dict], doc_id: str, fanout: int, text: str) -> list[dict]:
    """Assign child ids, then parent rows (deterministic extractive
    summaries over fanout groups) with real child ids wired."""
    for i, child in enumerate(children):
        child["chunk_index"] = i
        child["chunk_id"] = make_chunk_id(doc_id, i, child["text"])
        child["parent_id"] = None
    rows: list[dict] = list(children)
    base = len(children)
    for j in range(0, len(children), fanout):
        group = children[j:j + fanout]
        summary = summarize_children([c["text"] for c in group])
        parent = {
            "chunk_id": make_chunk_id(doc_id, base + j, summary),
            "doc_id": doc_id,
            "parent_id": None,
            "chunk_index": base + j,
            "tier": "parent",
            "text": summary,
            "summary": summary,
            "char_start": group[0]["char_start"],
            "char_end": group[-1]["char_end"],
            "heading_path": group[0].get("heading_path", []),
            "token_count": _token_count(summary),
            "chunk_contract_version": CHUNK_CONTRACT_V2,
            "provider": "semantic_v2",
        }
        rows.append(parent)
        for c in group:
            c["parent_id"] = parent["chunk_id"]
    return rows


def _region_row(region: Region, doc_id: str) -> dict:
    text = region.text.strip()
    lead = len(region.text) - len(region.text.lstrip())
    return {
        "doc_id": doc_id, "tier": "child",
        "text": text,
        "summary": summarize(text, max_sentences=2, max_chars=420),
        "char_start": region.start + lead,
        "char_end": region.start + lead + len(text),
        "heading_path": list(region.heading_path),
        "token_count": _token_count(text),
        "chunk_contract_version": CHUNK_CONTRACT_V2,
        "provider": "semantic_v2",
    }


def _exact_span(region: Region, abs_start: int, text: str) -> bool:
    return region.start <= abs_start and abs_start + len(text) <= region.start + len(region.text)


def _token_count(text: str) -> int:
    return len(text.split())


def _validate_contiguous(children: list[dict], source: str) -> None:
    """§8: every chunk is a real substring, start<end, monotonic, no
    overlap. Gaps are allowed (headings/metadata excluded)."""
    last_end = -1
    for row in children:
        assert 0 <= row["char_start"] < row["char_end"] <= len(source), "chunk offsets out of range"
        assert row["char_start"] >= last_end, "chunk overlap"
        assert source[row["char_start"]:row["char_end"]] == row["text"], "offset roundtrip failed"
        last_end = row["char_end"]