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
    "establish", "assign", "verify", "review", "define",
    "isolate", "perform", "document", "preserve", "validate",
    "monitor", "update", "reinforce", "analyze")

_STEP_MARK = re.compile(r"(?im)^\s*(?:step\s*\d+[:.)]?\s*|\d+[.)]\s+)")
_TRANSCRIPT_STAMP = re.compile(r"\*\*\[\d+:\d+\]\*\*\s*")
_SEQUENCE = re.compile(r"\b(first|next|then|finally|now)\b[, :]?",
                       re.IGNORECASE)


def _clean(line: str) -> str:
    line = _TRANSCRIPT_STAMP.sub("", line)
    return line.strip(" *\t")


def _is_imperative(sentence: str) -> bool:
    sentence = _strip_leads(sentence)
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

#: TRANSCRIPT-REGISTER-V1: real spoken instructions arrive behind
#: conversational leads — "So click on the free notebook", "Okay, so
#: let's run the next cell", "Just paste in the name". The lead is
#: noise; the imperative underneath is the step. Stripping is
#: iterative ("Okay, so let's run…" → run) and deterministic. This is
#: DISCOVERY register handling: MIN_STEPS and every downstream gate
#: are unchanged, and procedures never become facts.
_CONVERSATIONAL_LEAD = re.compile(
    r"(?i)^\s*(?:(?:so|okay|ok|alright|and|but|just|now|then|next|first|"
    r"finally)(?:[, :]+|\s+)|let'?s\s+|let\s+us\s+)")


def _strip_leads(sentence: str) -> str:
    prev = None
    while prev != sentence:
        prev = sentence
        sentence = _CONVERSATIONAL_LEAD.sub("", sentence, count=1)
    return sentence
_STEP_INLINE = re.compile(r"(?i)\bstep\s*(?:\d+|one|two|three|four|five|six|seven|eight|nine|ten)\b\s*[:.)]?\s*")


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


def count_opportunities(text: str) -> int:
    """SEMANTIC-LANE-LIVENESS-V1: how many imperative step sentences the
    compiler SEES, before the MIN_STEPS gate. Purely diagnostic — it
    shares the compiler's own helpers so it can never drift from what
    compile_procedure actually evaluates, and it changes no semantics.

    Distinguishes "this document had no procedural evidence" (a correct
    zero) from "evidence existed and produced nothing" (a defect).
    """
    return sum(1 for s in split_step_sentences(text) if _is_imperative(s))


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


# ======================================================================
# PROCEDURE-ARTIFACT-V2 (P3, 2026-08-28)
#
# V1 emits at most ONE artifact per document, whose steps are whatever
# imperative sentences the whole document happens to contain. On
# sentinel_procedures.md — three plainly separate tasks — it produced a
# single artifact with 5 steps out of 20, and the goal "Select the key".
#
# MEASURED, two independent defects, neither of them granularity:
#
#   1. SENTENCE SHREDDING. split_step_sentences splits on EVERY newline,
#      so a hard-wrapped source line becomes two "sentences": "Select the
#      key" / "you intend to replace." Steps were being cut in half.
#      Wrapping is presentation, not structure.
#
#   2. WHITELIST RECALL. _is_imperative recognises a step only when its
#      verb appears in a hand-written list, so generate, revoke, detach,
#      attach, boot, capture, collect, record, notify, hand, confirm and
#      close were all invisible. 5 of 20 real steps were seen. A list of
#      open-class English verbs can never be completed, so growing it is
#      not a fix.
#
# V2 replaces the whitelist with a CLOSED-CLASS EXCLUSION, the same
# doctrine entity_admission uses for pronouns: enumerate the function
# words that can open a declarative — determiners, pronouns,
# prepositions, subordinators, auxiliaries, wh-words — and treat a
# sentence-initial word outside that closed set as a bare verb. The
# closed set is bounded by the language; the verb list was not. The v1
# whitelist is kept as a POSITIVE override, so it can only ever add.
#
# Granularity then falls out: the goal statements that mark each task
# ("To rotate an API credential, …") are exactly the sentences the
# detector declines to call steps.
#
# V1 is untouched and still reachable — compile_procedure, _is_imperative
# and split_step_sentences all behave exactly as before.

