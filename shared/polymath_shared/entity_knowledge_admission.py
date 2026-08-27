"""POLYMATH-ENTITY-KNOWLEDGE-ADMISSION-V1 — the T1→T2 entity boundary.

Harbor decides how a mention is INTERPRETED (identity, concept, generic,
reference). That is Tier-1 information and stays exactly as it is: this
module does not touch Harbor, canonicalization, GLiNER, or any frozen
contract. It answers the later, different question:

    is this interpreted entity strong enough to be asserted as a
    canonical node that relations may hang off?

Why it exists: relation precision is now capped by endpoint quality, not
by relation logic. Two measured classes no F-gate can repair —

    "employed Pavlovian conditioning"  ->  Person `pavlov`
    "shown in Figure 4-7"              ->  Document `figure 4-7`

— became durable identities upstream, so FactAdmission could only ever
choose between a wrong edge and a lost one. The fix belongs here, at the
source.

Ordered, fail-closed, cheap-structural-first. Each gate is a pure
function of persisted evidence, so the whole ledger replays in seconds:

    E1 PROVENANCE   source offsets/chunk/score present
    E2 REGION       body prose (shares REGION-POLICY-V1 with FactAdmission)
    E3 SPAN         span is well-formed and does not cut a word
    E4 EXTENT       span is constituent-clean; no adjectival-proper drift
    E5 STRUCTURAL   not a document-structure artifact (Figure 4-7, Table 3)
    E6 TYPE         settled class is a real semantic class
    E7 DURABILITY   durable identity + graph-eligible under Harbor's own
                    admission class

REJECT here never destroys anything: the mention, its provenance and its
Tier-1 interpretation all remain. Only promotion to asserted knowledge
is refused.
"""

from __future__ import annotations

import functools
import pathlib
import re
from dataclasses import dataclass, field
from typing import Any, Optional

import yaml

ENTITY_ADMISSION_CONTRACT = "entity-knowledge-admission-v1"

_POLICY_PATH = pathlib.Path(__file__).with_name("entity_admission_policy.yaml")


@functools.lru_cache(maxsize=1)
def policy() -> dict[str, Any]:
    return yaml.safe_load(_POLICY_PATH.read_text())


PASS = "PASS"
REJECT = "REJECT"


@dataclass(frozen=True)
class EntityVerdict:
    outcome: str
    reason: Optional[str] = None
    detail: Optional[str] = None


@dataclass(frozen=True)
class EntityDecision:
    outcome: str
    reason: Optional[str]
    gate: Optional[str]
    detail: Optional[str] = None
    contract: str = ENTITY_ADMISSION_CONTRACT
    policy_version: str = ""
    trace: tuple[tuple[str, str, Optional[str]], ...] = ()


@dataclass
class EntityContext:
    """Everything a gate may read about one interpreted entity."""
    entity_id: str
    surface: str                      # the exact source surface
    normalized_surface: str
    core_type: Optional[str]          # SETTLED class, never the raw label
    admission_class: Optional[str]    # Harbor's own eligibility column
    doc_id: Optional[str] = None
    chunk_id: Optional[str] = None
    char_start: Optional[int] = None
    char_end: Optional[int] = None
    score: Optional[float] = None
    chunk_text: Optional[str] = None
    region: Optional[str] = None
    anchor_kind: Optional[str] = None
    decision_status: Optional[str] = None
    parse: Optional[dict] = None
    sentence_start: int = 0
    extra: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# E1 provenance
# ---------------------------------------------------------------------------

def e1_provenance(ctx: EntityContext) -> EntityVerdict:
    """An entity that cannot be pointed back at its source cannot be
    asserted, because nothing could ever audit or replay it."""
    if not ctx.entity_id:
        return EntityVerdict(REJECT, "E_PROV", "no entity id")
    if not ctx.surface or not ctx.surface.strip():
        return EntityVerdict(REJECT, "E_PROV", "empty surface")
    if not ctx.doc_id or not ctx.chunk_id:
        return EntityVerdict(REJECT, "E_PROV", "no document/chunk provenance")
    if ctx.char_start is None or ctx.char_end is None:
        return EntityVerdict(REJECT, "E_PROV", "no source offsets")
    if ctx.char_end <= ctx.char_start:
        return EntityVerdict(REJECT, "E_PROV", "degenerate span")
    return EntityVerdict(PASS)


