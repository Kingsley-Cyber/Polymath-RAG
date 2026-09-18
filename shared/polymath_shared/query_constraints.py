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
from collections.abc import Mapping
from dataclasses import dataclass, field, replace

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


# ---------------------------------------------------------------------------
# CA1 — deterministic SOURCE-identity resolution (NOT semantic search)
# ---------------------------------------------------------------------------
# Resolve a SOURCE constraint's surface value to the corpus doc_id it names, by IDENTITY:
# exact normalized title/author, then bounded author-name / title-fragment containment, then
# (only for a single weakly-matched candidate) Scout confirmation. Ambiguity (a tie at the top
# tier) resolves to NOTHING — prefer unresolved over confidently wrong. Scout rank alone never
# breaks an identity tie. The caller passes a source index already scoped to the active corpus
# (shared/ does no I/O); resolution never occurs against a global document universe.
_EXT = re.compile(r"\.(?:md|markdown|txt|html?|pdf|docx?|epub|rst)$", re.I)
_YEAR = re.compile(r"\s*[\(\[]\s*(?:19|20)\d{2}\s*[\)\]]\s*")
_NONWORD = re.compile(r"[^\w\s]")
_SPLIT = re.compile(r"\s[-–—:]\s")                       # author - title | title: subtitle
#: identity-resolution confidence bands (NOT semantic relevance)
_CONF_EXACT = 0.95        # exact normalized title / author / full identity
_CONF_CONTAINS = 0.85     # unique author-name or title containment
_CONF_SCOUT = 0.5         # weak lexical identity confirmed by a Scout nomination
_IDENTITY_FLOOR = 0.9     # a "convincing" identity match (exact or containment)
_WEAK_FLOOR = 0.6         # a title-fragment match (mention-like) — needs Scout to resolve
_SCOUT_CONFIRM_K = 3      # a weak candidate must sit in the Scout's top-K to be confirmed


def _norm(s: str) -> str:
    s = _YEAR.sub(" ", (s or "").lower())
    s = _NONWORD.sub(" ", s)
    return re.sub(r"\s+", " ", s).strip()


def _source_identity(source_name: str) -> tuple[str, str, str]:
    """(author_norm, title_norm, full_norm) parsed deterministically from a corpus source name
    like 'Walter Murch - In the Blink of an Eye (2001).md'. No " - " ⇒ the whole name is the title."""
    name = _EXT.sub("", source_name or "")
    name = _YEAR.sub(" ", name).strip()
    author, title = "", name
    parts = _SPLIT.split(name, maxsplit=1)
    if len(parts) == 2 and parts[0].strip():
        author, title = parts[0].strip(), parts[1].strip()
    return _norm(author), _norm(title), _norm(name)


def _identity_score(value: str, author_n: str, title_n: str, full_n: str) -> float:
    """Lexical IDENTITY score in [0,1] — exact match, then bounded containment. Never embeddings."""
    c = _norm(value)
    if not c:
        return 0.0
    if c == title_n or c == full_n or (author_n and c == author_n):
        return 1.0                                       # exact identity
    ct = set(c.split())
    if author_n and ct and ct <= set(author_n.split()):
        return 0.92                                      # author-name containment ("Murch" ⊂ "walter murch")
    if ct and ct <= set(title_n.split()):
        return 0.6                                       # title fragment (mention-like) — weak
    return 0.0


def resolve_constraint_targets(constraints: list[Constraint], source_index: Mapping[str, str],
                               *, scout_nominations: list[str] | None = None,
                               corpus_id: str | None = None) -> list[Constraint]:
    """Return the constraints with `resolved_targets` (doc_ids) + identity-resolution `confidence`
    filled; `kind`/`value`/`strength`/`reason` are preserved (CA1 resolves identity, never
    reinterprets the relationship). `source_index` = {doc_id: source_name} for the ACTIVE corpus.
    Fail-open: an unresolved / ambiguous source yields `resolved_targets=[]`, never an exception."""
    scout = [d for d in (scout_nominations or []) if d]
    out: list[Constraint] = []
    for c in constraints:
        if c.kind != "SOURCE":
            out.append(c)
            continue
        scored = sorted(                                  # deterministic: strongest first, doc_id tiebreak
            ((_identity_score(c.value, *_source_identity(sn)), did)
             for did, sn in source_index.items()),
            key=lambda x: (-x[0], x[1]))
        scored = [(s, d) for s, d in scored if s > 0.0]
        targets: list[str] = []
        conf = 0.0
        if scored:
            top = scored[0][0]
            tied = [d for s, d in scored if abs(s - top) < 1e-9]
            if len(tied) == 1 and top >= _IDENTITY_FLOOR:
                targets = [tied[0]]
                conf = _CONF_EXACT if top >= 1.0 else _CONF_CONTAINS
            elif len(tied) == 1 and top >= _WEAK_FLOOR and tied[0] in scout[:_SCOUT_CONFIRM_K]:
                targets = [tied[0]]                       # weak identity, Scout-confirmed
                conf = _CONF_SCOUT
            # tie at the top OR weak-and-unconfirmed ⇒ unresolved (prefer [] over a wrong guess)
        out.append(replace(c, resolved_targets=targets, confidence=round(conf, 2)))
    return out
