"""E5B deterministic concept inventory (concept-inventory-v1).

Retrieval-representation lane ONLY. Concepts are NOT entities: they
never become canonical entities, admission inputs, fact endpoints,
Neo4j nodes, graph seeds, or graph facts. The sink is experimental
routing metadata.

Zero new NLP/model dependencies: sentence boundaries from existing
text structure, standard-library tokenization, the frozen
GENERIC_HEAD vocabulary for the genericity guard.

Determinism contract: per-document output depends ONLY on (sorted
chunk identities, document text, contract version). No mutable global
counters, no ingestion-order IDs, no timestamp-derived identities,
no unsorted set/dict iteration, no frequency>1 admission authority.
PROCESS(A,B,C) == PROCESS(C,A,B) by construction.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Optional

from polymath_shared.entity_admission import GENERIC_HEAD
from polymath_shared.identity import content_hash

CONCEPT_CONTRACT = "concept-inventory-v1"
CONCEPT_NS = "concept_"

MAX_TOKENS = 5
MIN_TOKENS = 2

DOC_BUDGET_DEFAULT = 8
SECTION_BUDGET_DEFAULT = 6

DOC_BUDGET_GRID = (4, 8, 12)
SECTION_BUDGET_GRID = (3, 6, 8)

_TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9]*(?:['\u2019]s)?(?:/[A-Za-z0-9]+)*")
_STOP = frozenset(
    "a an the and or but if then else of to in on at by for with from as is are was were be "
    "been being that this these those it its they them their there here which who whom whose "
    "what when where why how not no nor so such than too very can could may might must shall "
    "should will would do does did done have has had i you he she we us our your his her him "
    "me my own into over under again once more most other some any all both each few between "
    "during before after above below up down out off about also just only because while since "
    "through against via per without within upon says said say welcome today welcome back "
    "right okay thanks title whereas therefore however although though whether "
    "than rather often already even still until toward towards away always never "
    "cannot hence thus accordingly consequently moreover furthermore otherwise "
    "meanwhile subsequently eventually finally initially currently recently "
    "previously precisely simply merely likely unlikely exactly roughly "
    "approximately typically usually sometimes rarely frequently particularly "
    "especially certainly clearly obviously presumably apparently probably "
    "possibly perhaps maybe instead instead across".split()
)
# clause/punctuation boundaries for candidate termination
_BOUNDARY_RE = re.compile(r"[.!?;:,()\"']")
from polymath_shared.verb_inventory import VERBS as _VERBS   # frozen 2026-09-03 (ADR-0017)

# grammatical function-verb closed class for the verbal-fragment guard
# (versioned policy, NOT a domain ontology; identity normalization is
# unaffected)
_FUNCTION_VERBS = frozenset(
    "bring take give make put use need become seem look come go try keep let "
    "find leave show fall rise grow drop lift cut add see say think know want work "
    "run set turn hold call help mean spend send ask talk start stop "
    "watch read write learn teach test check track measure combine require "
    "allow avoid reduce increase improve lower boost spike compress segment fix trade "
    "consume depend concern require create produce expose judge estimate appear "
    "remain access attempt verify review classify record forward assign attempt "
    "authenticate detect monitor evaluate perform compare attach close open "
    "run launch deploy install configure manage lead direct chair head serve own "
    "possess associate link relate suppress predict reallocate "
    "involve eliminate matter appear judge assess monitor support decline "
    "strengthen change interpret provide feel reallocate predict refer "
    "reveal guarantee understand wonder notice demand interfere"
    .split()
)


def _verb_base(word: str) -> bool:
    """Exact base-form membership (no inflection stemming). Base forms
    that are also nouns ('replay', 'rate', 'control', 'connect') get the
    verb-final compound exemption; inflected forms do not."""
    w = word.lower()
    return w in _VERBS or w in _FUNCTION_VERBS


def _verb_like(word: str) -> bool:
    """Suffix-stemming guard match: lemma and common inflections."""
    w = word.lower()
    if w in _VERBS or w in _FUNCTION_VERBS:
        return True
    for suffix, base_len in (("ed", 2), ("es", 2), ("s", 1)):
        if w.endswith(suffix) and len(w) > base_len + 3:
            stem = w[:-base_len]
            if stem in _VERBS or stem in _FUNCTION_VERBS:
                return True
            if (stem + "e") in _VERBS or (stem + "e") in _FUNCTION_VERBS:
                return True
    return False

_WEAK_MODIFIERS = frozenset({
    "real", "new", "main", "other", "same", "some", "any", "all", "many",
    "several", "general", "basic", "simple", "various", "different",
    "certain", "current", "entire", "whole", "particular", "additional",
    "actual", "own", "better", "worse", "less", "more", "most", "few",
    "effective", "ineffective", "familiar", "explanatory", "common",
    "larger", "smaller", "higher", "greater", "earlier", "later", "longer",
    "shorter", "wider", "narrower", "available", "complete", "unseen",
    "another", "such",
})


def normalize_concept_v1(surface: str) -> str:
    """Normalization policy (concept-inventory-v1):
    NFKC unicode, case fold, whitespace collapse, and a DELIBERATE
    hyphen equivalence: '-' and ' ' normalize to the same separator
    for identity ('working-memory' == 'working memory'). Original
    surface and offsets are retained separately."""
    text = unicodedata.normalize("NFKC", surface)
    text = re.sub(r"\s+", " ", text).strip().lower()
    text = re.sub(r"[-_/]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


@dataclass(frozen=True)
class ConceptOccurrence:
    chunk_id: str
    sentence_index: int
    char_start: int
    char_end: int
    surface: str


@dataclass
class ConceptCandidate:
    concept_id: str
    normalized: str
    surfaces: list[str] = field(default_factory=list)
    occurrences: list[ConceptOccurrence] = field(default_factory=list)
    token_count: int = 0
    generic: bool = False

    def occurrence_count(self) -> int:
        return len(self.occurrences)

    def distinct_chunks(self) -> int:
        return len({o.chunk_id for o in self.occurrences})


def concept_id(normalized: str) -> str:
    normalized = normalize_concept_v1(normalized)
    return CONCEPT_NS + content_hash({
        "normalized": normalized,
        "contract": CONCEPT_CONTRACT,
    })


def _sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+|\n+", text) if s.strip()]


def generate_candidates(
    chunk_id: str,
    text: str,
    *,
    sentence_offset: int = 0,
) -> list[ConceptCandidate]:
    """Sentence-local permissive candidate generation; conservative
    admission happens later. Deterministic (no set iteration)."""
    out: dict[str, ConceptCandidate] = {}
    order: list[str] = []
    for s_idx, sentence in enumerate(_sentences(text)):
        matches = list(_TOKEN_RE.finditer(sentence))
        tokens: list[str] = []
        spans: list[tuple[int, int]] = []
        for m in matches:
            pieces = re.split(r"-", m.group(0))
            off = m.start()
            for p in pieces:
                if not p:
                    continue
                tokens.append(p)
                spans.append((off, off + len(p)))
                off += len(p) + 1
        runs: list[list[int]] = []
        cur: list[int] = []
        for i, tok in enumerate(tokens):
            lower = tok.lower()
            gap = sentence[spans[i - 1][1]:spans[i][0]] if i > 0 else ""
            if lower in _STOP or _BOUNDARY_RE.search(tok):
                if len(cur) >= MIN_TOKENS:
                    runs.append(cur)
                cur = []
            elif _BOUNDARY_RE.search(gap):
                if len(cur) >= MIN_TOKENS:
                    runs.append(cur)
                cur = [i]
            else:
                cur.append(i)
        if len(cur) >= MIN_TOKENS:
            runs.append(cur)
        # "of"-bridging: a run split only by 'of' yields the joined phrase
        # (X of Y, X of Y of Z) — every content slot must be a content token
        of_runs: list[list[int]] = []
        i = 0
        while i < len(tokens):
            j = i
            while j < len(tokens) and (
                tokens[j].lower() in _STOP or tokens[j].lower() in ("of", "per")
                or _BOUNDARY_RE.search(tokens[j])):
                j += 1
            if j < len(tokens):
                k = j
                valid = True
                while k + 1 < len(tokens) and tokens[k + 1].lower() in ("of", "per"):
                    if k + 2 >= len(tokens):
                        valid = False
                        break
                    if tokens[k + 2].lower() in _STOP or _BOUNDARY_RE.search(tokens[k + 2]):
                        valid = False
                        break
                    k += 2
                if valid and k - j + 1 >= MIN_TOKENS and k < len(tokens):
                    of_runs.append(list(range(j, k + 1)))
            i = j + 1
        runs.extend(of_runs)
        for run in runs:
            is_of_run = ("of" in [tokens[i].lower() for i in run] or "per" in [tokens[i].lower() for i in run])
            for start in range(0, len(run) - MIN_TOKENS + 1):
                for end in range(start + MIN_TOKENS, min(start + MAX_TOKENS, len(run)) + 1):
                    idxs = run[start:end]
                    if is_of_run and (
                        tokens[idxs[0]].lower() in ("of", "per") or tokens[idxs[-1]].lower() in ("of", "per")
                    ):
                        continue
                    toks = [tokens[i] for i in idxs]
                    first_pos = spans[idxs[0]][0]
                    last_end = spans[idxs[-1]][1]
                    surface = sentence[first_pos:last_end]
                    norm = normalize_concept_v1(surface)
                    pos = first_pos
                    if pos < 0:
                        continue
                    cand = out.get(norm)
                    if cand is None:
                        cand = ConceptCandidate(
                            concept_id=concept_id(norm),
                            normalized=norm,
                            token_count=len(toks),
                        )
                        out[norm] = cand
                        order.append(norm)
                    if surface not in cand.surfaces:
                        cand.surfaces.append(surface)
                    cand.occurrences.append(ConceptOccurrence(
                        chunk_id=chunk_id,
                        sentence_index=s_idx,
                        char_start=pos,
                        char_end=pos + len(surface),
                        surface=surface,
                    ))
    return [out[n] for n in order]


def apply_overlap_policy(candidates: list[ConceptCandidate]) -> list[ConceptCandidate]:
    """Longest-useful-span policy: a shorter candidate that is a strict
    normalized substring of a longer one is dropped UNLESS it has an
    independent occurrence (an occurrence whose surface is not a
    substring of the longer's surfaces). Deterministic, no set order,
    no cross-call state."""
    by_id: dict[str, ConceptCandidate] = {}
    for c in candidates:
        if c.concept_id in by_id:
            existing = by_id[c.concept_id]
            existing.surfaces.extend(s for s in c.surfaces if s not in existing.surfaces)
            existing.occurrences.extend(c.occurrences)
        else:
            by_id[c.concept_id] = c
    kept: list[ConceptCandidate] = []
    kept_ids: list[str] = []
    ids = sorted(by_id, key=lambda i: (-by_id[i].token_count, by_id[i].normalized))
    for cid in ids:
        cand = by_id[cid]
        longer = next((
            by_id[lid] for lid in kept_ids
            if cand.normalized in by_id[lid].normalized
        ), None)
        if longer is not None:
            independent = any(
                not any(
                    o.chunk_id == lo.chunk_id
                    and lo.char_start <= o.char_start
                    and o.char_end <= lo.char_end
                    for lo in longer.occurrences
                )
                for o in cand.occurrences
            )
            if not independent:
                continue
        # context-noise suppression: a longer candidate that merely adds
        # weak-content tokens around an already-kept shorter one (equal
        # occurrence profile) is dropped in favor of the shorter
        for lid in kept_ids:
            shorter = by_id[lid]
            if cand.normalized.startswith(shorter.normalized) or cand.normalized.endswith(shorter.normalized):
                extra = cand.normalized.replace(shorter.normalized, "", 1).strip().split()
                if extra and all(w in _WEAK_CONTENT for w in extra):
                    if cand.occurrence_count() == shorter.occurrence_count():
                        break
        else:
            kept.append(cand)
            kept_ids.append(cid)
    return kept


def is_generic(candidate: ConceptCandidate) -> bool:
    words = candidate.normalized.split()
    if not words:
        return True
    head = words[-1]
    if head in GENERIC_HEAD:
        return True
    discriminative = [w for w in words if w not in _WEAK_MODIFIERS]
    return len(discriminative) < 2 and len(words) >= 2 and head in GENERIC_HEAD


def admit(
    candidates: list[ConceptCandidate],
    *,
    budget: int,
    in_summary_text: str = "",
) -> list[ConceptCandidate]:
    """Deterministic admission + ranking. Frequency is a ranking
    signal, never admission authority (single-occurrence concepts may
    be admitted). Deterministic tie-break by concept_id."""
    scored = []
    for c in candidates:
        if is_generic(c):
            continue
        words = c.normalized.split()
        if any(_verb_like(w) for w in words):
            continue  # verbal fragment (verb inventory + function verbs)
        if words and words[0] in _WEAK_MODIFIERS:
            continue  # weak-modifier led fragment
        density = sum(1 for w in words if w not in _WEAK_MODIFIERS) / len(words)
        score = (
            c.occurrence_count(),          # frequency (ranking only)
            c.distinct_chunks(),
            round(density, 3),
            -(1 if c.token_count > 3 else 0),  # >3-token candidates rank below
            c.token_count,                 # specificity tie-break
            1 if c.normalized in normalize_concept_v1(in_summary_text) else 0,
            -sum(1 for w in words if w in _WEAK_MODIFIERS),
        )
        scored.append((score, c.concept_id, c))
    scored.sort(key=lambda x: (x[0], x[1]), reverse=True)
    return [c for _, _, c in scored[:budget]]


def build_inventory(
    chunk_id: str,
    text: str,
    *,
    budget: int,
    in_summary_text: str = "",
) -> list[ConceptCandidate]:
    return admit(
        apply_overlap_policy(generate_candidates(chunk_id, text)),
        budget=budget,
        in_summary_text=in_summary_text,
    )


_WEAK_CONTENT = frozenset(
    "information material learner student problem task topic resources resource "
    "response decision results result number explanation research study evidence "
    "example approach strategy strategies method methods person people user thing "
    "stuff kind type part piece point form level amount context aspect factor "
    "feature case instance situation way ways group list set range variety "
    "document content section access environment address credential credentials "
    "permission message data feedback"
    .split()
)


def _ing_stem(word: str) -> str | None:
    if word.endswith("ing") and len(word) > 5:
        stem = word[:-3]
        if stem in _VERBS or stem in _FUNCTION_VERBS:
            return stem
        if (stem + "e") in _VERBS or (stem + "e") in _FUNCTION_VERBS:
            return stem + "e"
    return None


def _pre_filter(candidates: list[ConceptCandidate]) -> list[ConceptCandidate]:
    """Fragment rejection before overlap policy: 4-5-token spans,
    verb-led/tailed fragments, weak-modifier leads, generic heads.
    Gerund tokens ('-ing') are verb-flagged only as the FIRST token of a
    3+ token candidate (sentence-initial gerund clause), so noun
    compounds like 'working memory' survive."""
    survivors: list[ConceptCandidate] = []
    for cand in candidates:
        words = cand.normalized.split()
        if cand.token_count > 3:
            continue
        if not words:
            continue
        if is_generic(cand):
            continue
        if words[0] in _WEAK_MODIFIERS:
            continue
        hyphenated = any(
            re.fullmatch(r"[A-Za-z0-9'\u2019]+(?:-[A-Za-z0-9'\u2019]+)+", s) is not None
            for s in cand.surfaces
        )
        verb_flag = False
        if not hyphenated:
            for i, w in enumerate(words):
                if _verb_like(w):
                    # verb-final compound exemption: X verb where X is a
                    # discriminative noun ('session replay', 'conversion rate')
                    if (i == len(words) - 1 and len(words) == 2 and _verb_base(w)
                            and all(x not in _WEAK_CONTENT and x not in _WEAK_MODIFIERS
                                    for x in words[:i])):
                        continue
                    verb_flag = True
                    break
                stem = _ing_stem(w)
                if stem is not None and i == 0 and len(words) >= 3:
                    verb_flag = True
                    break
        if verb_flag:
            continue
        survivors.append(cand)
    return survivors


def document_inventory(
    chunks: list[dict],  # sorted by chunk_id upstream: [{chunk_id, text, summary}]
    *,
    budget: int = DOC_BUDGET_DEFAULT,
) -> list[ConceptCandidate]:
    candidates: list[ConceptCandidate] = []
    for ch in chunks:
        candidates.extend(generate_candidates(ch["chunk_id"], ch["text"]))
    kept = apply_overlap_policy(_pre_filter(candidates))
    summary_text = " ".join(ch.get("summary") or "" for ch in chunks)
    return admit(kept, budget=budget, in_summary_text=summary_text)


def section_inventory(
    children: list[dict],  # sorted by chunk_id upstream
    *,
    budget: int = SECTION_BUDGET_DEFAULT,
    section_summary: str = "",
) -> list[ConceptCandidate]:
    candidates: list[ConceptCandidate] = []
    for ch in children:
        candidates.extend(generate_candidates(ch["chunk_id"], ch["text"]))
    kept = apply_overlap_policy(_pre_filter(candidates))
    return admit(kept, budget=budget, in_summary_text=section_summary)


def enriched_representation(summary_text: str, concepts: list[ConceptCandidate],
                            max_concept_chars: int = 240) -> str:
    """Serialized enrichment text (routing-concept-enriched-v1 shape).
    Deterministic: concepts already ranked; surfaces joined in order."""
    lines = ["[DOCUMENT SUMMARY]", summary_text.strip(), "", "[KEY CONCEPTS]"]
    for c in concepts:
        surface = c.surfaces[0] if c.surfaces else c.normalized
        lines.append(f"- {surface}")
    text = "\n".join(lines)
    if len(text) > len(summary_text) + max_concept_chars:
        text = text[: len(summary_text) + max_concept_chars].rstrip()
    return text
