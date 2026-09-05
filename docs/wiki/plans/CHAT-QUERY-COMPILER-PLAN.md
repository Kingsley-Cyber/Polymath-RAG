---
title: "PLAN — CHAT-QUERY-COMPILER-V1: a conversation-aware query compiler and a task-authority synthesis contract in front of the existing retrieval engines"
change_id: CHAT-QUERY-COMPILER-V1
date: 2026-09-05
owner: King (architecture) · governance (execution)
last_reviewed: 2026-09-05
last_touched: 2026-09-05
revision: 5 (+ migration protections, CandidateEvidence / RetrievalCandidateEngine / CandidateBudget contracts, exact_terms in the compiler output, the pre-promotion regression suite, the three bold rules)
status: planned
register: 11.84
package: orchestrator/orchestrator/api/{ui.py,chat.py,fast.py,hybrid.py}, shared/polymath_shared/{chat_plan.py (new), chat_retrieval_v2.py (new), hybrid.py, pass1.py, answer_synthesis.py, query_receipts.py}, frontend/src/App.tsx, tests/determinism/test_chat_compiler_*.py + test_chat_retrieval_v2_*.py (new)
architecture_impact: "Adds a cognitive layer between the conversation and retrieval (CHAT-INTENT-PLAN-V1) and replaces the evidence-absolute synthesis contract with task authority + factual authority. FAST/HYBRID/GRAPH engines, ingestion, extraction, Neo4j/Qdrant projection and the GraphRAG extraction contract are untouched. /chat and /chat/stream converge on one ChatRuntime; receipts cover the streaming path; carry-context becomes used-evidence only."
---

# PLAN — CHAT-QUERY-COMPILER-V1

## 0. Thesis (owner, 2026-09-05)

> Polymath is currently a retrieval-first evidence QA system with an LLM renderer, not a conversational RAG assistant. Retrieval is fairly sophisticated. Its conversational query compiler is essentially missing.

The failure happens **before** retrieval (the raw utterance is the search query; "that", "the final one", pasted 800-word prompts all go straight to Qdrant) and **after** retrieval (the grounding block gives evidence authority over the *task*, so "what's the final prompt?" becomes "the evidence doesn't contain a final prompt").

**Three rules for the executor, in bold:** **Do not re-ingest.** **Do not preserve document routing as evidence authority.** **Do not add multi-query search until the full-corpus lexical fallback and the duplicate sparse paths are dealt with.**

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
| Lanes run **sequentially** inside `hybrid_retrieve`: pass-1 dense lanes → `lexical_search` (line 229) → latent → `rerank_children` (line 437); no thread pool or gather anywhere in `hybrid.py` / `pass1.py` / `fast.py` | `shared/polymath_shared/hybrid.py:177-437` | adding a lane adds its full latency; measured HYBRID retrieval 7.3–9.9 s |
| GRAPH = HYBRID first, then hop-1 expansion with the D2-qualified 8-seed / 20-fact caps; WILDCARD = FAST first, then the divergent sweep (`latent_top_k 24` per surface, `candidate_parents 8`, `max_bridges 3`, "maximize surprise subject to usefulness", separate `wildcard` lane) | `orchestrator/orchestrator/api/graph.py:6-8`, `shared/polymath_shared/divergent.py:9,27,65-67,95` | richer modes accumulate serial stages; the bounded caps and the separate wildcard lane are already right |
| `SINGLE-EMBED-V1`: pass-1 exposes the one query vector; hybrid reuses it and re-embeds only when a lane needs a different text | `pass1.py:196`, `hybrid.py:314` | the one-embedding principle exists and is to be extended, not invented |
| `query_shape.py`: "an LLM planning hop costs 1–3 s, while the whole retrieval including reranking is ~2.6 s" — the reason the earlier planner stayed deterministic | `shared/polymath_shared/query_shape.py:17-18` | the compiler must be deliberately cheap (§3.2, §3.16) |
| Degradation and liveness are first-class: `meta.degraded`, `meta.liveness.{live,suspect}`, latent `degraded = deepen_failed` | `hybrid.py:324-335`, `orchestrator/api/hybrid.py:219` | deadline-based lane degradation fits the existing contract rather than adding silent fallbacks |
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
  "semantic_queries": [],
  "exact_terms": [],
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