# ---------------------------------------------------------------------------
# E2 region
# ---------------------------------------------------------------------------

def e2_region(ctx: EntityContext) -> EntityVerdict:
    """The same region table FactAdmission uses. A name printed in an
    index, a reference list or a running head is evidence that the string
    occurs — never evidence that the document asserts a referent worth
    putting in the graph."""
    region = ctx.region or "BODY_PROSE"
    spec = policy()["regions"].get(region)
    if spec is None:
        return EntityVerdict(REJECT, "E_REGION_UNKNOWN", region)
    if not spec.get("licenses_entities", False):
        return EntityVerdict(REJECT, spec.get("reason", "E_REGION"), region)
    return EntityVerdict(PASS)


# ---------------------------------------------------------------------------
# E3 span integrity
# ---------------------------------------------------------------------------

_WORDCHAR = re.compile(r"\w")


def e3_span(ctx: EntityContext) -> EntityVerdict:
    """The span must not cut a word in half.

    `employs(prc, pavlov)` came from "employed Pavlovian conditioning":
    the provider span covered `Pavlov` inside `Pavlovian`, so a durable
    Person was minted from a fragment of an adjective. Checking the
    characters either side of the span is deterministic, model-free, and
    catches the whole class.
    """
    text = ctx.chunk_text
    if not text or ctx.char_start is None:
        return EntityVerdict(PASS)          # nothing to check against
    s, e = ctx.char_start, ctx.char_end
    if s < 0 or e > len(text):
        return EntityVerdict(REJECT, "E_SPAN_OUT_OF_RANGE",
                             "span lies outside its chunk")
    if text[s:e] != ctx.surface:
        return EntityVerdict(REJECT, "E_SPAN_SURFACE_MISMATCH",
                             f"chunk holds {text[s:e]!r}, entity claims "
                             f"{ctx.surface!r}")
    if s > 0 and _WORDCHAR.match(text[s - 1]) and _WORDCHAR.match(text[s]):
        return EntityVerdict(REJECT, "E_SPAN_CUTS_WORD",
                             f"span starts inside a word: {text[max(0,s-12):e]!r}")
    if e < len(text) and _WORDCHAR.match(text[e - 1]) and _WORDCHAR.match(text[e]):
        return EntityVerdict(REJECT, "E_SPAN_CUTS_WORD",
                             f"span ends inside a word: {text[s:min(len(text),e+12)]!r}")
    return EntityVerdict(PASS)


# ---------------------------------------------------------------------------
# E4 extent
# ---------------------------------------------------------------------------

def _span_tokens(ctx: EntityContext) -> list[dict]:
    if not ctx.parse or ctx.char_start is None:
        return []
    toks = ctx.parse.get("tokens") or []
    s = ctx.char_start - ctx.sentence_start
    e = ctx.char_end - ctx.sentence_start
    return [t for t in toks
            if t.get("char_start") is not None and s <= t["char_start"] < e]


def e4_extent(ctx: EntityContext) -> EntityVerdict:
    """The span must denote what its grammar says it denotes.

    An adjectival form ("Pavlovian", "Orwellian") describes; it does not
    name the person. Promoting it to a Person node asserts a referent the
    sentence never mentioned. Derivation to the base proper noun is NOT
    attempted — that would be manufacturing identity — so the honest
    outcome is refusal, with the mention preserved at Tier 1.
    """
    toks = _span_tokens(ctx)
    if not toks:
        return EntityVerdict(PASS)          # no parse: abstain, never guess
    naming_types = set(policy()["naming_core_types"])
    if ctx.core_type in naming_types:
        head = None
        ids = {t.get("i") for t in toks}
        for t in toks:
            if t.get("head_i") not in ids or t.get("head_i") == t.get("i"):
                head = t
                break
        head = head or toks[-1]
        if head.get("pos") == "ADJ":
            return EntityVerdict(
                REJECT, "E_EXTENT_ADJECTIVAL",
                f"{ctx.core_type} named by an adjective "
                f"({head.get('text')!r}); the referent is not mentioned")
        if head.get("pos") in {"VERB", "ADV", "AUX", "PART", "SCONJ", "CCONJ"}:
            return EntityVerdict(
                REJECT, "E_EXTENT_NOT_NOMINAL",
                f"{ctx.core_type} headed by {head.get('pos')} "
                f"({head.get('text')!r})")
    return EntityVerdict(PASS)


