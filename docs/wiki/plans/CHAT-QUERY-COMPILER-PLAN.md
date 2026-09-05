---
title: "PLAN — CHAT-QUERY-COMPILER-V1: a conversation-aware query compiler and a task-authority synthesis contract in front of the existing retrieval engines"
change_id: CHAT-QUERY-COMPILER-V1
date: 2026-09-05
owner: King (architecture) · governance (execution)
last_reviewed: 2026-09-05
last_touched: 2026-09-05
status: planned
register: 11.84
package: orchestrator/orchestrator/api/{ui.py,chat.py,fast.py,hybrid.py}, shared/polymath_shared/{chat_plan.py (new), answer_synthesis.py, query_receipts.py}, frontend/src/App.tsx, tests/determinism/test_chat_compiler_*.py (new)
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
│ MULTI-QUERY RETRIEVAL        │  existing FAST/HYBRID/GRAPH │
│ per query, query provenance  │                            │
└──────────────┬───────────────┘                            │
               ▼                                            │
┌──────────────────────────────┐                            │
│ MERGE · RERANK · DEDUPE      │  RRF by query weight, ≤10 per rerank call
└──────────────┬───────────────┘                            │
               ▼                                            │
┌──────────────────────────────┐                            │
│ COVERAGE / GAP CHECK         │  must_answer dimensions ✓/✗ │
└──────────────┬───────────────┘                            │
               └──────────────┬─────────────────────────────┘
                              ▼
                    ┌──────────────────────┐
                    │ FINAL SYNTHESIS      │  original request + resolved request
                    │ task authority       │  + conversation + evidence + coverage
                    │ factual authority    │
                    └──────────────────────┘
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

## 4. Phases and gates (assert before commit; targets fixed here, before the work)

Baseline set B = 30 logged single-turn questions (cinema 10, ecom-meta 10, field-evidence 10) with gold chunk ids, plus the conversation fixtures in §5. Baseline numbers are measured **first** and written into the work-log before any change.

| Phase | Change | Gate (must hold to promote) |
|---|---|---|
| P0.a hygiene | exam framing out of the core prompt; `/chat` default HYBRID + truthful `meta.mode`; `/chat/stream` receipts; reranker cap/batching | receipts on 100 % of stream turns; 40-doc rerank 200; single-turn suite green |
| P0.b compiler, **shadow** | compile every stream turn, receipt the plan, change nothing else | fallback rate < 5 % on B; task-verb preserved on 100 % of fixtures; p50 compile ≤ 2.5 s |
| P0.c compiled retrieval + no-retrieval routing | retrieve on compiled queries; skip retrieval for `conversation` policy | follow-up fixtures: gold chunk hit@10 ≥ 0.8 (baseline measured, expected ≪ 0.5); TRANSFORM/CONTINUE fixtures: 0 retrievals fired; B hit@10 not below baseline − 0.05 |
| P0.d synthesis v2 | authority split, used_evidence + legend in the answer event | "final prompt" fixture produces the artifact; factual fixture (§5 #6) keeps ≥ baseline citation precision; no "evidence doesn't contain" on artifact tasks |
| P0.e carry v2 | used-only carry, reranked, cap 8 | off-topic turn-1 chunk absent from turn-3 legend; prompt tokens per turn ≤ baseline |
| P1.a decomposition + coverage | 1–4 typed queries, gap check, one targeted second pass | multi-dimension fixture: every dimension ✓ or explicitly flagged weak; wall p50 ≤ baseline + 3 s |
| P1.b context selection | admission floor + per-document cap before the prompt | evidence items in prompt ≤ 24 with no drop in citation precision on B |
| P1.c runtime unification | ChatRuntime; `/chat` == `/chat/stream` modulo transport | same plan + same evidence ids for the same request on both routes (determinism test) |
| P1.d conversation regression suite | §5 frozen, including the owner's exact video-gen conversation | suite in CI (determinism.yml) |

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
10. **The owner's exact conversation** (video-gen prompt thread) frozen as a fixture; expected: turn N produces the final prompt with no retrieval.

## 6. Compiler model and cost

- Cheap lane from the existing pool with strict JSON output; candidates: gemini-3.1-flash-lite lanes (already qualified for strict schema), mistral-small-2603 via OpenRouter. Own limiter key; canary 8/8 valid plans on the fixtures before enabling; never share `limiter_key=default`.
- Budget: ≤ 2.5 s p50, ≤ 600 output tokens. Expected net latency effect on B: neutral to positive (one compile replaces several irrelevant retrievals on conversational turns; single-turn factual questions pay the compile).

## 7. Rejected alternatives

- **Regex/keyword intent router** — rejected: reference resolution ("that", "the final one") and task/knowledge separation need language understanding; QUERY-ROUTER-V1 stays for `/ask` knowledge routes.
- **Piping chat into `/retrieve/plan`** — rejected: its reformulations are TRAIL research signals; the *pattern* (one need → several queries, merge by query id) is borrowed, the planner is not.
- **Carrying all retrieved chunks** — rejected: measured noise propagation; only used evidence carries.
- **Letting the compiler rewrite the task** — rejected by guard 3.2.1; the search optimizer would drift the request.
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
