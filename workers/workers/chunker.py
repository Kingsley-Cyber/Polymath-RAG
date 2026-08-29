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

import re
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
    #: which chunk contract produced these spans (see CHUNK_CONTRACT)
    contract: str = "chunk-structure-v1"


#: CHUNK-STRUCTURE-V2 (2026-08-28). The v1 packer joins every sentence
#: with a single space, which is why 0 of 7,085 production chunks contain
#: a newline and 74% carry a markdown heading glued mid-text.
#:
#: That is not cosmetic. PROVEN by controlled experiment: the identical
#: definitional sentence is detected in source form and MISSED in stored
#: form.
#:
#: MECHANISM, measured — and NOT the one the pass-3 report claimed. No
#: characters are lost: `split_sentences` returns the glued text whole
#: (203 chars in, 203 chars out). It FAILS TO SPLIT, because its
#: boundary rule needs `[.!?]` followed by a capital-or-digit and "#"
#: is neither. The definition therefore stops BEGINNING a sentence, and
#: the concept patterns anchor on sentence start. Structure loss
#: destroys extraction by suppressing anchors, not by deleting text.
#:
#: V2 does NOT blindly insert "\n". It RECONSTRUCTS the separator that
#: actually existed, using the source offsets the packer already has:
#: the gap between sentence i and i+1 is source_text[end_i:start_{i+1}].
#: A paragraph break stays a paragraph break, a line break stays a line
#: break, and an ordinary sentence gap stays a space — so code
#: indentation, list items, table rows and transcript turns survive
#: because they were newline-separated in the source to begin with.
SEPARATOR_LEGACY = "legacy_space"
SEPARATOR_SOURCE = "source_structure"

CHUNK_CONTRACT_V1 = "chunk-structure-v1"
CHUNK_CONTRACT_V2 = "chunk-structure-v2"

#: A plan states which generation produced it. Chunk ids already differ
#: (the text differs), but an id alone cannot say WHY it differs, and a
#: half-old/half-new corpus is the failure mode P13 has to make
#: impossible. The stamp is what makes the two generations tellable
#: apart without re-deriving them.
CHUNK_CONTRACT = {
    SEPARATOR_LEGACY: CHUNK_CONTRACT_V1,
    SEPARATOR_SOURCE: CHUNK_CONTRACT_V2,
}


#: A newline that only wrapped a line is PRESENTATION, not structure.
#: P6 proved the cost of treating it as structure: on hard-wrapped
#: source, `split_sentences` splits on every newline, so
#: "Nessus was\ndeveloped by Tenable." becomes two fragments and the
#: fact can never be built. V1 hid this because its space join
#: accidentally reassembled the wrap; V2 preserves newlines, so V2 has
#: to tell a wrap from a break.
#:
#: The substitution is LENGTH-PRESERVING (one "\n" -> one " "), so every
#: char offset into the source stays exactly valid. That is why this is
#: a substitution and not an unwrap-and-reflow.
_WRAP_HARD_LINE = re.compile(r"^\s*(?:[-*+]\s|\d+[.)]\s|#{1,6}\s|\||>|\s{4,})")


def _soften_wraps(text: str) -> str:
    """Turn soft line wraps into spaces, leaving structure alone.

    A newline is a SOFT wrap only when the line it ends does not close a
    sentence and neither side opens a structural unit (heading, list
    item, table row, quote, indented code). Blank-line paragraph breaks
    are never touched.
    """
    lines = text.split("\n")
    out: list[str] = []
    for i, line in enumerate(lines):
        out.append(line)
        if i + 1 >= len(lines):
            continue
        nxt = lines[i + 1]
        soft = (line.strip() and nxt.strip()
                and not re.search(r"[.!?:;]\s*$", line)
                and not _WRAP_HARD_LINE.match(line)
                and not _WRAP_HARD_LINE.match(nxt))
        out.append(" " if soft else "\n")
    return "".join(out)


