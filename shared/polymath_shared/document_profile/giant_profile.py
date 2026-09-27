"""FACET-RETRIEVAL-V1 slice F4 — profiles that match giant documents (plan §3.4).

The measured problem (register 11.545, receipt `q_e09925df009649c6be872299`): `handbook.html` in
`cinema` has 802 parents; its document profile was built from a 500-token fingerprint whose
`coverage` held FIVE samples of the 802 sections and whose `framing` was the front matter, so the
profile names CPCS / YAML / JSON and nothing about motion, camera or prompting. The profile lanes
(dualread, the scout's probes, see-also fan-out, bridge atoms) therefore never route to it.

This module is the DETERMINISTIC policy for the two fixes (pure: no I/O, no model, no store):

  * ``section_groups`` — a document with more than ``GIANT_PARENT_THRESHOLD`` parents is cut into
    SECTIONS, one per top-level heading (a heading group larger than ``SECTION_SPLIT_PARENTS`` is
    split at the next heading level; groups smaller than ``MIN_SECTION_PARENTS`` fold into their
    predecessor; the count is capped at ``MAX_SECTION_PROFILES`` by merging neighbours). Every
    eligible parent belongs to exactly one section. A section carries the durable ``parent_ids``
    of its parents, so a section profile point can name the parents it stands for.
  * ``build_section_fingerprint`` — the LLM input for ONE section: the vNext ``DocumentFingerprint``
    built from that section's OWN parents (sampled at even strides when long), titled
    "<document> › <section>".
  * ``build_giant_fingerprint`` — the DOCUMENT-level input for a giant: a STRATIFIED sample across
    ALL sections, never the first pages — pass 1 takes the opening of every section (every section
    is represented before any second sample is taken), later passes add salient sentences from the
    middle, the end and the quartiles of each section, round-robin, until the budget is spent. The
    structure block lists every section title; the vocabulary is the document-wide term ranking.

The worker (``workers/workers/doc_profile_worker.py``) turns these inputs into LLM calls and stores
one profile point per section beside the document point (``projection.project_profile(section=…)``,
``scope: section``) and one atom row / point per section atom (``profile_atom.source_tag("section",
…)``), so the SAME lanes that read document profiles read them. The audit scorer lives in
``profile_coverage.py``.
"""
from __future__ import annotations

import hashlib
import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from polymath_shared import document_region
from polymath_shared.document_profile import context as _ctx
from polymath_shared.document_profile import fingerprint as _fp
from polymath_shared.document_profile import parent_skeleton as _ps

GIANT_PROFILE_VERSION = "giant-profile-v1"
GIANT_FINGERPRINT_BUILDER_VERSION = "fingerprint-giant-v1"

#: A document with MORE parents than this is a giant (plan §3.4: "more than 300 sections").
GIANT_PARENT_THRESHOLD = 300
#: A top-level heading group larger than this is split at the next heading level.
SECTION_SPLIT_PARENTS = 150
#: Groups smaller than this fold into their predecessor (a 1-parent title page is not a section).
MIN_SECTION_PARENTS = 3
#: Hard cap on section profiles per document (neighbours merge beyond it).
MAX_SECTION_PROFILES = 72
#: Deepest heading level a split may descend to (path[0] = top level).
MAX_SPLIT_DEPTH = 3
#: Input budgets. The section budget sits inside the fingerprint's [500, 2000] clamp; the giant
#: document budget is the fingerprint ceiling (one profile call stays under a Groq lane's 8K TPM:
#: ~2,000 input + ~1,500 prompt/output tokens).
SECTION_BUDGET_TOKENS = 1000
GIANT_DOCUMENT_BUDGET_TOKENS = 2000
#: Round-robin passes of the stratified sampler and the per-sample ceiling (tokens).
STRATIFIED_MAX_PASSES = 5
STRATIFIED_SAMPLE_TOKENS = 45
STRATIFIED_MIN_SAMPLE_TOKENS = 12
#: Fractions for the giant document input (structure carries EVERY section title; coverage takes
#: whatever the other surfaces leave, exactly like ``fingerprint.build_fingerprint``).
GIANT_ALLOCATION = {
    "identity": 0.06,
    "structure": 0.22,
    "framing": 0.06,
    "coverage": 0.46,
    "synthesis": 0.06,
    "vocabulary": 0.14,
}

