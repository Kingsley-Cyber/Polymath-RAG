# New-document quality probe — CySA+ CS0-004 Domain 1

Source: `full-cysa-cs0-004-domain-1-security-operations.md`, 522,992 bytes,
94,148 words. YouTube transcript, `source_url: youtu.be/gyE8di5QPfQ`.

**ID discrepancy, unresolved:** the request named `Q4ZGoLwc2Jo`; the file's
frontmatter says `gyE8di5QPfQ`. Title, word count (88,807), chunk count (356)
and duration (8h15m) all match, so this is the intended file, but the video id
does not.

Corpus: `quality-probe-v1` (isolated; `cysa-study-v1` untouched, P14 still
rebuilds exactly once). Run `run_f2262ea1`, status **query_ready**, 12/12
tickets done.

Sampling: 4 random items per phase, `random.seed(4)`, reproducible via
`scratchpad/probe_sample.py`. Not cherry-picked.

---

## Source profile

| feature | count |
|---|---|
| markdown headings | 3 (`## PARENT SUMMARY`, `## CHILD CHUNKS`, `## RAG METADATA`) |
| pre-chunked blocks | 356 `**N. Title**` sections with `<!-- chunk_id … -->` markers |
| transcript timestamps | 0 |
| tables / code fences | 0 / 0 |
| hard-wrapped lines | 364 |
| **glossary** | **none present in the source** |

The glossary check was requested. There is no glossary in this document, so
nothing was lost — the check is *not applicable*, not *passed*.

---

## Volumes

| stage | result | v1 would have produced |
|---|---|---|
| child chunks | 456 (`chunk-structure-v2`) | v1 contract |
| parent chunks | 114 | — |
| parent summaries | 114 authoritative, 0 superseded | duplicates possible |
| mentions | 5,960 | — |
| durable entity surfaces | 814 | — |
| relation candidates | 810 | — |
| accepted facts | 114 | — |
| **procedures** | **302** | **1** (one per document) |
| **concepts** | **26** | **≤10** (storage ceiling) |

First real exercise of `chunk-structure-v2`: before this ingest, 0 of 8,887
live chunks carried the V2 stamp. All 456 here do.

---

## Phase samples

### 1. Chunking — PASS

All 4 sampled chunks: stamped `chunk-structure-v2`, no heading glued mid-text,
text verbatim in source, spans contiguous. Newline counts 0–6, i.e. structure
preserved rather than flattened.

One chunk ends mid-sentence (the 1,200-char boundary), which is the contract
working as designed, not loss.

**Noise found:** chunk 155 contains the source's own
`<!-- chunk_id: ch-118 | parent_doc: … -->` marker as body text. The upstream
tool's chunk markers are being ingested as content. Cosmetic, not loss.

### 2. Summaries — MIXED

114 authoritative summaries, exactly one per parent chunk, zero superseded
(P23's supersede semantics holding on a fresh corpus).

Quality is uneven. One sampled summary is degenerate — the whole text is
`"domain one is a security operations."` Entity lists carry transcription
noise and non-entities: `'I'`, `'Somebody'`, `'Benna'`, `'Bennetta'`,
`'03 version'`, `'04 version'`, `'Chromeexe'`.

### 3. Entities — MIXED

814 durable surfaces from 5,960 mentions. Sample: `'Benna'` (Organization,
GLOBAL, 1 occurrence — a mis-transcription of "Balena"), `'AI tool'` (generic),
`'Plaid'` (Library), `'Unusual File Creations'` (Process).

Spoken-transcript ASR errors are being promoted to GLOBAL entity identity on a
single occurrence.

### 4. Facts — **FAIL. RELEASE BLOCKER.**

Of 4 sampled accepted facts, 3 are false knowledge:

```
you --uses--> http                                    pronoun subject
grock --similar_to--> i                               pronoun object
you --created--> reliable                             pronoun subject, adjective object
vulnerability prioritization --similar_to--> exploitability factors   defensible
```

**33 of 148 distinct accepted-fact endpoints (22%) are closed-class pronouns.**

This is not the P1 defect returning. P1 is working — `i` and `it` are correctly
classified `MENTION_ONLY` and carry `mention_*` ids. The defect is that a fact
was accepted anyway:

```
fact_b9c1a1fd…  subject_id=mention_ecd5b1d0…  object_id=mention_d13a16d8…
                decision=ACCEPT  rule_id=instance_of
```

**Mechanism: there are two fact-writing paths and only one enforces endpoint
eligibility.**

* `fact_admission._endpoints` (`fact_admission.py:238-270`) rejects both a
  `mention_`-prefixed id and a `MENTION_ONLY` class. It ran and worked —
  `fact_admission_decisions` holds 148 rows for this document, 147 REJECT,
  with `F3_ENDPOINTS` firing 135 times.
* The rulepack compiler path writes `relation_candidates.decision='ACCEPT'`
  (130 of them) straight through to `facts` **without** the F3 endpoint gate.

**Why no gate caught this:** `test_no_active_fact_has_a_pronoun_endpoint`
checks 12 surfaces — `you, we, they, he, she, them, him, her, this, that,
these, those`. `CLOSED_CLASS_PRONOUNS` has 29. Missing from the test:
`i, it, me, us, one, ones, which, who, whom, what, myself, yourself, himself,
herself, itself, ourselves, themselves`. The two pronouns that leaked here —
`i` and `it` — are both in the unchecked set. The gate reported green while
the defect was live.

### 5. Procedures — FAIL (over-extraction)

302 procedures from a lecture transcript. Steps are verbatim
(`all_steps_verbatim=True`), so nothing is invented, but the goals are
malformed: one sampled goal is
`"Right** of data that's leaving and then we can see another spike…"` —
carrying markdown `**` artifacts and no task semantics.

P3 fixed one-artifact-per-document. On continuous spoken narration it now
over-segments: paragraph-shaped speech is not a task boundary.

### 6. Concepts — PASS (with a caveat)

26 concepts, above the old ceiling of 10, so the P4 inventory is live. Names
were clean in the sample; the transcript-stamp fix committed earlier this
session is doing its job. 26 from an 8-hour lecture is plausibly low but not
demonstrably lossy.

---

## Verdict against the release-blocker rule

| finding | blocks release? |
|---|---|
| pronoun endpoints in 22% of accepted facts | **YES — false knowledge** |
| pronoun-fact gate checks 12 of 29 pronouns | **YES — false green** |
| procedure over-segmentation on narration | no — quality, not loss |
| ASR errors promoted to GLOBAL entities | no — quality, not loss |
| degenerate parent summary | no |
| upstream chunk markers ingested as text | no |
| glossary | not applicable — none in source |

**P14 must not run until the two YES rows are closed.** Rebuilding
`cysa-study-v1` now would write pronoun facts into the production corpus at
roughly the same rate, and the existing gate would report green while it
happened.

---

## Next actions

1. Route the rulepack compiler's accepted candidates through the same F3
   endpoint eligibility gate, so there is one authority rather than two paths.
2. Widen `test_no_active_fact_has_a_pronoun_endpoint` to the full
   `CLOSED_CLASS_PRONOUNS` set and mutation-test it.
3. Re-probe this corpus, confirm pronoun endpoints reach 0.
4. Only then freeze (P13) and rebuild (P14).

Deferred as quality, recorded not fixed: procedure over-segmentation on
narration, single-occurrence ASR entity promotion, degenerate summaries.
