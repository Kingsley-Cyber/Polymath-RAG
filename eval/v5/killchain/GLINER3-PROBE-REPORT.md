# Probe 2 — gliner_3_document_realistic_test.txt

9,662 bytes · 1,411 words · 3 documents in one file (technical cybersecurity,
learning-science prose, an e-commerce video transcript). Corpus
`gliner3-probe-v1`, run `run_6543ddf1`, **query_ready in 2m41s**, 12/12 tickets.

Ingested on the chunker with the v3.3 router port (`fbeecbc`).

---

## Speed — via the repo diagnostic

`eval/v5/scale/phase1_baseline_report.py gliner3-probe-v1`

| stage | p50 s | p95 s | failures |
|---|---|---|---|
| intake | 8.13 | 8.13 | 0 |
| **project_qdrant** | **51.94** | **51.94** | 0 |
| extract / profile / neo4j / canonicalize / verify | ~0 | ~0 | 0 |

Retries 1 (2 attempts), dead letters 0, duplicate fact tuples 0, entity
identity fragments 0.

### Throughput, two points

| file | bytes | words | wall | KB/s | words/s |
|---|---|---|---|---|---|
| gliner_3_document_realistic_test.txt | 9,662 | 1,411 | 161 s | 0.06 | 9 |
| CySA Domain 1 transcript | 522,992 | 94,148 | 997 s | 0.51 | 94 |

The small file's rate looks 8× worse, but that is **fixed cost, not
throughput**. 54× the bytes took only 6.2× the time. Decomposing the two
points:

```
fixed cost   ~161 s   (project_qdrant 52 s + intake 8 s + orchestration)
marginal     ~613 bytes/s  =  (997-161) s / (522,992-9,662) bytes
```

**Revised P14 projection** for `cysa-study-v1` (8,606,714 bytes):
`161 s + 8,606,714/613` ≈ **4.0 hours**, which replaces the earlier crude
4.6 h serial estimate with a decomposed one. `project_qdrant` is the stage to
watch, not extraction, at this document size.

---

## Sampling — 4 per phase, `seed(4)`

### Chunking — PASS
9 child + 3 parent, all `chunk-structure-v2`. All 4 sampled: verbatim in
source, no heading glued mid-text, 4–12 newlines retained, none ending
mid-sentence. The router port introduced no regression here.

### Summaries — MIXED
3 authoritative, one per parent, 0 superseded. Entity lists carry `'I'`,
`'you'` and `'DOCUMENT 3'` — pronouns and a structural label presented as
entities of the summary.

### Entities — MOSTLY GOOD
40 durable surfaces from 102 mentions. `Atlas Identity Gateway` (Technology),
`Amazon` (Organization), `7 August 2026` (Date, CORPUS_SCOPED) are right.
`Monday` admitted as a **GLOBAL** Date is not — a bare weekday is not a
durable identity.

### Facts — 0 accepted, and this is the finding
Only **4 candidates** from a fact-rich technical document, all rejected:

```
Daniel Ortiz --?--> Red Ridge Systems
    type_violation: no signature accepts (Person -> Organization)   trigger 'engineer'
Daniel Ortiz --has_role--> Red Ridge Systems
    binding: has_role noun trigger requires syntactic attachment
platform team --?--> mutual TLS
    type_violation: no signature accepts (Organization -> Technology)  trigger 'propose'
platform team --?--> DPoP
    type_violation: no signature accepts (Organization -> Technology)
```

`fact_admission_decisions` is **empty** — nothing reached admission; every
candidate died at the compiler.

Two causes, both rulepack coverage:

1. **Sparse candidate generation.** The document states `issued by Keycloak
   26.2`, `deployed in the company's AWS environment`, `replayed from two
   previously unseen IP addresses` — none became candidates at all.
2. **Missing type signatures** for Person→Organization and
   Organization→Technology under the `creation` evidence class.

**Not a sidecar outage.** I suspected spaCy was down; it is up
(`en_core_web_sm@3.8.0`, manifest ok), and GLiNER is serving. The
`has_role` rejection is a genuine binding rule, not a missing parse.

### Concepts — 0 from 83 sentences
Two textbook definitions missed:

```
"Metacognitive monitoring refers to a learner's assessment of what they know…"
"Metacognitive control refers to the decisions made on the basis of…"
```

Cause: the `refers to` pattern in `_DEFINE_PATTERNS` is bound to the literal
names `model|threat model|hook`, so `X refers to Y` matches for nothing else.

---

## The contrast that matters

| | transcript probe | this probe |
|---|---|---|
| failure mode | **over**-extraction, false facts | **under**-extraction |
| facts | 114 accepted, 22% pronoun endpoints | 0 accepted from 4 candidates |
| procedures | 302 from narration | 2 |
| concepts | 26 | 0 |

The pronoun-endpoint fix closed the false-knowledge side. This file shows the
other edge: on clean technical prose the rulepack fires on almost nothing.

---

## Verdict against the release-blocker rule

| finding | blocks release? |
|---|---|
| 0 facts from a fact-rich document | **no** — the evidence is still retrievable in chunks; this is derived-knowledge recall, not source loss |
| 0 concepts; `refers to` bound to 3 literal names | no — same reason, and narrowly fixable |
| `Monday` admitted GLOBAL | no |
| pronouns in summary entity lists | no — P5 proved summary entities do not gate retrieval |
| project_qdrant 52 s fixed cost | no — throughput, not correctness |

Nothing here meets the bar. All of it is recorded for **P16 retrieval
qualification**, where the question is whether answers are supported — not
whether these counters are high.

**Keep both probes as permanent canaries.** They fail in opposite directions,
which is exactly what makes the pair useful: the transcript catches
conversational noise becoming knowledge, this file catches clean prose
producing none.
