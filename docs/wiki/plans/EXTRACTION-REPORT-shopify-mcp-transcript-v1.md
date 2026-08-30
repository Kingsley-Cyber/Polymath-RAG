---
change_id: EXTRACTION-REPORT-SHOPIFY-MCP-TRANSCRIPT-V1
owner: governance
date: 2026-08-23
status: reference
architecture_impact: none (documentation; front matter added 2026-08-29 governance cleanup)
last_reviewed: 2026-08-29
---

# EXTRACTION REPORT — shopify-mcp-transcript-v1
Source: /Volumes/Flash Drive/markbuildsbrands_transcripts/
        "i make 150kmo from 3 businesses - heres the one id start today.md"
(YouTube transcript — codingwithjan: Shopify Global Catalog / MCP / API)
Pipeline: kimi_v1 + Predicate Compiler v2 SHADOW (all lanes run — this
is the diagnostic value of shadow mode)

## Entities (101 discovered)

GLOBAL 30 · CORPUS_SCOPED 1 · MENTION_ONLY 70.
Well-captured technical surfaces: API · MCP · Shopify · Chrome · USB
cable · price comparison tool. **DEFECT E-1:** pronouns "You" / "I"
admitted as durable entities — pronoun surfaces must be forced
MENTION_ONLY at Entity Admission (fixture needed).

## Facts admitted (shadow, ALL LANES) — quality analysis

| Subject | Predicate | Object | Verdict |
|---|---|---|---|
| You | acquired | commodity products | **JUNK** — business-jargon misfire of `acquired` (known pack sense-blindness, now measured live outside scientific domain) |
| Product | alias_of | Id | **JUNK** — "goes by this ID" copula misfire |
| Api | similar_to | Product | **JUNK** — explanatory analogy misfires `similar_to` |

## Rejected candidates (16) — mostly CORRECT

- scope_gate: question ×2 (interrogative openings) ✓
- scope_gate: conditional,speculative ×4 ("might also find",
  "could become") ✓ adversarial defense working on real hype language
- silent drops: empty-reason legacy-lane pairs (API→product etc.)

## Root cause & the architectural answer

The junk facts are the DOCUMENTED pack sense-blindness firing outside
its domain. Knowledge Router v1.1 already classifies this document
NARRATIVE/PROCEDURAL with `disabled: [scientific_predicate]` — under
ROUTER ENFORCEMENT these three junk facts never exist. Shadow mode ran
all lanes deliberately to measure exactly this.

Second fix required regardless: **E-1 pronoun admission ban**
("you","i","it" surfaces → MENTION_ONLY always). Small admission-side
fixture change, no gate weakening.

## Everything else

- Parent summaries ×2 composed from fact sentences (showing the junk —
  which is GOOD: summaries expose bad facts instead of hiding them)
- Corpus map: API · MCP · Chrome · Shopify · USB cable · price
  comparison tool — genuinely useful topical map
- Vocabulary: 0 families (guard holding)

## Verdict

Corpus proves why ROUTER ENFORCEMENT + E-1 are the two remaining gates
before production: both fixes are already designed; neither weakens
extraction. Scientific corpora stay clean (TEST copy: 7 good facts);
non-scientific corpora get entity+concept+procedure coverage without
junk relations once lanes respect routing.
