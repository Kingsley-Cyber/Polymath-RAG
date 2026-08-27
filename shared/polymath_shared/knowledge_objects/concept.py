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
        if len(out) >= max_concepts:
            break
    return out
