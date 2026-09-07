"""DOCUMENT-PROFILE-V1 step 2 — the lean context builder (owner spec 2026-09-07).

Turns what intake already knows about a document — its name, its heading paths, its first and last
sections, a few sampled positions, its known terms — into the ~500-token DOCUMENT block the profile
prompt receives. Lean but contextually rich: every surface is kept, each trimmed to a deterministic
token allocation, never dropped wholesale. Pure: the caller loads rows; this module never touches a
store. The rendered block is hashed (`input_hash`) as the second link of the profile receipt chain
(content hash → INPUT HASH → raw response hash → compiled hash → projection hash).

Structure sources (owner): headings / TOC for books; section names for papers; H1–H3 and captions for
HTML; speaker / timestamp / chapter boundaries for transcripts; and when a document has no structure,
positions beginning → 25 % → midpoint → 75 % → ending.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from typing import Any

BUILDER_VERSION = "lean-context-v1"
DEFAULT_BUDGET_TOKENS = 500
#: deterministic allocation (tokens); structure may spill into whatever the other surfaces leave unused
DEFAULT_ALLOCATION = {"identity": 40, "structure": 150, "opening": 80, "ending": 60, "middle": 100, "terms": 20}

_EXT_RE = re.compile(r"\.(md|html?|pdf|epub|txt|docx?)$", re.IGNORECASE)
_SUFFIX_RE = re.compile(r"(?:\s*\d+)?(?:_[0-9a-f]{6,}|\s*\(\d+\))+$", re.IGNORECASE)
_MD_LINK_RE = re.compile(r"\[([^\]]+)\]\([^)]*\)")
_BRACKET_NOISE_RE = re.compile(r"\[[^\]]{0,80}\]|\{[^}]{0,40}\}")
_FILE_SEGMENT_RE = re.compile(r"^[\w./-]+\.x?html?(#.*)?$|^[\w-]+\.xhtml$", re.IGNORECASE)
_PAGE_SEGMENT_RE = re.compile(r"^pages?\s+\d+(\s*[–-]\s*\d+)?$", re.IGNORECASE)
#: heading segments that are furniture, not structure
_FURNITURE_RE = re.compile(
    r"^(table of contents|contents|copyright|copyright page|dedication|acknowledg(e)?ments?|about the author|"
    r"title page|half title|cover|colophon|index|bibliography|references|notes|also by|praise for)\b", re.IGNORECASE)
_WS_RE = re.compile(r"\s+")


def est_tokens(text: str) -> int:
    """Deterministic token estimate (≈ 4 characters per token); never 0 for non-empty text."""
    t = (text or "").strip()
    return 0 if not t else max(1, len(t) // 4)


def clean_title(source_name: str) -> str:
    name = str(source_name or "").strip()
    name = _EXT_RE.sub("", name)
    name = _SUFFIX_RE.sub("", name)
    name = _MD_LINK_RE.sub(r"\1", name)
    name = _BRACKET_NOISE_RE.sub(" ", name)
    name = re.sub(r"_{2,}", " ", name)
    return _WS_RE.sub(" ", name).strip(" #›-–—:|,.")[:120]


def _trim_tokens(text: str, tokens: int, *, tail: bool = False) -> str:
    """Trim to ~tokens at a word boundary; `tail` keeps the END of the text."""
    t = _WS_RE.sub(" ", (text or "")).strip()
    limit = max(0, tokens) * 4
    if len(t) <= limit:
        return t
    if tail:
        cut = t[-limit:]
        sp = cut.find(" ")
        return ("… " + cut[sp + 1:]) if sp > 0 else cut
    cut = t[:limit]
    sp = cut.rfind(" ")
    return (cut[:sp] if sp > 0 else cut) + " …"


def _clean_segment(seg: str) -> str:
    s = _MD_LINK_RE.sub(r"\1", str(seg or ""))
    s = _WS_RE.sub(" ", s).strip(" #›-–—:|")
    return s


def structure_lines(parents: Sequence[dict], *, max_lines: int = 400) -> list[str]:
    """Distinct heading paths in document order, furniture and file/page segments removed, rendered
    'A › B › C'. Repeated leading segments are kept (they disambiguate) — trimming happens later."""
    seen: set[str] = set()
    out: list[str] = []
    for p in sorted(parents, key=lambda r: (r.get("chunk_index") is None, r.get("chunk_index") or 0, r.get("char_start") or 0)):
        hp = p.get("heading_path") or []
        if isinstance(hp, str):
            try:
                hp = json.loads(hp)
            except Exception:  # noqa: BLE001
                hp = [hp]
        segs = []
        for s in hp:
            cs = _clean_segment(s)
            if not cs or _FILE_SEGMENT_RE.match(cs) or _PAGE_SEGMENT_RE.match(cs) or _FURNITURE_RE.match(cs):
                continue
            segs.append(cs)
        if not segs:
            continue
        line = " › ".join(segs)
        key = line.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(line)
        if len(out) >= max_lines:
            break
    return out


def _stride_select(lines: list[str], tokens: int) -> list[str]:
    """Fit the structure into `tokens` by an even stride over the WHOLE list (first and last kept), so the
    selection spans the document instead of stopping at chapter 3."""
    if not lines:
        return []
    total = sum(est_tokens(x) + 1 for x in lines)
    if total <= tokens:
        return list(lines)
    # how many lines fit at the average line cost
    avg = max(1.0, total / len(lines))
    keep = max(2, int(tokens // avg))
    if keep >= len(lines):
        return list(lines)
    idx = sorted({0, len(lines) - 1} | {round(i * (len(lines) - 1) / (keep - 1)) for i in range(keep)})
    picked = [lines[i] for i in idx]
    # safety trim only for lines that overrun their share (a normal heading path is left whole)
    cap = max(12, tokens // max(1, len(picked)))
    return [x if est_tokens(x) <= cap else _trim_tokens(x, cap) for x in picked]


def _body_parents(parents: Sequence[dict]) -> list[dict]:
    rows = [p for p in parents if str(p.get("text") or "").strip()]
    rows.sort(key=lambda r: (r.get("chunk_index") is None, r.get("chunk_index") or 0, r.get("char_start") or 0))
    body = [p for p in rows if not _is_furniture_parent(p)]
    return body or rows


_FURNITURE_WORD_RE = re.compile(
    r"\b(table of contents|contents|copyright|dedication|acknowledg(e)?ments?|about the author|title ?page|half ?title|"
    r"cover|colophon|bibliography|references|praise for)\b", re.IGNORECASE)


def _is_furniture_parent(p: dict) -> bool:
    role = str(p.get("region_role") or "")
    if role in ("toc", "front_matter", "index", "bibliography", "marketing", "legal", "back_matter"):
        return True
    hp = p.get("heading_path") or []
    if isinstance(hp, str):
        hp = [hp]
    # a furniture word anywhere in a segment — "xhtml/copyright.xhtml" is front matter too
    return any(_FURNITURE_WORD_RE.search(_clean_segment(s)) for s in hp)


@dataclass
class DocumentContext:
    title: str
    identity: str
    structure: list[str]
    opening: str
    ending: str
    middle: list[str]
    terms: list[str]
    budget_tokens: int
    allocation: dict[str, int]
    used_tokens: dict[str, int] = field(default_factory=dict)
    sources: dict[str, Any] = field(default_factory=dict)
    builder_version: str = BUILDER_VERSION

    @property
    def structure_block(self) -> str:
        return "\n".join(self.structure) if self.structure else ""

    @property
    def excerpts_block(self) -> str:
        parts = []
        if self.opening:
            parts.append(f"OPENING:\n{self.opening}")
        for i, m in enumerate(self.middle, 1):
            parts.append(f"SAMPLE {i}:\n{m}")
        if self.ending:
            parts.append(f"ENDING:\n{self.ending}")
        if self.terms:
            parts.append("KNOWN TERMS: " + ", ".join(self.terms))
        return "\n\n".join(parts)

    def to_dict(self) -> dict[str, Any]:
        return {"builder_version": self.builder_version, "title": self.title, "identity": self.identity,
                "structure": self.structure, "opening": self.opening, "ending": self.ending, "middle": self.middle,
                "terms": self.terms, "budget_tokens": self.budget_tokens, "allocation": self.allocation,
                "used_tokens": self.used_tokens, "sources": self.sources}

    def input_hash(self, content_hash: str = "") -> str:
        """Second link of the receipt chain: a pure function of the rendered block, the builder version,
        the allocation and the document's content hash."""
        payload = json.dumps({"builder": self.builder_version, "content_hash": content_hash, "identity": self.identity,
                              "structure": self.structure_block, "excerpts": self.excerpts_block,
                              "allocation": self.allocation}, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def build_context(document: dict, parents: Sequence[dict], *, terms: Iterable[str] = (),
                  budget_tokens: int = DEFAULT_BUDGET_TOKENS, allocation: dict[str, int] | None = None) -> DocumentContext:
    """`document`: {source_name, media_type, frontmatter?, doc_id?}; `parents`: the document's parent
    rows {heading_path, text, chunk_index, char_start, char_end, region_role?} in any order."""
    alloc = dict(DEFAULT_ALLOCATION)
    if allocation:
        alloc.update({k: int(v) for k, v in allocation.items()})
    scale = budget_tokens / max(1, sum(alloc.values()))
    if scale < 1.0:                                   # a smaller budget shrinks every surface proportionally
        alloc = {k: max(4, int(v * scale)) for k, v in alloc.items()}
    fm = document.get("frontmatter") or {}
    title = str(fm.get("title") or "").strip() or clean_title(document.get("source_name") or "")
    ident_bits = [title]
    for key in ("subtitle", "author", "authors", "organization", "publisher", "type", "document_type"):
        v = fm.get(key)
        if v:
            ident_bits.append(f"{key}: {v if isinstance(v, str) else ', '.join(map(str, v))}")
    mt = str(document.get("media_type") or "")
    if mt:
        ident_bits.append(f"format: {mt.split('/')[-1]}")
    identity = _trim_tokens(" · ".join(ident_bits), alloc["identity"])

    body = _body_parents(parents)
    structure = structure_lines(parents)
    used: dict[str, int] = {}
    opening = _trim_tokens(body[0]["text"], alloc["opening"]) if body else ""
    ending = _trim_tokens(body[-1]["text"], alloc["ending"], tail=True) if len(body) > 1 else ""
    used["opening"], used["ending"] = est_tokens(opening), est_tokens(ending)

    # middle samples: unstructured (≤ 2 headings) or long documents get positions 25 / 50 / 75 %
    middle: list[str] = []
    if body and (len(structure) <= 2 or len(body) >= 40):
        n = len(body)
        picks = sorted({int(n * 0.25), int(n * 0.5), int(n * 0.75)} - {0, n - 1})
        per = max(8, alloc["middle"] // max(1, len(picks)))
        middle = [_trim_tokens(body[i]["text"], per) for i in picks if 0 <= i < n]
    used["middle"] = sum(est_tokens(m) for m in middle)

    term_list = [str(t).strip() for t in terms if str(t).strip()]
    terms_kept: list[str] = []
    spent = 0
    for t in term_list:
        c = est_tokens(t) + 1
        if spent + c > alloc["terms"]:
            break
        terms_kept.append(t)
        spent += c
    used["terms"] = spent

    # structure takes its allocation plus whatever the excerpt surfaces left unused
    spare = max(0, (alloc["opening"] + alloc["ending"] + alloc["middle"] + alloc["terms"])
                - (used["opening"] + used["ending"] + used["middle"] + used["terms"]))
    struct_budget = alloc["structure"] + spare
    structure_sel = _stride_select(structure, struct_budget)
    used["structure"] = sum(est_tokens(x) + 1 for x in structure_sel)
    used["identity"] = est_tokens(identity)

    return DocumentContext(
        title=title, identity=identity, structure=structure_sel, opening=opening, ending=ending, middle=middle,
        terms=terms_kept, budget_tokens=budget_tokens, allocation=alloc, used_tokens=used,
        sources={"parents": len(parents), "body_parents": len(body), "heading_paths": len(structure),
                 "structure_mode": ("headings" if len(structure) > 2 else "positions"),
                 "media_type": mt, "title_source": ("frontmatter" if fm.get("title") else "source_name")},
    )
