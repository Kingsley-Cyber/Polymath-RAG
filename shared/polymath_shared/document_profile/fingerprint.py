"""DOCUMENT-SEMANTIC-INDEX-V1 slice S5 — the vNext global DocumentFingerprint.

Plan of record: docs/wiki/plans/DOCUMENT-SEMANTIC-INDEX-V1-PLAN.md §5-§6, §18, §31,
slice S5. Migration authority: docs/wiki/plans/RETRIEVAL-MIGRATION-DEPENDENCY-V1.md
§18 (global profile / profile-atom integration), §S7 (global profile vNext
independence), GAP-04 (`doc_profile` upstream legacy-summary input).

The fingerprint is the DETERMINISTIC input the global-profile LLM sees — the vNext
successor to ``context.py``'s ``lean-context-v1`` ~500-token block. It is:

  * ADAPTIVE 500-2,000 tokens — 2,000 is a CEILING, never padding; a small document
    yields a small fingerprint (plan §18);
  * a FULL-STRUCTURE scan with NO first-400 bias — ``coverage`` (the largest surface)
    samples salient source sentences at even strides across the WHOLE document, so
    late-document content is represented and the profile is not dominated by the
    document's opening;
  * SELF-SUFFICIENT — the ``vocabulary`` surface derives salient terms
    deterministically from the source (TF x IDF across parents + exact identifiers),
    so the vNext profile no longer NEEDS the legacy
    ``document_summaries.major_concepts`` input (GAP-04). Dropping that reader in
    ``workers/workers/doc_profile_worker.py`` is the worker refactor (repo S8), not
    this slice — this slice makes the drop safe.

Six surfaces, ``coverage`` largest: identity, structure, framing, coverage,
synthesis, vocabulary.

Pure deterministic policy (shared/): no I/O, no model, no network. It REUSES the
existing deterministic helpers rather than inventing parallel infrastructure —
``context.py`` (token estimate / title / trim / heading stride) and
``parent_skeleton.py`` (whitespace / identifiers / DF / key terms / salient & lead
excerpts), and the single furniture authority ``document_region.is_noisy``. It does
NOT require durable parent identity (``chunk_id``): the fingerprint is a
document-scale routing input and keys nothing on a parent, so it works on the current
worker's parent rows too (durable identity is the per-parent MAP's concern, repo S9).

This module builds the INPUT block only. The LLM OUTPUT contract — the new
research-index tags LATENT-PATTERN / ANCHOR / RECALLQ / TENSION / BRIDGE / INVERSION /
BOUNDARY in ``prompt.py`` + ``compiler.py`` — is a separate, owner-gated change (the
500/1000/1500/2000 quality canary spends provider quota). The tag vocabulary is
exported here as the single version-pinned source of truth so that change consumes
it rather than re-declaring it.
"""
from __future__ import annotations

import hashlib
import json
from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from typing import Any

from polymath_shared import document_region
from polymath_shared.document_profile import context as _ctx
from polymath_shared.document_profile import parent_skeleton as _ps

est_tokens = _ctx.est_tokens

#: Bump when the fingerprint algorithm changes (plan §32 tracks builder versions
#: independently so effects do not couple into unrelated rebuilds).
FINGERPRINT_BUILDER_VERSION = "fingerprint-v1"

#: Adaptive budget bounds (plan §18). 2,000 is a ceiling, never required padding.
PROFILE_CONTEXT_BUDGET_MIN = 500
PROFILE_CONTEXT_BUDGET_MAX = 2000
#: S5 canary-selected (docs/wiki/experiments/document-profile-vnext-canary-2026-09-07):
#: on a 5-doc cinema cohort, field + research-tag coverage saturates at 500 and the
#: no-first-400-bias gate is already met (late-structure ~0.82 — the coverage surface
#: spans the whole document at every budget), while 1000-2000 nearly double the input
#: cost for no quality gain (slight regression at 2000). The plateau is the floor.
DEFAULT_BUDGET_TOKENS = 500

#: Fractional allocation across the six surfaces. Fractions (not absolute tokens)
#: so the same shape scales 500 -> 2,000. ``coverage`` is the largest share — the
#: full-document scan is the point of the fingerprint (plan §18). ``coverage`` is
#: also computed LAST and absorbs whatever the other five leave unused, so the total
#: never exceeds the budget and a content-poor document naturally underfills it.
DEFAULT_ALLOCATION = {
    "identity": 0.08,
    "structure": 0.20,
    "framing": 0.12,
    "coverage": 0.36,   # largest
    "synthesis": 0.12,
    "vocabulary": 0.12,
}

