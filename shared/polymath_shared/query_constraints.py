"""CONSTRAINT-AWARE-RETRIEVAL-V1 (CA0) — explicit query-constraint detection.

Deterministic, no-LLM detection of EXPLICIT source constraints in q0 ("according to X",
"what does X say", "in X's book", "the X method"). This is the high-confidence HARD path
(D2): it protects attribution constraints from planner nondeterminism. Strength comes from
the RELATIONSHIP expressed in q0 (D4), never from the mere presence of a proper noun — a
bare mention ("Murch, editing rhythm, and attention") yields NO constraint here (it may be
enriched to SOFT/EXPLORATORY by the planner later; it is never promoted to HARD on its own).

V1 detects SOURCE constraints only (the representation is extensible to DOCUMENT/SCOPE).
Resolution to doc_ids is CA1 (`resolve_constraint_targets`); ranking use is CA3.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

CONSTRAINT_KINDS = ("SOURCE", "DOCUMENT", "SCOPE")
CONSTRAINT_STRENGTHS = ("HARD", "SOFT", "EXPLORATORY")


@dataclass
class Constraint:
    """An explicit constraint the user's query places on the answer. Additive; JSON-native
    (a plain dataclass so `asdict` round-trips through the receipt)."""
    kind: str                                          # SOURCE (V1) | DOCUMENT | SCOPE
    value: str                                         # verbatim source surface ("Walter Murch", "Save the Cat")
    strength: str                                      # HARD | SOFT | EXPLORATORY (from the q0 relationship)
    resolved_targets: list[str] = field(default_factory=list)  # doc_ids — filled by CA1 resolution
    confidence: float = 0.0                            # detection confidence (resolution sets its own)
    reason: str = ""                                   # which trigger fired (provenance)

    def __post_init__(self) -> None:
        if self.kind not in CONSTRAINT_KINDS:
            self.kind = "SOURCE"
        if self.strength not in CONSTRAINT_STRENGTHS:
            self.strength = "SOFT"                      # never silently assert HARD
        if not isinstance(self.resolved_targets, list):
            self.resolved_targets = list(self.resolved_targets)


# A source/title surface: capitalized-initial phrase allowing internal function words so
# "Save the Cat", "The Anatomy of Story", "In the Blink of an Eye" are captured whole.
# Capitals must be REAL capitals even though the triggers compile case-insensitively:
# (?-i:[A-Z]) turns case-insensitivity OFF for the name-initial letters only, so a lowercase
# topic word ("the blink theory") is never mistaken for a named source.
_CAP = r"(?-i:[A-Z])"
_SRC = rf"(?P<src>[\"“']?{_CAP}[A-Za-z0-9.&'\-]*(?:\s+(?:the|of|an?|and|&|{_CAP}[A-Za-z0-9.&'\-]*)){{0,5}}[\"”']?)"
_SAY = r"(?:says?|argues?|writes?|claims?|notes?|states?|describes?|defines?|explains?|discusses?|suggests?|observes?|tells?)"
_NOUN = r"(?:book|work|writing|account|view|theory|framework|model|method|system|approach|paradigm|technique|structure|beat\s*sheet|principles?)"

# HARD — explicit attribution / source-scoped truth (D4). High confidence.
_HARD = [
    (re.compile(rf"\baccording to {_SRC}", re.I), "according-to"),
    (re.compile(rf"\bper {_SRC}\b", re.I), "per"),
    (re.compile(rf"\bwhat\s+does\s+{_SRC}\s+{_SAY}", re.I), "what-does-X-say"),
    (re.compile(rf"\bhow\s+does\s+{_SRC}\s+{_SAY}", re.I), "how-does-X-say"),
    (re.compile(rf"\bin {_SRC}[’'`]s\s+{_NOUN}", re.I), "in-Xs-book"),
    (re.compile(rf"\bin\s+the\s+book\s+{_SRC}", re.I), "in-the-book-X"),
    (re.compile(rf"\bthe {_SRC}\s+(?:\w+\s+){{0,3}}{_NOUN}\b", re.I), "the-X-method"),
    (re.compile(rf"\b{_SRC}[’'`]s\s+{_NOUN}\b", re.I), "Xs-book"),
    (re.compile(rf"(?:^\s*|[.;,]\s*){_SRC}\s+{_SAY}\b", re.I), "X-says"),
]
# SOFT — framing / lens (D4). Strong preference, not a filter.
_SOFT = [
    (re.compile(rf"\busing {_SRC}\s+as\s+(?:a\s+|the\s+)?(?:lens|frame(?:work)?|guide|basis|foundation)", re.I), "using-X-as-lens"),
    (re.compile(rf"\bfrom {_SRC}[’'`]s\s+(?:perspective|viewpoint|point of view|angle|standpoint|lens)", re.I), "from-Xs-perspective"),
    (re.compile(rf"\bthrough the (?:lens|frame(?:work)?|eyes) of {_SRC}", re.I), "through-lens-of-X"),
    (re.compile(rf"\bconsider(?:ing)? {_SRC}\s+(?:alongside|with|and)\b", re.I), "consider-X-with"),
    (re.compile(rf"\bwith {_SRC}\s+in mind\b", re.I), "with-X-in-mind"),
]
# EXPLORATORY — deliberate expansion (D4). Anchor only.
_EXPLORATORY = [
    (re.compile(rf"\bstarting (?:from|with) {_SRC}", re.I), "starting-from-X"),
    (re.compile(rf"\bbuilding on {_SRC}", re.I), "building-on-X"),
    (re.compile(rf"\buse {_SRC}(?:[’'`]s [\w\s]+?)?\s+to explore\b", re.I), "use-X-to-explore"),
    (re.compile(rf"\bwhat\s+(?:ideas\s+)?connects?\s+(?:to\s+)?{_SRC}", re.I), "what-connects-to-X"),
]

_TIERS = (("HARD", _HARD, 0.9), ("SOFT", _SOFT, 0.7), ("EXPLORATORY", _EXPLORATORY, 0.6))
_FUNC = frozenset("the of a an and & in on for to".split())


def _norm_src(s: str) -> str:
    s = (s or "").strip().strip("\"“”'`")
    s = re.sub(r"[’'`]s$", "", s).strip()               # drop possessive
    s = re.sub(r"\s+", " ", s).strip(" ,.;:")
    parts = s.split()
    while parts and parts[0].lower() in _FUNC:           # trim dangling leading/trailing function words
        parts = parts[1:]
    while parts and parts[-1].lower() in _FUNC:
        parts = parts[:-1]
    return " ".join(parts)


def detect_explicit_constraints(q0: str) -> list[Constraint]:
    """Return the explicit SOURCE constraints stated in q0 (deterministic). The strongest tier
    that matches wins for all sources it names; a query with no attribution/framing trigger
    returns [] (never a fabricated HARD constraint). At most one constraint per distinct source."""
    text = " " + re.sub(r"\s+", " ", (q0 or "").strip()) + " "
    for strength, rules, conf in _TIERS:
        found: dict[str, Constraint] = {}
        for rx, reason in rules:
            for m in rx.finditer(text):
                val = _norm_src(m.group("src"))
                if len(val) < 2 or val.lower() in _FUNC:
                    continue
                key = val.lower()
                if key not in found:
                    found[key] = Constraint(kind="SOURCE", value=val, strength=strength,
                                            confidence=conf, reason=reason)
        if found:
            return list(found.values())                  # first (strongest) tier that matches wins
    return []
