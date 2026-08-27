# EXTRACTION REPORT — ga-addtocart-transcript-v1
Source: /Volumes/Flash Drive/markbuildsbrands_transcripts/
        "add to cart report in google analytics.md"
(YouTube transcript — BlueAce Digital, Google Analytics / Shopify
add-to-cart reporting tutorial)
Pipeline: kimi_v1 + Predicate Compiler v2 shadow · persisted

## Result: 0 scientific facts — correct domain behavior

| Layer | Finding |
|---|---|
| Entities | 50 discovered → 15 GLOBAL · 1 CORPUS_SCOPED · 34 MENTION_ONLY |
| Relations | 0 candidates — no scientific frames in tutorial content |
| Facts | 0 |
| Rejections | 3 — ALL `scope_gate: question` (interrogative sentences refused) |
| Parent summary | entity map: BlueAce Digital · GA4 · Google Merchant Center · Simprosys app · item ID · last-28-days |
| Document summary | propagates parent intelligence |
| Corpus map | weighted entities; predicates empty |
| Vocabulary | 0 families — hardened guard holds across all three corpora |

## Notable behaviors demonstrated

1. **Question-scope gate live**: the tutorial's interrogative openings
   ("how to get visibility over how many add to carts…") produced
   candidates that were REFUSED by the question detector — first live
   appearance of this gate outside fixtures.
2. **Entity map is genuinely useful without facts**: GLOBAL surfaces
   captured the video's actual tool stack (GA4, Google Merchant
   Center, Simprosys app) even though no scientific relations exist.
3. **Cross-domain isolation holds at three corpora**:
   test-copy-v1 (scientific, 7 facts) · hooks-transcript-v1 (0) ·
   ga-addtocart-transcript-v1 (0) — separate maps, separate
   vocabularies, zero contamination.

## Known cosmetic issue (unchanged)

Front matter leaks into summary fallback text — intake-normalization
cleanup deferred.
