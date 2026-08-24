"""PROCEDURE artifact compiler — deterministic workflow extraction.

Compiles procedural evidence (numbered steps, transcript stamps,
imperative verbs: install/configure/create/open/select/run/deploy/
setup, first/next/finally) into a structured ProcedureArtifact.

Consumes ONLY accepted inputs: chunk texts + admitted entity surfaces
+ the router's knowledge profile. Never creates facts, never guesses.
Fail-closed: fewer than MIN_STEPS imperative sentences -> None.
"""
from __future__ import annotations

import re

from polymath_shared.knowledge_objects.knowledge_artifact import (
    KnowledgeArtifact, finalize)

MIN_STEPS = 2

#: Imperative openers that begin a step sentence. Deterministic list;
#: additions require a regression fixture.
_IMPERATIVE = (
    "install", "configure", "create", "open", "select", "run", "deploy",
    "setup", "set up", "add", "go to", "navigate", "paste", "click",
    "enable", "choose", "make sure", "sign in", "log in",
    "establish", "assign", "verify", "review", "define")

_STEP_MARK = re.compile(r"(?im)^\s*(?:step\s*\d+[:.)]?\s*|\d+[.)]\s+)")
_TRANSCRIPT_STAMP = re.compile(r"\*\*\[\d+:\d+\]\*\*\s*")
_SEQUENCE = re.compile(r"\b(first|next|then|finally|now)\b[, :]?",
                       re.IGNORECASE)


def _clean(line: str) -> str:
    line = _TRANSCRIPT_STAMP.sub("", line)
    return line.strip(" *\t")


def _is_imperative(sentence: str) -> bool:
    sentence = _SEQ_START.sub("", sentence)
    first = sentence.split()
    if not first:
        return False
    head = first[0].lower().strip(",")
    if head in _IMPERATIVE:
        return True
    # two-word imperatives ("Set up", "Go to")
    if len(first) > 1 and f"{head} {first[1].lower().strip(',')}" \
            .strip(",") in _IMPERATIVE:
        return True
    return False


_SEQ_START = re.compile(r"(?i)^\s*(first|next|then|finally|now)\b[, :]?\s*")
_STEP_INLINE = re.compile(r"(?i)\bstep\s*\d+\s*[:.)]\s*")


def split_step_sentences(text: str) -> list[str]:
    """Sentence segmentation tolerant of transcript stamps/step marks
    whether they open lines OR appear mid-line between sentences."""
    text = _TRANSCRIPT_STAMP.sub(" ", text)
    text = _STEP_MARK.sub("\n", text)
    text = _STEP_INLINE.sub("\n", text)
    out = []
    for para in text.split("\n"):
        for s in re.split(r"(?<=[.!?])\s+", para):
            s = s.strip()
            if len(s) > 8:
                out.append(s)
    return out


def compile_procedure(*, document_id: str, corpus_id: str,
                      text: str, title: str = "",
                      admitted_entities: list[str] | None = None,
                      source_chunk_ids: list[str] | None = None,
                      min_steps: int = MIN_STEPS) -> dict | None:
    """Return ProcedureArtifact dict or None when not procedural enough."""
    sentences = split_step_sentences(text)
    steps = [s for s in sentences if _is_imperative(s)]
    if len(steps) < min_steps:
        return None

    admitted = set(admitted_entities or [])
    tools: list[str] = []
    goal = steps[0]
    for e in sorted(admitted, key=len, reverse=True):
        if any(e.lower() in s.lower() for s in steps) and \
                e.lower() not in [t.lower() for t in tools]:
            tools.append(e)

    artifact = KnowledgeArtifact(
        artifact_id="pending",
        artifact_type="PROCEDURE",
        document_id=document_id,
        corpus_id=corpus_id,
        source_chunk_ids=list(source_chunk_ids or []),
        confidence=min(1.0, 0.6 + 0.05 * len(steps)),
    )
    body = {
        "title": title or f"Procedure ({len(steps)} steps)",
        "goal": goal.rstrip("."),
        "tools": tools,
        "steps": steps,
    }
    artifact = finalize(artifact, body)
    out = artifact.model_dump()
    out.update(body)
    return out