**Two query representations, not one.** `semantic_queries` are the rewritten dense-lane texts; `exact_terms` are identifiers, acronyms, quoted phrases, numbers and commands **preserved verbatim from the original input** ("RAPO", "FACS", "TS410", "System 1"). An LLM that rewrites "RAPO text-to-video" into "automated prompt optimization techniques for video generation" produces a good dense query and a useless BM25 query; the sparse lane therefore searches `exact_terms` + the original wording, never the rewrite alone.

**One string never does four jobs:**

```
task / shape detection   → resolved_request      (plan_for_query on the RESOLVED text, not the raw follow-up)
dense search             → semantic_queries
BM25 / exact search      → original terms + exact_terms
generation               → original_request + resolved_request
```

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

### 3.15 Five retrieval primitives; modes are compositions (owner, part 2)

```
A = HIERARCHICAL DENSE      document → section → children
B = GLOBAL DENSE CHILD      query → every child directly
C = GLOBAL SPARSE CHILD     BM25 / exact terminology → every child directly
G = GRAPH EXPANSION         entities/relationships from selected evidence (hop-1, bounded)
W = WILDCARD FRONTIER       latent abstraction / transfer search (separate lane)
```

| Mode | Retrieval | Notes |
|---|---|---|
| VECTOR / FAST | A + B | even the fastest mode gets document intelligence AND chunk precision; neither controls the other |
| **HYBRID (default chat mode)** | A + B + C | C is cheap and protects exact terminology; A protects context, B semantic precision, C exact match |
| GRAPH | A + B + C → G | not another retrieval engine: HYBRID evidence → 4–8 strongest entity seeds → hop-1 → ≤ 20 facts |
| WILDCARD | A + B (+ C) ∥ W | normal answer plus ≤ 3 grounded bridges from a separate frontier lane, never mixed into evidence ranking |

The compiler may add `graph_useful: true/false` (`RELATIONAL_SYNTHESIS` tasks: "how are X, Y and Z connected?"); GRAPH mode is honoured either way, but expansion stays tiny when the question is definitional.

### 3.16 Latency architecture (enforced, not aspirational)

```
STAGE 0  LLM QUERY COMPILER         the only unavoidable serial stage; fast lane, ≤ 600 output tokens
STAGE 1  ONE EMBEDDING              resolved_request → one qvec, reused by every dense lane (SINGLE-EMBED-V1 extended)
STAGE 2  CONCURRENT SEARCH          T=0: doc-summary K16 ∥ section-summary K24 ∥ global child K50 ∥ BM25 child K40
                                    (BM25 needs no embedding — it starts as soon as the compiled text exists)
STAGE 3  UNION → CHUNK-ID DEDUPE    70–120 unique candidates with provenance
STAGE 4  ONE CROSS-ENCODER CALL     not one per lane, not one per subquery; batches ≤ 10 docs until the sidecar cap is raised
STAGE 5  EVIDENCE COMPOSER          deterministic, metadata only (§3.17)
STAGE 6  G / W (optional, bounded)  graph after evidence; wildcard frontier overlaps stage 2 (§3.19)
STAGE 7  GENERATION                 begins immediately after composition
```

- **Subqueries:** the primary resolved query runs A + B + C; each typed subquery runs **B + C only**. Document routing happens once. Example: hierarchy 30 + primary dense 50 + primary BM25 40 + 3 × (dense 20 + BM25 15) = 195 raw hits → ≈70–120 after dedupe → one rerank → top 25–35.
- **Wall-clock budgets, not only K:** compiler (hard), core retrieval (hard), reranker (hard), graph / wildcard (bounded optional). A supplementary lane that misses its deadline never hangs the turn: the core result proceeds and the receipt records `degraded: [sparse_timeout | graph_timeout | wildcard_timeout | latent_timeout]` through the existing `meta.degraded` / `liveness` contract. Starting budgets (to benchmark): compiler 2.5 s, core lanes 3.0 s, rerank 3.0 s, graph 1.5 s, wildcard 2.5 s.
- **Design rules frozen:** (1) wall ≈ slowest parallel lane + one rerank, never the sum of lanes; (2) HYBRID is not materially slower than VECTOR; (3) GRAPH may be somewhat slower than HYBRID because seeds depend on evidence; (4) WILDCARD may be somewhat slower than HYBRID but its sweep overlaps core retrieval and stays at ≤ 3 bridges; (5) **more recall increases candidates, never serial model calls**.

