"""Deterministic ParentSkeleton — the lightweight, CPU-only representation the
parent-map LLM sees, one per retrieval-eligible parent.

Plan of record: docs/wiki/plans/DOCUMENT-SEMANTIC-INDEX-V1-PLAN.md §7-§10, slice S1.

This module is deterministic policy (shared/): no I/O, no model, no network.
It never writes a "summary" with Python and never requires a local LLM or
scikit-learn — only ``re``, ``collections.Counter`` and ``math.log``.

For each eligible parent it produces:

    alias              compact prompt id (P0001) — the manifest maps it back
    heading_path       source structure (kept as given, never invented)
    salient_excerpt    one bounded, source-authored sentence (not first-30-words)
    key_terms[]        3-5 high-information terms (TF x IDF + heading + rarity)
    identifiers[]      exact identifiers extracted DETERMINISTICALLY from source
                       (never left to the model's hook selection — plan §9)
    text_hash          content identity of the source parent
    skeleton_hash      content identity of the derived skeleton

The real ``parent_id`` (Postgres) and opaque content-hash ids never enter the
prompt; only the alias does. Furniture / noise parents (toc, index, front
matter, ...) are ACCOUNTED FOR as exclusions, not mapped and not
retrieval-eligible; the authority for that classification is the repository's
single region-role owner, ``document_region`` — this module does not invent a
competing furniture policy.
"""
from __future__ import annotations

import hashlib
import math
import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from polymath_shared import document_region

#: Bump when the skeleton algorithm changes (plan §32 tracks this independently
#: of the map prompt / map compiler so effects do not couple into rebuilds).
SKELETON_BUILDER_VERSION = "parent-skeleton-v1"

#: Bounds — all deliberately small; the point of the skeleton is density.
SALIENT_EXCERPT_MAX_WORDS = 30
KEY_TERMS_MIN = 3
KEY_TERMS_MAX = 5
MIN_SENTENCE_WORDS = 4
MIN_TERM_LEN = 3
ALIAS_MIN_WIDTH = 4

#: Generic terms rejected from key-term selection (plan §8.3). Intentionally
#: small and frozen — it is a stop list, not a domain thesaurus.
STOP_TERMS = frozenset(
    """
    the a an and or but nor for so yet of to in on at by from with without into
    onto upon over under above below is are was were be been being am do does did
    have has had having this that these those it its it's they them their there
    here what which who whom whose when where why how all any both each few more
    most other some such no not only own same than too very can will just should
    now then once about after again against because before between during through
    above below out off down up while as if else also may might must shall would
    could per via etc within upon toward towards across along around also thus
    section chapter page figure table example note important concept system
    information overview introduction summary contents index
    """.split()
)

# --- exact-identifier patterns (plan §8.1 / §9) --------------------------------
# Ordered most-specific first; extraction preserves canonical source form and
# first-seen order, deduplicated. These are matched on the RAW text so casing
# and zero-padding survive (021, AU21, CVE-2026-0217).
_IDENTIFIER_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bCVE-\d{4}-\d{4,7}\b", re.IGNORECASE),      # CVE-2026-0217
    re.compile(r"\bRFC\s?\d{3,5}\b", re.IGNORECASE),          # RFC 5246 / RFC5246
    re.compile(r"\bv?\d+\.\d+(?:\.\d+)+\b"),                  # 3.11.15, v2.1.0
    re.compile(r"\b[A-Z]{1,6}\d{1,6}(?:-\d{1,6})*\b"),        # AU21, CS0-003, ISO27001
    re.compile(r"\b0\d{2,6}\b"),                              # 021 (>=3-digit zero-padded code;
                                                              # >=3 avoids 2-digit table cells 02/03,
                                                              # a live-canary finding 2026-09-07)
    re.compile(r"\b[A-Z]{2,8}\b"),                            # FACS, TPM, DSL (acronyms)
)

_WORD_RE = re.compile(r"[A-Za-z][A-Za-z0-9'’\-]*[A-Za-z0-9]|[A-Za-z]")
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")
_WS_RE = re.compile(r"\s+")


