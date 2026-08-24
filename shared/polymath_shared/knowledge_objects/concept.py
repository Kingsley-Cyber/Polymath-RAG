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
)

_MAX_NAME = 8      # words
_MAX_DESC = 40


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
            parts = name.split()
            while parts and parts[0].lower() in ("the", "a", "an"):
                parts = parts[1:]
                name = " ".join(parts)
            desc = m.group("desc").strip()
            if not name or len(name.split()) > _MAX_NAME:
                continue
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
