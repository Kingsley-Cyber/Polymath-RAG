"""DISCOURSE-REFERENCE-V1 — deterministic reference_basis resolution.

Plan: `docs/wiki/plans/REFERENTIAL-ADMISSION-V2-PLAN.md`, PHASE 2B.

This is NOT coreference resolution. It answers exactly one question about
a LOCAL_REFERENCE mention:

    ANTECEDENT_RESOLVED | DOCUMENT_CONSTITUTED | EXTERNAL_UNRESOLVED | AMBIGUOUS

FORBIDDEN inferences (each would smuggle back the hidden guessing this
whole programme exists to remove):
  - nearest compatible noun        -> antecedent
  - appears twice                  -> same entity
  - same GLiNER type               -> same referent
  - embeddings / fuzzy linking / neural coreference / GLinker

ALLOWED evidence, all deterministic and all recorded on the result:
  E1 explicit apposition
  E2 explicit alias / equivalence construction
  E3 unambiguous repeated named anchor
  E4 definite/demonstrative with EXACTLY ONE compatible local antecedent,
     where "compatible" means either a shared lexical HEAD, or a TYPE-NOUN
     head naming the core_type of exactly one admitted anchor
  E5 event nominalization with an unambiguous source event in the document
  E6 bounded discourse participant: recurs AND has a discriminating modifier
     AND its head is neither a generic head nor an external-party noun

Two plausible antecedents -> AMBIGUOUS. Never a coin flip.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from polymath_shared.entity_admission import GENERIC_HEAD
from polymath_shared.entity_harbor import ReferenceBasis

DISCOURSE_CONTRACT = "discourse-reference-v1"

_DET = ("the ", "this ", "that ", "these ", "those ", "our ", "its ", "their ")
_STOP = frozenset({"the", "a", "an", "this", "that", "these", "those", "our",
                   "its", "their", "of", "for", "in", "on", "to", "and"})

# E5: nominalization -> the verb whose event it names. Deliberately a small
# closed table, not morphological guessing.
# PHASE 2B.1: the tables are POLICY DATA, versioned and hash-pinned, never
# inline constants. Once Harbor governs fact eligibility they are too
# authoritative to live as anonymous literals.
POLICY_PATH = (Path(__file__).resolve().parents[2]
               / "resources" / "discourse" / "discourse-reference-policy-v1.json")
POLICY_SHA256 = "4694c626adb79bdc052298b457b204bb8d5993dbfef1724132d043bc0bce93e7"


def _load_policy() -> dict:
    body = POLICY_PATH.read_text()
    digest = hashlib.sha256(body.encode()).hexdigest()
    if digest != POLICY_SHA256:
        raise RuntimeError(
            f"discourse policy pack drifted: {POLICY_PATH.name} sha256={digest} "
            f"expected {POLICY_SHA256}. Policy data is pinned; update the pin "
            f"deliberately with a gate rerun, never silently."
        )
    return json.loads(body)


_POLICY = _load_policy()
POLICY_VERSION = _POLICY["version"]
_TYPE_NOUN = {k: v["core_type"] for k, v in _POLICY["type_noun"].items()}
_INDEFINITE = tuple(_POLICY["indefinite_markers"])

# E6 guards. Recurrence alone is FORBIDDEN evidence (REVISION 2), so E6 needs
# a head that can constitute a participant at all.
#   - a generic head ("the system" x3) is repetition of a category, not a referent
#   - an external-party noun ("the vendor") denotes a party existing INDEPENDENTLY
#     of the document, so the document cannot constitute it; it may only be
#     ANTECEDENT_RESOLVED to a named anchor, or stay EXTERNAL_UNRESOLVED
_EXTERNAL_PARTY = frozenset(_POLICY["external_party"])

# SET-PARTITION-REFERENCE-V1. Ordinals are a genuinely CLOSED grammatical
# class in English — unlike nouns, they can be enumerated completely — so
# this is policy data of the same kind as the determiner and quantifier
# sets, not a noun blacklist. Numeric forms (2nd, 3rd) are matched by shape.
_ORDINAL = frozenset({
    "first", "second", "third", "fourth", "fifth", "sixth", "seventh",
    "eighth", "ninth", "tenth", "eleventh", "twelfth", "thirteenth",
    "fourteenth", "fifteenth", "sixteenth", "seventeenth", "eighteenth",
    "nineteenth", "twentieth", "last", "latter", "former", "next",
    "previous", "preceding", "subsequent",
})
_ORDINAL_NUMERIC = re.compile(r"^\d+(?:st|nd|rd|th)$", re.I)


def _is_ordinal_partition(target: str, tokens: list[dict] | None) -> str | None:
    """A definite NP whose modifier is an ORDINAL over a common-noun head.

    `the second group` partitions a population the document already
    introduced; it does not constitute a new bounded actor the way
    `the engineering group` does. The distinction is structural: spaCy tags
    `second`/`2nd` ADJ but `engineering` NOUN, so no head-noun list is
    needed and the rule generalizes to `the third cohort`, `the latter
    case`, and anything else of that shape.
    """
    if not _is_definite(target):
        return None
    toks = [t for t in (tokens or []) if t.get("pos") not in {"PUNCT", "SPACE"}]
    if toks:
        if any(t.get("pos") == "PROPN" for t in toks):
            return None                    # an identity anchor outranks this
        if toks[-1].get("pos") not in {"NOUN"}:
            return None
        mods = toks[1:-1] if len(toks) > 2 else toks[:-1]
        for m in mods:
            w = (m.get("lemma") or m["text"]).lower()
            if w in _ORDINAL or _ORDINAL_NUMERIC.match(m["text"]):
                return m["text"]
        return None
    words = _content(target)
    for w in words[:-1]:
        if w in _ORDINAL or _ORDINAL_NUMERIC.match(w):
            return w
    return None

_NOMINALIZATION = {
    "failure": ("fail", "failed", "fails"),
    "stoppage": ("stop", "stopped", "stops"),
    "outage": ("outage", "went down"),
    "migration": ("migrate", "migrated"),
    "deployment": ("deploy", "deployed"),
    "restart": ("restart", "restarted"),
}


@dataclass(frozen=True)
class DiscourseResult:
    basis: ReferenceBasis
    resolves_to: str | None = None
    evidence: tuple[str, ...] = ()
    candidates: tuple[str, ...] = ()
    contract: str = DISCOURSE_CONTRACT


def _content(phrase: str) -> list[str]:
    return [w for w in re.findall(r"[A-Za-z0-9][A-Za-z0-9\-]*", phrase.lower())
            if w not in _STOP]


def _is_definite(surface: str) -> bool:
    return surface.lower().startswith(_DET)


def _head(surface: str) -> str:
    c = _content(surface)
    return c[-1] if c else ""


def _np_candidates(prior: list[str], syntax: list[dict] | None,
                   target_head: str) -> list[str]:
    """E4 candidate generation over BOUNDED syntactic nominals.

    E4 BOUNDARY REPAIR: the previous regex allowed spaces inside its
    non-greedy span, so it crossed verbs and clause boundaries hunting for
    the head word. On a real document `the second group` "resolved" to
    `'recurring methodological issue is that sleep restriction studies
    often compare group'` — a fabricated antecedent, and the confident-wrong
    failure mode this gate forbids.

    Candidates are now spaCy noun chunks: one bounded NP each, no finite
    verb inside by construction, no clause crossing. The regex survives
    only as a TIGHT diagnostic fallback when syntax is absent — never as
    the authority.
    """
    out: list[str] = []
    if syntax:
        for sent, sx in zip(prior, syntax):
            for ch in sx.get("noun_chunks", []):
                text = sent[ch["char_start"]:ch["char_end"]]
                toks = [t for t in sx.get("tokens", [])
                        if t.get("char_start") is not None
                        and t["char_start"] >= ch["char_start"]
                        and t["char_end"] <= ch["char_end"]]
                if any(t.get("pos") in {"VERB", "AUX", "SCONJ"} for t in toks):
                    continue                      # never cross a clause
                if len(toks) > 6:
                    continue                      # bounded length
                if _content(text) and _content(text)[-1] == target_head:
                    out.append(text)
        return out
    # fallback: at most three tokens, no interior verb possible
    for sent in prior:
        m = re.search(rf"\b(?:a|an|the)\s+((?:[a-z]+\s+){{0,2}}{re.escape(target_head)})\b",
                      sent.lower())
        if m:
            out.append(m.group(1))
    return out


def resolve(target: str, context: list[str], *,
            admitted_anchors: list[tuple[str, str]] | None = None,
            syntax: list[dict] | None = None,
            target_tokens: list[dict] | None = None,
            ) -> DiscourseResult:
    """Classify one LOCAL_REFERENCE mention from its discourse.

    `context` is the ordered sentences up to AND INCLUDING the target's
    sentence. `admitted_anchors` are `(surface, core_type)` pairs already
    admitted in this document.
    """
    pairs = list(admitted_anchors or [])
    anchors = [a for a, _ in pairs]
    prior = context[:-1] if len(context) > 1 else []
    prior_text = " ".join(prior)
    target_head = _head(target)
    ev: list[str] = []

    if not _is_definite(target):
        return DiscourseResult(ReferenceBasis.EXTERNAL_UNRESOLVED,
                               evidence=("no definite/demonstrative determiner",))

    # ---- E3: the target's own words name an anchor already established ----
    # KNOWN LIMITATION (ledger row 69): resolves on ANY shared content word,
    # which is lexical relatedness, not identity. Fixed on
    # candidate/rescue-discourse-v1-failed; not promoted.
    tw = set(_content(target))
    named = [a for a in anchors if tw & set(_content(a))]
    if len(named) == 1:
        return DiscourseResult(ReferenceBasis.ANTECEDENT_RESOLVED, named[0],
                               ("E3 repeated named anchor",), tuple(named))
    if len(named) > 1:
        return DiscourseResult(ReferenceBasis.AMBIGUOUS, None,
                               ("E3 multiple named anchors match",), tuple(named))

    # ---- E4b: type-noun ANAPHORA — NOT IN THE LIVE V2 COMPOSITION --------
    # Row 70. E4b is retained, its input representation is correct, and its
    # tests are COMPONENT qualification only. It is not invoked by
    # admission-harbor-v2: "exactly one candidate + compatible type" proved
    # insufficient evidence of identity — with the wiring fixed it resolved
    # `vision system` -> `Siemens PLCs`, both Technology, wrong referent.
    # Type compatibility cannot separate two same-typed co-occurring
    # entities. If type-noun anaphora is later needed it must earn its own
    # qualification gate; this is an explicit exclusion, not dormancy.
    # exact-one type match is NECESSARY SUPPORTING evidence, never SUFFICIENT
    # identity evidence. "Acme Systems negotiated with the company" has exactly
    # one Organization and still must not resolve.
    type_of = _TYPE_NOUN.get(target_head)
    if type_of:
        # (2)(5) candidate must occur in a STRICTLY PRIOR sentence; a candidate
        # sharing the target's sentence is a co-participant, not an antecedent
        same_type = [a for a, ct in pairs
                     if ct == type_of and a.lower() in prior_text.lower()]
        if len(same_type) > 1:
            return DiscourseResult(ReferenceBasis.AMBIGUOUS, None,
                                   (f"E4b multiple admitted {type_of} anchors",),
                                   tuple(same_type))
        if len(same_type) == 1:
            # (6) a competing UNNAMED party introduced before the target means
            # the definite may denote that party instead
            competing = []
            for sent in prior:
                low = sent.lower()
                for noun in set(_EXTERNAL_PARTY) | {target_head}:
                    for det in _INDEFINITE:
                        if re.search(rf"\b{det}\s+(?:[a-z]+\s+)?{re.escape(noun)}\b", low):
                            competing.append(f"{det} {noun}")
            if competing:
                return DiscourseResult(
                    ReferenceBasis.AMBIGUOUS, None,
                    ("E4b competing unnamed party introduced before the target: "
                     f"{sorted(set(competing))[0]!r}",),
                    tuple(same_type) + tuple(sorted(set(competing))))
            return DiscourseResult(ReferenceBasis.ANTECEDENT_RESOLVED, same_type[0],
                                   (f"E4b type-noun anaphora: '{target_head}' -> exactly one "
                                    f"admitted {type_of} in strictly prior discourse, "
                                    f"no competing unnamed party",),
                                   tuple(same_type))

    # ---- E4: exactly one compatible antecedent introduced earlier ----------
    # Compatible = a prior noun phrase sharing the target's HEAD, or a prior
    # anchor whose sentence also introduced the head. Head identity only —
    # never "nearest noun", never type similarity.
    compat: list[str] = []
    for sent in prior:
        low = sent.lower()
        if target_head and target_head in _content(sent):
            for a in anchors:
                if a.lower() in low and a not in compat:
                    compat.append(a)
    # Head-sharing candidates are NOT type-filtered: sharing the target's
    # lexical head IS the positive evidence, and it stands without type
    # support (`patient portal` -> `careconnect portal`).
    for cand in _np_candidates(prior, syntax[:len(prior)] if syntax else None, target_head):
        # a first-mention target is its OWN first occurrence, not its
        # antecedent — self-match would make every introduced participant
        # look anaphoric (fixture ctx-04)
        if cand not in compat and _content(cand) != _content(target):
            compat.append(cand)
    if len(compat) == 1:
        return DiscourseResult(ReferenceBasis.ANTECEDENT_RESOLVED, compat[0],
                               ("E4 exactly one compatible local antecedent",),
                               tuple(compat))
    if len(compat) > 1:
        return DiscourseResult(ReferenceBasis.AMBIGUOUS, None,
                               ("E4 multiple compatible antecedents",), tuple(compat))

    # ---- E5: event nominalization whose source event the document states ---
    verbs = _NOMINALIZATION.get(target_head, ())
    if verbs:
        hits = [s for s in prior if any(re.search(rf"\b{re.escape(v)}\b", s.lower())
                                        for v in verbs)]
        if len(hits) == 1:
            return DiscourseResult(ReferenceBasis.DOCUMENT_CONSTITUTED, None,
                                   ("E5 nominalization of an event stated in this document",))
        if len(hits) > 1:
            return DiscourseResult(ReferenceBasis.AMBIGUOUS, None,
                                   ("E5 multiple candidate source events",))

    # ---- SET-PARTITION guard, BEFORE E6 ------------------------------------
    # E6 legitimately serves `the engineering group` / `the analytics team`
    # / `the review board`, so it is guarded rather than weakened. An ordinal
    # modifier IS discriminating but is NOT identity-bearing.
    ordinal = _is_ordinal_partition(target, target_tokens)
    if ordinal:
        return DiscourseResult(
            ReferenceBasis.AMBIGUOUS, None,
            (f"ordinal_set_partition: {ordinal!r} partitions a population the "
             f"document already introduced; it does not constitute a new "
             f"bounded actor. No partition was deterministically recoverable.",))

    # ---- E6: bounded discourse participant (REVISION 3a) -------------------
    if target_head in _EXTERNAL_PARTY:
        return DiscourseResult(
            ReferenceBasis.EXTERNAL_UNRESOLVED, None,
            (f"'{target_head}' denotes a party existing independently of this "
             "document; no named anchor resolved it",))
    if target_head in GENERIC_HEAD:
        return DiscourseResult(
            ReferenceBasis.EXTERNAL_UNRESOLVED, None,
            (f"generic head '{target_head}' cannot constitute a bounded "
             "participant; repetition of a category is not a referent",))
    # Requires BOTH recurrence AND a discriminating modifier. Recurrence alone
    # is forbidden evidence (REVISION 2); a bare repeated noun stays unresolved.
    if len(_content(target)) < 2:
        return DiscourseResult(
            ReferenceBasis.EXTERNAL_UNRESOLVED, None,
            ("bare head with no discriminating modifier",))
    later = [x for x in context if target.lower() in x.lower()]
    head_again = [x for x in context
                  if target_head and target_head in _content(x)
                  and any(d in x.lower() for d in _DET)]
    if len(later) > 1 or len(head_again) > 1:
        return DiscourseResult(
            ReferenceBasis.DOCUMENT_CONSTITUTED, None,
            ("E6 recurs as the same bounded participant AND carries a "
             "discriminating modifier",))

    # ---- default: a particular external referent, identity withheld -------
    return DiscourseResult(ReferenceBasis.EXTERNAL_UNRESOLVED, None,
                           ("no antecedent, no constituting event, "
                            "no repeated bounded reference",))
