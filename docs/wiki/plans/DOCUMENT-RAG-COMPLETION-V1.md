---
title: "DOCUMENT-RAG-COMPLETION-V1 — grounded-learning retrieval: the owner's scattered design joined into one plan"
date: 2026-09-23
last_reviewed: 2026-09-23
status: "PLAN OF RECORD — admitted 2026-09-23 (register 11.421). Owner decisions D1–D8 answered the same day. Execution slices S0–S9; S0 (easy fixes) started on branch fix/document-rag-easy-wins."
owner: "@king"
scope: "Chat retrieval + synthesis over document corpora (cinema first): compiler contract, retrieval lineage and concept routing, path-aware admission, synthesis contract, measurement. No new public mode; GNN excluded; ingestion unchanged except optional projections named below."
amends: "FINAL-RETRIEVAL-ROUTING-SYNTHESIS-V1 l.39 ('cross-encoder = final judge') and §47; WLK2C q0-primary non-displacement; ELITE-MODE §6 rule 1 and the WILDCARD novelty term (for chat document RAG)."
---

# DOCUMENT-RAG-COMPLETION-V1

## 0. Why this plan exists

**The owner's objective** (2026-09-23, verbatim): "I want a RAG pipeline that taps into latent or subdued chunks, since a lot
of my corpus knowledge is documents I'm not well versed on, so I may not know how to query properly. I'm using it to improve my
knowledge." Sequencing: document RAG is completed before CODE-KNOWLEDGE-V1.

**Most of the design already exists, in four owner-authorized plans that were never joined** (audit §10):
- FINAL §7: a technique per profile field per mode;
- FINAL §40–42 and ELITE §6: WILDCARD as the abstract-grounded frontier;
- WLK2A: judge a chunk against the bridge that retrieved it;
- LQF-V2: different ranking authorities at different stages.

**The root cause is measured** (audit §9, §12): the retrieval path is lost at five points, and every enrichment chunk is
judged against q0 alone. Survival from the judge's pool into the evidence: dense 75%, dual-read 56%, latent 37%, SEEALSO 33%,
lift 0%.

Audit: `docs/wiki/reports/2026-09-23/ENRICHMENT-SURFACES-AUDIT.md`. Compiler input:
`docs/document-rag/inputs/2026-09-23-rag-compiler-contract.md`.

## 1. Owner decisions (2026-09-23)

| # | Decision | Answer |
|---|---|---|
| D1 | Governing objective | **Grounded learning value adopted** (§2) |
| D2 | Retrieval for corpus-learning questions | **Always retrieve.** Only explicit non-corpus tasks may skip (reverses backlog B20) |
| D3 | Resolution lift | **Off now**; repair later as a PRECISION route |
| D4 | v3.2 atoms beside the vNext atoms | **Paused.** Use the existing profile routes first. Re-project only if they are shown unable to supply the needed concepts, and then with correct deduplication |
| D5 | Bridge planning | **Merged into the one compiler call.** Its inputs exist before the call (audit §15) |
| D6 | Latency budget | **Measure first, then set.** Provisional end-to-end ceilings: HYBRID ≤ 60 s, WILDCARD ≤ 90 s |
| D7 | Live-run budget | The owner's standing rule: 5–8 turns first, each on the owner's word |
| D8 | GRAPH traversal | **One hop only** (SEEALSO / concept neighbour). Bounded multi-hop stays deferred |

## 2. Part A — the governing law

**Objective: grounded learning value.** The question is the starting point of a learning need, not a complete
specification. A source chunk earns its place in five ways:
- a direct answer;
- a prerequisite;
- a mechanism;
- a correction;
- a transfer, with its limits stated.

In every case the source supports the connection the path depends on. Novelty, abstraction, domain difference or document
count alone earn nothing.

**Two judgments, never merged:**
- *Worth following* (retrieval): can this probe or bridge find evidence for a named need?
- *Worth including* (admission): does the retrieved source, with its path attached, support a connection that advances the
  learning need and add something beyond the current selection?

**Amendments (D1):**

| Old law | New law |
|---|---|
| FINAL l.39 "cross-encoder = final judge" | The cross-encoder is a retrieval-stage signal. Admission is path-aware (Part D) |
| FINAL §47 "LATENT may never substitute for DIRECT"; WLK2C non-displacement; ELITE §6 rule 1 | An unsupported connection never enters. A supported prerequisite or correction may outrank a redundant literal match. The answer states when a direct answer is missing, and never fills it with an unsupported tangent |
| The WILDCARD novelty term (ELITE §6) | Novelty is not a boost. It means only "adds beyond the selection" |

**Kept invariants:**
- profile, atom, lift, SEEALSO and bridge metadata are routing only, never evidence;
- source chunks are evidence, and claims carry citations;
- the raw query, exact terms and global child retrieval always survive (FINAL §53);
- no fourth public mode; GNN excluded;
- corpus scoping on every shared surface;
- no quotas and no guaranteed seats for any lineage.

