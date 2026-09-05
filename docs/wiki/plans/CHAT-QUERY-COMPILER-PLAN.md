---
title: "PLAN — CHAT-QUERY-COMPILER-V1: a conversation-aware query compiler and a task-authority synthesis contract in front of the existing retrieval engines"
change_id: CHAT-QUERY-COMPILER-V1
date: 2026-09-05
owner: King (architecture) · governance (execution)
last_reviewed: 2026-09-05
last_touched: 2026-09-05
revision: 3 (+ CHAT-RETRIEVAL-V2: three independent lanes fused at child level, cross-encoder as the common judge, composition after relevance, query-aspect coverage)
status: planned
register: 11.84
package: orchestrator/orchestrator/api/{ui.py,chat.py,fast.py,hybrid.py}, shared/polymath_shared/{chat_plan.py (new), chat_retrieval_v2.py (new), hybrid.py, pass1.py, answer_synthesis.py, query_receipts.py}, frontend/src/App.tsx, tests/determinism/test_chat_compiler_*.py + test_chat_retrieval_v2_*.py (new)
architecture_impact: "Adds a cognitive layer between the conversation and retrieval (CHAT-INTENT-PLAN-V1) and replaces the evidence-absolute synthesis contract with task authority + factual authority. FAST/HYBRID/GRAPH engines, ingestion, extraction, Neo4j/Qdrant projection and the GraphRAG extraction contract are untouched. /chat and /chat/stream converge on one ChatRuntime; receipts cover the streaming path; carry-context becomes used-evidence only."
---

# PLAN — CHAT-QUERY-COMPILER-V1

## 0. Thesis (owner, 2026-09-05)

> Polymath is currently a retrieval-first evidence QA system with an LLM renderer, not a conversational RAG assistant. Retrieval is fairly sophisticated. Its conversational query compiler is essentially missing.

The failure happens **before** retrieval (the raw utterance is the search query; "that", "the final one", pasted 800-word prompts all go straight to Qdrant) and **after** retrieval (the grounding block gives evidence authority over the *task*, so "what's the final prompt?" becomes "the evidence doesn't contain a final prompt").

Target sequence:

```
user + conversation
  → understand intent
  → resolve follow-up references
  → decide whether retrieval is needed
  → formulate 1–4 retrieval queries with jobs
  → retrieve (existing engines)
  → merge · rerank · dedupe · coverage check
  → synthesize against the RESOLVED task, with evidence as knowledge
```

## 1. Measured current state (2026-09-05, cinema corpus, main @ df0eeb5)