# ---------------------------------------------------------------------------
# E5 structural
# ---------------------------------------------------------------------------

@functools.lru_cache(maxsize=1)
def _structural_patterns() -> list[re.Pattern]:
    return [re.compile(p, re.I) for p in policy()["structural_patterns"]]


def e5_structural(ctx: EntityContext) -> EntityVerdict:
    """Document furniture is not a participant in what the document says.

    `located_in(figure 4-7, location)` exists because "Figure 4-7" became
    a durable Document entity from a body sentence that merely pointed at
    a figure. E2 cannot catch it — the sentence really is body prose — so
    the string shape has to.
    """
    surface = (ctx.surface or "").strip()
    for pat in _structural_patterns():
        if pat.fullmatch(surface):
            return EntityVerdict(REJECT, "E_STRUCT",
                                 f"document-structure reference {surface!r}")
    return EntityVerdict(PASS)


# ---------------------------------------------------------------------------
# E6 type
# ---------------------------------------------------------------------------

def e6_type(ctx: EntityContext) -> EntityVerdict:
    """The settled class must be a real semantic class (R1: the settled
    class, never the raw provider label)."""
    if not ctx.core_type:
        return EntityVerdict(REJECT, "E_TYPE_MISSING", "no settled class")
    if ctx.core_type not in set(policy()["admissible_core_types"]):
        return EntityVerdict(REJECT, "E_TYPE",
                             f"{ctx.core_type} is not an assertable class")
    return EntityVerdict(PASS)


# ---------------------------------------------------------------------------
# E7 durability
# ---------------------------------------------------------------------------

_PRONOUN_POS = {"PRON"}


def e7_durability(ctx: EntityContext) -> EntityVerdict:
    """Harbor's own eligibility, plus the grammatical nameability test.

    No lexical stoplist (R2): an endpoint fails because of its semantic
    state or because its head token is a pronoun, which is a parser fact.
    Harbor minting CORPUS_SCOPED ids for "we"/"they" is a recorded
    upstream defect; this gate fails closed regardless.
    """
    if not ctx.entity_id or ctx.entity_id.startswith("mention_"):
        return EntityVerdict(REJECT, "E_DURABLE", "no durable identity")
    if ctx.admission_class == "MENTION_ONLY":
        return EntityVerdict(REJECT, "E_DURABLE_INELIGIBLE",
                             "not graph-eligible under entity admission")
    toks = _span_tokens(ctx)
    if toks:
        ids = {t.get("i") for t in toks}
        head = next((t for t in toks
                     if t.get("head_i") not in ids or t.get("head_i") == t.get("i")),
                    toks[-1])
        if head.get("pos") in _PRONOUN_POS:
            return EntityVerdict(REJECT, "E_PRONOMINAL",
                                 "referent named only by a pronoun")
    return EntityVerdict(PASS)


# ---------------------------------------------------------------------------
# chain
# ---------------------------------------------------------------------------

ENTITY_GATES = (
    ("E1_PROVENANCE", e1_provenance),
    ("E2_REGION", e2_region),
    ("E3_SPAN", e3_span),
    ("E4_EXTENT", e4_extent),
    ("E5_STRUCTURAL", e5_structural),
    ("E6_TYPE", e6_type),
    ("E7_DURABILITY", e7_durability),
)


def admit_entity(ctx: EntityContext) -> EntityDecision:
    """Run the ordered chain; the first REJECT decides."""
    trace: list[tuple[str, str, Optional[str]]] = []
    for name, gate in ENTITY_GATES:
        v = gate(ctx)
        trace.append((name, v.outcome, v.reason))
        if v.outcome == REJECT:
            return EntityDecision(REJECT, v.reason, name, v.detail,
                                  policy_version=policy()["policy_version"],
                                  trace=tuple(trace))
    return EntityDecision(PASS, None, None,
                          policy_version=policy()["policy_version"],
                          trace=tuple(trace))
