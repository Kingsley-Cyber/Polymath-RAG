"""SUMMARY-VOCABULARY-LAYER S2: parent summary composition.

Deterministic retrieval-bridge artifact for one parent chunk:
settled facts + durable entities + scientific concepts composed into
a stable summary. No model, no I/O — the envelope carries provenance
(derived_from = child chunk ids).
"""
from __future__ import annotations

from polymath_shared.scientific_concept import (
    named_concept_evidence,
)
from polymath_shared.summary_layer import build_envelope

_REL_PHRASE = {
    "trained_on": "was trained on",
    "evaluated_on": "was evaluated on",
    "released_on": "was released on",
    "published_on": "was published on",
    "occurred_at": "occurred at",
    "introduced": "introduces",
    "proposed": "proposes",
    "uses": "uses",
    "uses_method": "uses the method",
    "contains_component": "includes",
    "part_of": "is part of",
    "member_of": "is a member of",
    "is_a": "is a",
    "instance_of": "is an instance of",
    "similar_to": "is similar to",
    "located_in": "is located in",
    "derived_from": "derives from",
    "acquired": "acquired",
    "created": "created",
    "developed": "developed",
    # PREDICATE-COMPILER-V2 predicates (scientific-kag-v2.0): the frame
    # lane emits these; composition must render them or facts vanish.
    "introduced_by": "was introduced by",
    "proposed_by": "was proposed by",
    "evaluated_against": "was evaluated against",
    "compared_against": "was compared against",
    "depends_on": "depends on",
    "uses_component": "uses",
}

MAX_SUMMARY_FACTS = 4
MAX_ENTITIES = 10
MAX_CONCEPTS = 10


def _fact_sentence(fact: dict) -> str | None:
    subj = (fact.get("subject_surface") or "").strip()
    obj = (fact.get("object_surface") or "").strip()
    rel = _REL_PHRASE.get(fact.get("predicate") or "", "")
    if not (subj and obj and rel):
        return None
    return f"{subj} {rel} {obj}."


def build_parent_summary(*, parent_id: str, parent_text: str,
                         children: list[dict], facts: list[dict],
                         entities: list[dict]) -> dict:
    """children: [{id, text}]; facts: [{predicate, subject_surface,
    object_surface}]; entities: [{surface, core_type}] (durable only).
    Returns the envelope with payload fields per design-of-record."""
    sentences = []
    seen = set()
    for fact in facts:
        s = _fact_sentence(fact)
        if s and s.lower() not in seen:
            seen.add(s.lower())
            sentences.append(s)
        if len(sentences) >= MAX_SUMMARY_FACTS:
            break

    if sentences:
        summary = " ".join(sentences)
    elif parent_text:
        head = " ".join(parent_text.split())[:180]
        summary = head + ("…" if len(head) < len(" ".join(parent_text.split())) else "")
    else:
        summary = ""

    durable = sorted({e["surface"] for e in entities
                      if e.get("surface")
                      and e.get("admission_class", "GLOBAL") != "MENTION_ONLY"})
    entity_surfaces = durable[:MAX_ENTITIES]

    concepts: list[str] = []
    seen_c = set()
    for child in children:
        text = child.get("text") or ""
        for m in re_finditer_candidates(text):
            key = m.lower()
            if key not in seen_c:
                seen_c.add(key)
                concepts.append(m)
        if len(concepts) >= MAX_CONCEPTS:
            break
    concepts = concepts[:MAX_CONCEPTS]

    payload = {
        "summary_type": "parent",
        "parent_id": parent_id,
        "entities": entity_surfaces,
        "concepts": concepts,
        "summary": summary,
        "fact_count": len(sentences),
    }
    return build_envelope(
        derived_from=[c["id"] for c in children],
        payload=payload)


def re_finditer_candidates(text: str) -> list[str]:
    """Named-concept surfaces inside one child text. Deterministic
    token-walk: start at a capitalized token; continue through
    capitalized tokens and small connectors (of/in/the/for/and);
    reject sentence-length runs via the 5-word cap; hyphenated
    technical terms scanned separately."""
    import re

    out: list[str] = []
    seen_spans: list[tuple[int, int]] = []
    tok_re = re.compile(r"[A-Za-z0-9][A-Za-z0-9\-]*")
    connectors = {"of", "in", "the", "for"}
    toks = [(m.start(), m.end(), m.group(0)) for m in tok_re.finditer(text)]
    i = 0
    n = len(toks)
    while i < n:
        st, en, w = toks[i]
        if not w[0].isupper():
            i += 1
            continue
        j = i
        words = [w]
        while j + 1 < n:
            nt = toks[j + 1]
            nxt = nt[2]
            # sentence punctuation breaks a chain
            gap_txt = text[toks[j][1]:nt[0]]
            if any(p in gap_txt for p in ".!?"):
                break
            if nxt[:1].isupper() and len(words) < 5:
                j += 1
                words.append(nxt)
            elif (nxt.lower() in connectors and j + 2 < n
                  and toks[j + 2][2][:1].isupper() and len(words) < 4):
                gap2 = text[nt[1]:toks[j + 2][0]]
                if any(p in gap2 for p in ".!?"):
                    break
                j += 2
                words.extend([nxt, toks[j][2]])
            else:
                break
        surface = text[st:toks[j][1]].strip()
        # strip leading articles from sentence-initial chains
        lead = words[0].lower()
        while surface and lead in ("the", "a", "an") and len(words) > 0:
            surface = surface.split(" ", 1)[1].strip() if " " in surface \
                else ""
            words = words[1:]
            if not words:
                break
            lead = words[0].lower()
        is_acronym = w.isupper() and len(w) >= 2 and w[-1].isdigit() is False
        if surface and (len(words) >= 2 or (w.isupper() and len(w) >= 3)):
            seen_spans.append((st, toks[j][1]))
            if named_concept_evidence(surface):
                out.append(surface)
        i = j + 1
    # lowercase technical compounds ("self-attention layers"): hyphenated
    for m in re.finditer(r"\b[a-z]+(?:-[a-z]+)+\b", text):
        cand = m.group(0)
        if named_concept_evidence(cand.replace("-", " ")) or \
                any(part in ("attention", "search", "training",
                             "learning") for part in cand.split("-")):
            if not any(cs <= m.start() and m.end() <= ce
                       for cs, ce in seen_spans):
                out.append(cand)
    return out
    # lowercase technical compounds ("self-attention layers"): hyphenated
    for m in re.finditer(r"\b[a-z]+(?:-[a-z]+)+\b", text):
        cand = m.group(0)
        if named_concept_evidence(cand.replace("-", " ")) or \
                any(part in ("attention", "search", "training",
                             "learning") for part in cand.split("-")):
            out.append(cand)
    return out