## 3. Target flow

```
question ─┬─ Profile Scout (profile items: concepts / theories / seealso / questions, stored vectors)
          └─ q0 lanes start (dense / sparse / hierarchy) ─────────────────────────────┐
ONE compiler call  →  plan: learning_need · probes {text, lineage, expected_contribution, │
  (fed profile item TEXT)     evidence_requirement} · bridges · synthesis_targets     │
concurrent probe retrieval (each probe keeps its own id + path) ─────────────────────────┤
fusion with per-probe local winners (LQF-V2), duplicates merged with all paths kept ─────┘
admission: stage 1 signals (worth following) → stage 2 path-aware judgment (worth including)
contribution-based, bundle-aware selection (sees the current selection)
synthesis: roles + paths + synthesis targets → answer that shows its connections
receipts at every stage
```

## 4. Part B — the compiler contract

The owner's input spec, as amended in audit §15.
- **Extend `ChatPlan` / `CompiledQuery`; no new service.**
  - Fill `retrieval_goal` with the learning need (never filled today).
  - Add, per probe: `expected_contribution` ("investigate X because it could help understand Y") and `evidence_requirement`
    ("look for Z").
  - Add, per plan: inquiry dimensions (precision / depth / transfer / cross-document synthesis) and `synthesis_targets`.
  - Keep the fields compact.
- **Fix `target`.** Stop writing doc ids into `target`; source references go to their own field. Check the consumers first
  (`graft callers`).
- **One planning call, including bridges (D5).** The compiler receives the selected profile items as TEXT with item
  references (Part C selection) and writes both the plan and the bridges. The separate bridge-compiler call is retired
  behind a flag.
- **Retrieval required for corpus-learning questions (D2).** The no-retrieval route stays only for explicit non-corpus tasks
  (rewrite / convert / continue a non-corpus artifact) and explicit "don't search" requests.
- **Degradation.** When the new fields are missing or invalid, retrieval continues and the probe is marked `unexplained`.
  Nothing invents a justification, treats an unexplained path as verified, or skips corpus retrieval.
- **Reasoning per stage, by provider + endpoint + model:** compiler, judge, synthesis and fallbacks, each set separately.
  The emitted settings are recorded (S1). Raw-HTTP switches go at the top level (S0 / E1).
- **No `depends_on`** until a dependent route is admitted.
- **Measured:** compile-phase time and the lane fallback rate, before and after (today: gemma 2.8%; the Alibaba lanes fail
  29 / 36).

## 5. Part C — retrieval execution

- **Lineage end to end.** Every probe keeps its own `query_id`, text and lineage class (USER / PROFILE / BRIDGE /
  CONCEPT / LATENT / GRAPH / PRECISION), carried through fusion, admission and synthesis. The probes are:
  - compiler subqueries and bridges;
  - profile-item probes;
  - the latent-kind search;
  - the dual-read route;
  - the graph destination.

  Lanes D–H stop reusing q0's id (`candidate_engine.py:814–919`).
- **Concept / theory routing** (audit §11; D4 means the profile store first):
  - *select*: q0 MaxSim over the profile `concepts` / `theories` / `seealso` multivectors (one corpus-filtered query; the
    vectors are already stored, so no embed call); score the items locally; keep the top k per mode, from measurement;
  - *global door*: the item vector searches children across all documents (dense, plus sparse for specialist terms);
  - *home door*: the item vector searches its own document's parent maps → children;
  - *neighbour door* (GRAPH, one hop, D8): the item vector searches other documents' items → their maps → children;
    optionally precomputed offline as a concept-neighbour table (no LLM).
- **Concurrency.** Lanes D–I run concurrently under `lane_deadline_s` (today they run one after another, outside it). q0
  lanes start as soon as the embedding exists, which may be during compilation.
- **Resolution lift off (D3).** Repair later as a PRECISION lineage: query-relevant term selection and every term kept.
- **Atom re-projection deferred (D4).** It becomes a slice only if the S6 measurements show the profile routes cannot supply
  the needed concepts, and then with deduplication across generations.

## 6. Part D — path-aware admission

**Stage 1, worth following:** cheap signals over every candidate: the cross-encoder against the probe text and against q0,
plus fusion rank and local-winner status. These build the shortlist. There is no standalone q0 eligibility floor, and a
subquery match alone admits nothing.

**Stage 2, worth including.** The judge sees:
- the original question and the learning need;
- the path: subquery / bridge / concept, its expected contribution and evidence requirement;
- the source text;
- the current selection.

It answers three questions:
1. Does the source support the relationship the path depends on, including the conditions it needs?
2. Does that supported relationship advance the learning need?
3. What does it add beyond the evidence already selected?

**Candidate implementations, chosen by evidence (S7):**
- (i) the cross-encoder with a composed path query;
- (ii) one batched LLM judge over the shortlist, sized to the D6 budget.

The winner must pass the Part F fixtures within the latency budget. Attaching bridge text to the reranker is a hypothesis,
not proof.