def normalize_whitespace(text: str) -> str:
    """Collapse runs of whitespace to single spaces and strip. Deterministic;
    the ONLY normalization the skeleton applies to text (Unicode normalization
    for embedding text is the map compiler's concern, plan §10)."""
    return _WS_RE.sub(" ", text or "").strip()


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _blank(match: re.Match[str]) -> str:
    return " " * (match.end() - match.start())


def extract_identifiers(text: str) -> list[str]:
    """Deterministic exact identifiers from source text, canonical form
    preserved, first-seen order, deduplicated. Independent of any model hook
    (plan §9: exact retrieval must never depend on the LLM picking an id).

    Patterns run most-specific first and each match is blanked out (same-length
    spaces preserve positions) before the next, less-specific pattern runs — so a
    generic rule can never re-extract a substring already claimed by a specific
    one (``0217`` inside ``CVE-2026-0217``, ``CVE`` inside the same)."""
    working = text or ""
    found: list[tuple[int, str]] = []
    for pattern in _IDENTIFIER_PATTERNS:
        for match in pattern.finditer(working):
            found.append((match.start(), match.group(0)))
        working = pattern.sub(_blank, working)
    best: dict[str, int] = {}
    for position, token in found:
        # An all-caps common word ("THE", "AND") is not an identifier.
        if token.isalpha() and token.lower() in STOP_TERMS:
            continue
        if token not in best or position < best[token]:
            best[token] = position
    return sorted(best, key=lambda t: (best[t], t))


def _word_tokens(text: str) -> list[str]:
    """Lower-cased content word tokens for DF/TF. Pure numbers are dropped here
    (they are handled as identifiers); short tokens and stop terms too."""
    tokens: list[str] = []
    for raw in _WORD_RE.findall(text or ""):
        low = raw.lower()
        if len(low) < MIN_TERM_LEN or low in STOP_TERMS:
            continue
        tokens.append(low)
    return tokens


def _heading_tokens(heading_path: Sequence[str]) -> set[str]:
    joined = " ".join(str(h) for h in heading_path)
    return set(_word_tokens(joined))


def document_frequency(parent_token_sets: Sequence[set[str]]) -> Counter:
    """df(term) over eligible parents — how many parents contain the term."""
    df: Counter = Counter()
    for token_set in parent_token_sets:
        df.update(token_set)
    return df


def idf(n_docs: int, df: int) -> float:
    """idf(term) = log((N + 1) / (df + 1)) + 1  (plan §8.2). Never divides by 0
    and never negative; a term in every parent still gets a small positive idf."""
    return math.log((n_docs + 1) / (df + 1)) + 1.0


def select_key_terms(
    tokens: Sequence[str],
    heading_tokens: set[str],
    identifier_tokens: set[str],
    df: Counter,
    n_docs: int,
) -> list[str]:
    """3-5 high-information terms: TF x IDF + heading overlap + rare-identifier
    bonus, generic stop terms already rejected. Deterministic tie-break: score
    desc, then term asc."""
    if not tokens:
        return []
    tf = Counter(tokens)
    scores: dict[str, float] = {}
    for term, count in tf.items():
        weight = idf(n_docs, df.get(term, 0))
        score = count * weight
        if term in heading_tokens:
            score += 2.0 * weight          # heading overlap
        if term in identifier_tokens:
            score += 3.0 * weight          # rare identifier bonus
        scores[term] = score
    ranked = sorted(scores, key=lambda t: (-scores[t], t))
    return ranked[:KEY_TERMS_MAX]


