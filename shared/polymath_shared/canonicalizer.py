"""C1: deterministic Stage-2 corpus canonicalization policy (pure).

Turns document-local entities into a canonical registry WITHOUT
erasing source-local identity (ADR 0009):

    canonical_entity -> membership -> local entity -> fact -> evidence
        -> source document/span

Policy (conservative: false merges are worse than missed merges):

  SAME_AS     normalized-exact-name match + identical core type +
              mergeable type class (Organization, Location, Product,
              Technology, Document).
  ALIAS_OF    explicit alias declaration from the corpus profile only
              (identical core type required).
  DISTINCT    same normalized name, incompatible core type.
  AMBIGUOUS   homonym-risk classes (Person, Concept, Event, Method,
              Process, Measurement, TimeReference) and unknown core
              types with equal normalized names — abstain.
  UNRESOLVED  empty or unnormalizable surface — abstain.

No fuzzy matching, no LLM, no string-similarity merges. Every
pairwise decision carries basis + canonicalizer_version. Memberships
carry decision, confidence, basis. Singletons are members of their own
canonical entity (decision SELF).

Determinism: canonical ids are content hashes; output is sorted; the
same entity set produces identical output regardless of input order.
Ids are stable under incremental growth (mergeable-class ids do not
embed the member list), so adding a document only adds the required
delta.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

from polymath_shared.identity import content_hash

CANONICALIZER_VERSION = "1.0.0"

MERGEABLE_CORE_TYPES = frozenset({
    "Organization", "Location", "Product", "Technology", "Document",
})
ABSTAIN_CORE_TYPES = frozenset({
    "Person", "Concept", "Event", "Method", "Process", "Measurement",
    "TimeReference",
})

_PUNCT_EDGE_RE = re.compile(r"^[\W_]+|[\W_]+$")


def normalize_surface(surface: str) -> str:
    """Deterministic surface normalization: NFC, lowercase, collapse
    whitespace, strip edge punctuation. Never a fuzzy match."""
    text = unicodedata.normalize("NFC", str(surface or ""))
    text = " ".join(text.split()).lower()
    return _PUNCT_EDGE_RE.sub("", text)


@dataclass(frozen=True)
class CanonicalEntityRow:
    corpus_id: str
    canonical_id: str
    canonical_type: str
    normalized_name: str
    canonicalizer_version: str


@dataclass(frozen=True)
class MembershipRow:
    corpus_id: str
    canonical_id: str
    local_entity_id: str
    decision: str
    confidence: float
    basis: list[str]
    canonicalizer_version: str


@dataclass(frozen=True)
class DecisionRow:
    corpus_id: str
    decision_id: str
    local_entity_a: str
    local_entity_b: str
    decision: str
    confidence: float
    basis: list[str]
    canonical_id: str | None
    canonicalizer_version: str


@dataclass
class CanonicalizationOutput:
    corpus_id: str
    canonicalizer_version: str
    canonical_entities: list[CanonicalEntityRow] = field(default_factory=list)
    memberships: list[MembershipRow] = field(default_factory=list)
    decisions: list[DecisionRow] = field(default_factory=list)


def _canonical_id(corpus_id: str, core_type: str, surface: str,
                  local_entity_id: str | None = None) -> str:
    basis = {
        "v": CANONICALIZER_VERSION,
        "corpus": corpus_id,
        "type": core_type,
        "name": surface,
    }
    if local_entity_id is not None:
        basis["local"] = local_entity_id
    return "cent_" + content_hash(basis)


def _pair_decision_id(a: str, b: str) -> str:
    x, y = sorted((a, b))
    return "dec_" + content_hash({
        "v": CANONICALIZER_VERSION,
        "a": x,
        "b": y,
    })


def canonicalize(
    corpus_id: str,
    entities: list[dict],
    aliases: dict[str, list[str]] | None = None,
) -> CanonicalizationOutput:
    """Compute the canonical registry for a corpus.

    entities rows: {entity_id, core_type, normalized_surface}.
    aliases: normalized canonical surface -> list of normalized alias
    surfaces (explicit corpus-profile declarations; never inferred).
    """
    alias_map: dict[str, str] = {}
    declared_canonicals: set[str] = set()
    for canonical_surface, alias_list in sorted((aliases or {}).items()):
        canon = normalize_surface(canonical_surface)
        declared_canonicals.add(canon)
        alias_map[canon] = canon
        for alias in alias_list or []:
            alias_map[normalize_surface(alias)] = canon

    # (canonical_surface, core_type) -> members, deterministic order
    groups: dict[tuple[str, str], list[tuple[str, str]]] = {}
    for entity in sorted(entities, key=lambda e: (e.get("entity_id") or "")):
        entity_id = entity["entity_id"]
        core_type = entity.get("core_type") or ""
        surface = normalize_surface(entity.get("normalized_surface") or "")
        canon_surface = alias_map.get(surface, surface)
        groups.setdefault((canon_surface, core_type), []).append((entity_id, surface))

    out = CanonicalizationOutput(corpus_id=corpus_id,
                                 canonicalizer_version=CANONICALIZER_VERSION)

    for (canon_surface, core_type) in sorted(groups):
        members = groups[(canon_surface, core_type)]
        alias_declared = canon_surface in declared_canonicals

        if core_type in MERGEABLE_CORE_TYPES:
            merge = True
        elif core_type in ABSTAIN_CORE_TYPES:
            # Explicit source declaration overrides homonym risk.
            merge = alias_declared
        else:
            merge = False  # unknown/empty type: never merge

        if merge:
            canonical_id = _canonical_id(corpus_id, core_type, canon_surface)
            out.canonical_entities.append(CanonicalEntityRow(
                corpus_id, canonical_id, core_type, canon_surface,
                CANONICALIZER_VERSION))
            for eid, surface in members:
                if len(members) == 1:
                    decision, basis = "SELF", ["singleton"]
                elif alias_map.get(surface) == canon_surface and surface != canon_surface:
                    decision, basis = "ALIAS_OF", ["explicit_source_alias"]
                elif alias_declared and core_type in ABSTAIN_CORE_TYPES:
                    decision, basis = "SAME_AS", ["explicit_source_alias"]
                else:
                    decision, basis = "SAME_AS", [
                        "normalized_exact_match",
                        "compatible_core_type",
                        "mergeable_type_class",
                    ]
                out.memberships.append(MembershipRow(
                    corpus_id, canonical_id, eid, decision, 1.0, basis,
                    CANONICALIZER_VERSION))
            for i in range(len(members)):
                for j in range(i + 1, len(members)):
                    a, sa = members[i]
                    b, sb = members[j]
                    if (alias_map.get(sa) == canon_surface and sa != canon_surface) or \
                       (alias_map.get(sb) == canon_surface and sb != canon_surface):
                        decision, basis = "ALIAS_OF", ["explicit_source_alias"]
                    elif alias_declared and core_type in ABSTAIN_CORE_TYPES:
                        decision, basis = "SAME_AS", ["explicit_source_alias"]
                    else:
                        decision, basis = "SAME_AS", [
                            "normalized_exact_match",
                            "compatible_core_type",
                            "mergeable_type_class",
                        ]
                    out.decisions.append(DecisionRow(
                        corpus_id, _pair_decision_id(a, b), a, b,
                        decision, 1.0, basis, canonical_id,
                        CANONICALIZER_VERSION))
        else:
            # Abstain: every member stays in its own singleton canonical
            # entity; pairwise decisions record the abstention.
            for eid, surface in members:
                cid = _canonical_id(corpus_id, core_type, canon_surface, eid)
                if not surface:
                    decision, basis = "UNRESOLVED", ["empty_surface"]
                elif core_type in ABSTAIN_CORE_TYPES:
                    decision, basis = "SELF", ["homonym_risk_type_class"]
                else:
                    decision, basis = "SELF", ["unknown_core_type"]
                out.canonical_entities.append(CanonicalEntityRow(
                    corpus_id, cid, core_type, canon_surface,
                    CANONICALIZER_VERSION))
                out.memberships.append(MembershipRow(
                    corpus_id, cid, eid, decision, 1.0 if decision == "SELF" else 0.0,
                    basis, CANONICALIZER_VERSION))
            for i in range(len(members)):
                for j in range(i + 1, len(members)):
                    a, _ = members[i]
                    b, _ = members[j]
                    if core_type in ABSTAIN_CORE_TYPES:
                        decision, basis = "AMBIGUOUS", [
                            "normalized_exact_match",
                            "homonym_risk_type_class",
                        ]
                    else:
                        decision, basis = "UNRESOLVED", ["unknown_core_type"]
                    out.decisions.append(DecisionRow(
                        corpus_id, _pair_decision_id(a, b), a, b,
                        decision, 0.0, basis, None, CANONICALIZER_VERSION))

    # Cross-type pairs sharing a canonical surface: DISTINCT, recorded
    # for audit; members stay in their own type groups.
    by_surface: dict[str, list[tuple[str, str]]] = {}
    for (surface, core_type), members in groups.items():
        by_surface.setdefault(surface, [])
        for eid, _ in members:
            by_surface[surface].append((eid, core_type))
    for surface in sorted(by_surface):
        typed = sorted(by_surface[surface])
        for i in range(len(typed)):
            for j in range(i + 1, len(typed)):
                a, type_a = typed[i]
                b, type_b = typed[j]
                if type_a == type_b:
                    continue
                out.decisions.append(DecisionRow(
                    corpus_id, _pair_decision_id(a, b), a, b,
                    "DISTINCT", 1.0,
                    ["normalized_exact_match", "incompatible_core_type"],
                    None, CANONICALIZER_VERSION))

    out.canonical_entities.sort(key=lambda r: (r.normalized_name, r.canonical_id))
    out.memberships.sort(key=lambda r: r.local_entity_id)
    out.decisions.sort(key=lambda r: r.decision_id)
    return out