**Selection is by contribution, bundle-aware:**
- chunks needed to establish a connection are kept together;
- evidence needed to answer the explicit question is preserved;
- a supported correction or prerequisite may outrank a redundant literal match;
- no quotas.

## 7. Part E — the synthesis contract

- **The prompt carries each row's role** (direct / prerequisite / mechanism / correction / transfer), its path and the plan's
  synthesis targets. Today `ui.py:3519` drops the role labels (E3).
- **The answer:**
  - explains each discovered concept, why it matters to the question, and which source supports it;
  - labels analogies and inferences with their limits;
  - states missing direct answers;
  - reconciles documents without inventing consensus.
- **WILDCARD is the full embodiment:**
  - every profile field competes;
  - the latent and profile-item frontiers go through the same admission;
  - DERIVED `[A#]` stays bound to its proving `[S#]` (ELITE §6).
- **Synthesis reasoning is tuned separately from the compiler's**, starting from thinking-off (11.411) and adjusted only by
  measurement.

## 8. Part F — measurement and acceptance

**First (S1–S2):**
- receipts: per-lane `lane_ms`; per-probe lineage and local-winner survival; `latent_selection`; compile sub-steps; emitted
  reasoning settings;
- a timing trace of one slow turn;
- one dropped chunk traced through every judge;
- D6 is then set from these numbers.

**Fixtures** (owner-labelled where the verdict is subjective):
1. A useful latent source that is dropped today survives, with its path (WLK-10 wc01 class: FACS / Laban / Murch).
2. A vague bridge fails (a lift `A1` term; a merely topical bridge) even when its subquery matches.
3. Direct evidence stays eligible.
4. A faulty premise is corrected by source material.
5. A cross-domain transfer is either established with its mapping and limits, or rejected.
6. Document synthesis keeps disagreements and scope differences visible.
7. Explicit scope is respected by every operation.
8. Duplicate routes merge without losing provenance.

**Metrics:** local-winner survival per lineage; chain precision; groundedness to the question and the learning need;
unsupported claims = 0; per-phase latency against D6.

**Baselines:** WLK-10 `BASELINE-2026-09-18.json` + `SURVIVAL-2026-09-18.json`; CA5 64×4; the main harness; this audit's
`receipt_audit.json` for lane survival. Receipts carry harness runs too: filter owner-style turns (model synthesis, distinct
questions) before comparing.

**Live runs:** 5–8 first, each on the owner's word (D7).

## 9. Execution slices

Each slice is admitted on its own (work-log, register row, asserting tests, guards). New behaviour sits behind a flag,
default off. Merge + bounce happens on the owner's word.

| Slice | Content | Proof |
|---|---|---|
| **S0** | Easy fixes on branch `fix/document-rag-easy-wins`: E1 compiler raw-HTTP reasoning placement; E4 WILDCARD atom-frontier receipt; E8 resolution lift off (D3); E2 bridge labels use real text | stand-in wire test (E1); unit tests; merge + bounce on the owner's word; then re-measure the lane fallbacks |
| S1 | E5 receipts | receipt fields present on a live turn |
| S2 | E6 traces → set the D6 budget | trace JSON in `docs/wiki/experiments/` |
| S3 | E3 synthesis roles + coverage lines; E7 `target` fix | unit tests; prompt inspection |
| S4 | Part B compiler contract, including merged bridge planning fed profile-item text and D2 always-retrieve | flag-gated; compile time + fallback measured; the plan-validation tests stay green |
| S5 | Part C lineage end to end + concurrent lanes D–I + q0 during compilation | flag-gated; per-probe receipts; latency trace |
| S6 | Part C concept routing: selection + global / home doors; neighbour door for GRAPH (one hop) | flag-gated; fixture 1 reach; D4 check (do the profile routes supply the concepts?) |
| S7 | Part D: stage-1 signals + stage-2 judge candidates, A/B | fixtures 1–3 + metrics; latency against D6 |
| S8 | Part E synthesis contract + WILDCARD alignment | fixtures 4–6; answer inspection |
| S9 | Acceptance: 5–8 live turns, expanded only on the owner's word; flag defaults flipped only on the owner's word | the full fixture table + baselines |
| later | the lift repaired as PRECISION; atom re-projection only if S6 shows it is needed (D4); multi-hop only if the owner lifts the deferral (D8) | — |

## 10. Do not do

- Remove or stop producing profile fields. Load profile metadata as evidence.
- Add quotas, novelty boosts or guaranteed seats. Use a standalone q0 floor as eligibility.
- Add a fourth public mode, touch GNN, or start CODE-KNOWLEDGE-V1 slices.
- Re-project atoms before the D4 condition is met. Re-ingest or re-embed the corpus.
- Build multi-hop traversal (D8). Add `depends_on` before a dependent route exists.
- Push, merge or bounce without the owner's word. Run live spend beyond D7. Run determinism suites without
  `-k "not test_live_"`.