SCOPE_DOCUMENT = "document"
SCOPE_SECTION = "section"

_EMPHASIS_RE = re.compile(r"[*_`]+")
_FILE_LIKE_RE = re.compile(r"\.(epub|pdf|docx?|x?html?|md|txt)$", re.IGNORECASE)
_WS_RE = re.compile(r"\s+")


@dataclass(frozen=True)
class SectionGroup:
    """One section of a giant document: a contiguous-by-heading set of parents."""

    ordinal: int                       # 1-based position in document order
    key: str                           # stable id from the heading key path (16 hex chars)
    title: str                         # human title ("04. Motion core" / "A › B" / "A + B")
    heading_path: tuple[str, ...]      # the heading key path the group was cut at
    parents: tuple[dict, ...]          # the parent rows, document order
    parent_ids: tuple[str, ...]        # durable ids (chunk_id) of those parents, same order
    chars: int                         # total normalized text length

    @property
    def parent_count(self) -> int:
        return len(self.parents)

    def content_hash(self) -> str:
        """The section's own content identity — the projection key of its point moves with it."""
        h = hashlib.sha256()
        for p in self.parents:
            h.update(_ps.normalize_whitespace(str(p.get("text") or "")).encode("utf-8"))
            h.update(b"\x1e")
        return h.hexdigest()


def is_giant(parent_count: int, *, threshold: int = GIANT_PARENT_THRESHOLD) -> bool:
    """More parents than the threshold → section profiles (300 itself is not a giant)."""
    return int(parent_count or 0) > int(threshold)


# ── heading keys ────────────────────────────────────────────────────────────────

def clean_heading_segment(segment: Any) -> str:
    """A heading segment as a grouping key: markdown links / emphasis stripped, whitespace
    collapsed; '' for file, page and furniture segments (the same furniture rules as the
    fingerprint's structure lines)."""
    s = _ctx._clean_segment(segment)
    s = _EMPHASIS_RE.sub("", s)
    s = _WS_RE.sub(" ", s).strip(" #›-–—:|[]")
    if not s:
        return ""
    if _ctx._FILE_SEGMENT_RE.match(s) or _ctx._PAGE_SEGMENT_RE.match(s) or _ctx._FURNITURE_RE.match(s):
        return ""
    if _FILE_LIKE_RE.search(s) and " " not in s.strip():
        return ""
    return s


def heading_key_path(heading_path: Any) -> tuple[str, ...]:
    """The cleaned heading path; empty segments are dropped, so the first element is the first
    REAL heading level. A parent with no usable heading yields ()."""
    hp = heading_path
    if isinstance(hp, str):
        try:
            import json
            hp = json.loads(hp)
        except Exception:  # noqa: BLE001 — a bare string heading
            hp = [hp]
    out: list[str] = []
    for seg in list(hp or []):
        c = clean_heading_segment(seg)
        if c:
            out.append(c)
    return tuple(out)


def section_key(path: Sequence[str]) -> str:
    """Stable 16-hex id of a heading key path (lower-cased) — the same headings give the same key
    across rebuilds, so a rebuilt section REPLACES its point instead of duplicating it."""
    joined = "›".join(str(s).strip().lower() for s in path)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()[:16]


def parent_id_of(parent: dict, position: int) -> str:
    """The durable parent id (``chunk_id`` / ``parent_id``); a positional fallback only for rows
    without one (synthetic tests) — production rows always carry ``chunk_id``."""
    for k in ("chunk_id", "parent_id"):
        v = parent.get(k)
        if v is not None and str(v).strip():
            return str(v)
    idx = parent.get("chunk_index")
    return f"idx:{idx if isinstance(idx, int) else position}"


# ── grouping ────────────────────────────────────────────────────────────────────

