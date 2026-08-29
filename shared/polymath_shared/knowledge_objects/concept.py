"""CONCEPT artifact compiler — grounded interpretations, never facts.

Compiles conceptual evidence into ConceptArtifacts:
  name / description / domain / supporting_sources / related_entities

Signals: "X is/are defined as Y", "X means Y", copula definitions
("A threat model describes assumptions..."), principle/framework
lexicon hits. Concepts are GROUNDED INTERPRETATIONS — they never
assert universal facts and never become CanonicalFacts.
"""
from __future__ import annotations

import re

from polymath_shared.knowledge_objects.knowledge_artifact import (
    KnowledgeArtifact, finalize)

_DEFINE_PATTERNS = (
    re.compile(r"(?i)^(?P<name>[^.;]{3,60}?)\s+(?:is|are)\s+"
               r"(?:often\s+|commonly\s+)?(?:described|defined)\s+as\s+"
               r"(?P<desc>[^.;]{10,200})"),
    re.compile(r"(?i)^(?P<name>[^.;]{3,60}?)\s+(?:is|are)\s+defined\s+as\s+"
               r"(?P<desc>[^.;]{10,200})"),
    re.compile(r"(?i)^(?P<name>[^.;]{3,60}?)\s+means\s+(?P<desc>[^.;]{10,200})"),
    re.compile(r"(?i)^(?P<name>[^.;]{3,60}?)\s+describes\s+"
               r"(?P<desc>[^.;]{10,200})"),
    re.compile(r"(?i)(?:the\s+)?(?:term\s+)?[\"']?(?P<name>model|threat "
               r"model|hook)[\"']?\s+(?:in |refers to)", re.I),
    # TRANSCRIPT-REGISTER-V1: the docstring has always claimed copula
    # definitions as a signal; these implement it for the registers
    # real technical transcripts use. Name guards (_bad_name, article
    # rules below) keep status statements and pronoun subjects out.
    #   "torch ... stands for pytorch"
    re.compile(r"(?i)^(?P<name>[^.;,]{2,60}?)\s+stands\s+for\s+"
               r"(?P<desc>[^.;]{6,200})"),
    #   "Fine-tuning is adjusting a base model's weights ..."
    #   (nominal subject + copula + gerund/process complement; the
    #   negative lookahead keeps article/demonstrative subjects out,
    #   and compile_concepts additionally requires the subject's head
    #   noun to be a NOMINALIZATION — spoken futures/progressives
    #   ("Age is going to be 28…", "Your trees are blocking…") are
    #   statements, not definitions)
    (_GERUND_COPULA := re.compile(
        r"(?i)^(?P<name>(?!(?:a|an|the|this|that|these|those|it|"
        r"there)\b)[^.;,]{3,60}?)\s+(?:is|are)\s+"
        r"(?P<desc>(?:the\s+(?:process|act|practice)\s+of\s+"
        r"[^.;]{6,200}|\w+ing\b\s[^.;]{6,200}))")),
    #   "Unsloth, which is an open source library to fine-tune ..."
    #   (capitalized-run appositive: continuation words must also be
    #   capitalized so the subject clause "We used Unsloth" never
    #   swallows the name)
    re.compile(r"(?P<name>[A-Z][\w'-]*(?:\s+[A-Z][\w'-]*){0,3}),\s+"
               r"which\s+(?:is|are)\s+(?:a|an|the)?\s*"
               r"(?P<desc>[^.;]{10,200})"),
    #   "A vector database is a system that stores embeddings ..."
    re.compile(r"(?i)^(?P<name>[^.;,]{3,60}?)\s+(?:is|are)\s+"
               r"(?:a|an)\s+(?P<desc>[^.;]{10,200})"),
)

#: Subjects that make a copula sentence a STATEMENT, not a definition.
_BAD_NAME_HEADS = frozenset(
    "this that these those it there he she we i you they which what who "
    "everything something anything nothing one here now today it's that's "
    "there's and but so okay ok well because also then".split())

