"""UD-derived syntactic record for the compiler's orientation layer.

spaCy (en_core_web_sm, version-pinned in the extraction manifest) is the
default parser. When it is unavailable the adapter returns None and the
compiler marks orientation weak (surface order only) — an explicit
degradation, never a silent guess. The parser is deterministic given a
pinned model version + fixed tokenizer; it never selects predicates.
"""
from __future__ import annotations

from typing import Optional

_PARSER_NAME = "spacy"
_PARSER_MODEL = "en_core_web_sm"

_nlp = None


def _get_nlp():
    global _nlp
    if _nlp is None:
        import spacy

        _nlp = spacy.load(_PARSER_MODEL)
    return _nlp


def parser_identity() -> tuple[str, str]:
    return _PARSER_NAME, _PARSER_MODEL


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
    import re

    years = re.findall(r"\b(1[89]\d{2}|20\d{2})\b", text)
    if years:
        record["temporal"]["valid_from"] = years[0]

    return record
