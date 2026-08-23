"""SCIENTIFIC-KAG-V1 phase 5.5: deterministic discourse bridge.

Scientific writing is not sentence-level: "Tree of Thoughts is a
reasoning framework. It allows LMs to explore paths." loses ToT→allows→
LMs when "It" dies as a non-durable pronoun. This module resolves a
LIMITED class of cross-sentence references deterministically, using
ONLY already-admitted entities — it never creates identity, it inherits
it.

Capability 1 — definitional apposition (intra-sentence):
  "X, a paradigm that ..." — an appos child of an entity head is a
  DESCRIPTION; argument tokens inside the appos subtree resolve to the
  entity head's admitted span.

Capability 2 — controlled anaphora (cross-sentence):
  pronoun + previous-sentence subject + distance <= MAX_ANAPHORA_DISTANCE
  + unique subject in the window -> the pronoun span resolves to that
  subject's entity. Type compatibility is checked downstream against the
  RESOLVED entity, never against the pronoun's own noisy GLiNER label.

Everything else abstains. No model, no embedding, no coreference
library — token positions and dependency arcs only.
"""
from __future__ import annotations

MAX_ANAPHORA_DISTANCE = 2

_PRONOUNS = frozenset({
    "it", "they", "them", "this", "these", "he", "she", "we",
})


def _entity_at_token(tok: dict, sl) -> object | None:
    from workers.kimi_candidates import _token_to_entity

    return _token_to_entity(tok, sl.entities, sl)


def _is_durable(ent) -> bool:
    admission = getattr(ent, "admission_class", None)
    if admission is None:
        return True  # harness-built spans: durability enforced by F3 later
    return admission in ("GLOBAL", "CORPUS_SCOPED")


def sentence_subject_entity(sl) -> object | None:
    """The first durable entity bound to the sentence's subject slot."""
    tokens = sorted(getattr(sl, "syntax", None or {}).get("tokens", []),
                    key=lambda t: t["char_start"])
    for tok in tokens:
        if tok.get("dep") not in ("nsubj", "nsubj:pass", "nsubjpass"):
            continue
        ent = _entity_at_token(tok, sl)
        if ent is not None and _is_durable(ent):
            return ent
    return None


def find_appos_entity_head(tok: dict, sl) -> dict | None:
    """If `tok` sits inside an appos subtree, return the head token of
    the entity phrase the appos describes (the governor chain up to the
    appos arc)."""
    tokens = {t["i"]: t for t in (
        getattr(sl, "syntax", None) or {}).get("tokens", [])}
    cur = tok
    seen = set()
    while cur is not None and cur.get("i") not in seen:
        seen.add(cur.get("i"))
        head_i = cur.get("head_i")
        if head_i is None or head_i == cur.get("i"):
            return None
        head = tokens.get(head_i)
        if head is None:
            return None
        if cur.get("dep") == "appos":
            return head
        cur = head
    return None


def is_pronoun_token(tok: dict) -> bool:
    return (tok.get("text") or "").lower() in _PRONOUNS


def resolve_anaphora(slices) -> dict:
    """Cross-sentence pronoun resolution over ordered slices.

    Returns {(chunk_id, start, end): EntitySpan} for pronoun spans that
    resolve under the owner rule. Ambiguity (two distinct subjects in
    the window) abstains per position.
    """
    out: dict = {}
    subjects: list[tuple[int, object]] = []  # (sentence_order, entity)
    order = 0
    for sl in slices:
        subj = sentence_subject_entity(sl)
        pronoun_positions = []
        tokens = sorted((getattr(sl, "syntax", None) or {}).get(
            "tokens", []), key=lambda t: t["char_start"])
        for tok in tokens:
            surface = (tok.get("text") or "").lower()
            if surface in _PRONOUNS:
                ent = _entity_at_token(tok, sl)
                if ent is not None:
                    pronoun_positions.append((tok, ent))
        for tok, ent in pronoun_positions:
            window = [(o, e) for o, e in subjects
                      if 0 < order - o <= MAX_ANAPHORA_DISTANCE]
            candidates = {id(e): (o, e) for o, e in window}
            uniq = {id(e): e for _, e in window}
            if len(uniq) == 1:
                resolved = next(iter(uniq.values()))
                key = (sl.entities[0].chunk_id if sl.entities else "c0",
                       sl.sentence_start + tok["char_start"],
                       sl.sentence_start + tok["char_end"])
                out[key] = resolved
        if subj is not None:
            subjects.append((order, subj))
        order += 1
    return out


def substitute_span(sl, span, replacement):
    """Return `replacement` for a pronoun span during argument binding."""
    return replacement