### 3.17 Evidence composer (deterministic, metadata only)

Final context ≈ 18 chunks, starting slot policy (benchmarked, not frozen):

```
8  pure cross-encoder relevance
4  alternate document / source coverage
3  exact / sparse winners (Lane C arrivals)
3  subquery / aspect coverage
```

A chunk may satisfy several slots (dedupe may yield fewer than 18). Diversity uses `doc_id` / `parent_id` / `rerank_score` only — no extra model, no extra embedding: first 8 unrestricted; afterwards a soft maximum of 3 chunks per document unless the score gap to the next document is large. Multi-lane agreement (`arrivals` length) is a bounded composition boost; the cross-encoder stays the relevance authority.

### 3.18 GRAPH stays bounded

`planner → A+B+C ∥ → one rerank → top evidence → 4–8 seeds → hop-1 → ≤ 20 facts → LLM`. Graph's job is relationships chunks cannot expose (A causes B, X contradicts Y, concept → mechanism chains). The existing 8-seed / 20-fact caps stay the default; 3 hops / 100 entities / 500 facts is never the default. Graph adds a bounded stage measured in hundreds of milliseconds, not a research mode.

### 3.19 WILDCARD as a parallel frontier

Today: FAST → then the divergent sweep (the baseline defines the obvious neighbourhood). New: the latent candidate sweep runs **beside** core retrieval from T=0; only the "is this too obvious?" **baseline exclusion** and validation wait for the core result. `latent_top_k 24`, `candidate_parents 8`, `max_bridges 3`, separate `wildcard` lane and the "maximize surprise subject to usefulness and source grounding" objective are kept as they are. Bridges join synthesis separately and never enter evidence ranking.

### 3.20 Operating profiles to benchmark (starting budgets, not measured values)

| Mode | Core candidates | Extra work | Final evidence | Latency rule |
|---|---|---|---|---|
| VECTOR | ~60–90 | none | ~15–18 | baseline |
| HYBRID | ~80–120 | BM25 in parallel | ~15–20 | p50 ≤ VECTOR + 0.5 s |
| GRAPH | as HYBRID | ≤ 8 seeds / ≤ 20 facts | ~15–20 + graph | p50 ≤ HYBRID + 1.5 s |
| WILDCARD | ~60–100 | ≤ 3 bridges | ~15–18 + bridges | p50 ≤ HYBRID + 2.0 s |

### 3.21 Migration protections (owner, part 3 — each verified in the code on 2026-09-05)

This is a **query-time migration**. Document/section vectors, child vectors, child BM25, entity cards, Neo4j and latent surfaces already exist; nothing is re-ingested.

