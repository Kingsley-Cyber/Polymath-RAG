"""IDENTITY-PRECISION-V2 — positive identity evidence, not absence of generics.

Real cross-domain probes (a spoken transcript and an academic psychology
text) showed `entity-admission-v1.1` promoting ordinary prose to GLOBAL
identity: `I`, `That`, `What`, `Researchers`, `These findings`,
`Worked examples`, `Two documents`, `When attention shifts`. Roughly 69%
of identity admissions on those documents were false.

The old rule effectively treated

    sentence-initial capitalization  ~=  proper-name evidence

The conceptual correction:

    CAPITALIZATION IS NEVER SUFFICIENT IDENTITY EVIDENCE.
    IDENTITY REQUIRES POSITIVE EVIDENCE, NOT MERELY THE ABSENCE
    OF GENERIC EVIDENCE.

The mechanism is SYNTACTIC, never a phrase blacklist — a growing
`GENERIC_HEAD` list would be defeated by the next book's fifty new nouns.
spaCy POS separates sentence-initial `Postgres/PROPN` from sentence-initial
`Researchers/NOUN` deterministically, and `syntax-evidence-v1` is already a
qualified contract.

Scope is the identity predicate ONLY. GLiNER, Harbor anchor kinds,
reference_basis, discourse-reference-v1, concept-evidence-v1, the
compiler, binding and canonicalization are all frozen.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum

IDENTITY_CONTRACT = "identity-precision-v2"


class IdentityEvidenceKind(str, Enum):
    PROPER_NAME = "PROPER_NAME"
    ACRONYM = "ACRONYM"
    IDENTIFIER = "IDENTIFIER"
    ESTABLISHED_ALIAS = "ESTABLISHED_ALIAS"


@dataclass(frozen=True)
class IdentityDecision:
    is_identity: bool
    kind: IdentityEvidenceKind | None = None
    reasons: tuple[str, ...] = ()
    exclusions: tuple[str, ...] = ()
    contract: str = IDENTITY_CONTRACT


# Function/clausal POS that can never head a referring nominal.
_NON_NOMINAL_HEAD = frozenset({"PRON", "DET", "SCONJ", "ADP", "ADV", "AUX",
                               "VERB", "PART", "CCONJ", "INTJ"})
# Quantifier lemmas that make a phrase denote a plurality, not one referent.
_QUANTIFIER = frozenset({"one", "two", "three", "several", "many", "few",
                         "every", "each", "all", "some", "both", "various",
                         "multiple", "numerous"})
_ACRONYM_RE = re.compile(r"^[A-Z][A-Z0-9]{1,}$")
_IDENTIFIER_RE = re.compile(r"^[A-Za-z]*\d[A-Za-z0-9.\-]*$")


class RetryableDependencyUnavailable(Exception):
    """A required dependency is momentarily unavailable; the stage may be
    retried without spending an attempt (moved here from the retired
    syntax_readiness module — LLM-DIRECT-CANON, ADR-0017)."""


def _content(tokens: list[dict]) -> list[dict]:
    return [t for t in tokens if t.get("pos") not in {"PUNCT", "SPACE"}]


def identity_evidence(surface: str, *, tokens: list[dict] | None = None,
                      aliases: set[str] | None = None,
                      require_syntax: bool = False,
                      heading_context: bool = False) -> IdentityDecision:
    """Decide IDENTITY from positive evidence only.

    `tokens` are the syntax-evidence-v1 tokens covering this span.

    S3 (D): under `admission-harbor-v2` the caller passes
    `require_syntax=True` and the DEGRADED path becomes physically
    unreachable — absent tokens raise rather than silently returning
    capitalization-based evidence. That is the whole point of the
    dependency: the same sentence must never yield `Researchers -> GENERIC`
    with a healthy sidecar and `Researchers -> GLOBAL` without one.

    The degraded path survives ONLY for surface-only historical evaluation
    (the frozen 55-item gold has no syntax), and never for a V2 decision.

    HEADING-IDENTITY-PRECISION-V1: `heading_context` says this span sits in
    a heading, where publishers title-case as house style and taggers read
    that as PROPN. In that context a PROPN tag whose capitalization is fully
    explained by title-casing is NOT sufficient positive identity evidence —
    otherwise `Working Memory` becomes a GLOBAL identity while `working
    memory` in the body admits as a CONCEPT, splitting one thing in two on
    typography alone. Every other kind of evidence survives untouched:
    acronyms, identifiers, established aliases, and proper names carrying
    capitalization that title-casing could not have produced (`PostgreSQL`).
    """
    if require_syntax and not tokens:

        raise RetryableDependencyUnavailable(
            f"identity_evidence({surface!r}) under admission-harbor-v2 requires "
            f"syntax-evidence-v1 tokens. Falling back to capitalization would "
            f"make graph identity depend on sidecar health.")
    words = [w for w in re.findall(r"[A-Za-z0-9][A-Za-z0-9.\-]*", surface)]
    if not words:
        return IdentityDecision(False, reasons=("empty surface",))

    if aliases and surface.strip().lower() in {a.lower() for a in aliases}:
        return IdentityDecision(True, IdentityEvidenceKind.ESTABLISHED_ALIAS,
                                ("exact match in the established alias set",))

    acronym = any(_ACRONYM_RE.match(w) for w in words)
    identifier = any(_IDENTIFIER_RE.match(w) for w in words)

    if tokens:
        toks = _content(tokens)
        if not toks:
            return IdentityDecision(False, reasons=("no content tokens",))
        excl: list[str] = []

        # E1 clausal / function-word head — "When attention shifts", "What changed"
        head = toks[-1]
        if head.get("pos") in _NON_NOMINAL_HEAD:
            excl.append(f"head {head['text']!r} is {head.get('pos')} — not a nominal referent")
        # E2 pronoun or bare determiner anywhere in a short span — "I", "That", "This"
        if any(t.get("pos") == "PRON" for t in toks):
            excl.append("contains a pronoun")
        if len(toks) == 1 and toks[0].get("pos") in {"DET", "SCONJ", "PRON"}:
            excl.append(f"bare {toks[0].get('pos')}")
        # E3 quantified plurality — "Two documents", "Several laboratory studies",
        # and critically "two John Smith", which must not inherit singular identity
        first = toks[0]
        if (first.get("pos") == "NUM"
                or first.get("lemma", first["text"]).lower() in _QUANTIFIER):
            excl.append(f"quantifier {first['text']!r} — denotes a plurality, "
                        "not one referent")
        if excl:
            return IdentityDecision(False, reasons=(), exclusions=tuple(excl))

        # POSITIVE evidence required. A PROPN tag is what separates
        # sentence-initial `Postgres` from sentence-initial `Researchers`;
        # capitalization alone is deliberately not consulted.
        propn = [t["text"] for t in toks if t.get("pos") == "PROPN"]
        if propn and heading_context:
            # Keep only proper-noun evidence the layout cannot account for.
            from polymath_shared.layout_evidence import independently_capitalized

            propn = [w for w in propn if independently_capitalized(w)]
            if not propn:
                excl.append(
                    "heading context: PROPN tagging is explained by title "
                    "capitalization, which is layout, not identity evidence")
        if propn:
            return IdentityDecision(
                True, IdentityEvidenceKind.PROPER_NAME,
                (f"proper-noun anchor {propn!r} (POS=PROPN, not capitalization)",))
        if acronym:
            return IdentityDecision(True, IdentityEvidenceKind.ACRONYM,
                                    ("acronym structure",))
        if identifier:
            return IdentityDecision(True, IdentityEvidenceKind.IDENTIFIER,
                                    ("identifier/model/version structure",))
        return IdentityDecision(
            False, reasons=(),
            exclusions=tuple(excl) or (
                "no proper-noun anchor, acronym or identifier — "
                "common nominal without positive identity evidence",))

    # ---- degraded mode: shape evidence only, no structural exclusions -----
    if acronym:
        return IdentityDecision(True, IdentityEvidenceKind.ACRONYM,
                                ("acronym structure (degraded: no syntax)",))
    if identifier:
        return IdentityDecision(True, IdentityEvidenceKind.IDENTIFIER,
                                ("identifier structure (degraded: no syntax)",))
    if any(re.match(r"^[A-Z]", w) and len(w) > 1 for w in words):
        return IdentityDecision(True, IdentityEvidenceKind.PROPER_NAME,
                                ("capitalized token (degraded: no syntax — "
                                 "structural exclusions unavailable)",))
    return IdentityDecision(False, exclusions=("no shape evidence (degraded)",))
