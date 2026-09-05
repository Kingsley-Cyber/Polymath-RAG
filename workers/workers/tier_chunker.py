"""TIER-CHUNKER-V3: heading-bounded parents with byte-exact offsets.

chunk-structure-v3 (latent plan D15, Phase 0). Parents are the
author's own sections — every parent span lies inside exactly one
heading_path — sized in words to ~850 target / 1,400 max. Parent text
is the REAL section text (an exact source substring, heading line
included), not a summary: enrichment compiles one canonical section
per call and hydration serves what the author wrote. Children are
exact sub-spans of their parent: prose packs at paragraph/sentence
boundaries, code/table/list blocks stay atomic. Heading lines never
appear in CHILD body text (they live in heading_path and in the
parent span), matching the v2 header rule.

Deviations from the v3.3 module this replaces (recorded in the plan's
D15 amendment): implemented natively on exact source spans — v3.3
rewrote text (markup scrub, token re-joins), which would break v4's
offset contract (§8) that UI provenance and the projection verifiers
rely on. Noise-kind classification is NOT re-implemented here: v4
already classifies region roles at insert time from heading_path
(region_role.py) — this chunker's job is to finally supply real
heading paths. Sub-stub sections (<15 non-heading words) drop at
chunk time, as in v3.3.

Everything here is deterministic: same text → same regions → same
spans → same content-addressed ids. No models, no embedder, no RNG.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from polymath_shared.identity import chunk_id as make_chunk_id
from workers.summarizer import summarize

CHUNK_CONTRACT_V3 = "chunk-structure-v3.1"   # TIER-CHUNKER-V3.1 (2026-09-05): small-section merge + fragment coalescing
PROVIDER = "tier_v3"

#: word budgets (a "word" is len(text.split()) — the v4 tokenizer
#: contract for chunk rows). D15: ~850 w target / 1,400 w max parents.
TIER_FROZEN_PARAMS = {
    "contract": CHUNK_CONTRACT_V3,
    "parent_target_words": 850,
    "parent_max_words": 1400,
    "parent_min_words": 280,
    "parent_stub_words": 15,
    "child_target_words": 120,
    "child_max_words": 250,
    "child_fragment_floor_words": 25,
    "atomic_child_max_words": 700,
}

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
_CODE_FENCE_RE = re.compile(r"^```")
_TABLE_RE = re.compile(r"^\s*\|.*\|\s*$")
_LIST_RE = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+")
_PARA_SEP_RE = re.compile(r"\n[ \t]*\n+")
_SENTENCE_CUT_RE = re.compile(r"(?<=[.!?])\s+")


@dataclass(frozen=True)
class TierRegion:
    kind: str                    # heading | prose | code | table | list
    text: str                    # exact source substring
    start: int                   # document-relative char offset
    heading_path: tuple[str, ...]
    level: int = 0               # heading level; 0 for non-headings

    @property
    def end(self) -> int:
        return self.start + len(self.text)


def _words(text: str) -> int:
    return len(text.split())


def walk_regions(text: str) -> list[TierRegion]:
    """Level-aware structural scan. Unlike the v2 walker, the heading
    stack POPS on same-or-shallower levels (an H2 after an H2 replaces
    it; an H1 clears the stack) — heading_path is the section's true
    ancestry, not the document's heading history. Every source byte
    belongs to some region, so section spans are contiguous."""
    regions: list[TierRegion] = []
    stack: list[tuple[int, str]] = []          # (level, title)
    lines = text.splitlines(keepends=True)
    i, offset = 0, 0
    prose_buf: list[tuple[str, int]] = []

    def path() -> tuple[str, ...]:
        return tuple(t for _, t in stack)

    def flush_prose() -> None:
        nonlocal prose_buf
        if prose_buf:
            regions.append(TierRegion(
                kind="prose",
                text="".join(ln for ln, _ in prose_buf),
                start=prose_buf[0][1], heading_path=path()))
            prose_buf = []

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        m = _HEADING_RE.match(stripped)
        if m:
            flush_prose()
            level = len(m.group(1))
            while stack and stack[-1][0] >= level:
                stack.pop()
            stack.append((level, m.group(2).strip()))
            regions.append(TierRegion(
                kind="heading", text=line, start=offset,
                heading_path=path(), level=level))
        elif _CODE_FENCE_RE.match(stripped):
            flush_prose()
            start = offset
            block = [line]
            i += 1
            offset += len(line)
            while i < len(lines) and not _CODE_FENCE_RE.match(lines[i].strip()):
                block.append(lines[i])
                offset += len(lines[i])
                i += 1
            if i < len(lines):                 # closing fence
                block.append(lines[i])
                offset += len(lines[i])
                i += 1
            regions.append(TierRegion(
                kind="code", text="".join(block), start=start,
                heading_path=path()))
            continue
        elif _TABLE_RE.match(line):
            flush_prose()
            start = offset
            block: list[str] = []
            while i < len(lines) and _TABLE_RE.match(lines[i]):
                block.append(lines[i])
                offset += len(lines[i])
                i += 1
            regions.append(TierRegion(
                kind="table", text="".join(block), start=start,
                heading_path=path()))
            continue
        elif _LIST_RE.match(line) and stripped:
            flush_prose()
            start = offset
            block = []
            while i < len(lines) and (lines[i].strip() == "" or _LIST_RE.match(lines[i])):
                if lines[i].strip() == "" and i + 1 < len(lines) \
                        and not _LIST_RE.match(lines[i + 1]):
                    break
                block.append(lines[i])
                offset += len(lines[i])
                i += 1
            regions.append(TierRegion(
                kind="list", text="".join(block), start=start,
                heading_path=path()))
            continue
        else:
            prose_buf.append((line, offset))
        offset += len(line)
        i += 1
    flush_prose()
    return regions


# ── span algebra: everything below is (start, end) pairs over `text` ─────────

def _trim(text: str, start: int, end: int) -> tuple[int, int]:
    """Shrink a span to its stripped content, keeping exactness."""
    raw = text[start:end]
    lead = len(raw) - len(raw.lstrip())
    trail = len(raw) - len(raw.rstrip())
    return start + lead, end - trail


def _paragraph_spans(text: str, start: int, end: int) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    cursor = start
    body = text[start:end]
    for m in _PARA_SEP_RE.finditer(body):
        s, e = _trim(text, cursor, start + m.start())
        if s < e:
            spans.append((s, e))
        cursor = start + m.end()
    s, e = _trim(text, cursor, end)
    if s < e:
        spans.append((s, e))
    return spans


def _sentence_spans(text: str, start: int, end: int) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    cursor = start
    body = text[start:end]
    for m in _SENTENCE_CUT_RE.finditer(body):
        s, e = _trim(text, cursor, start + m.start())
        if s < e:
            spans.append((s, e))
        cursor = start + m.end()
    s, e = _trim(text, cursor, end)
    if s < e:
        spans.append((s, e))
    return spans or [(start, end)]


def _line_spans(text: str, start: int, end: int, max_words: int) -> list[tuple[int, int]]:
    """Split a span at LINE boundaries into ≤max_words pieces (giant
    code blocks / tables — atomic units that still must embed)."""
    out: list[tuple[int, int]] = []
    buf_start: int | None = None
    buf_words = 0
    cursor = start
    for line in text[start:end].splitlines(keepends=True):
        line_end = cursor + len(line)
        w = _words(line)
        if buf_start is not None and buf_words + w > max_words:
            s, e = _trim(text, buf_start, cursor)
            if s < e:
                out.append((s, e))
            buf_start, buf_words = None, 0
        if buf_start is None:
            buf_start = cursor
        buf_words += w
        cursor = line_end
    if buf_start is not None:
        s, e = _trim(text, buf_start, cursor)
        if s < e:
            out.append((s, e))
    final: list[tuple[int, int]] = []
    for s, e in out:                       # a single giant LINE still splits
        if _words(text[s:e]) > max_words:
            final.extend(_hard_word_spans(text, s, e, max_words))
        else:
            final.append((s, e))
    return final or [(start, end)]


def _pack_spans(text: str, spans: list[tuple[int, int]],
                target: int, cap: int) -> list[tuple[int, int]]:
    """Greedily merge consecutive spans to ~target words, never past
    cap. The merged span is text[first_start:last_end] — separators
    between spans stay inside, so exactness is trivial."""
    out: list[tuple[int, int]] = []
    buf: tuple[int, int] | None = None
    for span in spans:
        if buf is None:
            buf = span
            continue
        if (_words(text[buf[0]:span[1]]) > cap
                or _words(text[buf[0]:buf[1]]) >= target):
            out.append(buf)
            buf = span
        else:
            buf = (buf[0], span[1])
    if buf is not None:
        out.append(buf)
    return out


def _hard_word_spans(text: str, start: int, end: int,
                     max_words: int) -> list[tuple[int, int]]:
    """Last-line-of-defense: split at whitespace runs into ≤max_words
    exact spans (giant unbroken blobs with no sentence boundaries)."""
    out: list[tuple[int, int]] = []
    buf_start = None
    last_end = start
    count = 0
    for m in re.finditer(r"\S+", text[start:end]):
        if buf_start is None:
            buf_start = start + m.start()
        last_end = start + m.end()
        count += 1
        if count >= max_words:
            out.append((buf_start, last_end))
            buf_start, count = None, 0
    if buf_start is not None:
        out.append((buf_start, last_end))
    return out or [(start, end)]


def _bounded_prose_spans(text: str, start: int, end: int,
                         target: int, cap: int) -> list[tuple[int, int]]:
    """Prose spans that NEVER exceed cap: paragraphs pack to target;
    an oversize packed span re-splits at sentences; a lone oversize
    sentence hard-splits at word boundaries. Exactness throughout."""
    out: list[tuple[int, int]] = []
    for span in _pack_spans(text, _paragraph_spans(text, start, end),
                            target, cap):
        if _words(text[span[0]:span[1]]) <= cap:
            out.append(span)
            continue
        for sub in _pack_spans(text, _sentence_spans(text, span[0], span[1]),
                               target, cap):
            if _words(text[sub[0]:sub[1]]) <= cap:
                out.append(sub)
            else:
                out.extend(_hard_word_spans(text, sub[0], sub[1], cap))
    return out


def _prose_child_spans(text: str, start: int, end: int,
                       p: dict) -> list[tuple[int, int]]:
    """Paragraph-first child spans: one child per idea where the sizes
    allow; oversize paragraphs cut at sentence boundaries; fragments
    below the floor coalesce into a neighbour when the cap permits."""
    units: list[tuple[int, int]] = []
    for para in _paragraph_spans(text, start, end):
        if _words(text[para[0]:para[1]]) <= p["child_max_words"]:
            units.append(para)
            continue
        units.extend(_bounded_prose_spans(
            text, para[0], para[1],
            p["child_target_words"], p["child_max_words"]))
    # coalesce true fragments (never whole short paragraphs past the floor).
    # TIER-CHUNKER-V3.1: a fragment that ends with ":" is a LEAD-IN for
    # whatever follows the prose region (a list, a table, a code block);
    # it is left for _coalesce_fragments, which sends it forward.
    out: list[tuple[int, int]] = []
    for span in units:
        frag = text[span[0]:span[1]]
        if (out and _words(frag) < p["child_fragment_floor_words"]
                and not frag.rstrip().endswith(":")
                and _words(text[out[-1][0]:span[1]]) <= p["child_max_words"]):
            out[-1] = (out[-1][0], span[1])
        else:
            out.append(span)
    return out


# ── sections → parents → rows ────────────────────────────────────────────────

@dataclass
class _Section:
    heading_path: tuple[str, ...]
    regions: list[TierRegion]


def _sections(regions: list[TierRegion]) -> list[_Section]:
    out: list[_Section] = []
    for r in regions:
        if out and out[-1].heading_path == r.heading_path and r.kind != "heading":
            out[-1].regions.append(r)
        else:
            out.append(_Section(heading_path=r.heading_path, regions=[r]))
    return out


#: Page-scaffold headings (page-converted EPUBs/PDFs, OCR fallbacks):
#: "Page 12", "pages_3-4", "OCR_FALLBACK_TEXT". These are conversion
#: artifacts, not the author's structure — treating each page as a
#: hard section boundary would freeze parents at page size. The v3.3
#: OCR lane's rule applies instead: CONSECUTIVE page sections under
#: the same real ancestry merge to the parent budget, labelled with
#: their page range.
_PAGE_SEG_RE = re.compile(r"^(?:pages?[ _]?\d+(?:[-–]\d+)?|OCR_FALLBACK_TEXT)$",
                          re.IGNORECASE)
_PAGE_NUM_RE = re.compile(r"(\d+)")


def _scaffold_base(path: tuple[str, ...]) -> tuple[str, ...] | None:
    """The real (non-scaffold) ancestry, or None when the path's tail
    carries no page scaffolding at all."""
    base = list(path)
    stripped = False
    while base and _PAGE_SEG_RE.match(base[-1]):
        base.pop()
        stripped = True
    return tuple(base) if stripped else None


def _merge_page_sections(text: str, sections: list[_Section],
                         p: dict) -> list[_Section]:
    out: list[_Section] = []
    run: list[_Section] = []
    run_base: tuple[str, ...] | None = None

    def _flush_run() -> None:
        nonlocal run, run_base
        if not run:
            return
        merged: list[_Section] = []
        cur: _Section | None = None
        cur_words = 0
        pages: list[int] = []
        for sec in run:
            w = sum(_words(r.text) for r in sec.regions if r.kind != "heading")
            nums = [int(m.group(1)) for seg in sec.heading_path
                    for m in [_PAGE_NUM_RE.search(seg)]
                    if _PAGE_SEG_RE.match(seg) and m]
            if cur is not None and cur_words + w > p["parent_target_words"]:
                merged.append(cur)
                cur, cur_words, pages = None, 0, []
            if cur is None:
                cur = _Section(heading_path=sec.heading_path,
                               regions=list(sec.regions))
            else:
                cur.regions.extend(sec.regions)
            pages.extend(nums)
            cur_words += w
            if pages:
                label = (f"Pages {min(pages)}–{max(pages)}"
                         if len(set(pages)) > 1 else f"Page {pages[0]}")
                cur.heading_path = (run_base or ()) + (label,)
        if cur is not None:
            merged.append(cur)
        out.extend(merged)
        run, run_base = [], None

    for sec in sections:
        base = _scaffold_base(sec.heading_path)
        if base is None:
            _flush_run()
            out.append(sec)
        elif run and base == run_base:
            run.append(sec)
        else:
            _flush_run()
            run, run_base = [sec], base
    _flush_run()
    return out


def _section_body_words(section: _Section) -> int:
    return sum(_words(r.text) for r in section.regions if r.kind != "heading")


def _common_prefix(a: tuple[str, ...], b: tuple[str, ...]) -> tuple[str, ...]:
    n = 0
    for x, y in zip(a, b):
        if x != y:
            break
        n += 1
    return tuple(a[:n])


def _merge_small_sections(text: str, sections: list[_Section],
                          p: dict) -> list[_Section]:
    """TIER-CHUNKER-V3.1 (owner 2026-09-05 "fix the html list chunking"):
    a section whose body is under `parent_min_words` absorbs the sections
    that follow it (document order) until it reaches the floor or the next
    section would push it past `parent_max_words`. Measured on a 316k-word
    HTML handbook with 3,773 headings (h4/h5 used as labels): 3,167 parents
    averaging 98 words, 3,051 of them under the frozen 280-word floor —
    the floor only ever applied INSIDE a section. Same rule on a Markdown
    book: 1,322 parents (857 under the floor) → 700 (6 under).

    Doctrine kept: sub-stub sections (body < parent_stub_words) and
    heading-only sections still drop as layout evidence — a title page or
    part divider never leaks into the next chapter's first parent; only
    sections that already carry real text merge, and only with sections
    that carry real text. The merged section's heading_path is the
    deepest ancestry the merged sections share (a run of "#### label"
    sections under one "### topic" becomes one parent under the topic)."""
    out: list[_Section] = []
    stub = p["parent_stub_words"]
    last_real = -1                       # index in `out` of the last section with real body
    for sec in sections:
        w = _section_body_words(sec)
        if w >= stub and last_real >= 0:
            prev = out[last_real]
            pw = _section_body_words(prev)
            shared = _common_prefix(prev.heading_path, sec.heading_path)
            if (pw < p["parent_min_words"] and shared
                    and pw + w <= p["parent_max_words"]):
                # dropped sub-stubs between them stay in `out` as layout
                # evidence; the parent span simply covers their bytes.
                prev.heading_path = shared
                prev.regions.extend(sec.regions)
                continue
        out.append(_Section(heading_path=sec.heading_path, regions=list(sec.regions)))
        if w >= stub:
            last_real = len(out) - 1
    return out


def _coalesce_fragments(text: str, spans: list[tuple[int, int]],
                        kinds: list[str], p: dict) -> list[tuple[int, int]]:
    """TIER-CHUNKER-V3.1: a child under `child_fragment_floor_words` joins
    the NEXT child when the pair fits `child_max_words` (a lead-in such as
    "The same applies to:" travels with the list or code block it
    introduces), else the previous one. Prose-internal coalescing already
    existed; this runs across region kinds inside one parent. Measured:
    the handbook's 2,297 prose stubs were exactly these lead-ins."""
    out = list(spans)
    kind = list(kinds)
    i = 0
    while i < len(out):
        s, e = out[i]
        # structured blocks (code / table / list) stay atomic — only a
        # prose fragment moves, and a span that already absorbed one is
        # settled (never chains a code block into the next paragraph).
        if kind[i] == "prose" and _words(text[s:e]) < p["child_fragment_floor_words"]:
            if i + 1 < len(out) and _words(text[s:out[i + 1][1]]) <= p["child_max_words"]:
                out[i] = (s, out[i + 1][1])
                kind[i] = "prose" if kind[i + 1] == "prose" else "mixed"
                del out[i + 1]
                del kind[i + 1]
                continue
            if i > 0 and _words(text[out[i - 1][0]:e]) <= p["child_max_words"]:
                out[i - 1] = (out[i - 1][0], e)
                kind[i - 1] = "prose" if kind[i - 1] == "prose" else "mixed"
                del out[i]
                del kind[i]
                i -= 1
                continue
        i += 1
    return out


