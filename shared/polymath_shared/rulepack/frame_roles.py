"""PREDICATE-COMPILER-V2 / CATEGORY-C: role-oriented frame binding.

Replaces positional assumptions for FRAME-classed anchors:

  C1 voice-aware orientation  "Studies evaluated BERT on GLUE"
       -> ARG1(BERT) is the fact subject regardless of voice;
          ARG0(studies) never becomes the evaluated model.
  C2 head-chain inheritance   "...ToT is a framework introduced by..."
       -> an admitted entity separated from its trigger ONLY by
          determiners/copulas/generic scientific heads inherits the
          slot (bounded walk, no loose extraction).
  C3 controlled pronouns      "BERT was introduced. It was evaluated..."
       -> previous-sentence resolution ONLY when exactly ONE durable,
          type-compatible candidate exists. Ambiguous -> None.

Deterministic lookup-only; fail-closed (empty result = no candidate).
Provenance strings ride through to the compiler decision reason.
"""
from __future__ import annotations

from typing import Any

from polymath_shared.rulepack.compound_heads import is_generic_head

#: UD labels treated as passive evidence when governed by the trigger.
_PASSIVE_DEPS = frozenset({"nsubj:pass", "agent", "obl:agent"})
_PRONOUN_LEMMAS = frozenset({"it", "they", "he", "she", "this", "these"})
_FILLER = frozenset({"a", "an", "the", "is", "was", "were", "been", "be",
                     ",", ";", "—"})


def detect_voice(tokens: list[dict], trig_head: dict | None) -> str:
    """'passive' when a passive-labeled dependent hangs off the trigger."""
    if trig_head is None:
        return "active"
    ti = trig_head["i"]
    for tok in tokens:
        if tok.get("head_i") == ti and tok.get("dep") in _PASSIVE_DEPS:
            return "passive"
    return "active"


def _toks_of(ud_args: dict[str, list[dict]], *slots: str) -> list[dict]:
    out: list[dict] = []
    for s in slots:
        out.extend(ud_args.get(s, []))
    return out


def orient_frame_slots(
    tokens: list[dict],
    trig_head: dict | None,
    ud_args: dict[str, list[dict]],
    pattern_group: str,
) -> dict[str, Any]:
    """Map UD slots -> fact subject/object TOKEN groups for a frame.

    pattern_group is the ontology mapping family:
      'theme_standard'   (trained_on / evaluated_on / depends_on):
          fact-subject = THEME (ARG1), fact-object = PREP standard (ARG2)
      'theme_by_agent'   (introduced_by / proposed_by):
          fact-subject = THEME, fact-object = BY-AGENT
      'agent_theme'      (uses_method):
          fact-subject = AGENT, fact-object = THEME

    Voice-aware: passive swaps surface nsubj into the theme slot and
    moves the by-phrase into the agent slot (same PropBank contract as
    role_assignment._PASSIVE_VOICE_MAP).
    """
    voice = detect_voice(tokens, trig_head)
    subj_toks = _toks_of(ud_args, "subject")
    obj_toks = _toks_of(ud_args, "object")
    prep_toks = _toks_of(ud_args, "prep_object", "oblique")

    if pattern_group == "theme_by_agent":
        if voice == "passive":
            return {"fact_subject": subj_toks,          # nsubj:pass = theme
                    "fact_object": prep_toks,           # by-agent
                    "voice": voice}
        return {"fact_subject": obj_toks,               # dobj = theme
                "fact_object": subj_toks,               # nsubj = agent
                "voice": voice}

    if pattern_group == "agent_theme":
        if voice == "passive":  # rare; theme leads, agent in by-phrase
            return {"fact_subject": prep_toks,
                    "fact_object": subj_toks,
                    "voice": voice}
        return {"fact_subject": subj_toks,
                "fact_object": obj_toks,
                "voice": voice}

    # default: theme_standard
    if voice == "passive":
        return {"fact_subject": subj_toks,              # theme
                "fact_object": prep_toks,               # on-standard
                "voice": voice}
    return {"fact_subject": obj_toks,                   # dobj theme
            "fact_object": prep_toks,                   # on-standard
            "voice": voice}


def _gap_is_inert(sentence: str, entity_end: int, trigger_start: int,
                  protected_texts: frozenset[str] = frozenset()) -> bool:
    """True when the span between the entity and the trigger is a
    determiner/copula/filler + OPTIONAL adjectives + exactly one closing
    GENERIC scientific head noun — i.e. an appositive/compound head
    chain ("ToT is a reasoning framework | introduced"). Any other
    content word (verbs, second nouns, another entity's text) breaks
    the chain."""
    gap = sentence[entity_end:trigger_start].strip()
    if not gap:
        return True
    words = [w.strip(",.;:—") for w in gap.split()]
    words = [w for w in words if w]
    if not words:
        return True
    # the word adjacent to the trigger must be the generic head
    if not is_generic_head(words[-1]):
        return False
    for w in words[:-1]:
        lw = w.lower()
        if lw in _FILLER:
            continue
        # descriptive modifiers allowed only when lowercase and not
        # part of any admitted entity surface (never steal an entity)
        if w.islower() and not any(lw in pt.lower().split()
                                   for pt in protected_texts):
            continue
        return False
    return True


def head_chain_theme(
    sentence: str,
    entities: list[Any],
    trigger_start: int,
    max_gap_tokens: int = 6,
) -> Any | None:
    """C2: nearest admitted entity LEFT of the trigger whose separating
    tokens are exclusively filler/generic-head words (deterministic
    bounded walk). None when no such chain exists."""
    best = None
    for e in entities:
        if e.end > trigger_start:
            continue
        gap_words = len([w for w in
                         sentence[e.end:trigger_start].split() if w])
        if gap_words > max_gap_tokens:
            continue
        if not _gap_is_inert(
                sentence, e.end, trigger_start,
                frozenset(x.text for x in entities if x is not e)):
            continue
        if best is None or e.end > best.end:
            best = e
    return best


def resolve_pronoun_subject(
    pronoun_tok: dict | None,
    prev_sentence_entities: list[Any],
    allowed_subject_types: set[str],
) -> tuple[Any | None, str]:
    """C3: inherit identity ONLY when the previous sentence holds
    exactly ONE durable candidate of a type the predicate accepts.

    Returns (entity|None, provenance_note)."""
    if pronoun_tok is None:
        return None, "no_pronoun"
    lemma = (pronoun_tok.get("lemma") or pronoun_tok.get("text", "")).lower()
    if lemma not in _PRONOUN_LEMMAS:
        return None, "not_subject_pronoun"
    cands = []
    for e in prev_sentence_entities:
        ct = getattr(getattr(e, "core_type", None), "value",
                     getattr(e, "core_type", ""))
        if str(ct).lower() in {a.lower() for a in allowed_subject_types}:
            cands.append(e)
    texts = {e.text for e in cands}
    if len(texts) == 1:
        e = cands[0]
        return e, f"pronoun_resolved_unique:{e.text}"
    if len(texts) > 1:
        return None, f"pronoun_ambiguous:{sorted(texts)[:4]}"
    return None, "pronoun_no_compatible_candidate"
