"""Evidence-span proposal: the deterministic lexical lane (docx §4, §22).

Phase C measured result (experiments/0001-gliner-evidence-pass.md): the
pinned GLiNER medium model does not fire on the 18 descriptive evidence
labels at any usable threshold, and gliner-multitask-large fires with
entity-style spans (it matches the nouns, not the verb phrases). The
evidence pass therefore runs on the rule pack's compiled trigger
vocabulary — exact verb/noun/multiword matches over each sentence.

This is bounded recall by design: an evidence span exists only when the
curated lexicon contains the trigger. Silence is a valid answer. The
GLiNER evidence task remains in the sidecar wire contract as an optional
co-proposer (POLYMATH_EVIDENCE_PROPOSAL_MODE=gliner) for future
qualification; it never overrides the compiler.
"""
from __future__ import annotations

import re
from typing import Any

from polymath_shared.contracts import EvidenceSpan

EXTRACTOR_VERSION = "lexical-evidence-v1"


def _lemma_candidates(token: str) -> list[str]:
    cands = [token]
    for suffix in ("ing", "ed", "es", "s"):
        if token.endswith(suffix) and len(token) - len(suffix) >= 3:
            cands.append(token[: -len(suffix)])
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
    """Deterministic evidence-span proposal over one chunk.

    Total order: (start, end, rule order) — reproducible from the same
    text and rule pack. Each trigger carries the evidence class of its
    owning predicate rule; the compiler disambiguates further.
    """
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
                    score=1.0,
                    extractor_version=EXTRACTOR_VERSION,
                ))

    return sorted(spans, key=lambda s: (s.start, s.end))