def _is_boilerplate(sentence: str) -> bool:
    """Cheap deterministic boilerplate reject: mostly non-alphabetic, or a bare
    page/number line, or an all-caps running header."""
    letters = sum(ch.isalpha() for ch in sentence)
    if letters < max(3, len(sentence) // 3):
        return True
    if re.fullmatch(r"[\d\W]+", sentence.strip() or " "):
        return True
    return False


def _sentences(text: str) -> list[str]:
    out: list[str] = []
    for part in _SENTENCE_SPLIT_RE.split(text):
        part = part.strip()
        if part:
            out.append(part)
    return out


def _truncate_words(text: str, max_words: int) -> str:
    words = text.split()
    if len(words) <= max_words:
        return text
    return " ".join(words[:max_words])


def select_salient_excerpt(
    text: str,
    heading_tokens: set[str],
    key_terms: Sequence[str],
    identifiers: Sequence[str],
) -> str:
    """Highest-scoring source sentence (never blindly the first 30 words), tie
    broken by earliest position, truncated to a small word ceiling (plan §8.4)."""
    normalized = normalize_whitespace(text)
    if not normalized:
        return ""
    key_set = set(key_terms)
    id_set = set(identifiers)
    best_score = -1.0
    best_sentence = ""
    for position, sentence in enumerate(_sentences(normalized)):
        words = sentence.split()
        if len(words) < MIN_SENTENCE_WORDS or _is_boilerplate(sentence):
            continue
        tokens = set(_word_tokens(sentence))
        score = float(len(tokens & key_set))
        score += 0.5 * len(tokens & heading_tokens)
        if any(ident in sentence for ident in id_set):
            score += 1.0
        # Prefer earlier sentences on ties: strictly-greater keeps the first.
        if score > best_score:
            best_score = score
            best_sentence = sentence
    if not best_sentence:
        # No qualifying sentence (e.g. a list or a single fragment): fall back to
        # the leading bounded slice of normalized text — still deterministic.
        best_sentence = normalized
    return _truncate_words(best_sentence, SALIENT_EXCERPT_MAX_WORDS)


@dataclass(frozen=True)
class ParentSkeleton:
    """One deterministic skeleton. ``parent_id`` is Postgres identity and never
    enters the prompt; the prompt sees ``alias``, ``heading_path``,
    ``salient_excerpt``, ``key_terms`` and ``identifiers`` only."""

    parent_id: str
    alias: str
    ordinal: int
    heading_path: tuple[str, ...]
    region_role: str
    source_position: int
    salient_excerpt: str
    key_terms: tuple[str, ...]
    identifiers: tuple[str, ...]
    text_hash: str
    skeleton_hash: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "parent_id": self.parent_id,
            "alias": self.alias,
            "ordinal": self.ordinal,
            "heading_path": list(self.heading_path),
            "region_role": self.region_role,
            "source_position": self.source_position,
            "salient_excerpt": self.salient_excerpt,
            "key_terms": list(self.key_terms),
            "identifiers": list(self.identifiers),
            "text_hash": self.text_hash,
            "skeleton_hash": self.skeleton_hash,
        }


@dataclass(frozen=True)
class ExcludedParent:
    """A parent accounted for but not mapped (plan §20.3)."""

    parent_id: str
    region_role: str
    reason: str


@dataclass(frozen=True)
class SkeletonManifest:
    builder_version: str
    skeletons: tuple[ParentSkeleton, ...]
    excluded: tuple[ExcludedParent, ...]
    alias_to_parent: dict[str, str] = field(default_factory=dict)
    manifest_hash: str = ""

    @property
    def eligible_count(self) -> int:
        return len(self.skeletons)

    def to_dict(self) -> dict[str, Any]:
        return {
            "builder_version": self.builder_version,
            "skeletons": [s.to_dict() for s in self.skeletons],
            "excluded": [
                {"parent_id": e.parent_id, "region_role": e.region_role, "reason": e.reason}
                for e in self.excluded
            ],
            "alias_to_parent": dict(self.alias_to_parent),
            "manifest_hash": self.manifest_hash,
        }


def _normalize_heading(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,) if value.strip() else ()
    return tuple(str(v) for v in value if str(v).strip())


def _identity(parent: Mapping[str, Any]) -> str:
    """The durable parent identity is the parent chunk's Postgres id
    (`chunk_id`, content-derived `chunk_<sha256(doc_id|idx|text)>`). `chunk_index`
    is positional (`UNIQUE(doc_id, chunk_index)`) and NOT stable across re-ingest,
    so it must never become a durable map key — a row without a durable id is a
    caller-contract error, raised loudly rather than mis-keyed."""
    for key in ("chunk_id", "parent_id"):
        val = parent.get(key)
        if val is not None and str(val).strip() != "":
            return str(val)
    raise ValueError(
        "ParentSkeleton requires a durable parent chunk id (chunk_id/parent_id); "
        "chunk_index is positional, not durable identity"
    )


def _source_position(parent: Mapping[str, Any], position: int) -> int:
    for key in ("char_start", "source_position", "chunk_index"):
        val = parent.get(key)
        if isinstance(val, int):
            return val
        if isinstance(val, str) and val.isdigit():
            return int(val)
    return position