| # | Risk | Where | Protection |
|---|---|---|---|
| 1 | **Sparse runs twice.** `FastSearcher` already fires a sparse BM25 companion probe beside every dense routing search (incl. `routing_child`), and HYBRID separately runs `_lexical_search()` over children — a new `GLOBAL_SPARSE_CHILD` lane on top would double-vote exact-match chunks | `fast.py:55-63`, `orchestrator/api/hybrid.py:100` | explicit primitives: `HIERARCHICAL_DENSE` (doc, section, filtered child dense), `GLOBAL_DENSE_CHILD`, `GLOBAL_SPARSE_CHILD`; sparse doc/section routing may stay as an optional recall helper with its **own provenance**, never voting the same child twice; dedupe by chunk id before fusion |
| 2 | **Postgres lexical fallback = latency disaster.** `_lexical_search()` falls back from Qdrant BM25 to loading the corpus's children from Postgres and scoring them in Python (`SELECT … FROM chunks` + `lexical_score`) | `orchestrator/api/hybrid.py:100-138` | interactive chat: Qdrant BM25 is the only qualified implementation; unavailable → `sparse_lane = DEGRADED`, continue with dense; the Python scan stays for diagnostics/legacy only (never on the chat path; 500k children × 4 subqueries is forbidden by test) |
| 3 | **Manual plan copy.** `HybridRetrievalPlan` is converted field by field into `Pass1RetrievalPlan` before Pass-1 runs; a field added to one plan never reaches the engine | `shared/polymath_shared/hybrid.py:199-213` | eliminate the seam: one `RetrievalCandidatePlan` / `CandidateBudget` consumed by the engine, mode wrappers only enable/disable lanes |
| 4 | **Two budget generations.** FAST's Pass-1 defaults are newer and broader; HYBRID declares older defaults; GRAPH inherits HYBRID | `pass1.py:64-87` vs `hybrid.py:55-81` | one `CandidateBudget` authority (hierarchy_doc_k, hierarchy_section_k, hierarchy_child_k, global_dense_k, global_sparse_k, merged_candidate_max, rerank_max, synthesis_max); modes override only what they genuinely need |
| 5 | **GRAPH treats document winners as the evidence structure** with an `unassigned_rescue_evidence` bucket for anything outside them | `orchestrator/api/graph.py:217-248` | canonical `CandidateEvidence[]` list; document/section grouping becomes presentation metadata; a global child winner is first-class evidence, not a rescue |
| 6 | **Graph seeding must use all final evidence.** Expansion already receives final evidence chunk ids for authorization | `graph.py` (D2 invariant) | preserve: entities on a `GLOBAL_DENSE_CHILD` winner are eligible seeds exactly like hierarchy-derived evidence |
| 7 | **GRAPH re-embeds the query** for its entity-card probe after HYBRID already embedded it | `graph.py:151` (`_embed_query(query)`) | one primary `qvec` from the plan; entity cards reuse it |
| 8 | **WILDCARD re-embeds after FAST** (`divergent_retrieve` calls `embed_query(query)`) | `divergent.py:99`, `wildcard.py:34` | share the primary vector |
| 9 | **Concurrency hazard in wildcard:** the query vector is stored on a function attribute (`_children_of._qvec = v`) and read later | `wildcard.py:57-64` | explicit immutable arguments (`children_of(parent_id, qvec)`) or a closure over one fixed `qvec`; never function-attribute state once lanes run concurrently |
| 10 | **`FastSearcher` carries mutable request state** (`self.latency`, `self._hidden_cache`, `self._sparse_query`) and mutates timing totals per search | `fast.py:53-77` | do not wrap one mutable `FastSearcher` in `asyncio.gather`; introduce an immutable `SearchContext {qvec, sparse_query, corpus, hidden_generations}`; each lane returns `{hits, latency, degradation}`; telemetry merged afterwards |
| 11 | **Corpus and generation filtering stay centralized.** `FastSearcher` enforces `corpus_id`, `representation_kind`, doc/parent filters and hidden blue/green generations | `fast.py:31,65-84` | the new global child search goes through the same adapter (or reproduces every filter, proven by tests 15–16); a raw Qdrant call that leaks another corpus or a rebuilding generation is the highest-risk correctness bug here |
| 12 | **Compiler needs two query representations** | §3.1 | `semantic_queries` + `exact_terms` |
| 13 | **Subqueries must not invoke the full hierarchy** | §3.16 | primary → A+B+C; subqueries → B+C |
| 14 | **Query-shape logic runs on the raw string** (`plan_for_query(query, …)` in fast/hybrid/graph) — "yeah give me all of those" misses the depth mode that "List all CySA+ domains and subdomains" triggers | `query_shape.py:128`, `fast.py:484`, `hybrid.py:172`, `graph.py:99` | `plan_for_query(resolved_request)` |
| 15 | **Preserve original exact language separately** | §3.1 | the four-string rule |
| 16 | **WILDCARD's "obvious" baseline is whatever FAST returned** (excludes surfaced parents, dampens same-document chunks) | `divergent.py:95-139` | baseline = the **final normal candidate neighbourhood** of the new engine, so the frontier never returns what Lane B already found |
| 17 | **Frontend carries 30 retrieved chunks regardless of use** | `App.tsx:153-175` | response contract returns `retrieval.{candidates, selected_evidence, used_evidence}`; future turns carry `used_evidence` only (§3.5) — fixed **before** breadth grows |
| 18 | **Up to 150 s before retrieval begins:** `POLYMATH_EMBED_WAKE_BUDGET_S = 150` and `_await_embedder()` waits for a parked embedder | `fast.py:258-261` | interactive policy: UI active → embedder stays warm; interactive wake budget tight (seconds, not minutes); ingest/non-interactive keeps its own policy. Cold-start tolerance is not retrieval latency |

