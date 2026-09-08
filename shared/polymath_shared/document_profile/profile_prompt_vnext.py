"""vNext global-profile request prompt — consumes the DocumentFingerprint.

Plan of record §18 (global profile / profile-atom integration), §5-§6, slice S5/S8.
Migration authority RETRIEVAL-MIGRATION-DEPENDENCY-V1 §18 (source-anchored vs
routing-inferred fields), §S7.

This is the vNext successor to the live profile prompt (`prompt.py`, `doc-profile-v3.2`).
It keeps the source-anchored fields (ONE / SUMMARY / TOPIC / TERM / Q) and the existing
routing fields (SEARCH / THEORY / CONCEPT / SEEALSO) and ADDS the research-index
surfaces (LATENT-PATTERN / ANCHOR / RECALLQ / TENSION / BRIDGE / INVERSION / BOUNDARY),
consuming the adaptive `DocumentFingerprint` block (full-structure, no first-400 bias)
instead of the lean context block.

It is a NEW, additive module: the LIVE `prompt.py` and `compiler.py` are deliberately
UNTOUCHED (T1828 handoff — until S8 switches the worker behind the quality canary). The
tag vocabulary is imported from `fingerprint` (the single source of truth); the tolerant
COMPILER that parses these tags is the S8 step (the live compiler is locked until then).
Pure policy (shared/): no I/O, no model. Qualification of the added surfaces is the
owner-gated 500/1000/1500/2000 canary.
"""
from __future__ import annotations

from polymath_shared.document_profile.fingerprint import (
    DocumentFingerprint,
    RESEARCH_INDEX_TAGS,
    ROUTING_INFERRED_FIELDS,
    SOURCE_ANCHORED_FIELDS,
)

PROFILE_VNEXT_PROMPT_VERSION = "doc-profile-vnext-v1"

SYSTEM = """You extract a compact retrieval profile from document evidence.

Use only the supplied document information. Correct meaning outranks exact counts; if
there is not enough evidence for an item, omit it rather than inventing information.

Two kinds of fields:

SOURCE-ANCHORED (must be defensible from the document text):

ONE: <what this document is mainly about — one specific sentence>
SUMMARY: <1-2 dense sentences of the main content>
TOPIC: <specific major topic>                         (aim 10)
TERM: <important term, entity, framework, method, acronym; preserve proper names/acronyms>  (aim 10)
Q: <a natural question this document can answer?>      (aim 15)

ROUTING-INFERRED (hypotheses that help a search system reach this document — these are
NOT factual claims and are never cited as evidence):

SEARCH: <short keyword-style query, 2-6 words, no question mark>   (aim 15)
THEORY: <underlying framework / mechanism / explanatory lens>       (aim 10)
CONCEPT: <transferable idea that could matter in another field>     (aim 10)
LATENT-PATTERN: <a recurring latent pattern or structure the document exhibits, distinct from a named concept>
ANCHOR: <a stable anchor idea the document repeatedly returns to>
RECALLQ: <a question whose answer this document is the natural anchor for>
TENSION: <a tension, tradeoff, or opposition the document holds>
BRIDGE: <a cross-domain connection to a different field this document could bridge to>
INVERSION: <the opposite or inverted framing of the document's core idea>
BOUNDARY: <a scope limit, boundary condition, or where the document's claims stop>
SEEALSO: <neighbouring / prerequisite / broader / contrasting knowledge>   (aim 10)

END

RULES

* Write one item per line, starting EVERY line with its exact label (TOPIC:, Q:, LATENT-PATTERN:, ...).
* Never write a label once and then list unlabeled lines under it. One item per line.
* The research-inferred lines (LATENT-PATTERN / ANCHOR / RECALLQ / TENSION / BRIDGE / INVERSION / BOUNDARY)
  are routing hypotheses: emit them only when the document genuinely supports them; a few strong lines beat
  many weak ones. Do not invent a cross-domain BRIDGE or a named THEORY merely because it seems related.
* Preserve identifiers, numbers and acronyms exactly.
* Do not explain your answer. Do not use markdown, bullets, or numbering. Do not create new labels.
End with END."""

USER_TEMPLATE = """DOCUMENT

{fingerprint}
"""


def build_vnext_profile_user_prompt(fingerprint: DocumentFingerprint) -> str:
    """Render the adaptive fingerprint block into the profile request."""
    block = fingerprint.render_block if isinstance(fingerprint, DocumentFingerprint) else str(fingerprint)
    return USER_TEMPLATE.format(fingerprint=(block or "").strip() or "(no document evidence)")


def build_vnext_profile_prompt(fingerprint: DocumentFingerprint) -> tuple[str, str]:
    """Return (system, user) for the vNext global-profile request."""
    return SYSTEM, build_vnext_profile_user_prompt(fingerprint)


def output_fields() -> tuple[str, ...]:
    """The full ordered label set the compiler (S8) must tolerate — source-anchored
    then routing-inferred (which already includes the new research-index tags). The
    single source of truth is `fingerprint`'s constants; this keeps prompt + compiler
    from drifting."""
    return SOURCE_ANCHORED_FIELDS + ROUTING_INFERRED_FIELDS