#: A candidate name containing its own copula/relative clause is a
#: sentence fragment, not a nominal ("the main thing is torch which").
_NAME_CLAUSE = re.compile(r"(?i)\b(is|are|was|were|which|that)\b")

#: List/section narration is not a concept name ("Number two is a
#: CRM…", "Part three is writing ads…").
_ENUMERATION_NAME = re.compile(
    r"(?i)^(?:number|part|step|section|chapter|tip|rule|point)\b")


def _bad_name(name: str) -> bool:
    words = name.lower().split()
    if not words or words[0] in _BAD_NAME_HEADS:
        return True
    if _ENUMERATION_NAME.match(name):
        return True
    return bool(_NAME_CLAUSE.search(name))


#: Nominalization suffixes: definitional subjects of gerund-copula
#: sentences are process/abstraction nouns ("Fine-tuning", "canonical-
#: ization", "governance"). "Age", "Your trees", "$1 ROAS" are not.
_NOMINAL_SUFFIX = re.compile(
    r"(?i)(?:ing|ion|ment|ness|ity|ance|ence|ism|ics)$")


def _nominal_head(name: str) -> bool:
    words = name.split()
    return bool(words) and bool(_NOMINAL_SUFFIX.search(words[-1]))

_MAX_NAME = 8      # words
_MAX_DESC = 40


def _clean_name(name: str) -> str:
    """Strip markdown-heading glue and collapse immediate repeats
    ('# Notes on X X' -> 'X') so concept names are clean nouns."""
    n = re.sub(r"^#+\s*", "", (name or "").strip())
    words = n.split()
    out: list[str] = []
    for w in words:
        if out and w.lower() == out[-1].lower():
            continue
        out.append(w)
    return " ".join(out)


def count_opportunities(sentences: list[str]) -> int:
    """SEMANTIC-LANE-LIVENESS-V1: definitional sentences the compiler
    SEES, before the max_concepts cap. Diagnostic only; uses the same
    patterns compile_concepts evaluates.

    Because the cap is 10/document, comparing this to `accepted` is the
    only way to know whether the cap is truncating real recall.
    """
    n = 0
    for s in sentences:
        for pat in _DEFINE_PATTERNS:
            if pat.search(s):
                n += 1
                break
    return n


def compile_concepts(*, document_id: str, corpus_id: str,
                     sentences: list[str],
                     domain: str = "general",
                     admitted_entities: list[str] | None = None,
                     source_chunk_ids: list[str] | None = None,
                     max_concepts: int = 10) -> list[dict]:
    """Return ConceptArtifact dicts for definitional sentences."""
    admitted = set(admitted_entities or [])
    out: list[dict] = []
    seen_names: set[str] = set()
    for s in sentences:
        for pat in _DEFINE_PATTERNS:
            m = pat.search(s)
            if not m:
                continue
            name = m.group("name").strip(" \"'").strip()
            name = _clean_name(name)
            parts = name.split()
            while parts and parts[0].lower() in ("the", "a", "an"):
                parts = parts[1:]
                name = " ".join(parts)
            # the refers-to pattern has no desc group (latent
            # IndexError, reachable from real transcript text — found
            # by the 2026-08-26 candidate sweep); the sentence itself
            # is the description then
            desc = (m.groupdict().get("desc") or s).strip()
            if not name or len(name.split()) > _MAX_NAME:
                continue
            if _bad_name(name):
                continue  # pronoun/demonstrative subject = statement
            if pat is _GERUND_COPULA and not _nominal_head(name):
                continue  # "Age is going to be 28…" narrates; only a
                # nominalization subject makes gerund-copula a definition
            key = name.lower()
            if key in seen_names:
                continue
            seen_names.add(key)
            related = [e for e in sorted(admitted, key=len, reverse=True)
                       if e.lower() in s.lower()][:6]
            artifact = KnowledgeArtifact(
                artifact_id="pending",
                artifact_type="CONCEPT",
                document_id=document_id,
                corpus_id=corpus_id,
                source_chunk_ids=list(source_chunk_ids or []),
                confidence=0.9,
            )
            body = {
                "name": name,
                "description": desc[:400],
                "domain": domain,
                "related_entities": related,
                "source_sentence": s[:300],
            }
            artifact = finalize(artifact, body)
            row = artifact.model_dump()
            row.update(body)
            out.append(row)
            break
        # max_concepts <= 0 means NO ceiling (CONCEPT_CONTRACT_V2 reads
        # every sentence). A positive value keeps the frozen v1
        # behaviour: stop scanning as soon as the cap is reached.
        if max_concepts > 0 and len(out) >= max_concepts:
            break
    return out