def _eligible_parents(parents: Sequence[dict]) -> list[tuple[int, dict, str]]:
    """(position, parent, parent_id) for non-noisy, non-empty parents in document order."""
    rows: list[tuple[int, int, dict]] = []
    for position, p in enumerate(parents):
        role = str(p.get("region_role") or document_region.ROLE_UNKNOWN)
        if document_region.is_noisy(role):
            continue
        if not _ps.normalize_whitespace(str(p.get("text") or "")):
            continue
        rows.append((_ps._source_position(p, position), position, p))
    rows.sort(key=lambda r: (r[0], r[1]))
    return [(pos, p, parent_id_of(p, pos)) for (_src, pos, p) in rows]


def _group_by_level(rows: list[tuple[tuple[str, ...], int, dict, str]], level: int,
                    prefix: tuple[str, ...]) -> list[tuple[tuple[str, ...], list[tuple[tuple[str, ...], int, dict, str]]]]:
    """Group rows by their heading key at `level` (rows shorter than the level attach to the
    running group — a section's own introduction stays with the section that follows it, or
    with the previous one when there is nothing after). Order = first appearance."""
    groups: dict[tuple[str, ...], list] = {}
    order: list[tuple[str, ...]] = []
    pending: list = []                       # rows without a key at this level, before any group
    current: tuple[str, ...] | None = None
    for row in rows:
        path = row[0]
        if len(path) > level:
            key = prefix + (path[level],)
            if key not in groups:
                groups[key] = []
                order.append(key)
                if pending:
                    groups[key].extend(pending)
                    pending = []
            groups[key].append(row)
            current = key
        elif current is not None:
            groups[current].append(row)
        else:
            pending.append(row)
    if pending:
        if order:
            groups[order[0]] = pending + groups[order[0]]
        else:
            key = prefix + ("(untitled)",)
            groups[key] = pending
            order.append(key)
    return [(k, groups[k]) for k in order]