#: ARTIFACT-CONFIDENCE-V2 (P7, 2026-08-29). Confidence was
#: min(1.0, 0.6 + 0.05 * len(steps)) — length, not reliability. It
#: saturated at 1.0 for any procedure with 8+ steps, which under the v1
#: one-artifact-per-document contract meant nearly all of them (live:
#: 12 at 1.00, 1 at 0.85). Worse, ask.py ranked on it, so a longer
#: procedure beat a shorter one for being longer.
#:
#: There is no defensible deterministic reliability signal available
#: here: this compiler SELECTS verbatim source sentences, so every step
#: is exactly as reliable as the document it came from. So confidence is
#: declared a NON-SIGNAL — a fixed provenance-compatible value that
#: nothing ranks or admits on. It is not in the artifact body hash, so
#: this does not change artifact identity.
CONFIDENCE_CONTRACT = "artifact-confidence-v2"
DECLARED_NON_SIGNAL_CONFIDENCE = 1.0

PROCEDURE_CONTRACT_V1 = "procedure-artifact-v1"
PROCEDURE_CONTRACT_V2 = "procedure-artifact-v2"

#: Words that can open an English DECLARATIVE but can never be a bare
#: imperative verb. CLOSED CLASSES ONLY. If this set ever needs a domain
#: word to work, the rule has stopped being grammatical and become a
#: heuristic — that is the signal to reject the change, not extend it.
NON_VERB_OPENERS = frozenset("""
the a an this that these those each every some any no all both either
neither much many few several such another other
i you he she it we they me him her us them one ones
my your his its our their whose
there here
and but or nor so yet for
if when while because although though after before since unless until
whether than as whereas whenever wherever
in on at to with from by of about into onto over under between during
through across against within without upon per via
is are was were be been being am
has have had do does did
can could will would may might must shall should ought need
not never always often usually typically generally however therefore
thus hence moreover furthermore additionally finally meanwhile
who whom which what where why how
""".split())

_AUX = frozenset("""is are was were be been being am has have had do does
did can could will would may might must shall should""".split())

#: Suffixes that cannot end a bare (uninflected) English verb.
_NON_BARE = re.compile(
    r"(?i)(ing|ed|tion|sion|ment|ness|ity|ance|ence|ism|ist|ly|ous|ful|"
    r"able|ible|al|ive|est)$")

#: Bare verbs whose spelling trips _NON_BARE. Closed, and every entry is
#: a genuine irregular spelling rather than a domain term.
_BARE_EXCEPT = frozenset({
    "add", "read", "feed", "need", "seed", "speed", "record", "reload",
    "upload", "download", "hold", "build", "find", "send", "spend", "end",
    "extend", "attend", "append", "bind", "install", "call", "pull",
    "fill", "poll", "enable", "disable", "handle", "toggle", "sample",
    "scale", "compile", "assemble", "cancel", "label", "seal", "reveal",
    "detail", "email", "shed", "spread", "embed", "exceed", "proceed",
})

_FENCE = re.compile(r"(?s)```.*?```|~~~.*?~~~")
_HARD_LINE = re.compile(r"(?m)^\s*(?:[-*+]\s|\d+[.)]\s|#{1,6}\s|\|)")

#: "To rotate an API credential, open the credential console."
#: The clause before the comma is the GOAL; what follows is the first
#: step. V1 threw the whole sentence away, losing both.
_GOAL_MARKER = re.compile(
    r"(?i)^\s*(?:in order\s+)?to\s+(?P<goal>[a-z][^,]{3,90}?),\s*(?P<rest>\S.*)$")


