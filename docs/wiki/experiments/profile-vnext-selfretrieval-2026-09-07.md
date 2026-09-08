---
title: "EXPERIMENT — vNext profile self-retrieval qualification (S8 gate)"
change_id: PROFILE-VNEXT-SELFRETRIEVAL-V1
date: 2026-09-07
owner: governance
last_reviewed: 2026-09-07
last_touched: 2026-09-07
status: complete
---

# vNext profile self-retrieval qualification (S8 gate)

**Question:** does the vNext (fingerprint + `profile_prompt_vnext`) profile self-retrieve
AT LEAST AS WELL as the current lean-context profile before we enable it? (The owner's
"qualify against the existing baseline" gate; do not flip `POLYMATH_DOC_PROFILE_VNEXT`
globally until it passes.)

**Method:** `scripts/profile_vnext_selfretrieval_canary.py --corpus cinema` — for all 67
cinema documents, generate the vNext profile through the existing `doc_profile` Groq
pool (`groq/compound`), project it to a SEPARATE canary Qdrant collection
(`polymath_document_profiles_<contract>_vnextcanary`, same competitor set as
production), and measure self-retrieval (each doc's own questions/searches → RRF over
identity/theme/title dense + questions/searches multivectors → rank of the source doc).
Baseline = the CURRENT profiles' self-retrieval on the same 67 docs (production
collection). 67 generations, 0 errors; the canary collection was deleted afterward.
Evidence: `profile-vnext-selfretrieval-2026-09-07.json`.

| profile | docs | probes | top-1 | top-3 | median rank |
|---|--:|--:|--:|--:|--:|
| baseline (lean-context, same cohort) | 67 | 400 | 0.860 | 0.995 | 1 |
| **vNext (fingerprint)** | 67 | 135 | **0.933** | 0.985 | 1 |

**Verdict: PASS.** The vNext profile self-retrieves BETTER than the baseline (top-1
0.933 vs 0.860), well above the gate (baseline − 0.03 tolerance). Median rank 1 for both;
top-3 within noise (0.985 vs 0.995). The vNext profiles produced fewer question/search
probes per doc (135 vs 400 total) yet a higher hit rate — the full-structure fingerprint
yields more discriminating routing surfaces. Evaluation-only: no production collection,
live worker, or authoritative state was touched.

**Decision:** enable the vNext profile via the reversible flag `POLYMATH_DOC_PROFILE_VNEXT=1`
(set in `.env`; takes effect on the next fleet/supervisor reload — the running fleet stays
on the legacy path until then). Rollback = unset the flag. This changes only NEW-document
profile generation; existing profiles are untouched (backfill is a separate controlled step).