### 3.22 Shared contracts introduced by the migration

```
RetrievalCandidateEngine v1  (candidate-retrieval-v1)
   HIERARCHICAL_DENSE ∥ GLOBAL_DENSE_CHILD ∥ GLOBAL_SPARSE_CHILD  →  CandidateEvidence[]

CandidateEvidence
   chunk_id · doc_id · parent_id · source_name · text
   arrivals[] · query_ids[]
   dense_rank? · sparse_rank? · hierarchy_rank? · rerank_score?
   is_neighbor · region_role

CandidateBudget                    (one authority; modes override only what they need)
   hierarchy_doc_k · hierarchy_section_k · hierarchy_child_k
   global_dense_k · global_sparse_k
   merged_candidate_max · rerank_max · synthesis_max

SearchContext (immutable)          qvec · sparse_query · exact_terms · corpus · hidden_generations
```

Every mode consumes `CandidateEvidence[]`: VECTOR = A+B, HYBRID = A+B+C, GRAPH = HYBRID candidates + G, WILDCARD = VECTOR/HYBRID baseline + W. Versions `pass1-retrieval-v2`, `hybrid-retrieval-v1`, `graph-retrieval-v1`, `divergent-retrieval-v1` are **not** overwritten; `candidate-retrieval-v1` and `chat-retrieval-plan-v1` are introduced and the existing modes adapt to them behind a rollback boundary. Establishing the shared candidate boundary is a dependency change: preflight, dependency map / reverse-dependent checks, work-log, and an ADR (AGENTS.md).

### 3.23 What is not migrated