def strip_non_prose(text: str) -> str:
    """Drop regions that are never procedural prose: fenced code,
    markdown headings, table rows.

    These are identifiable ONLY because CHUNK_CONTRACT_V2 preserves line
    structure. Under v1 chunk text a table row and a sentence were the
    same flat string, which is why `| Port | Service | Notes |` and
    `def isolate(host):` were being read as steps.
    """
    text = _FENCE.sub("\n", text)
    return "\n".join(
        line for line in text.split("\n")
        if not line.lstrip().startswith("#")
        and not line.lstrip().startswith("|"))


def unwrap_soft_lines(text: str) -> str:
    """Rejoin hard-wrapped prose. A newline is a SOFT wrap when the line
    it ends does not end a sentence and neither side opens a structural
    unit (list item, heading, table row, step mark). Everything else
    stays a real boundary.
    """
    lines = text.split("\n")
    out: list[str] = []
    for i, line in enumerate(lines):
        out.append(line)
        if i + 1 >= len(lines):
            continue
        nxt = lines[i + 1]
        soft = (line.strip() and nxt.strip()
                and not re.search(r"[.!?:;]\s*$", line)
                and not _HARD_LINE.match(line)
                and not _HARD_LINE.match(nxt)
                and not _STEP_MARK.match(nxt))
        out.append(" " if soft else "\n")
    return "".join(out)


def split_step_sentences_v2(text: str) -> list[str]:
    """Sentence segmentation that repairs soft wraps first.

    Same shape as v1 otherwise; v1 is left frozen because its output is
    pinned by the existing artifact fixtures.
    """
    text = _TRANSCRIPT_STAMP.sub(" ", unwrap_soft_lines(strip_non_prose(text)))
    text = _STEP_MARK.sub("\n", text)
    text = _STEP_INLINE.sub("\n", text)
    out: list[str] = []
    for para in text.split("\n"):
        for s in re.split(r"(?<=[.!?])\s+", para):
            s = s.strip()
            if len(s) > 8:
                out.append(s)
    return out


def is_imperative_v2(sentence: str,
                     admitted: frozenset[str] = frozenset()) -> bool:
    """True when `sentence` is an imperative instruction.

    `admitted` are admitted entity surfaces (lowercased) — the module's
    existing accepted input. An admitted entity opening a sentence is
    its SUBJECT, so the sentence is declarative: that single signal is
    what separates "Nessus scans network hosts" from "Scan the network".
    """
    s = _strip_leads(sentence).strip()
    if not s or s.endswith("?"):
        return False
    toks = re.findall(r"[A-Za-z][A-Za-z'-]*", s)
    if not toks:
        return False
    head = toks[0].lower()

    # POSITIVE OVERRIDE: the frozen v1 whitelist can only ever add.
    if head in _IMPERATIVE:
        return True
    if len(toks) > 1 and f"{head} {toks[1].lower()}" in _IMPERATIVE:
        return True

    if head in NON_VERB_OPENERS:
        return False
    if head in admitted:
        return False

    if len(toks) > 1:
        nxt = toks[1]
        if nxt.lower() in _AUX:                 # "Nessus was developed …"
            return False
        if nxt[:1].isupper():                   # "Dana Reyes, CISSP, …"
            return False
        if nxt.lower().endswith("ing"):         # "Port scanning is …"
            return False
        # third-person -s after a capitalised opener: "Nmap discovers …"
        if (toks[0][:1].isupper() and nxt.lower().endswith("s")
                and not nxt.lower().endswith("ss")
                and nxt.lower() not in NON_VERB_OPENERS):
            return False

    if _NON_BARE.search(head) and head not in _BARE_EXCEPT:
        return False
    if toks[0].isupper() and len(toks[0]) > 1:  # acronym / speaker label
        return False
    return True


def count_opportunities_v2(text: str,
                           admitted: frozenset[str] = frozenset()) -> int:
    """Diagnostic twin of count_opportunities for the v2 contract."""
    return sum(1 for s in split_step_sentences_v2(text)
               if is_imperative_v2(s, admitted))


