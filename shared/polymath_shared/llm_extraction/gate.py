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
    quote = e.get("quote") or e.get("evidence") or surface
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
    unknown = {i.neighborhood_id for i in packet.items} - expected_neighborhood_ids
    if unknown:
        return (SanitizeResult(ok=False, error_class="SANITIZE_UNKNOWN_NEIGHBORHOOD",
                               salvaged=salvaged, raw_chars=len(raw),
                               detail=f"model referenced unknown ids: {sorted(unknown)[:4]}"),
                None)
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
        self.collapsed = ""
        self.index_map = []
        last_ws = True
        for i, ch in enumerate(self.text):
            if ch.isspace():
                if not last_ws:
                    self.collapsed += " "
                    self.index_map.append(i)
                last_ws = True
            else:
                self.collapsed += ch
                self.index_map.append(i)
                last_ws = False
        if not self.index_map:
            self.index_map = [0] * len(self.collapsed)


def _find_exact(needle: str, haystack: str) -> tuple[int, int] | None:
    pos = haystack.find(needle)
    if pos == -1:
        return None
    return pos, pos + len(needle)


def _find_ws_collapsed(needle: str, view: ChunkView) -> tuple[int, int] | None:
    """Locate needle modulo whitespace runs; return EXACT source offsets."""
    n_collapsed = _WS_RE.sub(" ", needle.strip())
    if len(n_collapsed) < 4:
        return None
    pos = view.collapsed.find(n_collapsed)
    if pos == -1:
        return None
    start_src = view.index_map[pos]
    end_pos = pos + len(n_collapsed) - 1
    end_src = view.index_map[end_pos] + 1
    return start_src, end_src


def _locate(needle: str, view: ChunkView) -> tuple[int, int] | None:
    hit = _find_exact(needle, view.text)
    if hit:
        return hit
    return _find_ws_collapsed(needle, view)


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


def validate_and_normalize(packet: ExtractionPacket,
                           neighborhoods: dict[str, list[ChunkView]]) -> NormalizedExtraction:
    out = NormalizedExtraction()
    n_ent = n_rel = n_ent_rej = n_rel_rej = 0
    for item in packet.items:
        views = neighborhoods.get(item.neighborhood_id, [])
        by_id = {v.chunk_id: v for v in views}
        for ent in item.entities:
            placed = False
            for view in views:
                q = _locate(ent.quote, view)
                if not q:
                    continue
                hits: list[tuple[int, int]] = []
                in_quote = _find_exact(ent.surface, view.text[q[0]:q[1]])
                if in_quote:
                    hits.append((q[0] + in_quote[0], q[0] + in_quote[1]))
                else:
                    whole = _locate(ent.surface, view)
                    if whole:
                        hits.append(whole)
                for (s, e) in hits[:MAX_MENTIONS_PER_SURFACE]:
                    core, method = map_core_type(ent.type)
                    if method != "policy":
                        out.coercions.append({
                            "surface": ent.surface, "raw_type": ent.type,
                            "core": core, "method": method,
                            "neighborhood_id": item.neighborhood_id})
                    # label is the CANONICAL core type (the worker's
                    # _map_label passes core names through untouched);
                    # raw_type preserves the open-vocabulary proposal.
                    # text is the EXACT source slice — the model's surface
                    # may differ in whitespace (ws-collapsed matching), and
                    # downstream sentence comparison demands byte-exact
                    # span/frame agreement.
                    out.entities_by_chunk.setdefault(view.chunk_id, []).append({
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
            from polymath_shared.llm_extraction.ontology import normalize_predicate
            canon_pred, pred_method = normalize_predicate(rel.predicate)
            if pred_method == "related_fallback":
                out.stats_fallbacks = getattr(out, "stats_fallbacks", 0) + 1
                out.coercions.append({
                    "kind": "predicate_fallback", "raw": rel.predicate,
                    "canonical": canon_pred,
                    "neighborhood_id": item.neighborhood_id})
            missing = [name for name in (rel.subject, rel.object)
                       if not _locate(name, anchor)]
            if missing:
                n_rel_rej += 1
                out.rejections.append({
                    "kind": "relation", "predicate": rel.predicate,
                    "subject": rel.subject, "object": rel.object,
                    "error_class": "UNATTESTED_RELATION_ENDPOINT",
                    "detail": missing,
                    "neighborhood_id": item.neighborhood_id})
                continue
            out.evidence_by_chunk.setdefault(anchor.chunk_id, []).append({
                "start": q_span[0], "end": q_span[1], "text": anchor.text[q_span[0]:q_span[1]],
                "evidence_class": "llm_relation", "predicate": canon_pred,
                "predicate_raw": rel.predicate, "predicate_method": pred_method,
                "subject": rel.subject, "object": rel.object, "score": 1.0})
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
                core, method = map_core_type(
                    next((en.type for en in item.entities
                          if en.surface == name), name))
                if method != "policy":
                    out.coercions.append({
                        "surface": name, "raw_type": name, "core": core,
                        "method": method + "_endpoint",
                        "neighborhood_id": item.neighborhood_id})
                existing.append({"start": s, "end": e, "text": anchor.text[s:e],
                                 "label": name, "score": 1.0})
                n_ent += 1
        out.digests.append({
            "neighborhood_id": item.neighborhood_id,
            **item.digest.model_dump()})
    out.stats = {
        "entities": n_ent, "relations": n_rel,
        "entities_rejected": n_ent_rej, "relations_rejected": n_rel_rej,
        "neighborhoods": len(packet.items),
    }
    return out