#: Deterministic per-coverage-sample token estimate (a salient excerpt is bounded to
#: SALIENT_EXCERPT_MAX_WORDS=30 words ~= 45 tokens, plus a "COVERAGE N:" label).
#: Deliberately a touch high so the even-stride sample count stays within budget.
COVERAGE_EXCERPT_TOKENS = 56

# --- vNext profile OUTPUT contract vocabulary (single source of truth) ----------
# The current live profile (doc-profile-v3.2) emits ONE/SUMMARY/TOPIC/TERM/Q/SEARCH/
# THEORY/CONCEPT/SEEALSO. The vNext research-index adds the surfaces below. Consumed
# by the future prompt/compiler change (owner-gated canary) — declared here so it is
# version-pinned and testable now, not re-invented at wiring time.
SOURCE_ANCHORED_FIELDS: tuple[str, ...] = ("ONE", "SUMMARY", "TOPIC", "TERM", "Q")
#: NEW routing-inferred surfaces this phase adds. Kept explicit and hyphenated: the
#: compiler aliases PATTERN/PATTERNS -> CONCEPT, so LATENT-PATTERN is a DISTINCT label
#: (plan §18 naming note).
RESEARCH_INDEX_TAGS: tuple[str, ...] = (
    "LATENT-PATTERN", "ANCHOR", "RECALLQ", "TENSION", "BRIDGE", "INVERSION", "BOUNDARY",
)
#: Routing-inferred fields are hypotheses for the retriever, NEVER factual citations
#: (plan §18). = the pre-existing routing labels + the new research-index tags.
ROUTING_INFERRED_FIELDS: tuple[str, ...] = (
    "SEARCH", "THEORY", "CONCEPT", "SEEALSO",
) + RESEARCH_INDEX_TAGS


def _even_indices(n: int, k: int) -> list[int]:
    """k indices evenly spanning [0, n-1], first and last ALWAYS included (the
    no-first-400-bias guarantee — the full document is represented). Same formula as
    ``context._stride_select``'s index selection."""
    if n <= 0:
        return []
    if k >= n:
        return list(range(n))
    if k <= 1:
        return [0]
    return sorted({0, n - 1} | {round(i * (n - 1) / (k - 1)) for i in range(k)})


def _eligible_body(parents: Sequence[dict]) -> list[tuple[int, tuple[str, ...], str, str]]:
    """Non-noisy, non-empty parents in source order as ``(src_pos, heading_path,
    role, normalized_text)``. Furniture eligibility defers to the single region-role
    authority ``document_region.is_noisy`` (no competing furniture policy). Ordering
    is by source position then text, so it is independent of the caller's order and
    does not require a durable parent id."""
    rows: list[tuple[int, tuple[str, ...], str, str]] = []
    for position, p in enumerate(parents):
        role = str(p.get("region_role") or document_region.ROLE_UNKNOWN)
        text = _ps.normalize_whitespace(str(p.get("text") or ""))
        if document_region.is_noisy(role) or not text:
            continue
        hp = _ps._normalize_heading(p.get("heading_path"))
        src = _ps._source_position(p, position)
        rows.append((src, hp, role, text))
    rows.sort(key=lambda r: (r[0], r[3]))
    return rows


def _per_parent_signals(
    body: Sequence[tuple[int, tuple[str, ...], str, str]],
) -> list[dict[str, Any]]:
    """Per eligible parent: salient excerpt, opening (lead) excerpt, key terms and
    exact identifiers — reusing the parent-skeleton scoring so the fingerprint sees
    the SAME sentences and terms the per-parent MAP will (one deterministic pass of
    the same helpers, document-scale)."""
    token_lists = [_ps._word_tokens(text) for (_s, _hp, _r, text) in body]
    df = _ps.document_frequency([set(t) for t in token_lists])
    n_docs = len(body)
    out: list[dict[str, Any]] = []
    for i, (_src, hp, _role, text) in enumerate(body):
        htok = _ps._heading_tokens(hp)
        idents = tuple(_ps.extract_identifiers(text))
        idtok = {x.lower() for x in idents}
        kts = tuple(_ps.select_key_terms(token_lists[i], htok, idtok, df, n_docs))
        out.append(
            {
                "heading_path": hp,
                "salient": _ps.select_salient_excerpt(text, htok, kts, idents),
                "lead": _ps.select_lead_excerpt(text),
                "key_terms": kts,
                "identifiers": idents,
            }
        )
    return out


