"""UD-derived syntactic record for the compiler's orientation layer.

spaCy (en_core_web_sm, version-pinned in the extraction manifest) is the
default parser. When it is unavailable a DETERMINISTIC fallback (Q1-R,
pack v1.1.0) recognizes the two passive constructions realistic prose
depends on — "X is V-ed by Y" (agent passive) and "X is V-ed for Y"
(purpose passive: "Qdrant is used for vector retrieval" -> agent =
purpose NP) — so the compiler's existing voice normalization can orient
the fact canonically. Everything else returns None and the compiler
marks orientation weak (surface order only) — an explicit degradation,
never a silent guess.
"""
from __future__ import annotations

import os
import re
from typing import Optional

_PARSER_NAME = "spacy"
_PARSER_MODEL = "en_core_web_sm"

_DIAG_ENV = "POLYMATH_SYNTAX_REGEX_DIAGNOSTIC"
_DET_PARSER_NAME = "deterministic-syntax"
_DET_PARSER_VERSION = "v1.1.0"

_PASSIVE_BY_RE = re.compile(
    r"^(.{2,}?)\s+(?:is|are|was|were|been|being)\s+(?:still|also|often|commonly|typically|usually|generally|now|already|always)?\s*"
    r"([a-z]+(?:ed|en|d)|built|made|kept|held|used|run|done|written)\s+by\s+((?:.{2,}?))(?:,?\s+and\s+.+)?$",
    re.IGNORECASE,
)
_PASSIVE_FOR_RE = re.compile(
    r"^(.{2,}?)\s+(?:is|are|was|were|been|being)\s+(?:still|also|often|commonly|typically|usually|generally|now|already|always)?\s*"
    r"(used|implemented|measured|built|designed|written|employed|applied|run|powered|made)\s+(?:for|with|by)\s+((?:.{2,}?))(?:,?\s+and\s+.+)?$",
    re.IGNORECASE,
)

_nlp = None


def _get_nlp():
    global _nlp
    if _nlp is None:
        import spacy

        _nlp = spacy.load(_PARSER_MODEL)
    return _nlp


def parser_identity() -> tuple[str, str]:
    try:
        _get_nlp()
    except Exception:
        if os.environ.get(_DIAG_ENV) == "1":
            return _DET_PARSER_NAME, _DET_PARSER_VERSION
        return "none", "predicate-v2-no-parse"
    return _PARSER_NAME, _PARSER_MODEL


def _passive_record(subject: str, verb: str, complement: str) -> dict:
    """Deterministic passive syntactic record (Q1-R v1.1.0).

    The surface subject is the patient; the by/for complement is the
    agent. The compiler's _oriented_pair then validates the (agent,
    patient) signature and inverts the surface order — semantic roles,
    not surface order."""
    subject = subject.strip().rstrip(".,;:!?")
    complement = complement.strip().rstrip(".,;:!?")
    return {
        "voice": "passive",
        "subject": {"token_text": subject, "head_text": subject},
        "agent": {"token_text": complement, "head_text": complement},
        "object": {"token_text": complement, "head_text": complement},
        "temporal": {},
        "weak": True,
        "roleset_known": False,
        "parser": "deterministic-syntax-v1.1.0",
    }


def parse_sentence(text: str) -> Optional[dict]:
    """Parse one sentence into the syntactic record the compiler consumes.

    Shape:
      {
        "voice": "active" | "passive" | "unknown",
        "subject": {"token_text", "head_text", "entity_id"} | None,
        "agent":   {"token_text", "head_text", "entity_id"} | None,   # obl:agent
        "object":  {"token_text", "head_text", "entity_id"} | None,
        "temporal": {"valid_from", "valid_until"},
        "weak": bool,
      }

    `entity_id` fields are filled by the candidate builder when a span's
    head token coincides with a pass-1 entity span. The adapter itself
    only reports structure.
    """
    try:
        nlp = _get_nlp()
    except Exception:
        nlp = None

    if nlp is None:
        # PREDICATE-COMPILER-V2 (owner decision: regex passive fallback is
        # REMOVE_FROM_PRODUCTION). A parser failure reduces recall; it
        # never fabricates structure. The frozen regex parser survives
        # only behind the diagnostic flag for offline analysis.
        if os.environ.get(_DIAG_ENV) != "1":
            return None
        match = _PASSIVE_BY_RE.match(text.strip())
        if match:
            return _passive_record(match.group(1), match.group(2), match.group(3))
        match = _PASSIVE_FOR_RE.match(text.strip())
        if match:
            return _passive_record(match.group(1), match.group(2), match.group(3))
        return None

    doc = nlp(text)
    if not doc:
        return None

    record: dict = {"voice": "active", "weak": False, "temporal": {}}

    # aux:pass -> passive voice; nsubj:pass is the patient subject.
    if any(tok.dep_ == "aux:pass" for tok in doc):
        record["voice"] = "passive"

    for tok in doc:
        if tok.dep_ in ("nsubj", "nsubj:pass"):
            record["subject"] = {"token_text": tok.text, "head_text": tok.head.text}
        elif tok.dep_ == "obl:agent":
            record["agent"] = {"token_text": tok.text, "head_text": tok.head.text}
        elif tok.dep_ in ("obj", "iobj", "dobj", "obl") and tok.dep_ != "obl:agent":
            record.setdefault("object", {"token_text": tok.text, "head_text": tok.head.text})

    # ARGM-TMP style temporal detection: dates/years as determiners for the
    # temporal qualifier (docx §11.2 worked example). Regex-only, no model.
    years = re.findall(r"\b(1[89]\d{2}|20\d{2})\b", text)
    if years:
        record["temporal"]["valid_from"] = years[0]

    return record