def segment_tasks(text: str,
                  admitted: frozenset[str] = frozenset()) -> list[dict]:
    """Split `text` into LOCAL TASKS: (goal, ordered steps).

    Boundaries, in priority order:
      1. an explicit goal marker ("To rotate an API credential, …"),
         wherever it appears;
      2. a paragraph break — which exists in chunk text only because of
         CHUNK_CONTRACT_V2.

    Shadow-compared against DOCUMENT, SECTION and PARENT_NEIGHBOURHOOD
    segmentation on sentinel_procedures.md. DOCUMENT and
    PARENT_NEIGHBOURHOOD both collapse the three tasks into one;
    SECTION splits on headings and so merges the two tasks that share a
    section. Local task segmentation is the smallest unit that
    separates them without inventing boundaries inside a task.
    """
    tasks: list[dict] = []
    cur: dict | None = None

    def start(goal: str) -> dict:
        t = {"goal": goal, "steps": []}
        tasks.append(t)
        return t

    for block in re.split(r"\n\s*\n", strip_non_prose(text)):
        if not block.strip():
            continue
        cur = None                      # a paragraph break ends a task
        for sentence in split_step_sentences_v2(block):
            marker = _GOAL_MARKER.match(sentence)
            if marker:
                cur = start(marker.group("goal").strip())
                rest = marker.group("rest").strip()
                if is_imperative_v2(rest, admitted):
                    cur["steps"].append(rest)
                continue
            if not is_imperative_v2(sentence, admitted):
                continue
            if cur is None:
                cur = start(sentence.rstrip("."))
            cur["steps"].append(sentence)

    return [t for t in tasks if t["steps"]]


def compile_procedures(*, document_id: str, corpus_id: str,
                       text: str, title: str = "",
                       admitted_entities: list[str] | None = None,
                       source_chunk_ids: list[str] | None = None,
                       min_steps: int = MIN_STEPS) -> list[dict]:
    """PROCEDURE_ARTIFACT_V2 — one artifact per LOCAL TASK.

    Returns artifacts in document order. Ids stay content-addressed, so
    two tasks with different steps get different ids and replay is
    still idempotent. Steps are always verbatim source sentences: this
    compiler selects, it never rewrites.
    """
    admitted_list = list(admitted_entities or [])
    admitted = frozenset(e.lower() for e in admitted_list)

    out: list[dict] = []
    for i, task in enumerate(segment_tasks(text, admitted)):
        steps = task["steps"]
        if len(steps) < min_steps:
            continue

        tools: list[str] = []
        for e in sorted(admitted_list, key=len, reverse=True):
            if any(e.lower() in s.lower() for s in steps) and \
                    e.lower() not in [t.lower() for t in tools]:
                tools.append(e)

        # OBJECT-NAME-CONTRACT-V2 (audit F12): a document title that
        # fails the shared name gate (clause-shaped, or glue-repeated
        # tokens like "AWS Cloud DevOps Engineer Path DevOps") never
        # becomes a procedure title; the deterministic fallback does.
        from polymath_shared.knowledge_objects.concept import (
            object_name_admissible,
        )
        safe_title = title if (title and object_name_admissible(title)[0]) \
            else f"Procedure ({len(steps)} steps)"
        body = {
            "title": safe_title,
            "goal": task["goal"].rstrip("."),
            "tools": tools,
            "steps": steps,
        }
        artifact = KnowledgeArtifact(
            artifact_id="pending",
            artifact_type="PROCEDURE",
            document_id=document_id,
            corpus_id=corpus_id,
            source_chunk_ids=list(source_chunk_ids or []),
            confidence=DECLARED_NON_SIGNAL_CONFIDENCE,
            provenance={"contract": PROCEDURE_CONTRACT_V2,
                        "task_index": i},
        )
        artifact = finalize(artifact, body)
        record = artifact.model_dump()
        record.update(body)
        out.append(record)
    return out