# ======================================================================
# CONCEPT-INVENTORY-V2 (P4, 2026-08-28)
#
# `max_concepts=10` was a STORAGE ceiling, not a summary limit.
# compile_concepts stops scanning sentences the moment it has ten, so a
# 400-page book stored ten concepts and discarded the rest unread.
#
# MEASURED on the live corpus: 12 of 13 documents held EXACTLY 10
# concepts — pinned by construction — and the concept lane recorded
# 2,210 opportunities against 120 accepted (5.4%).
#
# Effects isolated on all 18 documents, rebuilt from the retained spool:
#
#   A  v1 text, cap 10       121 concepts   (what production holds)
#   B  v1 text, no cap       975 concepts   <- P4 alone, x8.1
#   C  v2 text, cap 10       122 concepts   <- P2 alone, x1.0
#   D  v2 text, no cap     1,236 concepts   <- P2+P4, x10.2
#
# Read C before concluding P2 did nothing: with the cap in place every
# document is already pinned at ten, so structure preservation CANNOT
# show up. P2's real contribution is B -> D, +261 concepts (+27%), and
# it was invisible while the ceiling bound.
#
# But lifting the ceiling alone is wrong. Of those 1,236, measurement
# showed ~28% were not concepts at all: sentence fragments ("exercises
# as a", "found in victim environments,"), bare generics
# ("information", "command"), participles ("touched", "running"). The
# cap had been acting as an accidental quality filter, so removing it
# without replacing that job would flood the inventory with exactly the
# noun-phrase junk this phase forbids.
#
# So the ceiling is replaced by ADMISSION, reusing the doctrine and the
# very lists entity_admission already uses for reference identity —
# GENERIC_HEAD, WEAK_MODIFIERS, DEICTIC_MODIFIERS — rather than
# inventing a parallel vocabulary. 1,236 -> 860 admitted.
#
# The top-N does not disappear; it stops being a storage decision.
# Every admitted concept carries `summary_rank`, so a caller that wants
# ten for a routing card takes the first ten and the other 850 stay
# durable and retrievable.
#
# V1 is untouched: compile_concepts still caps at 10.

from polymath_shared.entity_admission import (  # noqa: E402
    DEICTIC_MODIFIERS, GENERIC_HEAD, WEAK_MODIFIERS)

CONCEPT_CONTRACT_V1 = "concept-artifact-v1"
CONCEPT_CONTRACT_V2 = "concept-inventory-v2"

#: Default top-N for a routing card / document summary. A PRESENTATION
#: limit only — it never decides what is stored.
SUMMARY_TOP_N = 10

#: Function words that cannot open or close a nominal concept name.
#: Closed classes only: determiners, quantifiers, prepositions,
#: conjunctions, infinitival "to", positional deictics.
_EDGE_FUNCTION = frozenset("""
a an the this that these those and or but nor so yet for to of in on at
with from by about into onto over under between during through across
against within without upon per via as if when while because although
than then there here its his her their our your my
all any some each every both either neither no most many much few
several other another such next previous following above below same
""".split())

#: Discourse nouns with no concept identity of their own.
#: entity_admission.GENERIC_HEAD already covers the infrastructure
#: nouns; these are the ones the measurement surfaced.
_GENERIC_EXTRA = frozenset("""
information command id thing things way ways part parts point points
kind kinds type types area areas case cases example examples number
result results item items step steps issue issues topic topics
""".split())

_GENERIC_NAME = GENERIC_HEAD | _GENERIC_EXTRA

