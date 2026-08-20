"""REFERENTIAL-SPAN-V1 (PHASE 2C.1) — integration repair, no new semantics.

PHASE 2C proved the Harbor policy was never actually tested: GLiNER strips
determiners (`vision system`), while the discourse contract keys on them
(`the vision system`). Every protected definite abstained, and the P 0.917
that produced was mostly masking, not judgment.

The repair RECOVERS the determiner rather than normalising it away, because
these are not referentially equivalent:

    system / the system / this system / our system / a system

Two surfaces are kept, and they never overwrite each other:

    proposal_surface     exactly what GLiNER proposed — immutable provenance
    referential_surface  deterministic syntactic envelope in the SOURCE TEXT

Expansion is permitted ONLY when a spaCy noun chunk contains the proposal
span AND the chunk's head token is the proposal's head. This is not
"grab the previous token": containment plus head alignment is what stops
the envelope wandering across unrelated material. No aligned chunk means
NO expansion — fail closed.
"""
from __future__ import annotations

from dataclasses import dataclass

REFERENTIAL_SPAN_CONTRACT = "referential-span-v1"

_DETERMINERS = frozenset({
    "the", "a", "an", "this", "that", "these", "those",
    "our", "my", "your", "his", "her", "its", "their",
})


@dataclass(frozen=True)
class ReferentialSpan:
    proposal_surface: str          # NEVER rewritten — raw provider output
    proposal_start: int
    proposal_end: int
    referential_surface: str       # source-faithful envelope
    referential_start: int
    referential_end: int
    determiner: str | None
    head: str
    head_lemma: str
    envelope_source: str           # "noun_chunk" | "proposal"
    reasons: tuple[str, ...] = ()
    contract: str = REFERENTIAL_SPAN_CONTRACT

    @property
    def expanded(self) -> bool:
        return self.envelope_source == "noun_chunk"


def _tokens_in(tokens: list[dict], start: int, end: int) -> list[dict]:
    return [t for t in tokens
            if t.get("char_start") is not None
            and t["char_start"] >= start and t["char_end"] <= end]


def derive(proposal_surface: str, proposal_start: int, proposal_end: int,
           source_text: str, syntax: dict | None) -> ReferentialSpan:
    """Derive the referential envelope for one GLiNER proposal.

    `syntax` is one `syntax-evidence-v1` sentence result (tokens +
    noun_chunks) whose offsets are relative to the SAME string as
    `proposal_start`/`proposal_end`.
    """
    def _fallback(reason: str) -> ReferentialSpan:
        toks = _tokens_in((syntax or {}).get("tokens", []), proposal_start, proposal_end)
        head_tok = toks[-1] if toks else None
        return ReferentialSpan(
            proposal_surface, proposal_start, proposal_end,
            proposal_surface, proposal_start, proposal_end,
            determiner=None,
            head=(head_tok or {}).get("text", proposal_surface.split()[-1] if proposal_surface.split() else ""),
            head_lemma=(head_tok or {}).get("lemma", ""),
            envelope_source="proposal", reasons=(reason,))

    if not syntax:
        return _fallback("no syntax evidence — fail closed, no expansion")

    tokens = syntax.get("tokens", [])
    prop_tokens = _tokens_in(tokens, proposal_start, proposal_end)
    if not prop_tokens:
        return _fallback("proposal span aligns to no token")
    prop_head = prop_tokens[-1]

    # containment + head alignment
    aligned = []
    for ch in syntax.get("noun_chunks", []):
        if ch["char_start"] <= proposal_start and ch["char_end"] >= proposal_end:
            root = next((t for t in tokens if t["i"] == ch["root_i"]), None)
            if root is not None and root["i"] == prop_head["i"]:
                aligned.append((ch, root))

    if len(aligned) != 1:
        return _fallback(
            "no uniquely head-aligned containing noun chunk"
            if not aligned else "multiple head-aligned chunks — ambiguous, no expansion")

    ch, root = aligned[0]
    env = source_text[ch["char_start"]:ch["char_end"]]
    first = _tokens_in(tokens, ch["char_start"], ch["char_end"])
    det = None
    if first and first[0]["text"].lower() in _DETERMINERS:
        det = first[0]["text"]
    return ReferentialSpan(
        proposal_surface, proposal_start, proposal_end,
        env, ch["char_start"], ch["char_end"],
        determiner=det, head=root["text"], head_lemma=root.get("lemma", ""),
        envelope_source="noun_chunk",
        reasons=(f"noun chunk contains the proposal and its head '{root['text']}' "
                 f"is the proposal head",))
