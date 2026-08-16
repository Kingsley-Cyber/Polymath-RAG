"""Evidence-span proposal (ADR-0007, ADR-0008).

Pass 2 of the two-pass architecture is GLiNER's job: the evidence task
proposes coarse evidence spans (the 18-class inventory) as linguistic
recall beyond the enumerated trigger vocabulary. On the pinned model it
may abstain — a measured proposal set, not an error.

The lexical lane here is trigger LOCALIZATION: deterministic anchors
that map visible/proposed evidence onto the compiled rule-pack trigger
tables. It never pretends to be the neural pass; a GLiNER-proposed span
that no trigger can localize compiles to UNSUPPORTED — neural recall is
bounded by the curated lexicon, semantics stay with the compiler.

Modes:
  lexical  pass 2 abstains; this lane proposes (default until a
           qualified evidence model exists — experiment 0001)
  hybrid   GLiNER proposals merge with lexical anchors; the compiler
           applies identical gates either way
"""
from __future__ import annotations

import re
from typing import Any

from polymath_shared.contracts import EvidenceSpan

EXTRACTOR_VERSION = "lexical-evidence-v2"
GLINER_EVIDENCE_EXTRACTOR_VERSION = "gliner-evidence-v1"

DEFAULT_MODE = "lexical"

# Q1-R fix: the v1 stemmer could not map past-tense forms ("used" ->
# "us" -> dead end) and copula forms ("is" -> nothing), so realistic
# prose ("used", "based", "reduced", "increased", "reported") produced
# no evidence anchors at all. v2 restores -ed/-ing/-ies forms with
# e-restoration and a small irregular map. Multiword triggers and the
# deterministic compiler are untouched.
_IRREGULAR_LEMMAS = {
    "is": "be", "are": "be", "was": "be", "were": "be", "been": "be",
    "being": "be", "am": "be",
    "made": "make", "did": "do", "led": "lead", "ran": "run",
    "built": "build", "wrote": "write", "held": "hold", "took": "take",
}


def _lemma_candidates(token: str) -> list[str]:
    cands = [token]
    irregular = _IRREGULAR_LEMMAS.get(token)
    if irregular:
        cands.append(irregular)
    n = len(token)
    if n > 4 and token.endswith("ies"):
        cands.append(token[:-3] + "y")      # studies -> study
    if n > 4 and token.endswith("ing"):
        stem = token[:-3]
        cands.append(stem + "e")            # using -> use, making -> make
        cands.append(stem)
    if n > 3 and token.endswith("ed"):
        stem = token[:-2]
        cands.append(stem + "e")            # used -> use, based -> base
        cands.append(stem)
        if stem.endswith("i"):
            cands.append(stem[:-1] + "y")   # tried -> try
        if len(stem) >= 3 and stem[-1] == stem[-2]:
            cands.append(stem[:-1])         # stopped -> stop
    if n > 3 and token.endswith("es"):
        cands.append(token[:-2] + "e")      # uses -> use
    if n > 3 and token.endswith("s"):
        cands.append(token[:-1])            # uses -> use, leads -> lead
    return cands


def _match_verb(token: str, verbs: list[str]) -> str | None:
    lowered = token.lower()
    for cand in _lemma_candidates(lowered):
        if cand in verbs:
            return cand
    return None


def propose_evidence(
    text: str,
    chunk_id: str,
    rule_pack: dict[str, Any],
) -> list[EvidenceSpan]:
    """Deterministic trigger-localization over one chunk using the
    COMPILED trigger tables (class membership included — GATE 5).

    Total order: (start, end, rule order) — reproducible from the same
    text and rule pack. Each trigger carries the evidence class of its
    owning predicate rule; the compiler disambiguates further."""
    lowered = text.lower()
    spans: list[EvidenceSpan] = []

    for rule_id in rule_pack["predicate_order"]:
        rule = rule_pack["predicates"][rule_id]
        ev = rule["evidence"]
        class_id = ev["classes"][0]

        for phrase in ev.get("multiword", []):
            for m in re.finditer(re.escape(phrase.lower()), lowered):
                spans.append(EvidenceSpan(
                    chunk_id=chunk_id,
                    start=m.start(),
                    end=m.end(),
                    text=text[m.start(): m.end()],
                    evidence_class=class_id,
                    trigger_lemma=phrase.split()[0],
                    trigger_lexical_class="MULTIWORD",
                    trigger_predicate_id=rule_id,
                    trigger_match_source="multiword",
                    score=1.0,
                    extractor_version=EXTRACTOR_VERSION,
                ))

        verbs = [v.lower() for v in ev.get("verbs", [])]
        if verbs:
            for m in re.finditer(r"\b[a-z]+(?:'[a-z]+)?\b", lowered):
                lemma = _match_verb(m.group(0), verbs)
                if lemma:
                    spans.append(EvidenceSpan(
                        chunk_id=chunk_id,
                        start=m.start(),
                        end=m.end(),
                        text=text[m.start(): m.end()],
                        evidence_class=class_id,
                        trigger_lemma=lemma,
                        trigger_lexical_class="VERB",
                        trigger_predicate_id=rule_id,
                        trigger_match_source="verbs",
                        score=1.0,
                        extractor_version=EXTRACTOR_VERSION,
                    ))

        for noun in ev.get("nouns", []):
            for m in re.finditer(r"\b" + re.escape(noun.lower()) + r"\b", lowered):
                spans.append(EvidenceSpan(
                    chunk_id=chunk_id,
                    start=m.start(),
                    end=m.end(),
                    text=text[m.start(): m.end()],
                    evidence_class=class_id,
                    trigger_lemma=noun.lower(),
                    trigger_lexical_class="NOUN",
                    trigger_predicate_id=rule_id,
                    trigger_match_source="nouns",
                    score=1.0,
                    extractor_version=EXTRACTOR_VERSION,
                ))

    return sorted(spans, key=lambda s: (s.start, s.end))