def _select_coverage(per: Sequence[dict[str, Any]], budget: int) -> list[str]:
    """Even-stride salient excerpts across the WHOLE document (the largest surface,
    no first-400 bias). The even index set always spans first..last."""
    if not per or budget <= 0:
        return []
    n = len(per)
    k = max(1, min(n, budget // COVERAGE_EXCERPT_TOKENS))
    out: list[str] = []
    spent = 0
    for i in _even_indices(n, k):
        exc = per[i]["salient"]
        if not exc:
            continue
        cost = est_tokens(exc) + 3   # "COVERAGE N:" label overhead
        if out and spent + cost > budget:
            break
        out.append(exc)
        spent += cost
    return out


def _select_vocabulary(
    per: Sequence[dict[str, Any]], extra_terms: Iterable[str], budget: int
) -> list[str]:
    """Document-level vocabulary derived from the source (GAP-04 — no
    ``major_concepts`` dependency): exact identifiers (capped to half the budget so
    they never crowd out concepts) then key terms ranked by cross-parent frequency,
    then any optional caller ``extra_terms`` (deduped, never required)."""
    if budget <= 0:
        return []
    term_freq: Counter = Counter()
    for p in per:
        term_freq.update(p["key_terms"])
    idents: list[str] = []
    for p in per:
        for x in p["identifiers"]:
            if x not in idents:
                idents.append(x)
    ranked_terms = sorted(term_freq, key=lambda t: (-term_freq[t], t))
    seen = {t.lower() for t in ranked_terms} | {i.lower() for i in idents}
    extras: list[str] = []
    for t in extra_terms:
        s = str(t).strip()
        if s and s.lower() not in seen:
            extras.append(s)
            seen.add(s.lower())

    out: list[str] = []
    spent = 0
    ident_budget = budget // 2
    for x in idents:
        cost = est_tokens(x) + 1
        if out and spent + cost > ident_budget:
            break
        out.append(x)
        spent += cost
    for t in ranked_terms + extras:
        cost = est_tokens(t) + 1
        if spent + cost > budget:
            break
        out.append(t)
        spent += cost
    return out


@dataclass
class DocumentFingerprint:
    """The vNext deterministic global-profile INPUT. ``coverage`` is the largest
    surface (full-document span); ``vocabulary`` is source-derived (no legacy summary
    input). Every field is defensible from source material."""

    title: str
    identity: str
    structure: list[str]
    framing: str
    coverage: list[str]
    synthesis: str
    vocabulary: list[str]
    budget_tokens: int
    allocation: dict[str, int]
    used_tokens: dict[str, int] = field(default_factory=dict)
    sources: dict[str, Any] = field(default_factory=dict)
    builder_version: str = FINGERPRINT_BUILDER_VERSION

    @property
    def used_total(self) -> int:
        return sum(self.used_tokens.values())

    @property
    def structure_block(self) -> str:
        return "\n".join(self.structure) if self.structure else ""

    @property
    def render_block(self) -> str:
        """The DOCUMENT block the profile prompt receives."""
        parts: list[str] = []
        if self.identity:
            parts.append(f"IDENTITY:\n{self.identity}")
        if self.structure:
            parts.append("STRUCTURE:\n" + "\n".join(self.structure))
        if self.framing:
            parts.append(f"FRAMING:\n{self.framing}")
        if self.coverage:
            parts.append(
                "COVERAGE:\n"
                + "\n".join(f"COVERAGE {i}: {c}" for i, c in enumerate(self.coverage, 1))
            )
        if self.synthesis:
            parts.append(f"SYNTHESIS:\n{self.synthesis}")
        if self.vocabulary:
            parts.append("VOCABULARY: " + ", ".join(self.vocabulary))
        return "\n\n".join(parts)

    def to_dict(self) -> dict[str, Any]:
        return {
            "builder_version": self.builder_version,
            "title": self.title,
            "identity": self.identity,
            "structure": self.structure,
            "framing": self.framing,
            "coverage": self.coverage,
            "synthesis": self.synthesis,
            "vocabulary": self.vocabulary,
            "budget_tokens": self.budget_tokens,
            "allocation": self.allocation,
            "used_tokens": self.used_tokens,
            "sources": self.sources,
        }

    def input_hash(self, content_hash: str = "") -> str:
        """Receipt-chain link: a pure function of the rendered surfaces, the builder
        version, the allocation and the document's content hash (mirrors
        ``context.DocumentContext.input_hash``)."""
        payload = json.dumps(
            {
                "builder": self.builder_version,
                "content_hash": content_hash,
                "identity": self.identity,
                "structure": self.structure,
                "framing": self.framing,
                "coverage": self.coverage,
                "synthesis": self.synthesis,
                "vocabulary": self.vocabulary,
                "allocation": self.allocation,
            },
            sort_keys=True,
            ensure_ascii=False,
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def build_fingerprint(
    document: dict,
    parents: Sequence[dict],
    *,
    budget_tokens: int = DEFAULT_BUDGET_TOKENS,
    allocation: dict[str, float] | None = None,
    extra_terms: Iterable[str] = (),
) -> DocumentFingerprint:
    """Build the vNext deterministic fingerprint.

    ``document``: {source_name, media_type, frontmatter?, doc_id?, content_hash?}.
    ``parents``: the document's parent rows {heading_path, text, region_role,
    chunk_index/char_start} in any order — no ``chunk_id`` required. ``budget_tokens``
    is clamped to [500, 2000]. ``extra_terms`` is an OPTIONAL vocabulary supplement
    (e.g. a caller's leftover signals); the fingerprint is self-sufficient without it.
    """
    budget = max(PROFILE_CONTEXT_BUDGET_MIN, min(int(budget_tokens), PROFILE_CONTEXT_BUDGET_MAX))
    frac = dict(DEFAULT_ALLOCATION)
    if allocation:
        frac.update({k: float(v) for k, v in allocation.items()})
    total_frac = sum(frac.values()) or 1.0
    sub = {k: max(4, int(round(budget * v / total_frac))) for k, v in frac.items()}

    fm = document.get("frontmatter") or {}
    title = str(fm.get("title") or "").strip() or _ctx.clean_title(document.get("source_name") or "")
    ident_bits = [title]
    for key in ("subtitle", "author", "authors", "organization", "publisher", "type", "document_type"):
        v = fm.get(key)
        if v:
            ident_bits.append(f"{key}: {v if isinstance(v, str) else ', '.join(map(str, v))}")
    mt = str(document.get("media_type") or "")
    if mt:
        ident_bits.append(f"format: {mt.split('/')[-1]}")
    identity = _ctx._trim_tokens(" · ".join(ident_bits), sub["identity"])

    body = _eligible_body(parents)
    per = _per_parent_signals(body) if body else []

    # structure: full-document heading stride (spans the doc, never stops at ch.3)
    structure_all = _ctx.structure_lines(parents)
    structure = _ctx._stride_select(structure_all, sub["structure"])

    # framing: the opening orientation of the first eligible parent (its lead excerpt
    # when available — the window's opening thesis — else its salient sentence)
    framing = ""
    if per:
        framing = _ctx._trim_tokens(per[0]["lead"] or per[0]["salient"], sub["framing"])

    # synthesis: the closing content of the last eligible parent (tail-trimmed)
    synthesis = ""
    if len(per) > 1:
        synthesis = _ctx._trim_tokens(per[-1]["salient"], sub["synthesis"], tail=True)

    # vocabulary: source-derived terms + identifiers (GAP-04: no major_concepts)
    vocabulary = _select_vocabulary(per, extra_terms, sub["vocabulary"])

    # coverage: computed LAST and given whatever the other five surfaces did not use,
    # so it is the largest surface AND the total never exceeds the budget.
    used_others = (
        est_tokens(identity)
        + sum(est_tokens(x) + 1 for x in structure)
        + est_tokens(framing)
        + est_tokens(synthesis)
        + sum(est_tokens(t) + 1 for t in vocabulary)
    )
    coverage_budget = max(0, budget - used_others)
    coverage = _select_coverage(per, coverage_budget)

    used = {
        "identity": est_tokens(identity),
        "structure": sum(est_tokens(x) + 1 for x in structure),
        "framing": est_tokens(framing),
        "coverage": sum(est_tokens(x) + 3 for x in coverage),
        "synthesis": est_tokens(synthesis),
        "vocabulary": sum(est_tokens(t) + 1 for t in vocabulary),
    }
    return DocumentFingerprint(
        title=title,
        identity=identity,
        structure=structure,
        framing=framing,
        coverage=coverage,
        synthesis=synthesis,
        vocabulary=vocabulary,
        budget_tokens=budget,
        allocation=sub,
        used_tokens=used,
        sources={
            "parents": len(parents),
            "body_parents": len(body),
            "heading_paths": len(structure_all),
            "structure_mode": ("headings" if len(structure_all) > 2 else "positions"),
            "coverage_samples": len(coverage),
            "media_type": mt,
            "title_source": ("frontmatter" if fm.get("title") else "source_name"),
        },
    )