def _skeleton_hash(
    heading_path: tuple[str, ...],
    region_role: str,
    salient_excerpt: str,
    key_terms: tuple[str, ...],
    identifiers: tuple[str, ...],
) -> str:
    # Content identity of the DERIVED skeleton (excludes alias/ordinal/position
    # so identical parent content yields an identical hash and re-aliasing does
    # not churn it — plan §32/§33).
    payload = "\x1f".join(
        [
            SKELETON_BUILDER_VERSION,
            "\x1e".join(heading_path),
            region_role,
            salient_excerpt,
            "\x1e".join(key_terms),
            "\x1e".join(identifiers),
        ]
    )
    return _sha256(payload)


def build_parent_skeletons(
    parents: Sequence[Mapping[str, Any]],
) -> SkeletonManifest:
    """Build the deterministic skeleton manifest for one document's parents.

    ``parents`` are the repository's parent rows (as ``context.py`` consumes
    them): mappings with ``text``, ``heading_path``, ``region_role`` and an
    identity/order field (``parent_id`` / ``chunk_index`` / ``char_start``), in
    any order. Eligible parents (non-noisy role, non-empty text) get a skeleton;
    everything else is recorded as an exclusion. Same input => same manifest.
    """
    # 1) Split eligible from excluded, deterministically ordered by source
    #    position then identity so alias assignment is stable regardless of the
    #    caller's ordering.
    eligible: list[tuple[int, str, tuple[str, ...], str, str]] = []
    excluded: list[ExcludedParent] = []
    for position, parent in enumerate(parents):
        pid = _identity(parent)
        role = str(parent.get("region_role") or document_region.ROLE_UNKNOWN)
        heading_path = _normalize_heading(parent.get("heading_path"))
        text = normalize_whitespace(str(parent.get("text") or ""))
        if document_region.is_noisy(role):
            excluded.append(ExcludedParent(parent_id=pid, region_role=role, reason=role))
            continue
        if not text:
            excluded.append(ExcludedParent(parent_id=pid, region_role=role, reason="empty"))
            continue
        src_pos = _source_position(parent, position)
        eligible.append((src_pos, pid, heading_path, role, text))
    eligible.sort(key=lambda item: (item[0], item[1]))

    # 2) Corpus statistics over the eligible parents (sparse counters, §8.2).
    token_lists = [_word_tokens(text) for (_p, _id, _hp, _r, text) in eligible]
    token_sets = [set(toks) for toks in token_lists]
    df = document_frequency(token_sets)
    n_docs = len(eligible)

    # 3) Per-parent skeleton.
    width = max(ALIAS_MIN_WIDTH, len(str(n_docs)))
    skeletons: list[ParentSkeleton] = []
    alias_to_parent: dict[str, str] = {}
    for ordinal, (src_pos, pid, heading_path, role, text) in enumerate(eligible):
        alias = f"P{ordinal + 1:0{width}d}"
        heading_tokens = _heading_tokens(heading_path)
        identifiers = tuple(extract_identifiers(text))
        identifier_tokens = {i.lower() for i in identifiers}
        key_terms = tuple(
            select_key_terms(token_lists[ordinal], heading_tokens, identifier_tokens, df, n_docs)
        )
        salient = select_salient_excerpt(text, heading_tokens, key_terms, identifiers)
        skeletons.append(
            ParentSkeleton(
                parent_id=pid,
                alias=alias,
                ordinal=ordinal,
                heading_path=heading_path,
                region_role=role,
                source_position=src_pos,
                salient_excerpt=salient,
                key_terms=key_terms,
                identifiers=identifiers,
                text_hash=_sha256(text),
                skeleton_hash=_skeleton_hash(heading_path, role, salient, key_terms, identifiers),
            )
        )
        alias_to_parent[alias] = pid

    manifest_hash = _sha256(
        "\x1d".join(f"{s.alias}\x1c{s.parent_id}\x1c{s.skeleton_hash}" for s in skeletons)
    )
    return SkeletonManifest(
        builder_version=SKELETON_BUILDER_VERSION,
        skeletons=tuple(skeletons),
        excluded=tuple(excluded),
        alias_to_parent=alias_to_parent,
        manifest_hash=manifest_hash,
    )
