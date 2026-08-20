"""Sentence-aligned child/parent chunker. No LLM, deterministic.

Contract (ADR-0001 §2, docx §2):
  - chunks are sentence-aligned: a sentence is never split mid-way;
  - every chunk carries char offsets into the source document;
  - parents summarize children (deterministic extractive summaries);
  - chunk identity is a content hash, so re-chunking unchanged text is
    a no-op and shifted text only shifts the chunks it touches.

Top-down retrieval shape (the point of the tiering): document routing
card -> parent chunk (summary) -> child chunk (evidence). The parent
layer is the cheap scan layer; children are only pulled when a parent
matches.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from polymath_shared.identity import chunk_id
from workers.summarizer import split_sentences, summarize, summarize_children


@dataclass(frozen=True)
class ChunkSpec:
    text: str
    char_start: int
    char_end: int
    sentences: tuple[int, ...]  # global sentence indices
    # LAYOUT-EVIDENCE-V1: chunk-relative [start,end) ranges that are heading
    # text. The chunker is the only component holding both the document and
    # chunk coordinate systems at once, so the projection happens here.
    layout_headings: tuple[tuple[int, int], ...] = ()


@dataclass(frozen=True)
class ChunkPlan:
    doc_id: str
    children: list[ChunkSpec]
    parents: list[ChunkSpec]  # parent i summarizes children[fanout*i : fanout*(i+1)]
    document_summary: str
    fanout: int
    # layout-evidence-v1 regions in MATERIALIZED SOURCE offsets
    layout: list[dict] = field(default_factory=list)


def _pack_sentences(
    sentences: list[str],
    starts: list[int],
    target_chars: int,
    layout: list[tuple[int, int]] | None = None,
) -> list[ChunkSpec]:
    """Greedy sentence packing. Never splits a sentence; a sentence longer
    than the target becomes its own chunk.

    `layout` are document-offset heading regions. They are projected into
    chunk coordinates AS THE CHUNK IS ASSEMBLED, because that is the only
    moment both coordinate systems are known. Chunk TEXT is unchanged.
    """
    from polymath_shared.layout_evidence import project_regions

    chunks: list[ChunkSpec] = []
    buf: list[str] = []
    buf_len = 0
    idxs: list[int] = []
    first_start = 0
    last_end = 0
    heads: list[tuple[int, int]] = []
    offset = 0            # chunk-relative offset of the next sentence

    def _flush():
        chunks.append(ChunkSpec(
            text=" ".join(buf), char_start=first_start, char_end=last_end,
            sentences=tuple(idxs), layout_headings=tuple(heads),
        ))

    for i, (sentence, start) in enumerate(zip(sentences, starts)):
        end = start + len(sentence)
        if buf and buf_len + 1 + len(sentence) > target_chars:
            _flush()
            buf, buf_len, idxs, heads = [], 0, [], []
            first_start = start
        # Chunk-relative start of this sentence inside `" ".join(buf)`:
        # the joined length so far, plus one for the separator. `buf_len`
        # keeps its ORIGINAL meaning (sum of sentence lengths, no
        # separators) so packing decisions — and therefore chunk text,
        # chunk ids and embeddings — are bit-for-bit unchanged.
        offset = 0 if not buf else buf_len + len(buf)
        if layout:
            heads.extend(project_regions(layout, start, end, offset))
        buf.append(sentence)
        buf_len += len(sentence)
        idxs.append(i)
        last_end = end

    if buf:
        _flush()
    return chunks


def plan_document(
    text: str,
    doc_id: str,
    *,
    child_target_chars: int = 1200,
    parent_fanout: int = 4,
) -> ChunkPlan:
    """Deterministic chunk plan for one document.

    Pure function: no randomness, no model. `doc_id` must already be the
    content-hashed document identity (identity.document_id).
    """
    sentences = split_sentences(text)
    if not sentences:
        return ChunkPlan(doc_id=doc_id, children=[], parents=[], document_summary="", fanout=parent_fanout)

    starts: list[int] = []
    cursor = 0
    for sentence in sentences:
        starts.append(text.find(sentence, cursor))
        cursor = starts[-1] + len(sentence)

    # LAYOUT-EVIDENCE-V1: detected HERE, on the materialized source text,
    # which still has its line structure. Nothing downstream may re-derive
    # it from chunk text — that text is joined with spaces and no longer
    # carries the lines the detection depends on.
    from polymath_shared.layout_evidence import heading_regions

    layout = heading_regions(text)
    children = _pack_sentences(sentences, starts, child_target_chars, layout)
    parents: list[ChunkSpec] = []
    for i in range(0, len(children), parent_fanout):
        group = children[i : i + parent_fanout]
        text_block = " ".join(c.text for c in group)
        parents.append(ChunkSpec(
            text=summarize_children([c.text for c in group]),
            char_start=group[0].char_start,
            char_end=group[-1].char_end,
            sentences=tuple(s for c in group for s in c.sentences),
        ))

    return ChunkPlan(
        doc_id=doc_id,
        children=children,
        parents=parents,
        document_summary=summarize(text, max_sentences=6, max_chars=1600),
        fanout=parent_fanout,
        layout=[{"kind": "heading", "char_start": a, "char_end": b}
                for a, b in layout],
    )


def materialize_chunks(plan: ChunkPlan) -> list[dict]:
    """Render a plan into chunk rows (children then parents, parent_id set).

    chunk_index ordering: children keep their document order; parents are
    appended after the last child, also in document order. The index is
    part of the chunk identity, so the same text always yields the same
    (id, index) pairs.
    """
    rows: list[dict] = []
    child_by_spec: dict[int, dict] = {}

    for i, spec in enumerate(plan.children):
        row = {
            "chunk_id": chunk_id(plan.doc_id, i, spec.text),
            "doc_id": plan.doc_id,
            "parent_id": None,
            "chunk_index": i,
            "tier": "child",
            "text": spec.text,
            "summary": summarize(spec.text, max_sentences=2, max_chars=420),
            "char_start": spec.char_start,
            "char_end": spec.char_end,
            # layout-evidence-v1 projection; [] means "detected, none here",
            # which is different from NULL meaning "never detected".
            "layout_map": [[a, b] for a, b in spec.layout_headings],
        }
        rows.append(row)
        child_by_spec[i] = row

    base = len(plan.children)
    parent_rows: list[dict] = []
    for j, spec in enumerate(plan.parents):
        first_child = j * plan.fanout
        child_ids = [
            child_by_spec[k]["chunk_id"]
            for k in range(first_child, min(first_child + plan.fanout, len(plan.children)))
        ]
        parent_row = {
            "chunk_id": chunk_id(plan.doc_id, base + j, spec.text),
            "doc_id": plan.doc_id,
            "parent_id": None,
            "chunk_index": base + j,
            "tier": "parent",
            "text": spec.text,
            "summary": spec.text,
            "char_start": spec.char_start,
            "char_end": spec.char_end,
            "_children": child_ids,
        }
        parent_rows.append(parent_row)
        rows.append(parent_row)

    for parent_row in parent_rows:
        for child_id in parent_row.pop("_children"):
            for row in rows:
                if row["chunk_id"] == child_id:
                    row["parent_id"] = parent_row["chunk_id"]

    return rows
