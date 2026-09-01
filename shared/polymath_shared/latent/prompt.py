"""parent-enrichment-v1 prompt — six outputs, integer child refs.

The model reads a parent's child chunks (numbered 0..N-1) and returns
ONE JSON object. It may reference children ONLY by their numbers; it
may not produce ids, metadata, or anything outside the schema."""
from __future__ import annotations

PROMPT_VERSION = "parent-enrichment-prompt-v1"

SYSTEM_PROMPT = """You are a knowledge abstraction engine. You read a numbered sequence of passages from ONE section of a document and reply with ONE JSON object and nothing else - no prose, no markdown fences.

Schema (all fields required):
{"summary":"...","children":[{"ref":0,"gist":"..."}],"abstraction":"...","mechanisms":["..."],"affordances":["..."],"questions":["..."]}

Rules:
- summary: 80-120 words covering the whole section.
- children: EXACTLY one gist (20-35 words) per numbered passage, using each passage's number as "ref". Never invent numbers.
- abstraction: 25-45 words naming the domain-independent principle this section teaches - what stays true outside this subject.
- mechanisms: up to 2 short statements of HOW the core process works (cause -> effect), phrased generally.
- affordances: up to 2 short statements of what this knowledge lets someone DO, phrased generally.
- questions: up to 3 questions a learner in a DIFFERENT field might ask that this section answers.
- Reference passages only by the numbers given. Output JSON only."""


def render_parent_input(parent_id: str,
                        children: list[tuple[int, str]]) -> str:
    """The user prompt: numbered passages in source order. `parent_id`
    is shown for traceability only — the model never repeats it."""
    lines = [f"Section {parent_id} — {len(children)} passages:"]
    for ref, text in children:
        lines.append(f"\n[{ref}]\n{text}")
    return "\n".join(lines)


def prompt_hash() -> str:
    from polymath_shared.identity import content_hash
    return content_hash({"system": SYSTEM_PROMPT,
                         "version": PROMPT_VERSION})


MINIMAL_PROMPT_VERSION = "parent-enrichment-minimal-prompt-v1"

#: ENRICH-HARD-CASE-V1 escape contract: when both group lanes reject a
#: section's FULL enrichment, one bounded attempt asks a cross-family
#: lane for only what the latent projection fundamentally needs — the
#: two retrieval surfaces. Aggressively validated; persisted with the
#: minimal compiler contract, never passed off as the full one.
MINIMAL_SYSTEM_PROMPT = """You read passages from ONE document section and reply with ONE small JSON object and nothing else - no prose, no markdown fences, no explanations.

Return exactly this shape:
{"abstraction": "<the section's domain-independent principle in 1-3 plain sentences>", "transfer": "<1-2 sentences on where else this principle applies and what questions it answers>"}

Rules: plain declarative language; no lists; no keys other than abstraction and transfer; both values non-empty."""