Ingestion, chunking, parent construction, document summaries, section summaries, Qdrant projection, BM25 projection, entity extraction, canonical facts, Neo4j projection, latent enrichment. Changing ingestion at the same time would make it impossible to attribute any improvement to the query architecture.

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
| P1.a CHAT-RETRIEVAL-V2 lanes (after carry v2) | `RetrievalCandidateEngine v1` + `CandidateEvidence` + `CandidateBudget` (§3.22); Lanes A/B/C as independent experts fused at child level with full provenance (§3.14); **seams closed first**: duplicate sparse paths deduped (§3.21 #1), Postgres lexical fallback off the chat path (#2), plan-copy seam removed (#3), one budget authority (#4), corpus/generation filters through the shared adapter (#11), `plan_for_query` on the resolved request (#14); rescue caps retired; `chat-retrieval-v2` receipts | on B: gold chunk present in the union ≥ 0.9 (baseline measured first); lexical fixture set (acronyms, identifiers, quoted phrases) hit@union = 1.0; per-lane arrival recorded on 100 % of candidates; `/retrieve`, `/ask`, TRAIL unchanged (reverse-dependent tests) |
| P1.b decomposition + aspect coverage | 1–4 typed queries; primary runs A+B+C, subqueries run B+C only; provenance-normalized fusion (§3.10); per-aspect candidate counts; one targeted second pass | multi-dimension fixture: every dimension ✓ or explicitly flagged weak; no document exceeds one vote per subquery; wall p50 ≤ baseline + 3 s |
| P1.c judge + composition | cross-encoder as the common judge over the union (batches ≤ 10); composition = 8 pure relevance → 6 relevance + source diversity → 4 coverage/rescue (or post-rerank MMR 0.8/0.2); bounded multi-lane agreement boost; final 15–20 | funnel: gold chunk survives selection on ≥ 0.85 of B where in the union; MRR@final ≥ baseline; no final set with > 60 % of chunks from one document when ≥ 3 documents scored within 0.1 of the top; citation precision ≥ baseline |
| P1.d concurrency + one rerank | immutable `SearchContext`; lanes as concurrent tasks from one embedding shared with graph entity cards and the wildcard frontier (#7–#9); BM25 starts without the embedding; union → dedupe → exactly one reranker call per turn (batched); wall-clock budgets with `degraded` receipts; interactive embedder wake budget (#18) | on B: exactly 1 embedding per distinct query text and exactly 1 rerank call per turn (spy tests); HYBRID p50 ≤ VECTOR p50 + 0.5 s; a lane forced past its deadline yields a `degraded` receipt and a complete answer in ≤ core budget + rerank budget |
| P1.e mode recomposition | VECTOR = A+B, HYBRID = A+B+C (default), GRAPH = HYBRID → bounded G over the canonical `CandidateEvidence[]` (no `unassigned_rescue_evidence`; global winners seed the graph, #5–#6), WILDCARD = core ∥ W with the baseline = final normal candidate neighbourhood (#16); evidence composer slots (§3.17) | mode-equivalence tests (same primitives → same candidate union); GRAPH p50 ≤ HYBRID + 1.5 s with ≤ 8 seeds / ≤ 20 facts; WILDCARD p50 ≤ HYBRID + 2.0 s with ≤ 3 bridges never in the evidence list |
| P1.f runtime unification | ChatRuntime; `/chat` == `/chat/stream` == MCP modulo transport; compiler, budgets, lanes, composer live in the shared policy layer | same plan + same evidence ids for the same request on all routes (determinism test) |
| P1.g conversation regression suite | §5 frozen, including the owner's exact video-gen conversation, plus the funnel and latency expectations per fixture | suite in CI (determinism.yml) |

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
11. **One embedding, one rerank** — spies on the embedder and reranker clients: a HYBRID turn with three subqueries embeds each distinct query text once and calls the reranker once (batched).
12. **Deadline degradation** — with the sparse lane stubbed to exceed its budget, the turn completes within core + rerank budget, `meta.degraded` contains `sparse_timeout`, and the receipt records it.
13. **Wildcard separation** — bridges ≤ 3, present only in the `wildcard` lane, absent from `evidence_rows`, and the sweep starts before core retrieval finishes (timestamps in the funnel receipt).
14. **Graph bounded** — GRAPH mode on a definitional question with `graph_useful: false` expands ≤ 2 seeds; on a relational question ≤ 8 seeds / ≤ 20 facts; never more.
10. **The owner's exact conversation** (video-gen prompt thread) frozen as a fixture; expected: turn N produces the final prompt with no retrieval.

## 5b. Pre-promotion regression suite for CHAT-RETRIEVAL-V2 (frozen before P1.a is promoted)

```
 1. Exact acronym            RAPO is found by the sparse child lane (exact_terms), present in the final set.
 2. Hidden relevant paragraph the book loses document routing; its exact child still reaches the final candidates.
 3. Document-context question hierarchy still contributes useful contextual chunks.
 4. Multi-book synthesis      strong evidence from several books survives composition.
 5. Single-source dominance   diversity never discards obviously superior evidence (score-gap rule).
 6. Follow-up                 "how does that work?" resolves the prior subject before retrieval.
 7. Long pasted prompt        retrieval queries carry the information need, not 800 words of formatting.
 8. Completeness              "list all…" still triggers depth / neighbor behavior (shape on the resolved request).
 9. Graph                     a GLOBAL_DENSE_CHILD winner can seed graph relationships.
10. Wildcard                  a normal candidate is never returned as a supposedly novel bridge.
11. Sparse unavailable        no full-corpus Python scan in interactive chat; sparse_lane = DEGRADED instead.
12. Latency                   parallel A+B+C stays within the retrieval budget; one embedding, one rerank.
13. Degraded reranker         candidate recall intact; fusion order used; degradation receipted.
14. Carry context             unused retrieved noise is not carried forward.
15. Corpus isolation          no candidate from another corpus through the new child lanes.
16. Hidden-generation isolation  rebuilding projection chunks never leak.
```

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
- **Sequential mode choreography (GRAPH = HYBRID then G; WILDCARD = FAST then W)** — rejected: richer modes must not accumulate serial stages; only the parts that genuinely depend on evidence (seeds, baseline exclusion) wait.
- **Running full hierarchical routing per subquery** — rejected: 4 × routing explodes latency; the primary decides geography, subqueries hunt precise evidence with B + C.
- **One reranker call per lane or per subquery** — rejected: the union is reranked once.
- **Mixing wildcard bridges into evidence ranking** — rejected: separate objective, separate lane, ≤ 3 bridges (already the design).
- **Unbounded graph traversal as a default** — rejected: 8 seeds / 20 facts stay.
- **A hard similarity threshold as the noise fix** — rejected: the measured author-bio (0.5955) vs objectives-map (0.4894) case; noise is demoted by region and lost at selection.
- **Raising `final_max_children` to get recall** — rejected: breadth and synthesis evidence are separate budgets; only the candidate pool grows.
- **Per-query budgets only** — rejected: four subqueries multiply hits; the merged pool has its own cap and provenance-normalized fusion.
- **Editing `pass1-retrieval-v2` in place** — rejected: versioned behavior (`v3` / `CHAT-RETRIEVAL-PLAN-V1`) so existing evaluations stay comparable.
- **Touching ingestion / extraction / projection for this** — out of scope; the repository contract already isolates read behavior from those stages.

## 8. Out of scope

Ingestion, entity extraction, Neo4j/Qdrant projection, the GraphRAG extraction contract, TRAIL `/retrieve/plan`, the `/ask` router.

## 9. Open questions for the owner — with the defaults the unattended run assumes if unanswered

1. Compiler lane — **default: gemini-3.1-flash-lite via the existing pool** (already strict-schema qualified; own limiter key); a local model is a later swap behind the same contract.
2. `GENERAL_CONVERSATION` — **default: no corpus retrieval**; the answer may offer a corpus check in one line.
3. Prior artifacts — **default: last artifact verbatim + compiler-written summary of earlier ones**, within the compiler's input budget.
4. Style profiles — **default: study/exam framing only for `cysa-study-v1`; neutral everywhere else** (`corpora.profile.style`).

## 10. Governance

- Register row 11.84 (PLANNED). Each phase lands as its own work-log with Contract / Changes / Proof / Rejected claims / Open contract gaps and its gate numbers.
- The conversation fixtures (§5) contain no third-party personal data; the owner's own conversation is stored with the artifact text only.

## 11. Unattended execution protocol (owner: "I'll leave you to implement everything E2E")

1. **Bootstrap** per AGENTS.md: CONTINUITY-REPORT → register → two newest work-logs → guards → fleet-truth query; confirm `HEAD` matches the recorded state.
2. **This document is the ledger.** The executor re-reads §4 from disk before every phase (never from memory); owner edits between phases take effect at the next phase boundary.
3. **Per phase:** baseline numbers → failing tests → implementation → gate numbers written into that phase's work-log (Contract / Changes / Proof / Rejected claims / Open contract gaps, front matter, register row) → guard → commit on the branch → `--ff-only` into main → push → CI green before the next phase starts.
4. **Fleet safety:** edits to fleet-loaded code are batched per phase (one fence round each); no ingestion / extraction / projection files are touched; shadow mode precedes any behavior change on the live chat.
5. **Halt conditions (the only ones):** a gate missed twice with the numbers reported; a provider canary failing on readiness; a change that cannot meet its gate without altering a frozen contract or a §9 default; a security- or credential-touching step. Everything else is decided by the executor and recorded under Rejected claims.
6. **Order:** P0.0 → P0.a → P0.b → P0.c → P0.d → P0.e → P1.a → P1.b → P1.c → P1.d → P1.e → P1.f → P1.g. Carry v2 (P0.e) must be merged before any breadth change (P1.a); shadow mode (P0.b) before compiled retrieval (P0.c); the P1.a seams (§3.21 #1–#4, #11, #14) and the §5b suite before multi-query (P1.b). Nothing under §3.23 is touched at any phase.
7. **Completion report:** one final message with the before/after table of every gate, the commits, the CI runs, and the remaining open gaps.
