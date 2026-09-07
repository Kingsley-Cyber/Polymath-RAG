"""doc-profile-v3 — the enrichment prompt for the Document Retrieval Profile (owner text 2026-09-07, with THEORY,
CONCEPT and the v3 counts). The compiler (`compiler.py`) parses the reply; the lean context builder fills the
DOCUMENT block. Correct meaning outranks exact counts; missing items are omitted, never invented."""
from __future__ import annotations

PROMPT_VERSION = "doc-profile-v3.2"     # v3.1: aims 10/10/15/15/10/10/10 (owner 2026-09-07); v3.2: the label on EVERY line

SYSTEM = """You extract a compact search profile from document evidence.

Use only the supplied document information.

Your goal is to help a retrieval system:

1. understand what the document is about,
2. find it from user questions,
3. find it from short search queries,
4. identify important concepts and terms,
5. connect it to related knowledge.

OUTPUT FORMAT

Write one item per line using these exact labels. Start EVERY line with its label: each topic line begins
with TOPIC:, each question line with Q:, each search line with SEARCH:, and so on. Never write a label once
and then list unlabeled lines under it.

ONE: <what this document is mainly about>

SUMMARY: <1 or 2 sentences describing the main content>

TOPIC: <specific major topic>            (aim for 10 lines)
TERM: <important term, entity, framework, method, acronym, or jargon>   (aim for 10 lines)
Q: <natural question this document can answer?>                         (aim for 15 lines)
SEARCH: <short search query>                                             (aim for 15 lines)
THEORY: <underlying framework, mechanism, model, or explanatory lens>    (aim for 10 lines)
CONCEPT: <generalizable concept that could also matter in other domains> (aim for 10 lines)
SEEALSO: <type of related document or neighboring knowledge>             (aim for 10 lines)

END

RULES

ONE
* One sentence. State the central subject of the document. Be specific.

SUMMARY
* One or two dense sentences covering the document's main scope, argument, explanation, or purpose.

TOPIC
* Aim for 10. Use specific conceptual topics, each a different area the document covers; avoid broad labels such as "history", "technology" or "science" when a more specific topic exists.

TERM
* Aim for 10. Use important terminology actually supported by the document. Preserve proper names and acronyms.

Q
* Aim for 15. Questions a person could naturally ask; each a different information need, spread across the document's parts; the document must contain enough to answer it.

SEARCH
* Aim for 15. How a person might search for the information: usually 2 to 6 words, keyword-style, no question mark, varied wording, spread across the document's parts.

THEORY
* Aim for 10. Identify the deeper mechanisms or frameworks that help explain the document: established named frameworks when strongly supported, recurring mechanisms, causal patterns, or plain-language explanatory principles. Do not invent a named theory merely because it seems related; fewer lines are better than invented ones.

CONCEPT
* Aim for 10. Abstract beyond the document's immediate subject: "What transferable idea is demonstrated here that could also appear in a different field?" Prefer mechanisms, relationships, constraints, behaviors, tradeoffs and patterns over broad nouns.
* Good: coordinated action increases group leverage · delayed feedback destabilizes control · authority should follow verified identity.
* Weak: workers · technology · management.

SEEALSO
* Aim for 10. Describe neighboring, prerequisite, deeper, broader, contrasting, or complementary knowledge. Do not simply repeat a TOPIC. Do not invent specific documents or authors.

IMPORTANT

Correct meaning is more important than exact item counts: the aims are ceilings to reach when the document supports them, never quotas to fill.
If there is not enough evidence for an item, omit it rather than inventing information.
Do not explain your answer. Do not use markdown. Do not use bullets. Do not number items. Do not create new labels. Do not put more than one item on a line.
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
