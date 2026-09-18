---
title: "NAMED-SOURCE-CONSTRAINT-DIAGNOSIS-V1 — where explicit source constraints are lost in ranking"
date: 2026-09-18
last_reviewed: 2026-09-18
status: "DIAGNOSIS (pre-implementation; owner-directed, no repair applied)"
owner: "@king"
scope: "Architecture-level causal diagnosis of pmap_* named-source rank loss + the RELATED-evidence epistemic-output design requirement. No code change. No boost, no weight tuning, no gold change."
---

# Named-source constraint loss — causal diagnosis

Owner directive (2026-09-18): do NOT repair the named-document MRR issue. Produce an architecture-level
diagnosis first — determine whether Polymath is losing an *explicit user constraint* during
retrieval/ranking. Evidence below is from the deployed code (HEAD `d86eb62`, branch `production`) + a
live instrumented probe of `pmap_murch_blink`, `pmap_lumet`, `pmap_savecat` through the real engine
(`orchestrator.api.chat_retrieval.chat_retrieve_mode`). Method: read-only. No repair applied.

## Verdict
**Yes — the explicit named-source constraint is lost, and it is lost at the RERANKER.** The signal
that should win *already exists and is correct upstream* (the Profile Scout nominates the named
document at rank #1 in all three cases; it wins fusion), but the cross-encoder reranker — the final
ordering authority — re-sorts purely on `(q0_text, chunk_text)` semantic relevance with no document
identity, no scout rank, no lane rank, and no constraint signal. General high-density reference
textbooks out-rerank the named source's own prose and bury it.

## Causal trace (live, `pmap_murch_blink` = "In Walter Murch's book, what is the blink theory of editing?")

| Stage | Result for the named gold doc (*In the Blink of an Eye*) | Verdict |
|---|---|---|
| q0 → interpreted constraints | `intent=DEFINITION`, `exact_terms=[]`, `user_constraints=[]`, no source/author/title field | constraint **not captured** |
| Scout nomination | **rank #1** of 8 (fused 0.0328), above Dancyger/Mascelli | **correct** |
| profile/pMAP localization | profile-expansion adds `p0 target=Murch-doc`, but `target` is stripped at the retrieval boundary → becomes a global search "Walter Murch's editing principles" | target **dropped** |
| child retrieval | Murch chunks retrieved; **hierarchical rank 0**, **dense rank 1** | **recall fine** |
| per-lane ranks | Murch best chunk hR=0/dR=1; another hR=1/dR=7/sR=3 | top of lanes |
| RRF / fusion | Murch **highest fused score 0.0568** | **wins fusion** |
| **reranker** | Murch best **rerank 5.34 (6th of 15)**; Ed Hooks 9.46, Rabiger 7.47, Glebas 7.24 | **loses here** |
| final evidence | Murch recovered to doc rank 3 by a post-rerank diversity pass, still below two general texts | rank 3 → MRR 0.33 |

Same pattern, all three cases: **scout rank #1 → competitive/top fused → reranked 4th–6th → final doc rank 3–4.**
`pmap_savecat` even captured `exact_terms=['Save the Cat','fifteen beats']` and still lost at rerank —
proving lexical capture alone cannot help, because lane-C (BM25) only feeds fusion and **rerank overrides fusion**.

## Answers to the ten questions
1. **Interpretation preserve the constraint?** No. `ChatPlan`/`CompiledQuery` have no source/author/title
   field (`chat_plan.py:113-164`); `exact_terms` regex `_S_EXACT` matches only ALL-CAPS/quoted/unit tokens,
   never mixed-case "Murch" (`chat_plan.py:104-110,184-196`); the compiler is *designed to strip* source
   names ("NEVER put a title itself in a query", `chat_plan.py:524-525`). The constraint survives only as
   plain q0 tokens.
2. **Scout nominate the source?** Yes, decisively — **rank #1 in all three cases**. The scout is not the fault.
3. **pMAP localize into the source?** At the lane level yes (Murch hierarchical rank 0), but localization is
   *semantic* (`profile_nominate`/`search_parent_maps` over the q0 vector, `chat_retrieval.py:319-333`), not
   named-source-keyed; it worked only because the named doc is also the top semantic match, and the signal is
   discarded downstream.
4. **Answer-bearing child retrieved?** Yes — multiple Murch chunks with strong lane ranks. This is a pure
   **ranking** loss, not a recall loss.
5. **Where exactly is rank lost?** **The reranker** (cross-encoder, `rerank.py:117-174`), the final ordering
   authority. It re-sorts by pure `(q0, chunk_text)` relevance and drops the named source from fusion-#1 to
   rerank-6th.
6. **Why does each doc above it outrank it?** Their chunks are more topically saturated with the query's
   vocabulary, so the constraint-blind cross-encoder scores them higher (9.46/7.47 vs 5.34). It sees only
   chunk text vs q0 text — a general textbook's dense on-topic paragraph beats the named book's narrative prose.
7. **Does the fusion/reranker contract distinguish semantic relevance from constraint satisfaction?** **No.**
   The reranker is the sole final signal and is pure semantic relevance. Fusion carries dense+sparse+hierarchical
   *as fused ranks* (`candidate_engine.py:968-1052`) — doc identity enters only to *suppress* (per-doc vote
   halving, region demotion), never to satisfy a constraint. No candidate carries a "satisfies the named source"
   bit. The one hard per-doc scope (`document_ids`, DOCUMENT-SCOPED-RETRIEVE-V1) is **rejected by the chat engine
   with 422** (`retrieve.py:193-198`) and is never derived from q0.
8. **Do HYBRID/GRAPH/WILDCARD dilute a signal FAST preserves?** For named-source: **no** — the loss is at the
   mode-independent reranker; all modes lose. For the *sensitivity* single-targets (FAST #1, others #2): partly —
   extra lanes admit more competitor chunks into the reranked prefix, so gold FAST keeps at #1 slips to #2. That
   is "more candidates reaching a constraint-blind reranker," not a distinct constraint signal being diluted.
   Common root cause: reranker constraint-blindness.
9. **General issue for "according to X" / "in document X" / "what did author X say" / section-scoped?** **Yes,
   general.** All three probed forms fail identically. Any "answer FROM this named source/scope" intent is
   handled as a plain topical query; the source/scope constraint has no representation, no query-side resolver,
   and no ranking effect. Section/chapter scope fails the same way (no scope filter from q0; `document_ids`
   rejected by the chat engine).
10. **Smallest generalized architectural repair (when required).** The winning signal already exists (scout
    nominates the named doc #1) and is thrown away. Smallest generalized repair = make **explicit-constraint
    satisfaction a first-class ranking dimension, distinct from semantic relevance, applied ONLY when q0 carries
    an explicit source/scope constraint**:
    - (i) **Detect** an explicit source/scope constraint in q0 ("in/according to/from <source>", "in document X",
      chapter/section scope) → a structured constraint field on `ChatPlan` (new).
    - (ii) **Resolve** it to doc_id(s)/scope. A query-side source resolver is the confirmed missing piece — but
      the scout already supplies most of it (its #1 nomination *is* the resolution).
    - (iii) **Apply** constraint satisfaction as a distinct ordering term combined with the rerank score (or a
      doc-scoped retrieval) when the constraint is explicit + confidently resolved — NOT by tuning RRF/rerank
      weights.
    - **Gate:** only when the constraint is explicit. A bare topical query ("what is the blink theory of
      editing?" with no named source) keeps pure semantic ranking. This is generalized, not a Murch boost, not
      weight tuning.

## The design decision the owner must sanction before implementation
The repair necessarily makes a scout HIT (or a resolved named-source) **add rank** — a deliberate change from
the current law "the scout informs, never gates; a miss never subtracts; a hit never adds." Today the scout is
purely advisory (conditions the compiler's titles channel + adds global profile-expansion subqueries, with no
downstream ranking effect — `ui.py:1803-1839,1892`). Fixing named-source ranking requires the scout (or an
explicit-constraint resolver) to become a **bounded ranking signal when — and only when — the query states an
explicit constraint.** That boundary (advisory for topical queries, authoritative for explicit-constraint
queries) is the architectural choice to confirm.

## Separate design requirement — RELATED-evidence epistemic output (record, do NOT implement here)
Owner: loose-but-grounded related evidence is not inherently a failure. Polymath should eventually distinguish
answer/evidence epistemic grades — **DIRECT · PARTIAL · RELATED · SYNTHETIC_INSIGHT** — and, when direct support
is absent, state what could not be established and then present grounded related material, clearly separating
corpus-supported statements from derived interpretation.

Status: **NOT an established active contract** → recorded as a design requirement for subsequent work, per owner
instruction; not implemented here. Adjacent existing pieces to build on (not the same thing): claim-level
`EVIDENCE_STATES = UNSUPPORTED|PARTIAL|CONFLICTING|SUPPORTED` (`evidence_resolution.py:29`, drives P10 resolution
rounds) and per-claim `epistemics{certainty,attributed,attribution_source,negated}` in synthesis
(`answer_synthesis.py:362-380`). This also reframes the qualification's "unsupported hallucination" gate: a future
RELATED/SYNTHETIC_INSIGHT output is legitimate grounded material, not a hallucination, provided it is graded and
the absence of direct support is stated.

## Out of scope (this diagnosis)
No repair applied. No Murch-specific boost. No RRF/reranker weight tuning. No gold-label change. Implementation of
either the constraint-satisfaction ranking dimension or the epistemic-output grades awaits explicit owner
authorization.