| Fact | Where | Consequence |
|---|---|---|
| Streaming chat retrieves with the **current message only**: `graph_retrieve(query, …)`, `fast_retrieve(query, …)`, `hybrid_fast_retrieve(query, …)` | `orchestrator/orchestrator/api/ui.py:1441,1479,1489` | follow-ups ("how does that connect to dopamine?") retrieve the pronoun, not the antecedent |
| History and carried chunks enter only at prompt build | `ui.py::_grounded_messages` (history[-12:], carry[:30], bundle[:48], graph_facts[:20]) | Polymath can *talk* with history but cannot *retrieve* with it |
| Carry = up to 30 previously **retrieved** chunks, newest first, regardless of use | `frontend/src/App.tsx:153-175` | turn-1 retrieval noise becomes turn-N "evidence" |
| Grounding block: "Everything you assert must come from the provided evidence"; "The user is STUDYING this material"; "end with a brief 'for the exam' note" | `ui.py::_LLM_GROUNDING` | evidence is authoritative over the task; every cinema answer ends with an exam note |
| FAST embeds the raw query; HYBRID feeds the raw query to sparse lexical, query-shape, entity cards and the reranker | `fast.py:506`, `hybrid.py` | pasted instructions (tone, format, length) pollute the embedding and the lexical lane |
| Existing router classifies FACT/PROCEDURE/CONCEPT/POLYMATH queries and defaults to CONCEPT | `shared/polymath_shared/query_router.py:18-21` | knowledge-representation routes; no place for "rewrite this", "continue that", "final version" |
| Existing multi-query planner is TRAIL-specific (seed / tension / communities / invariant / contrast) | `shared/polymath_shared/corpus_plan.py`, `POST /retrieve/plan` | proves one-need→many-queries; not a conversation interpreter |
| `/chat` default mode is LEGACY; response stamps `meta.mode = HYBRID` | `retrieval_modes.DEFAULT_MODE`, `chat.py::attach_evidence_rows` | 12,732 claims / 437 KB triple dump in 30–50 s, mislabeled |
| `/chat/stream` writes **no** query receipts | `query_receipts.record_query_receipt` only in `chat.py` | the UI's sessions are unauditable |
| Streamed answer meta = `{verdict: generated, abstained, synthesis_version}`; no legend, no used-evidence list | `ui.py` answer event | [S#] tags cannot be resolved by the client; carry cannot be restricted to used sources |
| Reranker sidecar OOMs above ~10–20 documents (MPS cap 3.5 GiB); HYBRID sends 10 | `sidecar_reranker.log` (21 × 500 in 1 h) | wider callers silently degrade to fusion order |
| Replay of three cinema questions via `/chat/stream` | this session | retrieval 7.3–9.9 s (lexical 1.3–1.8, dense 1.2–1.7, rerank 2.2), LLM 4.8–7.0 s, wall 14–16 s; answers grounded and well cited |
| Only single-turn synthesis tests exist | `tests/determinism/test_answer_synthesis.py` | multi-turn continuation and dense-prompt transformation are untested |
| Pass-1 default plan (`pass1-retrieval-v2`): document summaries 10, section summaries 12, global children 24, entity cards 8; compressed to `final_max_children 12` / `final_max_total_items 15`; `rrf_k 60`; "No thresholds invented here" | `shared/polymath_shared/pass1.py:38,64-87` | retrieval is recall-oriented by design; the candidate → synthesis compression already exists and must stay separate from breadth |
| A second, hard-coded profile: `query_shape.depth_plan()` = section 24, global child 40, sections/doc 8, children/section 4, final children 28, final total 32, neighbor expansion ±1 | `shared/polymath_shared/query_shape.py:88-99` | changing Pass-1 defaults does NOT change completeness queries — a dependency trap for any breadth change |
| Documented threshold trap: an author-bio chunk scored cosine 0.5955 and ranked #1 after rerank while the correct objectives map scored 0.4894 (#7); the design demotes noisy document regions instead of deleting them | `shared/polymath_shared/document_region.py:9-10`, `pass1.py:127` | a hard similarity threshold is not the noise fix |
| `HybridRetrievalPlan` (`hybrid-retrieval-v1`): document summaries 10, section summaries 10, dense child 20, lexical child 20, `max_documents 5`, `max_sections_per_document 2`, `max_children_per_section 3`, `global_child_rescue_max 3`, `lexical_rescue_max 3`, `mmr_enabled False` / `mmr_lambda 1.0` ("REJECTED_BY_R1D"), final 10 children / 12 items | `shared/polymath_shared/hybrid.py:55-81` | the two global child lanes feed four-lane **document** aggregation; only 3 + 3 chunks may bypass it |
| "lexical child hits (lexical cannot bypass hierarchy provenance)" — lexical and global-dense hits contribute to document routing, then a capped rescue path | `hybrid.py:261-290` | an exact lexical or precise dense chunk needs its document to win first |
| Doctrine comment: "SUMMARIES ROUTE / CHILDREN PROVE / GLOBAL CHILD SEARCH PROTECTS RECALL / LEXICAL SEARCH PROTECTS EXACT TERMINOLOGY" | `pass1.py:3`, `reach.py:23` | intent already names three experts; the implementation gives one of them authority over what survives |
| Candidate provenance exists only as a single `arrival` string (`SECTION_LED`, `NEIGHBOR_EXPANSION`, rescue arrivals) | `pass1.py:313-377,527` | multi-lane agreement cannot be expressed or rewarded |
| Repository contract: bootstrap from CONTINUITY-REPORT → register → work-logs, run guards, record the slice before mutation; contract changes need reverse-dependent verification; private package imports never cross process boundaries (orchestrator may depend on `shared`, never on worker/control internals) | `AGENTS.md` §1, §3, §5 | compiler and budget policy live in `shared` (deterministic policy) or cleanly in the orchestrator; no cross-layer import |

Retrieval quality on single-turn factual questions is **good** (180-degree rule: top 5 of 10 on-concept, reranker live and re-ordering). This plan does not rebuild it.

## 2. Target architecture

```
┌──────────────────────────────┐
│ USER + CONVERSATION          │  message, history[-8:], prior artifact summary
└──────────────┬───────────────┘
               ▼
┌──────────────────────────────┐
│ LLM CHAT QUERY COMPILER      │  cheap lane, strict JSON, ≤2.5 s budget
│ resolve intent + references  │
│ separate TASK from KNOWLEDGE │
│ retrieval / no retrieval     │
│ 1–4 typed search queries     │
└──────────────┬───────────────┘
               ├── NO RETRIEVAL ────────────────────────────┐
               ▼                                            │
┌──────────────────────────────┐                            │
│ BROAD RETRIEVAL              │  existing FAST/HYBRID/GRAPH │
│ per query, query provenance  │  retrieval_candidate_budget │
└──────────────┬───────────────┘                            │
               ▼                                            │
┌──────────────────────────────┐                            │
│ DEDUPE + RRF (normalized)    │  merged_candidate_budget ~80–120
└──────────────┬───────────────┘                            │
               ▼                                            │
┌──────────────────────────────┐                            │
│ RERANK / CONTEXT SELECTOR    │  selection_budget ~20–30, ≤10 docs per rerank call
└──────────────┬───────────────┘                            │
               ▼                                            │
┌──────────────────────────────┐                            │
│ COVERAGE / GAP CHECK         │  must_answer dimensions ✓/✗ │
└──────────────┬───────────────┘                            │
               └──────────────┬─────────────────────────────┘
                              ▼
                    ┌──────────────────────┐
                    │ FINAL SYNTHESIS      │  synthesis_evidence_budget ~12–18
                    │ task authority       │  original + resolved request, conversation,
                    │ factual authority    │  evidence, coverage
                    └──────────┬───────────┘
                               ▼
                    USED / CITED EVIDENCE IDS  → the only items eligible for carry
```

`/chat`, `/chat/stream` and MCP become transports over one `ChatRuntime` (`ChatRequest → ChatPlan → ChatRuntime{retrieval, evidence selection, synthesis}`).

## 3. Contracts

### 3.1 CHAT-INTENT-PLAN-V1 (compiler output, strict JSON)

```json
{
  "contract": "chat-intent-plan-v1",
  "original_request": "so what's the final prompt ?? for video gen",
  "resolved_request": "Produce the final video-generation prompt based on the prompt and requirements developed earlier in this conversation.",
  "antecedent": {"turn": -2, "kind": "assistant_artifact", "summary": "draft video-gen prompt v3"},
  "task_type": "CONTINUE_PRIOR_ARTIFACT",
  "evidence_policy": "conversation",
  "retrieval_required": false,
  "retrieval_goal": null,
  "queries": [],
  "entities": [],
  "must_answer": [],
  "user_constraints": ["keep the deliverable a single paste-ready prompt"],
  "response_type": "artifact",
  "compiler": {"model": "…", "wall_ms": 0, "fallback": false}
}
```

Enums:

- `task_type`: `GROUNDED_QA` · `GROUNDED_SYNTHESIS` · `CREATE_FROM_KNOWLEDGE` · `TRANSFORM_USER_CONTENT` · `CONTINUE_PRIOR_ARTIFACT` · `GENERAL_CONVERSATION`
- `evidence_policy`: `corpus_grounded` · `conversation` · `mixed`
- `queries[].type`: `PRIMARY` · `DEFINITION` · `MECHANISM` · `CAUSAL` · `COMPARISON` · `COUNTERPOINT` · `PROCEDURE` · `EXAMPLE` · `ENTITY` · `BRIDGE`
- `response_type`: `answer` · `artifact`

Each query: `{id, type, query, weight}`; `query` ≤ 32 words, topical content only (never tone, length, format or output instructions); ≤ 4 queries; exactly one `PRIMARY` when `retrieval_required`.

Worked examples (from the owner's analysis) are frozen as fixtures: video-gen "final prompt" (no retrieval), Brainrot prompt rewrite (`TRANSFORM_USER_CONTENT`, no retrieval), "how does that affect creativity though?" (antecedent resolved, three typed queries), "use my cinema books to make this prompt better" (`CREATE_FROM_KNOWLEDGE`, three queries), "do the authors agree or disagree?" (task preserved, per-author queries + contradictions query).

### 3.2 Compiler invariants (guards)

1. **The compiler never rewrites the task.** `original_request` and `resolved_request` both reach synthesis; queries are search representations only. A regression asserts the resolved request preserves the task verb (compare / rewrite / list / decide …) of the original.
2. **Bounded and cheap.** Input = current turn + last 4–8 turns + prior artifact summary; output ≤ 600 tokens; wall budget 2.5 s on a cheap lane (gemini-3.1-flash-lite / mistral-small class via the existing provider pool, its own limiter key, never `default`). Provider qualification rules apply: canary on readiness before it is enabled.
3. **Deterministic fallback.** Compiler failure, timeout or invalid JSON → `{task_type: GROUNDED_QA, retrieval_required: true, queries: [PRIMARY = raw message], compiler.fallback: true}`. Behavior is then exactly today's; the fallback rate is a receipted, surfaced number (silent-fallback accounting law).
4. **Receipted.** The plan is stored on the query receipt (`meta.chat_plan`) for every turn, including shadow mode.

### 3.3 Multi-query retrieval, merge, coverage

- One retrieval call per compiled query through the existing engines (`hybrid_fast_retrieve` default; mode from the UI still honoured). Results keep `query_id` provenance.
- Merge: RRF (k = 60, already the fusion constant) weighted by `queries[].weight`; dedupe by chunk id; document diversity via the existing per-side allocation.
- Rerank on the merged top-N with ≤ 10 documents per reranker call (measured OOM ceiling) until the sidecar's memory cap is raised.
- Coverage: for each `must_answer` dimension, mark ✓ if ≥ 2 merged rows come from a query of that dimension with rerank score above the admission floor, else ✗. One targeted second pass for a ✗ dimension (≤ 1 extra query), then hand `coverage` to synthesis: "cultural-impact evidence is weak — do not present it as well supported".

### 3.4 Synthesis contract v2 (replaces `_LLM_GROUNDING`)

Authority split, verbatim in the prompt:

```
USER INTENT HAS TASK AUTHORITY. CORPUS EVIDENCE HAS FACTUAL AUTHORITY.
First answer or perform the user's RESOLVED request.
Retrieved evidence is supporting knowledge. It does not define the task and
does not need to contain the requested final artifact verbatim.
When asked to create, rewrite, transform, organize, compare, combine, infer
or synthesize, perform that operation.
Never answer that "the evidence doesn't contain the final answer" merely
because the requested artifact must be constructed.
If a factual premise needed to complete the task is absent from the evidence,
name that missing premise specifically.
Conversation content and user-provided text may be transformed without
corpus evidence. Factual claims ABOUT THE CORPUS still carry [S#] tags.
```

- The study/exam framing leaves the core prompt. Style becomes a per-corpus profile (`corpora.profile.style` — e.g. `study`, `reference`, `creative`), defaulting to neutral.
- The prompt receives: original request, resolved request, task_type, evidence_policy, coverage, conversation window, evidence with [S#] legend.
- The answer event returns `used_evidence` (chunk ids derived from emitted [S#] tags), the legend, `task_type`, `retrieval_required`, `compiler.fallback`.

### 3.5 Carry-context v2

- Frontend carries only `used_evidence` from prior answers (never the retrieved inventory), newest first, cap 8.
- Backend reranks carried items against the `resolved_request` and drops those below the admission floor before they enter the prompt.
- Measured guard: a deliberately off-topic turn 1 must not surface in turn 3's legend.

### 3.6 Receipts for the streaming path

`/chat/stream` records `kind = chat_stream` receipts with wall_ms per phase (compile, retrieve per query, merge, generate), `meta.chat_plan`, legend, `used_evidence`, model, verdict. Same table, same retention.

### 3.7 Runtime unification and hygiene

- `ChatRuntime` shared by `/chat`, `/chat/stream`, MCP. `/chat` without `mode` → HYBRID (LEGACY only when explicitly requested); `meta.mode` reports the executed mode. The `ui.py` header stops claiming byte-identity with `/chat`.
- Reranker sidecar: raise the MPS cap (`PYTORCH_MPS_HIGH_WATERMARK_RATIO`) or batch scoring internally; regression: 40 documents rerank without a 500.

### 3.8 Three explicit budgets (breadth is not evidence)

Retrieval stays recall-oriented; the LLM must not swim in what recall brings back. Named budgets, each its own knob, each receipted:

| Budget | Meaning | Default to benchmark | Rule |
|---|---|---|---|
| `retrieval_candidate_budget` | per compiled query, per lane | children 40–60 (was 24), sections 20–30 (was 12), documents 10, entity cards 8 | raise **upstream** recall first |
| `merged_candidate_budget` | **global** pool after dedupe + RRF across all subqueries | 80–120 | never defined per query only: 4 subqueries × 30 = 120 raw hits before dedupe |
| `selection_budget` | after rerank / context selection | 20–30 | reranker calls ≤ 10 documents each until the sidecar cap is raised |
| `synthesis_evidence_budget` | items handed to the LLM | 12–18 (today 12/15) | held constant while breadth is raised; `final_max_children = 60` is the anti-pattern |

Order of operations for any breadth change: (1) raise candidate budgets, (2) measure whether the missing answer is now **present in the candidate pool**, (3) only if present-but-unselected, work on selection/rerank; never on breadth alone.

### 3.9 Funnel instrumentation — where noise dies

Every chat turn records, per compiled query and merged: `retrieved_candidates` → `after_dedupe` → `after_rrf` (with per-query provenance) → `after_rerank` → `selected_for_llm` → `actually_cited` (from [S#] tags). Each stage keeps chunk ids and ranks. "Retrieval gave me bad stuff" then resolves to exactly one of:

1. the correct chunk was never retrieved (breadth / query formulation);
2. retrieved at rank 47 and truncated (candidate budget);
3. survived rerank but lost final selection (selection rule);
4. reached the LLM and was ignored (synthesis / prompt).

First diagnostic before any cap moves (P0.0): for the owner's "final video prompt" conversation and the §5 fixtures, dump the top 100 candidates with their rank at each stage. A `polymath chat funnel <receipt_id>` CLI over the receipt prints this table.

### 3.10 RRF under multiple subqueries — provenance and amplification

With LLM-generated subqueries the same document can appear under several near-duplicate formulations. If each occurrence contributes independently, a document wins because the planner was redundant, not because its evidence is stronger. Rules:

- keep `query_id` provenance on every hit through merge;
- dedupe by chunk id before fusion; fuse once per (chunk, query) with the query's `weight`, and **normalize** per document so that N redundant subqueries cannot add more than one document-level vote;
- the merged pool is capped by `merged_candidate_budget`, not by the sum of per-query caps;
- receipt the per-query contribution of every selected item (the funnel makes redundancy visible).

### 3.11 Versioned retrieval behavior and the second profile

- `Pass1RetrievalPlan` is `pass1-retrieval-v2` and is under evaluation. Multi-query retrieval, new fusion or new final-selection rules ship as **`pass1-retrieval-v3`** or a separate **`CHAT-RETRIEVAL-PLAN-V1`**, never as silent edits to v2 underneath existing evaluations. Receipts carry the plan version.
- `query_shape.depth_plan()` hard-codes its own limits (section 24, global child 40, sections/doc 8, children/section 4, final 28/32). Any budget change applies to BOTH profiles, or the depth profile is derived from the same budget object. A regression asserts both profiles read their limits from one policy source.
- No hard similarity threshold is introduced (§1, document_region case). Noise is demoted by region role and lost at selection, not deleted at retrieval.

### 3.12 Ordering constraint

Carry-context v2 (§3.5) lands **before** any breadth increase: raising breadth with the current 30-chunk carry increases the pool of historical contamination. The phase order enforces this (P0.e precedes P1.a).

### 3.13 Where the code lives (AGENTS.md §5)

The compiler contract, budgets, fusion and selection policy are deterministic policy in `shared/polymath_shared/chat_plan.py` + `chat_budgets.py` (pure functions, unit-testable); the LLM call and the transports live in the orchestrator. No orchestrator import of worker/control internals. Contract changes get reverse-dependent verification (`/chat`, `/chat/stream`, MCP, `/ask` and TRAIL `/retrieve/plan` checked) and an ADR if the dependency map changes.

### 3.14 CHAT-RETRIEVAL-V2 — three retrieval experts, no absolute authority (owner, part 1)

Today's shape is "find documents → find sections → allow a few global-child rescues → allow a few lexical rescues": documents are disproportionately authoritative over what survives. V2 keeps the same three mechanisms but makes them **independent ways for a chunk to earn its way into the answer**, fused at the **child-evidence level**.

```
                    RESOLVED QUERY (+ optional typed subqueries)
                          │
          ┌───────────────┼───────────────┐
          ▼               ▼               ▼
   LANE A            LANE B           LANE C
 HIERARCHICAL     GLOBAL DENSE     GLOBAL SPARSE
 doc summaries    CHILD            CHILD
 → docs           all children     all children, BM25
 → sections       dense K 50–75    K 30–50
 → children       no doc prereq    no doc prereq
 (K 16 / 24;      arrival =        arrival =
  6 docs, ~12     GLOBAL_DENSE_    GLOBAL_SPARSE_
  sections, ~30   CHILD            CHILD
  children)
 arrival =
 HIERARCHICAL_ROUTE
          └───────────────┼───────────────┘
                          ▼
              UNION + DEDUPE (≈70–120 unique chunks, provenance kept)
                          ▼
              CROSS-ENCODER RERANK against resolved_request → top ≈30
                          ▼
              EVIDENCE COMPOSITION (after relevance):
                pure relevance → source diversity → query-aspect coverage
                → multi-lane agreement → limited neighbor expansion
                          ▼
              FINAL ≈15–20 chunks → SYNTHESIS
```

**Lane A — hierarchical route** ("which books/sections understand this question?"): the existing strongest conceptual path, kept for breadth and section context. Document summaries K 12–20 → 5–8 documents → section summaries K 20–30 → 2–4 children per section → ≈25–40 candidates. Runs **once**, on the primary resolved query.

**Lane B — global dense child** ("forget the book, which exact chunks answer me?"): embedding against ALL children, K 50–75, no document prerequisite, identity preserved through final selection. Catches the 500-page book with two relevant paragraphs whose summary never mentions the topic. Diversity without losing precision: of its final slots, ≈6 best chunks regardless of source + ≈4 best chunks from documents Lane A did not surface.

**Lane C — global sparse child** ("what literally matches what the user said?"): the existing Qdrant sparse BM25 against `routing_child`, K 30–50, no document prerequisite. Protects acronyms, identifiers, quoted phrases, numbers, commands, specific names ("RAPO", "FACS", "TS410", "System 1", "attention residue"). An exact lexical chunk may say "I don't care whether my book won document routing" — and survive. The 3-chunk `lexical_rescue_max` path is retired, not widened.

**Provenance on every candidate** (replaces the single `arrival` string):

```json
{"chunk_id": "…", "doc_id": "…", "parent_id": "…",
 "arrivals": ["HIERARCHICAL_ROUTE", "GLOBAL_DENSE_CHILD", "GLOBAL_SPARSE_CHILD"],
 "found_by_queries": ["q0", "q2"],
 "hierarchical_rank": 4, "dense_rank": 3, "lexical_rank": 1,
 "dense_score": 0.78, "lexical_score": 12.4, "rerank_score": 0.91}
```

**The cross-encoder is the common judge.** Cosine, BM25 and RRF are different scales and are never compared directly; lanes generate candidates, the Qwen reranker scores relevance to the `resolved_request` (in batches ≤ 10 until the sidecar cap is raised; §3.8). Lane scores remain as evidence of *how* a candidate was found. **Multi-lane agreement** (a chunk found by two or three independent experts) earns a bounded boost at composition time — a tie-breaker-plus, never a reordering of a clear relevance gap; the exact weight is a benchmarked constant recorded in the plan version.

**Diversity happens after relevance**, at the chunk level, restrained. Final ≈18: first 8 by pure relevance; next 6 relevance + source diversity; last 4 coverage/rescue. Or MMR only after the cross-encoder with `0.80 × relevance − 0.20 × redundancy`. The existing document-level MMR (`mmr_enabled=False`, rejected by R1D) is **not** switched back on — it diversified routing, not evidence.

**Query-aspect coverage** (ties to the compiler §3.1): the primary resolved query runs all three lanes; each typed subquery runs Lanes B and C only (document routing once, cost bounded). Every chunk remembers which query and which lane found it, so composition can report `PRIMARY ✓ 12 · MECHANISM ✓ 7 · HABIT ✓ 5 · RECOVERY ✓ 9` and the §3.3 gap check has real inputs.

**Budgets under V2** (instances of §3.8): per-lane candidate budgets as above → union 70–120 → rerank top ≈30 → final 15–20 (up from 10/12). The consequential change is not 10 → 20; it is that a precise child no longer needs its document to win first, and an exact match is no longer a 3-chunk rescue.

**Versioning:** ships as `CHAT-RETRIEVAL-V2` (`chat-retrieval-v2` plan version on every receipt); `hybrid-retrieval-v1` and `pass1-retrieval-v2` stay intact for `/retrieve`, `/ask` and TRAIL until each is migrated on its own evaluation. Both retrieval profiles (§3.11) read the V2 budget object.

**Terminology:** diversity is **MMR** (Maximal Marginal Relevance); MRR (Mean Reciprocal Rank) is the evaluation metric used in the gates.

## 4. Phases and gates (assert before commit; targets fixed here, before the work)

Baseline set B = 30 logged single-turn questions (cinema 10, ecom-meta 10, field-evidence 10) with gold chunk ids, plus the conversation fixtures in §5. Baseline numbers are measured **first** and written into the work-log before any change.

| Phase | Change | Gate (must hold to promote) |
|---|---|---|
| P0.0 funnel + baselines | stage-by-stage candidate receipts (§3.9) on the current pipeline; top-100 dump for the owner's video-prompt conversation and the §5 fixtures; baseline numbers for B | every chat turn has a complete funnel receipt; baseline table written into the work-log before any cap or prompt changes |
| P0.a hygiene | exam framing out of the core prompt; `/chat` default HYBRID + truthful `meta.mode`; `/chat/stream` receipts; reranker cap/batching | receipts on 100 % of stream turns; 40-doc rerank 200; single-turn suite green |
| P0.b compiler, **shadow** | compile every stream turn, receipt the plan, change nothing else | fallback rate < 5 % on B; task-verb preserved on 100 % of fixtures; p50 compile ≤ 2.5 s |
| P0.c compiled retrieval + no-retrieval routing | retrieve on compiled queries; skip retrieval for `conversation` policy | follow-up fixtures: gold chunk hit@10 ≥ 0.8 (baseline measured, expected ≪ 0.5); TRANSFORM/CONTINUE fixtures: 0 retrievals fired; B hit@10 not below baseline − 0.05 |
| P0.d synthesis v2 | authority split, used_evidence + legend in the answer event | "final prompt" fixture produces the artifact; factual fixture (§5 #6) keeps ≥ baseline citation precision; no "evidence doesn't contain" on artifact tasks |
| P0.e carry v2 | used-only carry, reranked, cap 8 | off-topic turn-1 chunk absent from turn-3 legend; prompt tokens per turn ≤ baseline |
| P1.a CHAT-RETRIEVAL-V2 lanes (after carry v2) | Lanes A/B/C as independent experts fused at child level with full provenance (§3.14); budgets as one policy object (§3.8) read by both profiles; rescue caps retired; `chat-retrieval-v2` receipts | on B: gold chunk present in the union ≥ 0.9 (baseline measured first); lexical fixture set (acronyms, identifiers, quoted phrases) hit@union = 1.0; per-lane arrival recorded on 100 % of candidates; `/retrieve`, `/ask`, TRAIL unchanged (reverse-dependent tests) |
| P1.b decomposition + aspect coverage | 1–4 typed queries; primary runs A+B+C, subqueries run B+C only; provenance-normalized fusion (§3.10); per-aspect candidate counts; one targeted second pass | multi-dimension fixture: every dimension ✓ or explicitly flagged weak; no document exceeds one vote per subquery; wall p50 ≤ baseline + 3 s |
| P1.c judge + composition | cross-encoder as the common judge over the union (batches ≤ 10); composition = 8 pure relevance → 6 relevance + source diversity → 4 coverage/rescue (or post-rerank MMR 0.8/0.2); bounded multi-lane agreement boost; final 15–20 | funnel: gold chunk survives selection on ≥ 0.85 of B where in the union; MRR@final ≥ baseline; no final set with > 60 % of chunks from one document when ≥ 3 documents scored within 0.1 of the top; citation precision ≥ baseline |
| P1.d runtime unification | ChatRuntime; `/chat` == `/chat/stream` == MCP modulo transport; compiler, budgets and selection live in the shared policy layer | same plan + same evidence ids for the same request on all routes (determinism test) |
| P1.e conversation regression suite | §5 frozen, including the owner's exact video-gen conversation, plus the funnel expectations per fixture | suite in CI (determinism.yml) |

Rollout: feature flag `POLYMATH_CHAT_COMPILER` = `off` → `shadow` → `on`; each step is its own commit with its gate numbers in the work-log.

## 5. Acceptance tests (new `tests/determinism/test_chat_compiler_*.py`)

1. **Long pasted prompt → "make this better"** — `TRANSFORM_USER_CONTENT`, `retrieval_required = false`, answer is the transformed prompt; zero retrieval calls (spy on the engines).
2. **Prior assistant artifact → "give me the final version"** — antecedent resolved to the artifact turn; `CONTINUE_PRIOR_ARTIFACT`; artifact produced; no retrieval.
3. **"Using the evidence we just discussed, build X"** — antecedent subject resolved into `resolved_request`; `CREATE_FROM_KNOWLEDGE`; queries topical; answer cites [S#].
4. **800-word instructions** — every compiled query ≤ 32 words, contains none of a fixed list of instruction tokens (tone, format, words, markdown, bullet, JSON, respond, output).
5. **Corpus hits containing "final" cannot redefine the task** — with a stubbed retriever returning "Final Decisions" chunks, the answer still produces the requested artifact.
6. **Factual source question** — `GROUNDED_QA`; strict grounding unchanged; citation precision ≥ baseline; abstention still fires when evidence is absent.
7. **Task-verb preservation** — for 20 fixtures, the resolved request keeps the original's task class (compare / list / decide / rewrite …).
8. **Fallback** — compiler timeout → today's behavior, `compiler.fallback = true`, receipt written.
9. **Carry hygiene** — turn-1 noise absent from turn-3 legend; carried items ≤ 8.
10a. **Exact-terminology recall** — queries containing an identifier, acronym or quoted phrase present in exactly one chunk: that chunk is in the union and in the final set even when its document loses Lane A.
10b. **Precise child beats document routing** — a fixture corpus where the best chunk sits in a document whose summary never mentions the topic: Lane B surfaces it; final set contains it.
10c. **Provenance and agreement** — every candidate carries `arrivals` and `found_by_queries`; a chunk found by all three lanes is ranked at or above an otherwise-equal single-lane chunk, and never above one with a clearly higher rerank score.
10d. **Composition restraint** — with one document holding the top three by relevance and two other documents within 0.1, the final 18 include the other documents without displacing the top eight.
10. **The owner's exact conversation** (video-gen prompt thread) frozen as a fixture; expected: turn N produces the final prompt with no retrieval.

## 6. Compiler model and cost

- Cheap lane from the existing pool with strict JSON output; candidates: gemini-3.1-flash-lite lanes (already qualified for strict schema), mistral-small-2603 via OpenRouter. Own limiter key; canary 8/8 valid plans on the fixtures before enabling; never share `limiter_key=default`.
- Budget: ≤ 2.5 s p50, ≤ 600 output tokens. Expected net latency effect on B: neutral to positive (one compile replaces several irrelevant retrievals on conversational turns; single-turn factual questions pay the compile).

## 7. Rejected alternatives

- **Regex/keyword intent router** — rejected: reference resolution ("that", "the final one") and task/knowledge separation need language understanding; QUERY-ROUTER-V1 stays for `/ask` knowledge routes.
- **Piping chat into `/retrieve/plan`** — rejected: its reformulations are TRAIL research signals; the *pattern* (one need → several queries, merge by query id) is borrowed, the planner is not.
- **Carrying all retrieved chunks** — rejected: measured noise propagation; only used evidence carries.
- **Letting the compiler rewrite the task** — rejected by guard 3.2.1; the search optimizer would drift the request.
- **Switching the existing document-level MMR back on** — rejected: it diversifies routing, R1D rejected it, and V2 wants chunk-level diversity after relevance.
- **Widening `lexical_rescue_max` / `global_child_rescue_max`** — rejected: a bigger rescue path still makes documents authoritative; V2 removes the prerequisite instead.
- **Comparing cosine, BM25 and RRF scores directly** — rejected: different scales; the cross-encoder is the only cross-lane judge.
- **A hard similarity threshold as the noise fix** — rejected: the measured author-bio (0.5955) vs objectives-map (0.4894) case; noise is demoted by region and lost at selection.
- **Raising `final_max_children` to get recall** — rejected: breadth and synthesis evidence are separate budgets; only the candidate pool grows.
- **Per-query budgets only** — rejected: four subqueries multiply hits; the merged pool has its own cap and provenance-normalized fusion.
- **Editing `pass1-retrieval-v2` in place** — rejected: versioned behavior (`v3` / `CHAT-RETRIEVAL-PLAN-V1`) so existing evaluations stay comparable.
- **Touching ingestion / extraction / projection for this** — out of scope; the repository contract already isolates read behavior from those stages.

## 8. Out of scope

Ingestion, entity extraction, Neo4j/Qdrant projection, the GraphRAG extraction contract, TRAIL `/retrieve/plan`, the `/ask` router.

## 9. Open questions for the owner

1. Compiler lane: gemini-3.1-flash-lite (fastest, already canaried for strict schema) or a local model for zero marginal cost?
2. `GENERAL_CONVERSATION`: answer without corpus at all, or always attach a light corpus check?
3. Prior artifacts: carry the full artifact text or a compiler-written summary plus the last artifact verbatim?
4. Per-corpus style profiles: which corpora keep the study/exam framing (cysa-study-v1 presumably), and what is the default for cinema / ecom?

## 10. Governance

- Register row 11.84 (PLANNED). Each phase lands as its own work-log with Contract / Changes / Proof / Rejected claims / Open contract gaps and its gate numbers.
- The conversation fixtures (§5) contain no third-party personal data; the owner's own conversation is stored with the artifact text only.
