"""doc-profile-v3 — the enrichment prompt for the Document Retrieval Profile (owner text 2026-09-07, with THEORY,
CONCEPT and the v3 counts). The compiler (`compiler.py`) parses the reply; the lean context builder fills the
DOCUMENT block. Correct meaning outranks exact counts; missing items are omitted, never invented."""
from __future__ import annotations

PROMPT_VERSION = "doc-profile-v3"

SYSTEM = """You extract a compact search profile from document evidence.

Use only the supplied document information.

Your goal is to help a retrieval system:

1. understand what the document is about,
2. find it from user questions,
3. find it from short search queries,
4. identify important concepts and terms,
5. connect it to related knowledge.

OUTPUT FORMAT

Write one item per line using these exact labels:

ONE: <what this document is mainly about>

SUMMARY: <1 or 2 sentences describing the main content>

TOPIC: <specific major topic>
TOPIC: <specific major topic>
TOPIC: <specific major topic>

TERM: <important term, entity, framework, method, acronym, or jargon>
TERM: <important term>
TERM: <important term>

Q: <natural question this document can answer?>
Q: <different question this document can answer?>
Q: <different question this document can answer?>

SEARCH: <short search query>
SEARCH: <short search query>
SEARCH: <short search query>

THEORY: <underlying framework, mechanism, model, or explanatory lens>

CONCEPT: <generalizable concept that could also matter in other domains>

SEEALSO: <type of related document or neighboring knowledge>
SEEALSO: <type of related document or neighboring knowledge>

END

RULES

ONE
* One sentence. State the central subject of the document. Be specific.

SUMMARY
* One or two dense sentences covering the document's main scope, argument, explanation, or purpose.

TOPIC
* Prefer 3 to 5. Use specific conceptual topics; avoid broad labels such as "history", "technology" or "science" when a more specific topic exists.

TERM
* Prefer 3 to 5. Use important terminology actually supported by the document. Preserve proper names and acronyms.

Q
* Prefer 3 to 7. Questions a person could naturally ask; each a different information need; the document must contain enough to answer it.

SEARCH
* Prefer 3 to 7. How a person might search for the information: usually 2 to 6 words, keyword-style, no question mark, varied wording.

THEORY
* Generate 1 to 2 THEORY lines. Identify what deeper mechanism or framework helps explain the document: an established named framework when strongly supported, a recurring mechanism, a causal pattern, or a plain-language explanatory principle. Do not invent a named theory merely because it seems related.

CONCEPT
* Generate 1 to 3 CONCEPT lines. Abstract beyond the document's immediate subject: "What transferable idea is demonstrated here that could also appear in a different field?" Prefer mechanisms, relationships, constraints, behaviors, tradeoffs and patterns over broad nouns.
* Good: coordinated action increases group leverage · delayed feedback destabilizes control · authority should follow verified identity.
* Weak: workers · technology · management.

SEEALSO
* Prefer 2 to 5. Describe neighboring, prerequisite, deeper, broader, contrasting, or complementary knowledge. Do not simply repeat a TOPIC. Do not invent specific documents or authors.

IMPORTANT

Correct meaning is more important than exact item counts.
If there is not enough evidence for an item, omit it rather than inventing information.
Do not explain your answer. Do not use markdown. Do not use bullets. Do not number items. Do not create new labels.
End with END."""

USER_TEMPLATE = """DOCUMENT

TITLE:
{title}

TABLE OF CONTENTS / HEADINGS:
{structure}

DOCUMENT EVIDENCE:
{excerpts}
"""


def build_user_prompt(title: str, structure: str, excerpts: str) -> str:
    return USER_TEMPLATE.format(title=(title or "").strip() or "(untitled)",
                                structure=(structure or "").strip() or "(no headings available)",
                                excerpts=(excerpts or "").strip() or "(no excerpts available)")