def _positional(key: tuple[str, ...], rows: list, split_at: int) -> list[tuple[tuple[str, ...], list]]:
    """A group with no deeper headings and more than `split_at` parents is cut into equal contiguous parts
    (a flat book, a transcript): "<title> (part i of n)". Positional keys are not stable across a re-chunk —
    a re-cut document purges its orphan section points."""
    rows = sorted(rows, key=lambda r: r[1])
    n = -(-len(rows) // split_at)
    size = -(-len(rows) // n)
    out: list[tuple[tuple[str, ...], list]] = []
    for i in range(n):
        part = rows[i * size:(i + 1) * size]
        if part:
            out.append((key + (f"part {i + 1} of {n}",), part))
    return out


def _split(key: tuple[str, ...], rows: list, *, level: int, split_at: int, max_depth: int) -> list[tuple[tuple[str, ...], list]]:
    """Split a too-large group at the next heading level (recursively, bounded); a group the headings cannot
    split falls back to positional parts."""
    if len(rows) <= split_at:
        return [(key, rows)]
    subs = _group_by_level(rows, level, key) if level < max_depth else []
    if len(subs) < 2:
        return _positional(key, rows, split_at)
    out: list[tuple[tuple[str, ...], list]] = []
    for sk, srows in subs:
        out.extend(_split(sk, srows, level=level + 1, split_at=split_at, max_depth=max_depth))
    return out


def _title(path: tuple[str, ...]) -> str:
    return " › ".join(path)


def _make_group(ordinal: int, path: tuple[str, ...], title: str, rows: list) -> SectionGroup:
    rows = sorted(rows, key=lambda r: r[1])
    parents = tuple(r[2] for r in rows)
    return SectionGroup(
        ordinal=ordinal, key=section_key(path), title=title, heading_path=path, parents=parents,
        parent_ids=tuple(r[3] for r in rows),
        chars=sum(len(_ps.normalize_whitespace(str(p.get("text") or ""))) for p in parents),
    )


def section_groups(parents: Sequence[dict], *, threshold: int = GIANT_PARENT_THRESHOLD,
                   split_at: int = SECTION_SPLIT_PARENTS, min_parents: int = MIN_SECTION_PARENTS,
                   max_profiles: int = MAX_SECTION_PROFILES) -> list[SectionGroup]:
    """The section plan of a document: [] for a document that is not a giant (its parent count is at
    or under `threshold`), else one SectionGroup per top-level heading after the split / fold /
    cap rules (a heading group over `split_at` parents splits at the next heading level, or into
    positional parts when it has no deeper headings — so a flat book still gets sections).
    Deterministic; every eligible parent lands in exactly one group."""
    if not is_giant(len(parents), threshold=threshold):
        return []
    elig = _eligible_parents(parents)
    if not elig:
        return []
    rows = [(heading_key_path(p.get("heading_path")), pos, p, pid) for (pos, p, pid) in elig]
    # 1. one group per top-level heading (first appearance order); a flat document is one group, cut positionally below
    groups = _group_by_level(rows, 0, ())
    # 2. split the big ones at the next level
    split: list[tuple[tuple[str, ...], list]] = []
    for key, grows in groups:
        split.extend(_split(key, grows, level=1, split_at=split_at, max_depth=MAX_SPLIT_DEPTH))
    # 3. fold tiny groups into their predecessor (the leading tiny ones into the first real group)
    folded: list[tuple[tuple[str, ...], str, list]] = []
    lead: list = []
    for key, grows in split:
        if len(grows) < min_parents:
            if folded:
                folded[-1][2].extend(grows)
            else:
                lead.extend(grows)
            continue
        if lead:
            grows = lead + grows
            lead = []
        folded.append((key, _title(key), grows))
    if lead:
        if folded:
            folded[0][2].extend(lead)
        else:
            key = split[0][0] if split else ("(untitled)",)
            folded.append((key, _title(key), lead))
    # 4. cap: merge the smallest group into its smaller neighbour until under the cap
    while len(folded) > max_profiles:
        i = min(range(len(folded)), key=lambda j: (len(folded[j][2]), j))
        left = i - 1 if i > 0 else None
        right = i + 1 if i + 1 < len(folded) else None
        if left is None:
            j = right
        elif right is None:
            j = left
        else:
            j = left if len(folded[left][2]) <= len(folded[right][2]) else right
        a, b = (folded[j], folded[i]) if j < i else (folded[i], folded[j])
        merged = (a[0] + b[0], f"{a[1]} + {b[1]}", a[2] + b[2])
        lo, hi = min(i, j), max(i, j)
        folded[lo:hi + 1] = [merged]
    return [_make_group(n, key, title, grows) for n, (key, title, grows) in enumerate(folded, start=1)]


def plan_sections(parents: Sequence[dict], **kw) -> dict[str, Any]:
    """The plan as a receipt-able dict: giant?, threshold, and one row per section."""
    threshold = int(kw.get("threshold", GIANT_PARENT_THRESHOLD))
    groups = section_groups(parents, **kw)
    return {
        "version": GIANT_PROFILE_VERSION,
        "threshold": threshold,
        "parents": len(parents),
        "giant": is_giant(len(parents), threshold=threshold),
        "sections": [
            {"ordinal": g.ordinal, "key": g.key, "title": g.title, "heading_path": list(g.heading_path),
             "parents": g.parent_count, "chars": g.chars}
            for g in groups
        ],
    }


# ── inputs ──────────────────────────────────────────────────────────────────────

def document_title(document: dict) -> str:
    fm = document.get("frontmatter") or {}
    return str(fm.get("title") or "").strip() or _ctx.clean_title(document.get("source_name") or "")


def build_section_fingerprint(document: dict, group: SectionGroup, *, ordinal: int | None = None,
                              total: int | None = None,
                              budget_tokens: int = SECTION_BUDGET_TOKENS) -> _fp.DocumentFingerprint:
    """The LLM input for ONE section: the vNext fingerprint over the section's own parents (its
    heading stride, its even-stride salient coverage, its vocabulary), titled
    "<document> › <section>" and identified as "section i of n of <document>"."""
    doc_title = document_title(document)
    n = total if total is not None else ordinal
    ident = f"section {ordinal or group.ordinal} of {n or '?'} of “{doc_title}”"
    doc_like = {
        "source_name": document.get("source_name"),
        "media_type": document.get("media_type"),
        "frontmatter": {"title": f"{doc_title} › {group.title}", "subtitle": ident},
        "doc_id": document.get("doc_id"),
    }
    fp = _fp.build_fingerprint(doc_like, list(group.parents), budget_tokens=budget_tokens)
    fp.sources.update({"scope": SCOPE_SECTION, "section_key": group.key, "section_title": group.title,
                       "section_parents": group.parent_count, "giant_profile": GIANT_PROFILE_VERSION})
    return fp


def _group_signals(group: SectionGroup) -> list[dict[str, Any]]:
    """The section's per-parent signals (the fingerprint's own helpers); bare-number identifiers ("001",
    "016") are dropped so a giant's vocabulary budget goes to terms, not to a source registry's numbering."""
    body = _fp._eligible_body(list(group.parents))
    out = _fp._per_parent_signals(body) if body else []
    for sig in out:
        sig["identifiers"] = tuple(x for x in sig["identifiers"] if not str(x).isdigit())
    return out


def stratified_samples(groups: Sequence[SectionGroup], signals: Sequence[Sequence[dict[str, Any]]],
                       budget: int, *, max_passes: int = STRATIFIED_MAX_PASSES,
                       sample_tokens: int = STRATIFIED_SAMPLE_TOKENS) -> list[tuple[int, str]]:
    """Round-robin excerpts across ALL sections, (group index, labelled excerpt) in sampling order.
    Each excerpt is labelled "[<section ordinal>]"; the structure block maps ordinals to titles.

    Pass 1 = the opening (lead) of every section's first parent, trimmed so that every section gets
    a sample before any second one is taken (the per-sample ceiling shrinks with the section count,
    never under ``STRATIFIED_MIN_SAMPLE_TOKENS``). Pass 2 = the salient sentence of the middle
    parent; pass 3 = of the last parent; passes 4-5 = the quartiles. Stops when the budget is spent."""
    n = len(groups)
    if n == 0 or budget <= 0:
        return []
    # a sample is labelled with the section ORDINAL (the structure block maps it to the title), so
    # the label costs ~3 tokens and a long title can never eat a section's only sample
    label_cost = _ctx.est_tokens(f"[{n}] ") + 3
    per_first = max(STRATIFIED_MIN_SAMPLE_TOKENS, min(sample_tokens, budget // n - label_cost))
    out: list[tuple[int, str]] = []
    spent = 0

    def pick(sig: Sequence[dict[str, Any]], pass_no: int) -> str:
        if not sig:
            return ""
        m = len(sig)
        if pass_no == 0:
            return sig[0]["lead"] or sig[0]["salient"]
        idx = {1: m // 2, 2: m - 1, 3: m // 4, 4: (3 * m) // 4}[pass_no]
        return sig[idx]["salient"] or sig[idx]["lead"]

    for pass_no in range(min(max_passes, 5)):
        cap = per_first if pass_no == 0 else sample_tokens
        took = False
        for gi, g in enumerate(groups):
            exc = _ctx._trim_tokens(pick(signals[gi], pass_no), cap)
            if not exc:
                continue
            label = f"[{g.ordinal}] {exc}"
            cost = _ctx.est_tokens(label) + 3
            if out and spent + cost > budget:
                return out
            out.append((gi, label))
            spent += cost
            took = True
        if not took:
            break
    return out


def build_giant_fingerprint(document: dict, parents: Sequence[dict], groups: Sequence[SectionGroup], *,
                            budget_tokens: int = GIANT_DOCUMENT_BUDGET_TOKENS) -> _fp.DocumentFingerprint:
    """The DOCUMENT-level input for a giant: identity, EVERY section title as structure, the
    stratified sample as coverage (every section represented), the first content section's opening
    as framing, the last section's closing as synthesis, the document-wide vocabulary. Rendered by
    the same ``DocumentFingerprint`` the vNext prompt consumes; ``builder_version`` names this
    builder so the receipt chain shows which input made the profile."""
    budget = max(_fp.PROFILE_CONTEXT_BUDGET_MIN, min(int(budget_tokens), _fp.PROFILE_CONTEXT_BUDGET_MAX))
    total_frac = sum(GIANT_ALLOCATION.values()) or 1.0
    sub = {k: max(4, round(budget * v / total_frac)) for k, v in GIANT_ALLOCATION.items()}
    groups = list(groups)
    title = document_title(document)
    mt = str(document.get("media_type") or "")
    ident_bits = [title]
    fm = document.get("frontmatter") or {}
    for key in ("subtitle", "author", "authors", "organization", "publisher", "type", "document_type"):
        v = fm.get(key)
        if v:
            ident_bits.append(f"{key}: {v if isinstance(v, str) else ', '.join(map(str, v))}")
    ident_bits.append(f"{len(groups)} sections, {len(parents)} parts")
    if mt:
        ident_bits.append(f"format: {mt.split('/')[-1]}")
    identity = _ctx._trim_tokens(" · ".join(ident_bits), sub["identity"])

    signals = [_group_signals(g) for g in groups]
    structure_all = [f"{g.ordinal}. {g.title} ({g.parent_count})" for g in groups]
    structure = _ctx._stride_select(structure_all, sub["structure"])

    framing = ""
    for sig in signals:
        if sig:
            framing = _ctx._trim_tokens(sig[0]["lead"] or sig[0]["salient"], sub["framing"])
            break
    synthesis = ""
    for sig in reversed(signals):
        if sig:
            synthesis = _ctx._trim_tokens(sig[-1]["salient"] or sig[-1]["lead"], sub["synthesis"], tail=True)
            break
    flat = [p for sig in signals for p in sig]
    vocabulary = _fp._select_vocabulary(flat, (), sub["vocabulary"])

    used_others = (_ctx.est_tokens(identity) + sum(_ctx.est_tokens(x) + 1 for x in structure)
                   + _ctx.est_tokens(framing) + _ctx.est_tokens(synthesis)
                   + sum(_ctx.est_tokens(t) + 1 for t in vocabulary))
    coverage_budget = max(0, budget - used_others)
    samples = stratified_samples(groups, signals, coverage_budget)
    coverage = [text for _gi, text in samples]
    by_section: dict[str, int] = {}
    for gi, _text in samples:
        by_section[groups[gi].key] = by_section.get(groups[gi].key, 0) + 1

    used = {
        "identity": _ctx.est_tokens(identity),
        "structure": sum(_ctx.est_tokens(x) + 1 for x in structure),
        "framing": _ctx.est_tokens(framing),
        "coverage": sum(_ctx.est_tokens(x) + 3 for x in coverage),
        "synthesis": _ctx.est_tokens(synthesis),
        "vocabulary": sum(_ctx.est_tokens(t) + 1 for t in vocabulary),
    }
    return _fp.DocumentFingerprint(
        title=title, identity=identity, structure=structure, framing=framing, coverage=coverage,
        synthesis=synthesis, vocabulary=vocabulary, budget_tokens=budget, allocation=sub, used_tokens=used,
        sources={
            "parents": len(parents), "body_parents": sum(len(s) for s in signals),
            "heading_paths": len(structure_all), "structure_mode": "sections",
            "coverage_samples": len(coverage), "media_type": mt,
            "title_source": ("frontmatter" if fm.get("title") else "source_name"),
            "scope": SCOPE_DOCUMENT, "giant_profile": GIANT_PROFILE_VERSION, "sections": len(groups),
            "sections_sampled": len(by_section), "coverage_by_section": by_section,
        },
        builder_version=GIANT_FINGERPRINT_BUILDER_VERSION,
    )


def base_prompt_blocks(fp: _fp.DocumentFingerprint) -> tuple[str, str]:
    """(structure, excerpts) for the base ``doc-profile-v3.2`` prompt (``prompt.build_user_prompt``),
    rendered from a fingerprint the same way the lean context renders its blocks — so the base
    path and the vNext path see the SAME sampled evidence."""
    parts: list[str] = []
    if fp.identity:
        parts.append(f"IDENTITY:\n{fp.identity}")
    if fp.framing:
        parts.append(f"OPENING:\n{fp.framing}")
    for i, c in enumerate(fp.coverage, 1):
        parts.append(f"SAMPLE {i}:\n{c}")
    if fp.synthesis:
        parts.append(f"ENDING:\n{fp.synthesis}")
    if fp.vocabulary:
        parts.append("KNOWN TERMS: " + ", ".join(fp.vocabulary))
    return fp.structure_block, "\n\n".join(parts)
