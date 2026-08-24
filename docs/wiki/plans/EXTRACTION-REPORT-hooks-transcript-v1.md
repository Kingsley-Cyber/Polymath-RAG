# EXTRACTION REPORT — hooks-transcript-v1
Source: /Volumes/Flash Drive/markbuildsbrands_transcripts/
        "how to create unlimited hooks with ai that print money in just 49 sec.md"
(YouTube transcript, Mark Builds Brands, 49s video + front matter)
Pipeline: kimi_v1 + Predicate Compiler v2 shadow · persisted

## Result: 0 scientific facts — CORRECT behavior

| Layer | Finding |
|---|---|
| Entities | 20 discovered → 5 GLOBAL (Instagram, Mark, SOP, sonnet 4.5) · 15 MENTION_ONLY |
| Relations | 0 candidates — no scientific frame realizations present |
| Facts | 0 |
| Parent summary | composed from front matter + entities (fallback path) |
| Document summary | entities propagated, methods empty |
| Corpus map | entity items only (Instagram, Mark, SOP, sonnet 4.5); predicates empty |
| Vocabulary | 0 families after guard hardening |

## Why zero facts is the CORRECT result

This is marketing transcript content, not scientific prose. The
ontology is a SCIENTIFIC predicate ontology ("trained_on",
"evaluated_on", "introduced_by"). Marketing verbs ("create hooks",
"print money", "paste prompts") match no frames — and per the
fail-closed contract, no relations are guessed. A high-recall extractor
would have emitted junk like Mark --creates--> hooks.

## Defect found & fixed during this test

VOCABULARY GUARD BYPASS: a junk family formed ("brand builders academy"
with aliases GBT / Mark Builds Brands / Telegram Group) because a
document summary DERIVED from one parent counted as a second,
independent supporter. Fix: derived-layer ids recorded as provenance
only; admission now requires ≥2 INDEPENDENT (parent-level) summaries.
Verified: families 1 → 0 on this corpus.

## Cosmetic finding

YAML front matter (title/url/video_id) leaks into summary fallback text.
Suggested future fix: strip front matter at intake normalization.

## Cross-domain isolation confirmed

test-copy-v1 (scientific): 7 facts · hooks-transcript-v1 (marketing):
0 facts · separate corpus maps · separate vocabularies. The system
extracts what each corpus actually contains.