def merge_gliner_proposals(
    text: str,
    chunk_id: str,
    gliner_spans: list[dict],
) -> list[EvidenceSpan]:
    """ADR-0008: GLiNER pass 2 proposals enter as evidence candidates
    with their coarse class. The compiler still localizes triggers and
    decides — a proposal with no trigger localizes to UNSUPPORTED."""
    spans: list[EvidenceSpan] = []
    for item in gliner_spans:
        spans.append(EvidenceSpan(
            chunk_id=chunk_id,
            start=item["start"],
            end=item["end"],
            text=item.get("text") or text[item["start"]: item["end"]],
            evidence_class=item["label"],
            trigger_lemma=None,
            score=item["score"],
            extractor_version=GLINER_EVIDENCE_EXTRACTOR_VERSION,
        ))
    return sorted(spans, key=lambda s: (s.start, s.end))


def localize_trigger(span: EvidenceSpan, rule_pack: dict) -> EvidenceSpan:
    """Deterministic trigger localization inside an evidence span: find
    the first compiled verb/noun/multiword match within the span text.

    I3R-R1 typed trigger contract: on a match, records which lexical
    arm of which predicate authorized the trigger (VERB/NOUN/MULTIWORD
    + predicate id + source arm). Verb matching is BOUNDED surface-form
    matching (base + s/es/d/ed/ing + e-drop/y-drop/doubling), never a
    bare prefix wildcard — "application" can no longer match "apply"
    and "startled" cannot match "start".

    Returns the span unchanged when nothing matches — the compiler then
    reports UNSUPPORTED, never a guess."""
    text = span.text
    if span.trigger_lemma:
        return span
    lowered = text.lower()
    for rule_id in rule_pack["predicate_order"]:
        ev = rule_pack["predicates"][rule_id]["evidence"]
        for phrase in sorted(ev.get("multiword", []), key=len, reverse=True):
            if phrase.lower() in lowered:
                span.trigger_lemma = phrase.split()[0]
                span.trigger_lexical_class = "MULTIWORD"
                span.trigger_predicate_id = rule_id
                span.trigger_match_source = "multiword"
                return span
        for noun in sorted(ev.get("nouns", []), key=len, reverse=True):
            if re.search(r"\b" + re.escape(noun.lower()) + r"\b", lowered):
                span.trigger_lemma = noun.lower()
                span.trigger_lexical_class = "NOUN"
                span.trigger_predicate_id = rule_id
                span.trigger_match_source = "nouns"
                return span
        for verb in sorted(ev.get("verbs", []), key=len, reverse=True):
            for m in re.finditer(r"\b[a-z]+(?:'[a-z]+)?\b", lowered):
                if _bounded_verb_form(m.group(0), verb.lower()):
                    span.trigger_lemma = verb.lower()
                    span.trigger_lexical_class = "VERB"
                    span.trigger_predicate_id = rule_id
                    span.trigger_match_source = "verbs"
                    return span
    return span


def _bounded_verb_form(surface: str, lemma: str) -> bool:
    """I3R-R1C: a surface is a valid inflection of `lemma` only under
    explicit bounded forms (base, +s, +es, +d, +ed, +ing with e-drop,
    y->ies/ied, and consonant doubling). Arbitrary suffix strings that
    share a prefix are NOT valid forms."""
    if surface == lemma:
        return True
    forms = {
        lemma + "s", lemma + "es", lemma + "d", lemma + "ed", lemma + "ing",
    }
    if lemma.endswith("e"):
        forms |= {lemma[:-1] + "ing", lemma[:-1] + "d"}
    if lemma.endswith("y"):
        forms |= {lemma[:-1] + "ies", lemma[:-1] + "ied"}
    if (len(lemma) >= 3 and lemma[-3] not in "aeiou"
            and lemma[-2] in "aeiou" and lemma[-1] not in "aeiouy"):
        forms |= {lemma + lemma[-1] + "ed", lemma + lemma[-1] + "ing"}
    return surface in forms