@dataclass
class _ParentSpan:
    start: int
    end: int
    heading_path: tuple[str, ...]
    regions: list[TierRegion]      # non-heading regions inside the span


def _parent_spans(text: str, section: _Section, p: dict) -> list[_ParentSpan]:
    """Pack a section's regions into parent spans. Never crosses the
    section boundary; a single oversize region splits internally
    (prose at paragraph/sentence boundaries, structured at lines).
    A closing merge pass absorbs sub-MIN fragment parents into a
    neighbour when the cap allows, so budget splitting never strands
    a tiny tail parent."""
    pieces: list[tuple[int, int, TierRegion, int]] = []
    for r in section.regions:
        if r.kind == "heading":
            pieces.append((r.start, r.end, r, 0))
            continue
        w = _words(r.text)
        if w <= p["parent_max_words"]:
            pieces.append((r.start, r.end, r, w))
            continue
        if r.kind == "prose":
            subs = _bounded_prose_spans(text, r.start, r.end,
                                        p["parent_target_words"],
                                        p["parent_max_words"])
        else:
            subs = _line_spans(text, r.start, r.end, p["parent_max_words"])
        pieces.extend((s, e, r, _words(text[s:e])) for s, e in subs)

    parents: list[_ParentSpan] = []
    cur: _ParentSpan | None = None
    cur_words = 0
    for s, e, r, w in pieces:
        if cur is not None and cur_words > 0 and (
                cur_words + w > p["parent_max_words"]
                or cur_words >= p["parent_target_words"]):
            parents.append(cur)
            cur, cur_words = None, 0
        if cur is None:
            cur = _ParentSpan(s, e, section.heading_path, [])
        else:
            cur.end = e
        if r.kind != "heading" and (not cur.regions or cur.regions[-1] is not r):
            cur.regions.append(r)
        cur_words += w
    if cur is not None:
        parents.append(cur)

    merged: list[_ParentSpan] = []
    for span in parents:
        if merged:
            prev = merged[-1]
            small = (_words(text[span.start:span.end]) < p["parent_min_words"]
                     or _words(text[prev.start:prev.end]) < p["parent_min_words"])
            if small and _words(text[prev.start:span.end]) <= p["parent_max_words"]:
                prev.end = span.end
                for x in span.regions:
                    if not prev.regions or prev.regions[-1] is not x:
                        prev.regions.append(x)
                continue
        merged.append(span)
    return merged