def _reconstruct_separator(source_text: str, prev_end: int,
                           next_start: int) -> str:
    """The separator that actually stood between two packed sentences.

    Line COUNT is normalised — one break or a paragraph break, never a
    run of six blank lines — but the INDENTATION of the following line
    is reproduced exactly, because that indentation is the structure.
    `split_sentences` strips every part it returns, so a code line's
    leading spaces and a sub-list item's offset survive nowhere else:
    they sit in this gap, and discarding them flattens code blocks and
    list hierarchy just as surely as the space join did.
    """
    if next_start <= prev_end:
        return " "
    gap = source_text[prev_end:next_start]
    if gap.strip():
        # Non-whitespace in the gap means the sentence offsets did not
        # line up with the source (a repeated sentence resolving to an
        # earlier occurrence). Reproduce it verbatim rather than invent
        # a separator — literal fidelity outranks normalisation here.
        return gap
    newlines = gap.count("\n")
    if not newlines:
        return " "
    indent = gap[gap.rindex("\n") + 1:]
    return ("\n\n" if newlines >= 2 else "\n") + indent


def _pack_sentences_v2(
    sentences: list[str],
    starts: list[int],
    target_chars: int,
    source_text: str,
    layout: list[tuple[int, int]] | None = None,
) -> list[ChunkSpec]:
    """Structure-preserving greedy packing (CHUNK_CONTRACT_V2).

    Same packing DECISIONS as v1 — never splits a sentence, same
    target-driven flush — so chunk boundaries are comparable. Only the
    JOIN changes: sentences are rejoined with their real separators.
    """
    from polymath_shared.layout_evidence import project_regions

    chunks: list[ChunkSpec] = []
    buf: list[str] = []
    seps: list[str] = []
    buf_len = 0
    idxs: list[int] = []
    first_start = 0
    last_end = 0
    heads: list[tuple[int, int]] = []

    def _joined() -> str:
        out = []
        for i, s in enumerate(buf):
            if i:
                out.append(seps[i - 1])
            out.append(s)
        return "".join(out)

    def _flush():
        chunks.append(ChunkSpec(
            text=_joined(), char_start=first_start, char_end=last_end,
            sentences=tuple(idxs), layout_headings=tuple(heads),
        ))

    prev_end = None
    for i, (sentence, start) in enumerate(zip(sentences, starts)):
        end = start + len(sentence)
        if buf and buf_len + 1 + len(sentence) > target_chars:
            _flush()
            buf, seps, buf_len, idxs, heads = [], [], 0, [], []
            first_start = start
            prev_end = None
        if buf:
            seps.append(_reconstruct_separator(source_text, prev_end, start))
        # chunk-relative offset must count the REAL separators now
        offset = 0 if not buf else len(_joined()) + len(seps[-1])
        if layout:
            heads.extend(project_regions(layout, start, end, offset))
        buf.append(sentence)
        buf_len += len(sentence)
        idxs.append(i)
        last_end = end
        prev_end = end

    if buf:
        _flush()
    return chunks


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
    separator_mode: str = SEPARATOR_LEGACY,
) -> ChunkPlan:
    """Deterministic chunk plan for one document.

    Pure function: no randomness, no model. `doc_id` must already be the
    content-hashed document identity (identity.document_id).

    `separator_mode` selects the chunk contract. SEPARATOR_LEGACY is the
    frozen v1 behaviour (space join) and stays the DEFAULT so nothing
    re-identifies by accident; SEPARATOR_SOURCE is CHUNK_CONTRACT_V2,
    which rejoins sentences with the separator that actually existed in
    the source. The two generations are never silently equated — chunk
    ids differ because the text differs, which is the point.
    """
    # CHUNK_CONTRACT_V2 repairs soft wraps BEFORE sentence splitting.
    # Length-preserving, so every offset below still indexes the source.
    if separator_mode == SEPARATOR_SOURCE:
        text = _soften_wraps(text)
    sentences = split_sentences(text)
    contract = CHUNK_CONTRACT.get(separator_mode)
    if contract is None:
        raise ValueError(
            f"unknown separator_mode {separator_mode!r}; a chunk generation "
            f"must name its contract (one of {sorted(CHUNK_CONTRACT)})")

    if not sentences:
        return ChunkPlan(doc_id=doc_id, children=[], parents=[],
                         document_summary="", fanout=parent_fanout,
                         contract=contract)

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
    if separator_mode == SEPARATOR_SOURCE:
        children = _pack_sentences_v2(
            sentences, starts, child_target_chars, text, layout)
    else:
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
        contract=contract,
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
            "chunk_contract_version": plan.contract,
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
            "chunk_contract_version": plan.contract,
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
