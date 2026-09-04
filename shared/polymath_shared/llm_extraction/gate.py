"""The output gate — sanitize → validate → normalize → (caller writes).

The ONLY boundary between any LLM provider and the extraction pipeline
(different models, same contract). Everything unattested is rejected
durably — a rejection is recorded, never silently dropped (the governing
invariant: filtering decides what becomes knowledge, never whether
observed evidence survives).

VALIDATE means verbatim attestation: every entity surface and every
relation quote must be an exact substring of the neighborhood's chunk
text (whitespace-run normalization allowed for line wrapping — the
located offsets are always exact source coordinates). The model never
computes offsets; Python does.
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field

from polymath_shared.llm_extraction.contract import (
    CONTRACT_ID,
    ExtractionPacket,
    SanitizeResult,
)

# ---------------------------------------------------------------------------
# SANITIZE
# ---------------------------------------------------------------------------

_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL)
_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL)


def strip_thinking(raw: str) -> str:
    """Defense in depth against leaked reasoning tokens (non-thinking mode
    is the primary control). 3-line strip: <think> blocks, code fences,
    leading/trailing prose outside the outermost braces."""
    text = _THINK_RE.sub("", raw)
    m = _FENCE_RE.search(text)
    if m:
        text = m.group(1)
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end > start:
        text = text[start:end + 1]
    return text.strip()


def _repair_truncated(text: str) -> str | None:
    """Truncated-stream repair: keep the longest prefix in which every
    completed construct is intact (the measured failure: output budget
    cuts the stream mid-array or mid-object), close the open bracket
    stack, and drop any trailing separator. Returns repaired JSON text or
    None when nothing usable completed."""
    stack: list[str] = []
    in_str = False
    esc = False
    candidates: list[int] = []
    for i, ch in enumerate(text):
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch in "{[":
            stack.append(ch)
        elif ch in "}]":
            if stack:
                stack.pop()
                if len(stack) >= 2:
                    # an element nested under root completed — safe cut
                    candidates.append(i)
        elif ch == "," and len(stack) >= 3:
            # a key/value pair or array item completed mid-structure
            candidates.append(i)
    while candidates:
        cut = candidates.pop()
        prefix = text[:cut + 1].rstrip()
        if prefix.endswith(","):
            prefix = prefix[:-1].rstrip()
        if not prefix:
            continue
        open_stack: list[str] = []
        in_str = False
        esc = False
        ok = True
        for ch in prefix:
            if in_str:
                if esc:
                    esc = False
                elif ch == "\\":
                    esc = True
                elif ch == '"':
                    in_str = False
                continue
            if ch == '"':
                in_str = True
            elif ch in "{[":
                open_stack.append(ch)
            elif ch in "}]" and open_stack:
                open_stack.pop()
            else:
                continue
        if in_str or esc:
            continue  # cut inside a string literal — try an earlier point
        repaired = prefix + "".join(
            "]" if c == "[" else "}" for c in reversed(open_stack))
        try:
            json.loads(repaired)
            return repaired
        except json.JSONDecodeError:
            ok = False
        if not ok:
            continue
    return None


def _salvage_objects(text: str) -> list[dict]:
    """Last-resort salvage: recover every complete top-level {...}
    object (used when even truncation repair cannot produce a packet)."""
    out: list[dict] = []
    depth = 0
    obj_start = -1
    in_str = False
    esc = False
    for i, ch in enumerate(text):
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            if depth == 0:
                obj_start = i
            depth += 1
        elif ch == "}":
            if depth > 0:
                depth -= 1
                if depth == 0 and obj_start >= 0:
                    try:
                        out.append(json.loads(text[obj_start:i + 1]))
                    except json.JSONDecodeError:
                        pass
                    obj_start = -1
    return out


def _loads_lenient(text: str) -> dict | None:
    """json.loads with strict=False (allows literal control characters —
    measured local-lane failure: raw newlines inside quote strings)."""
    try:
        v = json.loads(text, strict=False)
        return v if isinstance(v, dict) else None
    except Exception:
        return None


def _clean_entity(e: object) -> dict | None:
    if not isinstance(e, dict):
        return None
    surface = e.get("surface") or e.get("name") or e.get("entity")
    if not isinstance(surface, str) or not surface.strip():
        return None
    t = e.get("type") or e.get("entity_type") or "Concept"
    # An entity WITHOUT a quote is dropped, never repaired: synthesizing
    # the quote from the surface would invent the attestation context the
    # model never emitted (a truncated stream cuts the quote field first).
    quote = e.get("quote") or e.get("evidence")
    if not isinstance(quote, str) or not quote.strip():
        return None
    return {"surface": surface.strip()[:200], "type": str(t).strip()[:80],
            "quote": quote.strip()[:2000]}


def _clean_relation(r: object) -> dict | None:
    if not isinstance(r, dict):
        return None
    out = {}
    for k in ("subject", "predicate", "object", "quote"):
        v = r.get(k)
        if not isinstance(v, str) or not v.strip():
            return None
        out[k] = v.strip()
    limit = {"subject": 200, "predicate": 120, "object": 200, "quote": 2000}
    return {k: out[k][:limit[k]] for k in out}


def _enforce_budgets(parsed: dict) -> dict:
    """Per-item shape tolerance + output-budget trimming.

    A malformed entry (entity-shaped relation, missing field) drops THAT
    entry — one bad relation must not poison a whole packet of good,
    attested proposals. Caps are budgets: over-long lists trim to the
    contract limits instead of rejecting the extraction.
    """
    items = parsed.get("items")
    if isinstance(items, list):
        parsed["items"] = [it for it in items[:8] if isinstance(it, dict)]
        for item in parsed["items"]:
            ents = item.get("entities")
            if isinstance(ents, list):
                cleaned = [c for c in (_clean_entity(e) for e in ents) if c]
                item["entities"] = cleaned[:80]
            rels = item.get("relations")
            if isinstance(rels, list):
                cleaned = [c for c in (_clean_relation(r) for r in rels) if c]
                item["relations"] = cleaned[:60]
            digest = item.get("digest")
            if isinstance(digest, dict):
                uses = digest.get("retrieval_uses")
                if isinstance(uses, list):
                    digest["retrieval_uses"] = [
                        u for u in uses if isinstance(u, str)][:3]
                for k in ("central_claim", "main_mechanism"):
                    v = digest.get(k)
                    if isinstance(v, str) and len(v) > 500:
                        digest[k] = v[:500]
            elif digest is not None:
                item["digest"] = {}
    return parsed


def sanitize(raw: str, expected_neighborhood_ids: set[str]) -> tuple[SanitizeResult,
                                                                     ExtractionPacket | None]:
    """SANITIZE stage: thinking strip + budget enforcement + JSON repair
    (lenient parse, truncation repair, per-object salvage) + packet parse.
    Returns a durable disposition either way."""
    text = strip_thinking(raw)
    packet: ExtractionPacket | None = None
    salvaged = False
    loose = _loads_lenient(text)
    if loose is not None:
        try:
            packet = ExtractionPacket.model_validate(_enforce_budgets(loose))
        except Exception:
            packet = None
    if packet is None:
        repaired = _repair_truncated(text)
        if repaired is not None:
            loose = _loads_lenient(repaired)
            if loose is not None:
                try:
                    packet = ExtractionPacket.model_validate(_enforce_budgets(loose))
                    salvaged = True
                except Exception:
                    packet = None
    if packet is None:
        items: list[dict] = []
        for obj in _salvage_objects(text):
            if "neighborhood_id" in obj:
                items.append(obj)
        if items:
            try:
                packet = ExtractionPacket.model_validate({
                    "contract": CONTRACT_ID, "profile": "volume",
                    "items": _enforce_budgets({"items": items})["items"]})
                salvaged = True
            except Exception:
                packet = None
    if packet is None:
        return (SanitizeResult(ok=False, error_class="SANITIZE_UNPARSEABLE",
                               salvaged=False, raw_chars=len(raw),
                               detail="no valid packet after sanitize/salvage"),
                None)
    # One-neighborhood-per-call transport (alias "n1"): an empty id is
    # unambiguous when exactly one neighborhood was sent — assign it.
    # (Measured 2026-08-30: under grammar masking the 4B sometimes emits
    # neighborhood_id:"" while the rest of the item is perfect.)
    if len(expected_neighborhood_ids) == 1:
        only = next(iter(expected_neighborhood_ids))
        for i in packet.items:
            if not i.neighborhood_id:
                i.neighborhood_id = only
    unknown = {i.neighborhood_id for i in packet.items} - expected_neighborhood_ids
    if unknown:
        # Drop ONLY the items that name an unknown neighborhood — one
        # hallucinated id must not discard the attested proposals of the
        # other neighborhoods in the same call. Nothing usable left → the
        # call is quarantined under its own error class.
        kept = [i for i in packet.items if i.neighborhood_id in expected_neighborhood_ids]
        if not kept:
            return (SanitizeResult(ok=False, error_class="SANITIZE_UNKNOWN_NEIGHBORHOOD",
                                   salvaged=salvaged, raw_chars=len(raw),
                                   detail=f"model referenced unknown ids: {sorted(unknown)[:4]}"),
                    None)
        packet = packet.model_copy(update={"items": kept})
        return (SanitizeResult(ok=True, salvaged=True, raw_chars=len(raw),
                               detail=(f"dropped {len(unknown)} item(s) with unknown "
                                       f"ids: {sorted(unknown)[:4]}")),
                packet)
    return (SanitizeResult(ok=True, salvaged=salvaged, raw_chars=len(raw)), packet)


# ---------------------------------------------------------------------------
# VALIDATE (verbatim attestation) + NORMALIZE
# ---------------------------------------------------------------------------

_WS_RE = re.compile(r"\s+")


@dataclass
class ChunkView:
    chunk_id: str
    text: str
    collapsed: str = field(init=False)
    index_map: list[int] = field(init=False)

    def __post_init__(self) -> None:
        collapsed: list[str] = []
        index_map: list[int] = []
        last_ws = True
        for i, ch in enumerate(self.text):
            if ch.isspace():
                if not last_ws:
                    collapsed.append(" ")
                    index_map.append(i)
                last_ws = True
            else:
                collapsed.append(ch)
                index_map.append(i)
                last_ws = False
        self.collapsed = "".join(collapsed)
        self.index_map = index_map


def _aligned(text: str, s: int, e: int) -> bool:
    """Token-boundary check: an attested hit may not start or end INSIDE
    a word ("host" inside "hostname" is not a mention of "host"). A needle
    that itself starts/ends with punctuation is boundary-free on that side."""
    starts_inside = s > 0 and text[s - 1].isalnum() and text[s].isalnum()
    ends_inside = e < len(text) and text[e - 1].isalnum() and text[e].isalnum()
    return not (starts_inside or ends_inside)


def _iter_exact(needle: str, haystack: str):
    """Yield every boundary-aligned exact occurrence, in source order."""
    if not needle:
        return
    pos = haystack.find(needle)
    while pos != -1:
        end = pos + len(needle)
        if _aligned(haystack, pos, end):
            yield pos, end
        pos = haystack.find(needle, pos + 1)


def _find_all_exact(needle: str, haystack: str, limit: int) -> list[tuple[int, int]]:
    hits: list[tuple[int, int]] = []
    for hit in _iter_exact(needle, haystack):
        hits.append(hit)
        if len(hits) >= limit:
            break
    return hits


def _find_exact(needle: str, haystack: str) -> tuple[int, int] | None:
    hits = _find_all_exact(needle, haystack, 1)
    return hits[0] if hits else None


def _find_all_ws_collapsed(needle: str, view: ChunkView,
                           limit: int) -> list[tuple[int, int]]:
    """Locate needle modulo whitespace runs; return EXACT source offsets
    (boundary-aligned in the collapsed text, which preserves every
    non-whitespace character and therefore every word boundary)."""
    n_collapsed = _WS_RE.sub(" ", needle.strip())
    if len(n_collapsed) < 4:
        return []
    hits: list[tuple[int, int]] = []
    for pos, end_pos in _iter_exact(n_collapsed, view.collapsed):
        start_src = view.index_map[pos]
        end_src = view.index_map[end_pos - 1] + 1
        hits.append((start_src, end_src))
        if len(hits) >= limit:
            break
    return hits


def _find_ws_collapsed(needle: str, view: ChunkView) -> tuple[int, int] | None:
    hits = _find_all_ws_collapsed(needle, view, 1)
    return hits[0] if hits else None


def _locate_all(needle: str, view: ChunkView, limit: int) -> list[tuple[int, int]]:
    """Exact hits win; whitespace-collapsed hits only when there is no
    exact hit (never mixed, so the two never double-count one span)."""
    hits = _find_all_exact(needle, view.text, limit)
    if hits:
        return hits
    return _find_all_ws_collapsed(needle, view, limit)


def _locate(needle: str, view: ChunkView) -> tuple[int, int] | None:
    hits = _locate_all(needle, view, 1)
    return hits[0] if hits else None


# Open-vocabulary fallback (documented, raw label preserved everywhere).
# Ordered: first hit wins. Anything unmatched falls to Concept.
LLM_TYPE_FALLBACKS: dict[str, str] = {
    "vulnerability": "Concept", "cve": "Technology", "protocol": "Technology",
    "framework": "Technology", "tool": "Technology", "software": "Technology",
    "hardware": "Product", "system": "Technology", "platform": "Technology",
    "standard": "Concept", "certification": "Concept", "organization": "Organization",
    "company": "Organization", "vendor": "Organization", "agency": "Organization",
    "person": "Person", "role": "Person", "attack": "Method",
    "technique": "Method", "procedure": "Method", "practice": "Method",
    "control": "Method", "process": "Process", "event": "Event",
    "incident": "Event", "metric": "Measurement", "measurement": "Measurement",
    "law": "Concept", "regulation": "Concept", "policy": "Concept",
    "standard_organization": "Organization",
}


# ---------------------------------------------------------------------------
# ATTESTATION-LEVELS-V1 (LLM-DIRECT-CANON, ADR-0017, 2026-09-03)
#
# The span-tagger rule "a relation endpoint must be a substring of the chunk
# that holds the quote" rejected 787 relations in 20 documents (the largest
# single rejection class after unattested entities), most of them correct:
# the subject sat in the neighbouring chunk, or the model wrote the list
# phrase the sentence implies. Endpoint attestation is now a recorded LEVEL:
#   quote        the surface is inside the attested quote
#   anchor       elsewhere in the chunk that holds the quote
#   neighborhood in another chunk of the same neighborhood the model saw
#   document     in a chunk of another neighborhood of the same packet
#   abstract     not located anywhere, but EVERY content token of the
#                surface occurs in the anchor chunk (a paraphrase/list of
#                what the sentence says, never an import of outside facts)
# An endpoint with no token support stays UNATTESTED_RELATION_ENDPOINT.
# Policy: POLYMATH_EXTRACTION_ATTESTATION=tiered (default) | strict
# (quote/anchor only — the pre-canon behaviour, kept for rollback).
# ---------------------------------------------------------------------------
#: LLM-DIRECT-CANON: the gate contract. Part of the extraction receipt identity
#: (llm_provider.contract_identity) AND of the execution contract
#: (execution.worker_contracts["extraction_gate"]), so a gate change is contract
#: drift the reconciler can see (GENERATION-SWAP-V1).
GATE_VERSION = "attestation-levels-v1"

ATTESTATION_LEVELS = ("quote", "anchor", "neighborhood", "document", "abstract")
_STRICT_LEVELS = frozenset({"quote", "anchor"})
_TOKEN_RE = re.compile(r"[a-z0-9]+")
_TOKEN_STOP = frozenset({
    "the", "and", "for", "with", "that", "this", "from", "into", "onto", "over",
    "under", "than", "then", "its", "their", "his", "her", "our", "your", "are",
    "was", "were", "been", "being", "has", "have", "had", "not", "but", "any",
    "all", "some", "such", "each", "per", "via", "etc", "also",
})


def attestation_policy() -> str:
    v = (os.environ.get("POLYMATH_EXTRACTION_ATTESTATION") or "tiered").strip().lower()
    return "strict" if v == "strict" else "tiered"


def _content_tokens(surface: str) -> list[str]:
    return [t for t in _TOKEN_RE.findall((surface or "").lower())
            if len(t) >= 3 and t not in _TOKEN_STOP]


def _tokens_supported(surface: str, text: str) -> bool:
    toks = _content_tokens(surface)
    if not toks:
        return False
    low = (text or "").lower()
    return all(re.search(r"(?<![a-z0-9])" + re.escape(t) + r"(?![a-z0-9])", low) for t in toks)


def attest_endpoint(name: str, anchor: "ChunkView", q_span: tuple[int, int],
                    views: list["ChunkView"],
                    all_views: list["ChunkView"] | None = None,
                    policy: str | None = None) -> str | None:
    """The attestation level of one relation endpoint, or None when the
    surface has no support at all (invention). Pure; deterministic."""
    policy = policy or attestation_policy()
    if _find_exact(name, anchor.text[q_span[0]:q_span[1]]):
        return "quote"
    if _locate(name, anchor):
        return "anchor"
    if policy == "strict":
        return None
    for v in views:
        if v is not anchor and _locate(name, v):
            return "neighborhood"
    for v in (all_views or ()):
        if v is not anchor and v not in views and _locate(name, v):
            return "document"
    if _tokens_supported(name, anchor.text):
        return "abstract"
    return None


def map_core_type(raw_label: str) -> tuple[str, str]:
    """Route an open-vocabulary type to a canonical core type.

    Returns (core_type, method) where method is 'policy' (queried the
    frozen query policy), 'fallback' (documented LLM fallback table), or
    'concept_default' (last resort). The raw label is preserved by the
    caller on every span and in the ledger either way.
    """
    from polymath_shared.query_policy import canonical_of
    core = canonical_of(raw_label)
    if core:
        return core, "policy"
    key = raw_label.strip().lower()
    if key in LLM_TYPE_FALLBACKS:
        return LLM_TYPE_FALLBACKS[key], "fallback"
    return "Concept", "concept_default"


MAX_MENTIONS_PER_SURFACE = 2


@dataclass
class NormalizedExtraction:
    """Worker-shaped output of a validated packet."""

    entities_by_chunk: dict[str, list[dict]] = field(default_factory=dict)
    evidence_by_chunk: dict[str, list[dict]] = field(default_factory=dict)
    digests: list[dict] = field(default_factory=list)
    rejections: list[dict] = field(default_factory=list)
    coercions: list[dict] = field(default_factory=list)
    stats: dict = field(default_factory=dict)
    # EXTRACTION-COVERAGE-V1: one durable disposition per neighborhood sent
    dispositions: list[dict] = field(default_factory=list)


_INTERROGATIVE_RE = re.compile(
    r"^\s*(which|what|who|whom|whose|where|when|why|how)\b", re.IGNORECASE)

_SENTENCE_PUNCT_RE = re.compile(r"[?!;]|\.\s|\.$")
_TERM_MAX_WORDS = 8
# Exact-token, case-sensitive membership: the lowercase rows match
# mid-sentence clause fragments; the capitalized rows are the unambiguous
# clause starters that never begin a real term. Uppercase keywords
# ("IS NOT NULL", "WHEN"), capitalized proper names ("The Open Group"),
# and hyphenated tokens ("In-memory") never match.
_CLAUSE_AUX = frozenset({
    "is", "are", "was", "were", "be", "been", "being",
    "has", "have", "had", "do", "does", "did",
    "will", "would", "should", "could", "can", "cannot", "may", "might",
    "must", "shall",
    "won't", "don't", "didn't", "doesn't", "isn't", "aren't", "wasn't",
    "weren't", "hasn't", "haven't", "hadn't", "can't", "couldn't",
    "shouldn't", "wouldn't", "mustn't",
})
_CLAUSE_OPENERS = frozenset({
    "if", "when", "while", "because", "although", "unless", "whether",
    "that", "this", "these", "those", "there", "it", "you", "we", "they",
    "he", "she", "i", "in", "on", "at", "of", "for", "with", "by", "to",
    "from", "as", "during", "within", "most", "some", "all", "each",
    "every", "any", "and", "or", "but", "so", "then", "also", "however",
    "the", "a", "an",
    "If", "When", "While", "Because", "Although", "Unless", "Whether",
    "You", "We", "They", "He", "She", "There", "However", "Then", "Also",
})


def is_term_surface(surface: str) -> bool:
    """TERM-SURFACE-GATE (owner 2026-08-30): an entity surface or a
    relation endpoint must be a TERM, not a clause. MEASURED: the local
    4B lane emitted clause-length surfaces ("If you won't specify any
    value") joined by RELATED_TO, which then leak into the cards'
    relation and keyword capsules. Owner rule: <= 8 words and no
    sentence punctuation; strengthened (measured necessary — the owner's
    own flagship example is 6 words with no punctuation) by two
    exact-token tests on multi-word surfaces: a lowercase finite
    auxiliary anywhere, or a clause-opening function word first.
    Measured on the live corpus: Learning SQL 10/128 surfaces caught,
    zero false positives; CySA+ (cloud) 118/2624 caught — code
    snippets, list-of-alternatives fragments, and quiz answer clauses,
    with the caught set free of real terms by eye."""
    s = (surface or "").strip()
    if not s:
        return False
    toks = s.split()
    if len(toks) > _TERM_MAX_WORDS:
        return False
    if _SENTENCE_PUNCT_RE.search(s):
        return False
    if len(toks) >= 2:
        if toks[0] in _CLAUSE_OPENERS:
            return False
        if any(t in _CLAUSE_AUX for t in toks):
            return False
    return True


def is_interrogative(quote: str) -> bool:
    """INTERROGATIVE-ATTESTATION (owner 2026-08-30): a relation whose only
    attestation is a question stem or an answer-option list is not a
    stated fact. MEASURED: practice-test stems ("Which one of the
    following is NOT a phase … ? Domination") became OPPOSES facts. The
    rule is deliberately narrow — a quote that ends with '?' or that
    opens with an interrogative word and contains '?' — so declarative
    prose ("X is not a Y.") is never touched."""
    q = (quote or "").strip()
    if not q:
        return False
    if q.endswith("?"):
        return True
    return "?" in q and bool(_INTERROGATIVE_RE.match(q))


def validate_and_normalize(packet: ExtractionPacket,
                           neighborhoods: dict[str, list[ChunkView]]) -> NormalizedExtraction:
    out = NormalizedExtraction()
    n_ent = n_rel = n_ent_rej = n_rel_rej = n_pred_fallback = 0
    policy = attestation_policy()
    all_views = [v for vs in neighborhoods.values() for v in vs]
    n_att = {lvl: 0 for lvl in ATTESTATION_LEVELS}
    for item in packet.items:
        views = neighborhoods.get(item.neighborhood_id, [])
        for ent in item.entities:
            if not is_term_surface(ent.surface):
                n_ent_rej += 1
                out.rejections.append({
                    "kind": "entity", "surface": ent.surface,
                    "error_class": "NON_TERM_SURFACE",
                    "neighborhood_id": item.neighborhood_id})
                continue
            placed = False
            core, method = map_core_type(ent.type)
            for view in views:
                q = _locate(ent.quote, view)
                if not q:
                    continue
                # Mentions INSIDE the attested quote first (boundary-
                # aligned, up to the cap); only when the surface is absent
                # from its own quote fall back to the chunk at large.
                hits = [(q[0] + s, q[0] + e) for s, e in _find_all_exact(
                    ent.surface, view.text[q[0]:q[1]], MAX_MENTIONS_PER_SURFACE)]
                if not hits:
                    hits = _locate_all(ent.surface, view, MAX_MENTIONS_PER_SURFACE)
                if not hits:
                    continue
                if method != "policy":
                    out.coercions.append({
                        "surface": ent.surface, "raw_type": ent.type,
                        "core": core, "method": method,
                        "neighborhood_id": item.neighborhood_id})
                existing = out.entities_by_chunk.setdefault(view.chunk_id, [])
                for (s, e) in hits:
                    if any(x["start"] == s and x["end"] == e for x in existing):
                        continue
                    # label is the CANONICAL core type (the worker's
                    # _map_label passes core names through untouched);
                    # raw_type preserves the open-vocabulary proposal.
                    # text is the EXACT source slice — the model's surface
                    # may differ in whitespace (ws-collapsed matching), and
                    # downstream sentence comparison demands byte-exact
                    # span/frame agreement.
                    existing.append({
                        "start": s, "end": e, "text": view.text[s:e],
                        "label": core, "raw_type": ent.type, "score": 1.0})
                    n_ent += 1
                    placed = True
            if not placed:
                n_ent_rej += 1
                out.rejections.append({
                    "kind": "entity", "surface": ent.surface,
                    "error_class": "UNATTESTED_ENTITY",
                    "neighborhood_id": item.neighborhood_id})
        for rel in item.relations:
            # Cheapest check first — a junk endpoint makes the relation
            # junk regardless of attestation.
            bad_endpoints = [n for n in (rel.subject, rel.object)
                             if not is_term_surface(n)]
            if bad_endpoints:
                n_rel_rej += 1
                out.rejections.append({
                    "kind": "relation", "predicate": rel.predicate,
                    "subject": rel.subject, "object": rel.object,
                    "error_class": "NON_TERM_ENDPOINT",
                    "detail": bad_endpoints,
                    "neighborhood_id": item.neighborhood_id})
                continue
            anchor: ChunkView | None = None
            q_span: tuple[int, int] | None = None
            for view in views:
                q = _locate(rel.quote, view)
                if q:
                    anchor, q_span = view, q
                    break
            if anchor is None or q_span is None:
                n_rel_rej += 1
                out.rejections.append({
                    "kind": "relation", "predicate": rel.predicate,
                    "subject": rel.subject, "object": rel.object,
                    "error_class": "UNATTESTED_RELATION_QUOTE",
                    "neighborhood_id": item.neighborhood_id})
                continue
            if is_interrogative(anchor.text[q_span[0]:q_span[1]]):
                n_rel_rej += 1
                out.rejections.append({
                    "kind": "relation", "predicate": rel.predicate,
                    "subject": rel.subject, "object": rel.object,
                    "error_class": "INTERROGATIVE_ATTESTATION",
                    "neighborhood_id": item.neighborhood_id})
                continue
            from polymath_shared.llm_extraction.ontology import normalize_predicate
            canon_pred, pred_method = normalize_predicate(rel.predicate)
            if pred_method == "related_fallback":
                n_pred_fallback += 1
                out.coercions.append({
                    "kind": "predicate_fallback", "raw": rel.predicate,
                    "canonical": canon_pred,
                    "neighborhood_id": item.neighborhood_id})
            levels = {name: attest_endpoint(name, anchor, q_span, views, all_views, policy)
                      for name in (rel.subject, rel.object)}
            missing = [name for name, lvl in levels.items() if lvl is None]
            if missing:
                n_rel_rej += 1
                out.rejections.append({
                    "kind": "relation", "predicate": rel.predicate,
                    "subject": rel.subject, "object": rel.object,
                    "error_class": "UNATTESTED_RELATION_ENDPOINT",
                    "detail": missing, "attestation_policy": policy,
                    "neighborhood_id": item.neighborhood_id})
                continue
            for lvl in levels.values():
                n_att[lvl] += 1
            out.evidence_by_chunk.setdefault(anchor.chunk_id, []).append({
                "start": q_span[0], "end": q_span[1], "text": anchor.text[q_span[0]:q_span[1]],
                "evidence_class": "llm_relation", "predicate": canon_pred,
                "predicate_raw": rel.predicate, "predicate_method": pred_method,
                "claim_kind": getattr(rel, "claim_kind", None),
                "subject": rel.subject, "object": rel.object, "score": 1.0,
                "attestation": {"subject": levels[rel.subject], "object": levels[rel.object]}})
            n_rel += 1
            # Endpoint mentions co-present with the relation quote: emit
            # additional real mentions inside the quote so the sentence
            # slice binds subject/object to the evidence deterministically.
            for name in (rel.subject, rel.object):
                in_quote = _find_exact(name, anchor.text[q_span[0]:q_span[1]])
                if not in_quote:
                    continue
                s, e = q_span[0] + in_quote[0], q_span[0] + in_quote[1]
                existing = out.entities_by_chunk.setdefault(anchor.chunk_id, [])
                if any(x["start"] == s and x["end"] == e for x in existing):
                    continue
                raw_type = next((en.type for en in item.entities
                                 if en.surface == name), name)
                core, method = map_core_type(raw_type)
                if method != "policy":
                    out.coercions.append({
                        "surface": name, "raw_type": raw_type, "core": core,
                        "method": method + "_endpoint",
                        "neighborhood_id": item.neighborhood_id})
                # label MUST be the canonical core type — the worker's
                # _map_label rejects anything else ("no core mapping"),
                # which would silently discard every endpoint mention.
                existing.append({"start": s, "end": e, "text": anchor.text[s:e],
                                 "label": core, "raw_type": raw_type,
                                 "score": 1.0})
                n_ent += 1
        out.digests.append({
            "neighborhood_id": item.neighborhood_id,
            **item.digest.model_dump()})
    out.stats = {
        "entities": n_ent, "relations": n_rel,
        "entities_rejected": n_ent_rej, "relations_rejected": n_rel_rej,
        "predicate_fallbacks": n_pred_fallback,
        "neighborhoods": len(packet.items),
        "attestation_policy": policy,
        "endpoint_attestation": dict(n_att),
    }
    return out