def _child_spans_for_parent(text: str, parent: _ParentSpan,
                            p: dict) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    kinds: list[str] = []
    for r in parent.regions:
        lo, hi = max(r.start, parent.start), min(r.end, parent.end)
        if lo >= hi:
            continue
        if r.kind == "prose":
            new = _prose_child_spans(text, lo, hi, p)
        else:                                   # code / table / list: atomic
            if _words(text[lo:hi]) > p["atomic_child_max_words"]:
                new = _line_spans(text, lo, hi, p["atomic_child_max_words"])
            else:
                s, e = _trim(text, lo, hi)
                new = [(s, e)] if s < e else []
        spans.extend(new)
        kinds.extend([r.kind] * len(new))
    return _coalesce_fragments(text, spans, kinds, p)


def tier_chunk_rows(text: str, doc_id: str,
                    params: dict | None = None) -> list[dict]:
    """Rows only (the historical surface). See tier_chunk_layout."""
    rows, _layout = tier_chunk_layout(text, doc_id, params)
    return rows


def tier_chunk_layout(text: str, doc_id: str,
                      params: dict | None = None) -> tuple[list[dict], list[dict]]:
    # CHUNK-GAP-ACCOUNTING-V1 (2026-09-03): the rows AND the layout evidence
    # that explains every byte no child covers. The v3.3 doctrine drops
    # sub-stub sections (title pages, part dividers, heading-only pages) and
    # keeps heading lines out of child text; before this, those drops were
    # recorded nowhere, so the literal-fidelity check read a 522-char title
    # page as possibly lost prose. Every such span is returned as a layout
    # region — kind `heading`, `dropped_stub` (section under
    # parent_stub_words of body) or `dropped_empty` (parent with no child
    # span) — and intake persists it in `document_layout`. Rows are
    # byte-identical to tier_chunk_rows: same ids, same order.
    """Chunk rows for one document under chunk-structure-v3: heading-
    bounded parents carrying REAL section text, exact-substring
    children, real heading_path on every row. Same row shape/ordering
    convention as the other providers (children in document order,
    parents appended after, content-addressed ids)."""
    p = dict(TIER_FROZEN_PARAMS)
    if params:
        p.update(params)

    regions = walk_regions(text)
    layout: list[dict] = [{"kind": "heading", "char_start": r.start, "char_end": r.end}
                          for r in regions if r.kind == "heading" and r.end > r.start]
    sections = _merge_small_sections(
        text, _merge_page_sections(text, _sections(regions), p), p)
    kept: list[tuple[_ParentSpan, list[tuple[int, int]]]] = []
    for section in sections:
        body_words = sum(_words(r.text) for r in section.regions
                         if r.kind != "heading")
        if body_words < p["parent_stub_words"]:
            if section.regions:                 # stub / heading-only section: recorded, not lost
                layout.append({"kind": "dropped_stub",
                               "char_start": min(r.start for r in section.regions),
                               "char_end": max(r.end for r in section.regions)})
            continue
        for parent in _parent_spans(text, section, p):
            child_spans = _child_spans_for_parent(text, parent, p)
            if not child_spans:
                layout.append({"kind": "dropped_empty",
                               "char_start": parent.start, "char_end": parent.end})
                continue
            kept.append((parent, child_spans))

    children: list[dict] = []
    parent_children: list[tuple[_ParentSpan, list[int]]] = []
    for parent, spans in kept:
        idxs: list[int] = []
        for s, e in spans:
            chunk_text = text[s:e]
            if not chunk_text.strip():
                continue
            idxs.append(len(children))
            children.append({
                "doc_id": doc_id,
                "tier": "child",
                "text": chunk_text,
                "summary": summarize(chunk_text, max_sentences=2, max_chars=420),
                "char_start": s,
                "char_end": e,
                "heading_path": list(parent.heading_path),
                "token_count": _words(chunk_text),
                "chunk_contract_version": CHUNK_CONTRACT_V3,
                "provider": PROVIDER,
            })
        if idxs:
            parent_children.append((parent, idxs))

    for i, child in enumerate(children):
        child["chunk_index"] = i
        child["chunk_id"] = make_chunk_id(doc_id, i, child["text"])
        child["parent_id"] = None

    rows: list[dict] = list(children)
    base = len(children)
    for j, (parent, idxs) in enumerate(parent_children):
        p_start, p_end = _trim(text, parent.start, parent.end)
        parent_text = text[p_start:p_end]
        parent_row = {
            "chunk_id": make_chunk_id(doc_id, base + j, parent_text),
            "doc_id": doc_id,
            "parent_id": None,
            "chunk_index": base + j,
            "tier": "parent",
            "text": parent_text,
            "summary": summarize(parent_text, max_sentences=3, max_chars=600),
            "char_start": p_start,
            "char_end": p_end,
            "heading_path": list(parent.heading_path),
            "token_count": _words(parent_text),
            "chunk_contract_version": CHUNK_CONTRACT_V3,
            "provider": PROVIDER,
        }
        rows.append(parent_row)
        for k in idxs:
            children[k]["parent_id"] = parent_row["chunk_id"]

    _validate(rows, text)
    layout = sorted({(d["kind"], d["char_start"], d["char_end"]) for d in layout
                     if d["char_end"] > d["char_start"]})
    return rows, [{"kind": k, "char_start": a, "char_end": b} for k, a, b in layout]


def _validate(rows: list[dict], source: str) -> None:
    """Offset contract (§8): every row is a byte-exact substring;
    children are monotonic and non-overlapping; every child sits
    inside its parent's span."""
    parent_span = {r["chunk_id"]: (r["char_start"], r["char_end"])
                   for r in rows if r["tier"] == "parent"}
    last_end = -1
    for row in rows:
        s, e = row["char_start"], row["char_end"]
        assert 0 <= s < e <= len(source), "chunk offsets out of range"
        assert source[s:e] == row["text"], "offset roundtrip failed"
        if row["tier"] == "child":
            assert s >= last_end, "child overlap"
            last_end = e
            ps, pe = parent_span[row["parent_id"]]
            assert ps <= s and e <= pe, "child escapes parent span"