#: A bare participle is not a nominal ("touched", "running").
_BARE_PARTICIPLE = re.compile(r"(?i)^\w+(?:ing|ed)$")

#: A finite verb inside the name means a sentence fragment was captured.
_FINITE_VERB = frozenset("""
is are was were be been being am has have had do does did can could
will would may might must shall should make makes made use uses used
provide provides include includes allow allows require requires
""".split())

#: Subordinators and comparatives that cannot appear INSIDE a nominal.
#: "of", "in" and "for" deliberately are not here — they are ordinary
#: inside a noun phrase ("chain of custody", "results of host queries").
_INTERNAL_SUBORDINATOR = frozenset(
    "as if when while because although though than whether unless "
    "until since where whereas".split())

#: Punctuation that only appears when the extractor sliced mid-clause.
_FRAGMENT_PUNCT = re.compile(r"[,;:&]|[)\]}](?![\w])|[\"“”]|\((?![^)]*\))")


def concept_name_admissible(name: str) -> tuple[bool, str]:
    """Does `name` carry durable concept identity?

    Returns (admitted, reason). Deterministic, no model. Every rule is a
    CLOSED CLASS test — if this ever needs a domain word to work, the
    inventory has stopped being governed by grammar and started being
    governed by a keyword list.
    """
    text = (name or "").strip()
    if not text:
        return False, "empty"
    tokens = text.split()
    low = [t.lower().strip(".,;:!?") for t in tokens]

    if _FRAGMENT_PUNCT.search(text):
        return False, "punctuation_fragment"
    if low[0] in _EDGE_FUNCTION:
        return False, "opens_with_function_word"
    if low[-1] in _EDGE_FUNCTION:
        return False, "ends_with_function_word"
    if any(t in _FINITE_VERB for t in low):
        return False, "contains_finite_verb"
    if any(t in _INTERNAL_SUBORDINATOR for t in low[1:-1]):
        return False, "contains_subordinate_clause"
    if not re.search(r"[A-Za-z]", text):
        return False, "no_letters"

    if len(tokens) == 1:
        if _BARE_PARTICIPLE.match(text):
            return False, "bare_participle"
        if low[0] in _GENERIC_NAME:
            return False, "bare_generic_noun"
        return True, "admitted"

    # Multi-token: a generic head is fine when a discriminative modifier
    # carries the identity ("incident response program"), not when every
    # modifier is weak or deictic ("next example", "involved system").
    discriminative = [t for t in low[:-1]
                      if t not in _EDGE_FUNCTION
                      and t not in _GENERIC_NAME
                      and t not in WEAK_MODIFIERS
                      and t not in DEICTIC_MODIFIERS]
    if low[-1] in _GENERIC_NAME and not discriminative:
        return False, "generic_head_no_modifier"
    return True, "admitted"


def compile_concept_inventory(*, document_id: str, corpus_id: str,
                              sentences: list[str],
                              domain: str = "general",
                              admitted_entities: list[str] | None = None,
                              source_chunk_ids: list[str] | None = None,
                              summary_top_n: int = SUMMARY_TOP_N) -> list[dict]:
    """CONCEPT_CONTRACT_V2 — the durable inventory.

    Reads EVERY sentence (no early stop) and stores every concept whose
    name passes admission. `summary_rank` is assigned in document order,
    so a top-N summary is a slice of the inventory rather than a
    different, lossier extraction.
    """
    rows = compile_concepts(
        document_id=document_id, corpus_id=corpus_id, sentences=sentences,
        domain=domain, admitted_entities=admitted_entities,
        source_chunk_ids=source_chunk_ids,
        max_concepts=0)                     # 0 = no ceiling, see below

    out: list[dict] = []
    for row in rows:
        ok, reason = concept_name_admissible(row["name"])
        if not ok:
            continue
        row = dict(row)
        row["provenance"] = {
            "contract": CONCEPT_CONTRACT_V2,
            "summary_rank": len(out),
            "in_summary": len(out) < summary_top_n,
            "admission": reason,
        }
        out.append(row)
    return out
